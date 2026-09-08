## MODIFIED Requirements

### Requirement: 数据迁移只在显式命令期间运行
foundation SHALL 提供异步迁移环境和基础 revision，MUST 不创建业务模型；只有显式迁移命令 MAY 改变 schema，数据库资源 MUST 仅在 lifespan、依赖 provider 或显式初始化路径创建。安装与导入 MUST 不创建数据库或自动执行迁移。

#### Scenario: 安装和导入不会创建数据库
- **WHEN** 开发者同步依赖、运行静态检查或导入后端包
- **THEN** `apps/backend/var` 中不会因此出现 SQLite 文件

#### Scenario: 显式升级基础数据库
- **WHEN** 开发者指定本地配置目录并执行迁移至 head
- **THEN** 数据库记录基础 revision 且没有提前创建领域业务表
