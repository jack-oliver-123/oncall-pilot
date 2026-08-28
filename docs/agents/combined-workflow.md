# OpenSpec 与 Matt Skills 组合工作流

本文件是本项目组合规则的规范来源。它描述两套能力如何协作，不复制任一上游 Skill 的正文。

## 1. 两层职责

### OpenSpec：变更控制平面

OpenSpec 独占以下职责：

- 管理 Change 生命周期和 active Change 选择。
- 持久化并维护 `proposal`、`specs`、`design`、`tasks` 等 artifact 依赖。
- 作为已确认目标、需求、设计、任务和验证状态的正式事实源。
- 授权实现、执行 artifact 一致性验证和归档。

推荐用户入口为 `/opsx:*` 命令层；对应的 `openspec-*` 是能力层入口。两者读取同一个 `openspec/` 状态，不是两套生命周期。

### Matt Pocock Skills：工程方法层

Matt Skills 按问题类型提供辅助方法：

| 问题 | 推荐入口 | 作用 |
| --- | --- | --- |
| 范围、目标或方案争议 | `mattpocock-skills:grilling` | 压力测试想法和决策 |
| 需要外部事实 | `mattpocock-skills:research` | 写入带来源的研究 Markdown；调用前确认目标路径 |
| 术语、领域边界或关系含糊 | `mattpocock-skills:domain-modeling` | 可能更新 `CONTEXT.md`/ADR；调用前确认文档副作用 |
| 模块、接口、seam 或架构取舍不清 | `mattpocock-skills:codebase-design` | 评估设计边界和杠杆点；默认先读 |
| 关键行为无法通过讨论确定 | `mattpocock-skills:prototype` | 创建 throwaway prototype，可能需要独立分支/commit；先确认范围 |
| 需要行为回归保护 | `mattpocock-skills:tdd` | 在既定 task 内执行 red-green-refactor，可能修改代码/测试 |
| 难复现 bug 或性能回归 | `mattpocock-skills:diagnosing-bugs` | 建立可变红的紧反馈回路并诊断，按实现授权执行 |
| 实现完成后的独立质量检查 | `mattpocock-skills:code-review` | 只读检查标准、回归风险和规格符合性 |

仓库级 wrapper `grill-with-docs` 只在同时需要方案压力测试和可能形成跨 Change 稳定术语时使用；否则分别调用 namespaced 的 `grilling` 或 `domain-modeling`，不要让 wrapper 和底层 Skill 重复级联。该 wrapper 没有 `mattpocock-skills:` 命名空间入口。

Matt Skills 可以发现问题、提出候选结论或进行独立检查，但不拥有 Change 状态，不得创建平行计划或静默覆盖 OpenSpec artifact。调用前必须声明该方法的副作用类别（只读、项目文档、实现、外部跟踪或 commit）和目标；只读不等于无副作用，具体 Skill 的行为以其当前正文为准。

## 2. 是否创建 Change

必须建立 Change 的工作包括：

- 改变系统行为或接口；
- 涉及多个文件；
- 需要设计权衡、架构决定或可追踪验收契约。

单文件、纯机械、无行为变化且无需设计权衡的操作可以不创建 Change，但不得声称已通过 OpenSpec 门禁。用户要求跳过也不能把符合上述边界的工作伪装成已批准 Change。

当存在 active Change 时，按目标、capability 和验收边界匹配请求。无法唯一匹配时暂停并让用户选择现有 Change 或创建新 Change，禁止按最近修改时间猜测，也禁止跨 Change 自动合并。

## 3. 默认工作流

```text
问题/请求
  -> 判断 Change 边界
  -> 读取 CONTEXT.md、相关 ADR、当前 OpenSpec 状态
  -> 按问题类型和副作用分类插入 Matt 方法
  -> 范围确认
  -> OpenSpec proposal/specs/design/tasks
  -> 实现授权
  -> openspec-apply-change + 按需 tdd/diagnosing-bugs
  -> openspec-verify-change + 必要的 code-review
  -> 归档确认
  -> openspec-archive-change
```

需求明确且探索结论已确认时，可以使用 `/opsx:propose` 或 `/opsx:ff` 快速生成完整 artifact；需求仍有争议时使用 `/opsx:new` → `/opsx:continue` 逐步暴露假设。快速生成不跳过范围确认或实现授权。

## 4. 产物唯一归宿

| 结论 | 正式归宿 |
| --- | --- |
| 目标、范围、非目标、为什么做 | `proposal.md` |
| 可观察行为、输入输出和边界场景 | `specs/<capability>/spec.md` |
| 技术方案、模块边界、研究约束、原型结论 | `design.md` |
| 可执行实现切片和测试任务 | `tasks.md` |
| 跨 Change 稳定词汇 | 根级 `CONTEXT.md` |
| 难逆转、令人意外且有真实取舍的决定 | `docs/adr/*.md` |
| 组合规则和运行时映射 | 本文件 |
| 组合规则回归记录 | `combined-workflow-scenarios.md` |

探索过程、被否决方案和未核实信息不应直接成为正式契约。外部事实如果影响设计或验收，必须附来源和日期；未核实内容只能标为假设。

## 5. 三个阶段门禁

### 5.1 范围冻结

只读探索完成后，展示目标、范围、非目标和需要写入的 OpenSpec artifact。只有用户明确确认范围，才能创建或更新正式 artifact。

### 5.2 实现授权

proposal、specs、design、tasks 完整后，展示实现契约快照和任务范围。只有用户明确确认“可以开始实现”，才能执行 `openspec-apply-change` 或修改实现文件。

### 5.3 验证后归档

实现完成后，必须展示验证结果。只有 OpenSpec verify 通过、必要的独立 code review 通过、任务/需求场景/设计/代码一致，并且用户明确确认归档，才能执行 archive。

每次确认只绑定当时展示的内容快照。目标、artifact、任务或验证结果发生变化时，原确认自动失效，必须重新展示并确认。沉默不是授权。

## 6. 冲突与副作用协议

### 已确认 artifact 与 Matt 建议冲突

以已确认的 OpenSpec artifact 为当前契约。报告冲突并暂停受影响工作；使用 `/opsx:update` 或 `openspec-update-change` 更新受影响 artifact，重新取得实现授权后才继续。不得由后调用者覆盖先调用者。

### 重叠入口被直接调用

允许用户显式调用底层入口，但先说明边界：

- active Change 的实现以 `openspec-apply-change` 为主，`implement` 不并行接管；
- OpenSpec `proposal/specs/design/tasks` 是正式规格，`to-spec` 不得在 active Change 中另建平行 Issue 规格；
- `openspec-verify-change` 检查 artifact 与实现的一致性，Matt `code-review` 检查代码标准和回归风险，两者互补，不能互相替代；
- GitHub Issue 只承担需求入口、讨论和状态跟踪，除非用户明确要求，否则不把它当作第二份实现契约。

不自动合并直接调用的结果，不自动把建议写回 artifact。

### 副作用分级

- 只读探索可以按矩阵自动建议或执行。
- `CONTEXT.md`、ADR、组合规范等项目文档写入必须在对应范围确认后执行；`research`、`domain-modeling` 和 `grill-with-docs` 不得被当作天然只读。
- `prototype` 可能创建 throwaway 代码并要求 commit；必须先展示目标路径、分支和副作用，取得对应确认后执行。
- OpenSpec artifact 写入必须经过范围确认，并且实际输出路径必须以 `openspec status --json` / `openspec instructions --json` 返回的 `artifactPaths`、`contextFiles` 为准，不得假设 schema 固定文件名。
- 代码、Issue、commit 和 archive 必须经过对应实现授权或归档确认。`to-spec` 会发布 GitHub Issue 并添加 triage label；必须单独展示 body、目标仓库、label 和副作用，取得发布确认，且它不会成为 OpenSpec artifact。
- 组合 Skill 本身不发布 Issue、不提交、不归档，也不自动管理批准状态。

### 辅助 Skill 失败

失败、中断或没有可信结论的辅助 Skill 不等于成功。保留当前 OpenSpec 状态，报告缺口；由用户决定重试、使用替代方法、把结论明确降级为假设，或终止。依赖该结论的后续阶段不得自动推进；与后续无关的可选检查只有在明确记录后才可跳过。

### 实现事实推翻设计假设

暂停受影响 task，把发现记录为阻塞或变更提议；通过 `/opsx:update` 同步 proposal/specs/design/tasks，并重新取得实现授权。普通实现困难可以在当前 task 内调整，不应把每个困难都升级为范围变化。

### 目标变化与中断恢复

目标、范围或关键假设变化时先更新 Change，识别受影响 artifact 和任务，再重新确认。会话中断时以已落盘 artifact 为恢复点，不依赖隐式会话记忆；只有持久化目标已失效时才重新探索。

## 7. 运行时映射与重复副本

组合规则的规范来源是本文件；组合 Skill 中的摘要与本文件冲突时，以本文件为准并暂停报告，不自行合并。当前入口映射如下：

| 作用 | 位置/入口 | 说明 |
| --- | --- | --- |
| Claude Code Matt/组合 Skill | `.claude/skills/` | 当前主运行时入口 |
| Claude Code OpenSpec 命令 | `.claude/commands/opsx/` | `opsx:*` 命令层 |
| Claude Code OpenSpec Skill | `.claude/skills/openspec-*` | OpenSpec 能力层 |
| Codex 兼容 OpenSpec Skill | `.codex/skills/` | 兼容运行时入口 |
| 通用 Agent Matt 副本 | `.agents/skills/` | 兼容/共享入口 |

`.agents/skills` 与 `.claude/skills` 的 Matt 副本，以及 `.claude/skills` 与 `.codex/skills` 的 OpenSpec 副本，不代表独立能力。当前 Change 不删除、覆盖或自动同步它们；上游升级或入口变化后，执行受影响场景并报告漂移。副本清理或自动一致性检查必须另建 Change。

## 8. 规则变更与证据

组合层依赖上游公开职责和 OpenSpec artifact 契约，不依赖提示词细节。上游升级后重新检查入口、产物顺序、副作用和冲突矩阵。任何失败都记录为未通过，不静默降级。

规则自身的回归材料见 `docs/agents/combined-workflow-scenarios.md`。场景记录必须包含场景 ID、前置状态、输入、预期路由、禁止动作、确认点、实际结果、执行日期、运行时和 `pass`/`fail`/`not-run` 结论。
