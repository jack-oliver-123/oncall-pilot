## MODIFIED Requirements

### Requirement: 后端提供依赖无关的健康检查
后端 SHALL 在 `/health` 提供进程存活检查，成功响应 MUST 为 HTTP 200 和 `{ok:true,data:{status:"ok"},meta:{requestId}}`，该检查 MUST 不探测数据库或外部服务。

#### Scenario: 调用健康检查
- **WHEN** 客户端向已创建的应用请求 `/health`
- **THEN** 返回 HTTP 200 和共享成功 envelope，其中 data 为 `{"status":"ok"}`
- **THEN** meta.requestId 与响应 X-Request-ID 一致
- **THEN** 请求过程中不连接 SQLite、Milvus、LLM 或 MCP
