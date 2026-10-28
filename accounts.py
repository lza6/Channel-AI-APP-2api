"""Account layer: persistent guest-account store + self-healing session pool.

Why this exists
---------------
The upstream allows one chat per XMPP stream, so throughput == number of live
sessions. This module keeps a warm pool of logged-in guest accounts, reuses
persisted credentials instead of registering new accounts on every restart, and
replaces dead sessions in the background so a burst of requests does not all pay
the ~2.8 s register+login cost.

Layout
------
AccountStore   : accounts.jsonl  (username/password/device_id/jid/publictoken + counters)
AccountFactory : provision() = reuse stored account, else register a brand-new guest
SessionPool    : min_idle warm sessions, max_size ceiling, background refill, retry
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field

from channel_client import ChannelClient, ChannelError, rest


@dataclass
class Account:
    username: str
    password: str
    device_id: str
    jid: str
    publictoken: str | None = None
    country: str = "US"
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    uses: int = 0
    fails: int = 0
    disabled: bool = False
    note: str = ""

    def key(self) -> str:
        return self.username


class AccountStore:
    """Tiny append-only JSONL store (rewritten compactly on trim)."""

    def __init__(self, path: str = "accounts.jsonl"):
        self.path = path
        self._lock = threading.RLock()
        self._accounts: dict[str, Account] = {}
        self._in_use: set[str] = set()   # usernames bound to a live session
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    account = Account(**{k: v for k, v in data.items() if k in Account.__annotations__})
                except (json.JSONDecodeError, TypeError):
                    continue
                self._accounts[account.key()] = account

    def _flush(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fp:
            for account in self._accounts.values():
                fp.write(json.dumps(asdict(account), ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)

    def upsert(self, account: Account) -> Account:
        with self._lock:
            self._accounts[account.key()] = account
            self._flush()
        return account

    def mark_used(self, username: str) -> None:
        with self._lock:
            account = self._accounts.get(username)
            if account:
                account.last_used = time.time()
                account.uses += 1

    def mark_failed(self, username: str, reason: str = "", disable_after: int = 3) -> None:
        with self._lock:
            account = self._accounts.get(username)
            if not account:
                return
            account.fails += 1
            account.note = reason[:200]
            if account.fails >= disable_after:
                account.disabled = True
            self._flush()

    def candidates(self, limit: int) -> list[Account]:
        """Least-recently-used, healthy, *not currently bound* accounts first."""
        with self._lock:
            usable = [a for a in self._accounts.values()
                      if not a.disabled and a.key() not in self._in_use]
            usable.sort(key=lambda a: (a.last_used or 0, a.created_at))
            return usable[:limit]

    def reserve(self, username: str) -> bool:
        with self._lock:
            if username in self._in_use:
                return False
            self._in_use.add(username)
            return True

    def unreserve(self, username: str) -> None:
        with self._lock:
            self._in_use.discard(username)

    def bindings(self) -> list[str]:
        with self._lock:
            return sorted(self._in_use)

    def stats(self) -> dict:
        with self._lock:
            total = len(self._accounts)
            disabled = sum(1 for a in self._accounts.values() if a.disabled)
            bound = len(self._in_use)
            return {"stored": total, "disabled": disabled,
                    "usable": total - disabled, "bound": bound,
                    "free": total - disabled - bound}


class AccountFactory:
    """Creates / revives single accounts."""

    def __init__(self, store: AccountStore, country: str = "US", verbose: bool = False,
                 verify: bool = False, max_attempts: int = 3):
        self.store = store
        self.country = country
        self.verbose = verbose
        self.verify = verify
        self.max_attempts = max_attempts
        self.register_count = 0
        self.revive_count = 0
        self.last_error: str | None = None

    # ---------------------------------------------------------------- helpers
    def _finish(self, client: ChannelClient, account: Account | None) -> Account:
        """Persist the account, then verify it over REST.

        Verification is a *health hint*, not a gate: the chat path is XMPP, so a
        flaky TLS handshake to the REST origin must not throw away a good account.
        Only an explicit 401/403 disables it.
        """
        record = account or Account(
            username=client.username or "",
            password=client.password or "",
            device_id=client.device_id,
            jid=client.jid,
            publictoken=client.publictoken,
            country=self.country,
        )
        record.jid = client.jid
        record.publictoken = client.publictoken
        record.disabled = False
        record.fails = 0
        self.store.upsert(record)          # persist first — never lose a live account

        if self.verify:
            status, payload = rest("/api/v2/currency/balances", client.jwt, client.jid,
                                   timeout=15, retries=1)
            if status in (401, 403):
                record.disabled = True
                record.note = f"verify rejected: {status} {payload}"
                self.store.upsert(record)
                client.close()
                raise ChannelError(f"account rejected by upstream: {status}")
            if status != 200:
                record.note = f"verify skipped (network): {status} {str(payload)[:120]}"
                self.store.upsert(record)
                if self.verbose:
                    print("   ! verify skipped:", record.note)

        self.store.mark_used(record.username)
        return record

    # ----------------------------------------------------------------- public
    def new_client(self, reuse: Account | None = None) -> ChannelClient:
        """Return a logged-in client, reusing `reuse` when its credentials still work."""
        if reuse is not None:
            try:
                client = ChannelClient(country=reuse.country or self.country, verbose=self.verbose)
                client.device_id = reuse.device_id
                client.username = reuse.username
                client.password = reuse.password
                client.connect()
                client.authenticate()          # SASL only — no re-registration
                client._buf = ""
                client._send(
                    "<?xml version='1.0'?>"
                    f"<stream:stream to='x.siki.ai' xmlns='jabber:client' "
                    f"xmlns:stream='http://etherx.jabber.org/streams' version='1.0'>"
                )
                client._read_until(lambda b: "</stream:features>" in b, client.timeout)
                client.bind()
                client.fetch_vcard()
                client._send("<presence/>")
                client._drain(0.5)
                self.revive_count += 1
                return client
            except Exception as exc:  # noqa: BLE001 - fall through to a fresh account
                self.last_error = f"revive failed: {type(exc).__name__}: {exc}"
                self.store.mark_failed(reuse.username, self.last_error)

        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                client = ChannelClient(country=self.country, verbose=self.verbose).login()
                self.register_count += 1
                return client
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.last_error = f"register attempt {attempt}: {type(exc).__name__}: {exc}"
                time.sleep(min(2.0 * attempt, 5.0))
        raise ChannelError(f"cannot provision account: {last_exc}")

    def provision(self) -> tuple[ChannelClient, Account]:
        """One account per call: reserve a free stored account, else register a new one."""
        reuse = None
        candidates = self.store.candidates(8)
        for candidate in candidates:
            if self.store.reserve(candidate.key()):
                reuse = candidate
                break

        try:
            client = self.new_client(reuse=reuse)
        except Exception:
            if reuse is not None:
                self.store.unreserve(reuse.key())
            raise

        record = self._finish(client, reuse)
        self.store.reserve(record.key())   # new accounts get bound to this session too
        return client, record


class SessionPool:
    """Self-healing, auto-growing pool of logged-in sessions.

    * `min_idle`  warm sessions kept ready by a background thread
    * `max_size`  initial capacity (== how many chats run in parallel)
    * `hard_max`  ceiling for autoscale; the pool grows when requests queue up
    * dead sessions are dropped and replaced transparently
    * registrations are rate-limited so a burst cannot hammer the upstream
    """

    def __init__(self, max_size: int = 4, min_idle: int | None = None,
                 store_path: str = "accounts.jsonl", country: str = "US",
                 verbose: bool = False, acquire_timeout: float = 120.0,
                 autoscale: bool = True, hard_max: int | None = None,
                 grow_step: int = 2, max_registrations_per_min: int = 30):
        self.max_size = max(1, max_size)
        self.min_idle = self.max_size if min_idle is None else max(0, min(min_idle, self.max_size))
        self.autoscale = autoscale
        self.hard_max = max(self.max_size, hard_max or max(self.max_size * 3, 12))
        self.grow_step = max(1, grow_step)
        self.max_registrations_per_min = max(1, max_registrations_per_min)
        self._cap = self.max_size                       # current dynamic capacity
        self.store = AccountStore(store_path)
        self.factory = AccountFactory(self.store, country=country, verbose=verbose)
        self.acquire_timeout = acquire_timeout
        self._idle: list[ChannelClient] = []
        self._total = 0                                 # live sessions (idle + busy + spawning)
        self._cv = threading.Condition()
        self._closed = False
        self._spawn_ts: list[float] = []                # registration rate limiter
        self._metrics = {"acquired": 0, "released": 0, "discarded": 0, "waited": 0,
                         "spawn_errors": 0, "grown": 0, "spawn_ms": []}
        self._bindings: dict[int, str] = {}             # id(client) -> account username
        self._maintainer = threading.Thread(target=self._maintain, name="pool-maintainer",
                                            daemon=True)
        self._maintainer.start()

    # ------------------------------------------------------------------ infra
    def _rate_limit_wait(self) -> None:
        """Keep registrations under `max_registrations_per_min` (protects the upstream)."""
        while True:
            now = time.time()
            with self._cv:
                self._spawn_ts = [ts for ts in self._spawn_ts if now - ts < 60]
                if len(self._spawn_ts) < self.max_registrations_per_min:
                    self._spawn_ts.append(now)
                    return
                sleep_for = 60 - (now - self._spawn_ts[0]) + 0.1
            time.sleep(max(0.1, sleep_for))

    def _create(self) -> ChannelClient:
        self._rate_limit_wait()
        started = time.time()
        try:
            client, record = self.factory.provision()
            with self._cv:
                self._bindings[id(client)] = record.key()
        finally:
            self._metrics["spawn_ms"].append(round((time.time() - started) * 1000, 1))
            del self._metrics["spawn_ms"][:-200]
        return client

    def _spawn_one(self) -> None:
        try:
            client = self._create()
        except Exception:  # noqa: BLE001
            with self._cv:
                self._total -= 1
                self._metrics["spawn_errors"] += 1
                self._cv.notify()
            time.sleep(2.0)
            return
        with self._cv:
            if self._closed:
                client.close()
                self._total -= 1
                self._metrics["discarded"] += 1
                username = self._bindings.pop(id(client), None)
                if username:
                    self.store.unreserve(username)
            else:
                self._idle.append(client)
            self._cv.notify()

    def _maintain(self) -> None:
        """Keep `min_idle` warm sessions available."""
        while True:
            with self._cv:
                if self._closed:
                    return
                need = self.min_idle - len(self._idle)
                can_spawn = self._cap - self._total
                slots = min(need, can_spawn)
                if slots <= 0:
                    self._cv.wait(5.0)
                    continue
                self._total += slots
            threads = []
            for _ in range(slots):
                thread = threading.Thread(target=self._spawn_one, daemon=True)
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()

    def _grow_locked(self) -> int:
        """Raise capacity after queue pressure. Caller holds `_cv`."""
        if not self.autoscale or self._cap >= self.hard_max:
            return 0
        grown = min(self.grow_step, self.hard_max - self._cap)
        self._cap += grown
        self._metrics["grown"] += grown
        return grown

    # ----------------------------------------------------------------- public
    def prewarm(self, count: int | None = None, block: bool = True) -> dict:
        want = self.min_idle if count is None else count
        deadline = time.time() + (self.acquire_timeout if block else 0)
        while time.time() < deadline:
            with self._cv:
                if len(self._idle) >= want:
                    return {"warm": len(self._idle), "cap": self._cap}
            time.sleep(0.25)
        with self._cv:
            return {"warm": len(self._idle), "cap": self._cap}

    def acquire(self, timeout: float | None = None) -> ChannelClient:
        """Hand out a validated session; register a new account when the pool must grow."""
        timeout = self.acquire_timeout if timeout is None else timeout
        deadline = time.time() + timeout
        while True:
            with self._cv:
                waited = False
                client = None
                while True:
                    if self._closed:
                        raise ChannelError("pool closed")
                    if self._idle:
                        client = self._idle.pop()
                        break
                    if self._total < self._cap:
                        self._total += 1
                        break
                    # queue pressure -> autoscale (bounded by hard_max)
                    grown = self._grow_locked()
                    if grown:
                        self._total += 1
                        break
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        raise ChannelError(
                            f"account pool exhausted (cap={self._cap}, hard_max={self.hard_max})")
                    waited = True
                    self._cv.wait(min(remaining, 5.0))
            if client is None:                      # slot reserved -> create a session
                try:
                    client = self._create()
                except Exception:
                    with self._cv:
                        self._total -= 1
                        self._metrics["spawn_errors"] += 1
                        self._cv.notify()
                    raise
                with self._cv:
                    self._metrics["acquired"] += 1
                return client
            if client.ping():                       # idle sessions can go stale
                with self._cv:
                    self._metrics["acquired"] += 1
                    if waited:
                        self._metrics["waited"] += 1
                return client
            with self._cv:
                self._metrics["discarded"] += 1
                self._total -= 1
                username = self._bindings.pop(id(client), None)
                if username:
                    self.store.unreserve(username)
                self._cv.notify()
            client.close()

    def release(self, client: ChannelClient, healthy: bool = True) -> None:
        if healthy and client.sock is not None:
            healthy = client.ping()      # drop sessions the upstream already killed
        with self._cv:
            self._metrics["released"] += 1
            if healthy and not self._closed and client.sock is not None:
                self._idle.append(client)
            else:
                self._total -= 1
                self._metrics["discarded"] += 1
                username = self._bindings.pop(id(client), None)
                if username:
                    self.store.unreserve(username)
                client.close()
            self._cv.notify()

    def discard(self, client: ChannelClient) -> None:
        self.release(client, healthy=False)

    def stats(self) -> dict:
        with self._cv:
            spawn = self._metrics["spawn_ms"]
            return {
                "max_size": self.max_size,
                "cap": self._cap,
                "hard_max": self.hard_max,
                "autoscale": self.autoscale,
                "min_idle": self.min_idle,
                "live_sessions": self._total,
                "idle": len(self._idle),
                "acquired": self._metrics["acquired"],
                "released": self._metrics["released"],
                "discarded": self._metrics["discarded"],
                "queued_acquires": self._metrics["waited"],
                "spawn_errors": self._metrics["spawn_errors"],
                "grown": self._metrics["grown"],
                "avg_spawn_ms": round(sum(spawn) / len(spawn), 1) if spawn else None,
                "accounts_registered": self.factory.register_count,
                "accounts_revived": self.factory.revive_count,
                "store": self.store.stats(),
                "last_error": self.factory.last_error,
            }

    def shutdown(self) -> None:
        with self._cv:
            self._closed = True
            idle, self._idle = self._idle, []
            self._cv.notify_all()
        for client in idle:
            client.close()
