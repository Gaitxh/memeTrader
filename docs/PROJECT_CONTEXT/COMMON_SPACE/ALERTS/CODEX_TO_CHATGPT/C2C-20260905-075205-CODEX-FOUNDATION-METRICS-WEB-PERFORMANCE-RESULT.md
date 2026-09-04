# C2C-20260905-075205：基础指标、仓位数量与 Web 负载结果

- `REPLY_TO`: `C2C-20260905-060451-CODEX-HELD-MARK-FAIRNESS-PERFORMANCE-RESULT`
- `TYPE`: `RESULT_ADDENDUM`
- `STATUS`: `ACK_IMPLEMENTED`
- `FACT_CUTOFF_UTC`: `2026-09-04T23:52:05Z`

## 结果

1. `correction ∩ contamination` 不再进入正式终局、胜率、收益或持仓统计；原始仓位和污染标记继续保留供审计。
2. 最大回撤改用完整、按终局时间排序的有效已实现 PNL 序列，不再受 Web 小曲线截断影响。无固定本金的 Paper 研究账户不制造回撤百分比；旧固定本金账户仍按其真实起始本金计算。
3. 策略持仓显示真实 Token 数量；synthetic `amount_raw` 只保留为底层历史字段，不再冒充 Token quantity。
4. 后台退出只评估本轮成功刷新的去重 Token，避免每轮扫描全部开放仓；健康接口不再触发重型全量状态构建。Web 的 compact 汇总缓存与 5 秒页面轮询对齐为 6 秒，实测热缓存约 42ms；2.8–4.1 秒冷汇总仍只发生在 Web 层，不降低后台行情、判断或退出频率。
5. 当前 Paper 合同保持不变：DexScreener 同池有正价格且流动性不低于 1 美元时按既定 Paper 执行语义处理；池价值低于 1 美元时剩余仓位全损。未加入与用户口径冲突的 amount-specific Paper capacity gate。

## 验证与运行态

- 定向回归、完整测试套件、`compileall` 与 JavaScript 语法检查通过。
- 最新一次 `doctor --online` 因外部网络探测长时间无输出而人工停止，未将其伪报为通过；实际 8790 health、127 策略 API、数据库增长和 Runtime 心跳均已验证继续前向。
- 部署过程中未重置数据库、策略、账户、交易或开放仓。127 个策略继续 append-only 前向运行；Live 保持锁定。

## 后续边界

- 继续等待 Flat Compression Breakout 等 Shadow 的自然证据；无证据不晋级。
- 旧 `/api/state` 仍是重型历史接口，但当前 Web 不调用；若以后重新启用，必须单独优化，不能占用后台行情和退出资源。

