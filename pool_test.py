"""Account-pool behaviour tests: cold auto-registration, autoscale, warm reuse.

Run: python -X utf8 pool_test.py [--fresh-store path]

1. 冷启动自动新号 : 空账号库 + max_size=N → N 个并发请求各自现注册一个新号
2. 突发自动扩容   : 容量 2 → 一波 8 并发 → cap 自动涨到 hard_max 并补号
3. 重启走复活     : 同一账号库再开池 → 不再注册，只做 SASL 复活
"""
from __future__ import annotations

import argparse
import os
import threading
import time

from accounts import SessionPool
from channel_client import Catalog

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def bot_ids(limit: int = 8) -> list[str]:
    bots = [b for b in Catalog.bots(limit=250) if b["config_type"] == "character"]
    bots.sort(key=lambda b: -(b.get("interactions") or 0))
    return [b["username"] for b in bots[:limit]]


def scenario_cold_register(store: str, size: int = 3) -> None:
    print(f"\n[1] 冷启动自动新号（空库，max_size={size}，min_idle=0，关掉 autoscale）")
    if os.path.exists(store):
        os.remove(store)
    pool = SessionPool(max_size=size, min_idle=0, store_path=store, autoscale=False)
    try:
        check("账号库起始为空", pool.store.stats()["stored"] == 0, str(pool.store.stats()))
        jids: list[str] = []
        lock = threading.Lock()
        bots = bot_ids()

        def worker(index: int) -> None:
            client = pool.acquire()
            try:
                pool.store.mark_used(client.username or "")
                with lock:
                    jids.append(client.jid)
            finally:
                pool.release(client)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(size)]
        started = time.time()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stats = pool.stats()
        check(f"{size} 个并发各自拿到不同账号", len(set(jids)) == size, f"{len(set(jids))} distinct")
        check("全部为现场注册（无历史库）", stats["accounts_registered"] == size,
              f"registered={stats['accounts_registered']} revived={stats['accounts_revived']}")
        check("账号已落库", stats["store"]["stored"] == size, str(stats["store"]))
        check("并发注册耗时合理（并行，非串行）", time.time() - started < size * 6,
              f"{time.time() - started:.1f}s")
        del bots
    finally:
        pool.shutdown()


def scenario_autoscale(store: str, bots: list[str]) -> None:
    print("\n[2] 突发自动扩容（max_size=2 / hard_max=8 / grow_step=3 / 8 并发）")
    pool = SessionPool(max_size=2, min_idle=2, store_path=store, hard_max=8, grow_step=3,
                       max_registrations_per_min=30)
    try:
        pool.prewarm()
        base_cap = pool.stats()["cap"]
        results: list[int] = []
        lock = threading.Lock()

        def worker(index: int) -> None:
            client = pool.acquire()
            try:
                reply = client.chat(bots[index % len(bots)], "reply with one word", quiet=2.0,
                                    max_seconds=90)
                with lock:
                    results.append(1 if reply.text else 0)
            except Exception:  # noqa: BLE001
                with lock:
                    results.append(0)
            finally:
                pool.release(client)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        started = time.time()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        wall = time.time() - started
        stats = pool.stats()
        check("8 并发全部拿到回复", sum(results) == 8, f"{sum(results)}/8 in {wall:.1f}s")
        check("容量自动上涨", stats["cap"] > base_cap, f"cap {base_cap} → {stats['cap']} (hard_max {stats['hard_max']})")
        check("扩容有上限", stats["cap"] <= stats["hard_max"], f"cap={stats['cap']}")
        check("按需补号（注册+复活=会话数）",
              stats["accounts_registered"] + stats["accounts_revived"] >= stats["live_sessions"],
              f"reg={stats['accounts_registered']} rev={stats['accounts_revived']} live={stats['live_sessions']}")
        check("无扩容失败", stats["spawn_errors"] == 0, f"spawn_errors={stats['spawn_errors']}")
    finally:
        pool.shutdown()


def scenario_reuse(store: str, size: int = 2) -> None:
    print("\n[3] 重启复用（不再注册新号，只 SASL 复活）")
    pool = SessionPool(max_size=size, min_idle=size, store_path=store, autoscale=False)
    try:
        before = pool.store.stats()["stored"]
        pool.prewarm()
        stats = pool.stats()
        check("复活而非注册", stats["accounts_registered"] == 0 and stats["accounts_revived"] >= size,
              f"reg={stats['accounts_registered']} rev={stats['accounts_revived']}")
        check("账号库没有膨胀", pool.store.stats()["stored"] <= before + 1,
              f"stored {before} → {pool.store.stats()['stored']}")
    finally:
        pool.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh-store", default="accounts_pooldemo.jsonl")
    parser.add_argument("--keep-store", action="store_true")
    args = parser.parse_args()
    store = args.fresh_store
    started = time.time()
    print(f"channel-demo account-pool test → store={store}")

    if os.path.exists(store):
        os.remove(store)
    scenario_cold_register(store, size=3)
    bots = bot_ids()
    scenario_autoscale(store, bots)
    scenario_reuse(store, size=2)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{'='*60}\n{passed}/{len(RESULTS)} PASS in {time.time()-started:.1f}s")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED: {name} {detail}")
    if not args.keep_store and os.path.exists(store):
        os.remove(store)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
