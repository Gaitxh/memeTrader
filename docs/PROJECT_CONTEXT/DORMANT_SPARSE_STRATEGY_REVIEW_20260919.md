# 超过12小时停流与低成交策略逐项处置（2026-09-19）

## 冻结范围与口径

- 截止：`2026-09-19T09:12:17.767319Z`；资金期：`chain-meme-trader/funding-20260906-v002-final-1000`。
- 只看当时仍可前向入场且**不是账户耗尽**的策略。纳入条件：最后一次 BUY 距截止至少12小时；或策略已运行至少12小时且累计 BUY 不多于3笔。
- 共30条：29条停流至少12小时、19条低成交（两类有重叠）、14条从未BUY。静默不自动等于故障；逐条按`信号→准入→安全→后帧→BUY`定位。
- PNL均为本资金期描述性Paper结果，不是收益保证。小样本不用于回填赢家或事后调参。

## 已确认并实施的处置

1. **策略487 / `trajectory169_trend_runner_control_v1`**：148笔后停流54.43小时，累计约+100.63U。根因是仍有ready信号，却被已退役的moonbag配对臂阻断；不是行情消失。新增`revision249_unpaired_trend_control_v1`，只移除失效配对依赖，保留原信号、退出、成本和风险。
2. **`failed_impulse_cooling_v1`**：22笔后停流93.85小时，约-59.08U。新机会要求已退役父策略先产生真实亏损，形成结构性断供。新增`revision246_observed_cooling_recovery_v1`，改用当时可见的下跌、低点、恢复和池深保持确认，不复活父账户。
3. **`dex_regime_recovered_runner_v1`**：5笔后停流156.81小时，约-46.78U。13条过期claim曾永久占用8个预留位；247已改为只有仍在成交期限内的claim占位。历史claim保留。修复后从永久容量拒绝恢复为正常等待信号，尚无盈利结论。
4. **`quiet_renewal_v1`**：4个与legacy control完全同入场的终局对照中，候选3次更差、1次相同，候选-49.538469U、控制-24.839159U，增量-24.699310U。处置为可逆暂停候选的新入场，保留历史和既有退出；`quiet_renewal_legacy_exit_control_v1`继续运行。不是账户耗尽处置。
5. **`synthetic_fast_harvest_v1`**：8次候选全部准入，全部在安全/后帧阶段过期，0 BUY。逐条证据显示BSC可选安全源没有给出可卖性事实，且同池卖出模拟均缺失。原臂及其精确证明合同不改；新增`revision255_synthetic_dex_continuity_v1`，同一BUILDING信号、同一1U注册仓位与退出，只在无明确危险证据且两帧原池身份、流动性、价格和交易连续性成立时允许Paper近似。它不是卖出模拟或安全声明，不增加接口请求。

## 其余25条独立结论

| 策略 | BUY / 静默 | 独立根因 | 当前处置 |
|---|---:|---|---|
| `cohort_opportunity_router_v1` | 45 / 23.99h | 104次准入后46 active、3 expired、55 reject；是多来源固定优先路由后的安全/机会淘汰，不是零输入 | 保留；拆分拒绝与安全终态观察，不为恢复频次降低共同门 |
| `alpha149_thin_depth_tier_v1` | 12 / 14.75h | 只覆盖30–180分钟、1k–5k流动性、合理FDV/liq且价格/池深不退的窄层；14次准入12笔BUY | 真实窄样本；约-28.18U，不扩宽，等待更多终局再决定退役 |
| `rw_quiet_reawakening_v1` | 7 / 14.66h | 需要成熟静默池重新出现交易与价格/流动性恢复；10次准入，机会本就稀疏 | 约-30.11U；不因12小时阈值放宽，继续小样本观察 |
| `archive_release_v1` | 6 / 13.92h | 归档池重新释放的事件稀少；7次准入6笔BUY，转换链正常 | 约-22.51U；保留原稀疏定义，不制造重复释放 |
| `quiet_renewal_legacy_exit_control_v1` | 4 / 112.77h | 与候选共享4次入场，之后没有新的合格静默复苏 | 作为更优退出对照保留；不把-24.84U说成盈利策略 |
| `clone_liquidity_leader_v1` | 4 / 23.99h | 24次准入中4 active、5 expired、15 reject；主要损耗在后续安全/机会终态 | 约+3.03U；保持独立安全门，继续记录终态 |
| `liquidity_leads_price_v1` | 4 / 19.91h | 正收益约+129.61U高度依赖右尾，4笔不足证明稳定性 | 已新增254金额参与广度确认臂；父臂不追参、不扩仓 |
| `clone_consensus_leader_v2` | 3 / 23.99h | 13次准入、9 reject、1 expired，双来源clone共识稀少且后段淘汰高 | 保留为稀疏证据臂；不降共识要求 |
| `clone_m5volume_leader_v1` | 3 / 23.99h | 18次准入、13 reject、2 expired；成交额leader常未通过后续安全 | 保留；不把单一成交额排名升级为买入依据 |
| `event_reawakening_v1` | 1 / 150.39h | 2次准入1笔BUY；多数观察缺同时为正的actual-flow和有效广度 | 分开记录flow缺失与非正；不移除事件/身份父门 |
| `alpha149_wide_decorr_young_v1` | 1 / 139.04h | 当前进程已有492 ready、3 broad-ready、3 signal；最新等待独立wide后帧，不是零信号 | 保留并受已上线后续帧容量保护；首笔核销-20U不足以追参 |
| `observed_set_relative_resilience_candidate_v1` | 1 / 10.73h | 未满12小时静默，但运行159小时仅2次准入、1次BUY；相对韧性事件稀少 | +6.76U只是单笔；保留，禁止据此扩大 |
| `alpha149_wide_goldendog_band_v1` | 0 | 当前进程748 ready、33 broad-ready、33 signal；最新等待独立wide帧 | 不是发现故障；继续用已修复的后续帧容量链，不放宽金狗band |
| `alpha149_elasticity_anomaly_fast_v1` | 0 | 需低流动性下价格弹性>=10、正回报且买方占优；当前无ready计数 | 真实条件稀缺；保留为零成交假设，不降低弹性阈值 |
| `alpha149_liquidity_add_dip_recovery_v1` | 0 | 必须先有加池、首次回撤、恢复、量能放大与正回报的完整序列；当前无ready | 序列输入不足；保留观测，不用单帧替代序列 |
| `alpha149_squeeze_release_v1` | 0 | 同时需要有效15秒/180秒窗、长窗低波动、短窗放大、正回报和稳定池 | 时间窗组合未出现；不缩短为同帧判断 |
| `event_clone_narrative_reawakening_v1` | 0 | 依赖严格事件身份、clone关系和微结构复苏的交集，无原生决策 | 维持WAIT；不得用营销文本或事后叙事补证据 |
| `event_recovered_narrative_runner_v1` | 0 | 是上条事件信号的恢复型别名；父信号为零，所以自然为零 | 不独立放开；父事件出现后才评估退出 |
| `experiment_quiet_reawakening_candidate_v1` | 0 | 13次`pattern_next_observation`准入但无BUY；旧8帧/600秒与自然轮换覆盖不匹配，已修为3帧/120秒；后段仍受安全/后帧 | 保留修订并观察容量保护后的新自然样本，不继续缩短静默合同 |
| `mature_new_acceptance_5u_v1` | 0 | 需要特定成熟复苏事件及两次独立确认，当前没有决策 | 真实零输入；不把普通成熟币代理为复苏事件 |
| `organic_reawakening_flow_v1` | 0 | 依赖微结构worker给出的有机资金复苏，不接受普通DEX计数替代 | 检查worker健康但保持金额流与身份门；无证据不买是正确结果 |
| `organic_reawakening_recovered_runner_v1` | 0 | 是有机复苏父信号的恢复runner，父信号为零 | 不脱离父臂单独入场 |
| `surface_lifecycle_pipeline_v1` | 0 | 仅1次准入；精确surface分类前的正actual-flow与广度父门大多未通过 | 继续分层记录surface与flow缺失，不制造BUY |
| `pressure234_mature_fast_v1` | 0 | 仅运行约19.6小时，需成熟池压力序列；处于新臂观察期 | 归类为未成熟而非故障；保持原序列和后帧合同 |
| `clone_liquidity_handoff_v1` | 0 | 只在既有clone leader关闭并发生流动性leader切换后触发；父链事件未出现 | 条件式零样本；不允许无handoff直接买入 |

## 系统链结论

- 不能用一个“12小时无交易”阈值统一降参。30条中至少有：退役依赖、过期claim占位、安全/卖出证据缺失、后续帧调度延迟、严格父事件缺失、真实窄信号、退出规则劣化七种不同原因。
- 后续帧调度已单独修复：信号进入pending时立即发布剩余期限容量保护；部署后短窗槽位等待p95由约14.64秒降至0.437秒，被动队列p95由约16.19秒降至2.30秒。它改善转换机会，不改变信号阈值或制造历史BUY。
- 本轮不触碰任何`RETIRED_DEPLETED / FAILED_ACCOUNT_DEPLETED`账户，不重置资金期，不回填交易，不开放Live。
- 下一次复核必须按本报告冻结的30条逐项比较“新准入、各终态、BUY和终局净值”，不能仅看策略总数或总BUY。

## 部署回读

- 11项相关测试通过；另一次包含已有`test_cohort_experiments.py`的宽跑出现其既有“期望12、实际32”策略数断言，不由255信号或安全代理行为造成，未篡改测试掩盖。
- `2026-09-19T09:21:58Z`首次由原监督器重载；一次误发的无索引诊断全表扫描造成I/O竞争，终止诊断并再次重载后，`09:29:31Z`实际运行PID为`35308`、532条策略。健康接口恢复running，原资金期不变，Paper-only、Live locked。
- `revision255_synthetic_dex_continuity_v1`已回读为`ACTIVE_FORWARD / INSUFFICIENT / 20U / cap16`；`quiet_renewal_v1`为`PAUSED_NEW_ENTRY`，legacy control仍`ACTIVE_FORWARD`。
- 部署时系统有3个开放仓、2个独立Token；没有重置、补单或改写历史。255尚无自然终局，不能宣称改善PNL。
