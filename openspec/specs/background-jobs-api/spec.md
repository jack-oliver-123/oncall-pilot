# background-jobs-api Specification

## Purpose

为已认证值班人员及后续客户端提供后台任务列表、详情、取消与重试的稳定 HTTP 合同，确保用户只能操作自己的持久任务，并以统一错误响应隐藏其他用户资源的存在性。

## Requirements

### Requirement: 后台任务 HTTP API
系统 SHALL 提供认证且 owner-scoped 的 `GET /background-jobs`、`GET /background-jobs/{id}`、`POST /background-jobs/{id}:cancel`、`POST /background-jobs/{id}:retry`，并在 contracts/OpenAPI 中定义请求、响应和统一错误 envelope。

#### Scenario: 查询任务
- **WHEN** 已认证用户请求任务列表或详情
- **THEN** 仅返回其 owner 的任务及当前状态、尝试次数、租约和时间戳

#### Scenario: 取消与重试
- **WHEN** 用户取消 queued/running 任务或重试 failed/cancelled 任务
- **THEN** Repository 原子更新状态/请求并返回最新任务；非法状态返回合同错误

#### Scenario: 重试保留历史
- **WHEN** 用户重试 failed 或 cancelled 任务
- **THEN** 创建新的 queued 任务并设置 retryOfJobId，原任务和事件保持可读

#### Scenario: 无认证及资源越权
- **WHEN** 用户未认证或请求他人的任务
- **THEN** 未认证返回 401，越权与缺失返回完全相同的 AUTH_FORBIDDEN 403
