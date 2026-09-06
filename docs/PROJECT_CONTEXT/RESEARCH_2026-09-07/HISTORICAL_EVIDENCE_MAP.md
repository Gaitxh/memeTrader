# memeTrader 全历史策略与证据地图（2026-09-07）

状态：历史目录与语义边界已完成；经济统计由同目录 `HISTORICAL_STATISTICS.md` 独立承担。本文件不运行回测、不扫描数据库、不根据当前页面重算历史，也不作策略盈利裁决。

## 1. 结论先行

1. 当前 `funding-20260906-v002-final-1000` 的 206 个策略只是最新部署切面，不是全部历史。ChainMemeTrader 至少有 v1–v22、三个显式资金期，以及资金期内追加的 79 个策略；更早还有信息优先、纯链上、买后信息、固定时点、路线、持有人、流动性存活等 Shadow/Paper 账本。
2. 仓库内没有可作为独立证据层的“历史回测报告”。`docs/HISTORICAL_TESTING.md` 明确把历史案例限定为身份、时序和未来数据拒绝测试；`CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.*` 也明确是对既有严格前向行的只读汇总，不是回测或参数搜索。
3. 目前唯一完整、冻结、机器可读的 ChainMemeTrader 历史宇宙导出只到 v1–v13：156 个 `definition_version × arm_id` 实例、124 个完整行为合同，生成于 2026-09-04。它不能代表 v14–v22、2026-09-05/06 资金期或 79 个追加臂。
4. v14–v17 曾把部分历史入场合同泛化为 market-visible，v18 才恢复“能复刻则复刻、不能复刻则不造交易”，v19 为 38 个不可复刻合同建立明确 DexScreener successor ID。跨这些版本直接合并 PNL 会混合不同策略语义。
5. v6、v7、v8、v9、v10、v16、v19 及 2026-09-05/06 资金期均有已确认工程或因果污染。工程 PASS、测试通过、注册成功、自然成交出现、多个账户投影或高累计收益都不等于 alpha、可实现利润或 Live 资格。

## 2. 证据等级与取用规则

|等级|含义|本轮用途|
|---|---|---|
|A：冻结机器产物|JSON/HTML 中含生成时间、版本、合同、frontier 或逐项行|可直接作为指定截止时点的目录或统计输入，但不得越过其 scope|
|B：公开阶段报告|项目内公开 Markdown/`SYSTEM_UPDATE_HISTORY.json`，记录问题、改动、验证和部署时点|用于版本语义、污染、资金和部署边界；数值仍须服从报告自己的截止时点|
|C：源代码注册定义|`src/memetrader/store.py` 及各实验 policy factory|证明“代码能够定义什么”和当前 ID 谱系；不能单独证明生产已注册、自然覆盖或盈利|
|D：本机运行附件|`data/backups/`、`data/tmp/` 中的精确已知文件|可用于复核原始证据，但不进 Git；本轮只核验文件存在/大小，不读取数据库或私有明细|
|E：仅文字声称/当前未导出|连续性文档提到的 API 截面、DB 表或旧运行数字，但没有对应冻结公开产物|必须标为待独立抽取或不可取得，不能填入最终经济结论|

共同因果约束：只使用决策时已经满足 `observed_at <= ingested_at <= recorded_at <= decision_at` 的证据；同一 token/cohort 被多个策略账户投影时不是多个独立市场样本；不同版本、资金期、成本、流动性门槛和执行合同不直接合并。

## 3. 可发现的权威文件与实际边界

|日期|文件/位置|实际覆盖|不能证明什么|
|---|---|---|---|
|2026-09-07|`docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/REVIEW_SCOPE.md`|本轮全历史重评的授权、当前期和完成标准|本身不是统计结果或策略结论|
|持续更新|`docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md` 顶部当前态；`docs/PROJECT_CONTEXT/SYSTEM_UPDATE_HISTORY.json`|当前权威状态及 2026-09-05/06 部署、污染和修复时间线|旧段落是历史截点；不能把某次短窗运行数字当长期 SLA|
|2026-09-04|`docs/PROJECT_CONTEXT/CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json`、`.html`|v1–v13 的 156 个实例、124 个行为合同、合同指纹、失败墓碑和当时的候选分类；文件元数据明确只读、无回测|不含 v14 以后；当时的 11 个 Shadow 候选不是 Paper/盈利候选|
|2026-09-04|`docs/PROJECT_CONTEXT/CHAIN_MEME_TRADER_DAILY_LEARNING_REPORT_LATEST.json`、`.html`|同一 2026-09-04 截面的日报选择与数据健康|文件名虽为 `LATEST`，但 `report_day_asia_shanghai=2026-09-04`；不能当 9 月 7 日当前结果|
|2026-09-04|`scripts/generate_historical_strategy_universe.py`|上述 v1–v13 导出的可复核生成逻辑：版本实例、行为合同、尾部/集中度/时间块和墓碑分类|脚本存在不等于报告已覆盖新版本；本轮未执行它|
|2026-09-05|`docs/PROJECT_CONTEXT/RESEARCH_REVIEW_2026-09-05_RELIABILITY.md`、`RELIABILITY_FUNDED_DEPLOYMENT_RESULT_2026-09-05.md`、`BROAD_COST_COVERAGE_SCALEOUT_RESEARCH_2026-09-05.md`|v22/127、首个固定 1000U 资金期、可靠性/覆盖、成本覆盖 runner 的设计依据及污染排除|设计证据不是新策略的反事实收益；短窗运行不是成熟经济结论|
|2026-09-05|`docs/PROJECT_CONTEXT/POOL_IDENTITY_AND_UI_REPAIR_2026-09-05.md`、`HELD_CATALOG_AND_CAPITAL_CREDIT_2026-09-05.md`|原池身份、持仓行情、资金补偿与研究隔离边界|补偿不是盈利；工程修复前后的收益不可无条件拼接|
|2026-09-06|`docs/PROJECT_CONTEXT/FOUNDATION_HISTORY_REPAIR_2026-09-06.md`、`MISSING_WRITEOFF_EVIDENCE_2026-09-06.json`|已确认异常生命周期 VOID、补款/资金依赖、缺失核销证据与全账期检索修复|未知核销不能被推定为错误或自然亏损|
|2026-09-06|`docs/PROJECT_CONTEXT/EVIDENCE_COMPLETION_2026-09-06.md`、`NINE_DIRECTION_IMPLEMENTATION_2026-09-05.md`、`L0_OUTCOMES_RELEASE_2026-09-06.md`、`COHORT_WALLET_PROBE_RELEASE_2026-09-06.md`|追加实验的输入接线、frontier、自然首窗及明确覆盖缺口|工程可达、首笔成交或局部自然样本不证明经济优势|
|2026-09-06|`docs/PROJECT_CONTEXT/STRATEGY_REVISION_CANDIDATES_2026-09-06.json`、`STRATEGY_VERSION_REVIEW_2026-09-06.md`|旧资金期对 122 个候选槽位的冻结审查/换版候选|候选矩阵不是部署证明；混合过历史门槛期，不能视为反事实回测|
|2026-09-06|`docs/PROJECT_CONTEXT/STRATEGY_V002_EXECUTION_TABLE_2026-09-06.md`、`IMPLEMENTATION_DELIVERY_2026-09-06.md`|122 个 V002 的逐 ID 规则变化、部署 frontier、84 个未改规则槽位和三段版本历史|122 个修订不等于 122 个独立入场假设，更不等于 122 个 alpha|
|长期说明|`docs/PAPER_FORWARD_EXECUTION_CN.md`、`PAPER_STRATEGY_FORWARD_LEARNING_CN.md`|Paper 的前向/成本/成熟门原则和早期三策略学习框架|文档中的早期成本/Phase 状态不能覆盖后续 ChainMemeTrader 合同|
|长期说明|`docs/INFORMATION_FIRST_SHADOW_CN.md`、`SOLANA_HOLDER_BREADTH_SHADOW_CN.md`、`docs/TOKEN_CONTEXT_FORWARD_LEARNING_CN.md`|信息优先、持有人宽度和 Token Context Shadow 的冻结设计及解释限制|描述性 Shadow 不产生交易授权、因果结论或盈利证明|
|历史测试|`docs/HISTORICAL_TESTING.md`、`research/historical_casebook.json`|历史事件/同名币/未来字段拒绝的测试案例目录；文件当前存在|不是可盈利回测数据集，旧网页的 `published_at` 不能替代本机 `observed_at`|

本机附件存在性已于 2026-09-07 只读核验：五个明确命名备份均存在——`before-funded-period-20260905-0737.sqlite3`、`before-position-void-20260906T073326Z.sqlite3`、`before-reviewed-funding-20260906T1421Z.sqlite3`、`before-all122-funding-20260906T1450Z.sqlite3`、`before-final-v002-funding-20260906T152754Z.sqlite3`；四个明确命名的 `data/tmp` 证据文件（VOID manifest/receipt、184-arm funnel、post-VOID negative-cash dependency）也存在。它们是本机恢复/核查资产，不是公开报告；本轮没有读取其数据库或明细内容。

## 4. ChainMemeTrader 全版本家族覆盖表

v1–v13 的注册时间和样本边界来自 2026-09-04 冻结 JSON；v14–v22 的合同来源是 `src/memetrader/store.py` 与公开连续性记录。对没有独立公开激活快照的版本，日期只标项目日，不臆造时分秒。

|版本家族|日期|策略数/结构|关键语义变化|历史证据资格与位置|
|---|---|---|---|---|
|v1 `v1-12-forward-arms`|2026-09-03|12 个固定/动态退出臂|20U、4%滑点、0额外费；Jupiter amount-specific 最低输出；主要是退出臂目录|冻结报告中无决策/终局；仅谱系与合同可复用|
|v2 `v2-12-evolution-stages`|2026-09-03|12 个演化阶段账户|从 Shadow、路线、固定 Paper 到动态/成本/安全的阶段式策略|冻结报告只有极少参与，不能作收益结论|
|v3 `route-truth-separated`|2026-09-03|12|路线真值与其他语义拆分|严格前向但样本稀疏；保留为 superseded baseline|
|v4 `paired-vault-rug-truth`|2026-09-03|12|配对 Vault/rug 真值|严格前向；后续合同取代，不跨版本合并|
|v5 `order-fill-kernel`|2026-09-03|12|显式 signal→intent→next quote fill→position；旧仓跨版本继续退出|冻结报告中 11 个成熟经济失败、1 个可复用；这是旧合同结论，不推广到后续执行核|
|v6 `entry3-exit4-forward-matrix`|2026-09-03|3 入场 × 4 退出|broad/flow/reawakening 与 fast/balanced/peak/research；共享一次权威 fill 投影|负现金 epoch，全部为工程失败；现金与 PNL 禁止作经济证据|
|v7 `capacity-cash-forward`|2026-09-03|12|尝试修复容量/现金|调度互扰，全部为工程失败；机会暴露不可比|
|v8 `sla90-cash-forward`|2026-09-03|12|90 秒信号执行 SLA、Jupiter 剩余量估值|把单池直接曲线容量提升为全市场终态，12 个实例均不可比|
|v9 `local-observer-forward`|2026-09-03|12|本地观察器和重试|单一 no-route 被当全损，12 个实例均不可比|
|v10 `route-surface-forward`|2026-09-03/04|12|路线与持有表面分离|最弱账户现金 veto 阻塞同族其他账户，全部为工程失败|
|v11 `independent-arm-cash-forward`|2026-09-04|12|每策略独立 1000U 现金；投影只到合格账户|现金隔离机制可复用；持续 Jupiter 估值随后被轻量 market mark 替代|
|v12 `dexmark5s-paper-exit-forward`|2026-09-04|12|Jupiter BUY，SELL 可回落到可见 Dex mark；5 秒估值|Jupiter BUY 覆盖依赖导致抽样偏差；不能与 v13 入场直接比较|
|v13 `dexmark5s-paper-buy-sell-forward`|2026-09-04|12|买卖均切到 DexScreener market mark，双侧各 4%|冻结报告当时 0 个 Paper 候选、11 个 Shadow 候选；不能被后续结果倒推改判|
|v14 `all-canonical-strategies-forward`|2026-09-04|124 个行为合同|把 v1–v13 的 124 个 canonical 合同装入共享 DEX-mark Paper 核|代码/注册谱系存在；2026-09-04 报告中的 v14 只是 draft，不能用该报告证明后来激活|
|v15 `all-canonical-strategies-clean-forward`|2026-09-04|124|用户要求清洁新 epoch，合同沿 v14|新 frontier，不回填；缺独立冻结公开全量结果|
|v16 `dex-pair-before-after-sell-forward`|2026-09-04|124|卖出触发前后同池可见才以后帧成交；连续缺失曾定义核销|后续确认存在延迟快照入场污染；v16 经济结果必须隔离|
|v17 `fresh-entry-before-after-sell-forward`|2026-09-04|124|增加入场快照最大年龄，清除 v16 延迟入场污染|仍继承 v14–v17 的历史合同泛化问题；不能称忠实复刻|
|v18 `historical-fidelity-forward`|2026-09-04|124：86 可运行 replica + 38 `COVERAGE_UNAVAILABLE`|恢复源入场语义；缺路线/安全/买后研究输入的合同只展示、不造交易|是忠实性边界基线；不可用即覆盖结果，不是策略失败|
|v19 `dexscreener-successors-clean-forward`|2026-09-04|124：86 replica + 38 明确 successor|不可复刻合同用新 ID 的 Dex 可见代理，保留来源 lineage，不冒充原合同|遗留 Jupiter exit raw-decimal 污染使 v19 结果失效；successor 也不是原策略复刻|
|v20 `market-only-accounting-corrected-clean-forward`|2026-09-04|124|策略逻辑不改；修正 market-only 数量/估值公式，不再用旧 Jupiter raw 结算|v19 污染后的清洁工程基线；无独立冻结全量经济报告|
|v21 `additive-principal-lock-runner-clean-forward`|2026-09-04|125 = 124 + 本金回收 runner|+80% 时卖 60%，以真实累计回款判断回本，40% runner；同时有 observer-only Vault Shadow|公开连续性记录 frontier 817128；工程/首窗通过不证明 runner 盈利|
|v22 `additive-first-mover-mature-control-multichain-forward`|2026-09-05|127 = 125 + 早期爆发 + 成熟延续|扩至 Solana/BSC/Robinhood；20U、双侧4%、0额外费；两个有行为差异的新臂|`RESEARCH_REVIEW_2026-09-05_RELIABILITY.md` 和后续资金报告；旧 v22 仓继续在旧期退出|
|`funding-20260905-fixed-1000`|2026-09-05 07:37:08Z|初始 127，每策略 1000U；其后同资金期增量加入 79 臂至 206|恢复固定现金门；新增臂各自从真实 deployment frontier 开始，旧 127 不重置|当前 122 候选的主要旧期审查来源；内部含门槛变化和工程 VOID，必须按时间/污染分段|
|`funding-20260906-reviewed-1000`|2026-09-06 14:54:54Z|206；122 个槽位进入当时版本化 V002，84 个规则不改|独立 1000U 新期，旧期停止新入场但旧仓继续退出|后续又发现负流动性门和 SQLite 锁序问题；作为中间 V002 期保留，不与最终期拼接|
|`funding-20260906-v002-final-1000`|2026-09-06 15:29:28Z|206；122 个最终 V002、84 个未改规则|修正 167/168 退出、密采样确认、125 回本语义、负流动性肯定门和共享 SQLite 死锁|当前生产期；截至地图截止仍受免费源、原池覆盖和 stale/unknown 约束，不能称成熟盈利|

## 5. 当前 206 的注册构成（不是 206 个独立 alpha）

当前代码入口在 `src/memetrader/runtime.py`，基础/追加注册和 version 常量在 `src/memetrader/store.py`。以下数量来自 policy factory 的静态合同与公开 127+79 交付对账；未读取生产 DB。

|组成|数量|源定义|机制边界|
|---|---:|---|---|
|历史 replica / Dex successor 基座|124|`Store.chain_meme_trader_dex_successor_policies()`|86 个尽量忠实 replica；38 个明确 successor，不可冒充原路线/安全/研究合同|
|v21 本金回收 runner|1|`Store.chain_meme_trader_v21_policies()`|真实累计回款决定是否回本，不用浮盈代替|
|v22 早期爆发、成熟延续|2|`Store.chain_meme_trader_v22_policies()`|早期尾部捕捉与成熟延续对照|
|成本覆盖分批兑现|1|`Store.chain_meme_trader_cost_coverage_scaleout_policy()`|历史高点回吐只支撑假设，不能反事实成交|
|九方向 pattern 候选/对照|18|`forward_patterns.experiment_policies()`|participation、quiet、breakout、reclaim、runner、support、migration、narrative、panic；共享候选不独立|
|资金/生命周期假设|18|`capital_policies.capital_policies()`|Vault、回本、延续、迁移、恢复、资金速度/广度、creator/bundle、ranker、regime、竞态、Direct LP、官方事件等|
|结果驱动单机制|2|`forward_patterns.result_driven_policies()`|单槽 conditional runner；breakout earn-the-hold|
|第二次独立讨论|8|`capital_policies.second_discussion_policies()`|2 个事件/表面方向 + 3 组各候选/对照退出|
|机会型小额入口|4|`capital_policies.opportunity_policies()`|净流未启动、流动性领先、止损收复、无 CA 事件资金 leader|
|时长竞态|1|`capital_duration_risk.duration_risk_policy()`|成熟模型/覆盖不足时 WAIT|
|Direct LP 指定量确认|1|`capital_policies.direct_lp_amount_specific_policy()`|quote 是入场前证据，不是 Jupiter 成交|
|证据补全|5|event actual flow、migration absorption、first-observed buyer、common funding、issuance holder factories|代理与完整证据严格区分；多数只支持 Solana/特定 surface|
|周期与波动率|4|`forward_patterns.cycle_and_volatility_policies()`|两机制及各自对照；5U，已有 L0 序列|
|纯 L0 退出|4|`l0_experiments.l0_experiment_policies()`|延续失败、回本后恶化及对照；20U|
|同机会 cohort|5|`cohort_experiments.cohort_experiment_policies()`|流动性/成交量 leader、相对韧性、handoff；5U，按 episode 去重|
|分段探针|3|`staged_probe.staged_probe_policies()`|20U一次、5U对照、5U Paper + 15U Shadow|
|成熟新接受|1|`mature_acceptance.mature_acceptance_policy()`|独立确认窗，5U|
|钱包观察候选/对照|4|`wallet_observer_experiments.wallet_observer_policies()`|地址不是人；没看到命中不能证明没交易|
|合计|206|127 基座 + 79 追加|同一机会可投影到多个账户；机制、参数变体和账户数都不能当独立样本数|

122 个 V002 也不是 122 个独立机制。`STRATEGY_V002_EXECUTION_TABLE_2026-09-06.md` 明确：32 个历史 reawakening 槽位共享新的 mature-flow-burst 入场，只比较四类退出；17 个缺原输入的槽位使用 7 个名称但只有 6 种实际 L0 形式；其余包含主通道/退出和资本释放的重复机制应用。最终报告必须按“行为合同 hash + 入场机会/cohort + 退出差异”归并，而不是按 UI 槽位求显著性。

## 6. ChainMemeTrader 之外的历史 Paper / Shadow 谱系

`src/memetrader/store.py` 中存在下列版本化注册/表命名空间。这里的“存在”只证明代码/表合同可定位；除非右栏有冻结公开报告，不能推定自然结果完整。

|谱系|代表版本|已有证据/报告|可复用与限制|
|---|---|---|---|
|早期三策略产品模型|`information_plus_token`、`token_only`、`token_then_information`；`three-strategy-families-policy-arms/v1`|`PAPER_STRATEGY_FORWARD_LEARNING_CN.md`、`PAPER_FORWARD_EXECUTION_CN.md`、旧连续性快照|策略3是策略2同入场、只隔离买后信息，不是第三个选币器；旧版曾有每 fill 0.40U 等成本，不能倒灌当前 0U 设置|
|Event/Token Context 分母|`shadow-event-followup/v3`、`shadow-event-admission/v2`、`token-context-*`|`TOKEN_CONTEXT_FORWARD_LEARNING_CN.md`|WAIT/REJECT/CANDIDATE 和 missing 都保留；LLM 结果不直接控制数值交易|
|信息优先 Shadow/ILG|`information-first-shadow/v1`、active outcome v2、`information-first-ilg/v1`|`INFORMATION_FIRST_SHADOW_CN.md`|描述活动越界/15/60/240 结果；`affects=none`，低活动不等于未定价|
|KOL addressability|base v1/v2/v3、route v1/v2|公开连续性记录：v1 历史保留，base v2 首 cohort 前废弃，route v1 首 attempt 前废弃，route v2 绑定 v3|不可变 attention point 与 exact identity 可复用；无交易授权|
|Token universe/funnel/outcome|forward outcome、funnel、fixed target execution、Jupiter quote/validity|`ARCHITECTURE_AND_DATAFLOW.md` 及相关学习文档|固定 0/15/60/240 目标、失败/missing 分母和 next-observed 语义可复用；不是策略成交|
|纯链上 Shadow 与路线|`onchain-only-shadow/v2`、Jupiter quote v2、EVM aggregator/route quote v1|项目研究/连续性报告；无单一全量冻结导出|Solana Jupiter minimum output 与 EVM fixed-block quote 必须分链；indicative 不能升级为 firm/live|
|流动性/表面安全|`liquidity-survival-shadow/v3`、market-surface safety、pretrade rug safety、route relation|`SAFETY_AND_INVARIANTS.md`、`ARCHITECTURE_AND_DATAFLOW.md`|exact pool、provider failure != pool death、持有表面 != 聚合路线，可直接作为硬因果边界|
|持有人/创建者|`solana-holder-breadth-shadow/v1`、`creator-launch-risk-shadow/v1`|`SOLANA_HOLDER_BREADTH_SHADOW_CN.md`|owner/address 不是独立人或 smart money；本机历史是覆盖下界|
|Vault/flat observers|v21/v22 vault-flow shadow、flat-compression-breakout shadow|2026-09-04/05 连续性与可靠性报告|`decision_eligible=0 / affects=none`；可形成候选机制，不能回写旧 Paper|
|执行与退出观察|dynamic exit challenger、held-account monitor、reverseability、deferred retry、stage4 paired challengers|`ARCHITECTURE_AND_DATAFLOW.md`、2026-09-03/04 公开研究规范|可复用 intent→later quote/fill、剩余数量、退避和终态语义；旧执行合同结果必须版本隔离|

当前缺口：仓库没有一个机器可读文件同时枚举这些 Shadow namespace 的 registration、activation、attempt、result、missing 和成熟状态。最终重评必须从只读 DB 按各自 registration/frontier 另行抽取；“有常量/有表/有测试”不等于“有自然样本”。

## 7. 关键语义、资金与阈值变更

### 7.1 执行语义

- v1–v11 重点使用 amount-specific Jupiter minimum output；v12 变为 Jupiter BUY + Dex-mark SELL fallback；v13 起普通 Paper 转为 Dex mark 买卖。
- v16 起要求卖出触发前后同原池可见；v17 增加新鲜入场；v20 修正 market-mark 数量/估值公式。2026-09-06 用户最终保留轻量 market-price/original-pool before/after 模型，不把深度冲击或 exact quote 设为普通 Paper 前置条件。
- 核销的显式 SELL intent 是操作指令，不是真实成交回执；Paper writeoff 也不是实盘可卖性证明。
- missing、failed、stale、429、兄弟池或一个 provider 的 no-route 均不能单独证明池死亡。只有肯定、同池、时点有效的低流动性/终态证据才能触发对应规则。

### 7.2 成本与资金

- Chain v1–v22 的主合同通常是 20U、买卖各 4%、0 额外每 fill 费用、每策略独立 1000U；追加实验中明确存在 5U 臂。不能把一个统一名义金额覆盖所有臂。
- 更早的三策略公平期曾使用双侧 4% 加每次实际成交固定 0.40U；更早学习文档还讨论 60bps/125bps 场地费上限。这些是不同合同，不能用当前 0U 重算。
- v22 曾短暂启用 `unconstrained_research_notional` 取消未来现金 veto；2026-09-05 07:37Z 新资金期恢复每策略 1000U 固定现金。资金不足是机会未成交原因，不自动证明入场机制错误。
- 三个显式资金期各有独立起点。旧期停止新 BUY 后仍允许原开放仓按原合同退出，卖出收入留在旧期；禁止把旧现金、曲线或仓位并入新期。

### 7.3 原池流动性门槛

- 2026-09-05 初期存在“买入仅要求正价格、退出以同池 `<1U` 核销”的不一致，造成浅池线性成交污染；随后入场/退出底线统一到 1U。
- 2026-09-06 09:24Z 共享门槛提高到 1000U；10:05Z 用户一度改为 100U；14:20Z 最终可编辑设置的默认值又为 1000U。历史原因码和成交不回写。
- 因此 `funding-20260905-fixed-1000` 不是一个同质门槛 epoch。统计必须按实际 activation/设置时点分段；不能把门槛变化后的表现归因给策略参数。

## 8. 已确认污染与不可比较区间

|事件|影响|处理/统计边界|证据位置|
|---|---|---|---|
|旧 r5 promotional listicle false positives|推广榜单被当成可交易信息，形成拒绝性 Paper 证据|r5 不并入 r6/当前 performance；只能用于误报机制复盘|`AGENTS.md`、`FORWARD_FALSE_POSITIVE_AUDIT_20260830.md`|
|v6 负现金 epoch|账户/收益真值破坏|全部经济结果无效；仅保留策略定义|2026-09-04 历史宇宙 JSON/HTML|
|v7 scheduler interference|曝光与成交机会受执行调度互扰|不比较策略优劣；保留参数|同上|
|v8 direct-curve terminal|把单池容量当全市场终态|终局/核销无效|同上|
|v9 no-route-only writeoff|单一 provider no-route 当全损|终局无效；路线观察仍可复用|同上|
|v10 weakest-arm cash veto|最弱账户阻塞同族账户|参与分母系统性偏低|同上|
|v14–v17 historical contract distortion|历史路线/安全/研究入场被泛化为 market-visible|不能称历史复刻；v18/v19 后才分为 replica/明确 successor|`store.py` v18/v19 注册说明|
|v16 delayed snapshot entry|过期快照仍可能入场|v16 经济样本隔离；v17 新 frontier 修正|`store.py` v17 stop/reset reason|
|v19 legacy Jupiter exit raw decimal|synthetic/legacy raw 数量污染 market-only 结算|v19 结果失效；v20 策略不改、工程重启|`store.py` v20 `invalidated_previous_results`|
|低流动性线性成交生命周期|浅池按线性价格产生不可信买卖/核销|2026-09-06 已 VOID 573 个生命周期、62 策略、1155 条腿；原始行/归档保留，正式研究排除；这些计数是账户投影，不是独立币数|`FOUNDATION_HISTORY_REPAIR_2026-09-06.md`、本机 VOID manifest/receipt|
|历史持仓行情延迟补偿|已确认更新延迟造成损失，产生 capital credits；另有缺原始证据的 writeoff|补款不是 PNL；未知案例不猜损失、不反事实补价|`HELD_CATALOG_AND_CAPITAL_CREDIT_2026-09-05.md`、`MISSING_WRITEOFF_EVIDENCE_2026-09-06.json`|
|撤销异常回款后的负现金依赖|后续 BUY 曾依赖后来被 VOID 的错误回款|保留实际历史，但不能补写反事实资本或恢复研究资格|`FOUNDATION_HISTORY_REPAIR_2026-09-06.md`、本机 post-VOID dependency JSON|
|负 liquidity 被当作“非已知低于门槛”|中间 V002 期出现错误 BUY|81 条、53 臂、3 cohort、2 token 均为重启前工程污染；最终期采用肯定式有限非负/达门槛检查|`CURRENT_OBJECTIVE_AND_PLAN.md` 顶部、`SYSTEM_UPDATE_HISTORY.json` final V002 条目|
|共享 SQLite writer 锁序死锁|生产主循环一度停滞，影响曝光/退出时序|停滞窗不评价策略；最终期修复共享 writer 线程归属|同上|
|正价但 liquidity 缺失被计成功|刷新 success 时间、清补源队列并覆盖旧完整帧|2026-09-07 修复后缺字段只记失败并保留旧帧时间；此前受影响时段的数据新鲜度须保守解释|`SYSTEM_UPDATE_HISTORY.json` 20260907 条目|

未确证项必须保持未确证：历史 missing writeoff、免费源覆盖缺口、缓存年龄、Pons/Four/429 限制、未知 holder/creator/flow，并不自动等于自然失败、rug、零收益或系统漏买。

## 9. 可复用策略机制（仅候选积木，不是已证 alpha）

### 9.1 应保留的因果/执行机制

- 不可变 registration + activation frontier + 行为合同 hash；旧仓按旧期退出，新策略只从自己的 frontier 开始。
- 同一机会的候选/对照共享输入，但账户、现金、退出和结果独立；分析时按 token/pool/cohort/episode 聚类。
- trigger 与 fill 分离：信号帧不能成交，必须等待严格后续同原池帧或合同指定 quote。
- exact chain + token + original pool 身份；持有表面、聚合路线和兄弟池三者不互相替代。
- unknown/failed/stale 与 confirmed terminal 分离；失败和空轮进入分母。
- 真实剩余数量、分批卖出、累计净回款、running high 和 next-frame exit；不使用后来 ATH 重建退出。
- 广覆盖主通道与低频隔离 observer 并存；证据稀疏不通过放松时序/身份/协议真值强造交易。

### 9.2 值得重新评估的行为假设

- broad launch、flow burst、成熟 flow reacceleration 和 quiet reawakening 的覆盖/质量差异。
- fast escape、balanced harvest、peak guard、成本覆盖分批、真实回本 runner、L0 连续恶化退出。
- 首波深重置后二次启动、波动率归一化资金压力、回撤收复/恐慌收复、流动性领先价格。
- 同机会 leader/relative-resilience/handoff，及 5U/20U/分段 Shadow 的容量与风险差异。
- exact event + post-event actual flow、migration absorption、钱包/参与者/发行后 holder 派发；前提是实际覆盖完整，且地址不冒充独立人。
- creator frequency、holder breadth、Vault regularity/unwind、surface lifecycle 适合作为分层或退出风险证据；在自然样本成熟前不升级为统一硬门。

### 9.3 不应复活的机制

- 用单一 no-route、一次请求失败、零值或不同池替代确证死亡池。
- 用最弱账户现金否决其他独立账户，或把账户副本数当独立市场样本。
- 用 current metadata、后来 holder/ATH/赢家、今天搜到的旧网页补历史入口。
- 用 synthetic `amount_raw` 当链上真实 mint raw，或用 stale Dex 高价结算 exact reserve collapse。
- 因零成交而放松身份、时序、原池、协议有效性或 next-frame 约束。

## 10. 明确遗漏与最终重评前的待补项

1. **v14–当前期没有单一冻结全量导出。** 需要 `HISTORICAL_STATISTICS.md` 按 registrations/activations/stops/additions/settings frontier 一次性只读抽取；本地图不能替代该统计。
2. **当前 206 没有公开的全员逐策略历史绩效文件。** V002 表只覆盖 122 个修订候选，84 个未改规则臂仍需从有效定义和账本抽取；不能把“未改”解释为“表现良好”。
3. **Shadow 没有统一结果包。** 多数 namespace 只有注册常量、表结构、设计说明或阶段截面；必须分别报告注册、attempt、result、missing、deadline 和影响级别。
4. **没有独立回测文件。** 如果后续重评使用历史行情做研究标签，必须明确标成事后标签/机制研究，并在新规则冻结后重新前向验证；不能补造 backtest PASS。
5. **版本激活精确时间不全在公开文件。** v14–v20 的精确 `registered_at/activated_at/stopped_at/frontier` 应从只读注册表获取；当前表故意不臆造。
6. **资金期内阈值异质。** 至少按 1U、1000U、100U、最终1000U及费用设置 activation 分段；UNKNOWN PNL 不按 0，VOID/capital credit/correction 使用有效账本口径但分别披露。
7. **独立性仍须处理。** 同 token/pool/cohort 多臂投影、候选/对照配对、同一 event、多币同源和同一 clone episode 均需 cluster-aware 报告；不能简单累加成交数或账户 PNL。
8. **真实可实现性仍未证明。** 当前普通 Paper 是轻量市场价模型；writeoff/SELL intent、原池可见、短窗更新和工程 PASS 均不能替代 amount-specific 主网成交、gas/税/MEV/失败恢复验证。Live 继续不具资格。

本地图的交付含义仅为：历史证据在哪里、每段能回答什么、哪些段落必须隔离、哪些机制可进入后续 10–20 个候选的设计池。最终候选仍要结合 `HISTORICAL_STATISTICS.md`、外部实证、独立反方审查及新 frontier 的自然结果；不得从本文件直接宣称策略有效。
