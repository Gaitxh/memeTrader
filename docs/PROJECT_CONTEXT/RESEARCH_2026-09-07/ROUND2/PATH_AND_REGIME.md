# ROUND2：增量账本、完整共享分母与固定时点路径

研究截止：**2026-09-06 18:41:40.387209 UTC**（北京时间 09-07 02:41:40）。本页是冻结描述性研究，不是策略有效性认证；没有任何已证明 alpha。全部 214 个账户、上一轮 8 个定义均保留。本研究未改应用、测试、配置、数据库、运行状态或提交。

## 结论先行

1. 当前 funding 的 214 个 arm 中，196 个有 BUY，18 个没有；12,999 个位置 / 781 个 Token，11,945 个完整终结、1,054 个仍开。原始已实现 -60,567.90 U，完整终结位置 -60,670.71 U，PF 0.2705。不同 stake、规则与执行通道不能合并成一条可交易收益曲线。
2. 上轮新 8 已部署 52.76 分钟：3 个新 entry 仍 0 BUY；其余 5 个账户是**同 20 个 cohort / 20 个 Token**，不是 100 个独立机会。baseline、profit_budget、depth_divergence、activity_failure 的自然结果完全相同；其专属退出尚未贡献差异。
3. progress_clock 的差异是真实行为差异，但不是已验证优势。双方都终结的 16 对中，2 对改善、3 对恶化、11 对相同，合计 +7.5080 U，中位差 0。改善主要来自两次 baseline 后来全损；另三次普通小赢家被提前变成小亏。
4. 五账户共同的 +42.7277 U 赢家均由 **max_hold** 退出，不能归功于 profit_budget。baseline 删掉这一 Token 后 -38.3332 U，progress_clock 删掉它后 -31.9634 U；赢家不是五次独立复制成功。
5. 赢家退出后 +5 / +15 分钟均已成熟，但冻结的 `market_mark_history` 在其退出后窗口中 **0 行**。因此没有同池后续价格证据支持“卖早了”“可以回补”或“应该继续持有”。这里是研究观察缺口，不是市场没有价格的证明。
6. 不能把“提前涨价、USD 流动性上升、买笔数占优”直接当成功先兆：12 个 baseline 亏损中，+120 秒仍有退出前观测的仅 5 个；这 5 个当时全部价格、报告流动性高于入场，买笔数占比不低于一半，最后仍亏。反之，三例普通小赢家在 +60/+120/+300 秒都还未覆盖当前往返成本。

## 1. 冻结、资源边界和复现

沿用上一轮 `data/research/20260907` 全历史冻结账本，旧截止 `2026-09-06T16:46:50.205259Z`、trade frontier 444765。只补新增 trade ID，不重新扫描全历史仓位或全量 snapshots。

| 冻结边界 / 读取对象 | 本轮值 |
|---|---:|
| trade frontier | 455132 |
| market_mark_history frontier | 2630054 |
| token_snapshots frontier | 1246285 |
| 新增 trade 行 | 10,367 = 4,586 BUY + 4,660 SELL + 1,121 WRITEOFF |
| 受影响位置主键 | 5,771 |
| 显式 entry_snapshot_id 读取 | 17,393 个唯一 ID |
| 合并后全历史位置 / definition versions | 227,892 / 25 |
| 选定 Token 路径 | 36 个窗口、2,723 行，全部查询完成 |
| 增量 SQL / 路径 SQL 总耗时 | 1.614 秒 / 0.322 秒 |
| 两阶段最长单条 SQL | 0.044 秒 / 0.033 秒 |

SQLite 使用 `mode=ro`、`query_only`、autocommit、每条语句 2 秒中断预算；trade ID、位置复合主键、snapshot ID、`market_mark_history(token_id, recorded_at, id)` 有界取数，逐批释放 cursor。未使用 Store、长事务、数据库复制、VACUUM、原始大表全扫。路径最多 20,000 行/Token，本次未触顶。后续统计全部离线运行。

增量 trade 10,262 行属于当前 final funding，102 行属于 reviewed funding，3 行属于前一 fixed funding，均按原 definition 单独归属。先固定 UTC cutoff，再取 ID frontier；仍逐行过滤 trade 的 created/recorded 时间，以及路径的 recorded 时间和 ID。位置终结状态只在 `closed_at <= cutoff` 时采用，PnL 按旧冻结 trade 加本次截止前增量累计，未采信当前 unrealized 占位值。

工件目录：`data/research/20260907_round2/`。

- `incremental_analysis.py`、`incremental_extract.json.gz`：增量原始事实；`--replay` 仅从冻结文件复算。
- `current214_statistics.csv`：214 行 arm 分母、尾部、remove-best、持有期与退出原因；无交易 arm 明确为零。
- `current214_positions.csv`、`all20_cohort_evidence.csv`：逐位置与完整 20 对共享机会证据。
- `all_history_regime_denominator.csv`：2,456 个 version × cost epoch × execution class × UTC date/hour × chain × age × liquidity × activity 分层；不丢 open 或 unknown 桶。
- `historical_version_epoch_days.csv`、`current_by_*.csv`、`current214_token_clusters.csv`：离线分层和 Token 聚类描述。
- `path_analysis.py`、`selected_paths.json.gz`、`selected_case_denominator.csv`：36 个明确 Token 的有界完整可得历史。
- `fixed_entry_checkpoints_phase_annotated.csv`：固定入场后时点，并区分实际退出前 / 退出后诊断。
- `exit_plus5_plus15.csv`、`post_exit_quote_comparisons.csv`：全部新账户位置的固定退出后时点与缺口，不选后见峰值。
- `offline_findings.py`、`offline_findings.json`：不打开 SQLite 的汇总。

旧 7 库、已拒绝工程污染 r5、缺失 ledger/指标以及旧版本归属继续以 [HISTORICAL_STATISTICS.md](../HISTORICAL_STATISTICS.md) 的隔库结果为准；本轮未重扫旧库或 backups，也未把其样本重复加入。

## 2. 成本、执行 epoch 与特征可用性

唯一已取得的显式成本 activation：`2026-09-06T14:23:26.648059Z`，key `chain-paper-execution:activation:20260906142326:998ef4a518ac`，activation snapshot 1117170。参数 buy +4%、sell -4%、额外每笔费 0 U、原池最低流动性 1,000 USD。此前记作 `legacy_activation_not_recorded`，表示实际激活口径未知；不能追扣当前成本，更不能凭版本名称推定实际历史参数。

当前新 8 每笔 stake 5 U。同报价买入再卖出：`5 × 0.96 / 1.04 - 5 = -0.384615 U`，损失 7.6923%；报价需上涨 `1.04 / 0.96 - 1 = 8.3333%` 才覆盖这组模拟往返摩擦。这不是 DEX 真实滑点、税、gas 或 amountful 可执行性证明。

按 entry snapshot provider 做**证据分层代理**，不是逐笔合同审计：

| 全历史 entry execution class | 位置数 | 解释限制 |
|---|---:|---|
| legacy main / same-frame possible | 221,002 | 底座核验当前主入口在三链存在同帧决策与成交；旧所有行不能一概称已证实同帧，也不能一概称 next-observed |
| legacy isolated receipt / next-observed unverified | 6,790 | observer receipt 归属清晰，不等于逐笔已核验严格后帧 |
| new8 strict later-observed contract | 100 | 当前新 8 的合同与赢家实例有严格 observed-after-signal/post-trigger 证据；只有 20 个共享 Token |

因此主入口账面成功不能作为新 entry 后帧可复制经济证据。全历史 `entry_snapshot_id` 均能找到、且 observed/ingested/recorded 均不晚于**实际 opened_at**，227,892/227,892 通过；这仅说明“入场时可得”，**没有证明旧 signal 决策时已经可得**。pair age 由该 as-of snapshot 内 pairCreatedAt 得到；本提取 age/activity 均无空值，但不额外保证供应商字段经济真实性。

“热度”只使用当时 `volume_5m_usd` 和笔数作为活跃度代理。没有历史热门排名、boost、社交热度、真实净买额、独立钱包、LP 实际增撤资，不从当前页面或 USD liquidity 变化倒填这些字段。

当前 funding 相同名称也不意味着全历史执行同一 policy revision；机械统计不把旧 factory 名称当成 current effective 机制。有效规则与先前同名替换问题见 [EFFECTIVE_POLICY_CORRECTIONS.md](../EFFECTIVE_POLICY_CORRECTIONS.md) 和上一轮 `FINAL_CONTRACT.md`。

## 3. 当前全部 214 与历史跨时段证据

当前 funding 从 15:29:28.508111 UTC 起，到截止约 3 小时 12 分。旧 cutoff 到新 cutoff：位置 8,413 → 12,999；完整终结 6,681 → 11,945；open 1,732 → 1,054；累计 writeoff 1,932 → 3,053；完整终结 PnL -40,134.18 → -60,670.71 U。差值同时含新增入场和原有位置自然到期，不是一个独立追加资金回报样本。

当前完整终结胜率 18.52%，位置 PnL 中位 -2.7134 U，10% 截尾均值 -6.0223 U，PF 0.2705；删最佳 Token 后 -62,574.17 U。最大盈利 Token `solana:429HAzmr…TUcci` 在 83 个 arm 出现，82 个终结贡献 +1,903.47 U；下一枚 `solana:CkhfwLfY…PqqZwP` 在 39 个 arm 贡献 +1,391.42 U。重复覆盖不是 122 个独立赢家。完整 ID 在 Token 聚类 CSV。

按执行通道保留的当前分母：

| 当前类 | 位置 / 独立 Token | 终结 / open | 终结 PnL U | 中位位置 PnL U |
|---|---:|---:|---:|---:|
| legacy main | 8,578 / 734 | 7,694 / 884 | -49,808.77 | -4.2829 |
| legacy isolated receipt | 4,321 / 302 | 4,168 / 153 | -10,890.29 | -1.3736 |
| new8 coupled | 100 / 20 | 83 / 17 | +28.34 | -1.3197 |

Token 会跨类出现，734+302+20 不能当总独立 Token 数。金额来自不同 stake / 策略账户，不能比较为相同资金效率。new8 的 +28.34 更是五账户复制后的会计总和，删共同赢家后 -185.30 U，不是五独立模型共同证实 alpha。

跨日期保留同 version 边界的典型反证：

| version / 日期 UTC | 终结位置 / Token | 原始终结 PnL U | 限制 |
|---|---:|---:|---|
| v22 / 09-04 | 54,049 / 2,384 | +7,684,951.13 | 最大单 Token +7,549,446.87；工程污染、旧成本 epoch 未知 |
| v22 / 09-05 | 99,594 / 3,767 | -368,168.64 | 同版本换日并未延续账面优势；并非时间因果实验 |
| fixed-1000 主入口 / 09-05 | 18,639 / 3,260 | -61,211.44 | activation 未记录；541 open |
| fixed-1000 主入口 / 09-06 | 1,388 / 249 | -7,500.64 | 仍属旧未记录成本 epoch |

全历史覆盖 UTC 09-03～09-06；不能将多版本短接为连续稳定 4 日实盘。当前 legacy 主入口与 isolated 通道的 15/16/17/18 UTC 入场块各自均负；新 8 的 17 UTC 块正，去掉共同赢家后也负，18 UTC 块负且未成熟。**没有发现可据此交易的钟点 alpha**。

当前三链 legacy 主入口与 isolated 各自均负。新 8 的 BSC 6 个 Token 看似正，剔除单赢家也负；不能改成“只做 BSC”。age、流动性和活跃度桶同样受样本构成与赢家驱动：新 8 的 5k～25k liquidity / 10k～100k m5 volume 桶正，恰包含该赢家，不能从这些桶直接制定门槛。全部 legacy liquidity 桶及 activity 桶的类内合计均负。

新 8 完整机会覆盖：Solana 12、BSC 6、Robinhood 2；entry-fill age <15m 19 个、15～60m 1 个（后者实际 fill age 907 秒，可能跨过 signal 的 900 秒边界，不能据 fill 桶指控 entry gate）；liq 5～25k 11、25～100k 4、≥100k 5；m5 volume 200～1k 3、1～10k 6、10～100k 7、≥100k 4。没有成熟币周期或多日期新策略证据。

## 4. 上轮新 8：全 20 个共享机会，而非赢家选例

三个 entry `boundary_retest / seller_absorption / price_then_depth` 各 0 BUY。0 样本是覆盖/观察尚无结果，不能说有效或失败，也不应为凑样本放宽契约。

| arm | BUY | SELL / writeoff | 终结 / open | 已实现 U | 胜 / 负 | 删最佳 Token U |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 20 | 11 / 5 | 16 / 4 | +4.3945 | 4 / 12 | -38.3332 |
| profit_budget | 20 | 11 / 5 | 16 / 4 | +4.3945 | 4 / 12 | -38.3332 |
| depth_divergence | 20 | 11 / 5 | 16 / 4 | +4.3945 | 4 / 12 | -38.3332 |
| activity_failure | 20 | 11 / 5 | 16 / 4 | +4.3945 | 4 / 12 | -38.3332 |
| progress_clock | 20 | 16 / 3 | 19 / 1 | +10.7643 | 1 / 18 | -31.9634 |

baseline 等四账户退出原因为 4 max_hold、7 hard_stop、5 writeoff；无专属退出。progress_clock 为 8 progress_clock、7 hard_stop、3 writeoff、1 max_hold。baseline 中位 -1.9250、PF 1.1122、截尾均值 -2.3809；progress_clock 中位 -1.0074、PF 1.3368、截尾均值 -1.5861。全部正面均值指标对单赢家高度敏感。

| cohort | baseline 终局 / PnL U | progress_clock 终局 / PnL U | 双方终结差 U |
|---|---|---|---:|
| 22107 | max_hold / +0.0497 | clock / -0.2820 | -0.3316 |
| 22109 | writeoff / -5.0000 | clock / -0.1061 | +4.8939 |
| 22111 | hard_stop / -3.9943 | 同 baseline | 0 |
| 22112 | hard_stop / -1.3197 | 同 baseline | 0 |
| 22144 | hard_stop / -2.5303 | 同 baseline | 0 |
| 22212 | hard_stop / -1.2989 | 同 baseline | 0 |
| 22248 | writeoff / -5.0000 | 同 baseline | 0 |
| 22330 | max_hold / +42.7277 | 同 baseline | 0 |
| 22512 | max_hold / +0.7357 | clock / -0.8331 | -1.5689 |
| 22770 | max_hold / +0.0534 | clock / -0.3034 | -0.3568 |
| 23273 | writeoff / -5.0000 | 同 baseline | 0 |
| 23292 | hard_stop / -2.9124 | 同 baseline | 0 |
| 23425 | hard_stop / -1.0074 | 同 baseline | 0 |
| 23452 | open | clock / -0.3883 | 未配对成熟 |
| 23453 | writeoff / -5.0000 | clock / -0.1285 | +4.8715 |
| 23590 | hard_stop / -1.1091 | 同 baseline | 0 |
| 23620 | open | clock / -0.3652 | 未配对成熟 |
| 23764 | open | open | 未成熟 |
| 23900 | writeoff / -5.0000 | 同 baseline | 0 |
| 23959 | open | clock / -0.3846 | 未配对成熟 |

两例回避全损合计 +9.7654 U，三例提前放弃小赢家合计 -2.2573 U。还有 3 例 clock 先终结而 baseline 未终结，不能拿 baseline 的 0 已实现占位值说 clock 赢或输。耦合 admission 必须五账户同时有容量，因而也不能从这张配对表声称更快退出能独立多做多少交易。

## 5. 成功与相似失败：时间顺序及反证

主分母为上述全部 20 个机会，按 baseline 截止结果分为正 4、负 12、open 4。另为每个机会寻找一个不同 Token 的负例：同 chain、同 fill-age / liquidity / activity 桶、入场相差 ≤45 分钟；按最小时间差、Token、arm 确定，已选 Token 不重复，不放宽桶。得到 16 个 legacy 负例、4 个无匹配。候选行可含跨 arm 重复，**16 是最终唯一 Token 数**；匹配本身按最终负结果选取，只能描述市场路径，不是随机对照，不与严格后帧新账户比较策略回报。

每个选定 Token 读取入场前 2 分钟至相关退出后 16 分钟（不超 cutoff）；赢家入场到退出的 160 帧由底座 agent 已核验，本研究不重复读取，只查其退出后窗口。`selected_case_denominator.csv` 中赢家 lifecycle 行数 0 明确是 delegated，不是“赢家没有路径”。有效研究报价要求同原池、VISIBLE、有限正价、有限非负 liquidity、observed≤recorded。完整可得采样历史不等于逐个 DEX 事件或所有交易渠道的完整历史。

固定 +60/+120/+300 秒各取随后 30 秒内首个满足条件的帧；选择不看结果或极值。报价若已在真实退出之后，标为 `after_exit_diagnostic`，不可作为该笔可用提前信号。成熟预算未完整落入 cutoff 的也标未成熟。

| baseline 结果层 | 固定 +60s：退出前可用 / 总数 | +120s | +300s | 关键反证 |
|---|---:|---:|---:|---|
| 4 个正结果 | 3/4 | 3/4 | 3/4 | 孤立赢家路径复用底座；三例普通赢家各时点均尚未覆盖 8.333% 往返报价门槛 |
| 12 个负结果 | 6/12 | 5/12 | 3/12 | 60s 目标前已有 5 笔终结；不能把之后报价当提前警示 |
| 4 个 open | 4/4 | 4/4 | 3/4 | open 仍右删失；300s 另 1 个预算未成熟 |
| 16 个匹配负 Token | 11/16 | 10/16 | 7/16 | 不同执行机制、后见选负例；不作胜率或因果估计 |

普通三个小赢家 +60/+120/+300 秒中位报价收益分别 +0.314%、+1.006%、+1.760%，最终靠慢速过程才小幅盈利。clock 过早退出的代价由完整配对账本直接显示，不需要峰值回测。

12 个负例中，+120 秒仍有退出前报价的 5 个中位报价收益 **+27.285%**、liquidity 比 **1.1399**；5/5 报价、报告 liquidity 高于入场、买笔数占比≥0.5，最后仍亏。这是幸存者选择后的条件组，不是说 +27% 的信号必然亏。它足以反驳“单看早期涨幅和买笔占比即可确认持续性”。5m volume / counts 是滚动聚合，不能直接差分命名为实际资金流或钱包卖压。

具体路径事实：

- **22111 快速失败**：17:49:32 入场，17:49:52 hard_stop，-3.9943 U，生命周期内研究 history 仅 2 个有效帧。60 秒退出测试无法保护已经发生的损失；不能用未来修复价格证明本可逃过。
- **22109 / 23453 时钟回避后续全损**：分别 17:56:37、18:30:14 clock 小亏退出；baseline 18:04:54、18:32:28 全损。22109 在 clock 附近仍高买笔占比，23453 附近已卖笔占优；两例不共享一条已证明的可预测撤池先兆。
- **22248 早涨后断崖**：最后一次采样 17:57:51 报价 0.0002182、liquidity 48,147.24；下一次采样 17:58:02 报价 1.487e-9、liquidity 0.12。此前持续性和表面深度并不保证下一次可退出。可得 history 不提供一个必然提前可识别的撤池信号。
- **22212 快跌后修复反例**：17:51:42 hard_stop，退出前参照报价 0.0002708；固定退出 +5 分钟首帧 17:56:52 报价 0.000442（约 +63.22%）。这只是同池报价恢复，不能证明硬止损错误、重新入场可成交或成本后有利润。

重要工程边界：`market_mark_history` 是采样图表，不保存所有 terminal/exit 决策输入。部分 writeoff 早于下一条 dust history，不能据先前较高采样报价否定核销或宣称未来函数。底座已在另一同组案例核验 `terminal_dust_pool` 有当时新鲜原池证据；本研究没有逐个核验上述三例 terminal mark，回避账面 writeoff **不等于成功预测真实撤池**。

## 6. 退出后固定 +5 / +15：完整覆盖与未知

对 100 个账户位置全部建立两个 horizon；open 无退出 anchor，目标/60 秒报价预算不成熟保留未知。成熟时只取 `target≤observed≤recorded≤target+60s` 的首个有效同池帧，不取最近峰、不向前偷用报价。EVM pool 地址忽略大小写，Solana 精确大小写。

每个机制按**20 个唯一共享 admission anchor**报告，不将 baseline 的三个完全相同副本当额外证据：

| arm / horizon | 总机会 | 有同池报价 | 成熟但无报价 | 未成熟预算/目标 | open 无 anchor |
|---|---:|---:|---:|---:|---:|
| baseline +5m | 20 | 5 | 10 | 1 | 4 |
| baseline +15m | 20 | 2 | 9 | 5 | 4 |
| progress_clock +5m | 20 | 9 | 8 | 2 | 1 |
| progress_clock +15m | 20 | 5 | 8 | 6 | 1 |

四个 baseline 等价账户的 5m/15m 覆盖完全复制。若按原始 100 账户行统计，+5m 为有价 29 / 缺价 48 / 未成熟 6 / open 17；+15m 为有价 13 / 缺价 44 / 未成熟 26 / open 17。不同退出时间产生不同观察窗口，不能把两 arm 覆盖差异当数据质量或经济优越的排名。

共同赢家 `bsc:0xd3c28b63fae40edbcca41eba73546d38fa9b8bed`、原池 `0x229248a9337ff128b2c067faa8f25eb0faaa7f18`：底座核验 BUY 452360、SELL 454104，入场报价 7.83e-7、退出报价 8.097e-6；`5/(7.83e-7×1.04)×8.097e-6×0.96-5 = +42.7277 U`。退出原因为 `market_mark_max_hold`，不是预算规则。+5 目标 18:28:36.601729、+15 目标 18:38:36.601729，两者预算均成熟、但退出后有界 history 0 行。主动跟踪停止等选择性覆盖会使退出后未知非随机，不能拿剩下有价的案例代表所有退出。

有价案例还用退出前 ≤15 秒内最后有效同池采样作**报价参照**，不是推断真实卖出 fill：22112 的 +5/+15 报价比参照约 0.7496/0.7494；22212 的 +5 为 1.6322；clock 的 22107 +5/+15 为 1.0151/1.0452；22512 为 0.9655/1.1845；22770 为 1.0216/1.0476。上下都有，且覆盖很稀疏。CSV 保留 source ID、provider、pool、observed、recorded、延迟与流动性，**没有给这些价格生成假想历史成交或重入收益**。

## 7. 值得区分的后续机制轴，而非复制上一轮清单

下面是本轮数据支持“值得反驳”的行为问题，不是完成验证的参数，也不是强凑新账户数。需要根代理再与全部 current effective 机制去重；若已有同机制则不另起新名字。旧策略和新 8 都不替换。

1. **快速下行冲击后的真实修复入场**：22212 提供一个 hard_stop 后固定时点恢复的观察，22111/22112 提供不恢复或继续低价的反例。研究状态应为下行冲击 → 旧低位/深度稳定 → 后续独立帧收复事先冻结的冲击参考位；它不同于上一轮向上突破后的 boundary retest。所有参考位须在确认时之前冻结，entry 只能下一帧。不以“跌过就买”或事后 +5m 涨幅触发；当前只有可观察修复案例，尚无充分匹配经济证据。
2. **卖笔扩张而价格暂时稳定的分配状态退出**：23453 与 22109 的先后差异提示，向买笔占优的失败（旧 activity_failure）与向卖笔占优的消耗是不同问题。可以研究滚动 count-share 状态从买优势转为卖优势、价格未创新进展而非要求立即大跌的序列；只称聚合交易笔数状态，不能称鲸鱼抛售或净资金流。22109 在 clock 时并未表现同一状态，是必须保留的反例。不要凭这两例调阈值直到都逃掉。
3. **慢而稳定的持有许可与无进展退出分开**：三例 baseline 小赢家都曾长时间未覆盖往返成本，却不等于马上应出；两个回避全损案例也不能证明每个 180 秒无进展都危险。可研究以事先定义的成本距离、持续小幅报价改善、原池留存、非恶化活动共同限制的有限延期状态，与硬风险退出隔离；不能仅修改 180 秒到另一个数字，更不能无限延期或取消 max_hold。要同时报告保留慢赢家与增加晚崩损失的代价。若当前已有等价 permission/progress 机制，结论应是对照它而非克隆。

另外，采样流动性、source 新鲜性、经济退出证据强弱是**交易资格/工程门槛**，不是额外 alpha 机制。当前不能从价格USD liquidity 计算中推导真实 LP 撤资；缺 reserve/LP amountful 数据时不伪造此类输入。

## 8. 必须保留的限制与停止线

本轮没有 MAE/MFE 新计算、没有峰值择时、没有新回测、模型搜索或阈值拟合；没有为少样本重定义成功。历史污染仅继承旧冻结已知标记，新增位置 `known_history_issue=False` **不等于 clean 审计通过**；不重写历史，也不把污染调整表当可交易证据。

路径匹配受选择偏差、相邻时段市场共振、同 Token 多 arm、不同 stake/持有规则、sampled marks 和主动退出后的覆盖丢失影响。跨日只四个 UTC 日期而且版本不断变化；新 8 仅约 53 分钟。大量 open、短期重新报价、真实路由深度、税/gas/MEV、滑点冲击、钱包独立性及真实成交仍未知。

下一轮候选如需增加，应冻结机制合同、独立信号/后帧执行、成本、观察分母与终止条件；观察新的自然 forward，不把本页参与设计的 20 个机会重复当独立验证集。当前结论到此为止：**存在可区分的退出行为与可反驳路径假设，没有已证明 alpha。**
