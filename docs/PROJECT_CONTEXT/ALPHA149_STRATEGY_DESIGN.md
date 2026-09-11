# ALPHA149：新增策略设计与落地说明

- 生成时间：2026-09-11（UTC+8）
- 依据：用户要求"先备份 → 设计策略（含聊天中提到的 + 自行设计）→ **只新增策略**落地实现"
- 备份：`data/backups/before-alpha149-20260911T113208Z/`（登记表全量 SQL + 账本摘要 + 工作树补丁 + git HEAD `a76e4a3`）
- 代码基线：`a76e4a3`，分支 `work/2026-09-04-c2c-115000-additive-strategy`（与 origin 同步）

## 0. 硬约束（本设计不得越过）

1. **只新增**：不改既有策略的阈值、退出规则、账户与合同；不改资金期、历史、核销记录。
2. Paper-only、Live 锁定；普通成本合同沿用当前激活设置（买/卖滑点 4%、共享原池底线 1000 USD、每次成交额外费用 0）。
3. 严格前向：只使用 `observed_at ≤ ingested_at ≤ recorded_at ≤ now` 且年龄 ≤30s 的帧；缺失保持未知，不补零。
4. 不新增 HTTP 请求、不提高采集频率、不改并发；新策略复用**已经算好的**连续原池特征。
5. 每个新臂独立 `arm_id`/`canonical_id`，走既有 append API 追加到当前资金期，激活前沿=注册时点，不回填。
6. 工程完成、自然样本、经济效果三者分开报告；**不以"已注册/已通过测试"声称赚钱**。

## 1. 复用机制（为什么能做到"只加不改"）

`Runtime` 已有一个进程内连续原池引擎 `_dex_trajectory`（`src/memetrader/dex_trajectory.py`），它对每个 (token, 原池) 维护最多 192 帧、TTL 900s 的因果去重滚动序列，并派生出 40+ 个实时特征（5/15/30/60/180/300 秒窗口的收益、速度、加速度、波动、流动性变化、成交额与笔数比、买笔占比、池龄归一化加速、回撤、流动性保持率、单调性、R²、平台占比、跳涨大小/间隔变异系数、首个回撤承接等）。

- 策略信号 = 这些特征的**纯函数布尔判定**（`mechanisms(f)`）。
- 入场 = 既有共同安全门 + 严格后帧 + 独立账户/限额（`entry_filter` 数据驱动，无需新代码）。
- 退出 = 既有硬止损/追踪/最大持有 + 引擎的 `exit_reason(kind,...)`。

因此新增策略的**全部业务逻辑放在一个新文件** `src/memetrader/alpha149.py`；既有文件只做**纯加法合入**（不改变任何既有臂的行为）：

| 加法点 | 文件 | 变更性质 |
|---|---|---|
| 合并新 SPECS / 机制 / 退出 | `dex_trajectory.py` | 追加合入（约 5 行），既有臂的判定分支一字不动 |
| 汇总新策略定义 | `cohort_experiments.py` | 追加 2 行 `policies.extend(policies149(...))` |

若这两处加法被判定为"修改其他地方"，则本包不落地——因为纯 DB 追加会产生**永远不会触发的死臂**（引擎按代码内的 `SPECS` 派发信号）。

## 2. 设计原则

1. **一个臂 = 一个经济假设**，不是同一假设的参数扫描。凡与既有臂机制重合的，一律不立项。
2. **优先修已被实测证明的"永不触发"缺陷**（不是新想法）：
   - `pool_age<300s` 时 `volume_5m/volume_1h` 数学上恒等于 1 → 用引擎已有的 `*_age_normalized` 字段替代该陷阱。
   - 5 条 Dex 入口共用"买笔占比>50% + 30s 流动性≥0"两个门 → 新增臂用**不同维度**分流。
   - `dex_hot_impulse_v1` 要求同链同龄同伴 ≥3，实测 51 次触发里 50 次因同伴不足被否 → 新增臂不依赖同伴数。
3. **针对实测亏损结构**：硬止损累计 −61,432U、核销 −102,311U，而追踪止盈 +20,548U、分批止盈 +15,218U。因此新增**退出臂**（提高兑现速度）与**入场质量臂**（要求可回收空间）优先级高于再增加入场数量。
4. 规则稀疏是允许的结果；不为凑交易量放宽任何门。

## 3. 新增入场臂（10 条）

统一默认：`notional_usd=5`、`max_concurrent_positions=2`、`single_token_lifetime_entry=True`、共同安全门、`require_post_decision_observation=True`；`max_hold_minutes` 见各行。第 5 条为独立小额合同（1U/max1）。

| # | arm_id | 机制与假设 | 入场判定（全部基于既有特征） | 退出 | 与既有臂的区别 |
|---|---|---|---|---|---|
| 1 | `alpha149_uncrowded_first_frame_v1` | 最早、竞争最少的那一帧往往定价最不充分 | 该池在本引擎内累计帧数 ≤5，且 30s 窗口成立，`return_fraction>0`，`liquidity_change_fraction≥0` | 15m + 共同硬退出 | hot 要求同伴排名前 25%；本条**不要求同伴存在**，只要求"足够早" |
| 2 | `alpha149_age_normalized_ignition_v1` | 用按真实池龄归一化的活动加速，修复 m5/h1 恒等陷阱 | 30s 窗口成立且 `return_fraction > FRICTION/2`；`volume_acceleration_age_normalized>1` 且 `tx_acceleration_age_normalized>1` 且两者非空 | 15m | 既有 quiet/volume_leads 用 `compressed` 前置条件；本条**不要求压缩**，只要求活动相对池龄加速 |
| 3 | `alpha149_liquidity_expansion_lead_v1` | 钱先进池、价格尚未反映 | `liquidity_change_fraction > FRICTION` 且 `return_fraction ≤ FRICTION/2` 且 `buy_count_share>0.5` | 价格补涨后速度转负 / 15m | 既有 volume_leads 看**成交额**；本条看**流动性（池子深度）**扩张 |
| 4 | `alpha149_plateau_ignition_v1` | 长平台后的第一次真实放量（平台越长，突破越干净） | 30s 窗口成立且 `return_fraction>0`；`plateau_fraction ≥ 0.5`；`realized_volatility` 处于窗口内低位（≤ 中位）；`rolling_tx_change_ratio>1` | 15m | 既有 quiet 要求 30s 涨幅 ≤ 摩擦（更早）；本条要求**已经启动**但此前是平台 |
| 5 | `alpha149_step_pump_fast_v1` | 规律阶梯式人工拉升在短周期内可预测且可吃（"跑得快"） | `monotonic_up_fraction ≥ 0.7`、`jump_interval_cv ≤ 0.8`、`jump_size_cv ≤ 1.0`、`liquidity_retention ≥ 1-FRICTION`、`pool_age_seconds ≤ 3600` | 5m 绝对上限 + 阶梯破坏（`monotonic_up_fraction` 跌破 0.5）/ 流动性骤降 | 全新机制；既有 synthetic 只做 BSC 条件式，本条依据**路径规律性**，1U/单仓/≤300s |
| 6 | `alpha149_buy_share_extreme_v1` | 极端买盘占比 = 强吸筹且尚未被卖压对冲 | `buy_count_share > 0.75` 且 `tx_acceleration_age_normalized>1` 且 `liquidity_change_fraction ≥ 0` | 15m | 共用门只要求 >0.5；本条要求**极端**并叠加按龄归一化加速 |
| 7 | `alpha149_liquidity_add_dip_recovery_v1` | 回撤中流动性**上升**（有人加池）比"回撤后收复"更强 | 存在 `first_dip` 且 `first_dip.liquidity_retention > 1.0`；当前 30s `return_fraction > 0` | 15m + 共同硬退出 | 既有 first_dip 要求**已收复高点**（更晚）；本条在回撤被加池承接时即入 |
| 8 | `alpha149_gap_repair_continuation_v1` | 断流是数据缺口而非趋势破坏，补帧后往往延续 | `continuity_started_at` 距今 <60s 且累计帧数 ≤4 且 30s 窗口成立且 `return_fraction>0` 且 `drawdown > -FRICTION` | 5m | 既有 reawakening 要求先回撤再启动；本条针对**观察断流后重建** |
| 9 | `alpha149_friction_multiple_escape_v1` | 只在可回收空间足够时入场，直接针对止损黑洞 | 30s `return_fraction ≥ 3×FRICTION`；`liquidity_usd ≥ 3000`；`volume_liquidity > 1`；`drawdown > -FRICTION` | 硬止损收紧至 −12% + 快速止盈（+25% 触发、回落 10% 走）+ 10m | 全新：以**成本倍数 + 池深**作为入场前提，而非只看动量 |
| 10 | `alpha149_multiframe_trend_confirm_v1` | 需要更多独立帧与平滑趋势，过滤单帧尖峰 | 30s 窗口 `frames ≥ 5`；`log_price_r2 ≥ 0.8`；`residual_dispersion` 低（≤ 中位）；`return_fraction > FRICTION` | 15m | hot 只看速度与加速度；本条要求**路径平滑 + 帧数确认**（对"重复帧被当独立帧"的天然防御） |
| 11 | `alpha149_organic_short_burst_v1` | 只看最近 15 秒的真实连续放量 | 15s 窗口 `frames ≥ 3` 且 `return_fraction > FRICTION/2`、买笔占比>0.5、笔数不降 | 5m | 新增最短尺度入口（既有臂最短用 30s 窗口） |
| 12 | `alpha149_writeoff_structure_avoid_v1` | 先规避最易核销的结构（薄池 + 高 FDV） | 30s `return_fraction>0` 且流动性不降；`liquidity_usd ≥ 5000`；`fdv_liquidity ≤ 500` | 15m，硬止损 −15% | 直接针对 BSC 37% 核销率的结构成因 |
| 13 | `alpha149_mature_revival_v1` | 老池（≥6h）出现真正的新一波 | `pool_age_seconds ≥ 21600`；`return_fraction > FRICTION`；`volume_acceleration_age_normalized > 1`；流动性不降 | 30m | 不依赖回撤/叙事条件（既有 reawakening 依赖事件与回撤） |
| 14 | `alpha149_turnover_surge_v1` | 关注度（换手）先起、价格未反映 | `volume_liquidity > 2` 且 `abs(return_fraction) ≤ FRICTION/2` 且成交额/笔数双增 | 15m | 与 volume_leads 的区别：用**周转率**而非 5m/1h 比值 |
| 15 | `alpha149_multi_horizon_agreement_v1` | 多尺度同向且短尺度更快 | 15s、30s、60s 收益同为正，且 30s 速度 > 60s 速度 | 15m | 全新：跨三个窗口的一致性检验 |
| 16 | `alpha149_shallow_drawdown_impulse_v1` | 强势币不回头 | `return_fraction > FRICTION` 且 `drawdown > -FRICTION/4` 且流动性不降 | 15m | 与"峰值死亡"假设配对：浅回撤者可持更久 |
| 17 | `alpha149_elasticity_anomaly_fast_v1` | 薄池中小额资金撬动异常涨幅 | `price_elasticity_proxy ≥ 10`、`liquidity_usd < 20000`、买笔占比>0.5、`return_fraction > FRICTION` | 1U/单仓/≤300s | 把聊天中 LPI/人工盘特征落成独立小额快打 |
| 18 | `alpha149_squeeze_release_v1` | 长窗压缩后短窗释放 | 180s 波动 ≤ 一个摩擦，15s 波动放大，价格上行，流动性不降 | 15m | 全新：用长短窗口波动比表达"压缩→扩张" |
| 19 | `alpha149_smooth_organic_trend_v1` | 自然（非阶梯）趋势 | `plateau_fraction ≤ 0.2`、`monotonic_up_fraction ≥ 0.6`、`log_price_r2 ≥ 0.6`、残差 ≤ 一个摩擦 | 15m | 与 #5 阶梯盘相反的路径形态 |

## 4. 新增退出臂（5 条，共享同一冻结机会）

退出臂不含独立入场机制：它们复用**同一原池上第一个触发的 ALPHA149 入场信号**
（`decision_key` 追加臂名，`paired_opportunity_group='alpha149_v1'`），
因此与既有 dex 退出臂一样是"同机会、不同退出合同"的对照。

| arm_id | 退出语义 | 目的 |
|---|---|---|
| `alpha149_profit_decay_exit_v1` | 30s `log_velocity<0` 且 `acceleration<0` 且 `rolling_volume_change_ratio<1` | 盈利衰减即走（比现有 velocity 退出更早一档） |
| `alpha149_liquidity_shock_exit_v1` | `liquidity_change_fraction ≤ -2×FRICTION`（价格可仍为正） | 直接针对核销黑洞：池子先跑 |
| `alpha149_plateau_stall_exit_v1` | `plateau_fraction ≥ 0.5` 且 `rolling_tx_change_ratio<1` 且速度 ≤0 | 滞涨兑现，避免全损 |
| `alpha149_peak_giveback_exit_v1` | 相对**已观察到**的运行高点回撤 ≥25% | 峰值死亡假设的机械实现（不使用未来 ATH） |
| `alpha149_flat_dead_exit_v1` | 平台占比 ≥50% 且笔数 <0.5 倍且无上行速度 | 时间止损，释放资金 |

## 5. 注册与验收

1. 通过既有 `Store.append_chain_meme_trader_policy` 追加 13 个臂；`entry_filter.direction` 与 `paired_opportunity_group='alpha149_v1'`；`assessment_status='INSUFFICIENT'`、`observer_only=False`、`decision_eligible=True`、`affects='paper_only'`。
2. 定向测试：`tests/test_alpha149.py`（新文件），覆盖每个机制的触发/不触发、成本与年龄门、缺失不补零、断流清空、窗口不足不触发、退出条件与优先级。
3. 加载：一个连贯发布边界内受控重载（原 `scripts/run_paper.ps1`），核对新臂出现在 `policy_additions`、加载清单哈希、资金期与历史摘要不变。
4. 自然观察：分别报告每臂自然信号/买入/终局数与同 fill 对照；样本不足即写"待验证"。
5. 回滚：删除本次追加的 `policy_additions` 行 + 回退两处加法合入；账本摘要必须与备份一致。

## 6. 明确不做

- 不接入未来数据、不用后来涨幅做标签、不用地址白名单。
- 不修改既有 30 个基定义与 187 条追加策略的任何字段。
- 不为"看起来有交易"放宽安全门、时间门或成本口径。
- 不恢复叙事 Agent、不改采集/调度/并发、不动 UI 与存储。

## 7. 交付与验收记录（2026-09-11）

**本轮最终交付：19 条入场臂 + 5 条退出臂 = 24 条新策略。**

| 环节 | 结果 | 证据 |
|---|---|---|
| 备份 | 完成（非全库：空间不足） | `data/backups/before-alpha149-20260911T113208Z/`（登记表全量 SQL、账本摘要、工作树补丁、MANIFEST） |
| 代码 | 新增 `src/memetrader/alpha149.py`（全部策略逻辑 + 独立 `Engine`） | 既有策略文件零改动：`dex_trajectory.py`/`cohort_experiments.py`/`trajectory144.py`/`mode_learning145.py`/`recipe145.py`/`chain_web.py` 均 `clean` |
| 接线（加法） | `store.py` +32/−6（引擎路由 + 退出路由）、`runtime.py` 1 行（加载清单加入 `alpha149.py`） | `Store._trajectory_engine_for`：`v144`→trajectory144，`alpha149`→新引擎，其他→原 dex 引擎（既有取值行为不变） |
| 定向测试 | `tests/test_alpha149.py` **11/11 通过** | 含隔离性（共享族/共享引擎不含任何 alpha149 臂）、19 个机制各自触发、缺失输入不触发、退出因果门、路由集成 |
| 回归 | 与改动前**完全一致**（无新增失败） | 改动前基线：`test_cohort_experiments` 1 条旧断言失败（`assert 30 == 12`）、`test_opening141` 1 条失败；改动后仍只有这两条 |
| 登记 | 追加 24 行到当前资金期（163 → 187），24 个互异 `behavior_contract_hash` | `scripts/register_alpha149.py --apply`；`chain_meme_trader_policy_additions` 由触发器强制 append-only |
| 加载 | 受控重载完成，`runtime-loaded-manifest` 含 `alpha149.py` | 新进程 19:40:47 起：`run_paper.ps1`→`memetrader run`、`run_chain_web.ps1`→`chain-web`；`/health` `ok/running` |
| 不变量 | 资金期与历史未变 | epoch 仍为 `chain-meme-trader/funding-20260906-v002-final-1000`；账本行数/PNL 仅按备份后的自然成交增量变化（+9 成交、+2.69U） |
| 自然样本 | **尚无**（注册后数分钟内） | `alpha149_*` 持仓 0；自然信号/买入/终局待观察，**不以注册或测试冒充盈利** |

### 已知边界

1. 新臂共享既有连续原池引擎派生的特征，**不新增任何 HTTP 请求、采集频率或并发**；
   特征门决定触发频率，规则稀疏是允许的结果。
2. 退出臂与入场臂共享同一冻结机会，因此**同机会的多臂盈亏不可相加**当作独立 Alpha
   （与项目既有的同 fill 去重口径一致）。
3. 19 条入场臂使用 1U/2U/5U 不等的独立小额账户，`max_concurrent_positions` 为 1–2，
   因此新臂的**资源占用上限是已知且有界的**。
4. 本轮未做的事：未修改 UI（所以新臂在 Web 上的筛选/展示仍取决于既有面板规则）、
   未恢复 Agent、未改存储与调度。
