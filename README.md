# Auto Group

NoneBot2 + LLBot/LLOneBot 群管理与群运营后台。

## 功能

- 自动处理加群请求：可视化答案规则，支持包含、完全匹配、正则、AND/OR。
- 入群风控：QQ 账号等级限制、答错次数达到阈值自动加入加群黑名单，自动填写完整备注。
- 入群图片验证：新人进群后 @ 欢迎并发验证码，答错依次禁言 10/20/30 秒，第 4 次踢出。
- 自动群分流：按群优先级和容量推荐群，申请非推荐群时拒绝并提示推荐群。
- 退群监听：记录退群 QQ、群、类型和操作者。
- 一键去重：先预览，确认后保留最高优先级群，踢出低优先级重复成员。
- 公告管理：同步公告、批量发送、删除公告。
- 群文件管理：上传一份文件，选择多个群批量分发，同步/删除群文件。
- 精华管理：发送指定内容后自动设精，支持同步和移出精华。
- 消息审查：正则命中后自动处理，可按规则开启腾讯云文本内容安全二次审核。
- 多模态图片审核：兼容 OpenAI Chat Completions，支持 ToolCall、JSON Schema、自定义提示词和思考预算。
- 批量撤回：独立 SQLite 缓存最近 2 万条群消息，按 QQ 授权命令管理员，并发撤回并自动跳过失败消息。
- 公开分流页：`#/join` 自动展示当前推荐入群链接。

## 环境

- Python 3.10+
- uv
- Node.js 22.12+ 或更新的 LTS 版本
- LLBot/LLOneBot，使用 OneBot v11 反向 WebSocket

## 后端启动

```powershell
uv sync
Copy-Item .env.example .env
uv run auto-group
```

默认监听 `http://127.0.0.1:8080`。

也可以使用 NoneBot CLI 启动：

```powershell
uv run nb run
```

项目已经在 `pyproject.toml` 配置了 `[tool.nonebot]`，`nb run` 会加载 `app.bot.dashboard` 和 `app.bot.events`，因此机器人事件、数据库初始化和后台 API 都会一起启动。`nb run` 输出的“旧的项目格式”只是 nb-cli 的格式提示，不影响运行。

LLBot/LLOneBot 反向 WS 地址配置为：

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

如果日志出现 `keepalive ping timeout`，可以在 `.env` 调大 `WS_PING_TIMEOUT_SECONDS`，或将 `WS_PING_INTERVAL_SECONDS=0` 关闭服务端 WebSocket ping。

后台初始账号密码来自 `.env`，首次部署前请修改 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`。

## 多管理员账号与操作记录

支持多个独立后台账号同时登录、协作管理群。首次部署时，`.env` 的 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 创建初始**超级管理员**；已有版本升级时保留原账号、密码和 TOTP 绑定，旧账号迁移为超级管理员。启动不会覆盖已存在账号的密码、权限或启用状态。

- **超级管理员**：拥有日常群管理权限，并可在“管理员管理”中新建账号、修改姓名与权限、停用/恢复账号、重置密码和双因素认证。
- **普通管理员**：可使用群管理、内容管理、后台任务及操作日志，不能查看或管理后台账号；后端也会拒绝直接调用账号管理接口。
- 每人使用自己的登录账号；登录名创建后固定，姓名/备注名可修改。账号通过停用保留历史记录，不提供删除账号或删除操作日志的接口。不能停用或降级当前登录的超级管理员，系统至少保留一个启用的超级管理员。

新账号的密码为 8–128 位。每个管理员可在“账号安全”修改自己的密码、独立绑定 TOTP 验证器。停用/恢复账号、修改权限、重置或修改密码、重置/启用/关闭双因素认证后，旧 Token 失效，已连接的后台 WebSocket 会断开。退出登录也会使该账号的所有已有登录失效；其他账号不受影响。已提交的后台任务继续执行，并保留原提交人的记录。多标签页切换账号时重新加载，避免混用旧账号的页面缓存。

“事件日志 → 操作日志”展示管理员账号、姓名、动作、目标、结果、来源 IP、渠道与时间，可按管理员 ID、结果、日期筛选，或搜索账号、姓名、动作、IP 和请求编号。详情保留请求编号、浏览器信息、耗时、脱敏参数；群配置和账号修改等写操作还保留修改前后的值。审计记录中的账号/姓名是操作发生时的快照，后来修改姓名不会改写历史记录。

日志包含登录成功/失败及限速、退出、修改密码、双因素认证操作、上传、后台 HTTP 请求（含验证失败）、WebSocket 连接/断开、业务查询和写入的成功/失败，以及后台任务排队、完成/失败和重启中断。业务记录与 `http.*` / `rpc.*` 请求记录分别保留，后者通过请求编号与业务记录关联。心跳和正常订阅维护不逐条落日志，读取日志也不会触发循环刷新。历史日志保留，能够关联到旧管理员的记录会补全账号名；旧记录缺少操作结果时标为“历史记录”，不推断为成功，缺少的 IP、请求编号等字段保持为空。

密码、JWT、TOTP 密钥/验证码、云密钥、API Key 和含认证信息的代理地址会递归脱敏，不保存在操作详情中。来源 IP 默认使用直连地址；只有明确启用已有的 `LOGIN_RATE_LIMIT_TRUST_PROXY_HEADERS=true` 时才使用代理头，需由可信反向代理正确覆盖这些头。升级时重新构建前端并重启后端，SQLite 会自动补充账号和日志字段及索引。

登录后台后进入“账号安全”可启用双因素认证。页面显示的二维码可用 Google Authenticator、Microsoft Authenticator 等 TOTP 验证器扫描，输入验证器生成的 6 位验证码确认绑定；之后登录需同时填写密码和动态验证码。更换设备前请先在新设备绑定验证器。

## 批量撤回消息

在后台“批量撤回”页面添加管理员 QQ 号，启用后该 QQ 可在机器人所在群发送：

```text
/大记忆清除术
/大记忆清除术 1000
```

省略条数默认 500；可指定 1–20000 的整数。命令只处理**当前群、当前机器人**在命令到达前缓存的最近消息，从新到旧取指定条数。QQ 撤回管理员配置对机器人所在的所有群生效，与后台登录账号独立；群主、群管理员也需要添加 QQ 授权。同一群已有任务时拒绝重复启动，命令重复上报也不会再次执行。任务在后台运行，完成后在群内回复成功数、失败并跳过数和耗时，并在后台操作日志记录操作者 QQ 和统计。

缓存库默认是 `data/message_cache.db`，独立于管理数据库，启用 WAL；**所有群、所有连接的机器人合计保留最近 20000 条收到的群消息记录**，超过容量自动淘汰最旧记录。只保存消息 ID、群号、机器人账号、发送者、时间和撤回状态，不保存正文、图片或文件；启动后开始缓存，不补抓启动前的历史。已成功撤回的消息和撤回命令不再作为目标，收到群撤回通知也会同步状态。缓存不足时处理现有记录并在结果中说明；失败记录保留，在被缓存淘汰前可再次尝试。

撤回默认使用 32 路持续并发，所有群共享并发上限。单条消息过期、权限不足、已经撤回或接口异常都只跳过该条；单条请求超过默认 5 秒后跳过，其他执行单元继续领取下一条，不会因一个失败或慢请求中断整批。机器人需要具备 QQ 允许的撤回权限，实际吞吐取决于 OneBot/QQ 接口响应和限流；提高并发可能增加接口失败。

可在 `.env` 调整后重启服务：

```text
MESSAGE_CACHE_PATH=./data/message_cache.db
MESSAGE_RECALL_CONCURRENCY=32
MESSAGE_RECALL_TIMEOUT_SECONDS=5
```

缓存路径必须与管理数据库不同；并发可设为 1–128，单条超时可设为大于 0、至多 60 秒。服务停止会取消尚未完成的撤回，不会在重启后自动重放命令。

## 腾讯云文本审核

消息审查规则默认仍是正则命中后直接执行动作。若在规则里开启“AI二次审核”，则正则命中后会调用腾讯云 TMS `TextModeration`，只有返回 `Block` 或 `Review` 时才撤回/禁言，返回 `Pass` 时不处理。腾讯云 `SecretId`、`SecretKey`、地域和策略编号可在后台“消息审查”页配置，`SecretKey` 保存后不会回显明文。

## QQ 等级与答错自动拉黑

在“群配置”中设置最低 QQ 等级、答错拉黑次数和统计窗口（默认 24 小时）。最低等级和拉黑次数默认均为 0，表示关闭；例如设置最低 16 级、24 小时内答错 3 次拉黑。

等级从申请人的 `get_stranger_info` 获取，兼容 `qq_level`、`qqLevel`、`level` 字段，不使用群成员等级。开启等级限制但获取失败时拒绝本次申请并提示重试。只有答案验证失败计入答错次数，等级不足、等级获取失败、分流和服务异常不计数。按“群 + QQ”统计窗口内答错次数，通过验证或管理员停用黑名单后重新计数。同一申请 flag 重复上报不会重复计数。

达到上限时加入现有全局加群黑名单，之后所有受管理群的加群申请均被拒绝。自动备注包含来源群、QQ、统计窗口、错误次数、阈值、最后一次错误答案及 UTC+8 时间；已有备注会保留。黑名单可在后台停用或删除。申请决策先保存，再调用 OneBot；执行状态和错误另行记录，避免网络重试反复累计。未启用或未管理的群不自动处理申请。

## 进群后图片验证码

在后台“群配置”新增或编辑群，开启“入群图片验证码”。默认关闭；只有启用且开启此开关的受管理群处理新入群成员，已有成员不补验证。机器人需要群管理员权限，LLBot/LLOneBot 需要上报成员增加、成员减少和群消息事件。

新人实际进群后，机器人会 **@ 新人、发送欢迎语和验证码图片**。使用 [`captcha`](https://github.com/lepture/captcha) 库在本地生成带干扰效果的 5 位字母数字 PNG，随机字符避开 `0/O/1/I/L`，不需要外部验证码服务或公开验证网页。新人直接在群内发送图片中的验证码，支持大小写、全角字符和空格归一化；仅处理该群该新人的回答，其他成员的发言不参与验证。验证前的每条非空文字消息均作为一次回答，图片、文件等没有文字的消息不算答错。

| 作答结果 | 处理 |
| --- | --- |
| 正确 | @ 提示验证通过，结束本次验证 |
| 第 1 次错误 | 禁言 10 秒，解禁后继续作答 |
| 第 2 次错误 | 禁言 20 秒，解禁后继续作答 |
| 第 3 次错误 | 禁言 30 秒，解禁后继续作答 |
| 第 4 次错误 | 直接踢出本群，不加入全局加群黑名单 |

每张图有效期 10 分钟。看不清可发送 `/验证码` 换图；过期后下一条消息会触发换图，不将过期答案计错。换图保留错误次数，冷却期间的消息不会计错或提前通过，也不能通过换图跳过冷却。不额外设置超时自动踢人。

验证状态、错误次数、冷却时间和消息去重记录保存在管理数据库，服务重启后继续生效。重复入群通知不会重复发图或重置次数，重复消息不会重复处罚。退群会结束验证，再次入群重新生成；机器人自己入群不触发验证。未验证成员的消息仍缓存消息 ID，但不会执行批量撤回命令；验证码文字回答不再匹配消息审查规则，带图消息继续按已有规则审核。

发图失败后，下一条消息会重新发图，不记答错。禁言失败仍保留对应冷却，群内提示管理员检查权限；踢人失败保留待踢状态，下一条新消息重试，不能再用正确答案绕过第 4 次错误。接口失败不会发送处理成功的提示。验证码发放、通过、答错及处罚执行结果写入 `verification.*` 操作日志，不记录验证码明文。启动时自动添加配置字段及验证表，升级需运行 `uv sync`、重新构建前端并重启后端。

## LLM 多模态图片审核

在“消息审查 → LLM 图片审核配置”中启用服务，添加渠道并填写各自的 API Base URL、API Key 和支持图片输入的模型名。最多配置 8 个渠道，按列表顺序使用，可上移、下移或停用。Base URL 可填 `https://api.openai.com/v1` 或兼容服务商的地址，也支持完整 `/chat/completions` 地址。API Key 不回显，留空保留已有值，调整顺序时按渠道 ID 保留正确密钥，也可主动清除；本地无鉴权服务允许留空。

每个渠道可单独填写“代理地址（可选）”，支持 `http://127.0.0.1:7890`、`https://proxy.example:8443` 和 `socks5://127.0.0.1:1080`，也支持 `http://用户名:密码@主机:端口` 等带认证的地址（账号密码中的特殊字符需 URL 编码）。代理地址不能含路径、查询参数或片段。HTTPS API 通常也使用 `http://` 代理地址，请按代理服务支持的协议填写。代理仅用于该渠道的审核 API 请求，包括 Chat Completions、Moderations 和重试；切换渠道时使用下一渠道自己的代理。保存后代理地址不回显，留空保留已有值，按渠道 ID 保留，可重新填写替换或勾选“清除已保存的代理地址”。未配置或清除渠道代理时沿用服务器的 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 和 `NO_PROXY` 环境设置；没有环境代理时直连。代理运行在后端服务器上，`127.0.0.1` 指后端所在机器。SOCKS5 所需依赖已包含在项目依赖中，更新后运行 `uv sync` 安装。

新增或编辑消息规则，开启“LLM 多模态图片审核”，选择作用群以及撤回、禁言或两者。图片审核无需正则命中，规则的表达式可留空，也不依赖 OCR 或腾讯云。群专属规则优先于全局规则，同一消息最多执行一次动作；一条消息有多张图片时逐张检查，遇到可靠的违规结论后执行动作。

图片审核成功执行撤回或禁言后，会引用回复原消息，说明模型原因、百分比和实际执行的动作，例如：

```text
警告：
因模型检测到：图片含有明确的违规内容
置信度：96.0%
已撤回并禁言 10分钟
```

仅撤回时显示“已撤回”，仅禁言时显示“已禁言”及配置的时长；两项动作只有一项成功时，也只显示成功的动作。两项均失败时不发送成功警告。回复失败会打印含群、用户、消息 ID 的日志，已完成的动作不会重复执行。审核原因使用纯文本消息段发送。

支持 `omni-moderation-latest` 和 `omni-moderation-*` 快照。渠道模型名填写该模型即可自动使用 `/moderations`，Base URL 可以填 `https://api.openai.com/v1` 或完整 `/moderations` 地址；原来填写的完整 `/chat/completions` 地址会替换为同一前缀下的 `/moderations`。仅发送模型名、图片和附带文字（最多 2000 字符），不发送提示词、ToolCall、思考预算、图片精细度或扩展参数，后台也会隐藏这些不适用的渠道设置。按官方内置分类审核，`flagged=true` 且**命中分类的最高 `category_scores` 分数**达到动作阈值才撤回/禁言；日志显示命中分类、分数及是否触发动作。未标记违规时即使分数达到阈值也不处理。它可与普通多模态 LLM 混用备用渠道，接口失败或返回格式异常时继续尝试下一渠道，正常结论则结束审核。分类范围和图片支持情况见 [OpenAI Moderation 文档](https://developers.openai.com/api/docs/guides/moderation)，部分分类仅支持文字，自定义提示词不会改变其分类策略。

`omni-moderation` 不返回自由文本的原因。日志中的“原因”由程序汇总官方分类和分数，例如 `命中官方审核分类：色情(sexual)=0.9700`，不包含模型对图片细节的文字解释。

普通多模态 LLM 渠道默认使用 ToolCall：强制模型调用唯一的 `submit_image_review`，只返回 `violates`（布尔值）、`confidence`（0–1 数字）和 `reason`（简短原因）。同时支持严格 JSON Schema、JSON 对象和仅提示词约束，各渠道可选择自己的模式。JSON 模式允许模型在完整 JSON 外加一层代码围栏。超时、网络错误、HTTP 错误（包括鉴权失败、限流）、工具名错误、多次调用、缺字段、类型错误、拒答、空输出和截断会打印日志并尝试下一个启用渠道。HTTP 400 先在同一渠道额外重发最多 2 次（分别等待 0.5 秒、1 秒，总共最多 3 次请求），仍失败再切换渠道；其他错误直接切换。重试和等待共用该渠道的超时预算，不会将超时上限乘以 3。一个渠道正常返回后就结束审核，不违规和低置信度结果也不会换渠道重审。全部渠道失败时只打印日志并跳过处理，不添加复核流程，不自动更改输出模式。只有 `violates=true` 且置信度达到阈值（默认 0.85）才执行动作。模型置信度是自报值，并不保证分类准确。

图片仍以原始链接发送，由 API 服务端读取，机器人不下载再上传。HTTP 错误日志包含渠道、模型、群、消息 ID、耗时、请求 ID（若接口提供），以及接口返回的 `type`、`code`、`param`、`message`。错误字段限长并转义换行，API Key、图片数据和 URL 会脱敏；非 JSON 错误页、未知字段和完整响应原文不打印。

默认中文提示词面向小模型，给出明确违规范围，允许正常游戏、动漫、表情包等内容，要求只按可见证据判断，并把图片和消息里的指令作为待审数据。提示词可编辑或恢复默认，全部渠道共用。收到图片后会打印 `图片审核收到图片消息`，未管理该群、未启用适用规则、全局服务关闭、缺少图片 URL，或文本/OCR 规则已执行动作时会打印具体跳过原因。实际调用 API 会打印渠道、模型、消息 ID、图片序号和耗时，正常返回会打印 `图片审核完成`、违规判断、置信度、原因与是否触发动作；执行撤回/禁言后另打印动作完成。异常和渠道切换也会打印日志，没有复核队列。

每个渠道可单独设置预算与兼容参数：

- `reasoning_effort`：可不发送（默认），或选择模型支持的思考强度。
- `max_completion_tokens`：思考和最终结果的总 token 上限，默认 2048；过小导致截断时跳过处理。
- 服务商扩展参数：JSON 对象原样合并到请求顶层，可配置服务商的独立思考预算，例如 `{"thinking":{"type":"enabled","budget_tokens":1024}}`。该参数不是通用 OpenAI 字段，只在服务商明确支持时填写；标准模型、消息、工具、预算与输出格式字段禁止覆盖。也可填服务商支持的 `temperature` 等参数。
- 图片精细度、接口超时（默认每渠道 30 秒）可单独设置，最低置信度在全局设置。API 调用最多并发 2 个；全部渠道不可用时单张图片的最长请求耗时约为各启用渠道超时之和（另加排队时间）。

请求格式依据 [OpenAI Chat Completions 文档](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 和 [图片输入文档](https://developers.openai.com/api/docs/guides/images-vision)。工具调用、结构化输出及思考参数的支持范围依模型与兼容服务商而异。

## 自定义后台入口

后台入口由前端构建环境变量控制，后端 `.env` 中的同名配置只在启用本地静态托管时使用：

```text
ADMIN_ROUTE_PREFIX=/manage-a8f3c2
```

前端构建时也要使用相同值：

```text
VITE_ADMIN_ROUTE_PREFIX=/manage-a8f3c2
```

设置后后台页面入口为：

```text
https://你的CDN域名/#/manage-a8f3c2
```

默认的 `/admin`、`/login` 不会单独作为后端静态页面暴露，因为默认 `FRONTEND_STATIC_ENABLED=false`。注意这只是隐藏后台页面入口，后台 API 仍依靠 JWT 鉴权；公网部署建议同时在反代层限制 `/api/admin/*` 和 `/api/auth/*`。

如果配置为 `/manage-a8f3c2`：

- 登录页：`https://你的CDN域名/#/manage-a8f3c2/login`
- 仪表盘：`https://你的CDN域名/#/manage-a8f3c2`
- 群配置：`https://你的CDN域名/#/manage-a8f3c2/groups`

## 前端启动

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

本地开发时建议把 `frontend/.env.local` 改成：

```text
VITE_API_BASE_URL=/api
VITE_ADMIN_ROUTE_PREFIX=/manage-a8f3c2
```

前端开发地址默认为 `http://127.0.0.1:5173`。Vite 将 `/api` 的 HTTP 和 WebSocket 请求代理到 `127.0.0.1:8080`。

## CDN 构建

```powershell
Set-Location frontend
npm run build
```

把 `frontend/dist` 上传到 CDN 或静态站点服务。前端使用 hash 路由，所以 CDN 只需要能访问根 `index.html`，不需要配置 history fallback。

生产环境 `.env.production` 示例：

```text
VITE_API_BASE_URL=https://bot.example.com/api
VITE_ADMIN_ROUTE_PREFIX=/manage-a8f3c2
VITE_APP_NAME=我的群助手
VITE_APP_ICON_URL=https://example.com/icon.png
VITE_ALIYUN_CAPTCHA_REGION=cn
VITE_ALIYUN_CAPTCHA_PREFIX=esa-xxxxxx
VITE_ALIYUN_CAPTCHA_SCENE_ID=your-scene-id
```

`VITE_APP_NAME` 自定义网站名称，默认 `Auto Group`；会同时用于浏览器标签页、登录页和后台品牌名，例如 `公开入口 - 我的群助手`。`VITE_APP_ICON_URL` 填可直接返回图片的 HTTP/HTTPS 链接，支持 PNG、ICO、SVG、JPEG、GIF、WebP 和 AVIF。运行 `npm run build` 时自动下载图片，作为带内容哈希的 favicon 写入 `dist/assets` 并更新 HTML；部署后浏览器从本站加载，不再请求原始图标链接。留空不设置自定义 favicon。下载超时（15 秒）、HTTP 错误、不支持的响应类型、空文件或超过 2 MiB 会使构建失败，并提示原因。

也可以在构建命令前传入环境变量（PowerShell）：

```powershell
Set-Location frontend
$env:VITE_APP_NAME = '我的群助手'
$env:VITE_APP_ICON_URL = 'https://example.com/icon.png'
npm run build
```

修改名称或图标地址后需重新构建并发布 `dist`。本地 `npm run dev` 也支持这两个参数，图标由开发服务器下载后提供；后端 `.env` 不控制前端品牌配置。

启用阿里云 ESA 验证码后，ESA 里的“需验证的接口”填后台登录接口：

```text
POST https://bot.example.com/api/auth/login
```

前端会动态加载阿里云验证码 JS，验证码通过后把 `captchaVerifyParam` 放到 `captcha-verify-param` 请求头发给登录接口。

后端 `.env` 示例：

```text
FRONTEND_STATIC_ENABLED=false
CORS_ORIGINS=https://cdn.example.com
ADMIN_ROUTE_PREFIX=/manage-a8f3c2
LOGIN_RATE_LIMIT_MAX_FAILURES=5
LOGIN_RATE_LIMIT_WINDOW_SECONDS=900
LOGIN_RATE_LIMIT_LOCK_SECONDS=900
```

后端登录接口默认启用失败限速：同一账号或同一客户端 IP 在窗口期内失败次数达到阈值后，会返回 `429` 并暂时拒绝继续尝试。公网部署时还应在防火墙或反代层限制源站只接受 ESA/CDN 回源，避免攻击者绕过边缘验证码直接打源站。

如果你临时想让后端直接托管 `frontend/dist`，设置 `FRONTEND_STATIC_ENABLED=true` 后重新启动后端即可。

## MD3 后台与管理 WebSocket

后台使用 Vuetify 4.2.4 的官方 MD3 蓝图，统一使用 `#6750A4` 种子色生成色彩角色，支持浅色、深色及跟随系统。主题选择保存在浏览器本地；页面标签保留查询状态，只挂载当前页面。路由和图表按需加载，日志只读取当前标签，文件只读取当前群的当前目录。

管理查询、增删改和任务通过 `/api/admin/ws` 通信。HTTP 保留 `/api/auth/login`、`/api/admin/uploads` 与 `/api/public/recommended-group`；OneBot 的 `/onebot/v11/ws` 不变。**旧 HTTP 管理接口已替换，升级时需同时发布后端和新的前端构建。** 数据库启动时自动新增任务表及分页索引，保留现有业务数据。

生产构建会把 `VITE_API_BASE_URL=https://bot.example.com/api` 推导为 `wss://bot.example.com/api/admin/ws`。若 WS 使用独立域名或路径，可设置完整地址：

```text
VITE_WS_BASE_URL=wss://socket.example.com/api/admin/ws
```

浏览器的 Origin 必须匹配后端 `CORS_ORIGINS`（包括协议和端口）；CDN 域名应列在其中。HTTPS 页面应使用 WSS。运行一个 NoneBot 进程即可，任务执行与订阅广播共享该进程，无需 Redis。

Nginx HTTPS 虚拟主机内的转发示例：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
    proxy_buffering off;
}
```

上游 CDN/网关也需开启 WebSocket 转发并保留 Origin。浏览器每 20 秒发送应用心跳。Upgrade 转发和空闲超时说明见 [Nginx 官方文档](https://nginx.org/en/docs/http/websocket.html)。CDN 可长期缓存带哈希的 `assets/*`，`index.html` 应使用短缓存或重新验证，便于同步更新前后端。

同步、公告、精华、文件操作与去重会先返回持久化任务编号。离开页面后任务继续执行，可在“后台任务”查看进度、逐群结果和分页操作明细。服务重启后，未完成任务标记为中断，需要核实外部操作结果后再次提交；发送、踢人等操作不会自动重放。去重仍须先生成完整预览，再明确确认执行。

完整方法、分页、订阅和任务恢复约定见 [管理 WS 协议](docs/admin-ws.md)。

## 验证

```powershell
uv run ruff check app tests scripts
uv run pytest -q
Set-Location frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

浏览器测试使用单独的生产构建、临时数据库与模拟 OneBot，自动启动 `8080` 与 `5173` 两个测试服务，需保证这两个端口空闲。测试数据包含 1 万条日志；后端测试另覆盖 1 万条去重明细、提交后通知、任务重复提交与重启中断。视觉截图保存在 `frontend/test-results/`。

资源字段变更后，重新生成 TypeScript 契约：

```powershell
uv run python scripts/generate_rpc_types.py
Set-Location frontend
npx prettier --write src/api/generated.ts
```
