## 1. 配置边界

- [x] 1.1 先增加配置安全失败测试，再完善 P01 loader 与 LLM typed validation，覆盖深合并、缺失字段和环境隔离
- [x] 1.2 补齐脱敏模板和模板回归测试，从模板安全补齐 ignored 本机配置

## 2. 模型边界

- [x] 2.1 先验证 chat 请求，建立 LlmProvider、可注入 Qwen provider、显式 factory 和必要运行依赖
- [x] 2.2 先验证超过 10 条原文输入，再实现 embedding 分批、顺序及无效响应检查
- [x] 2.3 先验证 rerank payload，再实现独立 HTTP client、真实分数、timeout 与有界 retry
- [x] 2.4 实现并测试三类 readiness、全边界错误脱敏、环境回退隔离、import-safety 和资源释放

## 3. 验证与交付

- [x] 3.1 编写中文使用文档与显式手动 smoke，分别记录 fake/local/live 证据
- [x] 3.2 运行 backend lint/typecheck/test、contracts check/typecheck/test、WIKI tests/build、openspec validate --all --strict 和 git diff --check，修复失败并完成 verify 报告
- [x] 3.3 同步全部 delta specs 并逐项核对，完成归档前的 artifact、任务及 WIKI 一致性检查

任务完成且 verify 通过后，按用户授权执行 archive 生命周期操作；归档后重建 WIKI、运行 docs:build、openspec validate --all --strict、git diff --check，并在 verification.md 记录最终状态。
