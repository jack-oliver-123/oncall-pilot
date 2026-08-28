# 组合工作流场景矩阵

本文件是手工回归材料，不是自动化测试。每个场景都区分预期行为与实际结果；`not-run` 不表示通过。执行记录应在规则、组合 Skill 或上游入口变化后更新，并在归档前处理失败项。

## 记录字段

- **场景 ID**：稳定标识。
- **前置状态**：active Change、artifact 和确认状态。
- **输入**：用户请求或直接入口。
- **预期路由**：应选择的 OpenSpec/Matt 入口。
- **禁止动作**：不能发生的副作用或越权。
- **确认点**：需要明确授权的位置。
- **实际结果**：执行时填写观察到的行为。
- **执行日期**：使用 `YYYY-MM-DD`。
- **运行时**：例如 `Claude Code` 或 `Codex`。
- **结论**：`pass`、`fail` 或 `not-run`。
- **原因/证据**：失败原因、跳过理由或可复核路径。

## 核心场景

### CWF-001：模糊想法先探索

- **前置状态**：无 active Change；用户只有模糊想法。
- **输入**：描述一个尚未明确范围的改进想法。
- **预期路由**：按问题类型建议 `grilling`、`research`、`domain-modeling`、`codebase-design` 或 `prototype`；必要时只读探索。
- **禁止动作**：未确认范围前不得创建或更新 OpenSpec artifact、代码或外部 Issue。
- **确认点**：范围冻结。
- **实际结果**：只读声明式演练确认：先按问题类型选择合适的 Matt 方法；范围未确认前不写 OpenSpec artifact、代码或 Issue，并在范围冻结处停止。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：组合 Skill 的路由步骤、方法副作用分类和范围冻结门禁；本次未创建额外 Change 或执行外部副作用。

### CWF-002：明确行为变更建立 Change

- **前置状态**：无 active Change；需求涉及行为或接口变化。
- **输入**：明确提出一项行为变更。
- **预期路由**：创建或选择 OpenSpec Change；按不确定性选择 `/opsx:new` → `/opsx:continue` 或 `/opsx:propose`/`/opsx:ff`。
- **禁止动作**：不直接调用 `implement` 修改代码，不创建平行传统 spec。
- **确认点**：范围确认后才写 artifact；完整 artifact 后再请求实现授权。
- **实际结果**：已通过本 Change 规划流程验证 OpenSpec artifact 创建路径；组合 Skill 只读演练确认明确行为变更应进入 OpenSpec，并按不确定性选择逐步或快速规划，不直接调用 `implement`。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：当前 Change 的真实 proposal/specs/design/tasks 创建记录，以及组合 Skill 的 Change 边界和入口规则；未直接修改业务代码。

### CWF-003：机械性小修可绕过 Change

- **前置状态**：无 active Change；请求无行为变化、无设计权衡。
- **输入**：格式化、拼写或明确机械性修正。
- **预期路由**：直接处理，不创建 Change。
- **禁止动作**：不得声称该操作已通过 OpenSpec Change 门禁。
- **确认点**：无 OpenSpec 实现授权；仍遵守普通文件修改授权。
- **实际结果**：只读声明式演练确认：单文件、纯机械、无行为变化且无需设计权衡的请求可以不创建 Change，但不得声称通过 OpenSpec 门禁；本次未执行实际机械修改。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：组合 Skill 与工作流规范的 Change 边界规则；本次未执行文件修改。

### CWF-004：多个 Change 无法唯一匹配

- **前置状态**：至少两个 active Change，目标或验收边界相近但不相同。
- **输入**：无法唯一归属的相关请求。
- **预期路由**：比较目标、capability 和验收边界；无法唯一匹配时询问用户选择或创建新 Change。
- **禁止动作**：不得按最近修改时间猜测或跨 Change 自动合并。
- **确认点**：Change 归属确认。
- **实际结果**：只读声明式演练确认：无法按目标、capability 和验收边界唯一匹配时，必须询问用户选择现有 Change 或创建新 Change；不会按最近修改时间猜测或跨 Change 合并。本次未构造第二个 active Change。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：组合 Skill 的 active Change 匹配和歧义停止规则；未创建隔离 Change 以避免污染仓库。

### CWF-005：Matt 建议与 artifact 冲突

- **前置状态**：active Change 的 artifact 已确认；方法层产生相反建议。
- **输入**：研究、建模或 code review 发现与 design/spec 不一致。
- **预期路由**：报告冲突并暂停；通过 `/opsx:update` 更新受影响 artifact，再重新取得实现授权。
- **禁止动作**：不得由后调用者静默覆盖已确认 artifact 或继续受影响实现。
- **确认点**：更新后的范围/方案和实现授权。
- **实际结果**：只读声明式演练确认：Matt 建议与确认 artifact 冲突时报告并暂停，使用 `/opsx:update` 更新受影响 artifact，再重新取得实现授权；不会静默覆盖或继续受影响实现。本次未注入真实冲突。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：组合 Skill 的冲突处理、artifact 更新和快照门禁规则；未修改当前正式 artifact。

### CWF-006：实现入口不被 implement 接管

- **前置状态**：active Change 的 tasks 已完成；尚未实现。
- **输入**：用户要求“开始实现”。
- **预期路由**：使用 `/opsx:apply` / `openspec-apply-change`；TDD 作为 task 内方法按需插入。
- **禁止动作**：不得并行启动 `implement` 或维护第二套任务状态。
- **确认点**：实现授权绑定当前 artifact/task 快照。
- **实际结果**：当前 Change 已按 `/openspec-apply-change` 路径进入实现；组合 Skill 只读演练确认 active Change 的实现唯一由该入口接管，TDD 只能作为 task 内方法，不并行运行 `implement`。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：本次实现实际使用 `openspec-apply-change`；组合 Skill 明确实现入口规则和禁止并行接管。

### CWF-007：辅助 Skill 失败不推进

- **前置状态**：探索或实现依赖 research、prototype、tdd 或 diagnosing-bugs 的结论。
- **输入**：辅助 Skill 失败、中断或无可信结论。
- **预期路由**：保留当前 Change，报告证据缺口，由用户选择重试、替代、明确假设或终止。
- **禁止动作**：不得把失败当成功或自动推进依赖该结论的阶段。
- **确认点**：选择恢复策略；若改变范围则重新确认。
- **实际结果**：只读声明式演练确认：保留当前 Change，报告证据缺口，并由用户选择重试、替代、明确假设或终止；不会把失败当成功或自动推进依赖阶段。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：`.claude/skills/openspec-with-matt-skills/SKILL.md` 的失败处理与副作用门禁规则；本次未触发真实失败或写入。

### CWF-008：验证区分 OpenSpec verify 与 code review

- **前置状态**：实现已完成，tasks 已更新。
- **输入**：用户要求检查是否完成。
- **预期路由**：先用 `/opsx:verify` 检查 artifact-to-code 完整性、正确性和一致性，再按需用 Matt `code-review` 检查标准和回归风险。
- **禁止动作**：不得用其中一个检查冒充另一个，也不得验证未通过就归档。
- **确认点**：验证结果和归档授权分别确认。
- **实际结果**：只读回归确认：OpenSpec 验证入口与 Matt `code-review` 入口职责分离；本次已执行 `openspec validate --strict`，并完成独立规则审查；没有把其中一个检查冒充另一个，也未执行归档。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：组合 Skill 的 verify/review 入口规则、`openspec validate` 通过结果和独立 Skill 审查记录。

### CWF-009：实现事实推翻设计

- **前置状态**：实现中发现现有代码或依赖行为推翻已确认假设。
- **输入**：实现或测试暴露设计/spec 假设不成立。
- **预期路由**：暂停受影响 task；用 `/opsx:update` 同步 artifact 和任务，再重新授权。
- **禁止动作**：不得只改 tasks、只在 review 备注或直接继续受影响实现。
- **确认点**：更新后的 artifact 和实现授权。
- **实际结果**：只读声明式演练确认：事实推翻设计时暂停受影响 task，使用 `/opsx:update` 同步受影响 artifact/task，并在新快照下重新取得实现授权；不会只改 tasks、只留 review 备注或继续旧实现。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：`.claude/skills/openspec-with-matt-skills/SKILL.md` 的冲突、更新和实现授权规则；本次未注入真实反事实。

### CWF-010：目标变化从 artifact 恢复

- **前置状态**：Change 已有部分 artifact；会话中断或目标发生变化。
- **输入**：继续工作或提出新目标。
- **预期路由**：读取已落盘 artifact；目标变化时先 update 并重新确认，不从隐式会话记忆继续。
- **禁止动作**：不得直接沿用旧 tasks 或自动新建平行 Change。
- **确认点**：更新后的范围和实现授权。
- **实际结果**：只读声明式演练确认：先读取落盘 OpenSpec 状态；目标变化走 `/opsx:update` 并重新确认，无法证明同一验收边界时先询问归属；不会依赖隐式会话记忆、沿用旧 tasks 或静默并入。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：`.claude/skills/openspec-with-matt-skills/SKILL.md` 的状态检查、Change 匹配、更新和快照门禁规则；本次未中断真实会话。

### CWF-011：重复副本只报告不清理

- **前置状态**：发现 `.agents`、`.claude` 或 `.codex` 中重复 Skill 或命名冲突。
- **输入**：用户要求组合或升级 Skill。
- **预期路由**：报告规范来源和运行时映射，执行受影响场景。
- **禁止动作**：本 Change 不删除、覆盖或自动同步上游副本。
- **确认点**：如需清理，另建 Change 后再授权。
- **实际结果**：已完成静态副本盘点；组合入口专项回归待执行。
- **执行日期**：2026-08-26（静态盘点）。
- **运行时**：Claude Code。
- **结论**：`not-run`。
- **原因/证据**：静态盘点不等同于组合入口行为验证。

### CWF-012：未确认不得归档

- **前置状态**：实现和验证结果已生成，但未收到归档确认。
- **输入**：用户询问是否可以结束 Change。
- **预期路由**：展示 tasks、verify、code review 和 coherence 结果，等待明确归档确认。
- **禁止动作**：不得把测试通过、沉默或“看起来完成”当作 archive 授权。
- **确认点**：验证后归档确认。
- **实际结果**：只读声明式演练确认：归档前必须展示 `tasks.md` 完成状态、OpenSpec verify、独立 code review 和 artifact-to-code coherence；即使全部通过也必须等待明确归档确认，不会把测试通过、沉默或“看起来完成”当作授权。
- **执行日期**：2026-08-26。
- **运行时**：Claude Code。
- **结论**：`pass`。
- **原因/证据**：`.claude/skills/openspec-with-matt-skills/SKILL.md` 的归档证据包和归档门禁规则；本次未执行实际归档。

## 变更记录

首次实现完成后，更新受影响场景的实际结果。若规则、组合 Skill 或上游入口发生变化，只重跑受影响场景并保留失败原因。
