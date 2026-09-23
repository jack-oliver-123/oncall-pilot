## MODIFIED Requirements

### Requirement: 文件上传 policy 与正文保存
系统 MUST 只接受 UTF-8 Markdown 和 PDF，单文件最大 10 MiB；后端 MUST 权威校验扩展名、MIME 和实际大小。Markdown 正文 MUST 按 UTF-8 解码，PDF MUST 提取文本。系统 MUST 保存文件名、size、MIME、SHA-256、uploadedAt、index status、实际 chunking config 和可索引正文，且不得把原文写入 MinIO。上传 API MUST 只创建文档，不隐式创建或入队索引任务；客户端成功后 MUST 显式调用索引任务 endpoint。客户端上传前 MUST 从共享 upload policy 过滤 `.md` 和 `.pdf` 并提示明显违反 policy 的文件；客户端选择 chunking strategy 后，multipart 的 `chunkingConfig` MUST 只带该 strategy 允许的字段。

#### Scenario: 上传有效 Markdown 或 PDF
- **WHEN** 用户在工作区选择符合扩展名、MIME、编码和大小限制的文件及合法切分策略
- **THEN** 保存文档元数据和正文，返回文档 DTO 及 `pending` 初始索引状态，但不产生 background job

#### Scenario: 上传后显式索引
- **WHEN** 客户端收到上传成功响应并 POST 索引任务
- **THEN** 任务进入 durable 队列，文档状态与任务状态保持一致，工作区开始展示任务状态

#### Scenario: 拒绝无效文件
- **WHEN** 文件扩展名、MIME、UTF-8 编码或实际大小不符合 policy
- **THEN** 返回合同定义的校验错误，且不产生文档记录或外部向量副作用，工作区显示可访问中文错误

### Requirement: 重复 hash、覆盖和删除生命周期
系统 MUST 在同一 owner/KB 下对活动文档 SHA-256 重复默认返回 `BUSINESS_CONFLICT` 409。只有显式 `overwrite` 才能软删除旧文档、按 owner/KB/document scope 清理旧向量并保存新文档。普通删除 MUST 同样清理对应 owner/KB/document scope 的向量；受保护 Repository 查询 MUST 在 SQL 层同时限定 owner、KB 和资源关系。工作区 MUST 对冲突和删除采取显式确认，并在成功后刷新服务端列表。

#### Scenario: 重复上传默认冲突
- **WHEN** 同一用户同一知识库上传 SHA-256 相同且未请求 overwrite 的文件
- **THEN** 返回 `BUSINESS_CONFLICT` 409，原文档保持活动状态，工作区展示覆盖确认而不静默重试

#### Scenario: 显式覆盖
- **WHEN** 同一用户同一知识库上传相同 hash 且用户明确确认 overwrite
- **THEN** 旧文档软删除并清理其 owner-scoped 向量，再保存新文档，工作区重新读取服务端列表

#### Scenario: 删除文档
- **WHEN** 用户在确认对话中确认删除自己的文档
- **THEN** 文档软删除且只清理对应 owner、KB 和 document scope 的向量，工作区刷新服务端列表并清理已选详情
