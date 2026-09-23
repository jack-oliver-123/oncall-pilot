## Why

P08 已提供认证工作台壳，P10 和 P11 已提供知识文档、切分和持久索引后端能力，但值班人员仍无法通过 `/knowledge` 管理真实知识库。当前前端只有零散的上传适配器，没有服务端事实来源驱动的状态管理、冲突确认、切分预览和后台任务恢复流程；现在补齐最终桌面工作区，才能让后端能力形成可用的完整闭环。

## What Changes

- 在 `packages/api-contracts` 中补齐并验证知识库工作区使用的知识库、文档、切分预览、索引任务和上传 multipart 合同，复用统一认证 header、envelope、错误目录与上传 policy。
- 新增 typed `knowledgeClient` 与 Pinia `knowledge` store，管理知识库、文档、选中详情、chunk preview、索引任务及覆盖确认；所有领域数据来自服务器，不使用 `localStorage` 或静态领域数组。
- 将 `/knowledge` 替换为真实中文桌面工作区：上传 `.md`/`.pdf`、选择切分策略、即时提示 policy、显式创建索引任务、轮询活动任务、显示失败原因并支持 retry、重建和通用后台任务取消。
- 对 hash 冲突和删除提供明确确认；成功后重新读取服务端列表，避免客户端状态与后端事实脱节。
- 提供行内折叠详情、metadata 和 chunk preview 有界滚动、长表格横向滚动，以及 loading、empty、error、status 的可访问中文文字；桌面页面只保留一个页面级滚动上下文。
- 增加 store、client、组件和合同门禁测试，并完成真实后端 API 的本地桌面浏览器 MD/PDF 上传、索引、预览、删除 smoke。

## Capabilities

### New Capabilities

- `knowledge-base-workspace`: 提供面向值班人员的真实知识库桌面管理工作区、Pinia 状态模型、上传策略选择、详情与切分预览、索引任务跟踪和确认交互。

### Modified Capabilities

- `knowledge-documents`: 明确客户端上传策略、hash 冲突确认、服务端刷新和文档列表工作区消费现有 owner-scoped API 的要求。
- `document-chunking`: 明确工作区只向 `fixed-character` 发送长度与 overlap，并通过 preview endpoint 展示服务端实际切分配置和结果。
- `durable-document-indexing`: 明确工作区轮询索引任务、展示失败原因、retry/重建，并将取消交给通用 background-job 能力的客户端使用边界。
- `authenticated-workspace-shell`: 将 `/knowledge` 从诚实占位页变为真实受保护业务页，并保留受保护 store 清理、单滚动上下文和可访问状态要求。

## Impact

- 前端：`apps/frontend/src/knowledge`、Pinia stores、知识库视图、工作台路由和全局样式；不改变认证及其他业务路由的行为。
- 共享合同：`packages/api-contracts/openapi/foundation.openapi.json`、生成类型、运行时校验及合同测试；使用现有后端路径并补齐客户端所需 request schema。
- 后端：复用 P10/P11 已实现的 knowledge、chunk preview、document index task 和 background-job API，不新增领域存储或绕过 owner isolation；仅在合同漂移时修正实现与生成物的一致性。
- 测试与验收：前端 typecheck/test/build、contracts 门禁、相关 backend tests、OpenSpec 严格校验、`git diff --check` 和本地真实后端浏览器 smoke；真实截图保存在仓库外。
