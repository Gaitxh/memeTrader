# GXH / memeTrader — Solana 纯链上核心资源重分配与执行计划

Date: 2026-09-03
Fact cutoff UTC: 2026-09-03T12:00:00Z
Owner: Lead ChatGPT research/review
Execution owner: existing Codex main thread only
Mode: Paper; Live remains locked
Status: PROMOTE_NOW / USER_SUPERSESSION

## 1. 决策摘要

下一阶段把**新增工程、研究和模型预算的大多数资源转到 Solana 纯链上策略核心**。这不是因为新闻、热点、人物、社区永远没有 alpha，而是因为当前本机前向证据表明：信息链的单位资源转化率很低，而纯链上已经进入“安全、可卖、成本、退出和真实前向收益”这些直接决定钱能否赚到/保住的瓶颈。

本轮资源配置建议：

- 70%：Solana 安全、执行、持仓机械监控与死亡池终态；
- 20%：严格前向的链上 alpha 数据工厂和 Shadow challenger；
- 5%：终端/轻量运行可观测性；
- 5%：信息链 passive maintenance，仅保留低成本 deterministic ingestion、exact evidence capture、不可变分母与后续可复盘 optionality；本轮高成本 information Agent dispatch 暂停。

这是一轮资源配置，不是永久删除信息线。只有新的前向证据证明信息线的独立确认率、可寻址率和扣成本收益重新具有较高边际价值时，才增加预算。

**当前不做：** 不扩大生产 Agent 并发；不因单个赢家调 TP/stop；不扩大 BSC/Robinhood；不把 CLMM/AMM-v4/Meteora 解码当当前最高优先级；不做大 UI 重写；不解锁 Live。

## 2. 为什么资源重分配是当前最优选择

### 2.1 信息链当前的边际产出很低

约过去 24h 的 r6 `agent_attempts`：

- `token_context`: 305 次 valid output，约 17.58M tokens；另有少量 invalid output；
- `trend_scout`: 45 次 valid output，约 3.28M tokens；
- `source_discovery`: 约 0.61M tokens；
- `fact_verifier`: 约 0.085M tokens。

合计信息相关 Agent 已消耗约 21.6M+ tokens。

同一窗口 `token_context_assessments`：

- `no_context=559`；
- `insufficient_reachable_sources=72`；
- `insufficient_context_only=1`；
- 没有形成可直接晋级的正向 Context 状态。

`decisions` 约为：`WAIT=825 / REJECT=17 / CANDIDATE=1`。新 120 秒 information WATCH 当前共 6 个自然 cohort，6/6 均最终 `EXPIRED_INSUFFICIENT_CONFIRMATION`。

这说明当前信息面不是“没有潜在价值”，而是**当前实现和来源覆盖下，继续加大 Agent/语义研究的机会成本太高**。

### 2.2 纯链上已碰到直接决定真钱结果的失败模式

当前 `onchain-paper-exploration/v4-20usdc-flat040` 已有 8 个自然 exact-size 入场，3 个固定基线仓位关闭、5 个仍开；动态退出同一入场的 v4 challenger 已有自然经济报价、部分止盈、no-route、uneconomic 和流动性归零案例。

当前 v4 动态退出报价约：

- `no_route=148`；
- `quoted_but_uneconomic=144`；
- `economic=8`。

这类问题不是展示层问题，而是直接回答：买不买得进、能不能卖、什么时候必须跑、池子死后是否还在浪费请求、Paper PNL 是否是假象。

### 2.3 当前 Solana 可执行候选高度集中于 PumpSwap

`onchain-only-shadow/v2-20usdc` 当前 Solana cohort 32 个，其中：

- PumpSwap: 31；
- Meteora dyn2: 1。

最近窗口仍基本相同。这意味着短期把大量资源继续投入 CLMM/AMM-v4/Meteora 全覆盖，会挤占更高价值的 PumpSwap 真实交易闭环。Raydium CPMM RPC custody 已完成，可保留；未支持 venue 继续 fail-closed `WAIT`。

Venue decoder 的再次扩张只有在前向 missed-opportunity denominator 证明：某未支持 venue 占“其他条件均合格但因 custody unknown 被挡”的至少约 10%，或出现足以改变经济结论的大量自然候选时才 PROMOTE_NOW。该 10% 仅是工程资源晋级门，不是交易门。

### 2.4 当前最危险的新发现：被验证的 pair 不一定是 Jupiter 实际 route

抽查最近 100 个 `baseline_buy / quoted` 的 Jupiter 结果，把 `route_json[*].amm_key` 与触发 DexScreener snapshot 的 `pairAddress` 比较：

- snapshot pair 在实际 route 中：69/100；
- snapshot pair **不在**实际 route 中：31/100；
- multi-leg route：69/100。

出现 `OKX DEX Router`、BisonFi、GoonFi、Deriverse、Whirlpool 等实际 route/leg；有些 PumpSwap snapshot 的 Jupiter route 完全不含该 PumpSwap pair。

当前 `_record_onchain_pretrade_rug_safety()` 先按 DexScreener snapshot pair 做 RPC custody，再对 Jupiter BUY 的 acquired minimum amount 做一次 SELL preflight。它没有把实际 BUY `routePlan` 的 route/surface 与被验证的持有流动性 surface 建立强制一致/可解释关系。

因此必须拆成两个概念：

1. **Holding Surface Safety**：买入后这个 Token 的可持有/可退出市场面是否有可靠 custody、vault、removable-liquidity、mint-control 证据；
2. **Execution Route Safety/Truth**：实际用于 BUY/SELL 的 aggregator route 是否可解释、金额特定、时效有效，并与持有市场面风险口径兼容。

不能再用“DexScreener pair 安全”暗示“Jupiter 实际 route 的所有经济/安全语义都已证明”。

## 3. 用户新的硬规则：确认死亡的池子不可恢复

用户明确规定：池子一旦真正被撤/端掉，就不考虑恢复。这一规则必须与临时 `no_route`、provider error 分开。

新增不可变语义建议：`POOL_DEAD_TERMINAL_NO_RECOVERY`。

### 3.1 只有链上事实才能把池标成 terminal dead

以下任一类经 exact pool/account 且时点有效的链上事实可进入候选 death classifier；具体 venue decoder 要给出可审计 reason code：

- pool account 被关闭、owner/layout 失效或 swap 状态被永久/明确禁用；
- quote/base vault 发生已确认的材料级抽空，且对应 venue 的 LP/position/removable-liquidity 状态证明可交易流动性已消失；
- protocol/position state 显示流动性为零并且不是单纯价格超出 CLMM range 的假“零 TVL”解释；
- exact surface 在确认 slot 上失去可用 reserve，且同一 surface 的 exact remaining-size route 不存在；
- 其他 venue-specific、可证明不可逆的 withdrawal/close 状态。

**不得**因为一次 Jupiter `no_route`、一次 DexScreener `liquidity=0`、一次 API timeout 就判死亡。

### 3.2 死亡池处理

一旦 `POOL_DEAD_TERMINAL_NO_RECOVERY` 被确认：

1. 如果死亡触发到达时仍存在极短的可退出可能，只允许发起**一次立即、最高优先级的 exact remaining-size SELL 尝试**；
2. 若没有经济可执行 route，剩余 Paper 仓位立即 `written_off/untradeable`；
3. 该 dead pool 不再进入 15/30/60/120/300 秒 Jupiter recovery/backoff 队列；
4. 继续保存廉价 append-only telemetry/accounting，但不再为该 pool 花执行请求；
5. 后来同 Token 出现另一个独立、已验证的新 pool/venue，只能作为**新 market surface / 新 cohort**，不能把已死亡 surface 或已核销仓位“恢复”；
6. 历史 PNL 不因后来新池出现而回写。

现有 P0-B adaptive scheduler 的“fresh liquidity/activity 可 re-arm”只适用于 `ROUTE_TEMPORARILY_UNAVAILABLE` 等非终态；确认 pool death 后必须禁止 re-arm。

## 4. 新主线的策略边界

### 4.1 先做“Post-pool / post-graduation 可执行策略”，不先做超早期狙击

短期 Strategy-2 的主研究对象应保持：已经进入可识别 AMM/pool、达到本地严格前向 on-chain trigger、能取得 amount-specific BUY/SELL evidence 的 Solana Token。

原因：

- 当前自然高动量样本主要已经在 PumpSwap；
- 已有 Jupiter、Paper、动态退出、creator launch、liquidity survival、holder shadow 等基础设施；
- 直接进入 bonding-curve/新块狙击会把延迟、MEV、优先费、bot 竞争、graduation base rate 和更弱 custody 混进同一轮，反而延长闭环时间。

Pump bonding-curve early-entry 可作为未来独立 arm；必须单独注册、单独成本/延迟模型、单独成熟门，不能与当前 post-pool cohort 混分母。

### 4.2 Venue 范围

当前 P0/Paper 主策略范围只有：

1. **canonical PumpSwap**。

Raydium CPMM v3 decoder 和既有前向证据完整保留，但本轮只作为 Research Lab 资产，不继续承担新策略开发/Paper promotion。其余 venue 全部 fail-closed WAIT。

CLMM / AMM-v4 / Meteora / Orca 暂不作为 P0 必须完成项，除非 missed-opportunity denominator 达到前述工程晋级门。

## 5. P0-0：立即修复 Holding Surface 与 Jupiter route 语义错位

这是下一 tranche 的最高优先级，优先于继续扩 venue。

### 5.1 新 append-only 事实层

建议新增两个隔离的证据对象（命名可由 Codex 按现有 Store 风格调整，但语义不得混合）：

#### A. `market_surface_safety/v1`

至少保存：

- token_id / snapshot_id / observed_at / slot；
- chain / program_id / venue / pool_address / surface_type；
- exact base/quote mint；
- vaults；
- custody class；
- protocol-owned / creator-withdrawable / position-owner-withdrawable；
- current removable liquidity share；
- permanent lock/burn facts；
- swap enabled state；
- direct mint/Token-2022 safety digest；
- PASS / WAIT / REJECT + transparent reasons。

#### B. `execution_route_observation/v1`

保存：

- phase BUY/SELL；
- exact input/output amount；
- requested/completed/anchor time；
- Jupiter router/mode；
- amount-specific minimum output；
- normalized price impact；
- fee fields；
- routePlan leg `ammKey/label/inputMint/outputMint/amount`；
- `route_verifiability = exact_onchain_legs | meta_aggregator_opaque | unsupported`；
- context slot；
- 与 selected holding surface 的 relation：`contains_surface / excludes_surface / opaque_router / multi_surface`。

不得删除现有 quote rows；新层从注册点前向开始。

### 5.2 最好报价与可验证路线分离

Jupiter Swap V2 `/order` 是 Meta-Aggregator 经济报价入口，可能使用 Metis、RFQ、Dflow、OKX 等不同 router；当前代码的 `routePlan` 已经显示这点。若需要严格解释 on-chain AMM route，可增加**研究性并行 `/build`/Metis verifiable route overlay**，而不是把现有 `/order` 当作错误 API。

建议：

- `/order`：保存为 `economic_best_quote`；
- `/build`（或等价 Metis-only route）：保存为 `verifiable_onchain_route`；
- 两者绝不互相回填；
- 先 Shadow 比较 best quote 与 verifiable quote 的成本差、覆盖率和 route safety；
- 后续新 Paper execution version 若选择可验证路线，必须在注册时冻结允许的价格劣化上限；不得看完赢家后再设。

当前阶段不要立刻声称 opaque Meta-Aggregator route 不安全；正确动作是把“holding surface 安全”和“execution route 可解释性”拆开，未知处 fail closed 或只保留 research evidence。

## 6. P0-1：把 Solana Mint / Token-2022 安全从第三方报告提升为直接链上事实

当前安全层对 mintable/freezable/Token-2022 危险能力仍主要依赖 GoPlus/Rugcheck。下一版应直接读取 mint account 和 Token-2022 extensions，把第三方 API 变为 cross-check，不再是关键单点。

至少解析：

- classic SPL Mint: mintAuthority、freezeAuthority、supply、decimals；
- Token-2022 TransferFeeConfig：当前/下一 epoch fee、authority；
- PermanentDelegate；
- TransferHook program + authority/upgradability 可验证部分；
- DefaultAccountState；
- NonTransferable；
- MintCloseAuthority；
- Pausable/可冻结类 extension（按当前 Token-2022 实际支持集）；
- 其他能改变 transferability、扣费、冻结或代扣能力的 extension。

初始规则保持透明：

- 明确可阻止/接管 holder transfer 的危险能力 -> REJECT；
- 能升级但安全边界无法证明 -> WAIT；
- 第三方与本地 RPC 不一致 -> WAIT/REJECT，记录 disagreement；
- 不建立一个不透明 scam score。

## 7. P0-2：事件驱动 held-position watcher + pool-death terminal

直接使用 Solana RPC WebSocket/订阅能力，Agent 不进入关键路径。

对每个 open position 至少监控：

- exact pool account；
- quote/base vault；
- LP mint/locker/authority（venue applicable）；
- token mint；
- 后续支持 CLMM 时再订阅 exact position/tick/liquidity accounts。

优先用 `accountSubscribe`；program/log subscription 只作为补充，不能代替 exact held account truth。

### 建议状态

- `ENTRY_HOT`: 入场后最早阶段；
- `OPEN_WARM`；
- `OPEN_COOL`；
- `ALERT`；
- `ROUTE_TEMPORARILY_UNAVAILABLE`；
- `POOL_DEAD_TERMINAL_NO_RECOVERY`。

### 调度优先级

1. confirmed on-chain safety/death trigger；
2. hard stop / trailing / TP / max-hold exact SELL；
3. fresh new-entry safety preflight；
4. fixed-horizon research quote；
5. temporary no-route retry；
6. dead-pool: 永不 retry。

目标不是承诺“能在原子撤池前跑掉”。原子撤池的主要防线是 pre-BUY custody/lock。Post-BUY watcher 的价值在渐进抽流动性、authority/状态变化、route degradation 和提前实现利润。

验收必须记录真实检测延迟分布，不要凭设计声明实时。先测 public RPC；只有 p95 延迟/断线证明不够时才考虑付费 RPC。

## 8. P1：严格前向 On-chain Alpha Data Factory

当前 `_momentum_score()` 只有 liquidity、5m volume、5m tx count、buy-sell count imbalance，容易被小额刷单/微交易和流动性表象操纵。它保留为 immutable control，不直接重调。

新增研究-only `onchain_alpha_feature_frame/v1`，每个 frame 只使用当时已经被本机观察的事实，`decision_eligible=0 / affects=none`。

### 8.1 复用已有 append-only 数据

当前已经有：

- `token_launch_facts`: 约 20k 首发事实，含 creator、create signature、bonding curve、initial buy、initial market cap/native、virtual reserves；
- `creator_launch_risk_cohorts`: 约 8.9k；
- `liquidity_survival_cohorts/outcomes`: 数千 cohort / 万级 outcome；
- `solana_holder_shadow`: holder breadth/concentration 低频样本；
- Jupiter exact-size quote/route；
- immutable market snapshots。

不要另造重复账本去重新采集同样事实。

### 8.2 第一批特征族

#### 时序/价格
- age since create / migration / pool activation；
- 5s/15s/30s/60s/5m return；
- momentum acceleration / reversal；
- realized volatility / peak drawdown as-of；
- liquidity-adjusted price move。

#### 交易流，而不是只有笔数
- actual SOL/USDC buy/sell value；
- buy/sell count ratio；
- buy/sell **value** ratio；
- median/p90 trade size；
- microtrade ratio；
- trade-size entropy；
- burstiness / inter-arrival time；
- unique buyer/seller breadth（只有可验证时才命名 unique owner，不叫 unique human）；
- top1/top5 flow concentration。

优先实现 PumpSwap transaction/event decoder 获得真实 swap value。若只能得到 DexScreener count，不把它冒充真实净流。

#### Creator / launch
- creator prior launch count；
- prior 24h launch count；
- seconds since prior launch；
- prior mature liquidity-collapse / writeoff lower bound；
- initial creator buy size / initial market-cap ratio；
- creator/known related balance sell velocity（只有可靠 relation 才使用）。

#### Holder / concentration
- top1/top10 supply share，排除已证明 pool/burn/locker/protocol custody；
- holder breadth change；
- dust ratio。

由于公共 RPC holder scan 当前可有 6–30s 级延迟，它不是 ENTRY_HOT 的同步阻塞项；先做异步/Shadow 特征。

#### Liquidity / route quality
- quote-side reserve path；
- liquidity survival ratio；
- removable-liquidity share；
- exact $20 BUY min output / price impact；
- immediate SELL recovery；
- 25%/50%/100% remaining-size sellability；
- route persistence、route leg count、router class；
- no-route/uneconomic duration。

#### 协调钱包/狙击
早期共同钱包/cohort 只先作为风险、集中度或交互特征。不要把“smart wallet/sniper cohort”直接做正向买入信号；需要活动匹配 placebo/因果对照后才可晋级。

## 9. P1 Challenger 设计：先透明规则，后模型

不要一次把所有特征混成一个黑盒分数。保持当前 momentum>=80 版本为 control，建立互斥/可解释的 Shadow arms：

- A `FLOW_QUALITY`: control + value-flow breadth / anti-microtrade；
- B `CREATOR_RISK`: control + serial-launch/prior-collapse bounded gate；
- C `ROUTE_QUALITY`: control + immediate exact-size round-trip recovery/route persistence；
- D `EARLY_ACCELERATION`: control + 15/30/60s acceleration/volatility shape。

所有 arm：

- 新 registration；
- no backfill；
- 不挑 winner；
- 15/60/240 fixed outcomes + same-entry dynamic-exit paired outcomes；
- missing/no-route/dead/writeoff 留在 ITT 分母；
- 同一日期 cluster 统计，避免把同一行情 burst 当独立样本。

模型（XGBoost/GBDT）只在本地前向 frame + outcome 足够后进行 offline research。训练必须严格按时间切分，模型版本/feature schema/preprocessing 冻结后再启动新的 forward Shadow。模型绝不能在 entry 时读取 60/240m outcome。

## 10. Profitability / promotion metrics

纯链上当前**尚未被证明稳定盈利**。已有正 PNL 自然样本很有价值，但数量少且 meme return 极端偏态，不能据此直接扩大风险。

至少继续满足现有 maturity gate：

- >=30 个 primary terminal Token；
- >=15 个独立 trigger dates；
- positive/nonpositive 各 >=5。

除此之外，每个候选策略必须同时报告：

- exact-entry count / terminal count；
- realized PNL after all modeled/verified costs；
- executable equity，不能用 DEX mark 冒充；
- mean / median return；
- win rate；
- profit factor；
- max drawdown；
- lower-tail / CVaR；
- writeoff rate；
- no-route rate；
- capital-time efficiency；
- top1/top3 PNL contribution；
- **remove-best-1 / remove-best-3 后的 PNL**；
- fixed-vs-dynamic same-entry paired delta；
- 按 trigger date 聚类的 bootstrap/CI 或等价稳健区间。

晋级不以“总 PNL 为正”单独决定。若收益几乎全部由一个极端赢家贡献，必须显示而不是隐藏。

## 11. 信息线 Maintenance Mode

保留：

- deterministic source ingestion / immutable observations；
- exact CA / exact post / source provenance；
- 小预算 WATCH observer；
- Strategy-3 post-entry context research，但绝不延迟 emergency exit；
- 未来可复盘“链上先动，信息后来到”的 outcome label。

暂停/显著降频：

- 泛热点 Trend Scout 高频运行；
- 普通 Token Context 大规模 Luna 调查；
- 新来源/新 KOL/新语义层扩张；
- 为了提高非空率而放宽 independent evidence；
- 新 production Agent 并发。

本轮 coherent focus cycle 中，`trend_scout / source_discovery / token_context / fact_verifier / WATCH Agent dispatch / S3 post-entry narrative Agent dispatch` 的**主动模型派发暂停**；5% maintenance 预算指廉价 collector/storage、exact provenance、被动分母和 Lead/Codex 的按需研究，不是继续烧生产 Agent token。只有达到已固化的信息 reactivation gate（跨日 exact-addressable 被动事件、相对链上 trigger 的真实 lead time、以及 materially nonzero incremental executable-candidate yield）后才注册新的主动 Agent 预算版本。

任何启停/配额变更都应记录生效时点；旧 Agent rows 不改写。

## 12. 多链、venue 与 UI 的处置

### BSC / Robinhood
保留研究资产和现有 immutable rows，但本轮不继续 route/Paper 扩张。未来恢复时，仍必须满足原有 firm route + gas/L1/L2 + tax/transfer safety 门。

### CLMM / AMM-v4 / Meteora / Orca
继续 fail-closed WAIT。只有真实前向 missed-opportunity denominator 达到工程晋级门才投入 decoder。

### UI
大 UI 重构降级。用户允许终端承担实时展示，因此当前只做最小可观测性。

建议新增只读 CLI/脚本 `onchain-cockpit`（最终名称按项目现有 CLI 风格），只读 SQLite/backend 产生的数据，不因用户打开终端而触发 provider call。支持一次性和 `--watch 2`：

- 当前 active registration/version；
- 最近 trigger/BUY/SELL；
- open positions、remaining raw、cost basis；
- latest indicative mark vs fresh executable recovery；
- pool/surface safety class；
- removable liquidity / reserve；
- `HOT/WARM/ALERT/DEAD` 状态；
- last exact SELL quote age/status；
- Jupiter due queue / temporary retry / dead terminal counts；
- P0 safety PASS/WAIT/REJECT；
- info Agent day spend/call count；
- feature frame freshness。

Web 后续只在这套 backend truth 稳定后再做 cockpit polish。

## 13. Codex 实施顺序

### Tranche 0 — Authority / budget supersession

1. 把本文件和当前用户新要求写入 authoritative plan/ledger；
2. 高成本 information Agent dispatch 暂停；被动 collector/provenance/immutable denominator 进入 maintenance mode；
3. 保留已注册实验和旧 rows，不删除、不回填；
4. BSC/Robinhood、CLMM/AMM-v4/Meteora 大扩张降级；
5. Live 继续 locked。

Acceptance:
- 配额/启停有明确生效点；
- production Agent concurrency 不增加；
- Runtime 其余 onchain paths 不受影响。

### Tranche 1 — Route/holding-surface truth P0

Files/methods to inspect first:
- `src/memetrader/collectors.py::JupiterQuoteClient.quote`
- `src/memetrader/runtime.py::_record_onchain_pretrade_rug_safety`
- `src/memetrader/runtime.py::_token_universe_jupiter_quote_once_unlocked`
- `src/memetrader/store.py::_apply_onchain_paper_exploration_quote_locked`
- `src/memetrader/strategy.py::SafetyChecker`

Tasks:
- register append-only route/surface evidence version；
- persist route-to-surface relation；
- add test fixtures where snapshot pair absent from Jupiter route；
- compare `/order` economic best vs optional `/build` verifiable route in research-only overlay；
- no current v4 rewrite。

Acceptance:
- no entry can be labelled “route/surface fully verified” unless the two dimensions are separately present and fresh；
- opaque routes are explicitly named opaque, not silently treated as the verified DexScreener pair；
- existing v4 rows unchanged。

### Tranche 2 — Direct mint/Token-2022 safety P0

Tasks:
- local account decoder；
- external-provider disagreement ledger；
- transparent hard blockers/WAIT；
- targeted tests for mint/freeze, transfer fee, permanent delegate, hook, nontransferable/default state。

Acceptance:
- GoPlus outage alone no longer makes all direct mint controls unknowable if RPC facts are available；
- dangerous extension fixtures fail closed；
- no opaque score。

### Tranche 3 — Held-position subscription + pool-death terminal P0

Tasks:
- exact account subscriptions + reconnect/slot dedupe；
- event-driven state reducer；
- one immediate SELL on confirmed death；
- no rearm after terminal dead；
- current adaptive retry only for temporary route failures；
- record detection/quote latency。

Acceptance:
- natural/fixture confirmed death schedules zero later retry；
- temporary `no_route` does not get misclassified dead；
- emergency quote outranks research quote；
- no Agent dependency。

### Tranche 4 — PumpSwap flow decoder + alpha frame P1

Tasks:
- transaction/event decode to actual SOL/token flow；
- derive value/breadth/concentration/burst features；
- join existing launch/creator/liquidity/route facts strictly as-of；
- immutable frames, affects=none。

Acceptance:
- every feature has source record IDs/as-of time；
- no future target/outcome fields in frame；
- no duplicate fact collection when existing ledger can be joined。

### Tranche 5 — Transparent challengers P1

Implement A/B/C/D one at a time or as clearly isolated preregistered arms. No production threshold change.

### Tranche 6 — Minimal terminal cockpit

Implement after backend state exists; do not block Tranche 1–4 for UI.

## 14. Testing / causal acceptance

Minimum test classes:

1. exact route pair mismatch / multi-leg / opaque-router fixtures；
2. PumpSwap canonical custody + direct mint controls；
3. Raydium CPMM regression；
4. Token-2022 extension decode；
5. pool-dead vs temporary no-route；
6. death -> one emergency attempt -> permanent no-retry；
7. subscription reconnect / duplicate slot idempotency；
8. priority fairness under Jupiter budget；
9. strict as-of feature frame/no-future leakage；
10. immutable registration/no update/delete；
11. current Paper ledger isolation；
12. Live locked regression。

自然前向验收优先于“大而全回归反复跑”。有界定向测试通过后允许当前 immutable Paper 继续收样，不为了等待所有研究成熟而停 Runtime。

## 15. 外部研究与官方事实基线

本轮研究依据包括：

- Pump official bonding curve/graduation docs: canonical graduation to PumpSwap is automatic/irreversible and migrated pool is protocol controlled: https://pump.fun/docs/bonding-curve
- Jupiter Swap V2 Order/Execute and Build docs: Meta-Aggregator vs Metis/custom route semantics and routePlan/ammKey: https://dev.jup.ag/docs/swap/order-and-execute and https://dev.jup.ag/docs/swap/build-swap-transaction
- Solana Token Extensions: Transfer Fee, Permanent Delegate, Transfer Hook and RPC WebSocket subscriptions: https://solana.com/docs/
- Raydium official Burn & Earn / CPMM / CLMM / program docs: https://docs.raydium.io/
- Li et al. 2026, *Catching the Rug: Early Detection of Pump-and-Dump Risks in Solana Memecoins*, large Solana dataset and first-minutes feature study: arXiv:2608.20271
- 2026 research on coordinated sniper cohorts: use only as a caution that apparent wallet cohorts can be confounded by activity/regime; do not promote smart-wallet signals without matched controls.

External research guides feature hypotheses; it does not overwrite current r6 forward outcomes and does not justify backfilling winners.

## 16. Final operating rule

本项目当前最重要的不是“预测哪个币能涨得最多”，而是先把一个可重复的、严格前向的闭环做真：

**发现 -> 当时链上状态 -> 安全持有面 -> amount-specific BUY -> immediate sellability -> 事件驱动持仓 -> dynamic SELL -> dead-pool terminal writeoff -> 全成本净收益 -> 前向学习。**

一旦这个闭环在 **canonical PumpSwap primary** 上达到跨日成熟/资本门，再用同一基础设施比较更丰富的链上 alpha、Raydium CPMM 或其他 venue、早期 bonding-curve arm，以及是否重新增加信息预算。这样资源投入最接近“赚更多真钱、少死在不可卖和假 PNL 上”的北极星。
