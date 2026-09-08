## Purpose

为 On-call Pilot 建立唯一的本地 JSON 项目配置来源、确定性的用户覆盖语义和浏览器公开投影，防止凭据进入版本库或前端产物。

## ADDED Requirements

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
缺失必需项目配置、无效 JSON 或非对象根节点 MUST 在应用启动或前端构建阶段产生明确失败；缺失用户配置 SHALL 等同空对象。

#### Scenario: 缺失用户配置
- **WHEN** 本地只存在有效 `project.json`
- **THEN** 后端启动和前端构建继续使用项目配置

#### Scenario: 项目配置无效
- **WHEN** 必需项目配置缺失、无法解析或根节点不是对象
- **THEN** 消费方在启动或构建完成前失败并指出原因

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
