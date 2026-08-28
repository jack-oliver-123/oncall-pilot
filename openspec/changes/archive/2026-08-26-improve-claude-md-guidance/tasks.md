## 1. 更新项目级 Agent 指引

- [x] 1.1 将根级 `CLAUDE.md` 的 Change 列表命令修正为 `openspec list --json`，保留其余快速检查和仓库地图
- [x] 1.2 在 `frontend/CLAUDE.md` 插入当前工具链状态和首次初始化时的更新要求
- [x] 1.3 在 `backend/CLAUDE.md` 插入当前工具链状态和首次初始化时的更新要求

## 2. 验证改动

- [x] 2.1 检查 diff 仅包含三个已批准区块，且没有修改全局 `CLAUDE.md` 或 `wiki-sync`
- [x] 2.2 运行 `openspec validate improve-claude-md-guidance` 并记录验证结果
- [x] 2.3 分别执行三条文档命令，确认列表、状态和 artifact 指令均成功
