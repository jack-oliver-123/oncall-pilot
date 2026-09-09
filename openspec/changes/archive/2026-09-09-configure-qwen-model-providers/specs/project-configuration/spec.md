## ADDED Requirements

### Requirement: 最终配置模板覆盖模型和后续基础设施
脱敏模板 SHALL 包含 app、backend、frontend、database、llm、modelCapabilities、vectorStore、mcp、clsMcpServer、prometheusAlerts、clsLogUpload、aiopsDemo；aiopsDemo MUST 至少包含 backendBaseUrl、email、displayName、password、pollIntervalSeconds、indexWaitSeconds。password、secret、apiKey MUST 为空且实际凭据只填 ignored user config；后续 section 仅作为配置骨架，不初始化对应服务。

#### Scenario: 安全初始化本机配置
- **WHEN** 从模板准备本机配置
- **THEN** 缺失文件复制模板，已有值保留并补齐缺失模板字段，project.json 与 user.project.json 均保持 ignored，测试只使用临时目录

### Requirement: 模型配置必须显式验证
LLM 配置消费方 MUST 验证 llm 三类模型 section 和所选 modelCapabilities，拒绝缺失字段、无效 URL、非正超时、负重试、非法温度、非法向量参数和缺失 profile；空 apiKey 模板可加载但创建生产 provider 前 MUST 失败。普通 loader SHALL 在存在 llm 时验证其结构，无 llm 的基础配置仍可用于现有非模型功能。

#### Scenario: 合并后验证且不读取环境变量
- **WHEN** 用户覆盖一个嵌套 LLM 字段，OS 环境中同时存在其他模型配置
- **THEN** 验证深合并结果并仅使用 JSON 中的配置，错误只暴露安全字段位置和原因而不回显输入值

## MODIFIED Requirements

### Requirement: 配置错误必须快速失败
缺失必需项目配置、无效 JSON、不可读或非 UTF-8 文件、非对象根节点 MUST 在应用启动或前端构建阶段产生明确失败；缺失用户配置 SHALL 等同空对象。后端错误 MUST 使用固定文件名与原因，不包含配置内容、底层异常或敏感路径，不通过异常链泄密。

#### Scenario: 缺失用户配置
- **WHEN** 本地只存在有效 project.json
- **THEN** 后端启动和前端构建继续使用项目配置

#### Scenario: 项目配置无效
- **WHEN** 必需项目配置缺失、无法解析或根节点不是对象
- **THEN** 消费方在启动或构建完成前失败并指出原因

#### Scenario: 配置异常不回显秘密
- **WHEN** 无效配置内容或所在目录含 apiKey
- **THEN** 后端公开错误与格式化 traceback 均不包含该秘密
