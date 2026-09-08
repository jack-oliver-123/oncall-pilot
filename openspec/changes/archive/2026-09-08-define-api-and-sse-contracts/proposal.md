## Why

工程基座 `establish-project-foundation` 已验证并归档（用户确认它是原请求中 bootstrap 前置工程）。目前只有手写健康响应，两端缺少统一错误、request ID 和事件协议，后续功能容易产生互不兼容的临时 payload。需要先冻结可机器验证的共享合同，再增加业务 endpoint。

## What Changes

- 以 `packages/api-contracts` 中的 OpenAPI 3.1 文档及其 JSON Schema components 为 HTTP、错误目录、path、SSE 的唯一事实源，生成 TypeScript 和 Python 协议声明并检测漂移。
- **BREAKING**：`/health` 从裸 `{status:"ok"}` 改为 `{ok:true,data:{status:"ok"},meta:{requestId}}`，继续只表示进程存活。
- 统一四类错误、验证字段路径、安全默认消息、异常响应与 `X-Request-ID` 透传/生成。
- 定义八类 SSE 事件、chat/aiops channel、工具四态生命周期，事件错误复用 HTTP 错误结构。
- 建立 typed apiClient/sseClient，提供 request ID/bearer/fetch 注入、运行时协议校验和跨字节 chunk frame 解析。
- 用生成检查、跨语言合同测试、path 对齐和禁止私有事件结构的边界测试约束后续扩展。

## Capabilities

### New Capabilities

- `api-protocol`: 成功/失败 envelope、错误目录、request ID、安全异常、OpenAPI 合同及后续扩展规则。
- `sse-protocol`: 八类事件和工具生命周期、公共字段、错误复用与 wire frame。
- `frontend-transport`: typed HTTP/SSE transport、注入点、协议校验及分块流处理。

### Modified Capabilities

- `backend-foundation`: 健康检查响应改用共享成功 envelope，保留无依赖探测约束。
- `wiki-sync`: 修复同日归档时只按名称折叠 delta 的误判，以 OpenSpec 创建日期作为同日排序依据，保证本次前置和后续合同可连续归档。

## Impact

影响 contracts 源/生成物/测试、后端协议适配与测试、前端 transport 与测试、根生成检查命令和合同扩展文档。后端运行时不读取 TypeScript 或仓库合同文件，不增加应用 npm 依赖；测试可增加 JSON Schema 验证器。当前 OpenAPI 只登记 foundation 的 `/health`，不实现认证、聊天、AIOps、业务 SSE endpoint、自动重连、持久化或 UI 变更。
