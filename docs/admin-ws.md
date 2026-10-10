# 管理 WebSocket 协议 v1

端点：`/api/admin/ws`。管理查询与操作只通过此端点；登录、验证码、上传、公开入群查询和 OneBot 通信沿用 HTTP 或原有接口。前后端需配套升级。

## 连接与认证

每个已登录浏览器页面建立一条连接，使用 HTTPS 时连接 WSS。服务端检查 Origin，允许配置在 `CORS_ORIGINS` 中的来源及同源请求（`*` 保留现有开发配置语义）；缺少 Origin 会被拒绝。

连接后 5 秒内的第一个请求必须认证，JWT 不放在 URL 中：

```json
{"v":1,"id":"auth-1","method":"auth.authenticate","params":{"token":"<JWT>"}}
```

认证成功响应包含 `admin_id` 与 `expires_at`。认证失败或 JWT 到期关闭码为 `4001`；非法来源为 `1008`。客户端收到登录失效后关闭连接、清空缓存与页面状态并返回登录页。队列拥塞关闭码为 `1013`，客户端通过重新查询恢复。

## 消息格式

请求：

```json
{"v":1,"id":"request-uuid","method":"groups.list","params":{"page":1,"page_size":25,"q":"测试"}}
```

成功响应和失败响应都使用同一个请求 ID，并可乱序返回：

```json
{"v":1,"type":"response","id":"request-uuid","result":{"items":[],"total":0,"page":1,"page_size":25}}
```

```json
{"v":1,"type":"response","id":"request-uuid","error":{"code":"VALIDATION_ERROR","message":"请求参数不正确","details":[]}}
```

错误码包括 `AUTH_REQUIRED`、`FORBIDDEN`、`NOT_FOUND`、`CONFLICT`、`VALIDATION_ERROR`、`BOT_UNAVAILABLE`、`INTERNAL_ERROR`。每个连接最多同时处理 8 个请求，发送队列最多 64 条；前端将读取请求限制为并发 2 个。客户端默认请求超时 30 秒，心跳每 20 秒一次；连接失败在 1～30 秒内指数退避并加入抖动。

所有管理方法有 Pydantic 输入及输出模型。资源列表与详情 DTO 位于 `app/schemas/resources.py`，方法注册表位于 `app/api/websocket.py`；`frontend/src/api/generated.ts` 从资源模型生成，其他方法类型位于 `frontend/src/api/types.ts`。

## 分页与资源

列表统一返回 `PageResult<T> = { items, total, page, page_size }`，页码从 1 开始，默认 25 条、最大 100 条，超出范围返回校验错误。空页仍返回真实总数和空的 `items`。

列表参数：`page`、`page_size`、`q`、`group_id`、`enabled`、`status`、`job_id`、`start_date`、`end_date`。适用筛选在后端执行；日期起点包含、终点不包含。群按优先级降序、唯一群号升序；带创建时间的列表按时间降序及唯一 ID 降序，其他列表按 ID 降序。

列表不包含 `raw_event`、`raw_data`、`detail` 或任务参数。长文本截取到 180 字符，规则列表只展示前 3 个匹配项；详情方法返回完整内容。任务摘要不携带保护成员与错误详情数组，这些通过分页明细查询。

| 方法 | 参数与返回 |
| --- | --- |
| `<resource>.list` | 分页输入 → `PageResult` |
| `<resource>.get` | `{id}` → 完整详情；`jobs.get` 专门返回任务摘要 |
| `<resource>.create` | `{data}` → 新记录详情 |
| `<resource>.update` | `{id,data}` → 更新后详情 |
| `<resource>.delete` | `{id}` → `{ok:true}` |
| `groups.options` | 分页/搜索/指定群 → 只含 `id,group_id,name,enabled` 的分页选项 |
| `groups.move` | `{group_id,position}` → `{ok:true}`，位置为完整排序中的 1 起始位置 |
| `dashboard.summary` | `{}` → 基础数量与今日摘要 |
| `dashboard.trends` | `{}` → 7 天趋势 `items` |
| `dashboard.breakdown` | `{}` → 申请结果分布 `items` |
| `dashboard.rankings` | `{}` → 群人数、活跃群及活跃成员排行 |
| `dashboard.recent` | `{}` → 最近退群和操作记录 |
| `cloud.get / cloud.update` | `{}` / 腾讯云配置 → 脱敏配置；SecretKey 不回显 |
| `image-review.get / image-review.update` | `{}` / `{enabled,system_prompt,min_confidence,channels}` → 脱敏配置；按渠道 ID 保留密钥，API Key 不回显，空值保留，渠道的 `clear_api_key=true` 清除 |
| `files.browse` | `{group_id,folder_id?,page?,page_size?,q?}` → 目录分页 |
| `files.url` | `{group_id,file_id,busid}` → `{url}` |
| `jobs.findByRequestId` | `{request_id}` → 当前管理员的 `JobRef` 或 `null` |
| `jobs.actions` | `{job_id,...分页参数}`，这里是管理任务 ID → 对应去重动作分页 |

资源名称为 `groups`、`rules`、`blacklist`、`moderation`、`whitelist`、`recall-admins`、`notices`、`essence`、`files`、`joins`、`leaves`、`audits`、`actions`、`jobs`、`job-items`。直接 CRUD 适用于 `groups`、`rules`、`blacklist`、`moderation`、`whitelist`、`recall-admins`；其余业务操作通过后台任务。`actions.list` 的 `job_id` 是原始去重任务编号，`job-items.list` 的 `job_id` 是管理任务编号。

`recall-admins.create` 的 `data` 为 `{user_id,enabled?,note?}`；QQ 必须是正整数且唯一，默认启用。`recall-admins.update` 仅允许修改 `enabled`、`note`，删除或停用立即影响后续命令的授权检查，已有任务继续完成。记录配置位于管理数据库，收到的消息 ID 缓存在独立的 `MESSAGE_CACHE_PATH` SQLite 数据库。实际撤回由群内 `/大记忆清除术 [条数]` 启动，完成后写入 `messages.bulk-recall` 操作日志；这些群命令不使用管理 WS 的持久化任务编号。

群移动在一个数据库事务中重排优先级；界面保留直接编辑优先级和跨页指定位置。仪表盘重型聚合缓存 15 秒，消息事件不会逐条触发重算。文件目录缓存 30 秒且分页返回，修改后失效；只读取当前层，不递归预取。

## 订阅与变更通知

```json
{"v":1,"id":"subscribe-1","method":"subscribe","params":{"topics":["groups","files:1001","jobs:8"]}}
```

`unsubscribe` 使用相同参数；每个连接最多 64 个主题，响应为 `{ok:true}`。`ping` 返回 `{pong:true}`。资源主题与资源名称一致，另支持 `activity`、`dedupe`、`cloud`、`image-review`、五个 `dashboard.*` 分区；`<resource>:<group_id>` 限定群，`jobs:<job_id>` 限定任务。

```json
{"v":1,"type":"event","topic":"files:1001","payload":{"group_id":1001}}
```

推送只包含变更标识与范围，在数据库提交成功后发布，回滚不发送。通知按主题每秒合并，前端只刷新相关活动查询。浏览器隐藏、区块离开可视区域、离开页面或关闭弹窗会取消相应订阅并取消等待中的查询；恢复可见或重连后恢复当前订阅并同步当前数据。查询有效期 30 秒、闲置回收 5 分钟，不在切换焦点时自动请求。

## 持久化后台任务

以下方法立即返回 `JobRef = {id,kind,status}`，外部操作由最多 2 个后台执行单元执行：

| 方法 | 主要参数 |
| --- | --- |
| `groups.sync / notices.sync / essence.sync / files.sync` | `group_id` 或 `selection` |
| `notices.send / essence.create` | `selection,content` |
| `notices.delete` | `group_id,notice_id` |
| `essence.delete` | `group_id,message_id` |
| `files.distribute` | `selection,file_path,name?,folder_id?`，文件须来自上传端点 |
| `files.delete` | `group_id,file_id,busid` |
| `files.rename` | `group_id,file_id,new_name,current_parent_directory?` |
| `files.rename-folder` | `group_id,folder_id,new_name` |
| `dedupe.preview` | `{}`，同步启用群并生成保护后的预览 |
| `dedupe.execute` | `{job_id}`，编号为完整成功的管理预览任务 |

目标选择 `selection` 使用 `{mode:"ids",ids:[1001],q:"",excluded_ids:[]}` 或 `{mode:"all_matching",ids:[],q:"关键词",enabled:true,excluded_ids:[1002]}`。提交时由后端解析并保存目标群，随后新建的群不会加入已提交任务。

`jobs.get` 返回 `{id,kind,status,summary,dedupe_job_id}`。`summary` 含总数、已完成数、失败数、当前阶段等；逐群结果通过 `job-items.list` 查询，完整错误或保护详情通过 `job-items.get` 查询，去重执行动作通过 `jobs.actions` 查询。状态为 `pending`、`running`、`preview`、`success`、`failed`、`interrupted`。单群失败不会阻止其他群继续，任务最终失败并保留各项结果。

任务提交以“管理员 ID + 请求 ID”唯一去重，相同 ID 不重复创建任务。提交响应丢失时客户端保留请求 ID，通过 `jobs.findByRequestId` 查询已提交任务，普通写请求不自动重放。请求超时不代表外部操作没有完成。

去重执行只接受完整成功且未执行过的预览，预览过程中任一群同步失败会禁止执行。前端明确确认后才提交执行，执行时逐项再次检查手动白名单及已同步的管理员角色。重启将未完成任务标记为中断，不自动重放发送、上传或踢人；应核实结果再手动提交新任务。

数据库查询、写入与去重计算通过受限工作线程执行，每个执行单元使用独立 Session。等待 OneBot 时不持有数据库事务；变更通知使用当前单进程内的事件循环广播。
