## Context

参见 proposal.md。P01 已锁定 SQLAlchemy、aiosqlite 和 Alembic，配置入口为 `load_project_config(config_dir)`。现有迁移环境没有 metadata 或 revision，且手工拼接 URL。P02 已固定健康检查合同，本次无需 endpoint 或 SSE 变更。

## Goals / Non-Goals

**Goals:** 用显式资源所有权提供可复用的事务与迁移基座，通过真实临时 SQLite 证明替换契约与隔离。

**Non-Goals:** 不预建认证、Chat 等领域 CRUD、ORM model、通用键值业务表、默认 tenant、PostgreSQL adapter、运行时自动迁移或应用启动数据库探测。不创建 `extended_sqlite` 空模块；实际 SQLite 实现收敛于 `oncall_pilot.memory.sqlite`。

## Decisions

1. `memory.contracts` 提供 `Repository` Protocol 与 frozen `SchemaRevision` record；唯一已有真实需求是读取已迁移数据库的 revision。SQLite adapter 与测试 fake 执行相同 contract。后续领域按自己的用例扩展 Protocol，不提前构造泛型 CRUD 框架。领域只持有 Repository，session 只由组合层与 adapter 接收。
2. `memory.sqlite` 提供显式 `open_database(config_dir)`、可关闭的 `Database` 与事务 async context manager。使用 `async_sessionmaker(expire_on_commit=False)`，每次事务新建 session，正常提交、异常/取消回滚。使用 NullPool，避免跨 event loop 复用连接，关闭成本可控。调用方负责跨 Repository 原子事务；adapter 只查询或 flush，不 commit。
3. 以 `make_url` 解析并校验 `sqlite+aiosqlite` 本地文件 URL；相对路径以配置目录父目录解析，支持绝对路径、空格和百分号文件名。拒绝内存数据库、URI/query 模式及非 SQLite URL，保证 NullPool 下每个 session 使用相同持久文件且不误连外部数据库。配置解析保持纯函数，只有显式 engine factory 创建父目录。连接统一 foreign_keys=ON、busy_timeout=5000，并关闭 sqlite3 legacy transaction control，由 SQLAlchemy begin 事件显式 BEGIN，以保证事务内 DDL/savepoint 行为。
4. `memory.sqlite.base.Base` 提供稳定约束命名；当前 metadata 无业务表。首个空基础 revision 建立 Alembic 版本链，唯一新增表为 Alembic 自身的版本表。不添加无用 foundation 业务表来凑迁移。Alembic 使用同一 URL/engine 配置，offline 只生成 SQL，不建目录或文件；runtime 不调用 create_all 或迁移。提供 script.py.mako 支持后续显式生成 revision。
5. JSON serializer 严格接受 JSON 值并拒绝 NaN/Infinity、非字符串 key 及自定义对象；UTC TypeDecorator 将 aware datetime 归一为无时区 UTC 存储，读取恢复 UTC aware datetime，拒绝 naive 输入；ID 使用显式 `uuid4`，不在 import 生成。约定未来关系、查询、状态字段规范化；JSON 仅用于无需关联查询的有限附加属性。基础 record 只含不可变标量。
6. 测试 fixture 使用 pytest tmp_path，helper 显式执行 Alembic。事务/字段测试表仅在测试中通过 DDL 建立，不注册到生产 Base；迁移一致性在原始 fresh database 上用 autogenerate compare_metadata 检查。import safety 在独立进程阻断资源创建、配置读取和连接。
7. 保持现有 app factory 和 `/health` 无数据库依赖；选用用户允许的“显式初始化路径”，后续领域 Change 在 lifespan/provider 中拥有并注入 Database。与现在就启动数据库相比，这避免 P03 给无持久化 endpoint 的进程增加不必要依赖。

## Risks / Trade-offs

- SQLite 同时只有一个 writer → 独立短事务、busy_timeout；不声称支持无界写并发，不在事务中等待 LLM/网络。
- NullPool 每次打开连接存在成本 → 当前侧重隔离和资源可控，后续有性能证据时再调整池策略。
- 首个迁移无业务 DDL → 通过版本链、空 metadata 比较及后续 autogenerate 探针证明迁移入口有效，业务 schema 由未来 Change 增量添加。
- 基础 record 不能证明未来领域权限过滤 → 本次 contract 仅覆盖 schema revision；后续 tenant interface 必须显式 tenant ID 并独立验收。

## Migration Plan

在显式临时 JSON 配置目录执行 `alembic -c alembic.ini -x config-dir=<path> upgrade head`。验证重复升级、downgrade base 和再次升级，并检查 `alembic check`。上线操作不在本次范围；基础 downgrade 只移除版本标记，不删除业务表。后续 revision 必须独立声明回滚风险。
