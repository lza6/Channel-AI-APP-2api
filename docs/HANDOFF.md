# 交接单 · Channel 2API → new-api（给对接会话用）

> 本文件是"一页交接"：仓库在哪、上游桥怎么起、new-api 渠道怎么填、必调什么参数、
> 会踩哪些坑、验收怎么算过，末尾还有**可直接粘贴给另一个会话的 prompt**。
> 详细背景见 `docs/ANALYSIS.md`，完整对接说明见 `docs/NEWAPI_INTEGRATION.md`。

---

## 1. 基本信息

| 项 | 值 |
|---|---|
| 仓库 | `https://github.com/lza6/Channel-AI-APP-2api`（master） |
| 上游 | Channel App（`com.channel.ai` 1.6.1.3330）→ XMPP `x.siki.ai:443`（直连 TLS） |
| 桥接层 | `demo_server.py`（Python 标准库，OpenAI 兼容，默认端口 8921） |
| 能力 | 对话 169 个 bot（角色扮演，NSFW 可选）+ 绘图 18 个 bot（一次 prompt 出 3 张无水印直链） |
| 并发模型 | 一个 XMPP 会话只能跑一个对话 ⇒ 并发＝会话池容量，池满自动扩容/排队 |
| 计费单位 | 上游是 `energy`（每号免费 5 点，文本不扣、绘图扣 1），**不是 token** |
| 实测时延 | 首字节 2.5–10 s、整轮 6–10 s（p95 ~19 s）、绘图 60–240 s |

---

## 2. 15 分钟验收路径（先跑通，再谈接渠道）

```bash
git clone https://github.com/lza6/Channel-AI-APP-2api && cd Channel-AI-APP-2api

# ① 上游桥（小池 + 自动扩容到 16）
python -X utf8 demo_server.py --port 8921 --pool 4 --min-idle 4 --hard-max 16 \
       --grow-step 4 --api-key channel-local-key

# ② 三条自检
curl -s http://127.0.0.1:8921/health
curl -s -H 'Authorization: Bearer channel-local-key' \
     'http://127.0.0.1:8921/api/bots?type=character&limit=5'
curl -s -X POST http://127.0.0.1:8921/v1/chat/completions \
     -H 'Content-Type: application/json' -H 'Authorization: Bearer channel-local-key' \
     -d '{"model":"Stranger","messages":[{"role":"user","content":"用一句话介绍自己"}]}'

# ③ 压测（13 断言 / 约 1 分钟）
CHANNEL_API_KEY=channel-local-key python -X utf8 stress_test.py \
     --base http://127.0.0.1:8921 --concurrency 8
# 期望：13/13 PASS

# ④ 账号层压测（12 断言：自动新号/自动扩容/重启复用）
python -X utf8 pool_test.py
# 期望：12/12 PASS
```

---

## 3. new-api 渠道配置（照抄）

### 3.1 对话渠道

| 字段 | 值 | 说明 |
|---|---|---|
| 类型 | **OpenAI**（`ChannelTypeOpenAI = 1`） | 桥接层就是 OpenAI 协议 |
| Base URL | `http://127.0.0.1:8921` | **不要带 `/v1`、不要带尾斜杠**（new-api 会自己拼 `/v1/chat/completions`） |
| 密钥 | `channel-local-key` | = 桥 `--api-key`；桥不设 key 时填任意非空值 |
| 模型 | bot 的 `username`，如 `0_b2cf4ea3-b728-4112-be3d-9829d950bcea` | 一行一个 |
| 模型重定向 | `channel-stranger` → `0_b2cf4ea3-…` | 把友好名映射到 bot（推荐，便于给用户看） |
| 渠道设置 JSON | `{"relay_timeout_seconds": 120}` | 长尾保护 |

> Docker 里的 new-api 访问宿主机：Base URL 用 `http://host.docker.internal:8921`。

### 3.2 绘图渠道（可同渠道，也可另建）

| 字段 | 值 |
|---|---|
| 类型 / Base URL / 密钥 | 同上 |
| 模型 | 绘图 bot 的 `username`（`curl '/api/bots?type=image&limit=20'` 取） |
| 渠道设置 JSON | `{"relay_timeout_seconds": 400}` ← **必须**，否则 240 s 出图被掐断 |

```bash
curl -s -X POST http://127.0.0.1:8921/v1/images/generations \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer channel-local-key' \
  -d '{"model":"0_77932319-ce40-40fd-8b69-de2561b659da","prompt":"cat on a windowsill, cinematic light"}'
# → {"data":[{"url":"https://osscdn.siki.ai/xxx.jpg","revised_prompt":"…"} ×3]}
```

---

## 4. 必调参数（不改会误判失败）

| 参数 | 位置 | 建议值 | 原因 |
|---|---|---|---|
| `RELAY_TIMEOUT` | 环境变量（秒，0=不限） | `600` | 绘图最慢 240 s |
| `relay_timeout_seconds` | 渠道设置 JSON | 对话 `120` / 绘图 `400` | 覆盖全局，长尾不被 kill |
| `stream_first_token_timeout` | 全局 relay 设置 | ≥ `20` | 我们首字节 2.5–10 s，个别 40 s+ |
| `disable_stream_first_token_timeout` | 渠道设置 JSON | `true` | 慢 bot 不被判渠道故障 |
| `pass_through_body_enabled` | 渠道设置 | **不要开** | 上游只认 `model`/`messages` |
| `request_compression` | 渠道设置（默认开） | 保持默认 | 桥已支持 gzip 请求体（实测 200） |

---

## 5. 八个坑（现象 → 处置）

| 现象 | 根因 | 处置 |
|---|---|---|
| 测试 404 | Base URL 写成 `…:8921/v1` → `/v1/v1/chat/completions` | Base URL 只写到端口 |
| 401 | 桥 `--api-key` 与渠道密钥不一致 | 两边一致，或桥不设 key |
| 504 / 超时 | 非流式 + 慢 bot | 调 `relay_timeout_seconds`；客户端改 `stream:true` |
| `502 no reply from … within 120s` | 该 bot 冷/挂起（上游偶发） | 配多个 bot 做模型重定向 + 重试；或换高互动 bot |
| 返回 3 张图但界面只显示 1 张 | 上游固定一次出 3 张，`n` 参数被忽略 | 正常现象 |
| 并发上不去 | 池容量小于并发且关了扩容 | 开 autoscale：`--hard-max` 抬高硬顶 |
| 换机后首个请求很慢 | 池未预热 | 保持 `--min-idle = --pool` |
| `/api/bots` 偶发 500/超时 | 目录 CDN TLS 抖动（本机 18–28 s 甚至失败） | 已内建 single-flight + 缓存 + stale 兜底；对话走 `0_<uuid>` 不依赖 CDN |

---

## 6. 验收清单

- [ ] `/health` 返回 `status: ok`，`pool.cap ≥ 1`
- [ ] `/api/bots?type=character` 返回 ≥ 50 个 bot
- [ ] 经 **new-api**（不是直连桥）跑 `chat/completions` 非流式 → 有内容、`finish_reason: stop`
- [ ] 经 new-api 跑 `stream: true` → 收到多个 `data:` 分片 + `[DONE]`
- [ ] 经 new-api 跑 `/v1/images/generations` → 返回 ≥1 个 `osscdn.siki.ai` 直链且能 `curl` 下来
- [ ] 未知模型返回 404（不是 500/502）
- [ ] 20 并发跑一遍，成功率 100%，`/stats` 里 `chat_ok + chat_error == requests`
- [ ] 重启桥后 `/stats` 显示 `accounts_registered = 0`（走复活，不重复注册）

---

## 7. 可直接粘贴给"对接会话"的 prompt

```text
任务：把 Channel 2API 接到 new-api（你只做渠道接入与联调，不改上游桥的协议实现）。

仓库：https://github.com/lza6/Channel-AI-APP-2api  （Python 标准库，无第三方依赖）
上游桥：python -X utf8 demo_server.py --port 8921 --pool 4 --min-idle 4 --hard-max 16 \
        --grow-step 4 --api-key channel-local-key
能力：对话 bot 169 个 + 绘图 bot 18 个；OpenAI 兼容 /v1/chat/completions（支持 SSE）与
      /v1/images/generations；模型名 = bot 的 username（0_<uuid>）。

要求：
1. 先按仓库 docs/HANDOFF.md 第 2 节跑通三条自检 + stress_test.py（须 13/13 PASS），
   再动 new-api 配置；跑不通先报告，不要改上游桥。
2. 在 new-api 建渠道：类型 OpenAI(1)，Base URL = http://127.0.0.1:8921（不带 /v1），
   密钥 = channel-local-key，模型 = 0_<uuid> 或模型重定向友好名→0_<uuid>。
   对话渠道设置 {"relay_timeout_seconds":120}，绘图渠道 {"relay_timeout_seconds":400}。
3. 全局参数：RELAY_TIMEOUT=600；stream_first_token_timeout ≥ 20；
   渠道 disable_stream_first_token_timeout=true；不要开 pass_through_body_enabled。
4. 按 HANDOFF.md 第 6 节验收清单逐项验证，每项附实际命令与输出；
   20 并发一轮必须 100% 成功。
5. 不要改动 new-api 的受保护品牌信息（项目名/作者标识）；不要提交任何 key 或账号文件
   （accounts.jsonl 已在 .gitignore）。
6. 遇到"502 no reply"属上游 bot 冷/挂，配置多 bot 重定向 + 重试即可，不要把它当桥的 bug。

交付：渠道配置截图/JSON、验收清单逐项证据、剩余风险与已知限制说明。
```

---

## 8. 速查

```bash
# 上游桥
python -X utf8 demo_server.py --port 8921 --pool 4 --min-idle 4 --hard-max 16 --grow-step 4 \
       --api-key channel-local-key
# 观测
curl -s http://127.0.0.1:8921/stats | python -m json.tool
# 纯协议最小复现（不装 App、不开模拟器，证明链路可用）
python -X utf8 pure_protocol_demo.py
```
