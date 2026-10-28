# Channel 2API（com.channel.ai 1.6.1.3330）

把 Channel（AI 角色陪伴 App）的 XMPP 后端封装成 **OpenAI 兼容 HTTP API**，附本地演示页与压测脚本。
纯 Python 标准库实现，无第三方依赖。

* 逆向细节：见 [`docs/ANALYSIS.md`](docs/ANALYSIS.md)
* **对接 new-api：见 [`docs/NEWAPI_INTEGRATION.md`](docs/NEWAPI_INTEGRATION.md)**（含渠道参数、超时、坑表）
* 一句话原理：`游客注册(IQ jabber:iq:register) → SASL(JWT) → vCard(publictoken) → XMPP 发消息收回复`

```
app 侧                       本仓库                         上游
┌──────────┐   HTTP    ┌──────────────┐   XMPP over TLS  ┌────────────┐
│ 你的客户端 │ ────────► │ demo_server  │ ───────────────► │ x.siki.ai  │
└──────────┘  OpenAI   │ 账号池/限流    │  443 (直连 TLS)   │  AI bot    │
                        └──────────────┘                  └────────────┘
```

## 快速开始

```powershell
cd D:\apk-analysis\channel-ai
python -X utf8 demo_server.py --port 8921 --pool 8 --min-idle 8 --api-key channel-local-key
# 打开 http://127.0.0.1:8921
# 带 --api-key 时：请求需带 Authorization: Bearer channel-local-key
```

```bash
curl -s http://127.0.0.1:8921/health
curl -s -X POST http://127.0.0.1:8921/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer channel-local-key' \
  -d '{"model":"Stranger","messages":[{"role":"user","content":"你好，用一句话介绍自己"}]}'
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 演示页（bot 列表 + 对话 + 运行态） |
| GET | `/health` | 存活 + 账号池快照 |
| GET | `/stats` | 请求数 / 成功失败 / p50·p95 / 池状态 |
| GET | `/v1/models` | 全部 bot（当作"模型"），含 `display_name`/`type`/`interactions` |
| GET | `/api/categories` | 目录分类（17 个） |
| GET | `/api/bots?q=&type=character\|image&limit=` | 目录 / 搜索 |
| GET | `/api/showcase` | 绘图样例（含 prompt 原文与图片直链） |
| POST | `/api/accounts` | 取一个游客账号（优先复用库里的），返回 `jid/jwt/publictoken/balances`（**无需短信**） |
| GET | `/api/accounts/<jid>/balances` | 查 energy/coins |
| POST | `/v1/chat/completions` | OpenAI 兼容，支持 `stream:true`（SSE） |
| POST | `/v1/images/generations` | 绘图（实测出 3 张 osscdn 直链，60–180 s，扣 1 energy） |

### 请求 / 响应示例

```json
POST /v1/chat/completions
{"model":"Stranger", "messages":[{"role":"user","content":"hi"}], "stream": false}
```

```json
{
  "id": "chatcmpl-…", "object": "chat.completion", "model": "0_b2cf4ea3-…",
  "choices": [{"index":0,"message":{"role":"assistant","content":"*Gives a weak smile* Hey..."},"finish_reason":"stop"}],
  "usage": {"prompt_tokens":7,"completion_tokens":6,"total_tokens":13},
  "x_channel": {"bot_display_name":"Stranger","first_token_ms":2583.7,"elapsed_s":5.61,
                "thinking":true,"images":[],"balance":null,"parts":1}
}
```

`model` 可以是 bot 的 `0_<uuid>`、`0_<uuid>@x.siki.ai`、显示名（如 `Stranger`），
未命中时服务端会回落到上游搜索。**会话上下文由上游按账号保存**，因此同一账号的多轮对话会延续。

## 直接当库用

```python
from channel_client import ChannelClient, Catalog, rest

client = ChannelClient(country="US").login()          # 注册+登录，约 2.8s
print(client.jid, client.publictoken, client.jwt[:20])

bot = [b for b in Catalog.bots() if b["config_type"] == "character"][0]
reply = client.chat(bot["username"], "介绍一下你自己")
print(reply.text, reply.first_token_ms, reply.elapsed)
print(rest("/api/v2/currency/balances", client.jwt, client.jid))
client.close()
```

## 自动注册账号 / 高并发

上游是"一个 XMPP 会话 = 一个并发"，所以**并发能力 = 账号池大小**。`accounts.py` 负责这件事：

| 机制 | 行为 |
|---|---|
| 自动新号 | 池里没有空号时，现场注册（`IQ jabber:iq:register`，无短信，约 4 s） |
| 账号持久化 | `accounts.jsonl` 保存 `username/password/device_id/publictoken`，**重启只做 SASL 复活，不再重复注册** |
| 一号一会话 | 账号在 `_in_use` 中预留，杜绝两个会话抢同一账号导致互相踢下线 |
| 预热 | `--min-idle` 个会话并行注册/复活（4 个 ≈ 14 s 全好），首个请求不吃冷启动惩罚 |
| 健康检查 | 空闲会话在 acquire/release 各 ping 一次（`urn:xmpp:ping`），死会话立刻丢弃并补新 |
| 坏号处理 | 复活失败计入 `fails`，≥3 次标记 disabled；凭据仍在库里，可随时复活 |
| 背压 | 池满时请求排队（`queued_acquires` 计数），不失败、不无脑扩号 |

容量公式：`可持续并发 ≈ pool_size`，`QPS ≈ pool_size / 平均延迟(≈8 s)`。

实测（4 会话池、8 并发突发）：**13/13 PASS，18 个请求全部成功，wall 20.4 s，
`queued_acquires=5`（排队生效）、`discarded=7`（死会话自动替换）、`spawn_errors=0`**。

## 压测

```powershell
python -X utf8 stress_test.py --base http://127.0.0.1:8921 --concurrency 2
```

最近一次实跑（本机，2026-10-29）：**13/13 PASS / 50.2s**

| 项 | 结果 |
|---|---|
| `/health` × 15 | median ≈ 1 ms |
| 目录 `/api/bots` | 100 bots（冷启 13.8 s，之后命中 120 s 缓存） |
| 游客账号 | 4.3 s（含 balances 校验） |
| 串行对话 | median 7.7 s，首字节 2.6 s（热 bot，78 万互动）|
| 并发 ×4 / ×8 | 11.7 s / 20.4 s，全部成功（池满排队） |
| SSE 流式 | 3 chunk + `[DONE]` |
| 错误路径 | 404/400 全部符合预期 |

## 已知限制

1. **首字节 2.5–4 s**，整轮 6–9 s：这是上游 bot 的思考时间，不是封装层开销。
2. 每个账号同时只能有一个对话在飞（XMPP 会话被锁）→ 并发上限＝池大小；池满了请求排队。
3. `/v1/images/generations` 返回 `osscdn.siki.ai` 直链（实测无水印）。一次 prompt 通常出 3 张，
   但渲染需 60–180 s，接口默认等 240 s；可用 `max_seconds` / `quiet` 调整。
4. 纯文本对话不扣 `energy`；绘图才扣，额度由上游账号决定。
5. 本机 DNS 偶尔把 `x.siki.ai` 解析到 `127.0.0.1`，客户端内置 DoH 兜底；也可用
   `CHANNEL_HOST_IP=13.248.161.98` 强制指定出口 IP。

## 文件说明

| 文件 | 作用 |
|---|---|
| `channel_client.py` | 协议库：游客注册 / SASL+JWT / vCard / 对话 / 绘图 / 目录 / DoH 兜底；`python channel_client.py` 可自检 |
| `accounts.py` | 账号层：`AccountStore`（持久化）+ `AccountFactory`（注册/复活）+ `SessionPool`（预热/健康检查/自愈） |
| `accounts.jsonl` | 账号库（运行时生成，已 gitignore） |
| `demo_server.py` | OpenAI 兼容 HTTP 服务（默认 8921） |
| `demo.html` | 演示面板（bot 列表 / 对话 / 运行态 / 一键建号） |
| `stress_test.py` | 本地压测，13 个断言 |
| `docs/ANALYSIS.md` | 逆向分析报告（协议、鉴权链、坑表、绘图链路） |
| `docs/NEWAPI_INTEGRATION.md` | new-api 对接指南（路径 A 零代码 / 路径 B 原生渠道 + 参数与坑表） |
| `artifacts/` | 原始报文留档（多轮对话 XML、绘图报文、dex 字符串） |
| `jadx_out/` | 全量反编译产物（34,945 个 java 文件） |
| `xmpp_client.py` / `probe_*.py` / `matrix*.py` / `vcard_*.py` / `*_test.py` | 首轮探针脚本（定位协议时的一次性实验，保留作证据） |

## 合规与使用边界

* 本项目仅用于协议研究与本地联调演示；上游内容与账号归其运营方所有。
* 未绕过任何付费墙、未发起任何真实付费请求，绘图仅使用 bot 自带免费额度。
* 未做大规模账号囤积/刷量；默认池大小 2，请求排队，不做无限并发。
* 请勿将本项目用于对外提供服务或商业分发。
