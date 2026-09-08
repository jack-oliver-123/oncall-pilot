## Context

见 proposal.md。现有合同生成器从 OpenAPI 生成 Pydantic 和 TypeScript 声明，前端通用 transport 已支持 bearer。P03 提供 Database.transaction、UTCDateTime、UUID 和 Base.metadata，运行时不自动迁移。当前没有 tenant 或业务表。

## Goals / Non-Goals

**Goals:** 将 HTTP 与领域服务、事务及 SQLite adapter 分开；以真实临时 SQLite 和公开接口证明安全行为。保留 P02 的单一合同与 P03 的显式资源生命周期。

**Non-Goals:** 不引入 JWT、cookies、自动过期、权限系统、tenant 默认值或 P08 页面。

## Decisions

- 注册返回 UserResponse（id/email/createdAt），登录返回 LoginResponse（user/token/tokenType=Bearer），me 返回 UserResponse，logout 返回 data=null，沿用现有成功状态 200。输入邮箱为常见非空 local@domain 格式、首尾空白允许，规范化 strip().casefold() 后限长 254；密码 8–128 字符、不裁剪。合同约束用生成器可验证的 pattern 表达。
- users 使用 UUID 主键、规范邮箱唯一、password_hash 和 UTC created_at；auth_sessions 使用 UUID、user_id 外键、token_hash 唯一且约束 64 位小写十六进制，以及 created_at/last_seen_at/revoked_at。显式 0002 migration，不通过 create_all 建表。记录使用 frozen dataclass，秘密字段不参与 repr。
- 登录使用 secrets.token_urlsafe(32)，只将 SHA-256 hex digest 交给 Repository。PasswordManager 在显式初始化时创建 pwdlib 推荐 Argon2 hasher 和 dummy hash；hash/verify 在工作线程运行，避免阻塞 event loop。查询邮箱事务先结束，再执行昂贵校验，再用独立短事务写会话，避免 SQLite 读升级锁冲突。唯一约束冲突只将邮箱重复转换为业务错误。
- AuthService 接收 AuthTransactions 和 PasswordManager；组合层注入只返回 AuthRepositoryPort 的事务上下文，领域服务不接触 Database、ORM session 或 SQLite adapter。Repository 提供明确的邮箱登录查找、token hash 身份解析和带 owner ID 的会话读取/touch/revoke；owner 来自服务端记录，客户端无 owner 输入。touch/revoke 使用未撤销条件，避免并发撤销后恢复。无 token 明文 Repository 参数。
- FastAPI lifespan 管理数据库和密码服务，测试显式进入 lifespan；/health 本身不读数据库。dependency 用 HTTPBearer(auto_error=False) 接收 bearer 并统一抛出 AUTH_UNAUTHENTICATED。所有认证响应禁止缓存；安全错误无 input/SQL 参数日志。
- authClient 复用通用 transport，认证 state 通过注入 Storage、客户端和清理回调创建 Vue reactive 只读状态。仅 token 存入固定 key；initialize 不信任缓存身份；401 清理，网络/5xx 保留 token 但清除身份并报告失败。操作序号与发起时 token 防止旧响应覆盖新身份，logout 先清理本地再尝试撤销捕获的 token。受保护业务未来使用 state 提供的带 401 清理能力的 API client。
- 测试切片依次覆盖合同、migration/Repository、HTTP 服务、前端状态，每个切片先确认失败再实现。数据库检查是用户明确要求的秘密不落盘安全验收；不使用计时阈值证明 dummy 校验，改在密码验证边界记录调用并实际执行 Argon2。

## 归档门禁修正

P02/P03 与 P04 的 created 和 archive 日期均为 2026-09-08。原 WIKI 校验按目录名折叠，add-user-authentication 会排到基础 Change 前面。同步器仅对同一日期、同一 requirement 且仅含 ADDED/MODIFIED 的组先折叠 ADDED 再折叠 MODIFIED；涉及 REMOVED（含重命名源）的组保留原顺序，避免删除后重新添加被颠倒；日期和同类操作目录顺序保持确定，不影响导航。WIKI 新规则采用独立 ADDED requirement，保留 P02 已有 requirement，避免将新增关注点误写为并列 MODIFIED。回归同时验证新版本通过、旧版本仍拒绝和幂等性，不使用 allow-unsynced。

## Risks / Trade-offs

- localStorage token 可被同源脚本读取 → 按本次约束只存 token，页面安全需后续继续维护。
- 无自动过期意味着会话持续有效 → 文档明确仅支持主动撤销，不返回 expiresAt。
- 登出网络失败不能保证服务端撤销 → 本地始终清理并抛出失败供调用方呈现。
- Argon2 有 CPU/内存成本 → 使用推荐参数和工作线程；限流与滥用防护不纳入本次功能。

## Migration Plan

开发者显式运行 Alembic upgrade head 后启动应用；验收仅用临时配置。降级到 0001 会删除认证表及账户会话，仅用于临时数据库往返测试，实际回滚需要另行评估数据保留。本任务不对本机或生产数据执行迁移。

## 依赖依据

2026-09-08 核对 pwdlib 官方指南：https://frankie567.github.io/pwdlib/guide/ 。使用 PasswordHash.recommended()、hash()、verify()，未知账号校验使用同类 dummy hash。
