## MODIFIED Requirements

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

## ADDED Requirements

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
