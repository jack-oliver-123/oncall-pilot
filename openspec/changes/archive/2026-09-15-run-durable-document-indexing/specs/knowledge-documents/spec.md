## MODIFIED Requirements

### Requirement: 文件上传 policy 与正文保存
系统 MUST 只接受 UTF-8 Markdown 和 PDF，单文件最大 10 MiB；后端 MUST 权威校验扩展名、MIME 和实际大小。Markdown 正文 MUST 按 UTF-8 解码，PDF MUST 提取文本。系统 MUST 保存文件名、size、MIME、SHA-256、uploadedAt、index status、实际 chunking config 和可索引正文，且不得把原文写入 MinIO。上传 API MUST 只创建文档，不隐式创建或入队索引任务；客户端成功后 MUST 显式调用索引任务 endpoint。

#### Scenario: 上传有效 Markdown 或 PDF
- **WHEN** 用户上传符合扩展名、MIME、编码和大小限制的文件
- **THEN** 保存文档元数据和正文，返回文档 DTO 及 `pending` 初始索引状态，但不产生 background job

#### Scenario: 上传后显式索引
- **WHEN** 客户端收到上传成功响应并 POST 索引任务
- **THEN** 任务进入 durable 队列，文档状态与任务状态保持一致

#### Scenario: 拒绝无效文件
- **WHEN** 文件扩展名、MIME、UTF-8 编码或实际大小不符合 policy
- **THEN** 返回合同定义的校验错误，且不产生文档记录或外部向量副作用

### Requirement: 文档 DTO 和可追溯索引元数据
文档详情和列表 DTO MUST 返回稳定 document ID、原始文件名、size、MIME、SHA-256、uploadedAt、index status 以及实际采用的 chunking strategy 和参数；不得返回原文全文。index status MUST 使用 `pending`、`running`、`succeeded`、`failed`、`cancelled`。

#### Scenario: 查询文档详情
- **WHEN** 用户请求自己的文档详情
- **THEN** 返回完整元数据和切分配置，不返回文件正文，且状态可反映索引任务最新持久状态
