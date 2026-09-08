## Purpose

为不具备技术背景的值班人员提供清晰、诚实且可访问的 On-call Pilot 桌面 Web 入口，同时为后续产品界面建立稳定的构建和验证基线。

## ADDED Requirements

### Requirement: 前端提供诚实的最小值班工作台
前端 SHALL 显示 On-call Pilot 品牌、值班工作台语境和当前尚未开放业务操作的清晰状态，不得展示虚构数据、无效按钮、假导航或未实现能力。

#### Scenario: 首次打开 foundation 页面
- **WHEN** 值班人员在受支持的桌面浏览器打开应用
- **THEN** 能立即识别这是 On-call Pilot 值班工作台
- **THEN** 能理解当前没有可执行的业务操作，而不会误认为页面加载失败

### Requirement: 页面语言面向非技术值班人员
界面文案 MUST 使用简体中文和用户可识别的值班语言，不得要求用户理解日志、容器、数据库、模型、MCP 或构建配置。

#### Scenario: 检查首屏文案
- **WHEN** 非技术值班人员阅读首屏
- **THEN** 文案只描述其所处工作区和当前可操作状态
- **THEN** 首屏不暴露实现术语或开发说明

### Requirement: 桌面布局保持单一滚动上下文
前端 SHALL 以桌面 Web 为验收目标，在支持的桌面视口中保持内容完整、无重叠，并 MUST 不产生页面与内部容器两个独立滚动条。

#### Scenario: 验证桌面视口
- **WHEN** 浏览器在典型 Windows 桌面视口渲染 foundation 页面
- **THEN** 所有文案和品牌元素均可见且不重叠
- **THEN** 页面最多存在一个滚动容器

### Requirement: 基础可访问性从首日生效
前端 MUST 提供语义化结构、可见键盘焦点和足够颜色对比，并 MUST 在用户请求 reduced motion 时禁用非必要动画。

#### Scenario: 使用键盘和 reduced motion
- **WHEN** 用户仅使用键盘并启用 reduced motion 浏览页面
- **THEN** 页面结构可被顺序理解且焦点始终可见
- **THEN** 不播放非必要过渡动画

### Requirement: 浏览器只消费公开配置 interface
前端应用源码 SHALL 只通过 typed public-config interface 获取允许公开的配置，不得直接导入完整项目配置或用户配置 JSON。

#### Scenario: 检查前端配置导入
- **WHEN** 自动化测试检查前端源码依赖
- **THEN** 只存在对 public-config interface 的消费
- **THEN** 不存在对两份完整本地 JSON 的直接导入

### Requirement: 前端提供独立质量命令
前端 workspace SHALL 提供开发、lint、format check、typecheck、test 和生产构建命令，且这些命令 MUST 能由根 workspace 统一调用。

#### Scenario: 从根目录验证前端
- **WHEN** 开发者运行根级前端质量命令
- **THEN** lint、格式检查、严格类型检查、测试和生产构建均在前端 workspace 上执行
