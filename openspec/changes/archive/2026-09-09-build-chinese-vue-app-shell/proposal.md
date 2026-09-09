## Why

P04 认证与共享合同已具备真实服务能力，但前端仍是静态 foundation 入口。需要建立可恢复身份、隔离账号数据并承载后续业务路由的中文桌面工作台。

## What Changes

- 使用 Vue Router 与 Pinia 接入真实登录、注册、身份恢复、退出及受保护状态清理。
- 提供 /login、/register，以及 WorkspaceLayout 下 /chat、/knowledge、/aiops、/mcp；根路径与未知路由回到 /chat。
- 建立 rail、Chat 专属会话插槽、账号退出、顶栏标题与真实服务连通状态，业务画布铺满剩余空间。
- 复用已登记的 registerUser、loginUser、getCurrentUser、logoutUser、getHealth HTTP operations 与 SseEvent；不扩展 endpoint、schema、错误码或事件合同。为现有 SSE 添加认证生命周期接入。
- 建立共享加载、空、错误、反馈与异步状态组件，以及中文设计 tokens、Lucide 图标、焦点和 reduced motion。
- 以桌面浏览器验收；不新增移动专用流程，不实现聊天、知识库、智能运维或工具连接业务，不使用领域假数据。

## Capabilities

### New Capabilities
- `authenticated-workspace-shell`：认证路由、中文桌面工作台、Pinia 受保护数据及共享交互状态。

### Modified Capabilities
- `frontend-auth-state`：补充认证 SSE 及登出撤销顺序，保留失败清理与异步身份隔离。

## Impact

主要影响 apps/frontend 的应用入口、认证状态、路由、stores、布局、视图、共享组件与测试；依赖现有 Vue Router、Pinia、Lucide，不增加运行依赖。同步 OpenSpec 与 WIKI。后端及 contracts 通过现有测试确认兼容；不修改生产配置、用户本地配置或业务数据库。
