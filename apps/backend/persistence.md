# 持久化边界

`oncall_pilot.memory` 只导出数据库无关契约和不可变 record。SQLite 实现放在 `oncall_pilot.memory.sqlite`。本项目不提供旧 `super_ai` namespace，也不预建没有实际需求的 `extended_sqlite` 或领域 CRUD。

## 显式初始化与事务

先按 [迁移指南](migrations/README.md) 对目标数据库执行显式迁移，然后由组合层使用下面的调用方式。示例中的 `config_dir` 必须由 app factory、lifespan 或依赖 provider 注入；不要在 module scope 执行。

```python
from pathlib import Path

from oncall_pilot.memory import Repository, SchemaRevision
from oncall_pilot.memory.sqlite import SQLiteRepository, open_database


async def read_revision(repository: Repository) -> SchemaRevision:
    return await repository.schema_revision()


async def run(config_dir: Path) -> SchemaRevision:
    async with open_database(config_dir) as database:
        async with database.transaction() as session:
            return await read_revision(SQLiteRepository(session))
```

领域函数只接收 Repository，不接收 ORM model、engine 或 session。未来 PostgreSQL adapter 实现相同领域 Protocol，在组合层替换；本次只实现 schema revision contract，不声称覆盖未来领域权限、查询或 CRUD。

`open_database` 读取 `project.json` 与可选 `user.project.json` 的深合并结果。`database.url` 必须是 `sqlite+aiosqlite:///...` 文件 URL；相对数据库路径以配置目录的父目录解析，与进程 cwd 无关。支持绝对路径、空格与百分号文件名，不支持内存数据库、SQLite URI/query 模式或其他驱动。没有环境变量覆盖入口。

初始化只建立 engine/session factory 和所需父目录，首次连接才创建数据库文件；不会自动迁移或建表。未迁移数据库调用 `schema_revision()` 抛出 `SchemaNotInitialized`。当前 FastAPI app factory 和 `/health` 不初始化数据库；未来领域 Change 可在 lifespan 中持有该上下文。

每个 `transaction()` 创建独立 async session，正常退出提交，异常或取消退出回滚并关闭。多个 Repository 通过同一个 session 组成原子工作单元；adapter 不调用 commit，不把 session 传入领域。不跨协程共享 session，不在事务中等待网络或 LLM。SQLite 同时只有一个 writer，忙等待上限 5 秒；NullPool 每次归还即关闭连接，不承诺无界并发吞吐。所有在途事务结束后再关闭 Database，关闭后拒绝新事务。

## 字段和 schema 约定

- `new_id()` 显式生成标准 UUID4 字符串；未来主键建议长度 36。ID 与时间在创建 record 时生成，禁止用 import 时求值作为默认参数。
- `utc_now()` / `as_utc()` 使用 aware datetime。ORM 层 `UTCDateTime` 存储无时区 UTC，读取恢复 UTC aware datetime，拒绝 naive datetime，保留微秒。
- SQLAlchemy `JSON` 字段统一经过 engine 的 serializer/deserializer，保留标准 JSON 值语义和中文；拒绝 NaN/Infinity、非字符串 key、tuple 与自定义对象。JSON 值按整值替换写入；不要依赖 ORM 自动发现嵌套原地修改。record 含集合时需在 adapter 边界转为深度不可变结构。
- 需要查询、关联、唯一约束或状态流转的数据必须使用规范化列和表。JSON 仅承载不参与这些操作的有限附加属性；不建立通用大 JSON 业务状态表。
- 未来 ORM model 继承 `sqlite.base.Base`，约束使用统一命名；CHECK 约束必须显式命名。新 model 要加入迁移 metadata 的显式导入，再生成、审查并测试 revision。
- tenant-scoped Repository 必须显式传入 tenant ID，并测试过滤，不使用默认或全局 tenant。

## 测试

`tests/migration_helpers.py` 提供临时 JSON 配置与显式 Alembic 命令 helper；`migrated_config` / `database` fixture 使用每个测试独立的 `tmp_path`。禁止引用开发者真实配置或 `var/memory.sqlite3`。测试 fixture 会关闭资源，临时文件由 pytest 管理。

迁移测试在原始空数据库比较 `Base.metadata`，另用未迁移表探针确认比较器能发现漂移。事务/字段测试的表只在测试内创建，不进入生产 metadata。基础 revision 无业务表是范围限制，不代表已完成后续领域 schema 验收。
