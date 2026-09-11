## Context

参见 `proposal.md` 的 Why。现有认证、`OwnerScope`、SQLite 和 Milvus 边界已经分别由既有 capability 定义；本 change 需要把它们组合成文档生命周期，而不引入跨应用源码依赖或运行时全局连接。

## Goals / Non-Goals

**Goals:**

- 以 contracts OpenAPI 为 HTTP 输入输出和错误码唯一来源，再生成 TypeScript/Python 类型。
- 通过显式注入的文档 repository、文本提取器、chunking service 和 vector deletion adapter 完成可测试的 owner-scoped 生命周期。
- 让 Markdown 与 PDF 最终得到同一种可索引文本，并让 preview 与未来 indexing 共享纯函数入口。
- 用 SQLite 活动/软删除状态、唯一 owner/KB/hash 约束和事务保证冲突与覆盖的一致性。

**Non-Goals:**

- 不创建前端文档 UI，不实现全文检索、embedding、index worker 或 MinIO 原文存储。
- 不支持用户自定义知识库、跨用户共享、批量上传或任意文件格式。

## Decisions

### 1. Contract-first 的 multipart API

在 `foundation.openapi.json` 增加 knowledge base/document schemas、upload policy 常量、multipart request、preview response 和 `AUTH_UNAUTHENTICATED`/`AUTH_FORBIDDEN`/`BUSINESS_CONFLICT`/validation responses。OpenAPI 的 schema 负责可观察字段；后端仍对扩展名、MIME、实际字节数和 Markdown 解码做权威检查。选择 multipart 是因为文件与 overwrite/chunking 参数必须在一次请求中提交；跨 SQLite/Milvus 不宣称分布式原子事务，不另造 JSON 临时协议。

### 2. 默认知识库使用确定性 ID

知识库 ID 由认证用户 ID 通过既有 owner scope 的确定性规则派生，API 只暴露该默认记录。数据库文档表直接存 `owner_user_id` 与 `knowledge_base_id`，所有 repository 方法使用无默认值的 keyword-only owner 参数，并在 SQL WHERE 同时限定三者；不依赖先查资源再做 service 检查。

### 3. 正文留在 SQLite，向量删除走注入 adapter

文档表保存提取后的可索引正文和切分 JSON 配置，原始上传文件不落 MinIO。文档 repository 与 vector deletion adapter 在 service 层协调：先在 owner scope 内标记旧文档删除，再清理同 owner/KB/document 的向量；adapter 失败时由事务/补偿边界返回可重试错误，测试使用 fake，不建立真实 Milvus 连接。

### 4. 纯文本 splitter service

实现 `chunk_document_text(text, config, *, limit=None)` 为无 I/O 的统一入口，config 保存 strategy 与参数，返回带顺序、字符范围/标题等 metadata 的 chunk。fixed-character 使用滑动窗口；heading 按 Markdown heading 分组并继承标题路径、忽略围栏代码中的标题标记；paragraph 按空行分割。策略配置经单独 validator 规范化，只有 fixed-character 生成默认参数，其余策略拒绝 max/overlap；文档写入规范化后的配置，preview 传入 limit=12 提前停止切分并裁剪 excerpt。

### 5. PDF 提取与输入生命周期

HTTP adapter 在 multipart 解析前累计请求流，超过 10 MiB + 64 KiB 的头部/字段预算即拒绝；文件读取上限为 10 MiB + 1 字节，service 按精确 10 MiB 上限校验文件大小、扩展名和声明 MIME。Markdown 严格 UTF-8 decode，PDF 由 `pypdf` 从内存字节流提取页文本。提取完成后只把正文交给 repository，框架临时上传文件在响应后关闭，不持久化临时路径或依赖应用目录。模块导入不执行配置读取、数据库、Milvus 或 pypdf 文件操作。

## Risks / Trade-offs

- [PDF 文本顺序或扫描 PDF 质量不稳定] -> 提取失败/空正文返回明确 validation 错误，不保存文档；用真实文本 PDF fixture 覆盖，不宣称 OCR。
- [SQLite 正文增加数据库体积] -> 当前范围接受 10 MiB 单文件上限；未来大文件存储可另建 change，不能提前引入 MinIO 原文。
- [覆盖与向量删除跨存储不具备单事务] -> 采用 owner/KB/document 精确删除、软删除和可重试 adapter，测试验证 scope；未来索引 change 再定义 outbox/后台补偿。
- [heading/paragraph 对边界文本的解释差异] -> 将策略输入输出和 metadata 固定在 service tests，并让 preview/indexing 只调用同一入口。

### 补充：已核实的输入与事务边界

认证错误复用现有 `AUTH_UNAUTHENTICATED`。multipart 字段为 file、可选 JSON 字符串 chunkingConfig 与 overwrite（默认 false）。`.md` 接受 text/markdown、text/plain，`.pdf` 接受 application/pdf；扩展名忽略大小写，UTF-8 BOM 可接受，缺失 MIME、空文件、空白正文、加密/损坏/无文本 PDF 返回校验失败。overlap 必须为非负整数。

SQLite 事务不得等待向量网络 I/O：短事务记录软删除意图及 hash 占位，事务外在线程池调用精确 Milvus 删除，短事务确认清理后释放 hash 占位。失败返回统一内部错误，DELETE 同一 ID 可重试；overwrite 必须先完成清理再发布新记录。活动记录及待清理记录共同持有唯一 owner/KB/hash 占位，最终发布并发冲突返回 409。不在本 change 创建后台补偿或 indexing。

## Migration Plan

新增 SQLite migration 创建知识库/文档表及索引；部署时不迁移现有业务数据。回滚应用版本前保留新增表，必要时由独立数据库迁移操作清理；不删除既有认证、tenant 或向量表。
