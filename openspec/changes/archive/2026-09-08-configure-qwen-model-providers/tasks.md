## 1. 配置基础

- [x] 1.1 完善 P01 文件错误、LLM typed validation 与能力 profile，覆盖深合并及缺失/非法字段。
- [x] 1.2 补齐安全模板，从模板创建缺失的 ignored 本机配置并验证 ignore。

## 2. 模型边界

- [x] 2.1 提升实际使用依赖并实现可注入 Protocol、chat/embedding adapter、显式 factory 与资源关闭。
- [x] 2.2 实现独立 rerank HTTP payload、结果校验、timeout/retry 与无 fallback 行为。
- [x] 2.3 实现三类最小 readiness 与所有 API key 脱敏，覆盖失败和取消。

## 3. 验证与交付

- [x] 3.1 用 fake adapter/transport 覆盖参数、多批次顺序、非法响应、环境隔离、import-safety 和生命周期。
- [x] 3.2 记录真实凭据手动 smoke 步骤和未运行状态，执行 backend 全门禁、contracts 检查、OpenSpec validate 与 git diff --check。
- [x] 3.3 完成 OpenSpec verify 的完整性、正确性、一致性核对并记录验证报告，准备同步 specs 与归档。
