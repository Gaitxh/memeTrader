# Information-first Shadow 前向研究

`information-first-shadow/v1` 用真实前向分母检验一个有限问题：当合格新闻、原帖或事件关系已经可用，而本机已观测到的市场活动仍较低时，Token 在随后 15/60/240 分钟的价格路径是否与其他样本不同。

它是描述性研究账本，不是交易信号、因果证明或“尚未定价”判定，`affects=none`。它不改变证据角色、候选排名、安全门、仓位、Paper 或 Live。

## 冻结规则

- Runtime 写入最终 `WAIT / REJECT / CANDIDATE` 决策后，对该 `event_id + token_id + version` 只冻结一次；历史不回填。
- 信息必须是当时已被本机观察并入库的 `feature/confirmation`。`identity/promotion` 不构成 lead。
- `signal_available_at` 取 lead 的 `observed_at`、`ingested_at` 与事件—Token 关系可用时间三者中的最晚者。
- 精确 CA 可使用该 CA 合格观察的可用时间；词义或 Agent 映射只能在最终决策时视为可用。
- 基线价格必须在 `signal_available_at` 前已经观察且入库。缺失基线仍建立 denominator cohort，标为 `baseline_missing_at_signal_available`，绝不用后来价格补填。

## 描述性市场层

当前只使用信号时点已知的市值、5 分钟成交量和 5 分钟成交笔数，形成：

- `low_observed_market_activity`
- `observed_market_activity`
- `insufficient_market_data`

“低已观测市场活动”不等于“未定价”。当前数据库没有可靠的 unique buyers、图像相似度或 holder cluster 历史；这些字段明确为 `not_available`，不能以 buys、零值或后来数据替代。

DexScreener 的 `pairCreatedAt` 只能描述交易对时间，不能声称是链上 mint 时间。来源数量也只是本机观察到的平台/来源种类，不等于独立事实来源数。

## 结果与网页

结果只接受目标时点之后才真实入库的快照，窗口错过后写入终态 `missing`；结果表不可更新或删除。Sources 页面提供中英文面板，按市场活动层展示 cohort、可随访数、信号基线缺失、60 分钟观察/缺失/等待和平均原始回报。

在跨多个日期、包含失败和 missing 的独立样本达到预注册成熟门前，不得把这些分层用于提高 Agent 频率、放大仓位或修改退出策略。
