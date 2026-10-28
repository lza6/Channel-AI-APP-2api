"""从上游目录生成模型清单：docs/MODELS.md + models.json（可直接喂给 new-api）。

用法：python -X utf8 build_models.py
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter

from channel_client import Catalog


def load_verify() -> dict:
    path = os.path.join("artifacts", "bot_verify.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fp:
        data = json.load(fp)
    return {row["id"]: row for row in data.get("text", []) if row.get("id")}


def row(bot: dict, verified: dict) -> str:
    tags = []
    if bot.get("can_generate_text"):
        tags.append("text")
    if bot.get("can_generate_images"):
        tags.append("image")
    if bot.get("is_nsfw"):
        tags.append("nsfw")
    if bot.get("can_face_swap"):
        tags.append("faceswap")
    check = verified.get(bot["username"])
    status = "✅ 已验证" if check and check.get("ok") else ("⏳ 未抽查" if not check else "❌ 失败")
    latency = f"{check['elapsed_s']}s" if check and check.get("ok") else "—"
    return (f"| `{bot['username']}` | {str(bot.get('display_name'))[:28]} | "
            f"{bot.get('interaction_count') or bot.get('interactions') or 0} | {'/'.join(tags) or '—'} | {status} | {latency} |")


def main() -> None:
    bots = Catalog.bots(limit=300)
    cats = Catalog.categories()
    verified = load_verify()
    chat = [b for b in bots if b.get("config_type") == "character"]
    image = [b for b in bots if b.get("config_type") == "image"]
    chat.sort(key=lambda b: -(b.get("interaction_count") or b.get("interactions") or 0))
    image.sort(key=lambda b: -(b.get("interaction_count") or b.get("interactions") or 0))

    field_stats = Counter()
    for bot in bots:
        for key, value in bot.items():
            if value not in (None, "", [], {}, False):
                field_stats[key] += 1

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "counts": {"total": len(bots), "character": len(chat), "image": len(image)},
        "categories": [c["name"] for c in cats],
        "models": [
            {
                "id": b["username"], "bare_jid": b.get("bare_jid"),
                "publictoken": b.get("publictoken"), "display_name": b.get("display_name"),
                "type": b.get("config_type"),
                "can_generate_text": b.get("can_generate_text"),
                "can_generate_images": b.get("can_generate_images"),
                "can_face_swap": b.get("can_face_swap"),
                "image_generator_jid": b.get("image_generator_jid"),
                "nsfw": b.get("is_nsfw"),
                "interactions": b.get("interaction_count") or b.get("interactions"),
                "image_generator_jid": b.get("image_generator_jid"),
                "subtitle": b.get("subtitle"),
                "verified": bool((verified.get(b["username"]) or {}).get("ok")),
            }
            for b in chat + image
        ],
    }
    with open("models.json", "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=1)

    lines = [
        "# 模型清单（上游目录快照）",
        "",
        f"> 生成时间：{payload['generated_at']}　数据源：`/v2/category/newexplore`（匿名接口，无需账号）",
        f"> 机器可读版：[`models.json`](../models.json)　验证明细：[`artifacts/bot_verify.json`](../artifacts/bot_verify.json)",
        "",
        f"**共 {len(bots)} 个模型**：对话（character）{len(chat)} 个 · 绘图（image）{len(image)} 个 · 分类 {len(cats)} 个",
        "",
        "> 说明：上游目录是**动态**的（不同时间拉到的数量会变，实测曾见 187 / 233 / 233），"
        "以 `python -X utf8 build_models.py` 现场生成的结果为准。",
        "",
        "## 能力字段说明",
        "",
        "| 字段 | 含义 | 本项目如何使用 |",
        "|---|---|---|",
        "| `config_type` | `character`=对话角色 / `image`=绘图模型 | 决定走 `/v1/chat/completions` 还是 `/v1/images/generations` |",
        "| `username` | JID localpart（`0_<uuid>`） | **就是 new-api 里的模型名** |",
        "| `can_generate_text` | 可对话 | 对话渠道模型必选 |",
        "| `can_generate_images` | **对话中可顺手出图** | 聊天里它可能回 `🌟 Generating images...` 再给图 |",
        "| `image_generator_jid` | 绑定的绘图模型 | 角色 → 绘图模型的映射 |",
        "| `can_face_swap` | 支持换脸请求 | 未接入 |",
        "| `is_nsfw` / `text_maturity` | 内容分级 | 上游按账号/地区策略过滤 |",
        "| `interactions` | 历史互动数 | **挑选练手模型的指标：越高越稳** |",
        "| `lorebooks` / `suggested_prompts` / `styles` | 角色设定与建议提示词 | 可直接当 prompt 样例 |",
        "",
        "## 对话模型 Top 40（按人气）",
        "",
        "| 模型名（new-api 用这个） | 显示名 | 互动数 | 能力 | 抽查 | 时延 |",
        "|---|---|---|---|---|---|",
    ]
    lines += [row(b, verified) for b in chat[:40]]

    lines += [
        "",
        f"## 绘图模型（全部 {len(image)} 个）",
        "",
        "| 模型名（new-api 用这个） | 显示名 | 互动数 | 能力 | 抽查 | 时延 |",
        "|---|---|---|---|---|---|",
    ]
    lines += [row(b, verified) for b in image]

    lines += [
        "",
        "## 全部模型名（直接粘进 new-api 渠道「模型」框）",
        "",
        "```",
        *[b["username"] for b in chat + image],
        "```",
        "",
        "## 想只看一小批？",
        "",
        "```bash",
        "# 导出全部模型名（每行一个，直接粘进 new-api 渠道的模型框）",
        "python -c \"import json;print('\n'.join(m['id'] for m in json.load(open('models.json'))['models']))\"",
        "",
        "# 只要绘图模型",
        "python -c \"import json;print('\n'.join(m['id'] for m in json.load(open('models.json'))['models'] if m['type']=='image'))\"",
        "",
        "# 人气前 10 的对话模型",
        "python -c \"import json;d=[m for m in json.load(open('models.json'))['models'] if m['type']=='character'];d.sort(key=lambda m:-(m['interactions'] or 0));print('\n'.join(m['id'] for m in d[:10]))\"",
        "```",
        "",
        "## 抽查结果（`verify_bots.py`）",
        "",
        f"最近一次抽查：**{sum(1 for v in verified.values() if v.get('ok'))}/{len(verified)} 个对话模型可用**"
        "（详见 `artifacts/bot_verify.json`；抽查只覆盖样本，不代表未抽查的不可用）。",
    ]
    with open(os.path.join("docs", "MODELS.md"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")

    print(f"已生成 models.json + docs/MODELS.md")
    print(f"  total={len(bots)} character={len(chat)} image={len(image)} categories={len(cats)}")
    print("  非空字段 Top:", ", ".join(f"{k}({v})" for k, v in field_stats.most_common(8)))


if __name__ == "__main__":
    main()
