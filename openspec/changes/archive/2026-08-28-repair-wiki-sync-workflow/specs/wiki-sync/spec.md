## Purpose

为 OpenSpec Change 提供确定、跨平台且可验证的 WIKI 投影，使 active 与 archived artifact 能通过统一页面、索引和导航被查阅，同时保持 OpenSpec 为唯一正式事实源。

## ADDED Requirements

### Requirement: Deterministic repository-level synchronization entry

仓库 SHALL 提供一个不隶属于特定 Agent 运行时副本的 WIKI 同步入口；Claude、通用 Agent 和人工调用相同输入时 SHALL 使用该入口并产生相同输出。

#### Scenario: Runtime-independent invocation
- **WHEN** 任一受支持运行时按文档调用 WIKI 同步
- **THEN** 调用 SHALL 到达同一个仓库级同步实现
- **AND** 调用 SHALL NOT 依赖仅存在于其他运行时目录的脚本

### Requirement: Active and archived Change projection

同步器 SHALL 根据当前 `openspec/changes/` 状态生成 active 与 archived Change 页面、统一索引和 VitePress 导航；页面 SHALL 通过相对路径引用对应 OpenSpec artifact，而不复制 artifact 内容。

#### Scenario: Archived Change is projected
- **WHEN** 一个已归档 Change 包含 proposal、design 和 tasks artifacts
- **THEN** 同步器 SHALL 在 `docs/changes/archive/` 生成对应页面
- **AND** 页面 SHALL 引用归档后的 artifact 路径
- **AND** 索引与导航 SHALL 包含同一归档条目

#### Scenario: Active Change is projected
- **WHEN** 一个 active Change 包含可用 artifacts
- **THEN** 同步器 SHALL 在 `docs/changes/active/` 生成对应页面
- **AND** 索引与导航 SHALL 将其列入进行中变更

### Requirement: Cross-platform artifact references

生成输出 SHALL 在不要求 Git 符号链接支持的 clone 中解析 OpenSpec artifact，并 SHALL 对每个 include 目标执行存在性校验。

#### Scenario: Windows clone disables symlinks
- **WHEN** 仓库运行于 `core.symlinks=false` 的 Windows clone
- **THEN** 同步 SHALL NOT 要求创建 `docs/openspec` 符号链接
- **AND** 生成页面的 artifact include SHALL 解析到仓库根级 `openspec/`

#### Scenario: Include target is missing
- **WHEN** 生成页面引用的必要 artifact 不存在
- **THEN** 同步器 SHALL 以非零状态停止并指出缺失的 include 目标

### Requirement: OpenSpec-aware archive validation

同步器 SHALL 依据每个归档 Change 自身的 OpenSpec 状态判断 specs 是否需要同步，并 SHALL 区分合法跳过与未同步错误。存在 delta spec 时，同步器 SHALL 要求可识别且格式正确的 operation；空文件、空 operation 段落或无法解析的 RENAMED SHALL 在写入前失败。

#### Scenario: Change declares skip_specs
- **WHEN** 归档 Change 的 `.openspec.yaml` 声明 `skip_specs: true` 且没有 delta specs
- **THEN** 同步器 SHALL 将该 Change 视为合法无规格变更
- **AND** SHALL 继续生成其 WIKI 页面而不要求绕过标志

#### Scenario: Delta specs are synchronized
- **WHEN** 归档 Change 存在 delta specs 且其要求已反映在对应 main specs
- **THEN** 同步器 SHALL 通过 archive spec 校验并继续生成页面

#### Scenario: Delta specs are not synchronized
- **WHEN** 归档 Change 存在尚未反映到 main specs 的 delta spec 操作
- **THEN** 同步器 SHALL 在写入 WIKI 输出前以非零状态停止
- **AND** 错误 SHALL 指出未同步的 capability 或 requirement

#### Scenario: Delta specs contain no operations
- **WHEN** 归档 Change 存在 delta spec 文件，但未包含任何 ADDED、MODIFIED、REMOVED 或 RENAMED Requirements 段落
- **THEN** 同步器 SHALL 在写入 WIKI 输出前以非零状态停止
- **AND** 错误 SHALL 指出该 delta spec 缺少可识别 operation

#### Scenario: Operation section is empty or RENAMED is malformed
- **WHEN** delta spec 含有 ADDED、MODIFIED 或 REMOVED 段落但没有 requirement，或 RENAMED 段落无法解析出成对 FROM/TO
- **THEN** 同步器 SHALL 在写入 WIKI 输出前以非零状态停止
- **AND** 错误 SHALL 指出 capability、operation 与格式问题

### Requirement: Idempotent and verifiable WIKI output

对同一 OpenSpec 状态重复运行同步 SHALL 产生相同的页面、索引和导航；生成后与独立校验均 SHALL 校验目录集合、include 目标以及索引和导航顺序的一致性。独立校验 SHALL 仅从当前 OpenSpec 源构造期望输出，并与受管页面、索引和导航全文比较；SHALL NOT 把受检 WIKI 中的生成字段当作期望值来源。

#### Scenario: Synchronization runs twice
- **WHEN** 输入 OpenSpec 状态未发生变化且同步器连续运行两次
- **THEN** 第二次运行后的受管 WIKI 文件内容 SHALL 与第一次完全相同

#### Scenario: Navigation diverges from index
- **WHEN** 受管索引与 VitePress 导航包含不同条目或顺序
- **THEN** 输出验证 SHALL 失败并指出导航不一致

#### Scenario: Standalone verification ignores existing WIKI dates as oracle
- **WHEN** 对已生成 WIKI 运行独立校验
- **THEN** 校验器 SHALL 仅从当前 OpenSpec Change 源构造期望页面、索引与导航
- **AND** SHALL NOT 把受检 WIKI 输出中的 createdDate 或其他生成字段当作期望值来源
- **AND** 受管页面、索引与导航全文 SHALL 与该期望一致，否则失败

#### Scenario: Existing WIKI date diverges from OpenSpec source
- **WHEN** 受管页面 frontmatter 的日期与 OpenSpec 元数据推导出的期望不一致
- **THEN** 独立校验 SHALL 失败

### Requirement: Strict synchronization inputs

同步入口 SHALL 在执行任何仓库读取或写入前拒绝非法调用参数。

#### Scenario: Mode or name is invalid
- **WHEN** 调用方传入不支持的 mode、在 all 模式附带 name，或 Change 名称包含路径分隔符、`.`、`..` 或为空
- **THEN** 同步入口 SHALL 以非零状态停止
- **AND** SHALL NOT 写入或删除任何 WIKI 输出

### Requirement: Buildable documentation site

仓库 SHALL 提供锁定依赖的 VitePress 文档构建命令，且生成的 WIKI 页面 SHALL 在该命令下成功构建。

#### Scenario: Build generated WIKI
- **WHEN** 依赖已按锁文件安装且 WIKI 同步成功
- **THEN** `npm run docs:build` SHALL 成功完成
- **AND** 构建 SHALL NOT 修改 OpenSpec artifacts 或 main specs
