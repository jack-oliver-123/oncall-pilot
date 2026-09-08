## 1. 持久化边界

- [x] 1.1 建立 Repository Protocol、不可变基础 record、JSON/UTC/ID 约定及字段测试。
- [x] 1.2 建立 Base、配置注入、async engine/session factory、事务和关闭路径及配置测试。

## 2. 迁移与契约

- [x] 2.1 接入 Alembic metadata 和共享 engine，增加首个 revision、revision 模板及临时 migration helper。
- [x] 2.2 验证 fresh/repeat upgrade、downgrade/re-upgrade、metadata 一致及漂移探针、offline 不创建数据库。
- [x] 2.3 验证并发 session、异常/取消回滚、外键、测试数据库隔离和资源关闭。
- [x] 2.4 以 SQLite/fake 运行 Repository contract，验证未迁移失败与全部 module import safety。

## 3. 文档与验收

- [x] 3.1 编写后端持久化与迁移指南，同步 active WIKI 并验证文档构建。
- [x] 3.2 执行显式 alembic upgrade head、pytest、Ruff、strict Pyright、openspec validate --all --strict、git diff --check 和 WIKI 测试，完成三维验证报告。
