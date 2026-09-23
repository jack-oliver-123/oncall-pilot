## MODIFIED Requirements

### Requirement: 桌面工作台结构
工作台 MUST 提供左侧导航、仅 Chat 可用的会话区域插槽、账号与退出、标题及服务状态；业务路由画布 MUST 铺满剩余可用空间，不被统一卡片或最大宽度限制。Chat、AIOps、MCP 等尚未开放业务 MUST 显示诚实占位，无虚构数据或操作；`/knowledge` MUST 显示真实知识库工作区并复用受保护工作台壳。

#### Scenario: 切换预留业务路由
- **WHEN** 用户依次打开四个受保护路由
- **THEN** 导航和标题同步，仅 Chat 显示会话区域，知识库显示真实文档管理工作区，其他未开放页明确表示业务尚未开放

#### Scenario: 桌面布局与服务状态
- **WHEN** 在 1440×900、1280×720 桌面渲染，或 `/health` 请求成功、失败
- **THEN** 布局完整无横向溢出且最多一个滚动容器，服务状态用文字表达检查中、进程可连接或无法连接，不声称外部依赖可用

### Requirement: 受保护状态生命周期
应用 MUST 提供可登记及注销的受保护 store 清理机制与仅内存的 protectedData 状态。登出、401、账号切换 MUST 清除所有已登记数据，旧请求 MUST 无法重新写回新身份数据；不得使用 localStorage 保存 chat、knowledge、AIOps 领域数据。knowledge store MUST 登记清理回调。

#### Scenario: 多 store 清理
- **WHEN** 多个 store 登记清理，随后登出或当前请求返回 401
- **THEN** 所有已登记 store 清空，已注销回调不执行，清理不删除服务端业务数据

### Requirement: 共享可访问交互状态
应用 MUST 提供 AppLoadingState、AppEmptyState、AppErrorState、AppFeedback、AsyncStatusBadge，状态用文字与 ARIA 表达；错误可提供真实重试操作。全局反馈 MUST 支持 success、info、error，手动关闭与 3 秒自动消失，新消息重置 timer，组件卸载清理 timer。知识工作区的上传 policy、覆盖确认、删除确认、详情展开和任务状态 MUST 复用可访问文字和键盘焦点。

#### Scenario: 辅助技术与键盘
- **WHEN** 检查知识工作区的加载、错误、空列表、确认、删除确认、详情展开和任务 status，使用键盘或 reduced motion
- **THEN** 状态有可读文字与正确 live/alert 语义，图标不重复朗读，焦点清晰且非必要动画禁用
#### Scenario: 反馈生命周期
- **WHEN** 连续发布消息、手动关闭或卸载反馈组件
- **THEN** 只显示最新消息并从新消息起计时 3 秒；关闭后不残留消息，卸载后无 timer
