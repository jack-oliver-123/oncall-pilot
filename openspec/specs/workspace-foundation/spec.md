# workspace-foundation Specification

## Purpose

为 On-call Pilot 提供唯一、可发现且可验证的仓库骨架与 workspace 关系，使后续产品 Change 在同一命名、目录、契约和进程边界上演进。

## Requirements

### Requirement: 仓库采用最终顶层骨架
仓库 MUST 将应用、共享契约、配置、基础设施说明、脚本、规格和文档分别置于约定顶层目录，并 MUST 移除被新应用目录取代的旧根级前后端目录。

#### Scenario: 检查干净克隆的目录
- **WHEN** 维护者检查仓库顶层目录
- **THEN** 仓库包含 `apps/backend`、`apps/frontend`、`packages/api-contracts`、`config`、`infra`、`scripts`、`openspec` 和 `docs`
- **THEN** 根级 `backend` 和 `frontend` 不再存在

### Requirement: 项目统一使用 On-call Pilot 命名
面向人员的名称 SHALL 使用 On-call Pilot；代码标识 MUST 使用各语言中合法且可追溯到该名称的形式，不得继续暴露 Super AI 或 `super_ai`。

#### Scenario: 检查项目入口和包
- **WHEN** 维护者检查 README、前端标题、npm workspace 和 Python 导入包
- **THEN** 所有名称均与 On-call Pilot 一致
- **THEN** Python 导入使用 `oncall_pilot`

### Requirement: workspace 依赖方向保持单向
前端应用 MAY 依赖共享 API contracts；API contracts MUST 独立于前后端应用；后端 MUST 不依赖 npm workspace，前后端 MUST 不通过文件系统导入彼此源码。

#### Scenario: 验证 workspace 依赖图
- **WHEN** 自动化测试检查 manifests 与源码导入
- **THEN** 仅允许前端指向 API contracts 的应用级 workspace 依赖
- **THEN** 跨前后端交互只能使用可观察的 HTTP 契约

### Requirement: API contracts 提供最小 typed entrypoint
API contracts workspace SHALL 暴露可被前端消费的 typed entrypoint，并 SHALL 为 foundation 健康响应提供最小类型契约和独立的 typecheck/test 命令。

#### Scenario: 消费健康响应契约
- **WHEN** 前端或 contracts 测试从包入口导入健康响应类型
- **THEN** 导入无需访问前端或后端源码即可成功
- **THEN** 类型约束与后端 `/health` 的可观察响应一致

### Requirement: 应用进程与基础设施进程分离
后端、前端和官方 CLS MCP Server MUST 作为主机进程运行；未来 Compose 范围 MUST 只包含 etcd、MinIO、Milvus、Attu 和 Alertmanager。

#### Scenario: 检查 foundation 基础设施内容
- **WHEN** 维护者检查 `infra` 与仓库容器文件
- **THEN** 只能看到进程归属与未来基础设施范围说明
- **THEN** 不存在应用 Dockerfile、`project.compose.json` 或应用 Compose 服务

### Requirement: 不引入历史重写方案
从零建立的项目骨架 MUST 通过正常文件变更演进，不得把 filter-repo、force push 或历史重写作为迁移或安全步骤。

#### Scenario: 审查迁移说明和任务
- **WHEN** 维护者搜索 foundation 文档与自动化脚本
- **THEN** 不存在要求重写 Git 历史的步骤
