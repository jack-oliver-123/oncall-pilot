## 1. 建立可测试的仓库级同步模块

- [x] 1.1 添加 `scripts/sync_wiki.py`，以显式仓库上下文实现 Change 收集、OpenSpec-aware specs 校验、页面渲染和输出验证
- [x] 1.2 使用根级 `openspec/` 的直接相对 include，移除符号链接要求、外部项目站点名称和 requirement evolution 特例
- [x] 1.3 新增 `tests/test_sync_wiki.py`，通过临时仓库覆盖 active/archive 投影、`skip_specs`、未同步阻断、缺失 include、幂等性和导航一致性

## 2. 建立文档站点与统一调用入口

- [x] 2.1 添加 `.gitignore`、`package.json`、`package-lock.json` 和 `docs/index.md`，提供锁定的 VitePress `docs:dev`、`docs:build`、`docs:preview` 命令
- [x] 2.2 更新 `.claude/skills/wiki-sync/SKILL.md` 与 `.agents/skills/wiki-sync/SKILL.md`，统一调用 `python scripts/sync_wiki.py` 并准确说明 `skip_specs` 与构建门禁
- [x] 2.3 删除 `.agents/skills/wiki-sync/scripts/sync_wiki.py`，确认不存在第二份同步实现

## 3. 生成并验证真实 WIKI

- [x] 3.1 运行 Python tests 并修复所有失败
- [x] 3.2 对真实仓库运行 `python scripts/sync_wiki.py all`，生成 active/archive 页面、索引和 VitePress 导航
- [x] 3.3 验证 `2026-08-26-improve-claude-md-guidance` 的归档页存在，且所有 include 目标、目录集合、索引与导航顺序一致
- [x] 3.4 运行 `npm run docs:build` 并确认 VitePress 成功构建生成的 WIKI
- [x] 3.5 运行 `openspec validate repair-wiki-sync-workflow --strict`，并确认没有修改任何归档 artifact 或现有 main spec 内容

## 4. 收敛审查与依赖发现

- [x] 4.1 修复 `verify_wiki`：期望仅从 OpenSpec 源构造；受管页面、索引与 config 与 render 结果全文比较；禁止回读 WIKI frontmatter 作为 createdDate oracle
- [x] 4.2 严格 delta 解析：无 operation、空 ADDED/MODIFIED/REMOVED、畸形 RENAMED 在写盘前失败，并补充对应 unittest
- [x] 4.3 Python `sync_wiki` seam 拒绝非法 mode、`all`+name、空名与含路径分隔符/`.`/`..` 的名称；补充 unittest
- [x] 4.4 更新两份 wiki-sync Skill：触发覆盖“同步/重建 WIKI、artifact 集合变化”；`--allow-unsynced` 绑定当前完整错误列表与状态的一次性批准
- [x] 4.5 `package.json` 增加 `overrides.vite=6.4.3`，更新 lockfile；`npm audit` 为 0 且 `npm run docs:build` 通过
- [x] 4.6 重跑 Python tests、`python scripts/sync_wiki.py all`、独立 verify 路径，确认归档 OpenSpec/main specs 哈希未变；`openspec validate repair-wiki-sync-workflow --strict`
