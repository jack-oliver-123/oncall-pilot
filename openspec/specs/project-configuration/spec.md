# project-configuration Specification

## Purpose

为 On-call Pilot 建立唯一的本地 JSON 项目配置来源、确定性的用户覆盖语义和浏览器公开投影，防止凭据进入版本库或前端产物。

## Requirements

### Requirement: 仓库只提交脱敏配置模板
仓库 SHALL 只跟踪 `config/project.template.json` 与 `config/user.project.template.json`；任何 key、secret 或 password 模板值 MUST 为空，本地实际配置、环境文件、数据库和日志 MUST 被忽略。

#### Scenario: 检查可提交配置
- **WHEN** 维护者检查 Git 跟踪文件和 ignore 规则
- **THEN** 本地 `project.json`、`user.project.json`、`.env*`、SQLite 和日志文件不会进入待提交集合
- **THEN** 模板中不存在非空凭据

### Requirement: 项目配置采用确定性递归深合并
配置加载器 SHALL 先读取必需的 `project.json`，再以可选的 `user.project.json` 覆盖；对象 MUST 递归合并，数组、标量和 `null` MUST 整体替换。

#### Scenario: 合并嵌套用户覆盖
- **WHEN** 用户配置只覆盖项目配置中的一个嵌套字段
- **THEN** 该字段使用用户值且未覆盖的同级项目字段保持不变

#### Scenario: 替换非对象值
- **WHEN** 用户配置为数组、标量或 `null` 提供覆盖值
- **THEN** 对应项目值被整体替换而不是逐项合并

### Requirement: 配置错误必须快速失败
缺失必需项目配置、无效 JSON、非法编码、不可读文件或非对象根节点 MUST 在应用启动或前端构建阶段产生明确失败；缺失用户配置 SHALL 等同空对象。后端错误 MUST 只指出配置文件名与安全原因，不回显配置内容、系统路径或原始异常链。

#### Scenario: 缺失用户配置
- **WHEN** 本地只存在有效 `project.json`
- **THEN** 后端启动和前端构建继续使用项目配置

#### Scenario: 项目配置无效
- **WHEN** 必需项目配置缺失、无法解析或根节点不是对象
- **THEN** 消费方在启动或构建完成前失败并指出原因

#### Scenario: 安全文件错误
- **WHEN** 后端加载含秘密的损坏 JSON、非法 UTF-8 或不可读路径
- **THEN** 错误提供文件名和安全原因，公开 traceback 不包含秘密和系统路径细节

### Requirement: 项目配置不使用操作系统环境变量
后端和前端构建 MUST 只消费本地 JSON 深合并结果作为项目配置；测试 MUST 通过显式临时目录注入配置，而不是依赖开发者真实值或环境变量。

#### Scenario: 隔离测试配置
- **WHEN** 测试在没有项目配置环境变量且本机配置内容未知的环境中运行
- **THEN** 测试只使用自己创建的临时 JSON 并产生确定结果

### Requirement: 浏览器公开投影采用明确 allowlist
浏览器 bundle SHALL 只接收 `frontend.title`、`frontend.apiBaseUrl` 和明确标记为 public 的 analytics key；其他字段无论名称或层级如何均 MUST 保留在 bundle 外。

#### Scenario: 构建公开配置
- **WHEN** 项目与用户配置包含公开字段以及 LLM、CLS、MCP、MinIO 或任意其他秘密字段
- **THEN** 前端运行时只能读取 allowlist 中的公开字段

### Requirement: 构建产物秘密扫描可证明隔离
自动化测试 MUST 使用带唯一 sentinel secret 的临时配置执行真实生产构建，并 MUST 扫描完整输出目录以证明 sentinel 不存在。

#### Scenario: 扫描生产 bundle
- **WHEN** 测试使用临时配置中的 sentinel secret 构建前端
- **THEN** 构建成功且输出目录任何文件中均不存在该 sentinel

### Requirement: 本机配置永不由测试改写或暂存
开发者 MAY 从模板复制 ignored 的本机配置用于启动和构建；自动化测试 MUST 不覆盖这些文件，且仓库命令 MUST 不将其加入 Git 暂存区。

#### Scenario: 在已有本机配置时运行测试
- **WHEN** workspace 已存在开发者的 ignored 本机配置
- **THEN** 测试结束后这些文件内容保持不变且仍未被跟踪

### Requirement: LLM 配置在深合并后按需 typed validation
loader SHALL 在存在 llm 时验证 provider、chat/embedding/rerank typed section 与 modelCapabilities；显式加载 provider 配置 MUST 要求这些 section。API key MUST 显式提供，模板空值可解析但 provider factory MUST 在创建 client 前拒绝空白值。URL MUST 是无用户信息、query 或 fragment 的 HTTP(S) URL。模型、数值和匹配 chat 的正整数 contextWindowTokens MUST 有效，验证错误 MUST 不回显输入。

#### Scenario: 合并并验证 LLM
- **WHEN** user 配置覆盖部分模型参数与凭据
- **THEN** 先递归合并再验证，保留同级默认值，凭据不出现在模型 repr 或错误中

#### Scenario: 缺失或非法字段
- **WHEN** LLM 缺失必需字段、profile 不匹配、timeout 非正数或 embedding 违反固定模型/维度/批次限制
- **THEN** provider 配置加载安全失败且不创建外部 client

#### Scenario: 兼容基础配置
- **WHEN** project 配置没有 llm section
- **THEN** 基础 loader 继续工作，但显式 provider 配置加载明确失败

### Requirement: 完整配置模板保留未来 section
模板 SHALL 包含 app/backend/frontend、llm、modelCapabilities、vectorStore、mcp、clsMcpServer、prometheusAlerts、clsLogUpload、aiopsDemo 及已有 database。aiopsDemo MUST 至少包含 backendBaseUrl/email/displayName/password/pollIntervalSeconds/indexWaitSeconds。所有 password/key/secret 凭据 MUST 为空且只在 ignored user config 填写；本机文件从模板复制且不得覆盖已有配置。

#### Scenario: 初次配置及凭据隔离
- **WHEN** 从模板初始化本机 project.json 和 user.project.json
- **THEN** 必需 section 存在、凭据为空、两个本机文件被 Git ignore，已有本机文件保持原值
