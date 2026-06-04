# Auto Group

NoneBot2 + LLBot/LLOneBot 群管理与群运营后台。

## 功能

- 自动处理加群请求：可视化答案规则，支持包含、完全匹配、正则、AND/OR。
- 自动群分流：按群优先级和容量推荐群，申请非推荐群时拒绝并提示推荐群。
- 退群监听：记录退群 QQ、群、类型和操作者。
- 一键去重：先预览，确认后保留最高优先级群，踢出低优先级重复成员。
- 公告管理：同步公告、批量发送、删除公告。
- 群文件管理：上传一份文件，选择多个群批量分发，同步/删除群文件。
- 精华管理：发送指定内容后自动设精，支持同步和移出精华。
- 消息审查：正则命中后自动处理，可按规则开启腾讯云文本内容安全二次审核。
- 公开分流页：`#/join` 自动展示当前推荐入群链接。

## 环境

- Python 3.10+
- uv
- Node.js 20+
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
VITE_API_BASE_URL=http://127.0.0.1:8080/api
VITE_ADMIN_ROUTE_PREFIX=/manage-a8f3c2
```

前端开发地址默认为 `http://127.0.0.1:5173`。

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
