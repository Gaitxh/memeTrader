# 长期停滞续作247：过期预留永久占仓修复

## 结论与范围

本轮承接完整全链路 Paper 任务和 246 的未闭环项，优先处理“多天不交易”的当前逐环节证据。保持 `D:/OpenTrader/memeTrader_2`、原资金期 `chain-meme-trader/funding-20260906-v002-final-1000`、普通 20U、买卖各 4% 滑点、原池 1000U 底线；Live 仍锁定。没有删除历史、重置账户、恢复定时研发、增加接口或放宽安全/原池/时钟条件。

## 246 实际加载与自然判断

2026-09-19T06:53:46Z 的 `/api/live` 已补齐前轮缺失回读：525 条策略，`revision246_observed_cooling_recovery_v1` 唯一注册，激活于 06:28:36.722785Z、快照 1746620，1000U 现金、零仓位/成交。06:28:51Z 至约 06:55Z 共 1605 条 pattern 判断、91 个不同 Token，0 准入；主要原因是冷却种子不满足，另有 269 条 45 秒路径间隔拒绝和 37 条同池不同上游来源拒绝。

只读回放把最大间隔从 45 秒改为 60 秒后，269 条中 212 条可继续进入后续判断，但仍 0 条达到最终准入；因此本轮没有追参、没有修改 246 合同或追加一个无实际信号差异的复制策略。不同上游来源的 37 条继续严格拒绝，不混合为同一条价格路径。

## 当前长期停滞的真实断点

对 246 激活后的评价尾部逐臂读取，而不是依靠策略名称推测：

- `experiment_quiet_reawakening_candidate_v1`、`event_reawakening_v1`、`surface_lifecycle_pipeline_v1`、两条 quiet renewal 和旧 cooling 均持续产生明确的基线、池龄、活动或聚合条件拒绝；这是当前有输入但没有信号，不是注册缺失。
- 多条 cohort/narrative 臂持续为 `wait_passive_cohort_opportunity`，尚无上游自然 cohort 信号；不把零交易当成程序已坏或市场没有机会。
- `trajectory169_trend_runner_control_v1` 在新窗口已有 111 条信号/ready，但旧 moonbag 配对结构和历史处置需单独解释，不能把 control 的正收益直接当作可独立恢复依据。
- `dex_regime_recovered_runner_v1` 的 2981 条新 cohort 判断全部为 `strategy_open_or_reserved_limit`，而当时全系统开放仓位为 0。这是确定性工程矛盾。

进一步账本追踪确认：该臂有 8 条 2026-09-12 的 claim，`terminal_reason IS NULL`、没有任何对应仓位；5 个真实历史仓位均已关闭或核销。共享 `open_or_reserved_full` 只检查 claim 是否无终态，导致这些旧回执永久占满当前 8 仓上限。相同形态还存在于其他臂，因此修复共享容量输入，而不是只对一个策略打补丁。

## 实现

`cohort_enrollment.open_or_reserved_full` 现在把 claim 视为持久所有权回执，而不是永久仓位：

- 真实 `status='open'` 仓位继续占容量；
- 无仓位、无终态 claim 只有在对应 admitted decision 的注册 `max_signal_to_execution_start_seconds` 截止内才占容量；
- 截止时间按调用时明确的 `as_of` 计算，观察阶段使用 decision time，成交阶段使用 fill time；
- 旧 claim 不删除、不改写、不补造终态，仍可审计；新鲜安全等待继续占位，当前 cohort 在成交时排除自身避免自我阻断。

改动位于 `src/memetrader/cohort_enrollment.py` 和 `src/memetrader/store.py`，回归在 `tests/test_cohort_enrollment.py`。

## 验证与部署

- `tests/test_cohort_enrollment.py`：4 项通过，包括并发 claim、重启安全等待、拒绝终态，以及 8 条过期 claim 保留但不占容量/新鲜 claim 仍占容量。
- `tests/test_opening141.py` 同跑时 4 条旧断言失败：仍期待已被用户统一合同取代的 5U/2 仓及旧漏斗计数；当前实际合同为 20U/8 仓。这些失败未用于通过声明，也不是本轮修复造成的回归。
- 生产只读复算：8 条旧无终态 claim 仍在，开放仓 0，修复语义下 `capacity_full_8=false`。
- 受控停止已核验旧 Paper wrapper 35144 一次；监督器 4296 启动新 wrapper 22696/运行 PID 38644，启动回执 07:02:50.440064Z。Web 和监督器未停止。
- manifest 525 条策略；`cohort_enrollment.py`、`store.py`、`cooling_recovery246.py` 的加载 SHA256 与磁盘逐一相同。健康 200、心跳约 0.003 秒、Paper-only、Live locked、原资金期。
- 部署后至 07:04:16Z，目标臂 55 条自然 cohort 判断全部恢复为普通 `wait_passive_cohort_opportunity`，不再出现永久容量拒绝；0 新信号/ready，故不宣称新增成交或盈利。

## 未闭环项

本轮修复一个已证实的执行阻断，不等于完整十二节任务或所有长期停滞已解决。继续时应：观察目标臂新的自然 cohort 信号、下一帧/安全/成交转化与净结果；对 cohort 上游长期无信号的臂追踪具体生产者；单独处理 169 配对结构；保留 246 的自然前向观察。不得以恢复到“等待真实信号”冒充盈利改善，也不得为产生交易降低原池、时钟或成本真实性。
