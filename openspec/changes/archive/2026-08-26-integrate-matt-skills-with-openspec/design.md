## Context

本 Change 的动机和范围见 `proposal.md`，可验证行为见 `specs/combined-agent-workflow/spec.md`。当前仓库已同时存在 Claude Code、Codex 兼容目录和多个 OpenSpec/Matt 入口，但没有项目级组合契约；`openspec/config.yaml` 仅选择 `spec-driven` schema，且没有 active Change。

设计必须保持两个抽象层的差异：OpenSpec 管理 Change 的正式状态和 artifact 依赖；Matt Pocock Skills 提供可插入的工程方法。组合层只能适配二者，不能复制上游提示词或把方法建议提升为未经确认的正式意图。

## Goals / Non-Goals

**Goals:**

- 提供一个 Claude Code 下可调用的 `openspec-with-matt-skills` Markdown Skill，能够读取项目规则和 OpenSpec 状态，按问题类型路由辅助能力。
- 在项目文档中维护唯一的组合规则，包括角色边界、规范入口、触发矩阵、产物映射、确认快照、冲突/失败/恢复规则和运行时映射。
- 用根级 `CLAUDE.md` 提示不可绕过的短规则，用 `CONTEXT.md` 保存稳定术语，用一个 ADR 保存分层方案及取舍。
- 用手工场景矩阵验证用户可观察的路由和门禁行为，并把失败或未执行状态显式记录。
- 保持实现可回滚：不改上游 Skill、不删重复副本、不引入脚本和外部依赖。

**Non-Goals:**

- 不把 Matt Skills 的正文复制到组合 Skill，也不修改其触发描述或内部流程。
- 不让 `implement`、`to-spec` 或 Matt code review 取代 OpenSpec 的实现、规格或 artifact 验证职责。
- 不建立第二套需求规格，不把 GitHub Issue 当作 OpenSpec 实现契约。
- 不在本 Change 中清理 `.agents`、`.claude`、`.codex` 的重复副本或自动同步它们。
- 不实现解析自然语言、管理批准状态或模拟用户确认的路由脚本。

## Decisions

### 1. OpenSpec 是控制平面，Matt Skills 是方法层

组合规则把 OpenSpec artifact 作为当前 Change 的唯一正式事实源；Matt Skills 只能发现问题、提供候选结论或独立质量检查。冲突必须通过 `openspec-update-change` 重新落盘并重新授权，而不是以后调用者覆盖先前结论。

**替代方案**：让两套工具各自维护计划，或让 Matt Skills 的建议优先。两者都会产生平行事实源，无法可靠恢复，也会让实现者自行解决范围冲突，因此不采用。

### 2. 组合入口采用 Markdown 路由器

新增 `.claude/skills/openspec-with-matt-skills/SKILL.md`，按输入问题和当前 OpenSpec 状态选择允许的只读方法、推荐的 `opsx:*`/`openspec-*` 入口以及暂停点。它不执行代码、Issue、commit 或 archive，也不维护布尔批准状态。

**替代方案**：使用脚本解析状态并自动分支，或修改上游 Skills 让它们互相调用。脚本会引入跨平台和确认语义的维护成本；上游改造会扩大冲突面并造成版本分叉，因此不采用。

### 3. 按问题类型触发，而非机械绑定阶段

- 范围或方案争议：`mattpocock-skills:grilling`
- 外部事实：`mattpocock-skills:research`
- 术语和领域边界：`mattpocock-skills:domain-modeling`
- 模块、接口和 seam：`mattpocock-skills:codebase-design`
- 关键未知行为：`mattpocock-skills:prototype`
- 行为实现：`mattpocock-skills:tdd`
- 困难 bug/性能回归：`mattpocock-skills:diagnosing-bugs`
- 独立代码质量检查：`mattpocock-skills:code-review`

`grill-with-docs` 仅在同时需要压力测试和可能产生跨 Change 稳定术语时使用，避免与其底层 Skill 级联重复。

### 4. 规范入口按层命名

用户文档优先推荐 `/opsx:new|propose|ff|continue|apply|verify|update|archive`；对应的 `openspec-*` 是能力层入口。Matt 方法使用 `mattpocock-skills:<name>` 命名空间。裸名作为兼容入口但不主动推荐。所有 OpenSpec 入口共享同一个 `openspec/` 状态。

### 5. 产物和长期文档各有唯一归宿

- `proposal.md`：目标、范围、非目标和为什么现在做。
- `specs/<capability>/spec.md`：可观察行为与边界场景。
- `design.md`：技术方法、模块边界、研究证据约束和原型结论。
- `tasks.md`：实现切片和测试任务；TDD 不创建第二套完成状态。
- `CONTEXT.md`：跨 Change 稳定词汇及关系，不写实现细节。
- `docs/adr/0001-openspec-control-plane-matt-method-layer.md`：分层架构及替代方案。
- `docs/agents/combined-workflow.md`：操作规则、触发矩阵、入口映射、门禁和异常协议。
- `docs/agents/combined-workflow-scenarios.md`：手工回归场景及执行结果。

### 6. 确认绑定内容快照

三个门禁分别是范围确认、实现授权、归档确认。每次确认仅授权当时展示的目标、artifact 或验证结果；任何内容变化都要求重新展示并确认。组合 Skill 不把沉默或曾经出现的关键词视为持续授权。

### 7. OpenSpec context 只注入稳定指针

实现阶段可把 `openspec/config.yaml` 的 `context` 配置为指向稳定的组合工作流文档和 `CONTEXT.md`（若存在），但不把动态 Change 状态、批准状态或完整矩阵复制成第三份规则。具体配置属于实现任务，需在写入前按当前 OpenSpec 配置格式验证。

## Risks / Trade-offs

- [重复副本可能漂移] → 记录运行时映射并在上游入口或规则变化后执行受影响场景；副本治理另建 Change。
- [自然语言路由可能漏判] → 对高影响操作使用明确的停止条件和场景矩阵；不确定时暂停而不是猜测。
- [手工确认增加流程时间] → 只在范围、实现授权和归档三个高影响节点确认，阶段内只读探索不逐项确认。
- [组合 Skill 与上游升级不兼容] → 依赖公开职责和 artifact 契约；升级后重新检查入口、顺序、副作用和冲突矩阵。
- [领域文档过度膨胀] → `CONTEXT.md` 只收录稳定词汇，ADR 只收录难逆转、令人意外且存在真实取舍的决定。
- [研究或辅助 Skill 失败导致错误推进] → 将失败/未验证结果显式标为缺口或假设，不自动推进依赖该结论的阶段。

## Migration Plan

1. 在 OpenSpec apply 阶段创建或更新项目级规则、术语表、ADR、组合 Skill 和场景矩阵，并按任务顺序逐项验证。
2. 在 Claude Code 中先执行场景矩阵的核心冲突和门禁场景；记录运行时、日期、实际结果和结论。
3. 运行 OpenSpec validate/verify，并完成独立 code review；任何失败回到对应 artifact 或实现任务。
4. 在获得明确归档确认后归档本 Change。重复副本保持原样，未来若发现实际漂移则另建治理 Change。

回滚方式是删除本 Change 引入的组合规则、组合 Skill 和项目文档改动，并保留 OpenSpec 历史 artifact；不需要回滚应用代码或上游 Skill。

## Open Questions

无。运行时副本的最终清理和自动一致性检查已明确留给后续独立 Change，不影响本次方案或任务拆分。
