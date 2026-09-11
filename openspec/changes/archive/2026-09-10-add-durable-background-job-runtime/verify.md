# 验证报告：add-durable-background-job-runtime

## 验证范围

本报告按 completeness、correctness、coherence 对照本 Change 的 proposal、design、三项 delta specs 和任务清单；包括 9 个 Requirement、19 个 Scenario。所有功能证据来自临时 SQLite、真实本地 HTTP 认证与 fake handler，不涉及生产数据库、真实 LLM/MCP 或前端 UI 验收。

## 需求与证据映射

| 需求 | 实现 | 验证证据 |
| --- | --- | --- |
| 持久任务模型与重启恢复 | 0003 migration、background_models.py、background_jobs.py | test_migrations：升级/重复升级/check/降级再升级；独立 Python 进程领取后退出，再打开数据库和 worker 恢复 |
| Owner-scoped Repository | 必填 keyword-only owner、复合 owner/parent 外键、查询缺失返回 None | test_owner_parameter_contract_before_io；双用户读写/事件隔离与错误 parent 外键拒绝 |
| 原子领取与租约 | writer 事务、独立领取 token、heartbeat 更新 leaseExpiresAt | 6 个并发领取仅一个赢家；续租超越初始 lease；过期回收；旧 token 续租/事件/完成被拒绝 |
| 重试、timeout 与取消 | finish/recover/cancel/retry、JobContext、BackgroundWorker | 指数退避 2/4/8/16/30、最大尝试次数、手动新任务保留 retryOfJobId、queued/running 取消、timeout handler finally 清理 |
| 单调持久事件及重放 | 状态与事件同事务、唯一 sequence、list_events(after_sequence)、replay_events | 并发追加 6 个事件有序；消费者 aclose 不取消任务；重连重放 queued/running/progress/succeeded |
| fencing 与安全错误 | running/token/expiry 检查、固定安全消息 | 旧租约写回失败；含 password/token 异常不进入 errorMessage 或日志 |
| 生命周期清理 | lifespan stop_event、handler 清理、heartbeat 事务自然结束、emit shield | 默认并发 2、未知 kind 不消费、关闭后无 task 且 database 拒绝访问；轮询故障后继续；正常关闭再恢复 |
| 四个 HTTP API | canonical OpenAPI、生成 DTO、protected_router | 真实认证、无认证401、缺失/越权403完全等价、非法状态409、取消/新任务重试、注销保留任务；OpenAPI 实际路由比对 |
| tenant 调度目录例外 | _owners 只发现 owner ID，后续业务操作强制 scope | 双 owner worker 测试、参数合同与独立规范/规格审查；tenant delta 保留原场景 |

## 审查与修复

- Standards 独立审查最初发现调度目录例外未记录、get 缺失返回语义偏离；已修正规范、delta 及实现，复查无剩余 finding。
- Spec 独立审查最初发现 tenant 例外同步遗漏；已补完整 MODIFIED requirement 并保留全部旧场景，复查无 CRITICAL/WARNING。
- 全量运行最初 314 个断言通过，但产生 SQLite 关闭警告。已修复：不直接取消轮询/heartbeat 中的数据库事务，关闭等连接自然清理；emit 被取消时等待写事务结束。33 项专项以线程异常/RuntimeWarning 为失败重跑通过。
- 任务曾在先前未实现时被错误勾选，已恢复并依据本轮证据逐项更新；不以 artifact 文件存在性或 CLI all_done 作为验收证据。

## 明确边界

这是可复用持久任务运行时；索引和 AIOps 业务 handler 尚由后续 Change 接入。事件重放是 Repository/async iterator 基础，没有 HTTP Last-Event-ID。执行为至少一次，具体 handler 需要幂等且必须遵守 async 协作取消与有界 I/O；不承诺强杀阻塞或吞掉取消的恶意 handler。运行时直接使用 _utc_now()/asyncio.sleep()，没有 clock 参数和 heartbeatAt/result 列。

## 门禁结果

| 门禁 | 结果 |
| --- | --- |
| backend Ruff | 通过 |
| backend strict Pyright | 0 errors / 0 warnings |
| backend 全量 pytest（资源警告作为错误） | 314 passed，302.98 秒，无 warning |
| 后台任务与 HTTP 专项 | 13 passed |
| 生命周期修复后专项（后台任务/HTTP/auth） | 33 passed，无资源清理警告 |
| migration | 全量内覆盖 5 项，包含 upgrade/check/downgrade/re-upgrade |
| contracts 生成一致性/typecheck/Vitest | 通过，39 passed |
| frontend lint/format/typecheck/Vitest/build | 通过，67 passed |
| WIKI tooling | 37 tests OK |
| VitePress build | 归档投影重建通过，14.12 秒；66 个 include 与导航验证通过 |
| OpenSpec strict | 归档前含 Change 21/21；归档后 main specs 20/20 通过 |
| git diff --check | 通过 |

代码检查结论：Completeness 9/9 需求有实现和证据；Correctness 19/19 场景有实现及专项/既有测试覆盖；Coherence 与最终设计一致。CRITICAL 0、WARNING 0。实现门禁全部通过，11/11 任务完成。已归档到 2026-09-10-add-durable-background-job-runtime；全部三项 specs 同步核验通过，归档后 WIKI/build/tooling/OpenSpec/diff 复核通过，active Change 列表为空。
