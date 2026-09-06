# Token 前置特征 point-in-time 证据审查

**状态：2026-09-07 完成一次冻结、只读、有界的描述性审查。不是回测，不挑参数，不证明 alpha，不改变 Strategy / Paper / Live。**

## 1. 结论先行

本项目现有证据足以真实完成一轮“暴涨 / 普通 / 失败 / 暴跌”的时点前置特征审查，但不足以宣称数据已经证明最优阈值或 alpha。它不禁止基于可解释机制预注册并冻结新的 Paper challenger，再以前向数据证伪。

- 较早的全 token universe 提供大分母和多链横截面；最终冻结 frontier 有 229,500 个 cohort，但只有 93,075 个 observed baseline，40,336 个明确 missing baseline，另有 96,089 个 cohort 根本没有 baseline 记录。60 分钟 outcome 的最后评估时间停在 2026-09-03 15:00:25Z 左右，而 cohort 延伸至 2026-09-06 17:01:10Z，故“后半段没有 outcome”不是失败或暴跌。
- 确定性 SHA-256 样本中的 12,000 个 universe cohort，保留了 4,941 个 baseline 未登记、2,146 个 baseline missing、437 个 outcome missing、9 个 outcome 未登记/未成熟和 55 个 route 不可比较/未评估。可作 60 分钟同池四分类的只有 4,412 个：101 暴涨、3,326 普通、517 失败、468 暴跌。
- 较新的 chain-meme 固定结果框完整保留 2,729 个有 h0 的 cohort。60 分钟只有 506 个 observed（56 暴涨、297 普通、122 失败、31 暴跌）；1,447 个 UNKNOWN、776 个 PENDING/未登记。240 分钟全为 PENDING，因此本轮没有 240 分钟经济比较。
- `positions_evidence.csv` 的 223,306 行并未用于选样或构造特征。去重后是 15,694 个 token/cohort/snapshot 入场单元；它与 universe baseline 精确 snapshot 匹配为 0，与 chain-meme source snapshot 匹配 1,435/2,729。匹配组仍保留 679 缺结果、482 未成熟、27 暴跌、46 失败、185 普通、16 暴涨，未只抽赢家。
- 两个样本框的边际关联并不稳定。旧 universe 中，暴涨相对普通的 5 分钟买单占比中位数高 0.0477，交易数高 16；但分别只有 4/12 和 6/12 个可比较分层方向为正。当前 chain-meme 中，暴涨相对普通的 `log10(volume_5m)` 高 0.776、买单占比高 0.117、5 分钟交易数高 1,554.5，可是只有 5 个分层能同时容纳至少 3 个暴涨和 3 个普通样本，方向也混合。
- 当前 chain-meme 暴涨与失败的若干边际差异看似很大，但在冻结的“同链 × UTC 12 小时 × 池龄 × 流动性”分层下，**零个**分层同时达到两边各 3 个样本。它们主要反映时间、链、资金期、市场面或采集覆盖差异，不能当成可迁移阈值。

最稳妥的研究结论是：`t0` 的活跃度/买卖结构值得作为后续前向假设，但现有结果不能证明任何阈值实证最优。可以把可解释候选冻结为新的 Paper/Shadow 前向 challenger；它不支持把描述性差异直接升级为已验证 alpha、增资或 Live。

## 2. 冻结研究合同

脚本在正式计算前把合同写入模块说明和常量：`scripts/analyze_token_precursors_20260907.py`（2026-09-07）。

| 项目 | 冻结定义 |
|---|---|
| 主 horizon | 固定 60 分钟；同时完整记录 chain 的 0/15/60/240 与 universe 的 15/60/240 覆盖 |
| universe `t0` | 已记录 baseline 的精确 `snapshot_id`；可用时刻取 baseline `evaluated_at`，特征仅来自该不可变 snapshot |
| chain `t0` | cohort 的精确 `source_snapshot_id` 与 `decided_at`；h0 outcome 用于 baseline outcome 完整性 |
| 暴涨 | 固定目标收益 `>= +100%` |
| 普通 | `-20% < return < +100%` |
| 失败 | `-80% < return <= -20%` |
| 暴跌 | `return <= -80%` |
| 缺失处理 | baseline 未登记、baseline missing、outcome missing/UNKNOWN、PENDING/未登记、时间顺序无效、route 不可比均单列；绝不填 0 或并入暴跌 |
| universe 抽样 | frontier 内 `definition_version|cohort_id|token_id` 的无符号 SHA-256 最小 12,000 名；不看 outcome，不按赢家或交易选择抽样 |
| chain 抽样 | 所有已有 h0 固定 outcome 的 cohort，不抽样 |
| 分层 | chain × UTC 12 小时块 × 池龄桶 × 流动性桶 |
| 池龄桶 | `<15m`、`15-60m`、`1-6h`、`6-24h`、`>=24h`、unknown |
| 流动性桶 | `<$1k`、`$1-5k`、`$5-25k`、`$25-100k`、`>=$100k`、unknown |
| 不确定性 | 不报告 cohort-iid 置信区间；同 token 可跨 cohort 重复，未做 token-cluster bootstrap。仅报描述性中位数差与同分层方向计数 |

结果标签允许读取 `t0` 后固定 outcome；任何特征都不得读取 `t0` 后数据。funnel 的 `ever` 字段只用于选择流程审计，明确标为 post-`t0`、`causal_feature=false`，没有进入特征比较。

本轮时序复核的实际边界如下：所有进入四分类的行都通过了 snapshot `observed_at/ingested_at/recorded_at <= t0 < target_at`。Universe 的 `t0` 是 baseline `evaluated_at`，所以这证明 baseline 在其自身 t0 可用，但**不证明**它早于原 discovery decision；chain 的 `t0=decided_at`，其 source snapshot 三时钟均不晚于 decision。导出的 CSV 没有 target snapshot 三时钟或 late-budget 字段，因此本轮没有独立重验 `target_observed_at >= target_at` 与 late budget，只依赖既有固定 outcome 表的终态合同；该项是明确未验证边界，不得写成已复核事实。

## 3. 数据语义与因果边界

### 3.1 实际使用的表

- `token_universe_forward_cohorts`：全 universe 样本框、链与 discovery 时钟。
- `token_universe_forward_baselines`：精确 baseline snapshot ID 和 missing 分母。
- `token_universe_forward_outcomes`：固定 15/60/240 分钟 target 状态。
- `token_universe_outcome_quality`：只用于确认 baseline/target pair 地址相同并读取固定目标收益。
- `token_universe_funnel_transitions`：抽样 cohort 的后续流程 `ever` 标记，只作选择审计。
- `chain_meme_trader_v6_cohorts` 与 `chain_meme_universe_outcomes`：较新的精确 source snapshot 与 0/15/60/240 状态。
- `token_snapshots`：只按上述精确主键 ID 读取；没有扫表或按未来窗口搜索。
- `data/research/20260907/positions_evidence.csv`（提取截止 2026-09-07）：只作 exact-entry 审计标记。

schema/index 的相关事实来自 `src/memetrader/store.py`（2026-09-07 工作树）：snapshot 有 `(token_id, observed_at DESC)` 索引（约第 1065 行），funnel 有 `(cohort_id, stage, recorded_at, id)` 索引（约第 4132 行），outcome 有 horizon/status 索引（约第 4450 行）。本脚本仍只对 snapshot 使用主键 `id IN (...)`，没有让 13GB snapshot 历史承担范围扫描。

### 3.2 一个必须排除的易混字段

`token_universe_outcome_quality.same_pair_return` 不是固定 60 分钟目标收益；当前实现对同池路径取 `max(...)`（`src/memetrader/store.py` 约第 19819 行），本质上是最大有利/路径最大收益。它不是固定目标 return，故最终结果完全排除此字段。

最终 universe 标签使用 `raw_fixed_horizon_return`（由固定 outcome 的 `raw_return` 写入，`src/memetrader/store.py` 约第 19712 行），并额外要求 quality 层记录的 baseline pair 地址等于 target pair 地址。否则保留为 `ROUTE_INCOMPARABLE_OR_UNASSESSED`。

chain-meme observer 的 source pair 固定合同用于 h0→h60 比值；这仍只是市场快照路径，不等于可执行收益。

## 4. 样本框与完整性

### 4.1 全 universe

最终 frontier：cohort ID 229,500、outcome ID 389,838、quality ID 372,352、funnel transition ID 1,523,827、snapshot ID 1,182,648。

全 cohort 链分布为 Solana 175,372、Robinhood 38,963、BSC 14,170、Base 995。固定 outcome 的历史覆盖只到 2026-09-03，而新的 cohort 持续到 2026-09-06；因此 universe 抽样用于历史、多链对照，但不是当前采集状态的完整代表。

| 60m 类别/覆盖状态 | 12,000 hash 样本数 | 含义 |
|---|---:|---|
| 暴涨 | 101 | 同池固定目标收益 `>=100%` |
| 普通 | 3,326 | `(-20%,100%)` |
| 失败 | 517 | `(-80%,-20%]` |
| 暴跌 | 468 | `<=-80%` |
| route 不可比/未评估 | 55 | 不参与四分类 |
| outcome missing | 437 | 不填成亏损 |
| outcome 未登记/未成熟 | 9 | baseline 已有但无 h60 终态 |
| baseline missing | 2,146 | 已有 missing 记录 |
| baseline 未登记 | 4,941 | cohort 没有 baseline 行 |

Universe 的 exact baseline 与 `positions_evidence.csv` 没有精确 snapshot 匹配，证明这两套表不能被默认为同一入场语义。

### 4.2 当前 chain-meme 固定 outcome

最终 frontier：cohort ID 20,191、outcome ID 10,922；实际纳入所有 2,729 个有 h0 outcome 的 cohort，决定时间 2026-09-06 11:13:04Z 至 16:09:38Z。

| horizon | OBSERVED | UNKNOWN | PENDING/未登记 | 可做本轮经济比较 |
|---|---:|---:|---:|---|
| 0m | 2,729 | 0 | 0 | 仅作 baseline |
| 15m | 1,390 | 1,106 | 233 | 可描述，但非主标签 |
| 60m | 506 | 1,447 | 776 | 是，四类合计 506 |
| 240m | 0 | 0 | 2,729 | 否 |

60 分钟 observed 的四类为 56/297/122/31。exact position 匹配的 1,435 个 cohort snapshot 里，只有 274 个有四类结果，另有 679 个 UNKNOWN、482 个未成熟；因此当前 Paper 选择样本远未成熟到足以评价收益。

## 5. 前置特征观察

所有列均来自精确 `t0` snapshot 或 snapshot 当时已经携带的 5 分钟/1 小时滚动字段：价格变化、volume、buy ratio、liquidity、market cap、pool age、记录延迟。没有查询 `t0` 后路径。

### 5.1 universe：覆盖较广，但 marginal 与分层方向冲突

| 暴涨对照 | 特征 | 描述性中位数差 | 可比较分层；正/负 |
|---|---|---:|---:|
| 普通 | buy ratio 5m | +0.0477 | 12；4/6（另 2 个相等） |
| 普通 | 5m 交易数 | +16 | 12；6/6 |
| 普通 | 1h 价格变化 pct | +14.66 | 12；2/10 |
| 失败 | log10(volume 5m) | -0.696 | 7；1/6 |
| 失败 | pool age 分钟 | +0.556 | 7；4/3 |
| 暴跌 | buy ratio 5m | +0.0437 | 10；6/4 |

边际中位数差与同分层方向可能相反。最明显的是 1 小时价格变化：总体看暴涨较高，但 10/12 个可比较分层的暴涨中位数反而更低。它不能被宣称为数据已经证明的 momentum 最优阈值；仍可作为明确预注册、独立前向检验的候选机制。

此外，12,000 行中只有 677 行有正 liquidity 可用于 log10/liquidity 比率，约 4,600–4,900 行有 volume、buy ratio、pool age 等字段。特征缺失强烈依赖链、provider 和采集时期。

### 5.2 chain-meme：活跃度差异明显，但时段/版本混杂严重

| 暴涨对照 | 特征 | 描述性中位数差 | 可比较分层；正/负 |
|---|---|---:|---:|
| 普通 | log10(volume 5m) | +0.776 | 5；3/2 |
| 普通 | volume5m/liquidity | +2.372 | 5；3/2 |
| 普通 | buy ratio 5m | +0.117 | 5；3/2 |
| 普通 | 5m 交易数 | +1,554.5 | 5；4/1 |
| 失败 | buy ratio 5m | +0.251 | **0** |
| 失败 | log10(volume 5m) | +1.176 | **0** |
| 暴跌 | buy ratio 5m | +0.156 | 2；2/0 |
| 暴跌 | 5m 交易数 | +1,469.5 | 2；2/0 |

这里的“交易数高 1,500”不是稳健效应大小：暴涨交易数中位数为 1,593.5、普通为 39，说明当前小窗存在完全不同的市场面/采集尺度。更强的警告是，暴涨 vs 失败没有任何冻结分层满足两边各 3 个样本。边际中位数差只刻画已观察混合分布，不控制 chain/time/age/liquidity，也没有控制 funding/observer version。

## 6. Funnel 与已交易样本

Universe 样本中，后续曾到 `candidate_evaluation` 的比例为：暴涨 10/101（9.90%）、普通 403/3,326（12.12%）、失败 67/517（12.96%）、暴跌 23/468（4.91%）。`decision_final` 只有普通 1 个，`paper_fill` 为 0；样本量不足以评价 funnel 是否偏爱赢家。

这些是 post-`t0` 的选择结果，不是入场可用特征。chain-meme exact-position 也只作覆盖切片；因为同一个 cohort 可被多个 arm 重复持有，报告按“是否至少有一个 exact position row”计 cohort，而不把 223,306 行仓位重复当独立 token 样本。

## 7. 可复用机制与不可执行结论

可以复用为下一版前向假设的机制只有：

1. 精确 snapshot 的 5 分钟成交强度、buy ratio、volume/liquidity 可以继续观察；它们在当前 chain-meme 边际比较中方向一致性相对较好。
2. 所有候选阈值必须按 chain/provider/市场面版本分别预注册；当前数据不支持跨链共用同一标尺。
3. 必须持续保留 baseline 未登记、baseline missing、outcome UNKNOWN/PENDING、route 不可比、无成交的分母。
4. 固定目标收益必须与路径最大收益分开；`same_pair_return=max(path)` 不能冒充 h60 return。
5. positions 只能通过 exact cohort/snapshot 对齐；同 token 或同名字匹配不足以证明相同决策时点。

本轮不能执行的结论：

- 不能宣称高 5m volume、buy ratio 或交易数是数据已经证明的最优入场阈值；可以把可解释候选预注册为新的前向 Paper/Shadow challenger。
- 不能把 marginal 中位数差解释成因果效应或 out-of-sample alpha；本报告不提供 iid 置信区间。
- 不能因 outcome/funnel 工程可运行就判定盈利、Paper 合格或 Live 合格。
- 不能评价 240 分钟表现；当前 chain 框尚无一个成熟 240 分钟结果。
- 不能用缺失/UNKNOWN 代替暴跌，也不能用 `maximum_return`、`minimum_return` 或 `peak_return_tier` 重新构造赢家。

## 8. 采集与产物

最终采集从 2026-09-06 17:01:37.926Z 到 17:01:55.198Z，共 17.27 秒。SQLite 只读查询 224 次；最慢 0.256 秒，总 SQL 时间 2.66 秒，全部低于单语句 2 秒上限。每批 cursor 均在下一批前 fetch/close；未持有跨批 read transaction。

产物：

- `scripts/analyze_token_precursors_20260907.py`：冻结合同、只读抽取和计算。
- `data/research/20260907/token_precursor_summary.json`：frontier、完整分母、运行诊断。
- `data/research/20260907/token_precursor_cohorts.csv`：两个样本框的逐 cohort 审计行；不含 raw JSON。
- `data/research/20260907/token_precursor_feature_comparison.csv`：三组暴涨对照的描述性中位数差和分层方向；无 iid 置信区间。
- `data/research/20260907/token_precursor_strata.csv`：冻结分层下的类别/特征中位数。
- `data/research/20260907/token_precursor_funnel.csv`：post-`t0` 选择流程覆盖，明确非因果特征。

这些 `data/research/20260907/token_*` 文件为 ignored 研究产物；最终数值以 `token_precursor_summary.json` 的 frozen frontier 为准，不随在线数据库继续增长而自动更新。
