# On-call Pilot 前端

此 workspace 使用 Vue 3、Vite 6、TypeScript strict、Vue Router 与 Pinia 构建中文桌面 Web 认证工作台。浏览器只通过 `virtual:public-config` 消费允许公开的配置。

## 启动与验证

在仓库根运行 `npm run frontend:dev`。质量门禁为 `npm run frontend:lint`、`npm run frontend:format:check`、`npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build`。

## 认证与路由

`src/application.ts` 的 `createApplication` 创建每个应用独立的 Pinia、认证客户端、路由与公开 HTTP client；模块导入不访问 Storage 或网络。`main.ts` 显式传入公开 API URL 和 localStorage，再安装 router。

`/login`、`/register` 为 publicOnly，`/chat`、`/knowledge`、`/aiops`、`/mcp` 位于受保护的 `WorkspaceLayout`。根路径及未知路径回 `/chat`。未认证访问保留完整内部 redirect，登录后恢复；外站、认证页与未登记路径不能作为 redirect。首次导航缓存一次 `auth.initialize()`；恢复失败保留 token，显示错误及显式重试。

注册调用真实 P04 API，成功后返回登录，不隐式登录。登录只持久化 `oncall-pilot.auth.token`；公开用户与密码不持久化。刷新有 token 时经 `/auth/me` 恢复。登出先隐藏受保护画布并取消旧身份请求结果，尝试服务端撤销（10 秒取消上限），随后清理本地。失败同样清理本地，但明确提示未确认服务端撤销。

## 受保护数据与 typed transport

现有 `src/transport/apiClient.ts` 按共享 operation 返回 typed data 并运行时验证 envelope，`sseClient.ts` 按共享 SseEvent 解码网络流。基础传输支持 fetch、request ID、bearer、AbortSignal 注入，不自行读取秘密配置，不自动重连。

业务 HTTP 使用 `auth.request(operation, init)`；未来已登记 SSE endpoint 使用 `auth.stream(path, init)`。两者捕获请求身份，当前握手 401 清理认证和受保护状态；身份变更取消流，旧结果不影响新会话。本 Change 不创建 SSE 业务 endpoint。

`protectedData` 仅在内存记录当前资源选择，不伪造领域数据。新增实际业务 store 在 setup 中登记同步 reset，并在 scope dispose 时注销：

```typescript
onScopeDispose(auth.registerProtectedStore(reset));
```

清理回调只清客户端数据，不删除服务端资源。所有已登记回调都会执行，单个回调异常不会阻止后续回调；清理后汇总抛出异常。禁止向 localStorage 写入 chat、knowledge、AIOps 数据。

## 工作台与共享交互

`WorkspaceLayout` 提供导航 rail、仅 Chat 路由可用的 `conversations` slot、账号退出、标题与服务状态。`getHealth` 仅表示后端应用进程可连接，不代表业务或外部依赖正常；支持有界检查、手动刷新和卸载取消。route-canvas 铺满可用区域，不限制业务最大宽度，不统一套卡片。当前四个业务页面均为明确的“尚未开放”占位，不提供聊天、知识库、智能运维或工具操作。

共享组件位于 `src/components`：AppLoadingState、AppEmptyState、AppErrorState、AppFeedback、AsyncStatusBadge。状态均有文字与 ARIA。`feedback.show(kind, text)` 支持 success/info/error，最新消息替换旧消息并重置 3 秒计时；支持手动关闭和卸载清理 timer。

设计 tokens 集中在 `styles.css`；只让 document 滚动，不创建内部独立滚动区。桌面 1440×900、1280×720 是验收目标；窄视口沿用同一布局做换行防溢出，不提供移动专用抽屉、底部导航或替代流程。键盘焦点与 reduced motion 为共享基线。
