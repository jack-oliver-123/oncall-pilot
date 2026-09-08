# On-call Pilot API contracts

此 workspace 暴露最小 typed entrypoint，目前只包含与后端 `/health` 一致的 `HealthResponse`。它不承担业务 contract 或 OpenAPI code generation。

## 验证

从仓库根运行：

```powershell
npm run contracts:typecheck
npm run contracts:test
```

contracts 不依赖 frontend 或 backend，frontend 通过 npm workspace 单向依赖本包。
