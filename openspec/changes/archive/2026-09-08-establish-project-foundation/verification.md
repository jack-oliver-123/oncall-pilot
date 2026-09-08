# 验证记录（2026-09-08）

用户明确授权将本 Change 视为第 02 个 Change 的前置工程，验证、同步并归档后继续实现 API/SSE 合同。

| 维度 | 结果 |
| --- | --- |
| 完整性 | 34/34 任务；五组 capability 均有实现和测试 |
| 正确性 | 配置、健康检查、导入安全、前端公开投影及构建秘密扫描通过 |
| 一致性 | Standards 与 Spec 独立审查发现的最低 Python 版本和导入监控缺口已修复并复核 |

本轮 Windows `npm run check` 全部通过：后端 15、contracts 1、前端 9、仓库/WIKI 21 个测试；Ruff、strict Pyright、TypeScript、lint/format、生产构建、OpenSpec strict 和文档构建通过。修复后再次运行 Python 3.12 后端全部检查通过；隔离 Python 3.10.20 环境实际断言解释器版本并运行 pytest 15/15、Ruff、Pyright，全部通过。默认 uv 安装目录首次安装失败，改用仓库外任务专用目录成功，未更改项目 Python pin。

远端证据：[当前 HEAD 的 GitHub Actions](https://github.com/jack-oliver-123/oncall-pilot/actions/runs/34181768397) 为成功，覆盖 Linux/Windows。该历史运行的最低版本 job 没有解释器断言，不作为真实 3.10 证据。本次 CI 修复未提交或推送，远端没有运行该修复；最低版本的新增证据为上述 Windows 隔离实测，不能当作 Linux 实测。

浏览器证据沿用 [PR #2](https://github.com/jack-oliver-123/oncall-pilot/pull/2) 中已发布的 2026-09-08 Playwright 记录：1440×900、390×844 截图、无横向溢出或嵌套滚动、console 0 error/0 warning、reduced motion。此次未修改 UI，也未重新执行浏览器验收。

五组主规格已逐项同步，OpenSpec strict 8/8、WIKI 19 个 include、VitePress 和 `git diff --check` 通过。没有未关闭的 CRITICAL/WARNING。仅完成本地验证与归档，不包含 Git 提交或远端发布。
