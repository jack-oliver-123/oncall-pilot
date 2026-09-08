# On-call Pilot 后端

此 workspace 提供 `oncall_pilot` src-layout package、FastAPI app factory、主机 CLI、`/health`、通用 JSON 配置加载、SQLite 持久化边界、Alembic async 迁移及用户认证。Agent 和 MCP 能力尚未开放。

持久化调用约定见 [持久化指南](persistence.md)，迁移命令见 [迁移指南](migrations/README.md)。

## 安装与启动

```powershell
uv sync
uv run alembic -c alembic.ini -x config-dir=../../config upgrade head
uv run python -m oncall_pilot --config-dir ../../config --host 127.0.0.1 --port 8000
```

## 验证

```powershell
uv run ruff check .
uv run pyright
uv run pytest
```

后端 module import 不读取配置或连接外部依赖；应用只在 app factory 被调用时读取显式配置目录。

HTTP 响应使用 contracts 生成的 envelope；`/health` 返回成功 envelope，其 data 为 `{status:"ok"}`。`protocol.py` 提供 success、api_error、failure、ApiException、统一异常 handler 和 SSE serializer。有效 X-Request-ID 原样透传，其余生成 UUID，响应头与 meta 一致；验证失败只公开字段 path/type 和安全消息，不公开原始 input/ctx。

增加 endpoint 前先修改 `packages/api-contracts` 中的 OpenAPI 合同并运行根 `npm run contracts:generate`。后端合同测试比较所有生成模型的结构、实际 OpenAPI path/response/headers，未登记路径会失败。SSE 必须使用生成的事件模型，serializer 不接受私有 payload。错误 detail 由业务调用方负责选择安全公开字段。

## 用户认证

| 接口 | 输入与认证 | 成功 data |
| --- | --- | --- |
| `POST /auth/register` | `{email,password}` | `{id,email,createdAt}`，注册不自动登录 |
| `POST /auth/login` | `{email,password}` | `{user,token,tokenType:"Bearer"}` |
| `GET /auth/me` | `Authorization: Bearer <token>` | 当前公开用户 |
| `POST /auth/logout` | `Authorization: Bearer <token>` | `null`，撤销当前会话 |

成功沿用 200 envelope；密码错误及未知账号统一 `AUTH_INVALID_CREDENTIALS`（401），缺失、无效或已撤销会话为 `AUTH_UNAUTHENTICATED`（401），规范邮箱重复为 `BUSINESS_EMAIL_ALREADY_EXISTS`（409）。邮箱去除首尾空白并 casefold；密码为 8–128 个字符，不裁剪。仅支持常见 `local@domain` 格式，不执行邮箱所有权验证。

密码通过 `pwdlib[argon2]` 哈希；未知账号执行 dummy Argon2 校验。每次登录生成独立的 32 字节随机 opaque token，仅客户端接收原值，SQLite 只存 64 位 SHA-256 hex digest。会话具有 createdAt、lastSeenAt、revokedAt，没有自动过期、expiresAt 或滑动 TTL；登出不删除用户或业务数据。

应用 lifespan 显式拥有 Database 和密码服务并确定关闭；不会自动运行迁移。业务 endpoint 可依赖 `auth.api.current_identity` 获取服务端认证的 owner。CORS 只允许 `http://127.0.0.1:5173`，认证响应 `Cache-Control: no-store`，不使用 cookie。测试只访问临时 SQLite。
