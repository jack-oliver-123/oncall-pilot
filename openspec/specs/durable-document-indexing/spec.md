# durable-document-indexing Specification

## Purpose

为个人知识文档提供可在客户端断开、worker 重启和外部依赖失败后继续恢复的持久索引执行能力，并让每次索引结果可追踪、可重建且严格受 owner scope 保护。

## Requirements

### Requirement: 持久文档索引领域任务
系统 MUST 在 SQLite 持久化 `document_index_tasks` 领域记录，保存 task ID、owner、knowledge base、document、status、failureReason、retryOfTaskId 以及 created/updated/started/completed 时间戳。领域记录 MUST 通过 `background_jobs.resourceType=document_index_task` 与 `resourceId=taskId` 关联，且不得新增 `jobId` 列。

#### Scenario: 显式创建首次任务
- **WHEN** 文档上传成功后客户端显式 POST 索引任务
- **THEN** 创建一个领域 task 和一个已入队的 durable background job，文档仍由上传 API 单独创建

#### Scenario: 客户端断开
- **WHEN** 客户端在创建任务后断开连接
- **THEN** durable worker 继续执行，任务状态和结果仍持久保存

### Requirement: 有序索引流程与完整向量 metadata
索引 handler MUST 重新读取当前 owner-scoped 文档，复用 P10 splitter 产生全部 chunks，使用 embedding provider 按每批最多 10 条且保持顺序生成向量，显式 initialize Milvus，按完整 owner/tenant/knowledge base/document scope 删除旧 chunks，再一次批量写入全部 chunks。每条记录 MUST 写入 chunkId、documentId、knowledgeBaseId、ownerUserId、tenantId、content、source、createdAt 和 chunking metadata。

#### Scenario: 超过十段文档
- **WHEN** 文档产生超过 10 个 chunks
- **THEN** 只有 embedding 调用分成多个每批不超过 10 条的有序批次，Milvus 只执行一次包含全部记录的 insert_chunks

#### Scenario: 初始化和清理顺序
- **WHEN** handler 开始索引一个已有向量的文档
- **THEN** Milvus initialize 发生在删除前，删除发生在一次批量写入前，调用顺序可观测且删除始终带完整 scope

### Requirement: 状态、失败恢复与取消
领域状态 MUST 统一使用 `pending`、`running`、`succeeded`、`failed`、`cancelled`。底层 background job 的 `queued` MUST 映射为 `pending`；embedding、splitter 或 Milvus 错误 MUST 不被吞掉，安全 failureReason MUST 持久化，失败不得将文档标记为 succeeded。任务 MUST 支持有限自动重试、手动重建并保留 retryOfTaskId，以及 queued/running 取消。

#### Scenario: 依赖失败
- **WHEN** embedding、切分或 Milvus 任一步骤失败
- **THEN** 文档和领域 task 进入失败或可恢复状态，持久化原因不含凭据或原始异常，且不返回成功状态

#### Scenario: 手动重建
- **WHEN** 用户对已失败、已取消或已完成的任务请求重建
- **THEN** 创建新的 attempt 和 durable job，旧 task 保留且新 task 的 retryOfTaskId 指向来源

#### Scenario: 取消
- **WHEN** 用户取消 queued 或 running 索引任务
- **THEN** queued 任务直接成为 cancelled，running 任务收到协作取消信号并最终成为 cancelled，客户端不需要保持连接

### Requirement: 索引任务 owner isolation
所有索引任务创建、查询、重试、重建和取消 MUST 从 `CurrentUser` 派生 owner scope，并在 SQL 查询同时限定 owner、knowledge base 和 document 关系；跨用户操作 MUST 统一为 AUTH_FORBIDDEN，不披露任务存在性。

#### Scenario: 跨用户访问
- **WHEN** 用户 B 使用用户 A 的 task、document 或 knowledge base ID 请求索引操作
- **THEN** 返回统一 403 envelope，且不创建、修改或读取用户 A 的任务
