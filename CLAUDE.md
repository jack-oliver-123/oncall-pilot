# Agent skills

## 快速检查

从仓库根目录执行：

- `openspec list --json`：列出 active Change。
- `openspec status --change <id> --json`：查看指定 Change 的 artifact 状态。
- `openspec instructions <artifact> --change <id> --json`：读取实际 artifact 路径和写作约束。

## 仓库地图

- `openspec/`：正式 Change、main specs 和 OpenSpec 配置。
- `CONTEXT.md`、`docs/adr/`：稳定领域词汇和已接受架构决策。
- `docs/agents/`：Issue、triage、领域文档和组合工作流规范。
- `.claude/commands/opsx/`：推荐的 OpenSpec 命令层入口。
- `frontend/`、`backend/`：模块边界；进入目录后继续遵守其嵌套 `CLAUDE.md`。

## Issue tracker

本仓库使用 GitHub Issues，技能通过 `gh` CLI 读写。详见 `docs/agents/issue-tracker.md`。

## Triage labels

使用默认的五个 triage labels：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

## Domain docs

本仓库使用 single-context 布局：根级 `CONTEXT.md` 和 `docs/adr/`。详见 `docs/agents/domain.md`。

## Combined workflow

OpenSpec 是正式 Change 的控制平面；Matt Pocock Skills 是按问题类型插入的方法层，不得维护平行规格或静默覆盖已确认 artifact。涉及行为、接口、跨文件或设计权衡的工作必须建立 Change；实现、验证和归档遵守阶段门禁。完整规则、入口映射和冲突处理见 `docs/agents/combined-workflow.md`。
