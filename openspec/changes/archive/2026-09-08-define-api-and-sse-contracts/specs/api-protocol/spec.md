## Purpose

为 On-call Pilot 所有 HTTP 消费方建立唯一、可机器验证的响应、错误目录和路径合同，确保跨语言实现具有一致的成功、失败与请求关联语义，并使后续业务扩展具备稳定且可追踪的边界。

## ADDED Requirements

### Requirement: HTTP 响应使用统一 envelope
HTTP API MUST 返回 `{ok:true,data,meta:{requestId}}` 或 `{ok:false,error:{code,category,httpStatus,message,details?},meta:{requestId}}`，不得返回私有 envelope。

#### Scenario: 成功响应保留 JSON 数据
- **WHEN** 请求成功，数据为对象、数组、标量或 null
- **THEN** ok 为 true，data 完整保留，meta 含有效 requestId

#### Scenario: 四类错误响应
- **WHEN** 发生 AUTH、BUSINESS、VALIDATION 或 SYSTEM 错误
- **THEN** ok 为 false，HTTP 状态与 error.httpStatus 相同，code/category/status 来自稳定目录

### Requirement: 错误目录安全且可扩展
每个错误码 MUST 具有固定 category、HTTP status 和安全默认消息；AUTH_*、BUSINESS_*、VALIDATION_*、SYSTEM_* 及新增业务错误 MUST 先登记合同，未登记错误不得作为公共响应发出。

#### Scenario: 未知异常与框架错误
- **WHEN** endpoint 抛出未知异常或框架产生 HTTP 错误
- **THEN** 响应使用目录中安全默认消息，不暴露异常文本、凭据或堆栈

#### Scenario: 请求验证失败
- **WHEN** 请求字段或嵌套数组成员验证失败
- **THEN** details 包含对应字段 path 与验证 type，保留来源和数组索引，不包含 input 或 ctx

### Requirement: 请求标识端到端一致
服务器 MUST 透传合法 X-Request-ID，缺失或非法时生成有效标识；成功和失败响应的 meta.requestId MUST 与 X-Request-ID 响应头一致。

#### Scenario: 透传与生成
- **WHEN** 请求分别携带合法、空白、超长或缺失标识
- **THEN** 合法值原样透传，其余生成新标识，异常路径也遵守同一规则

### Requirement: 机器合同先于 endpoint
packages/api-contracts MUST 成为 response、错误、OpenAPI path 和 SSE 的单一事实来源；当前只登记 foundation/health，后续提案 MUST 先增加合同再增加 endpoint。

#### Scenario: 检测跨语言或 path 漂移
- **WHEN** 应用增加未登记路径、私有响应或修改生成声明
- **THEN** 合同检查失败，必须先修正合同与实现一致性
