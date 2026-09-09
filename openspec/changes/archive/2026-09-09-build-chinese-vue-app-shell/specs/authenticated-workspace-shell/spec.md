## Purpose

为中文值班人员提供依赖真实认证服务的桌面工作台入口，以明确的路由保护、账号数据清理和共享交互状态承载后续真实功能，同时清晰表达尚未开放的业务范围，避免把占位页面误认为已交付业务。

## ADDED Requirements

### Requirement: 路由与首次身份恢复
应用 MUST 将 /login、/register 标记为仅未登录可用，将 /chat、/knowledge、/aiops、/mcp 放入受保护工作台；/ 与未知路径 MUST 重定向 /chat。首次导航 MUST 只启动一次身份初始化，后续导航复用结果。

#### Scenario: 未认证访问受保护链接
- **WHEN** 未登录访问 /knowledge?tab=recent
- **THEN** 转至登录页并保留完整内部 redirect，登录成功返回原位置

#### Scenario: 已认证与兜底路径
- **WHEN** 已认证访问登录、注册、根路径或未知路径
- **THEN** 最终进入 /chat，不出现登录页或无限重定向

#### Scenario: 刷新恢复与失败
- **WHEN** 带 token 刷新页面，或恢复遇到 401、网络失败
- **THEN** 有效身份通过 /auth/me 恢复；401 清理身份；网络失败显示可重试错误且不渲染受保护内容

### Requirement: 真实认证表单
登录和注册 MUST 调用共享合同的真实 API，提供字段标签、校验、提交中和错误文字；注册成功 MUST 返回登录而不隐式登录。redirect MUST 仅接受应用内受保护路由。

#### Scenario: 注册后登录
- **WHEN** 用户注册成功并使用相同凭据登录
- **THEN** 注册后提示成功并返回登录，登录后进入工作台；密码不被持久化

#### Scenario: 错误与重复提交
- **WHEN** 表单不合法、凭据错误或请求未完成
- **THEN** 显示可访问的明确错误，提交中禁止重复提交，失败不显示成功反馈

### Requirement: 桌面工作台结构
工作台 MUST 提供左侧导航、仅 Chat 可用的会话区域插槽、账号与退出、标题及服务状态；业务路由画布 MUST 铺满剩余可用空间，不被统一卡片或最大宽度限制。尚未开放业务 MUST 显示诚实占位，无虚构数据或操作。

#### Scenario: 切换预留业务路由
- **WHEN** 用户依次打开四个受保护路由
- **THEN** 导航和标题同步，仅 Chat 显示会话区域，各页明确表示业务尚未开放

#### Scenario: 桌面布局与服务状态
- **WHEN** 在 1440×900、1280×720 桌面渲染，或 /health 请求成功、失败
- **THEN** 布局完整无横向溢出且最多一个滚动容器，服务状态用文字表达检查中、进程可连接或无法连接，不声称外部依赖可用

### Requirement: 受保护状态生命周期
应用 MUST 提供可登记及注销的受保护 store 清理机制与仅内存的 protectedData 状态。登出、401、账号切换 MUST 清除所有已登记数据，旧请求 MUST 无法重新写回新身份数据；不得使用 localStorage 保存 chat、knowledge、AIOps 领域数据。

#### Scenario: 多 store 清理
- **WHEN** 多个 store 登记清理，随后登出或当前请求返回 401
- **THEN** 所有已登记 store 清空，已注销回调不执行，清理不删除服务端业务数据

### Requirement: 共享可访问交互状态
应用 MUST 提供 AppLoadingState、AppEmptyState、AppErrorState、AppFeedback、AsyncStatusBadge，状态用文字与 ARIA 表达；错误可提供真实重试操作。全局反馈 MUST 支持 success、info、error，手动关闭与 3 秒自动消失，新消息重置 timer，组件卸载清理 timer。

#### Scenario: 反馈生命周期
- **WHEN** 连续发布消息、手动关闭或卸载反馈组件
- **THEN** 只显示最新消息并从新消息起计时 3 秒；关闭后不残留消息，卸载后无 timer

#### Scenario: 辅助技术与键盘
- **WHEN** 检查加载、空、错误和状态标签，使用键盘或 reduced motion
- **THEN** 状态有可读文字与正确 live/alert 语义，图标不重复朗读，焦点清晰且非必要动画禁用
