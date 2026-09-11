## Purpose

为值班人员提供受认证和 tenant 约束的个人知识文档管理能力，并为后续索引保留稳定、可追溯的正文与元数据基础。

## ADDED Requirements

### Requirement: 隐式默认知识库与 owner-scoped 文档 API
系统 MUST 为每个认证用户提供一个稳定的隐式默认知识库 ID，且不得提供创建或删除多个知识库的能力。系统 MUST 提供 `GET /knowledge-bases`、`GET/POST /knowledge-bases/{kb}/documents`、`GET/DELETE /knowledge-bases/{kb}/documents/{document}` 和 `GET /knowledge-bases/{kb}/documents/{document}/chunk-preview`；所有路径 MUST 从 `CurrentUser` 派生 owner scope。

#### Scenario: 用户访问自己的默认知识库
- **WHEN** 已认证用户请求 `GET /knowledge-bases`
- **THEN** 返回仅包含该用户稳定默认知识库的 DTO，且其文档列表只包含该用户的文档

#### Scenario: 跨用户访问知识库或文档
- **WHEN** 用户使用其他用户的 `kb` 或 `document` 标识请求任一路径
- **THEN** 返回统一 `AUTH_FORBIDDEN` 403，且不披露资源是否存在

#### Scenario: 未认证访问
- **WHEN** 请求缺少有效认证
- **THEN** 返回合同定义的 401 错误

### Requirement: 文件上传 policy 与正文保存
系统 MUST 只接受 UTF-8 Markdown 和 PDF，单文件最大 10 MiB；后端 MUST 权威校验扩展名、MIME 和实际大小。Markdown 正文 MUST 按 UTF-8 解码，PDF MUST 提取文本。系统 MUST 保存文件名、size、MIME、SHA-256、uploadedAt、index status、实际 chunking config 和可索引正文，且不得把原文写入 MinIO。

#### Scenario: 上传有效 Markdown 或 PDF
- **WHEN** 用户上传符合扩展名、MIME、编码和大小限制的文件
- **THEN** 保存文档元数据和可索引正文，并返回文档 DTO 及初始索引状态

#### Scenario: 拒绝无效文件
- **WHEN** 文件扩展名、MIME、UTF-8 编码或实际大小不符合 policy
- **THEN** 返回合同定义的校验错误，且不产生文档记录或外部向量副作用

### Requirement: 重复 hash、覆盖和删除生命周期
系统 MUST 在同一 owner/KB 下对活动文档 SHA-256 重复默认返回 `BUSINESS_CONFLICT` 409。只有显式 `overwrite` 才能软删除旧文档、按 owner/KB/document scope 清理旧向量并保存新文档。普通删除 MUST 同样清理对应 owner/KB/document scope 的向量；受保护 Repository 查询 MUST 在 SQL 层同时限定 owner、KB 和资源关系。

#### Scenario: 重复上传默认冲突
- **WHEN** 同一用户同一知识库上传 SHA-256 相同且未请求 overwrite 的文件
- **THEN** 返回 `BUSINESS_CONFLICT` 409，原文档保持活动状态

#### Scenario: 显式覆盖
- **WHEN** 同一用户同一知识库上传相同 hash 且明确请求 overwrite
- **THEN** 旧文档软删除并清理其 owner-scoped 向量，再保存新文档

#### Scenario: 删除文档
- **WHEN** 用户删除自己的文档
- **THEN** 文档软删除且只清理对应 owner、KB 和 document scope 的向量

### Requirement: 文档 DTO 和可追溯索引元数据
文档详情和列表 DTO MUST 返回稳定 document ID、原始文件名、size、MIME、SHA-256、uploadedAt、index status 以及实际采用的 chunking strategy 和参数；不得返回原文全文。

#### Scenario: 查询文档详情
- **WHEN** 用户请求自己的文档详情
- **THEN** 返回完整元数据和切分配置，不返回文件正文
