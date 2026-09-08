# On-call Pilot API contracts

此 workspace 是 HTTP response、错误目录、OpenAPI path 和 SSE event 的单一事实来源。源文件是 `openapi/foundation.openapi.json`（OpenAPI 3.1），当前只登记 foundation 的 `GET /health`。共享入口同时提供 `HealthResponse`、`ApiError`、`SseEvent`、operation 表和运行时 `parseContract`。

## 合同布局与扩展顺序

- `openapi/foundation.openapi.json`：唯一手写机器合同，`components.schemas` 包含公共 envelope、错误分支与八类 SSE。
- `src/generated.ts`：由合同生成的 TypeScript 声明、错误目录和 operation 表。
- 后端 `oncall_pilot/generated_contracts.py`：同一次生成产生的 Pydantic 声明与错误目录；后端运行时不读取合同文件、不导入 TypeScript。
- `fixtures/protocol.json`：两端共享的正向示例；独立 JSON Schema、Pydantic schema 比较及负向测试验证语义。

后续每个涉及 endpoint 的提案必须先声明新增 path、request/response schema、错误码及 SSE 扩展，再修改此合同并运行生成命令，最后实现 endpoint 和消费者。生成器只支持当前用到的 JSON Schema 子集，遇到未支持约束会失败；扩展语义需要同时补生成器与运行时校验测试。生成文件不得手改，不能用应用私有 event union、DTO 或事件字典绕过合同。静态边界检查识别直接声明/构造，运行时 serializer/parser 与 path/schema 合同测试继续约束动态输入。

当前成功响应为 `{ok:true,data,meta:{requestId}}`，失败响应为 `{ok:false,error:{code,category,httpStatus,message,details?},meta:{requestId}}`。`/health` 的 data 为 `{status:"ok"}`，只表示进程存活。四类错误前缀为 AUTH_*、BUSINESS_*、VALIDATION_*、SYSTEM_*；message 使用安全默认值，details 只能放明确允许公开的内容。

认证合同包含 `RegisterRequest`、`LoginRequest`、`AuthUser`、`LoginData`、`UserResponse`、`LoginResponse` 和 `LogoutResponse`。注册、登录为公开 POST，`/auth/me` GET 和 `/auth/logout` POST 使用 `BearerAuth` HTTP bearer scheme。登录返回 opaque token，无 expiresAt；公开用户仅有 id、email、createdAt。错误密码与未知账号复用 `AUTH_INVALID_CREDENTIALS`，重复邮箱使用 `BUSINESS_EMAIL_ALREADY_EXISTS`，失效会话复用 `AUTH_UNAUTHENTICATED`。合同验收比较实际请求、响应与 security，所有字符串正则采用 Unicode 字符语义。

SSE 包含 content.delta、reasoning.delta、tool.call、reference.source、task.status、report、complete、error，公共字段为 id/type/channel/timestamp。tool.call 按 started/delta/completed/failed 收窄；失败状态及 error 事件复用 ApiError。合同定义 payload 形状，后续业务负责同一 callId 的状态先后关系。

前端 `apiClient` 根据 operation 返回 typed data；`sseClient` 返回共享事件的异步迭代器。两者通过参数注入 fetch/request ID/bearer/signal，不读取本机秘密。网络异常和 ProtocolError 不伪装成 ApiClientError。SSE parser 支持 UTF-8 分块、三类换行与多行 data，EOF 不派发未结束 frame；单帧缓存上限为 1 MiB UTF-16 字符单位，不自动重连。当前尚无业务 SSE endpoint。

## 验证

从仓库根运行：

```powershell
npm run contracts:typecheck
npm run contracts:test
npm run contracts:generate
npm run contracts:check
npm run wiki:test
```

contracts 不依赖 frontend 或 backend，frontend 通过 npm workspace 单向依赖本包。
