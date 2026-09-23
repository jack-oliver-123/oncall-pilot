## 1. 共享合同与生成物

- [x] 1.1 对照现有 P10/P11 FastAPI 路由核对知识库、文档、chunk preview、文档索引任务和通用 background-job operation 的 OpenAPI path、security、request body、multipart 字段、response schema 和错误响应
- [x] 1.2 若合同缺少工作区需要的上传字段或响应约束，先修改 `foundation.openapi.json`，运行合同生成并补充 contracts tests，确保 TypeScript 与 backend generated contracts 对齐
- [x] 1.3 增加/更新合同测试，覆盖统一 bearer/request ID/envelope、upload policy、策略字段省略和真实路径，运行 `contracts:typecheck`、`contracts:test` 与 `contracts:check`

## 2. Typed knowledge client

- [x] 2.1 扩展 `knowledgeClient` 为列表、详情、上传、删除、chunk preview、文档 index task 创建/读取/retry 以及通用 background-job 列表/取消/重试的 typed adapter
- [x] 2.2 实现共享 upload policy 的前端即时校验、策略 config 序列化和 multipart，保证 `.md`/`.pdf`、overwrite、fixed 参数与 heading/paragraph 参数边界可测试
- [x] 2.3 增加 client 测试，覆盖 auth header/envelope、上传 FormData、策略字段、冲突错误、delete/preview/task 请求和请求失败行为

## 3. Pinia knowledge store

- [x] 3.1 新增受保护 `knowledge` store，维护 knowledgeBases、documents、selected detail、preview、tasks、loading/error/status、upload state 和 overwrite/delete confirmation
- [x] 3.2 实现首次加载、详情/preview 加载、上传后显式创建索引、冲突覆盖、删除后服务端刷新，以及服务器响应覆盖本地状态的 action
- [x] 3.3 实现约 2 秒活动 task poll、失败原因、retry/手动重建和通过通用 background-job 能力取消；终态停止 poll，组件卸载停止 timer
- [x] 3.4 登记 protected store 清理，使用 request generation 和当前用户校验阻止旧请求回写，增加 owner 数据清理、poll/retry/overwrite/delete/store 行为测试

## 4. 知识库桌面工作区

- [x] 4.1 将 `/knowledge` 路由接入真实 `KnowledgeView`，保留其他业务路由和 P08 认证保护行为；在单知识库时隐藏无意义 selector
- [x] 4.2 实现中文上传区、策略选择、fixed-character 长度/overlap 输入、policy 即时提示、上传中/成功/失败反馈和显式索引状态
- [x] 4.3 实现文档列表、默认折叠行内详情、metadata、chunk preview、失败原因、retry/重建/取消、hash 覆盖确认和删除确认
- [x] 4.4 增加有界列表/详情/preview 样式、长表格横向滚动和单滚动上下文约束，覆盖 desktop 与现有移动响应式布局的无溢出、可访问文字、focus 和 reduced motion
- [x] 4.5 增加组件测试，覆盖上传、策略字段、行内 detail、preview、冲突/删除确认、loading/empty/error/status 文字和滚动 CSS 约束

## 5. 集成验证与真实 smoke

- [x] 5.1 运行 frontend lint、format check、typecheck、test、build，修复实现与测试问题
- [x] 5.2 运行相关 backend knowledge/index/background-job tests、contracts 门禁、`openspec validate --all --strict` 和 `git diff --check`
- [x] 5.3 启动本地真实 backend API 与 frontend dev server，用桌面浏览器完成 MD/PDF 上传、索引跟踪、chunk preview、删除 smoke，确认 console、滚动和中文状态，并将截图保存在仓库外
- [x] 5.4 汇总验证证据，检查 OpenSpec tasks 与实现一致，准备 `openspec-verify-change` 与归档前的 delta spec 同步
