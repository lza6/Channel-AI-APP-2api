"""Channel demo server — OpenAI-compatible facade over the com.channel.ai XMPP backend.

Run:  python -X utf8 demo_server.py [--port 8920] [--pool 2]

Endpoints
  GET  /                          web demo page
  GET  /health                    liveness + pool snapshot
  GET  /stats                     request metrics
  GET  /v1/models                 bots exposed as chat models
  GET  /api/categories            catalog categories
  GET  /api/bots?q=&type=&limit=  bot directory (character | image)
  GET  /api/showcase              showcase prompts + images
  POST /api/accounts              create a fresh guest account (jid/jwt/publictoken/balances)
  GET  /api/accounts/<jid>/balances
  POST /v1/chat/completions       {model, messages, stream} -> OpenAI chat completion
  POST /v1/images/generations     {model, prompt} -> best-effort image bot request
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from accounts import AccountFactory, SessionPool
from channel_client import ChannelClient, ChannelError, Catalog, Reply, rest

VERSION = "0.1.0"
STARTED = time.time()
POOL: SessionPool | None = None
FACTORY: AccountFactory | None = None
STATS_LOCK = threading.Lock()
STATS = {
    "requests": 0,
    "chat_ok": 0,
    "chat_error": 0,
    "image_requests": 0,
    "accounts_created": 0,
    "latencies_ms": [],
}
ACCOUNTS: dict[str, str] = {}  # bare jid -> jwt, for balance lookups
API_KEY = os.environ.get("CHANNEL_API_KEY", "")


def bump(**kwargs) -> None:
    with STATS_LOCK:
        for key, value in kwargs.items():
            if key == "latency":
                STATS["latencies_ms"].append(round(value, 1))
                del STATS["latencies_ms"][:-500]
            else:
                STATS[key] += value


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(ratio * (len(ordered) - 1))))
    return ordered[index]


def stats_snapshot() -> dict:
    with STATS_LOCK:
        latencies = list(STATS["latencies_ms"])
        return {
            "uptime_s": round(time.time() - STARTED, 1),
            "requests": STATS["requests"],
            "chat_ok": STATS["chat_ok"],
            "chat_error": STATS["chat_error"],
            "image_requests": STATS["image_requests"],
            "accounts_created": STATS["accounts_created"],
            "latency_ms": {
                "p50": percentile(latencies, 0.50),
                "p95": percentile(latencies, 0.95),
                "samples": len(latencies),
            },
            "pool": POOL.stats() if POOL else None,
        }


# --------------------------------------------------------------- bot helpers
_BOT_INDEX: dict[str, dict] = {}
_BOT_INDEX_AT = 0.0


def bot_index(force: bool = False) -> dict[str, dict]:
    """username(uuid) -> bot item, plus display-name aliases."""
    global _BOT_INDEX, _BOT_INDEX_AT
    if not force and _BOT_INDEX and time.time() - _BOT_INDEX_AT < 300:
        return _BOT_INDEX
    index: dict[str, dict] = {}
    for bot in Catalog.bots(limit=250):
        index[bot["username"]] = bot
        index[f"{bot['username']}@x.siki.ai"] = bot
        index.setdefault(bot["display_name"].lower(), bot)
    _BOT_INDEX, _BOT_INDEX_AT = index, time.time()
    return index


def resolve_bot(model: str) -> dict:
    """Resolve a bot by username / bare JID / display name.

    Username-shaped ids (`0_…`, `pt_…`) are matched strictly — a fuzzy upstream
    search there would happily return an unrelated bot instead of a 404.
    """
    index = bot_index()
    key = (model or "").strip()
    bot = index.get(key) or index.get(key.lower())
    if bot is not None:
        return bot
    if not key or key.startswith(("0_", "pt_")):
        raise KeyError(model)
    for item in Catalog.search(key, limit=5):
        if (item.get("display_name") or "").lower() == key.lower():
            return item
    hits = Catalog.search(key, limit=1)
    if hits and hits[0].get("can_generate_text"):
        return hits[0]
    raise KeyError(model)


def public_bot(bot: dict) -> dict:
    return {
        "id": bot.get("username"),
        "object": "model",
        "owned_by": bot.get("creator_display_name") or "channel",
        "display_name": bot.get("display_name"),
        "type": bot.get("config_type"),
        "can_generate_text": bot.get("can_generate_text"),
        "can_generate_images": bot.get("can_generate_images"),
        "image_generator_jid": bot.get("image_generator_jid"),
        "nsfw": bot.get("is_nsfw"),
        "interactions": bot.get("interaction_count"),
        "subtitle": bot.get("subtitle"),
        "avatar": (bot.get("avatar_image") or {}).get("small_url"),
        "publictoken": bot.get("publictoken"),
    }


# ------------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    server_version = f"channel-demo/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter default logging
        if os.environ.get("DEMO_VERBOSE"):
            super().log_message(fmt, *args)

    # ------------------------------------------------------------- utilities
    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if raw and "gzip" in (self.headers.get("Content-Encoding") or "").lower():
            raw = gzip.decompress(raw)      # new-api may gzip outbound request bodies
        return raw

    def _read_json(self) -> dict:
        raw = self._read_body()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc

    def _check_key(self) -> None:
        if not API_KEY:
            return
        supplied = (self.headers.get("Authorization") or "")
        supplied = supplied[7:] if supplied.lower().startswith("bearer ") else supplied
        supplied = supplied or (self.headers.get("x-api-key") or "")
        if supplied != API_KEY:
            raise PermissionError("invalid api key")

    def _query(self) -> dict[str, list[str]]:
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ------------------------------------------------------------------ GET
    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        try:
            if path in ("/", "/index.html", "/demo", "/demo.html"):
                with open(os.path.join(os.path.dirname(__file__), "demo.html"), "rb") as fp:
                    return self._text(200, fp.read(), "text/html; charset=utf-8")
            if path == "/health":
                return self._json(200, {"status": "ok", "version": VERSION,
                                        "pool": POOL.stats() if POOL else None})
            if path == "/stats":
                return self._json(200, stats_snapshot())
            if path == "/v1/models":
                models = [public_bot(b) for b in Catalog.bots(limit=250)]
                return self._json(200, {"object": "list", "data": models})
            if path == "/api/categories":
                return self._json(200, {"data": Catalog.categories()})
            if path == "/api/bots":
                q = (self._query().get("q") or [""])[0]
                wanted = (self._query().get("type") or [""])[0]
                limit = int((self._query().get("limit") or ["60"])[0])
                items = Catalog.search(q, limit=limit) if q else Catalog.bots(limit=250)
                if wanted:
                    items = [b for b in items if b.get("config_type") == wanted]
                return self._json(200, {"data": [public_bot(b) for b in items[:limit]]})
            if path == "/api/showcase":
                return self._json(200, {"data": Catalog.showcase()})
            if path.startswith("/api/accounts/"):
                jid = urllib.parse.unquote(path.rsplit("/", 2)[-2])
                return self._account_balances(jid)
            return self._json(404, {"error": {"message": f"unknown path {path}"}})
        except Exception as exc:  # noqa: BLE001
            return self._fail(exc)

    def _account_balances(self, jid: str):
        local, jwt = jid.split("@")[0], ACCOUNTS.get(jid)
        if not jwt:
            raise KeyError(jid)
        status, data = rest("/api/v2/currency/balances", jwt=jwt, jid=local)
        return self._json(200, {"jid": jid, "upstream_status": status, "data": data})

    # ----------------------------------------------------------------- POST
    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        try:
            if path in ("/v1/chat/completions", "/v1/images/generations"):
                self._check_key()
            if path == "/api/accounts":
                return self._create_account()
            if path == "/v1/chat/completions":
                return self._chat_completions()
            if path == "/v1/images/generations":
                return self._images_generations()
            return self._json(404, {"error": {"message": f"unknown path {path}"}})
        except Exception as exc:  # noqa: BLE001
            return self._fail(exc)

    def _fail(self, exc: Exception):
        status = 500
        if isinstance(exc, KeyError):
            status, message = 404, f"model not found: {exc.args[0] if exc.args else ''}"
        elif isinstance(exc, ValueError):
            status, message = 400, str(exc)
        elif isinstance(exc, TimeoutError):
            status, message = 504, "upstream timeout"
        elif isinstance(exc, PermissionError):
            status, message = 401, str(exc)
        elif isinstance(exc, ChannelError):
            status, message = 502, str(exc)
        else:
            message = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        return self._json(status, {"error": {"message": message, "type": "channel_demo"}})

    # ---------------------------------------------------------------- routes
    def _create_account(self):
        body = self._read_json()
        country = (body.get("country") or "US").upper()[:2]
        factory = FACTORY if country == (FACTORY.country if FACTORY else "US") else AccountFactory(
            POOL.store, country=country)
        client, record = factory.provision()
        try:
            balances_status, balances = rest("/api/v2/currency/balances", client.jwt, client.jid)
        finally:
            POOL.store.unreserve(record.key())   # credentials stay reusable
            client.close()
        bump(accounts_created=1)
        ACCOUNTS[client.jid] = client.jwt
        return self._json(200, {
            "jid": client.jid,
            "username": record.username,
            "password": record.password,
            "device_id": record.device_id,
            "jwt": client.jwt,
            "publictoken": record.publictoken,
            "balances": balances,
            "balances_status": balances_status,
            "reused_from_store": record.uses > 0,
            "note": "guest account created without SMS verification",
        })

    def _chat_completions(self):
        body = self._read_json()
        model = body.get("model") or body.get("bot")
        messages = body.get("messages") or []
        stream = bool(body.get("stream"))
        if not model:
            raise ValueError("model (bot username or display name) is required")
        if not messages:
            raise ValueError("messages is required")
        prompt = messages[-1].get("content") or ""
        if isinstance(prompt, list):  # OpenAI multimodal-style content
            prompt = " ".join(part.get("text", "") for part in prompt if isinstance(part, dict))
        if not prompt.strip():
            raise ValueError("last message content is empty")

        bot = resolve_bot(str(model))
        bot_jid = bot.get("bare_jid") or f"{bot['username']}@x.siki.ai"
        bump(requests=1)
        started = time.time()

        client = POOL.acquire()
        try:
            reply: Reply = client.chat(
                bot_jid, prompt,
                quiet=float(body.get("quiet") or 2.5),
                max_seconds=float(body.get("max_seconds") or 120),
            )
            bump(latency=(time.time() - started) * 1000)
            bump(chat_ok=1)
        except Exception:
            bump(chat_error=1)
            POOL.discard(client)
            raise
        POOL.release(client)

        completion_id = "chatcmpl-" + uuid.uuid4().hex[:24]
        created = int(time.time())
        if stream:
            return self._stream_completion(completion_id, created, bot, reply, prompt)
        return self._json(200, {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": bot.get("username"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply.text},
                "finish_reason": "stop",
            }],
            "usage": _usage(prompt, reply.text),
            "x_channel": {
                "bot_display_name": bot.get("display_name"),
                "bot_jid": bot_jid,
                "first_token_ms": reply.first_token_ms,
                "elapsed_s": reply.elapsed,
                "thinking": reply.thinking,
                "images": reply.images,
                "balance": reply.balance,
                "parts": len(reply.parts),
            },
        })

    def _stream_completion(self, completion_id, created, bot, reply: Reply, prompt: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.close_connection = True

        def emit(payload: dict) -> None:
            self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

        base = {"id": completion_id, "object": "chat.completion.chunk", "created": created,
                "model": bot.get("username")}
        emit({**base, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]})
        for part in reply.parts or [reply.text]:
            emit({**base, "choices": [{"index": 0, "delta": {"content": part + "\n"},
                                       "finish_reason": None}]})
        emit({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
              "usage": _usage(prompt, reply.text)})
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _images_generations(self):
        body = self._read_json()
        model = body.get("model") or body.get("bot") or ""
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        bot = resolve_bot(model) if model else None
        if bot is None:
            candidates = [b for b in Catalog.bots(limit=250) if b.get("config_type") == "image"]
            if not candidates:
                raise ValueError("no image bot available")
            bot = candidates[0]
        bot_jid = bot.get("bare_jid") or f"{bot['username']}@x.siki.ai"
        bump(image_requests=1)
        client = POOL.acquire()
        try:
            reply = client.chat(bot_jid, prompt,
                                quiet=float(body.get("quiet") or 8.0),
                                max_seconds=float(body.get("max_seconds") or 240))
        except Exception:
            POOL.discard(client)
            raise
        POOL.release(client)
        data = [{"url": image.get("url", ""),
                 "revised_prompt": image.get("prompt") or prompt,
                 "preview_url": image.get("preview")}
                for image in reply.images if image.get("url")]
        return self._json(200, {
            "created": int(time.time()),
            "model": bot.get("username"),
            "data": data,
            "x_channel": {
                "text": reply.text,
                "balance": reply.balance,
                "elapsed_s": reply.elapsed,
                "bot_display_name": bot.get("display_name"),
                "images_found": len(data),
            },
        })


def _usage(prompt: str, completion: str) -> dict:
    prompt_tokens = max(1, len(prompt) // 4)
    completion_tokens = max(1, len(completion) // 4)
    return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens}


def main() -> None:
    global POOL
    parser = argparse.ArgumentParser(description="Channel demo server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("DEMO_PORT", 8920)))
    parser.add_argument("--pool", type=int, default=int(os.environ.get("CHANNEL_POOL", 4)))
    parser.add_argument("--min-idle", type=int,
                        default=int(os.environ.get("CHANNEL_MIN_IDLE", os.environ.get("CHANNEL_POOL", 4))))
    parser.add_argument("--store", default=os.environ.get("CHANNEL_ACCOUNTS", "accounts.jsonl"))
    parser.add_argument("--country", default=os.environ.get("CHANNEL_COUNTRY", "US"))
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--api-key", default=os.environ.get("CHANNEL_API_KEY", ""))
    args = parser.parse_args()
    global API_KEY
    API_KEY = args.api_key

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/health", timeout=2) as probe:
            if probe.status == 200:
                print(f"port {args.port} already serving a channel-demo; stop it first")
                raise SystemExit(1)
    except urllib.error.URLError:
        pass

    POOL = SessionPool(max_size=args.pool, min_idle=args.min_idle, store_path=args.store,
                       country=args.country, verbose=bool(os.environ.get("CHANNEL_VERBOSE")))
    global FACTORY
    FACTORY = POOL.factory
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"channel-demo {VERSION} on http://127.0.0.1:{args.port}  "
          f"(max={args.pool}, min_idle={args.min_idle}, store={args.store})", flush=True)

    def warm() -> None:
        # prewarm in the background so the HTTP port is usable immediately
        started = time.time()
        print("prewarming:", POOL.prewarm(), f"in {time.time()-started:.1f}s", flush=True)

    threading.Thread(target=warm, name="prewarm", daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        POOL.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
