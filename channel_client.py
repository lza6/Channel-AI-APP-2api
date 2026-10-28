"""Channel (com.channel.ai) backend client — clean-room reimplementation of the app protocol.

Verified against the live service on 2026-10-29 (see docs/ANALYSIS.md).

Protocol summary
----------------
TLS (x.siki.ai:443, direct TLS, XMPP 1.0)
  1. guest registration  : IQ set  <query xmlns='jabber:iq:register'> (pre-auth, no SMS)
  2. SASL PLAIN          : authcid = localpart, password = md5(device_id)
                           -> <success jwt='...'/> carries the REST bearer token
  3. bind resource
  4. vCard               : IQ get <vCard xmlns='vcard-temp'/> -> PUBLICTOKEN (pt_<uuid>@x.siki.ai)
  5. chat                : <message to='0_<uuid>@x.siki.ai' type='chat'> with <body>,
                           <publictoken xmlns='proximity:publictoken'> and a UUID stanza id
                           -> bot answers with thinking/active chatstates + <body>

REST (Authorization: Bearer <jwt>, jid: <bare jid>, client: android)
  https://admin-api-prod.shroom.gg/api/v2/...   (authenticated)
  https://d11absfiaqzcnz.cloudfront.net/...     (public catalog, no auth)
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import html
import json
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Iterable

XMPP_HOST = "x.siki.ai"
XMPP_PORT = 443
PUBLIC_API = "https://d11absfiaqzcnz.cloudfront.net"
PRIVATE_API = "https://admin-api-prod.shroom.gg"
NS_STREAM = "http://etherx.jabber.org/streams"
NS_CHATSTATES = "http://jabber.org/protocol/chatstates"
APP_VERSION = "1.6.1.3330"
SDK_RELEASE = "14"

# Bot replies that are status chatter rather than model output.
NOISE_BODIES = {"🌟 Generating images...", "📷 Image", "🎨 Generating your image..."}


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


DOH_RESOLVERS = (
    "https://1.1.1.1/dns-query?name={host}&type=A",
    "https://dns.google/resolve?name={host}&type=A",
)


def resolve_host(host: str = XMPP_HOST, port: int = XMPP_PORT) -> str:
    """Resolve `host`, falling back to DoH when the local resolver is hijacked.

    Local DNS on this box intermittently answers 127.0.0.1 for the upstream domains
    (see docs/ANALYSIS.md, "环境坑"), so a DoH lookup is used as a second opinion.
    """
    override = os.environ.get("CHANNEL_HOST_IP")
    if override:
        return override
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        addrs = [info[4][0] for info in infos]
        if addrs and not all(a.startswith(("127.", "0.")) for a in addrs):
            return addrs[0]
    except OSError:
        pass
    for template in DOH_RESOLVERS:
        try:
            request = urllib.request.Request(template.format(host=host),
                                             headers={"accept": "application/dns-json"})
            data = json.loads(urllib.request.urlopen(request, timeout=10).read())
            for answer in data.get("Answer") or []:
                if answer.get("type") == 1 and answer.get("data"):
                    return answer["data"]
        except Exception:  # noqa: BLE001 - try the next resolver
            continue
    raise ChannelError(f"cannot resolve {host}")


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def build_resource(version: str = APP_VERSION, country: str = "US") -> str:
    """android-<appVersion>-<androidRelease>-<lang>-<country>-<tz>-<20 chars>"""
    return f"android-{version}-{SDK_RELEASE}-en-{country}-China Standard Time-{uuid.uuid4().hex[:20]}"


class ChannelError(RuntimeError):
    pass


_DNS_LOCK = threading.Lock()


@contextlib.contextmanager
def dns_override(host: str, port: int = 443):
    """Point `host` at its DoH-resolved IP for the duration of the block.

    The local resolver on this box intermittently answers 127.0.0.1 for the
    upstream domains, which breaks urllib. Patching getaddrinfo for just that
    host is the smallest hammer that keeps SNI/Host correct.
    """
    try:
        ip = resolve_host(host, port)
    except ChannelError:
        yield
        return
    original = socket.getaddrinfo

    def patched(name, p, family=0, type=0, proto=0, flags=0):  # noqa: A002
        if name == host:
            return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "",
                     (ip, p or port))]
        return original(name, p, family, type, proto, flags)

    with _DNS_LOCK:
        socket.getaddrinfo = patched
        try:
            yield
        finally:
            socket.getaddrinfo = original


@dataclass
class Reply:
    text: str
    parts: list[str] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)
    thinking: bool = False
    elapsed: float = 0.0
    first_token_ms: float | None = None
    raw: str = ""
    balance: dict | None = None


class ChannelClient:
    """One authenticated guest account over one XMPP stream."""

    def __init__(self, country: str = "US", timeout: float = 30.0, verbose: bool = False):
        self.country = country.upper()
        self.timeout = timeout
        self.verbose = verbose
        self.device_id = uuid.uuid4().hex
        self.resource = build_resource(country=self.country)
        self.username: str | None = None
        self.password: str | None = None
        self.jwt: str | None = None
        self.publictoken: str | None = None
        self.sock: ssl.SSLSocket | None = None
        self._buf = ""
        self._lock = threading.RLock()
        self.created_at = time.time()

    # ------------------------------------------------------------------ infra
    @property
    def jid(self) -> str:
        return f"{self.username}@{XMPP_HOST}"

    def _log(self, direction: str, payload: str) -> None:
        if self.verbose:
            print(f"{direction} {payload[:300]}")

    def _send(self, xml: str) -> None:
        if self.sock is None:
            raise ChannelError("not connected")
        self._log(">>", xml)
        try:
            self.sock.sendall(xml.encode())
        except OSError as exc:  # server closed the stream
            raise ChannelError(f"send failed: {exc}") from exc

    def _read_until(self, predicate, timeout: float) -> str:
        deadline = time.time() + timeout
        while True:
            if predicate(self._buf):
                return self._buf
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ChannelError(f"timeout waiting for stanza; buffer={self._buf[-400:]!r}")
            self.sock.settimeout(min(remaining, 5))
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                raise ChannelError("stream closed by server")
            text = chunk.decode("utf-8", "replace")
            self._log("<<", text)
            self._buf += text

    def _drain(self, seconds: float, predicate=None, quiet: float | None = None) -> str:
        """Read for `seconds`, optionally stopping early when predicate hits + quiet period."""
        out = ""
        start = last_data = time.time()
        while time.time() - start < seconds:
            if predicate is not None and predicate(self._buf):
                if quiet is None or time.time() - last_data >= quiet:
                    break
            self.sock.settimeout(1.0)
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            text = chunk.decode("utf-8", "replace")
            self._log("<<", text)
            self._buf += text
            out += text
            last_data = time.time()
        return out

    def _respond_pings(self) -> None:
        for ping_id in re.findall(r"<iq[^>]*type='get'[^>]*id='([^']+)'[^>]*>\s*<ping ", self._buf):
            self._send(f"<iq type='result' id='{ping_id}'/>")

    # -------------------------------------------------------------- handshake
    def connect(self) -> None:
        address = resolve_host(XMPP_HOST)
        raw = socket.create_connection((address, XMPP_PORT), timeout=self.timeout)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.sock = ctx.wrap_socket(raw, server_hostname=XMPP_HOST)
        self.sock.settimeout(self.timeout)
        self._send(
            "<?xml version='1.0'?>"
            f"<stream:stream to='{XMPP_HOST}' xmlns='jabber:client' "
            f"xmlns:stream='{NS_STREAM}' version='1.0'>"
        )
        self._read_until(lambda b: "</stream:features>" in b, self.timeout)

    def register_guest(self) -> tuple[str, str]:
        """Anonymous in-band registration — the only credential is the device id."""
        nonce = str(uuid.uuid4())
        formatted = f"{self.country}.{_digits(self.device_id + nonce)}"
        username = f"tmp_{self.country}_{md5(formatted)}".lower()
        password = md5(self.device_id)
        iq_id = str(uuid.uuid4())
        self._buf = ""
        self._send(
            f"<iq id='{iq_id}' type='set'><query xmlns='jabber:iq:register'>"
            f"<username>{username}</username>"
            f"<password>{password}</password>"
            f"<verificationcode>sc:{self.device_id}</verificationcode>"
            f"<resource>{self.resource}</resource>"
            "</query></iq>"
        )
        resp = self._read_until(lambda b: f"id='{iq_id}'" in b or f'id="{iq_id}"' in b, self.timeout)
        if "type='error'" in resp or 'type="error"' in resp:
            raise ChannelError(f"registration failed: {resp[-300:]}")
        self.username, self.password = username, password
        return username, password

    def authenticate(self) -> str:
        token = base64.b64encode(f"\x00{self.username}\x00{self.password}".encode()).decode()
        self._buf = ""
        self._send(
            f"<auth xmlns='urn:ietf:params:xml:ns:xmpp-sasl' mechanism='PLAIN'>{token}</auth>"
        )
        resp = self._read_until(lambda b: "<success" in b or "<failure" in b, self.timeout)
        if "<failure" in resp:
            raise ChannelError(f"SASL failed: {resp[-300:]}")
        match = re.search(r"jwt='([^']+)'", resp)
        if not match:
            raise ChannelError("no jwt in SASL success")
        self.jwt = match.group(1)
        return self.jwt

    def bind(self) -> None:
        iq_id = "bind-" + uuid.uuid4().hex[:8]
        self._buf = ""
        self._send(
            f"<iq id='{iq_id}' type='set'><bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
            f"<resource>{self.resource}</resource></bind></iq>"
        )
        self._read_until(lambda b: f"id='{iq_id}'" in b or f'id="{iq_id}"' in b, self.timeout)

    def fetch_vcard(self) -> dict:
        """Own vCard; the PUBLICTOKEN field is required on every outgoing message."""
        self._buf = ""
        self._send("<iq type='get' id='vc1'><vCard xmlns='vcard-temp'/></iq>")
        resp = self._read_until(lambda b: "</iq>" in b, self.timeout)
        data = {}
        for key, value in re.findall(r"<([A-Z]+)>([^<]*)</\1>", resp):
            data[key] = html.unescape(value)
        self.publictoken = data.get("PUBLICTOKEN")
        return data

    def login(self) -> "ChannelClient":
        with self._lock:
            self.connect()
            self.register_guest()
            self.authenticate()
            self._buf = ""
            self._send(
                "<?xml version='1.0'?>"
                f"<stream:stream to='{XMPP_HOST}' xmlns='jabber:client' "
                f"xmlns:stream='{NS_STREAM}' version='1.0'>"
            )
            self._read_until(lambda b: "</stream:features>" in b, self.timeout)
            self.bind()
            self.fetch_vcard()
            self._send("<presence/>")
            self._drain(1.0)
        return self

    def close(self) -> None:
        try:
            if self.sock is not None:
                self.sock.sendall(b"</stream:stream>")
                self.sock.close()
        except OSError:
            pass
        finally:
            self.sock = None

    def alive(self) -> bool:
        """Round-trip an XMPP ping IQ: proves the stream is still usable."""
        return self.ping()

    def ping(self, timeout: float = 4.0) -> bool:
        if self.sock is None:
            return False
        iq_id = "p-" + uuid.uuid4().hex[:8]
        try:
            self._send(f"<iq type='get' id='{iq_id}'><ping xmlns='urn:xmpp:ping'/></iq>")
            deadline = time.time() + timeout
            while time.time() < deadline:
                if f"id='{iq_id}'" in self._buf or f'id="{iq_id}"' in self._buf:
                    self._buf = self._buf[self._buf.rfind("</iq>") + 5:] if "</iq>" in self._buf else ""
                    return True
                self.sock.settimeout(min(1.0, deadline - time.time()))
                try:
                    chunk = self.sock.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    return False
                self._buf += chunk.decode("utf-8", "replace")
                self._respond_pings()
                self._buf = self._buf[-8000:]
            return False
        except (OSError, ChannelError):
            return False

    # ------------------------------------------------------------------- chat
    def chat(self, bot_jid: str, text: str, timeout: float = 60.0,
             quiet: float = 2.5, max_seconds: float = 90.0,
             on_part=None) -> Reply:
        """Send one message and collect the bot's answer.

        `on_part(part, elapsed)` is called as each new bot body arrives, so callers
        can stream progressively (the upstream sends whole bodies, not tokens).
        """
        if not bot_jid.endswith("@" + XMPP_HOST):
            bot_jid = f"{bot_jid}@{XMPP_HOST}"
        started = time.time()
        cleaned = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        with self._lock:
            self._buf = ""
            stanza_id = str(uuid.uuid4())  # the AI worker ignores non-UUID ids
            self._send(
                f"<message id='{stanza_id}' to='{bot_jid}' type='chat'>"
                f"<publictoken xmlns='proximity:publictoken'>{self.publictoken or ''}</publictoken>"
                f"<body>{cleaned}</body>"
                "<request xmlns='urn:xmpp:receipts'/>"
                f"<active xmlns='{NS_CHATSTATES}'/>"
                "<nick xmlns='http://jabber.org/protocol/nick'>Guest</nick>"
                "</message>"
            )
            parts: list[str] = []
            images: list[dict] = []
            thinking = False
            balance = None
            seen: set[str] = set()
            seen_images: set[str] = set()
            first_token_ms = None
            answered = False
            last_data = time.time()

            while time.time() - started < max_seconds:
                if answered and time.time() - last_data >= quiet:
                    break
                self.sock.settimeout(1.0)
                try:
                    chunk = self.sock.recv(65536)
                except socket.timeout:
                    continue
                except OSError as exc:
                    raise ChannelError(f"read failed: {exc}") from exc
                if not chunk:
                    raise ChannelError("stream closed by server")
                piece = chunk.decode("utf-8", "replace")
                self._log("<<", piece)
                self._buf += piece
                last_data = time.time()
                for new_part in _extract_parts(piece, bot_jid, seen):
                    parts.append(new_part)
                    answered = True
                    if first_token_ms is None:
                        first_token_ms = round((time.time() - started) * 1000, 1)
                    if on_part is not None:
                        on_part(new_part, round(time.time() - started, 2))
                if "<thinking" in piece or "<composing" in piece:
                    thinking = True
                for image in _scan_images(self._buf):
                    key = image.get("url") or str(image.get("wrapper"))
                    if key not in seen_images:
                        seen_images.add(key)
                        images.append(image)
                        if image.get("url"):
                            answered = True
                bal = _extract_balance(piece)
                if bal:
                    balance = bal
                self._buf = self._buf[-8000:]
                self._respond_pings()

            raw = self._buf
            self._buf = ""
            self._respond_pings()

        if not parts and not any(image.get("url") for image in images):
            raise ChannelError(f"no reply from {bot_jid} within {max_seconds:.0f}s")

        return Reply(
            text="\n".join(parts),
            parts=parts,
            images=images,
            thinking=thinking,
            elapsed=round(time.time() - started, 2),
            first_token_ms=first_token_ms,
            raw=raw,
            balance=balance,
        )


def _strip_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def _message_stanzas(raw: str, bot_jid: str) -> Iterable[tuple[str, str]]:
    """Yield (stanza_id, inner_xml) for complete, non-error messages from the bot."""
    for match in re.finditer(r"<message\b([^>]*)>(.*?)</message>", raw, re.S):
        attrs, inner = match.group(1), match.group(2)
        if f"from='{bot_jid}'" not in attrs and f'from="{bot_jid}"' not in attrs:
            continue
        if "<error" in inner:
            continue
        stanza = re.search(r"\bid='([^']+)'", attrs)
        yield (stanza.group(1) if stanza else ""), inner


def _extract_parts(raw: str, bot_jid: str, seen: set[str]) -> list[str]:
    """New bot body texts in `raw`, skipping mirrored duplicates and status chatter."""
    out = []
    for stanza_id, inner in _message_stanzas(raw, bot_jid):
        if stanza_id:
            if stanza_id in seen:
                continue
            seen.add(stanza_id)
        body_match = re.search(r"<body[^>]*>(.*?)</body>", inner, re.S)
        if not body_match:
            continue
        body = _strip_tags(body_match.group(1)).strip()
        if body and body not in NOISE_BODIES and body not in out:
            out.append(body)
    return out


def _scan_images(buffer: str) -> list[dict]:
    """Extract generated images from an accumulated stanza buffer (idempotent)."""
    images: list[dict] = []
    seen: set[str] = set()

    def push(entry: dict) -> None:
        url = entry.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            images.append(entry)

    for match in re.finditer(r"<imagedata\b(.*?)/>", buffer, re.S):
        attrs = dict(re.findall(r"(\w+)='([^']*)'", match.group(1)))
        url = attrs.get("fullimageurl")
        if url:
            push({
                "url": url,
                "preview": attrs.get("previewimageurl"),
                "prompt": html.unescape(attrs.get("userInputtedPrompt") or attrs.get("prompt") or ""),
                "genindex": attrs.get("genindex"),
            })
    for match in re.finditer(r"<imageurl>([^<]+)</imageurl>", buffer):
        push({"url": match.group(1)})
    for match in re.finditer(r"<fullimageurl>([^<]+)</fullimageurl>", buffer):
        push({"url": match.group(1)})
    for match in re.finditer(r"<imageWrapper\b([^>]*)>", buffer):
        push({"wrapper": dict(re.findall(r"(\w+)='([^']*)'", match.group(1)))})
    return images


def _extract_balance(raw: str) -> dict | None:
    balance = None
    for block in re.findall(r"<balanceupdate>(.*?)</balanceupdate>", raw, re.S):
        balance = {}
        for key, value in re.findall(r"<(\w+)>([^<]*)</\1>", block):
            balance[key] = int(value) if value.isdigit() else value
    return balance


# --------------------------------------------------------------------- REST
def rest(path: str, jwt: str | None = None, jid: str | None = None,
         base: str = PRIVATE_API, payload: dict | None = None,
         method: str | None = None, timeout: float = 30.0,
         retries: int = 1) -> tuple[int, object]:
    """Tiny REST helper. One retry by default: TLS handshakes to the origin flake."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return _rest_once(path, jwt=jwt, jid=jid, base=base, payload=payload,
                              method=method, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.6 + attempt)
                # second chance with a DoH-pinned IP (local DNS hijack recovery)
                host = urllib.parse.urlparse(base).hostname
                if host:
                    try:
                        with dns_override(host):
                            return _rest_once(path, jwt=jwt, jid=jid, base=base,
                                              payload=payload, method=method, timeout=timeout)
                    except Exception as inner:  # noqa: BLE001
                        last_error = inner
    return 0, {"error": f"request failed: {type(last_error).__name__}: {last_error}"}


def _rest_once(path: str, jwt: str | None = None, jid: str | None = None,
               base: str = PRIVATE_API, payload: dict | None = None,
               method: str | None = None, timeout: float = 30.0) -> tuple[int, object]:
    headers = {"client": "android", "Accept": "application/json"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    if jid:
        headers["jid"] = jid
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, headers=headers,
                                     method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, _maybe_json(body)
    except urllib.error.HTTPError as exc:
        return exc.code, _maybe_json(exc.read())


def _maybe_json(body: bytes):
    try:
        return json.loads(body)
    except Exception:  # noqa: BLE001
        return body.decode("utf-8", "replace")


class Catalog:
    """Anonymous public catalog endpoints (no credentials needed).

    * single-flight: concurrent cold requests share one upstream fetch
    * stale-while-error: if the CDN is unreachable we keep serving the last
      known-good payload instead of failing the whole dashboard
    """

    _cache: dict[str, tuple[float, object]] = {}
    _locks: dict[str, threading.Lock] = {}
    _lock_guard = threading.Lock()
    _ttl = 120

    @classmethod
    def _path_lock(cls, path: str) -> threading.Lock:
        with cls._lock_guard:
            lock = cls._locks.get(path)
            if lock is None:
                lock = cls._locks[path] = threading.Lock()
            return lock

    @classmethod
    def _get(cls, path: str) -> object:
        cached = cls._cache.get(path)
        if cached and time.time() - cached[0] < cls._ttl:
            return cached[1]
        with cls._path_lock(path):
            cached = cls._cache.get(path)
            if cached and time.time() - cached[0] < cls._ttl:
                return cached[1]
            status, data = rest(path, base=PUBLIC_API, timeout=20, retries=1)
            if status != 200:
                if cached:                       # stale-while-error
                    return cached[1]
                raise ChannelError(f"catalog {path} -> {status} {data}")
            cls._cache[path] = (time.time(), data)
            return data

    @classmethod
    def categories(cls) -> list[dict]:
        return cls._get("/sidekick/category/allnames?version=1")

    @classmethod
    def bots(cls, limit: int = 200, category: str = "newexplore") -> list[dict]:
        data = cls._get(f"/v2/category/{category}?limit={limit}")
        return data.get("sidekicks", []) if isinstance(data, dict) else []

    @classmethod
    def search(cls, term: str, limit: int = 30, nsfw: bool = False) -> list[dict]:
        flag = "true" if nsfw else "false"
        status, data = rest(
            f"/v2/sidekick/search?search_term={urllib.parse.quote(term)}"
            f"&include_nsfw={flag}&limit={limit}",
            base=PUBLIC_API,
        )
        return data if isinstance(data, list) else []

    @classmethod
    def showcase(cls, limit: int = 40) -> list[dict]:
        status, data = rest("/sidekick/showcase?allow_nsfw=false", base=PUBLIC_API)
        return (data or [])[:limit] if isinstance(data, list) else []


class AccountPool:
    """Pool of logged-in guest accounts; holds at most `size` live XMPP sessions."""

    def __init__(self, size: int = 2, country: str = "US", verbose: bool = False):
        if size < 1:
            raise ValueError("size must be >= 1")
        self.size = size
        self.country = country
        self.verbose = verbose
        self._idle: list[ChannelClient] = []
        self._total = 0
        self._cv = threading.Condition()
        self._closed = False
        self.created = 0
        self.reused = 0

    def acquire(self, timeout: float = 90.0) -> ChannelClient:
        with self._cv:
            deadline = time.time() + timeout
            while True:
                if self._closed:
                    raise ChannelError("pool closed")
                if self._idle:
                    self.reused += 1
                    return self._idle.pop()
                if self._total < self.size:
                    self._total += 1
                    break
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise ChannelError("account pool exhausted")
                self._cv.wait(remaining)
        try:
            client = ChannelClient(country=self.country, verbose=self.verbose).login()
        except Exception:
            with self._cv:
                self._total -= 1
                self._cv.notify()
            raise
        self.created += 1
        return client

    def release(self, client: ChannelClient) -> None:
        healthy = client.sock is not None
        with self._cv:
            if healthy and not self._closed:
                self._idle.append(client)
            else:
                self._total -= 1
                client.close()
            self._cv.notify()

    def discard(self, client: ChannelClient) -> None:
        with self._cv:
            self._total -= 1
            self._cv.notify()
        client.close()

    def stats(self) -> dict:
        with self._cv:
            return {
                "pool_size": self.size,
                "live_sessions": self._total,
                "idle": len(self._idle),
                "accounts_created": self.created,
                "reused": self.reused,
                "jids": [c.jid for c in self._idle],
            }

    def shutdown(self) -> None:
        with self._cv:
            self._closed = True
            idle, self._idle = self._idle, []
        for client in idle:
            client.close()


if __name__ == "__main__":
    """协议层自检：注册 -> JWT -> vCard -> 目录 -> 对话。"""
    print("1) 注册游客账号 …")
    client = ChannelClient(country="US", verbose=False).login()
    print(f"   jid={client.jid}")
    print(f"   jwt={client.jwt[:24]}…  publictoken={client.publictoken}")

    status, balances = rest("/api/v2/currency/balances", client.jwt, client.jid)
    print(f"2) balances ({status}) {balances}")

    bots = [b for b in Catalog.bots() if b["config_type"] == "character"]
    print(f"3) 目录：{len(Catalog.categories())} 分类 / 至少 {len(bots)} 个对话 bot")

    bot = bots[0]
    print(f"4) 对话 {bot['display_name']} …")
    reply = client.chat(bot["username"], "你好，请用一句话介绍你自己。",
                        on_part=lambda part, elapsed: print(f"   +{elapsed:.2f}s {part[:60]!r}"))
    print(f"   首字节 {reply.first_token_ms} ms / 总 {reply.elapsed} s")
    print(f"   内容：{reply.text[:200]}")
    client.close()
