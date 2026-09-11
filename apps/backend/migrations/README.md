# 数据迁移

Alembic 是 schema 唯一权威。基础 revision 为 0001_persistence_foundation，只建立版本链。0002_user_authentication 增加认证表；当前 head 0003_background_jobs 增加后台任务与事件表。运行时不调用 create_all 或自动迁移。

从 apps/backend 显式传入本地配置目录：

```powershell
uv run alembic -c alembic.ini -x config-dir=../../config upgrade head
uv run alembic -c alembic.ini -x config-dir=../../config current
uv run alembic -c alembic.ini -x config-dir=../../config check
```

以上命令会连接指定配置中的数据库，仅在你明确准备操作该数据库时执行。自动化验收使用 tests/migration_helpers.py 生成的临时配置，不使用开发者配置。配置 URL、相对路径和资源约定见 [持久化指南](../persistence.md)。

仅生成 SQL，不创建数据库文件或父目录：

```powershell
uv run alembic -c alembic.ini -x config-dir=../../config upgrade head --sql
```

后续领域 Change 添加继承 Base 的 model，并在 env.py 引入其 metadata 声明后，生成候选 revision：

```powershell
uv run alembic -c alembic.ini -x config-dir=../../config revision --autogenerate -m "领域变更说明"
```

必须人工审查生成的 DDL、规范化列、索引、外键、自定义类型 import 及 downgrade，再对临时 fresh/已有版本数据库验证升级。SQLite 使用 batch 迁移；foreign_keys=ON 时重建被引用表需要在该领域 Change 中明确设计迁移顺序，不假设所有生成结果可直接执行。

基础 revision 可用 downgrade base 撤销版本标记后重新 upgrade head；它没有业务 DDL。后续 revision 不继承无损回滚保证。

2026-09-08 核对的官方依据：[SQLAlchemy SQLite 事务控制](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl)、[Alembic async 迁移](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)。运行时与迁移共用显式 BEGIN 策略；Alembic 通过 async connection 的 run_sync 执行迁移。


P09 在首次运行新 worker 前要求显式 upgrade head。0003 的任务/事件 owner 复合外键与 sequence 唯一约束必须保留；`check` 同时对比业务 metadata。降级到 0002 会删除任务与事件，应先停止 worker 并备份需保留的数据。验收覆盖临时数据库升级、重复升级、check、降级与再次升级，不操作本机开发或生产数据。
