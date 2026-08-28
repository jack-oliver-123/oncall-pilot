---
name: openspec-with-matt-skills
description: 当用户要组合或路由 OpenSpec Change 与 Matt Pocock Skills（例如 grilling proposal、研究 design、领域建模、prototype、TDD、诊断 bug 或 verify 后 code review）时使用；保持 OpenSpec 为控制平面，并为文档、代码、Issue、commit 和 archive 副作用设置门禁。
---

# OpenSpec 与 Matt Skills 组合路由

本 Skill 是交互式路由层，不替代 OpenSpec 或任何上游 Matt Pocock Skill。先读取 `docs/agents/combined-workflow.md`，再检查当前 OpenSpec 状态，然后才推荐或调用方法。该工作流文档是规范来源；若本文件摘要与其冲突，暂停并报告，不自行合并。

## 职责

- OpenSpec 是 Change 状态、已确认意图、artifact、实现授权、验证和归档的控制平面。
- Matt Pocock Skills 是探索、质询、研究、建模、原型、TDD、诊断和独立审查的方法层。
- 本 Skill 只负责在两层之间路由，不复制上游指令、不创建平行计划，也不维护批准状态。

## 路由步骤

1. 读取 `CLAUDE.md`、存在时的 `CONTEXT.md`、相关 `docs/adr/` 和 `docs/agents/combined-workflow.md`。
2. 检查 OpenSpec 状态。存在多个 active Change 时，按目标、capability 和验收边界匹配；无法唯一匹配时停止并让用户选择或创建 Change。
3. 判断请求是机械性操作还是需要 Change。行为、接口、跨文件或设计变化必须进入 OpenSpec Change。
4. 范围不确定时，先读取相关 Skill 的当前正文并声明副作用类别；只有确认为只读的方法才能在范围确认前运行。研究、领域建模、grill-with-docs、prototype 等可能写入文档、代码、分支或 commit，必须先展示目标和副作用并取得对应确认。
5. 将已确认结论按语义映射到唯一 OpenSpec artifact；实际写入路径必须以 `openspec status --change "<name>" --json` 和 `openspec instructions <artifact-id> --change "<name>" --json` 返回的 `artifactPaths`/`contextFiles` 为准，不假设 schema 固定文件名。
6. 遇到写入、外部副作用或下文阶段门禁时停止，说明授权对象并请求明确确认。

## 方法路由矩阵

- 范围、目标或方案存在争议 → `mattpocock-skills:grilling`
- 需要外部事实 → `mattpocock-skills:research`
- 术语、边界或关系含糊 → `mattpocock-skills:domain-modeling`
- 模块、接口、seam 或架构存在不确定性 → `mattpocock-skills:codebase-design`
- 关键行为无法通过讨论确定 → `mattpocock-skills:prototype`
- 行为实现需要回归保护 → 在 `openspec-apply-change` 内使用 `mattpocock-skills:tdd`
- bug 难以复现或出现性能回归 → `mattpocock-skills:diagnosing-bugs`
- 实现后需要独立质量检查 → 在 `openspec-verify-change` 后使用 `mattpocock-skills:code-review`
- 同时需要方案压力测试和可能跨 Change 稳定的术语 → 仓库级 wrapper `grill-with-docs`；它没有 `mattpocock-skills:` 命名空间入口，同一目的下不得再调用其底层方法。

按问题选择方法，不要把一个 Matt Skill 机械绑定到每个 OpenSpec 阶段。

## OpenSpec 入口规则

- 假设或范围仍在逐步暴露时，优先使用 `/opsx:new` → `/opsx:continue`。
- 范围和探索结论已确认时，才使用 `/opsx:propose` 或 `/opsx:ff`。
- active Change 的实现只由 `/opsx:apply` / `openspec-apply-change` 接管，不并行运行 `implement`。
- 使用 `/opsx:verify` / `openspec-verify-change` 检查 artifact 与实现的完整性、正确性和一致性。
- `mattpocock-skills:code-review` 只补充代码标准和回归审查，不替代 OpenSpec 验证。
- 目标、范围、假设或已确认建议变化时，使用 `/opsx:update` / `openspec-update-change`。
- 只有验证通过且用户明确确认归档后，才使用 `/opsx:archive` / `openspec-archive-change`。
- `to-spec` 是外部 Issue 发布入口，不是只读材料整理。它会发布 Issue 并添加 triage label；执行前必须展示拟发布 body、目标仓库、label 和副作用，取得单独发布确认。即使发布，也不会成为 OpenSpec artifact，active Change 中不得由它创建平行可执行规格。

## Artifact 语义映射

以下是 `spec-driven` 的语义默认值，不是跨 schema 的物理路径承诺：

- 范围、目标和非目标 → proposal artifact
- 可观察行为和边界场景 → specs artifact
- 技术方案、研究约束和原型结论 → design artifact
- 可执行实现切片和测试工作 → tasks artifact
- 跨 Change 稳定词汇 → 根级 `CONTEXT.md`
- 难逆转且存在真实取舍的决定 → `docs/adr/*.md`

对于 OpenSpec artifact，始终以当前 Change 的 `openspec status --json` 返回的 `artifactPaths`，以及 `openspec instructions --json` 返回的 `contextFiles`/`resolvedOutputPath` 为实际归宿；不要把默认文件名当成 schema 不变的路径。探索笔记和被否决方案不会自动成为正式需求。影响设计或验收的外部事实需要来源和日期；未核实信息仍是明确标注的假设。

## 停止条件与冲突处理

- 已确认的 OpenSpec artifact 是当前契约。Matt 建议与其冲突时，报告冲突并停止；通过 `/opsx:update` 更新 artifact 并重新取得实现授权后再继续。
- 辅助 Skill 失败、中断或没有可信结论不等于成功。保留 Change，报告证据缺口，由用户选择重试、替代方法、明确假设或终止。
- 不把新请求静默并入 active Change。无法证明验收边界相同时，先询问归属。
- 实现事实推翻设计假设时，暂停受影响 tasks 并更新 Change；普通实现困难可以留在当前 task 内处理。
- 发现重复运行时副本或命名冲突时，报告映射或漂移，不删除、覆盖或同步上游副本。
- 用户可以显式调用重叠 Skill，但调用前说明职责重叠、副作用和推荐的 OpenSpec 替代入口；不得自动合并其输出。

## 副作用门禁

只读探索可以按路由矩阵执行。以下操作必须受门禁约束：

1. **范围冻结**：展示范围快照，等待明确确认后才创建或更新正式 artifact。
2. **实现授权**：展示完整 artifact/task 快照，等待明确确认后才修改实现文件。
3. **归档确认**：展示 `tasks.md` 完成状态、OpenSpec verify 结果、独立审查结果和 artifact-to-code coherence，等待明确确认后才归档。

项目文档写入、OpenSpec artifact 写入、代码修改、Issue 发布、commit 和归档，不会因为上一阶段或同名请求曾获批准而自动获得授权。快照变化会使原确认失效。

## 输出要求

每次路由都应说明：

- 选中的 Change，或为什么需要新建 Change；
- 使用的 Matt 方法（如有）及其适用原因；
- OpenSpec 入口和 artifact 归宿；
- 将停止推进的副作用或门禁；
- 冲突、失败证据或未解决歧义。

只有对应 OpenSpec 操作和确认真实发生后，才能声称 Change 已实现、已验证或可以归档。
