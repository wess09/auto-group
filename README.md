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
- 公开分流页：`/join` 自动展示当前推荐入群链接。

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

LLBot/LLOneBot 反向 WS 地址配置为：

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

默认后台账号密码来自 `.env`：

```text
admin / admin123
```

## 前端启动

```powershell
Set-Location frontend
npm install
npm run dev
```

前端开发地址默认为 `http://127.0.0.1:5173`，会代理 `/api` 到后端。

## 构建

```powershell
Set-Location frontend
npm run build
Set-Location ..
uv run auto-group
```

构建后可直接通过后端访问 `/admin` 和 `/join`。
