## Purpose

为文档预览和未来索引提供一个一致、可测试且有界的文本切分行为，确保保存的配置与产生的 chunk metadata 可追溯。

## ADDED Requirements

### Requirement: 统一切分入口与三种策略
系统 MUST 通过同一个 `chunk_document_text` 行为入口支持 `fixed-character`、`markdown-heading` 和 `paragraph` 三种策略，预览和未来 indexing MUST 复用该入口。默认策略 MUST 是 `fixed-character`，默认 `maxCharacters=1200`、`overlap=200`。

#### Scenario: fixed-character 切分
- **WHEN** 使用 fixed-character 处理文本
- **THEN** 按 maxCharacters 形成有序 chunk，并按 overlap 保留相邻上下文

#### Scenario: markdown-heading 切分
- **WHEN** 使用 markdown-heading 处理含 Markdown 标题的文本
- **THEN** 按标题层级形成有序 chunk，并保留可追溯的标题 metadata

#### Scenario: paragraph 切分
- **WHEN** 使用 paragraph 处理文本
- **THEN** 按段落形成有序 chunk，并保留 chunk 顺序 metadata

### Requirement: 策略参数校验与持久化
只有 fixed-character MUST 接受 `maxCharacters` 和 `overlap` 参数；fixed-character MUST 校验正数 maxCharacters 及 `overlap < maxCharacters`。其他策略传入这些参数 MUST 被拒绝。文档保存时 MUST 保存实际 strategy 和参数。

#### Scenario: 非法 fixed-character 参数
- **WHEN** maxCharacters 非正数或 overlap 不小于 maxCharacters
- **THEN** 返回参数校验错误且不保存文档

#### Scenario: 其他策略携带 fixed 参数
- **WHEN** markdown-heading 或 paragraph 携带 maxCharacters 或 overlap
- **THEN** 返回参数校验错误且不保存文档

### Requirement: 有界 chunk preview
系统 MUST 提供 chunk preview 响应，最多返回 12 个 chunk，每个 chunk 的 excerpt 最多 400 字，并包含顺序、策略和可追溯 metadata；preview MUST 不改变文档或索引状态。

#### Scenario: 预览长文档
- **WHEN** 用户请求自己的长文档 chunk preview
- **THEN** 返回不超过 12 段且每段 excerpt 不超过 400 字的结果

#### Scenario: 预览不改变状态
- **WHEN** 用户重复请求 chunk preview
- **THEN** 返回确定性结果，文档元数据和 index status 不发生变化
