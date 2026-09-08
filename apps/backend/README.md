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
