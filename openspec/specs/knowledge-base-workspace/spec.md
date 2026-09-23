# knowledge-base-workspace Specification

## Purpose

为值班人员提供一个受认证保护、由真实后端 API 驱动的中文知识库桌面工作区，让文档上传、切分预览、索引跟踪、失败恢复和删除操作形成可追溯闭环。

## Requirements

### Requirement: 服务端事实来源的知识库工作区状态
工作区 MUST 通过 typed knowledge client 和受保护的 Pinia store 管理知识库列表、文档列表、选中文档详情、chunk preview、文档索引任务以及覆盖确认状态。知识库、文档、详情、预览和任务数据 MUST 来自真实 HTTP API；领域数据不得写入 `localStorage`，不得用静态数组伪造。认证失效或账号切换时，store MUST 清空内存状态并拒绝旧请求写回新身份。

#### Scenario: 首次进入工作区
- **WHEN** 已认证用户打开 `/knowledge`
- **THEN** 客户端读取知识库和服务端文档列表，页面用 loading、空状态或列表状态表达当前结果

#### Scenario: 登出或账号切换
- **WHEN** 认证状态清理 knowledge store
- **THEN** 知识库、文档、详情、预览、任务、错误和覆盖确认全部清空，服务端文档不被删除

#### Scenario: 旧请求返回
- **WHEN** 账号切换后旧用户的请求才返回
- **THEN** 旧响应不得写入当前 knowledge store

### Requirement: 上传策略选择与显式索引
工作区 MUST 只允许选择 `.md` 和 `.pdf` 文件，并使用共享 upload policy 在提交前提示扩展名、MIME、10 MiB 大小和 UTF-8 Markdown 约束；后端校验仍是最终权威。上传前 MUST 让用户选择 `fixed-character`、`markdown-heading` 或 `paragraph` 策略；只有 `fixed-character` 请求可发送 `maxCharacters` 和 `overlap`，另外两种策略 MUST 不发送这些字段。上传成功后客户端 MUST 显式创建索引任务，并向用户表达文档已进入索引流程。

#### Scenario: 选择 fixed-character 上传
- **WHEN** 用户选择 fixed-character 并提交有效 Markdown 或 PDF
- **THEN** multipart 请求包含文件、overwrite 值和包含 strategy、maxCharacters、overlap 的 chunking config，上传成功后另发创建索引任务请求

#### Scenario: 选择 heading 或 paragraph 上传
- **WHEN** 用户选择 markdown-heading 或 paragraph
- **THEN** multipart 请求的 chunking config 只包含 strategy，不包含 maxCharacters 或 overlap

#### Scenario: 前端即时拒绝明显无效文件
- **WHEN** 用户选择非 `.md`/`.pdf` 文件或超过共享大小限制的文件
- **THEN** 页面显示中文可访问提示且不发上传请求

### Requirement: 索引任务跟踪与恢复操作
工作区 MUST 约每 2 秒 poll 活动文档索引任务，并显示 pending、running、succeeded、failed、cancelled 的文字状态。失败时 MUST 展示安全的 failure reason，并提供 retry 或手动重建；取消 MUST 通过已有通用 background-job API 能力执行，不得在知识页实现另一套后台任务状态机。任务和文档状态以服务器最新响应为准。

#### Scenario: 上传后跟踪任务
- **WHEN** 上传和索引任务创建成功
- **THEN** 页面显示 indexing 状态并定期读取该任务，直到进入终态或用户离开页面

#### Scenario: 任务失败后恢复
- **WHEN** 索引任务为 failed 或 cancelled
- **THEN** 页面显示 failure reason，并允许 retry 或创建保留 retryOfTaskId 的新 attempt，成功后继续轮询新任务

#### Scenario: 取消活动任务
- **WHEN** 用户取消 queued 或 running 的后台任务
- **THEN** 客户端调用通用 background-job cancel endpoint，随后刷新任务和文档状态，不创建知识页专用取消状态机

### Requirement: 冲突、删除和服务端刷新
hash 冲突 MUST 显示明确的覆盖确认；未确认前不得静默覆盖。删除 MUST 显示明确确认，成功后 MUST 重新读取服务端文档列表并清理对应的选中详情和 preview。冲突、权限、校验和网络失败 MUST 以可访问中文错误呈现。

#### Scenario: hash 冲突
- **WHEN** 上传返回 `BUSINESS_CONFLICT`
- **THEN** 页面说明已有同内容文档并提供覆盖确认，未确认时原文档保持不变

#### Scenario: 确认覆盖
- **WHEN** 用户明确确认覆盖并重新提交相同文件
- **THEN** multipart 请求带 `overwrite=true`，成功后页面展示新文档并从服务器刷新列表

#### Scenario: 删除文档
- **WHEN** 用户确认删除选中文档
- **THEN** 客户端调用真实 DELETE endpoint，成功后刷新服务端列表并折叠详情

### Requirement: 桌面文档列表与行内详情布局
工作区 MUST 在桌面提供有界的文档列表区域；列表可独立滚动，详情默认在对应文档行下折叠。展开详情后 metadata 与 chunk preview MUST 各自有界滚动，长表格 MUST 支持横向滚动且不能撑坏整页；页面 MUST 只有一个页面级滚动上下文，不新增移动专用导航或替代流程。

#### Scenario: 折叠和展开详情
- **WHEN** 用户点击文档行的详情操作
- **THEN** 对应行下展开或折叠详情，其他文档行保持可扫描且不被导航离开

#### Scenario: 预览长文档
- **WHEN** chunk preview 返回多段长文本或长 metadata
- **THEN** 预览容器在固定边界内滚动，表格需要时可横向滚动，页面和工作台壳不产生第二个独立滚动条

### Requirement: 工作区状态可访问
loading、empty、error、上传校验、覆盖确认、删除确认和索引 status MUST 同时提供中文文字和合适的语义化/ARIA 状态；状态不能只靠颜色表达。键盘焦点 MUST 可见，用户请求 reduced motion 时不得播放非必要动画。

#### Scenario: 状态辅助技术表达
- **WHEN** 使用键盘或屏幕阅读器检查工作区
- **THEN** loading、错误、空列表、任务状态和确认操作均可被文字和语义化控件理解
