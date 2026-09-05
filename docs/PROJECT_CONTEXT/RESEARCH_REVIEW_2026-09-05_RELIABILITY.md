# 2026-09-05 可靠性约束下的策略研究复核

## 结论

本轮没有候选满足“可晋级为新 Paper 策略”的证据门槛，晋级数为 **0**。这不是认定任何现有策略失败，也不是停止持续研究；原因是当前退出行情存在数分钟延迟、自然前向观察时间短，且候选机制缺少足够的独立时点样本。为避免把工程延迟、同币多账户投影或研究内筛选误当成 alpha，本轮只保留研究结论，不新增策略、不启动实验。

Runner、FirstMover、Mature 是进入本轮前已经部署的三个增量策略，不是本轮新增。其完整合同位于 `Store.chain_meme_trader_v21_policies()` 和 `Store.chain_meme_trader_v22_policies()`（`src/memetrader/store.py:23019-23145`）。

## 核查范围与截止时间

- 代码：当前工作区的 V22 策略合同、Flat Compression Shadow、统一入场过滤和成交口径。
- 数据：只读查询 `data/memetrader_forward_20260830_r6.sqlite3`；仅查询三个 arm、Flat 状态聚合和最近 1000 条行情，不做全库回扫。
- 行情观测截止：**2026-09-05T06:59:18.665355Z**（最近 1000 条 `token_snapshots` 的最大 `recorded_at`）。三个策略原始持仓事件最晚约为 **2026-09-05T06:55:52.775041Z**。
- 主线程 API 页面取样曾显示 Runner 约 1315 个终局、FirstMover 约 115 个终局、Mature 约 641 个终局；该表面取样与稍后只读 SQL 的原始状态行口径/时点不同，本文不把两者强行合并。
- SQL 原始状态行：Runner 1401 closed、102 written_off、427 open；FirstMover 114 closed、1 written_off；Mature 583 closed、69 written_off、18 open。Runner 另有大量旧仓；这些计数不是独立市场事件数，同一币在多个账户的投影不能按多份独立证据计算。

## 当前成本后证据的边界

V22 单笔为 20U，买价乘 1.04、卖价乘 0.96，未计额外固定费时往返损耗约 7.69%，标的价格需上涨约 8.33% 才回本（注册合同 `src/memetrader/store.py:24728-24788`；方案口径 `EXECUTION_PLAN_RELIABILITY_AND_UI_2026-09-05.md:184-189`）。

三个新增 arm 的基础 accounting-contamination 与 market-fill-correction 行均为 0；FirstMover 的入场 `signal_age` 最大 72.867 秒，Mature 最大 89.485 秒，均在 90 秒门内。但这只能说明所查入场记录满足当前时限，不能证明退出可靠：当前实际行情已过期数分钟，退出触发、成交估值与持仓完成度可能受工程延迟影响。因此本轮不根据这些 PnL 调止损、止盈或持有期。

有限探索结果也没有支持立即制造过滤型策略：

- FirstMover 按入场时 `m5_volume_usd / m5_trades` 分为 `<2`、`2-5`、`5-10`、`>=10` U/笔，四组成本后原始平均 PnL 均为负；表现最不差的 `>=10` 组也只有 16 例、均值约 -2.10U，属于研究内小样本。
- Mature 以入场时交易数与成交量加速度是否同时达到 1 倍或 2 倍分组，各组成本后原始平均 PnL 均为负；没有证据支持把“加速度过滤”包装成新策略。

这些结果只支持“当前不能晋级”，不支持“策略永久无效”：样本窗口短、退出延迟未修复，且上述分组已经使用本批数据发现，后续必须用新的自然前向窗口验证。

## 候选复核

### 1. 成熟静默后二次确认突破：继续 Shadow，不晋级

Flat Compression Shadow 要求币龄至少 6 小时、prior55 不超过 2 笔/200U；near-trigger 为 m5 至少 3 笔或 300U，breakout 为 m5 至少 10 笔且 1000U，并要求 180 秒内两个独立样本确认（`register_flat_compression_breakout_shadow()`、`observe_flat_compression_breakout_market_batch()`，`src/memetrader/store.py:23147-23166,23243-23389`）。它明确是 `decision_eligible=false`、`affects=none`。

截至上述 UTC，状态记录为：3950 条 insufficient、203 条 flat-watch、209 条 no-breakout、1 条 near-trigger，**0 条 confirmation-pending / shadow-breakout-candidate**。没有入场候选，更没有成本后完整往返，因此不能升为 Paper。当前只需保留现有观察，不扩容、不新建 Observer。

### 2. 冲击后回撤—需求恢复：输入不完整，不实现

该机制与现有长期静默 `reawakening` 的差异是：先存在当时已知的冲击高点，再观察回撤、流动性稳定和买卖需求恢复，并作为新的 REAWAKENING cohort 入场，不能把亏损旧仓事后改名为二次入场。

当前持仓有 `highest_signal_price_usd`，但没有形成可审计的 token 级“当时高点 → 回撤 → 独立恢复确认”前向序列和固定候选分母；用现值或后见高点回筛会产生未来数据污染。因此本轮不实现。待实时性修复后，若继续研究，最低必需输入是每次样本的 `observed_at/ingested_at/recorded_at`、运行高点、回撤、流动性、m5 buys/sells/volume，以及恢复确认后的下一报价。

## 多链快速核实

实际配置（仅读取白名单字段，未读取或回显密钥）为 Paper、`chain_meme_trader_only_enabled=true`；候选链包含 Solana/BSC/Base/Robinhood，多链采集与 DexScreener surface 实际配置为 Solana/BSC/Robinhood，周期 90 秒。Base 在候选范围内，但不在当前多链采集/surface 范围。

最近 1000 条行情中：Solana 875 条，最新 `2026-09-05T06:59:18.665355Z`；BSC 94 条，最新 `2026-09-05T06:41:18.579125Z`；Robinhood 31 条，最新 `2026-09-05T06:37:55.352463Z`；没有 Base。说明 BSC/Robinhood 已有真实 DexScreener 采样，但明显晚于 Solana，不能据此声称三链等价覆盖。

公开 EVM route-quote 最近结果停在 **2026-09-03T12:22:21.380518Z**：近 62 条中大量为 BSC/Robinhood `no_official_pool`，Base 有 11 条 `EvmRouteQuoteError`，只有少量 Robinhood 有效 quoted。Robinhood registry 最近一次为 **2026-09-03T14:12:48.767628Z**，194 个资产/部署。0x aggregator 结果为 0 条，且运行环境未配置 `MEMETRADER_ZEROX_API_KEY`。

因此当前免费 API 阻断仅明确为：如要启用 0x aggregator 价格补充，需要注册并配置 0x API key；这不是 Solana/BSC/Robinhood DexScreener 采集的前置条件。Jupiter API key 也未配置，但代码允许公共限速路径（`src/memetrader/runtime.py:1187-1188,1373-1387`）。Base 的直接问题首先是未纳入当前采集范围及既有 route error，不能先归因于缺少付费 API。

## 本轮处置

- 新 Paper 策略晋级：0。
- 新 Observer/运行实验：0。
- 保留现有三个增量策略和 Flat Shadow，不改定义、不回填。
- 下一研究前置条件：先恢复并验证行情/退出实时性；Flat 出现自然确认候选，或回撤恢复具备完整时点序列后，再按独立部署起点冻结新 ID 和规则。
