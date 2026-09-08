# On-call Pilot 前端

此 workspace 使用 Vue 3、Vite 6 和 TypeScript 5.6 strict 构建面向非技术值班人员的桌面 Web 壳。浏览器只通过 `virtual:public-config` 获取 allowlist 字段，不直接读取完整项目 JSON。

## 启动

从仓库根运行：

```powershell
npm run frontend:dev
```

## 验证

```powershell
npm run frontend:lint
npm run frontend:format:check
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
```

当前 foundation 不提供认证、聊天、知识库、AIOps 或 MCP 操作。桌面验收要求页面至多存在一个滚动容器，并检查键盘、reduced motion、console 和移动视口可读性。

`src/transport/apiClient.ts` 和 `sseClient.ts` 提供独立基础传输，不在当前页面发起请求。HTTP 调用使用共享 operation，SSE 事件联合直接来自 `@oncall-pilot/api-contracts`；错误 envelope 转换为 ApiClientError，协议无效使用 ProtocolError。通过参数传入 baseUrl、fetch、getRequestId、getBearer 和 AbortSignal；调用方从公开配置获取 API base URL，认证状态留给后续 Change。
