## Purpose

为本仓库建立一套可追踪、可恢复且能跨运行时复用的 Agent 组合工作流，让 OpenSpec 管理正式变更状态，同时让 Matt Pocock Skills 提供不绕过变更门禁的工程方法能力。

## ADDED Requirements

### Requirement: Route work according to change boundary and problem type

The combined workflow SHALL distinguish mechanical work from behavior, interface, cross-file, or design-changing work, and SHALL route qualifying work through an OpenSpec Change. When a qualifying request lacks a unique active Change, the workflow SHALL identify the appropriate entry path without silently merging it into an unrelated Change.

#### Scenario: Mechanical change can bypass a Change
- **WHEN** a request is purely mechanical, has no behavior change, and requires no design trade-off
- **THEN** the workflow MAY process it without creating an OpenSpec Change and SHALL not represent it as an OpenSpec-approved change

#### Scenario: Behavioral request enters OpenSpec
- **WHEN** a request changes behavior, an interface, multiple files, or a design decision
- **THEN** the workflow SHALL require an OpenSpec Change before implementation proceeds

#### Scenario: Related request cannot be uniquely assigned
- **WHEN** more than one active Change exists and the request cannot be uniquely matched by goal, capability, and acceptance boundary
- **THEN** the workflow SHALL pause and ask the user to select an existing Change or create a new one

### Requirement: Preserve the control-plane and method-layer boundary

OpenSpec SHALL remain the formal source of truth for confirmed intent, requirements, implementation tasks, verification, and archival state. Matt Pocock Skills SHALL provide exploratory, analytical, testing, diagnostic, prototyping, or review methods and SHALL NOT silently create a competing specification or change state.

#### Scenario: Method advice supplements a Change
- **WHEN** a Matt Skill produces a confirmed conclusion relevant to an active Change
- **THEN** the conclusion SHALL be mapped to the appropriate OpenSpec artifact and SHALL not create a parallel plan

#### Scenario: Method advice conflicts with a confirmed artifact
- **WHEN** a Matt Skill finds advice that conflicts with a confirmed OpenSpec artifact
- **THEN** the workflow SHALL report the conflict, pause affected work, and require an explicit OpenSpec update and renewed authorization before proceeding

#### Scenario: TDD refines execution without changing scope
- **WHEN** TDD is used to implement an item from `tasks.md`
- **THEN** TDD SHALL supply red-green-refactor execution discipline while the OpenSpec task remains the scope and completion contract

### Requirement: Enforce side-effect and stage gates

The workflow SHALL allow read-only analysis to run according to the routing matrix, but SHALL gate project-document writes, OpenSpec artifact writes, code changes, external Issue or commit actions, and archival behind the appropriate confirmation and lifecycle stage.

#### Scenario: Exploration remains read-only until scope confirmation
- **WHEN** a request needs exploration, research, domain modeling, codebase design, or a prototype before scope is fixed
- **THEN** the workflow MAY run the permitted analysis and SHALL stop before creating or updating formal artifacts until the user confirms the scope conclusion

#### Scenario: Implementation requires explicit authorization
- **WHEN** proposal, specs, design, and tasks are complete but implementation has not been authorized for the displayed snapshot
- **THEN** the workflow SHALL not modify implementation files and SHALL request explicit implementation authorization

#### Scenario: Archive requires verified completion
- **WHEN** implementation is complete
- **THEN** the workflow SHALL permit archival only after OpenSpec verification, required independent code review, artifact-to-code coherence, and explicit archive confirmation all pass

### Requirement: Use canonical artifact destinations and recovery rules

Confirmed conclusions SHALL be persisted according to their meaning: scope and non-goals in `proposal.md`, observable behavior and boundary scenarios in delta specs, technical approach and evidence constraints in `design.md`, executable slices in `tasks.md`, stable cross-Change vocabulary in `CONTEXT.md`, and difficult-to-reverse trade-offs in an ADR. The workflow SHALL recover from persisted OpenSpec artifacts rather than hidden session memory.

#### Scenario: Research evidence becomes a design constraint
- **WHEN** external research affects design or acceptance
- **THEN** the workflow SHALL record the relevant conclusion with source and date, and SHALL mark unverified information as an assumption rather than a hard constraint

#### Scenario: Goal changes during implementation
- **WHEN** a goal, scope, or key assumption changes for an active Change
- **THEN** the workflow SHALL use the OpenSpec update path to identify affected artifacts and tasks, and SHALL require renewed implementation authorization before affected work resumes

#### Scenario: Interrupted work resumes from artifacts
- **WHEN** a session ends before a Change is complete
- **THEN** the workflow SHALL resume from the current persisted OpenSpec artifact state and SHALL not require repeating exploration unless the persisted goal is no longer valid

### Requirement: Expose distinct lifecycle and method entry points

The workflow SHALL document `opsx:*` as the recommended OpenSpec command-layer entry, `openspec-*` as the corresponding capability layer, and the namespaced Matt Skill entry points as method-layer helpers. It SHALL document the mapping among Claude Code, Codex-compatible, and shared Agent skill locations without treating duplicate copies as separate capabilities.

#### Scenario: OpenSpec command and skill share state
- **WHEN** a user enters an OpenSpec action through either `opsx:*` or its `openspec-*` capability
- **THEN** both entry layers SHALL operate on the same OpenSpec Change state and artifact dependency rules

#### Scenario: Duplicate runtime copy is discovered
- **WHEN** the workflow finds duplicate upstream Skill copies or a naming collision
- **THEN** it SHALL report the mapping or drift and SHALL not silently modify, delete, or synchronize upstream copies

#### Scenario: Explicit bypass is requested
- **WHEN** a user directly invokes an overlapping method such as `implement`, `to-spec`, or Matt code review during an active Change
- **THEN** the workflow SHALL explain the overlap, side effects, and recommended OpenSpec alternative, and SHALL not auto-merge the result into the formal Change
