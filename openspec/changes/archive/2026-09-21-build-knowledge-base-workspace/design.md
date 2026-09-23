## Context

P08 的 `createApplication` 已集中创建认证、router、Pinia 和 protected store 清理机制；共享 transport 已能根据 `packages/api-contracts` 的 operation 表发送 bearer、request ID 和统一 envelope。P10/P11 后端已经提供默认知识库、文档 CRUD、chunk preview、文档索引任务和 durable background job API。当前知识路由仍渲染 `PlaceholderView`，已有 `knowledgeClient` 只覆盖上传后创建任务，且没有列表、详情、preview、覆盖和删除状态。

工作区必须保持 owner-scoped API 边界，不保存领域数据到浏览器持久化存储。后端已有文档索引任务路径与通用 background-job 路径，前端需要让两者的职责清晰：文档索引 task 用于展示业务状态和 failure reason，取消交由通用 job endpoint；不能在页面里复制一份任务运行时。

## Goals / Non-Goals

**Goals:**

- 让 `/knowledge` 使用真实 API 完成知识库加载、文档列表、上传、索引跟踪、详情和 chunk preview。
- 用共享 contract 的类型和 `documentUploadPolicy` 构造安全的 multipart 请求，并在策略变化时精确省略无效字段。
- 让 Pinia store 可测试、可清理、可防止旧身份请求污染，并把服务器响应作为状态事实来源。
- 让桌面文档工作区具备单页滚动上下文、有界列表/详情/preview 区域、键盘和状态可访问性。
- 使用 focused unit/component tests 保护 HTTP 合同、状态清理、轮询与确认交互。

**Non-Goals:**

- 不新增知识库创建、重命名、删除或多租户选择能力；默认知识库仍由后端按用户提供。
- 不改造后端索引 handler、向量存储、认证协议或通用 background-job worker。
- 不将原文正文返回浏览器，不在前端实现本地全文搜索或离线缓存。
- 不新增移动专用导航；移动视口只接受现有工作台的响应式布局。

## Decisions

### 1. knowledgeClient 只负责 typed HTTP 适配

在 `apps/frontend/src/knowledge/knowledgeClient.ts` 中封装知识库、文档、preview、文档索引 task 和通用 background-job operation。请求参数使用 contract operation 的路径参数和 `FormData`，上传 config 在 client 内从策略对象序列化，确保 heading/paragraph 不会携带 fixed 字段。client 不保存响应、不启动定时器，便于 store 控制身份生命周期。

备选方案是让组件直接调用 `auth.request`，这样会重复路径和 envelope 处理，也难以统一测试 multipart 和取消；因此不采用。

### 2. Pinia store 以请求代数保护身份边界

新增 `createKnowledgeStore(auth, clientFactory)`，状态包含 `knowledgeBases`、`documents`、`selectedDocumentId`、`selectedDetail`、`previewByDocumentId`、`tasksByDocumentId`、`uploadState`、`overwriteCandidate`、`deleteCandidate`、loading/error 和 polling 状态。每次 reset 增加 generation；异步 action 记录开始时 generation，只有 generation 仍相同且认证用户 ID 未变化时才写入结果。store 通过 `auth.registerProtectedStore(reset)` 登记清理，在 scope dispose 时注销。

轮询使用一个 store 内的 interval，活动 task 集合由服务器返回的任务状态决定；间隔固定为约 2000ms，终态移除。任务展示读取 document index task；取消 action 先从 task 得到关联 durable job/resource，再调用通用 background-job cancel，并刷新对应文档和任务。若现有后端返回无法直接关联的字段，保留 document task 的 cancel endpoint 作为兼容适配，但不在 UI 引入另一种本地状态机。

### 3. 上传 workflow 显式分两步，并把冲突变成可恢复输入

store 的 upload action 先调用文档 POST；成功后再调用 `createDocumentIndexTask`。如果创建 task 失败，保留已上传文档并显示可重试错误，不假装索引已成功。收到 `BUSINESS_CONFLICT` 时保存 `overwriteCandidate`（文件和策略），由组件要求用户明确确认后再次调用带 `overwrite=true` 的上传请求。删除同样通过组件原生确认对话框/确认区完成，成功后重新 list，不通过本地数组删除来模拟服务器结果。

### 4. `/knowledge` 采用数据密度优先的单页工作区

新增 `KnowledgeView.vue`，由顶部的知识库摘要和上传表单、活动索引提示、固定可用空间的文档列表组成。单知识库时只展示名称与文档计数，不渲染 selector；多知识库的 client 形状仍支持列表但当前后端只返回一个默认库。文档行包含状态文字、详情/删除操作；详情插入当前行之后，metadata 和 preview 各自放入 `max-height` + `overflow: auto` 的区域，metadata 使用 `overflow-x: auto` 的表格包装。

工作台 `route-canvas` 保持默认 grid，但 knowledge canvas 设置 `min-height: 0`，列表使用其唯一的内部垂直滚动容器，根页面不再因固定列表和详情产生第二个滚动上下文。小视口沿用现有侧栏和折叠结构，不新增替代导航。

### 5. 合同源文件优先，生成物可重复生成

如果 frontend 使用的 operation/schema 已经存在，优先补充 OpenAPI 的 multipart schema、request body 和错误响应，使 `scripts/generate_contracts.py` 生成 `generated.ts` 与 backend generated contracts，再运行 contracts check。测试直接检查 operation、security、FormData key、auth header 和 envelope，避免只测试一个 mock fetch 的 happy path。

## Risks / Trade-offs

- [Risk] 后台 worker 运行速度受 Qwen/Milvus 本地依赖影响，浏览器 smoke 可能长时间停留在 running → 用真实 backend 的 task 状态轮询、在 smoke 记录状态和失败原因，不把 pending 当作成功。
- [Risk] 现有 background job DTO 不一定能从 document task 直接得到 job ID → 优先复用已有通用 job resource 关联；若合同当前只能按 document task 取消，client 将该路径封装为通用 cancel adapter并保持 UI 不出现第二种状态模型。
- [Risk] 列表和详情同时包含长文本会导致桌面溢出 → 所有宽内容包裹在明确的有界滚动元素中，使用 1280×720 和 1440×900 浏览器截图检查 `scrollWidth` 与滚动容器数量。
- [Risk] 旧请求在登出后返回可能污染 store → generation 与当前 user ID 双重校验，并用测试模拟延迟响应后 reset。
- [Risk] API 生成物和实际 FastAPI 路由漂移 → 每次合同变更后运行生成 check、contracts tests 和相关 backend API tests，未通过时不进入浏览器 smoke。

## Migration Plan

1. 在现有 P08/P10/P11 基线上补充 contracts、frontend client/store/view 和 focused tests。
2. 运行前端、contracts、相关 backend、OpenSpec 和 diff 检查，并启动本地后端与 frontend dev server。
3. 使用真实账号在桌面浏览器完成 MD/PDF 上传、任务跟踪、preview 和删除，截图保存至仓库外 QA 目录。
4. 失败时回滚只涉及本 Change 的前端路由/组件和生成合同；SQLite/文档数据由测试临时配置隔离，代码回滚不会删除服务端业务数据。

## Open Questions

无。取消行为使用现有 document index cancel adapter 对外保持通用 background-job 语义，不扩大 P11 后端接口范围。
