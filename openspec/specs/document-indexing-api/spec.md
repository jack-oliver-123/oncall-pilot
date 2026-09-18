# document-indexing-api Specification

## Purpose

为前端提供文档上传后显式发起索引、查询进度、重建重试和取消的稳定 owner-scoped HTTP contract，使文档索引不依赖连接存活并能安全恢复。

## Requirements

### Requirement: 索引任务 HTTP contract
系统 MUST 在 canonical OpenAPI、Python DTO 和 TypeScript contract 中定义认证 owner-scoped 的 POST `.../index-tasks`、GET `.../index-tasks/{task}`、POST `.../index-tasks/{task}:retry`、POST `.../index-tasks/{task}:cancel`，响应统一使用 API success/failure envelope，并返回领域状态、文档/知识库标识、失败原因（安全可公开内容）、时间戳和 retry 来源。

#### Scenario: 查询任务
- **WHEN** 已认证用户查询自己的索引 task
- **THEN** 返回与后端领域记录一致的 DTO；queued 显示为 pending

#### Scenario: 首次任务创建
- **WHEN** 已认证客户端在上传成功后提交 document ID
- **THEN** API 校验 owner/KB/document 关系，创建 pending task 并将其加入 durable 队列

#### Scenario: 非法或越权任务
- **WHEN** 请求缺少认证、引用不存在资源或引用其他用户资源
- **THEN** 分别返回合同定义的 401 或统一 AUTH_FORBIDDEN 403 envelope

### Requirement: 重试与取消 contract
重试 endpoint MUST 创建新 task 并保留来源关系；取消 endpoint MUST 支持 queued/running 任务并返回持久化状态。已完成任务的非法状态变更 MUST 返回 BUSINESS_CONFLICT 409，不能伪造成功。

#### Scenario: 重试来源保留
- **WHEN** 用户重试一个 failed 或 cancelled task
- **THEN** 响应返回新的 task ID，retryOfTaskId 指向旧 task，旧 task 和其历史保持不变

#### Scenario: 取消已运行任务
- **WHEN** 用户取消 running task
- **THEN** API 返回已记录取消请求的状态，worker 最终完成领域状态更新
