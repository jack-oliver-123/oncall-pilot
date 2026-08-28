## Why

当前项目级 Agent 说明准确记录了治理规则，但缺少可直接执行的 OpenSpec 状态检查入口；前后端目录也没有明确声明尚未初始化工具链，后续会话可能臆测命令或技术栈。需要把已验证的操作入口和当前模块状态写入对应 `CLAUDE.md`，提高规则的可执行性并降低错误假设。

## What Changes

- 在根级 `CLAUDE.md` 增加已验证的 OpenSpec 快速检查命令和最小仓库地图。
- 在 `frontend/CLAUDE.md` 明确当前没有前端 manifest、源码入口或可执行命令，不得推断框架、包管理器或运行时。
- 在 `backend/CLAUDE.md` 明确当前没有后端 manifest、源码入口或可执行命令，不得推断语言、框架、数据库或运行时。
- 要求首次初始化前端或后端工具链时，同步补充准确命令和入口文件。
- 不修改用户全局 `CLAUDE.md`，不处理 `wiki-sync` 的路径或依赖问题。

## Capabilities

### New Capabilities

无。本次是 Agent 项目文档的可操作性改进，不引入系统可观察行为，Change 已设置 `skip_specs: true`。

### Modified Capabilities

无。

## Impact

- 受影响文件：根级 `CLAUDE.md`、`frontend/CLAUDE.md`、`backend/CLAUDE.md`。
- 不影响应用代码、API、依赖、OpenSpec main specs 或外部系统。
