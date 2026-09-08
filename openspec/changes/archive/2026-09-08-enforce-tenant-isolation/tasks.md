## 1. 合同与生成

- [x] 1.1 增加 OpenAPI 受保护操作模板、共享 401/403 和公开例外，生成跨语言声明并测试漂移拒绝。

## 2. 强制归属边界

- [x] 2.1 实现 CurrentUser/OwnerScope、认证 dependency、受保护 router 与安全资源缺失转换。
- [x] 2.2 实现 SQLite scope helper，统一认证 Repository 的 owner_user_id 参数与创建归属校验。
- [x] 2.3 实现向量 metadata、搜索/删除 filter 和空 KB 延迟召回短路，验证过滤执行次序。

## 3. 隔离验收

- [x] 3.1 增加可复用参数级失败检查、两个用户的 SQLite 读取/列表/更新/删除/创建/父子关系与 SQL 条件测试。
- [x] 3.2 增加真实认证加本地 HTTP 探针合同测试，覆盖不可枚举 403、401、伪造 scope、并发身份和登出持久数据保留。
- [x] 3.3 增加前端双用户切换、迟到响应和 403 状态回归，验证清理边界。

## 4. 文档与验证

- [x] 4.1 更新 AGENTS、持久化架构与 contracts 接入文档，覆盖全部资源和后台工作。
- [x] 4.2 同步 WIKI，运行 backend/contracts/frontend、生成物、tooling、docs、OpenSpec 和 git diff 门禁，修复所有发现。
- [x] 4.3 按 verify 的完整性、正确性、一致性记录逐需求场景证据，确认实现可进入主规格同步与归档。
