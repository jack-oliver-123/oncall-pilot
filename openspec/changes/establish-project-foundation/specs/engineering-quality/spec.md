## Purpose

为 On-call Pilot 建立从本地到 Windows/Linux CI 一致的安装、检查和验收契约，使任何后续 Change 都能以单一命令面证明工程质量。

## ADDED Requirements

### Requirement: 依赖安装可由锁文件复现
仓库 SHALL 跟踪 npm 与 Python 锁文件，并 SHALL 提供从干净克隆安装全部 workspace 的明确命令；CI MUST 拒绝未同步的 manifest 与 lockfile。

#### Scenario: 从干净克隆安装
- **WHEN** 开发者按 README 运行根 npm 安装和后端 Python 同步
- **THEN** 所有 workspace 依赖成功解析并生成或使用受跟踪锁文件

#### Scenario: CI 使用冻结锁文件
- **WHEN** manifest 与 lockfile 不一致
- **THEN** CI 安装阶段失败而不是静默更新锁文件

### Requirement: 根目录提供统一质量命令面
根 workspace SHALL 提供后端、前端、API contracts、OpenSpec 和文档的独立命令，并 SHALL 提供一个跨平台总检查命令执行全部非交互式门禁。

#### Scenario: 运行根总检查
- **WHEN** 开发者从仓库根运行总检查命令
- **THEN** OpenSpec strict validation、后端 lint/typecheck/test、contracts typecheck/test、前端 lint/format/typecheck/test/build、WIKI 测试和文档构建全部执行
- **THEN** 任一子门禁失败都会使总命令失败

### Requirement: 后端质量配置严格且一致
后端检查 MUST 启用严格类型检查、自动 asyncio 测试模式以及已冻结的 lint 规则和语言基线，并 MUST 能独立运行 lint、typecheck 和 tests。

#### Scenario: 验证后端质量门禁
- **WHEN** 开发者在后端 workspace 运行规定的三个质量命令
- **THEN** lint 使用 100 字符行宽、Python 3.10 目标和 B/E/F/I/UP 规则
- **THEN** 类型检查以 strict 模式运行且异步测试无需逐个标记事件循环模式

### Requirement: CI 覆盖 Linux 与 Windows 主机
CI SHALL 在 Linux 上执行完整门禁并验证 Python 3.10 与 3.12；Windows SHALL 使用 Python 3.12 执行安装及后端、contracts、前端的关键 smoke gates；两者 MUST 使用 Node 22。

#### Scenario: 提交跨平台变更
- **WHEN** pull request 或受保护分支触发 CI
- **THEN** Linux 完整检查和 Windows smoke 检查均成功后才满足质量基线

### Requirement: 归档前执行完整验收
Change MUST 在 OpenSpec validation、所有 workspace 门禁、文档构建、秘密扫描和 `git diff --check` 全部通过后才具备归档条件；失败或未运行的门禁不得报告为通过。

#### Scenario: 存在失败门禁
- **WHEN** 任一要求的检查失败或未执行
- **THEN** 验证结果记录缺口且 Change 不得归档

### Requirement: 项目指南提供单一代理事实源
根 `AGENTS.md` SHALL 成为目录、命令、导入与依赖注入、配置与凭据、tenant、真实 MCP、OpenSpec 简体中文、桌面前端验收、分支命名和 UI PR 截图规则的唯一代理事实源；`CLAUDE.md` SHALL 只提供兼容指针。

#### Scenario: Agent 开始仓库工作
- **WHEN** Agent 从根或应用 workspace 开始任务
- **THEN** 能从 `AGENTS.md` 找到必需规则或准确的条件式文档指针
- **THEN** 不需要在 `CLAUDE.md` 中维护重复规则

### Requirement: 项目文档统一使用简体中文且如实描述能力
项目维护的文档、OpenSpec artifact、ADR、README、Issue/PR 文本和面向用户的文案 SHALL 使用简体中文，并 MUST 如实说明实际骨架、启动、验证和可用能力。代码标识、命令、路径、文件名、配置键、标准、协议、框架、库、产品专名、OpenSpec 结构关键字、日志与错误原文及必要引用 MAY 保留原文；生成文件、锁文件以及第三方或上游原文不要求机械翻译。

#### Scenario: 编写项目维护文档
- **WHEN** 维护者新增或更新项目文档、OpenSpec artifact、ADR、README、Issue/PR 文本或面向用户的文案
- **THEN** 叙述性内容使用简体中文
- **THEN** 保留原文的技术内容在需要处获得中文说明，且可执行内容和标准词义保持不变

#### Scenario: 阅读 foundation 文档
- **WHEN** 非项目作者按 README 检查可用能力
- **THEN** 能区分当前可运行骨架、未来技术约束和未实现产品范围
- **THEN** 文档不声称认证、聊天、知识库、AIOps、MCP 或其他未实现产品能力已经可用
