# 对接 new-api 指南（Channel 2API）

> 本文给"另一个会话来执行对接"用。目标：把本仓库的 Channel 上游接到 new-api，跑通
> `/v1/chat/completions`（含 SSE）与 `/v1/images/generations`。
> 所有数字都是本机实测（2026-10-29，见 `docs/ANALYSIS.md`）。

---

## 0. TL;DR

| 路径 | 工作量 | 适用 | 建议 |
|---|---|---|---|
| **A. OpenAI 兼容渠道**（把 `demo_server.py` 当上游） | 0 行代码，10 分钟 | 立刻可用、验证能力 | ✅ **先做这个** |
| B. 原生 Go 渠道移植（XMPP 直接进 new-api） | 6 个文件 + 会话池移植 | 要单进程、要精细计费 | 能力验证通过后再做 |

关键事实（决定对接参数）：

| 事实 | 数值 | 含义 |
|---|---|---|
| 首字节 | 2.5–10 s（个别 bot 40–90 s） | 首包超时别设 < 15 s |
| 整轮 | 6–10 s（p95 ~19 s） | 非流式超时 ≥ 60 s |
| 绘图 | 60–240 s | 绘图渠道 `relay_timeout_seconds` ≥ 400 |
| 单账号并发 | **1**（一个 XMPP 会话串行） | 并发能力 ＝ 账号池大小 |
| 账号预热 | 4–5 s/个（并行 4 个 ≈ 14 s 全好） | 池要预热，不要懒加载 |
| energy | 5/账号（免费），文本不扣、绘图扣 1 | 绘图是消耗品，注意号池规模 |
| 模型 | 169 个对话 bot + 18 个绘图 bot | 用 bot `username` 当模型名 |

---

## 1. 路径 A：OpenAI 兼容渠道（推荐）

### 1.1 起上游桥

在能访问 `x.siki.ai` 的机器上（与 new-api 同机最简单）：

```bash
# 常态小池 + 突发自动扩容（推荐）
python -X utf8 demo_server.py --port 8921 --pool 4 --min-idle 4 --hard-max 16 --grow-step 4        --api-key channel-local-key
```

| 参数 | 说明 |
|---|---|
| `--pool` | 初始并发容量（= 同时可跑的对话数） |
| `--min-idle` | 预热会话数，建议 = `--pool`（并行注册/复活，约 4–5 s/个） |
| `--hard-max` | 自动扩容硬顶；排队出现时容量按 `--grow-step` 往上抬到这里（0=自动取 `pool*3`） |
| `--grow-step` | 每次扩容步长（默认 2） |
| `--max-reg-per-min` | 每分钟最多注册多少新号（默认 30，给上游注册打闸） |
| `--no-autoscale` | 关掉自动扩容，容量固定为 `--pool` |
| `--api-key` | 上游桥的鉴权；new-api 渠道"密钥"填同一个值 |
| `--store` | 账号库路径（默认 `accounts.jsonl`），**重启会复用，不会重复注册** |

自检（不经过 new-api）：

```bash
curl -s http://127.0.0.1:8921/health
curl -s http://127.0.0.1:8921/v1/models | head -c 300
curl -s -X POST http://127.0.0.1:8921/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer channel-local-key' \
  -d '{"model":"Stranger","messages":[{"role":"user","content":"用一句话介绍自己"}]}'
```

> Docker 里的 new-api 访问宿主机：Base URL 用 `http://host.docker.internal:8921`。

### 1.2 建渠道（对话）

new-api 后台 → 渠道 → 新建：

| 字段 | 值 |
|---|---|
| 类型 | **OpenAI**（`ChannelTypeOpenAI = 1`） |
| Base URL | `http://127.0.0.1:8921` ← **不要带 `/v1`，不要带尾斜杠**（new-api 会拼 `/v1/chat/completions`） |
| 密钥 | `channel-local-key`（= 上游桥 `--api-key`；不设则填任意非空值） |
| 模型 | 直接填 bot 的 `username`，一行一个，例如 `0_b2cf4ea3-b728-4112-be3d-9829d950bcea` |
| 模型重定向（可选） | `channel-stranger` → `0_b2cf4ea3-…`，把友好名映射到 bot |
| 分组 / 权重 | 按需 |

拿 bot 列表：

```bash
curl -s 'http://127.0.0.1:8921/api/bots?type=character&limit=200' \
  | python -c "import json,sys;[print(b['id'], b['display_name'], b['interactions']) for b in json.load(sys.stdin)['data'][:20]]"
```

`model` 三种写法都支持：`0_<uuid>`（推荐，唯一）、`0_<uuid>@x.siki.ai`、显示名（`Stranger`，可能重名）。

### 1.3 建渠道（绘图）

同一类型（OpenAI）再建一个渠道（或同渠道加模型）：

| 字段 | 值 |
|---|---|
| Base URL | `http://127.0.0.1:8921` |
| 模型 | 绘图 bot 的 `username`（`curl /api/bots?type=image`） |
| 渠道设置 JSON | `{"relay_timeout_seconds": 400}` ← **必须**，否则 240 s 的等待会被掐断 |

调用：

```bash
curl -s -X POST http://127.0.0.1:8921/v1/images/generations \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer channel-local-key' \
  -d '{"model":"0_77932319-ce40-40fd-8b69-de2561b659da","prompt":"cat on a windowsill, cinematic light"}'
# → {"created":…, "data":[{"url":"https://osscdn.siki.ai/xxx.jpg","revised_prompt":"…"}, ×3]}
```

### 1.4 必调的 new-api 参数（否则会误判失败）

| 参数 | 位置 | 建议值 | 原因 |
|---|---|---|---|
| `RELAY_TIMEOUT` | 环境变量（秒，0=不限） | `600` | 绘图最慢 240 s |
| `relay_timeout_seconds` | 渠道设置 JSON | 对话 `120`，绘图 `400` | 覆盖全局，避免长尾被 kill |
| `stream_first_token_timeout` | 全局 relay 设置 | ≥ `20` | 我们首字节 2.5–10 s，个别 40 s+ |
| `disable_stream_first_token_timeout` | 渠道设置 JSON | `true` | 慢 bot 不被判成渠道故障 |
| `request_compression` | 渠道设置（默认开） | 保持默认 | 上游桥已支持 gzip 请求体（实测通过） |
| `pass_through_body_enabled` | 渠道设置 | **不要开** | 上游只认 `model`/`messages`，透传无意义 |

### 1.5 已知坑（对号入座）

| 现象 | 原因 | 处置 |
|---|---|---|
| new-api 测试返回 404 | Base URL 写成 `…:8921/v1` → 变成 `/v1/v1/chat/completions` | Base URL 只写到端口 |
| 401 | 上游桥 `--api-key` 与渠道密钥不一致 | 两边一致，或上游不设 key |
| 504/超时 | 用了非流式 + bot 慢 | 调 `relay_timeout_seconds`；客户端改 `stream:true` |
| `502 no reply from … within 120s` | 该 bot 冷/挂起（上游偶发） | 渠道配多个 bot 做模型重定向 + 重试；或换高互动 bot |
| 返回 3 张图但 new-api 只显示 1 张 | 上游固定一次出 3 张，`n` 参数被忽略 | 正常现象，文档写清即可 |
| 并发上不去 | 账号池小于并发且关了扩容 | 开 autoscale：`--hard-max` 抬高硬顶；池满会排队而不是失败 |
| 突发后延迟变长 | 扩容中（每个新号 4–5 s 冷启动） | 正常；稳态请求走已预热会话，可提前 `--min-idle` 抬高 |
| `/api/bots` 偶发 500/超时 | 目录 CDN TLS 抖动（本机实测 18–28 s 甚至失败） | 已内建 single-flight + 缓存 + stale 兜底；对话走 `0_<uuid>` 时不依赖 CDN |
| 换机器后第一次请求很慢 | 池未预热 | 保持 `--min-idle = --pool` |
| 请求体被压缩导致 400 | 旧版上游桥不认 gzip | 本项目已支持；老版本请升级或关 `request_compression` |

---

## 2. 路径 B：原生 Go 渠道（想单进程 / 精细计费时）

### 2.1 为什么不能只写 HTTP 适配

Channel 的对话是 **XMPP**（`x.siki.ai:443` 直连 TLS），没有 REST 发消息接口。
Go 侧必须自带一个 XMPP 会话池（等价于本仓库 `channel_client.py` + `accounts.py`）。

### 2.2 注册链（6 处）

按 new-api 现有渠道惯例（参考 `relay/channel/imagerator/`、`notrack`）：

1. `common/constants.go`（或 `constant/channel.go`）：新增 `ChannelTypeChannelAI = <下一个空闲号>` 与名称表
2. `relay/channel/channelai/adaptor.go`：`Init / GetRequestURL / SetupRequestHeader / ConvertOpenAIRequest / DoRequest / DoResponse / GetModelList`
3. `relay/channel/channelai/dto.go`：内部请求体（`{bot, prompt, quiet, max_seconds}`）
4. `relay/channel/channelai/pool.go`：**XMPP 会话池**（移植 `accounts.py`：注册→SASL→vCard→预热→ping 健康检查→坏会话替换）
5. `relay/relay_adaptor.go`：`case ChannelTypeChannelAI: return &channelai.Adaptor{}`
6. `web/src/...` 渠道类型下拉 + i18n（若前端要露出该类型）

### 2.3 协议映射（照抄即可）

| OpenAI 侧 | Channel 上游 | 备注 |
|---|---|---|
| `messages[-1].content` | `<body>` | 只发**最后一条** user 消息：上游按账号保存上下文，多轮自己延续 |
| —— | `stanza id` 必须 **UUID v4** | 非 UUID → 上游只回执不生成（本项目最大的坑） |
| —— | `<publictoken xmlns='proximity:publictoken'>` 自己的 pt | 必须带 |
| 回复 `<body>` 序列 | `choices[0].message.content`（多段用 `\n` 拼接） | 每段一条 message |
| `<thinking/>` chatstate | 可选映射到 `reasoning_content` | 只表示"正在思考" |
| `<imagedata fullimageurl=…>` | `/v1/images/generations` 的 `data[].url` | 一次 3 张 |
| `<balanceupdate><energy>` | 计费旁路（非 token） | 见 2.5 |

### 2.4 会话池参数（Go 版照此实现）

```
max_size        = 渠道设置 pool_size（默认 4）
min_idle        = max_size（启动预热）
每次请求         = acquire → 用 → release；会话内串行（1 并发）
健康检查         = 空闲会话在 acquire/release 时各 ping 一次，失败即丢弃并补新
账号持久化       = accounts.jsonl（username/password/device_id/publictoken/计数）
坏号策略         = fails≥3 标记 disabled；仍可用 credentials 复活（SASL 不需要重新注册）
```

**容量公式**：`可持续并发 ≈ cap`（cap 会从 `--pool` 自动涨到 `--hard-max`），`QPS ≈ cap / 平均延迟(≈8 s)`。
例：`--pool 4 --hard-max 16` → 稳态 ~0.5 QPS，突发可冲到 16 并发（约 2 QPS）；
要长期 4 QPS 就得 `--hard-max ≈ 32`（32 个号，首次预热约 1 分钟，之后都走复活）。

**扩容实测（4 会话池 / 8 并发）**：`cap 8`、`queued_acquires=0`、`discarded=2`、全绿。
**扩容实测（2 会话池 / 12 并发 / hard_max 10）**：12/12 成功，wall 31.5 s，`grown=8`、
`accounts_registered=5`（现场注册）、`spawn_errors=0`。

### 2.5 计费建议

上游单位是 **energy**（账号级，文本不扣、绘图 1 次 1 点），不是 token。
两种做法：

- **按次计费**（推荐）：`model` 级固定 quota/次；绘图与对话分别定价
- **估算 token**：`tokens ≈ len(text) / 4`（本项目 demo 就这么算，仅作展示）

不要用上游 `usage`——它不返回。

### 2.6 验证门禁（不要跳）

```bash
cd relaykit && GOWORK=off go build ./...      # relaykit 独立可构建
go build ./...                                 # 主模块
scripts/staging.ps1 verify                     # 部署前本地 staging 门禁
```

无 schema 变更 → 三数据库矩阵可跳过；有 channel 设置 JSON 变更 → 至少验 SQLite + PostgreSQL 读写。

---

## 3. 能力矩阵（对接时决定挂多少模型）

| 能力 | 规模 | 说明 |
|---|---|---|
| 对话 bot | 169（`config_type=character`） | 角色扮演，NSFW 可选；`interaction_count` 越高越稳 |
| 绘图 bot | 18（`config_type=image`） | 一次 prompt 出 3 张，`osscdn` 直链无水印 |
| 目录/搜索 | 17 分类 | 匿名接口，不需要账号 |
| showcase | prompt 原文 + 图 | 可直接当提示词样例库 |
| 免费额度 | energy 5/账号 | 绘图消耗；文本不消耗 |

---

## 4. 观测与调参

`GET /stats` 关键字段：

| 字段 | 含义 | 健康值 |
|---|---|---|
| `latency_ms.p50 / p95` | 端到端 | p50 6–10 s / p95 < 25 s |
| `pool.live_sessions / max_size` | 会话占用 | 稳态 = max_size |
| `pool.queued_acquires` | 排队次数 | 持续增长 → 池太小 |
| `pool.discarded` | 被丢弃的死会话 | 少量正常（上游会踢空闲流） |
| `pool.accounts_registered` | 新注册数 | 首次启动后应停止增长（走复用） |
| `pool.accounts_revived` | 复活数 | 重启后应等于 pool_size |
| `pool.store.free` | 账号库空闲号 | 0 且 queue 增长 → 加号 |

---

## 5. 一页速查

```bash
# 上游桥
python -X utf8 demo_server.py --port 8921 --pool 8 --min-idle 8 --api-key channel-local-key

# 能力自检
curl -s http://127.0.0.1:8921/health | python -m json.tool
curl -s -X POST http://127.0.0.1:8921/v1/chat/completions -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer channel-local-key' \
  -d '{"model":"Stranger","messages":[{"role":"user","content":"hi"}],"stream":true}'

# new-api 渠道
#   类型=OpenAI(1)  Base=http://127.0.0.1:8921  密钥=channel-local-key
#   模型=0_<uuid>（或模型重定向 友好名→0_<uuid>）
#   渠道设置={"relay_timeout_seconds":120}  绘图渠道 =400

# 压测（改 --concurrency 看池行为）
python -X utf8 stress_test.py --base http://127.0.0.1:8921 --concurrency 8
```
