## 1. 验收合同

- [x] 1.1 添加 Compose 白名单、版本、依赖、持久卷/healthcheck 和废资产黑名单测试，先确认失败。
- [x] 1.2 添加 fake client 与生命周期、schema/index、tenant escaping、跨用户、无 I/O 拒绝和配置/import-safety 测试，先确认失败。

## 2. 基础设施与向量 adapter

- [x] 2.1 实现五服务 Compose、只读 Alertmanager 配置和本地运行指南。
- [x] 2.2 实现 merged vectorStore 配置、官方 SDK seam、惰性 connect/health 和幂等 initialize，将 pymilvus 提升为运行依赖。
- [x] 2.3 实现验证后的 insert、授权 KB search 与三维 delete-document，复用 P05 归属合同。
- [x] 2.4 更新持久化文档，添加仅 loopback、独立 collection 的可选真实 smoke。

## 3. 验证与归档

- [x] 3.1 运行 backend lint/typecheck/test、tooling tests、docker compose config、依赖锁检查、openspec validate --all --strict 和 git diff --check，修复问题。
- [x] 3.2 检查本机 Milvus 可用性，有服务时运行 smoke；如实区分 fake、结构检查和 live evidence。
- [x] 3.3 使用 openspec-verify-change 完整映射任务/需求/场景/设计，记录 verification.md 并完成 WIKI 同步与构建。
- [x] 3.4 准备同步与归档：核对全部 delta/main spec 差异、CLI 返回路径、目标目录和后置验证命令。

上述实现与验证清单通过后，按用户授权同步全部 delta specs、逐项比较并归档，再验证 WIKI/规格/补丁状态，结果记录在 verification.md。归档动作不作为自己的前置 checkbox，避免循环依赖。
