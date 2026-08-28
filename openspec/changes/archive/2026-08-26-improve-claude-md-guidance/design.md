## Context

参见 `proposal.md` 的动机。三个目标文件采用层级继承：根级 `CLAUDE.md` 提供仓库通用入口，目录级文件只补充各模块约束。当前前后端目录均没有应用 manifest、源码入口或可验证命令，因此设计必须记录已知事实，不能预先选择技术栈。

## Goals / Non-Goals

**Goals:**

- 让 Agent 从根规则直接获得已验证的 OpenSpec 检查入口和主要规则位置。
- 让进入前后端目录的 Agent 明确区分“尚未配置”与“需要自行猜测”。
- 保持每条信息只有一个详细事实源，避免把组合工作流全文复制进 `CLAUDE.md`。

**Non-Goals:**

- 不建立前端或后端工具链。
- 不修复或记录 `wiki-sync` 工作流。
- 不修改用户全局行为偏好或现有 OpenSpec main specs。

## Decisions

### 使用最小增量而非重写规则文件

在根文件现有标题后插入“快速检查”和“仓库地图”，在两个目录文件的简介后插入“当前工具链”。保留其余内容和结构，避免审计改进意外改变既有治理规则。

备选方案是按通用模板重写三个文件；这会复制大量已有规则并扩大审查面，因此不采用。

### 只记录已实际验证的命令

根文件只加入逐条通过本地 CLI 验证的命令：使用 `openspec list --json` 枚举 active Change，使用 `openspec status --change <id> --json` 查看指定 Change 状态，使用 `openspec instructions <artifact> --change <id> --json` 读取 artifact 指令。前后端不提供占位命令，而是要求首次引入真实工具链的 Change 同步更新说明。

备选方案是写入常见的 npm、Python 或容器命令；当前仓库没有相应 manifest，写入后会形成不可执行或误导性指导，因此不采用。

### 用路径索引连接规范而不复制规范

仓库地图仅说明 `openspec/`、`CONTEXT.md`、`docs/adr/`、`docs/agents/`、`.claude/commands/opsx/`、`frontend/` 和 `backend/` 的职责。组合规则仍以 `docs/agents/combined-workflow.md` 为详细规范来源。

备选方案是把阶段门禁和冲突协议复制到根文件；副本会增加漂移风险，因此不采用。

## Risks / Trade-offs

- [前后端初始化后“当前尚无工具链”可能过期] → 将同步更新准确命令和入口明确列为首次初始化 Change 的要求。
- [根文件加入仓库地图后略微增长] → 只列跨会话稳定且高价值的入口，不列具体实现文件。
- [OpenSpec CLI 后续版本可能调整参数] → 当前命令已经在 `1.7.0` 验证；未来升级时按实际 CLI 更新，而不添加未验证兜底。

## Migration Plan

1. 对三个文件执行精确增量插入。
2. 重新读取变更 diff，确认仅包含批准内容且 Markdown 结构正确。
3. 分别执行 `openspec list --json`、`openspec status --change improve-claude-md-guidance --json` 和 `openspec instructions proposal --change improve-claude-md-guidance --json`，确认文档中的三类命令均成功。
4. 运行 `openspec validate improve-claude-md-guidance` 验证 Change。
5. 若需回滚，仅撤销三个插入区块；不影响任何应用或数据。
