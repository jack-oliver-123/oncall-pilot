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

当前页面仍为 foundation 壳，完整认证页面在 P08 实现；聊天、知识库、AIOps 或 MCP 操作尚未开放。桌面验收要求页面至多存在一个滚动容器，并检查键盘、reduced motion、console 和移动视口可读性。

`src/transport/apiClient.ts` 和 `sseClient.ts` 提供独立基础传输，不在当前页面发起请求。HTTP 调用使用共享 operation，SSE 事件联合直接来自 `@oncall-pilot/api-contracts`；错误 envelope 转换为 ApiClientError，协议无效使用 ProtocolError。通过参数传入 baseUrl、fetch、getRequestId、getBearer 和 AbortSignal；调用方从公开配置获取 API base URL。

## 可复用认证状态

`src/auth/authClient.ts` 封装四个认证操作，`src/auth/authState.ts` 提供可注入的 Vue 只读响应式状态。P08 可在应用组合层创建：

```typescript
const auth = createAuthState({
  client: createAuthClient({ baseUrl: publicConfig.frontend.apiBaseUrl }),
  storage: window.localStorage,
});
const unregister = auth.registerProtectedStore(() => protectedStore.$reset());
await auth.initialize();
```

示例中的 `protectedStore` 指未来实际业务 store；模块导入不会读取 Storage 或发送请求。应在应用创建时调用一次 initialize；有 token 时必须经 `/auth/me` 验证后恢复用户，无 token 保持未认证。网络/5xx 恢复失败保留 token 供重试，状态为 error，调用方应捕获错误。

认证仅向 localStorage 的 `oncall-pilot.auth.token` 保存 token，用户只在内存，密码不持久化。注册不自动登录；登录前清理旧身份，登出立即清理本地再请求服务端撤销。登出网络失败会抛出错误，不能向用户声称服务端已撤销。登出及 401 不删除服务端业务数据、不清除无关本地配置。迟到的认证响应不覆盖后来状态。

业务 HTTP 使用 `auth.request(operation, init)`，使 401 清理当前身份与全部已登记受保护 store；组件卸载后可调用 `unregister()` 解除清理回调。清理回调应同步清除本地状态且不抛异常。不在回调中调用服务端数据删除。完整页面接入、SSE 认证失效交互和跨标签页协调由后续对应 Change 决定。
