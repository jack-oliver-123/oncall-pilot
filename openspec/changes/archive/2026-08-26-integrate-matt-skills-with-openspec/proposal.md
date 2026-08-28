## Why

当前仓库同时提供 OpenSpec 与 Matt Pocock Skills，但两者处于不同抽象层，且存在重复副本、同义入口和职责重叠。缺少明确的组合契约会导致需求规格、实现任务和工程建议分叉，或让辅助 Skill 绕过 OpenSpec 的变更门禁。现在建立项目级组合规则，使 OpenSpec 成为唯一正式变更事实源，同时保留 Matt Skills 在探索、建模、测试和审查方面的价值。

## What Changes

- 建立 `combined-agent-workflow` 能力，定义 OpenSpec 控制平面与 Matt 方法层的职责边界。
- 新增 `openspec-with-matt-skills` 交互式路由 Skill，按问题类型建议或执行允许的只读辅助能力，并在写入和阶段门禁处暂停。
- 将稳定术语、架构取舍、触发矩阵、产物映射、冲突处理和恢复规则写入项目级文档。
- 更新根级 `CLAUDE.md`，使 Claude Code 从所有入口都遵守组合工作流不变量。
- 增加无副作用的场景矩阵，用于首次验证及规则或上游入口变化后的回归检查。
- 不删除重复 Skill 副本、不修改上游 Skill、不引入脚本路由器；这些属于后续可独立评估的工作。

## Capabilities

### New Capabilities

- `combined-agent-workflow`: 为 OpenSpec 变更生命周期接入 Matt Pocock 工程方法 Skills，并定义路由、产物、门禁、冲突、失败和恢复行为。

### Modified Capabilities

- 无。当前 `openspec/specs/` 中没有已存在的 capability 主规格。

## Impact

- 影响 Claude Code 项目规则、Agent Skill 发现与调用约定，以及 OpenSpec 变更规划和验证流程。
- 新增根级领域词汇表、聚焦架构决策记录、组合工作流手册和手工场景矩阵。
- 不改变应用业务代码、业务 API 或上游 Skills 内容；不引入运行时脚本或新的外部依赖。
