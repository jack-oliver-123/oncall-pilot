# On-call Pilot 后端

此 workspace 提供 `oncall_pilot` src-layout package、FastAPI app factory、主机 CLI、`/health`、通用 JSON 配置加载和空 Alembic async 环境。它不包含业务模型、认证、Agent 或 MCP 功能。

## 安装与启动

```powershell
uv sync
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
