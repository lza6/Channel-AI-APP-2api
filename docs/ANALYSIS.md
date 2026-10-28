# Channel 1.6.1.3330 · 逆向分析报告（第一轮）

> 目标：`Channel_1.6.1.3330_Mod_Paid.apk`（`com.channel.ai`，122 MB，Mod Paid）
> 分析时间：2026-10-29 · 工作目录：`D:/apk-analysis/channel-ai/`
> 结论标签：`已验证`＝本机实际跑通并观察到结果；`静态确认`＝读反编译代码确认；`合理推断`＝有间接证据；`待验证`＝缺条件

---

## 1. 应用身份

| 项 | 值 | 证据 |
|---|---|---|
| 包名 / 版本 | `com.channel.ai` / 1.6.1.3330 (1613330) | `AndroidManifest`、`BuildConfig` |
| 应用名 / 类型 | Channel — AI 角色陪伴聊天（NSFW 可选），带 AI 绘图 | `assets/onboarding/*.json`、`assets/girlnames.txt` |
| minSdk / target | 26 / 35 | 静态确认 |
| 壳 / 加固 | **无 dex 壳**；`libprotect.so`+`libstub.so` 是 Mod 作者 (`com.rh.protect`) 的付费去广告包裹层，`libuniffi_cel.so` 只是 CEL 表达式求值（Unleash 特性开关用） | 静态确认 |
| 主要 SDK | Amplitude、RevenueCat、Superwall、AppLovin/AdMob、Singular、Sentry、AWS S3、Auth0、Smack(XMPP)、ACRCloud | `BuildConfig` + dex 字符串 |

`BuildConfig`（jadx 反混淆后常量名被折叠成 `n`，按字符串值还原）：

```
XMPP_HOST            = x.siki.ai            # 直连 TLS XMPP，端口 443
XMPP_PORT            = 443
OAUTH_HOST           = https://x.siki.ai:5443/
PUBLIC_API_URL       = https://d11absfiaqzcnz.cloudfront.net/     # 匿名可读的目录服务
PRIVATE_API_URL      = https://admin-api-prod.shroom.gg           # 需 Bearer 的业务 REST
PUBLIC_IMAGES_URL    = https://osscdn.siki.ai/
AWS_BUCKET           = channel-ej
UNLEASH_URL/KEY      = https://unleash.baseclub.co/api/frontend/ + token
AMPLITUDE_KEY_PROD   = 0efbcc3f56912e80b68cd18d19150fa7
```

> 注意：dex 里出现的 `https://api-production.8-lives-cat.io/` 是 **RevenueCat SDK 的 fallback URL**
> （jadx 把包名字符串折叠成了 `n`），与 Channel 业务无关——这是一条容易误判的假线索。

平台侧命名空间为 `proximity:*`（Proximity 系聊天中台），Siki 是同一套中台的另一个白标，
Channel 是它的贴牌客户端（`channel.surf` / `channel.bot` 为对外域名）。

---

## 2. 认证链路（核心发现）

### 2.1 游客注册**不需要短信**

`RegistrationActivity.initGuestRegistration()` + `Dao.generateGuestPacket()`：

```xml
<iq id="<uuid>" type="set">
  <query xmlns="jabber:iq:register">
    <username>tmp_<country>_<md5(country + "." + digits(deviceId+uuid))></username>
    <password><md5(deviceId)></password>
    <verificationcode>sc:<deviceId></verificationcode>
    <resource>android-1.6.1.3330-14-en-US-<tz>-<rand20></resource>
  </query>
</iq>
```

* 这条 IQ 在 **SASL 认证之前** 就发（`UnauthenticatedStandardXMPPAction`），服务端直接受理。
* 返回 `<iq type='result'>` 回显 query＝注册成功；同名重注册返回 `405 not-allowed`（可用于探测账号是否存在）。
* `verificationcode` 字面量就是 `sc:` + deviceId，**没有任何服务端校验**，因此无需手机号/SMS。
* 用户名只由 `deviceId` 决定 ⇒ 换个 `deviceId` 即换一个新账号，天然形成"设备池"。

**实测（已验证）**：连续注册 20+ 个账号全部成功，单账号注册+PIN 握手 ≈ 2.8 s。

### 2.2 SASL 成功响应里直接给 REST 的 JWT

```
C: <auth mechanism='PLAIN'>base64(\0<localpart>\0<password>)</auth>
S: <success jwt='eyJhbGciOiJIUzI1NiIs...' xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>
```

* `authcid` 必须是 **localpart**（写成完整 JID 会 `<invalid-xml>` 断流）。
* JWT 的 `sub` = 账号 bare JID，`exp` ≈ 30 天；它同时是 REST 的 `Authorization: Bearer`。
* App 里另有 `proximity:jwt:token` IQ 刷新通道，但**首轮不需要**——SASL 已经给了。

### 2.3 REST 需要的三个头

```
Authorization: Bearer <jwt>
jid: <bare jid>            # 完整 jid 或 localpart 均可
client: android
```

**实测（已验证）**

```
GET https://admin-api-prod.shroom.gg/api/v2/currency/balances
→ 200 {"coins":0,"energy":5,"maxEnergy":5,"slowModeAvailable":false,"nextEnergyRecharge":null}
```

无 JWT → `401 {"reason":"Unauthorized"}`。公开域名 `d11absfiaqzcnz.cloudfront.net` 走 `/public/*`
回源，不需要任何头即可读取目录。

---

## 3. 协议面

### 3.1 REST（Retrofit `ChannelApi`，路径已完整还原）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `api/v2/character/auto-fill` | 角色卡 AI 补全 |
| POST | `api/v2/character/create` / `edit` / `delete` | 角色 CRUD |
| POST | `api/v2/avatar/generate` / `locate-face` | 头像生成 / 人脸框 |
| GET | `api/v2/currency/balances` | coins / energy / slowMode |
| GET | `api/v2/chat/conversations`、`api/v2/chat/messages/sync` | 会话历史（含 `historyCutoff`） |
| POST | `api/v2/chat/delete` | 删除会话 |
| POST | `api/v2/message/reroll` / `replace` | 重生成 / 改写消息 |
| POST | `api/v2/onboarding/save` | 落库 onboarding（返回 `persona created successfully`） |
| GET | `api/v2/sidekick/{jid}`、`character/my-characters` | 角色详情 |
| GET | `v2/sidekick/search`、`v2/category/{cat}`、`sidekick/category/allnames`、`sidekick/showcase`、`welcome` | 目录（匿名，走 CDN） |

**这个 App 的"发送消息"没有 REST 接口** —— 聊天全部走 XMPP。

### 3.2 XMPP 自定义命名空间（`_legacy/xmpp`、`_legacy/ui/utils/XMPPActions`）

```
proximity:jwt:token         取/刷新 JWT          proximity:publictoken      消息内嵌发送者 publictoken
proximity:sidekick:getbyusername  角色解析        proximity:vcardlookup      按 jid/temptoken 查 vCard
proximity:users:lookup      用户搜索             proximity:uploads          上传凭证
jabber:iq:register          游客/手机注册        jabber:iq:roster           好友
proximity:muc:*             群组               proximity:channels*         频道
```

### 3.3 发消息与收消息（已验证）

```xml
<!-- 发送（关键：id 必须是 UUID，且必须带自己的 publictoken） -->
<message id="<UUID v4>" to="0_<uuid>@x.siki.ai" type="chat">
  <publictoken xmlns="proximity:publictoken">pt_<uuid>@x.siki.ai</publictoken>
  <body>你好</body>
  <request xmlns="urn:xmpp:receipts"/>
  <active xmlns="http://jabber.org/protocol/chatstates"/>
  <nick xmlns="http://jabber.org/protocol/nick">Guest</nick>
</message>
```

回复时序（单个 bot）：

```
+0.19s  <message ...><received type='server' id='<uuid>'/>          ← 服务器投递回执
+0.19s  <message ...><publictoken>pt_bot@x.siki.ai</publictoken>…  ← 回显 bot 的 publictoken（= vCard 替代）
+0.23s  <thinking xmlns='http://jabber.org/protocol/chatstates'/>   ← "正在思考"
+2-4s   <message ...><nick>Stranger</nick><active/><body>…</body></message>  ← 真正回复
        <balanceupdate><energy>5</energy>…</balanceupdate>          ← 纯文本不扣 energy
```

* 每条 stanza 服务器会**镜像两份**（`to=bare` 与 `to=bare/resource`），按 stanza `id` 去重。
* 首字节（`thinking` → `body`）实测 **2.5–4.1 s**，整轮 6–9 s（含 2.5 s 静默判定窗口）。
* 上下文由服务端按账号保存，同一 XMPP 会话多轮对话可延续（已验证 turn2 能复述 turn1）。

### 3.4 走过的坑（都在代码里修掉了）

| 坑 | 现象 | 根因 / 修法 |
|---|---|---|
| stanza `id` 用非 UUID | 只收到回执，AI 永不回复 | AI worker 要求 UUID 格式 id |
| vCard 元素写成 `<vcard>` | `Unknown tag <vcard/> qualified by namespace 'vcard-temp'` | 大小写敏感，必须 `<vCard xmlns='vcard-temp'/>` |
| 不带 `publictoken` 元素 | 同样只回执不生成 | 每条消息必须带**自己的** publictoken |
| 对 bot 的 `pt_` JID 发 `type='publicchat'` | `service-unavailable` 并回显我的 body | 对话必须发 `0_<uuid>@x.siki.ai` + `type='chat'` |
| bind 之后不回 ping | 空闲 ~30 s 被服务端断流 | 读循环内即时 `<iq type='result' id=…/>` |
| 本机 DNS 把 `x.siki.ai` 解析到 127.0.0.1 | `ConnectionRefusedError 10061` | 走 DoH（1.1.1.1 / dns.google）取真实 A 记录（`13.248.161.98` / `76.223.77.20`）后按 IP 连接、SNI 仍用域名 |

---

## 4. 目录 / 模型面（匿名可读）

| 接口 | 返回 | 实测 |
|---|---|---|
| `GET /sidekick/category/allnames?version=1` | 17 个分类（含 `has_chatbot` / `has_imagebot`） | ✅ |
| `GET /v2/category/newexplore?limit=250` | 187 个 sidekick：169 个 `character`（可对话）+ 18 个 `image`（绘图） | ✅ |
| `GET /v2/sidekick/search?search_term=&include_nsfw=&limit=` | 搜索 | ✅ |
| `GET /sidekick/showcase?allow_nsfw=false` | 绘图样例，**含 prompt 原文** + `osscdn.siki.ai` 图片直链 | ✅ |
| `GET /welcome`（需 `jid` 头） | 新用户默认 bot | ✅ |

单个 bot 的关键字段：`username`(=JID localpart)、`bare_jid`、`publictoken`、`config_type`
(`character`|`image`)、`can_generate_text`、`can_generate_images`、`image_generator_jid`、
`interaction_count`（可直接当"热度"排序）、`avatar_image.{small,medium,large}_url`。

---

## 5. 计费 / 额度面

`currency/balances` 给的是 `energy / maxEnergy`（新游客 5/5）+ `coins` + `slowModeAvailable`。

* **纯文本对话实测不扣 energy**（连续 5 轮后仍 5/5）。
* **绘图扣 energy**：一次请求后 `energy` 由 5 → 4，并给出 `nextEnergyRecharge`（2 小时后回充）。
* 未做真实付费调用（红线），绘图只消耗账号自带的免费 energy。

### 5.1 绘图链路（已验证）

对 `config_type=image` 的 bot（如 `Illustrious XL` / `Real Amateur Photos`）用**同一条 chat 文本消息**发 prompt 即可，
上游先把 prompt 交给图像模型，再连发多条消息：

```xml
<message ...><imageWrapper type='image' estimatedTimeInSeconds='11'/>…</message>   <!-- 先告知预估 -->
<message ...><generationmetadata><creatordata .../></generationmetadata>
            <balanceupdate><energy>4</energy>…</balanceupdate>
            <body>🌟 Generating images...</body></message>
<message ...><imagedata fullimageurl='https://osscdn.siki.ai/<uuid>.jpg'
                       previewimageurl='https://osscdn.siki.ai/<uuid>.jpg?image_process=resize,w_400,h_600/format,webp'
                       prompt='(masterpiece, best quality)…<lora:…>' userInputtedPrompt='…' genindex='0'/>
            <body>📷 Image</body></message>   <!-- 每次出图一条，实测一次请求出 3 张 -->
```

* 实测一次 prompt 返回 **3 张** `osscdn.siki.ai` 直链（`genindex` 0/1/2），
  `curl -I` 校验 `200 image/jpeg 132 KB`，**无水印**。
* 出图耗时约 **60–180 s**（`estimatedTimeInSeconds≈11` 只是首图预估，3 张串行渲染更久）。
* 注意 `prompt` 属性里会含**未转义的 `>`**（`&lt;lora:x:0.3>`），解析必须按 `…/>` 切割而不是 `[^>]*`。

---

## 6. 本轮达成 / 未达成

**已达成的真实链路（全部本机跑通）**

1. 无短信批量游客注册 → JWT → REST 鉴权（20+ 账号）
2. 匿名目录：17 分类 / 187 bot / showcase prompt
3. XMPP 多轮对话：OpenAI 兼容封装 `/v1/chat/completions`（含 `stream=true` SSE）
4. 并发 2 路（账号池 2 会话，队列化）13/13 压测项 PASS
5. 绘图：`Illustrious XL` 一次 prompt → 3 张 `osscdn.siki.ai` 直链（无水印、可下载、energy 5→4）（见 §5.1）

**未达成 / 待验证**

* `proximity:vcardlookup`、`proximity:sidekick:getbyusername` 在本部署返回
  `No module is handling this query`（推测这些模块挂在别的子域/组件上，需要抓真机流量确认）。
* 单张图的渲染完成时延不稳定（60–180 s），`/v1/images/generations` 默认等 240 s；
  超时会返回已捕获到的部分结果，需要在调用侧按需加大 `max_seconds`。
* 未验证手机号/OAuth 账号与游客账号的能力差异（游客是否有隐藏限流）。
* Mod 版与原版的差异（去广告/解锁付费）未逐一比对；`libprotect.so` 只做展示文案。

---

## 7. 复现命令

```powershell
cd D:\apk-analysis\channel-ai
python -X utf8 channel_client.py            # 协议层自检（注册→JWT→vCard→对话）
python -X utf8 demo_server.py --port 8921 --pool 2
python -X utf8 stress_test.py --base http://127.0.0.1:8921 --concurrency 2
```

原始报文留档：`artifacts/turn1.xml` / `turn2.xml` / `turn3.xml`（多轮）、
`artifacts/first_chat_transcript.txt`、`artifacts/image_reply.xml`、`artifacts/dex_strings.txt`。
