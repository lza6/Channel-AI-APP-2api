"""Local stress / smoke test for the Channel demo server.

Usage: python -X utf8 stress_test.py [--base http://127.0.0.1:8921] [--concurrency 2]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import threading
import time
import urllib.error
import urllib.request

RESULTS: list[tuple[str, bool, str]] = []


API_KEY = os.environ.get("CHANNEL_API_KEY", "")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


def call(base: str, path: str, payload=None, timeout: float = 120.0, raw: bool = False):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, headers=_headers(),
                                     method="POST" if data is not None else "GET")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (body.decode() if raw else json.loads(body)), time.time() - started
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed, time.time() - started


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    return ok


def scenario_health(base):
    print("\n[1] /health 稳定性")
    latencies = []
    ok_all = True
    for _ in range(15):
        status, data, elapsed = call(base, "/health")
        ok_all = ok_all and status == 200 and data.get("status") == "ok"
        latencies.append(elapsed * 1000)
    check("health 15x200", ok_all, f"median={statistics.median(latencies):.0f}ms")
    return latencies


def scenario_catalog(base):
    print("\n[2] 目录接口")
    status, data, elapsed = call(base, "/api/bots?limit=100&type=character")
    bots = data.get("data", []) if isinstance(data, dict) else []
    check("bots>=50", status == 200 and len(bots) >= 50, f"{len(bots)} bots, {elapsed*1000:.0f}ms")
    status, cats, _ = call(base, "/api/categories")
    check("categories", status == 200 and len(cats.get("data", [])) >= 5, f"{len(cats.get('data', []))} 类")
    return bots


def _energy(balances):
    if not isinstance(balances, dict):
        return None
    return balances.get("energy", (balances.get("data") or {}).get("energy"))


def scenario_account(base):
    print("\n[3] 游客账号（无短信）")
    status, data, elapsed = call(base, "/api/accounts", {})
    ok = (status == 200 and data.get("jwt") and str(data.get("publictoken", "")).startswith("pt_")
          and _energy(data.get("balances")) is not None)
    check("account created", ok, f"{str(data.get('jid'))[:38]} {elapsed*1000:.0f}ms")
    if ok:
        status, bal, _ = call(base, f"/api/accounts/{data['jid']}/balances")
        check("balances lookup", status == 200 and bal.get("upstream_status") == 200)
    return data


def scenario_chat(base, bots, turns=2):
    print("\n[4] 串行对话基线 + 多轮上下文")
    if not bots:
        return check("chat baseline", False, "no bot")
    hot = sorted(bots, key=lambda b: -(b.get("interactions") or 0))
    bot = hot[0] if hot else bots[0]
    print(f"      bot: {bot.get('display_name')} ({bot.get('interactions')} 互动)")
    latencies, first_tokens = [], []
    ok = True
    for index, prompt in enumerate([
        "Hi! In one short sentence, who are you?",
        "And what did I just ask you?",
    ][:turns]):
        status, data, elapsed = call(base, "/v1/chat/completions",
                                     {"model": bot["id"],
                                      "messages": [{"role": "user", "content": prompt}]})
        content = ""
        if status == 200:
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        ok = ok and status == 200 and len(content) > 3
        latencies.append(elapsed * 1000)
        first_tokens.append(data.get("x_channel", {}).get("first_token_ms") if status == 200 else None)
        print(f"      turn{index+1}: {elapsed*1000:.0f}ms first_token={first_tokens[-1]}ms -> {content[:70]!r}")
    check("serial chat ok", ok,
          f"median={statistics.median(latencies):.0f}ms first_token={first_tokens[0]}ms")


def scenario_concurrency(base, bots, concurrency):
    print(f"\n[5] 并发 x{concurrency}")
    if not bots:
        return check("concurrency", False, "no bot")
    hot = sorted(bots, key=lambda b: -(b.get("interactions") or 0))
    pool = hot[:max(concurrency, 1)] or bots
    results = []
    lock = threading.Lock()

    def worker(index):
        bot = pool[index % len(pool)]
        status, data, elapsed = call(base, "/v1/chat/completions",
                                     {"model": bot["id"],
                                      "messages": [{"role": "user", "content": f"ping {index}, reply one word"}]},
                                     timeout=180)
        with lock:
            results.append((status, elapsed,
                            data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            if status == 200 else str(data)[:80]))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(concurrency)]
    started = time.time()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.time() - started
    ok = (len(results) == concurrency
          and all(status == 200 and len(content) > 1 for status, _elapsed, content in results))
    detail = f"wall={wall:.1f}s max={max(r[1] for r in results):.1f}s"
    if not ok:
        detail += " | " + "; ".join(f"{status}:{content[:40]}" for status, _elapsed, content in results)
    check(f"concurrent x{concurrency}", ok, detail)


def scenario_stream(base, bots):
    print("\n[6] SSE 流式")
    if not bots:
        return check("stream", False, "no bot")
    data = json.dumps({"model": bots[0]["id"], "stream": True,
                       "messages": [{"role": "user", "content": "say hi"}]}).encode()
    request = urllib.request.Request(base + "/v1/chat/completions", data=data,
                                     headers=_headers(), method="POST")
    chunks, done = 0, False
    started = time.time()
    with urllib.request.urlopen(request, timeout=180) as resp:
        for line in resp:
            text = line.decode().strip()
            if not text.startswith("data: "):
                continue
            payload = text[6:]
            if payload == "[DONE]":
                done = True
                break
            chunks += 1
    check("stream chunks + [DONE]", done and chunks >= 2, f"{chunks} chunks, {time.time()-started:.1f}s")


def scenario_errors(base):
    print("\n[7] 错误路径")
    status, data, _ = call(base, "/v1/chat/completions",
                           {"model": "0_does-not-exist-0000",
                            "messages": [{"role": "user", "content": "hi"}]})
    check("unknown model -> 404", status == 404, f"{status} {str(data)[:60]}")
    status, data, _ = call(base, "/v1/chat/completions", {"model": "Stranger", "messages": []})
    check("empty messages -> 400", status == 400, f"{status}")
    status, data, _ = call(base, "/v1/chat/completions",
                           {"messages": [{"role": "user", "content": "hi"}]})
    check("missing model -> 400", status == 400, f"{status}")
    status, _, _ = call(base, "/nope")
    check("unknown path -> 404", status == 404, f"{status}")


def scenario_stats(base, expected_ok):
    print("\n[8] /stats 一致性")
    status, data, _ = call(base, "/stats")
    ok = (status == 200
          and data.get("chat_ok", 0) + data.get("chat_error", 0) == data.get("requests", -1)
          and data.get("chat_ok", 0) >= expected_ok)
    check("stats counters", ok,
          f"requests={data.get('requests')} ok={data.get('chat_ok')} "
          f"p50={data.get('latency_ms', {}).get('p50')}ms "
          f"pool={data.get('pool', {}).get('live_sessions')}/{data.get('pool', {}).get('max_size')} "
          f"idle={data.get('pool', {}).get('idle')} "
          f"discarded={data.get('pool', {}).get('discarded')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8921")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    print(f"channel-demo stress test -> {base}")
    started = time.time()

    scenario_health(base)
    bots = scenario_catalog(base)
    scenario_account(base)
    scenario_chat(base, bots)
    scenario_concurrency(base, bots, args.concurrency)
    scenario_stream(base, bots)
    scenario_errors(base)
    scenario_stats(base, expected_ok=2 + args.concurrency + 1)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{'='*60}\n{passed}/{total} PASS in {time.time()-started:.1f}s")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED: {name} {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
