## 1. 共享合同切片

- [x] 1.1 先写认证 DTO、path、安全和错误验收并确认失败
- [x] 1.2 扩展唯一 OpenAPI 合同并生成 Python/TypeScript 声明，通过合同测试

## 2. 认证持久化切片

- [x] 2.1 先写认证迁移、约束、owner 隔离和事务回滚验收并确认失败
- [x] 2.2 实现 users/auth_sessions migration、不可变记录和 owner-safe Repository，通过对应验收

## 3. 认证 HTTP 切片

- [x] 3.1 先写注册、重复邮箱、登录、dummy 校验、秘密不落盘、lastSeen、撤销、me、错误及 CORS 验收并确认失败
- [x] 3.2 实现 pwdlib 密码边界、AuthService、FastAPI dependency 和资源生命周期，通过对应验收

## 4. 前端状态切片

- [x] 4.1 先写 authClient/auth state 恢复、最小存储、清理、网络失败和竞态验收并确认失败
- [x] 4.2 实现可复用认证客户端、只读状态与受保护 store 清理，通过对应验收

## 5. 验证与交付

- [x] 5.1 运行 backend/contracts/frontend 全部门禁、生成漂移、路径和跨语言合同检查
- [x] 5.2 核对任务、需求场景与设计一致性，修复全部 CRITICAL 并记录验证结果
- [x] 5.3 运行 openspec validate --all --strict、git diff --check 和 WIKI 同步构建，达到归档条件

- [x] 5.4 以失败回归修复同日创建和归档的 WIKI 规格折叠顺序，保留未同步拒绝与幂等校验
