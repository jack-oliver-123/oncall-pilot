# backend-foundation Specification

## Purpose

为 On-call Pilot 提供可安装、可启动且 import-safe 的最小后端应用，使后续业务模块能够在明确的配置、依赖注入和异步持久化边界上扩展。

## Requirements

### Requirement: 后端包采用合法且唯一的导入命名
后端 SHALL 以 src layout 提供 `oncall_pilot` 包，项目源码和测试 MUST 使用 `from oncall_pilot...`，不得从 `src.oncall_pilot` 或 `super_ai` 导入。

#### Scenario: 安装后导入后端包
- **WHEN** 开发者完成后端依赖同步并从后端 workspace 外导入包
- **THEN** `oncall_pilot` 可被正常解析
- **THEN** 禁止的导入形式会被自动化检查识别

### Requirement: module import 不产生 I/O 副作用
导入任何 `oncall_pilot` module MUST 不主动读取项目配置或执行应用级文件 I/O，也 MUST 不连接 SQLite、Milvus、LLM 或 MCP。Python 导入机制读取模块文件本身不属于应用副作用。

#### Scenario: 在阻断外部副作用时导入全部 module
- **WHEN** 测试监控项目配置加载、应用级文件 I/O、数据库连接、网络连接和外部客户端初始化后导入全部后端 module
- **THEN** 所有导入成功且没有触发任何受监控的应用副作用

### Requirement: 后端提供显式 app factory
后端 SHALL 通过 app factory 创建应用，并 SHALL 允许测试显式注入临时配置目录；配置错误 MUST 在 factory 调用期间清晰失败。

#### Scenario: 使用临时配置创建应用
- **WHEN** 测试向 app factory 传入包含有效本地 JSON 的临时目录
- **THEN** 应用成功创建且不依赖开发者本机配置

#### Scenario: 使用无效配置创建应用
- **WHEN** app factory 收到缺失或无效的必需项目配置
- **THEN** 创建过程在启动前失败并指出配置问题

### Requirement: 后端提供依赖无关的健康检查
后端 SHALL 在 `/health` 提供进程存活检查，成功响应 MUST 为 HTTP 200 和 `{ok:true,data:{status:"ok"},meta:{requestId}}`，该检查 MUST 不探测数据库或外部服务。

#### Scenario: 调用健康检查
- **WHEN** 客户端向已创建的应用请求 `/health`
- **THEN** 返回 HTTP 200 和共享成功 envelope，其中 data 为 `{"status":"ok"}`
- **THEN** meta.requestId 与响应 X-Request-ID 一致
- **THEN** 请求过程中不连接 SQLite、Milvus、LLM 或 MCP

### Requirement: 后端提供主机启动 interface
后端 SHALL 提供可从主机运行的命令入口，显式接收配置目录、监听地址和端口；这些进程参数 MUST 不被当作项目配置从环境变量读取。

#### Scenario: 使用显式参数启动
- **WHEN** 开发者从仓库根运行后端开发命令
- **THEN** 入口使用仓库本地配置目录和显式 host/port 创建应用

### Requirement: 数据迁移只在显式命令期间运行
foundation SHALL 提供异步迁移环境和基础 revision，MUST 不创建业务模型；只有显式迁移命令 MAY 改变 schema，数据库资源 MUST 仅在 lifespan、依赖 provider 或显式初始化路径创建。安装与导入 MUST 不创建数据库或自动执行迁移。

#### Scenario: 安装和导入不会创建数据库
- **WHEN** 开发者同步依赖、运行静态检查或导入后端包
- **THEN** `apps/backend/var` 中不会因此出现 SQLite 文件

#### Scenario: 显式升级基础数据库
- **WHEN** 开发者指定本地配置目录并执行迁移至 head
- **THEN** 数据库记录基础 revision 且没有提前创建领域业务表
