# Auto Group

NoneBot2 + LLBot/LLOneBot 群管理与群运营后台。

## 功能

- 自动处理加群请求：可视化答案规则，支持包含、完全匹配、正则、AND/OR。
- 入群风控：QQ 账号等级限制、答错次数达到阈值自动加入加群黑名单，自动填写完整备注。
- 自动群分流：按群优先级和容量推荐群，申请非推荐群时拒绝并提示推荐群。
- 退群监听：记录退群 QQ、群、类型和操作者。
- 一键去重：先预览，确认后保留最高优先级群，踢出低优先级重复成员。
- 公告管理：同步公告、批量发送、删除公告。
- 群文件管理：上传一份文件，选择多个群批量分发，同步/删除群文件。
- 精华管理：发送指定内容后自动设精，支持同步和移出精华。
- 消息审查：正则命中后自动处理，可按规则开启腾讯云文本内容安全二次审核。
- 多模态图片审核：兼容 OpenAI Chat Completions，支持 ToolCall、JSON Schema、自定义提示词和思考预算。
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

后台账号密码来自 `.env`，首次部署前请修改 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`。

## 腾讯云文本审核

消息审查规则默认仍是正则命中后直接执行动作。若在规则里开启“AI二次审核”，则正则命中后会调用腾讯云 TMS `TextModeration`，只有返回 `Block` 或 `Review` 时才撤回/禁言，返回 `Pass` 时不处理。腾讯云 `SecretId`、`SecretKey`、地域和策略编号可在后台“消息审查”页配置，`SecretKey` 保存后不会回显明文。

## QQ 等级与答错自动拉黑

在“群配置”中设置最低 QQ 等级、答错拉黑次数和统计窗口（默认 24 小时）。最低等级和拉黑次数默认均为 0，表示关闭；例如设置最低 16 级、24 小时内答错 3 次拉黑。

等级从申请人的 `get_stranger_info` 获取，兼容 `qq_level`、`qqLevel`、`level` 字段，不使用群成员等级。开启等级限制但获取失败时拒绝本次申请并提示重试。只有答案验证失败计入答错次数，等级不足、等级获取失败、分流和服务异常不计数。按“群 + QQ”统计窗口内答错次数，通过验证或管理员停用黑名单后重新计数。同一申请 flag 重复上报不会重复计数。

达到上限时加入现有全局加群黑名单，之后所有受管理群的加群申请均被拒绝。自动备注包含来源群、QQ、统计窗口、错误次数、阈值、最后一次错误答案及 UTC+8 时间；已有备注会保留。黑名单可在后台停用或删除。申请决策先保存，再调用 OneBot；执行状态和错误另行记录，避免网络重试反复累计。未启用或未管理的群不自动处理申请。

## LLM 多模态图片审核

在“消息审查 → LLM 图片审核配置”中启用服务，添加渠道并填写各自的 API Base URL、API Key 和支持图片输入的模型名。最多配置 8 个渠道，按列表顺序使用，可上移、下移或停用。Base URL 可填 `https://api.openai.com/v1` 或兼容服务商的地址，也支持完整 `/chat/completions` 地址。API Key 不回显，留空保留已有值，调整顺序时按渠道 ID 保留正确密钥，也可主动清除；本地无鉴权服务允许留空。

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
VITE_ALIYUN_CAPTCHA_REGION=cn
VITE_ALIYUN_CAPTCHA_PREFIX=esa-xxxxxx
VITE_ALIYUN_CAPTCHA_SCENE_ID=your-scene-id
```

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
