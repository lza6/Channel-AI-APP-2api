"""Bot 可用性抽查：拿真实账号逐个对话，记录成功率/首字节/时延。

用法：
  python -X utf8 verify_bots.py            # 12 个对话 bot 抽查
  python -X utf8 verify_bots.py --count 20 # 抽查更多
  python -X utf8 verify_bots.py --image    # 附带 1 个绘图 bot 的出图验证（耗时 1-4 分钟）
"""
from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time

from accounts import SessionPool
from channel_client import Catalog

PROMPT = "你好，请用一句话说明你是谁。"


def pick(bots: list[dict], count: int) -> list[dict]:
    """高人气 + 随机抽样，兼顾'热门是否可用'与'冷门是否可用'。"""
    hot = sorted(bots, key=lambda b: -(b.get("interaction_count") or b.get("interactions") or 0))
    hot = hot[: max(1, count // 2)]
    rest = [b for b in bots if b not in hot]
    random.seed(20261029)
    cold = random.sample(rest, min(len(rest), count - len(hot)))
    return hot + cold


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--pool", type=int, default=6)
    args = parser.parse_args()

    bots = [b for b in Catalog.bots(limit=250) if b.get("config_type") == "character"]
    images = [b for b in Catalog.bots(limit=250) if b.get("config_type") == "image"]
    print(f"目录：对话 bot {len(bots)} 个 / 绘图 bot {len(images)} 个")

    sample = pick(bots, args.count)
    print(f"抽查 {len(sample)} 个对话 bot（并发 {args.pool}）\n")

    pool = SessionPool(max_size=args.pool, min_idle=args.pool, store_path="accounts.jsonl",
                       hard_max=args.pool + 4, autoscale=True)
    pool.prewarm()

    results: list[dict] = []
    lock = threading.Lock()
    sem = threading.Semaphore(args.pool)

    def worker(bot: dict) -> None:
        with sem:
            client = pool.acquire()
            started = time.time()
            try:
                try:
                    reply = client.chat(bot["username"], PROMPT, quiet=2.5, max_seconds=120)
                except Exception:                 # 上游偶发不回复：重试一次再判失败
                    reply = client.chat(bot["username"], PROMPT, quiet=3.0, max_seconds=150)
                row = {"id": bot["username"], "name": bot.get("display_name"),
                       "ok": bool(reply.text), "first_token_ms": reply.first_token_ms,
                       "elapsed_s": reply.elapsed, "chars": len(reply.text),
                       "sample": reply.text[:60].replace("\n", " ")}
            except Exception as exc:  # noqa: BLE001
                row = {"id": bot["username"], "name": bot.get("display_name"), "ok": False,
                       "error": f"{type(exc).__name__}: {exc}"[:120],
                       "elapsed_s": round(time.time() - started, 1)}
            finally:
                pool.release(client)
            with lock:
                results.append(row)
                flag = "OK " if row["ok"] else "ERR"
                print(f"  {flag} {str(row['name'])[:34]:34} {row.get('elapsed_s'):>5}s "
                      f"ft={row.get('first_token_ms')}ms {row.get('sample') or row.get('error')}")

    threads = [threading.Thread(target=worker, args=(bot,)) for bot in sample]
    started = time.time()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.time() - started

    ok = sum(1 for r in results if r["ok"])
    firsts = [r["first_token_ms"] for r in results if r.get("first_token_ms")]
    print(f"\n对话抽查：{ok}/{len(results)} 成功，wall {wall:.1f}s，"
          f"首字节中位 {sorted(firsts)[len(firsts)//2] if firsts else '—'} ms")

    image_result = None
    if args.image and images:
        bot = sorted(images, key=lambda b: -(b.get("interaction_count") or 0))[0]
        print(f"\n绘图验证：{bot.get('display_name')} …")
        client = pool.acquire()
        try:
            reply = client.chat(bot["username"], "a cat on a windowsill, cinematic light",
                                quiet=8.0, max_seconds=260)
            urls = [i.get("url") for i in reply.images if i.get("url")]
            image_result = {"id": bot["username"], "name": bot.get("display_name"),
                            "images": urls, "elapsed_s": reply.elapsed,
                            "balance": reply.balance}
            print(f"  出图 {len(urls)} 张 / {reply.elapsed}s / energy={ (reply.balance or {}).get('energy') }")
            for url in urls:
                print("   ", url)
        except Exception as exc:  # noqa: BLE001
            image_result = {"id": bot["username"], "error": str(exc)[:120]}
            print("  失败:", exc)
        finally:
            pool.release(client)

    # merge with previous run so历史抽查结果不被覆盖
    previous: dict[str, dict] = {}
    prev_image = None
    if os.path.exists("artifacts/bot_verify.json"):
        try:
            with open("artifacts/bot_verify.json", encoding="utf-8") as fp:
                old = json.load(fp)
            previous = {row["id"]: row for row in old.get("text", []) if row.get("id")}
            prev_image = old.get("image")
        except json.JSONDecodeError:
            pass
    for row in results:
        previous[row["id"]] = row
    payload = {"counts": {"character": len(bots), "image": len(images)},
               "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "text": list(previous.values()),
               "image": image_result or prev_image}
    with open("artifacts/bot_verify.json", "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=1)
    print("\n已写 artifacts/bot_verify.json")
    pool.shutdown()
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
