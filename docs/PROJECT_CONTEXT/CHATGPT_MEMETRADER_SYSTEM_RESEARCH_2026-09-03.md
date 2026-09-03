# memeTrader 系统级研究审查：Meme 发现、叙事、链上结构、安全、执行与持续学习

日期：2026-09-03
研究截止：2026-09-02T18:12:27Z
角色：Lead ChatGPT / research, strategy, causal & trading-economics review
状态：`RESEARCH_SYNTHESIS / NO_RUNTIME_CHANGE`
北极星：提高严格前向、可执行、扣除真实近似成本后的风险调整盈利概率；不是提高交易数、页面数量、Agent 调用量或历史最高收益。

---

# 0. 执行摘要

## 0.1 不应把“新闻→币”和“币→新闻”设计成对称的两条流水线

更合理的系统不是先验规定 News-first 或 Token-first，而是把三个**独立触发入口**汇合到同一个可审计机会状态：

1. **Narrative/Event-first radar**：重大新闻、X/KOL 原帖、社会事件、文化梗先出现时建立 `NarrativeEpisode`。此时可以完全没有 Token。它的职责是提前发现叙事和建立 watch，不是马上从几十个同名 clone 中强制选赢家。
2. **Token/onchain-first investigation**：新 Token、新池、bonding curve、成交/流动性异动先出现时，exact `(chain, CA)` 已知，再定向重建“为什么有人买它”：项目/人物关系、X 原帖、新闻、社区传播、KOL、叙事、操纵。
3. **Onchain-only alpha challenger**：如果以后严格前向数据证明市场微观结构、钱包行为、安全和真实路由本身具有稳定的扣费后优势，不应强制要求找到新闻。

三条入口都汇入：

`OpportunityState(token_id, narrative_episode_id?, market_surface_id, as_of)`

但下面四类必须独立：

- `Identity`：是不是正确 CA/正确币；
- `Safety / Behavioral Integrity`：合约与操纵/内幕风险；
- `Execution`：能不能按真实金额买进、卖出、成本多少；
- `Alpha State`：叙事、热度、加速度、链上微观结构、链级 regime。

**Identity / Safety / Execution 是 gate；Narrative / Social / Market 是预测变量。** 不应再把它们全部加成一个 0–100 分后用总分弥补硬风险。

## 0.2 现在不能科学宣布“现实中 Token-first 一定优于 News-first”

本机完整 funnel DAG 中：

- 首次 `onchain_momentum` trigger Token：约 2,835；
- 有 Event relation 的 Token：约 380；
- 两者同时存在：147；
- 147 中 144 个链上 trigger 先于 Event relation；
- relation - onchain 中位约 +0.34 分钟；115 个在 5 分钟内。

但这 147 条 relation **全部是 `reverse_news_observation`**，即程序看见 Token 后主动反查新闻产生。这只能说明**当前 token→news 实现很快**，不能证明现实信息发生在价格之后。

因此应新增严格前向、`affects=none` 的 **lead–lag ledger**，统一冻结：

- `T_narrative_first_primary_available`
- `T_narrative_first_independent_available`
- `T_token_create`
- `T_token_first_local_seen`
- `T_market_ignition`
- `T_social_acceleration`
- `T_executable_entry_quote`

以后按 narrative type / chain / launchpad / market surface / regime 学习谁通常领先，而不是在架构里预先规定谁一定领先。

## 0.3 当前主 Paper 比普通回测严格，但还不足以叫“真实可执行 Paper”

当前已有：

- point-in-time evidence；
- fresh quote；
- wrong-token / stale quote rejection；
- 固定 adverse slippage；
- swap fee；
- 已知 Token tax；
- 仓位/日 exposure/流动性约束；
- deterministic stop/trailing/TP；
- append-only execution attempts。

但正常主 Paper BUY/SELL 仍主要使用：

`DexScreener mark × (1 ± 4% adverse slippage)`

而不是针对模拟仓位金额的 router `minimum output`。它也没有完整计入：

- Solana priority/signature/rent 等实时网络费；
- BSC gas；
- Base L2 execution + L1 data/security fee；
- Robinhood Chain gas；
- 各 route/pool 实时费用。

独立 `onchain_only_jupiter_quote_*` Shadow 在 Solana 上反而比主 Paper 更接近 amount-specific executable semantics。

因此当前主 Paper PNL 只能叫：

`simulated cost-adjusted approximation`

不能用于 Live 结论。

## 0.4 当前安全层不是“没有检查”，而是“合约级安全较强，Meme 行为级安全不足”

当前已经做 GoPlus / Honeypot.is / RugCheck、mint/freeze/transfer 权限、honeypot、税、卖出能力、风险总分等。

但尚未正式进入 Decision 的 Meme 原生风险包括：

- creator/deployer launch history；
- initial self-buy；
- creator 当前 token exposure；
- creator 是否卖出还是转移到关联地址；
- first-N buyers；
- shared funding source；
- sniper/bundle/co-firing wallet clusters；
- wash trading / circular flow；
- 经济实体级 supply concentration；
- LP ownership / lock / withdrawability；
- liquidity failure mode；
- creator/related-wallet net selling；
- 早期交易量是否由少数钱包制造。

外部 2026 USENIX 研究进一步说明：高收益 Meme 里人工增长/洗量/LPI 很普遍。因此这些不是“以后锦上添花”的指标，而是安全/完整性层的重要部分。

## 0.5 当前 `attention` 与 `candidate_score` 需要拆结构，不应只调权重

当前 Event attention 把来源数、source kind、engagement、official-social bonus 混在一起；Candidate quality 又把 identity match、attention、source count、liquidity、volume、tx、buy ratio、market cap、age 混成一个总分。

在 578 个已有严格 `$35` Jupiter 15m round-trip 的 Solana onchain Shadow 样本里，当前 `_momentum_score` 与结果的单调关系不稳定：全样本 rank correlation 约 -0.08；两个自然日期分别约 -0.16 / +0.09。

反而一些**归一化强度**在两个日期方向更一致，例如：

- transactions / liquidity；
- volume / liquidity；
- liquidity / market cap。

极端 buy/sell imbalance 并没有更好。

这些只属于 exploratory diagnosis，**不能直接变成生产阈值**；但足以说明“所有看起来好的数字都加分”不是可靠设计。

## 0.6 X/KOL 经验帖有很高研究价值，但应是 hypothesis generator，不是 oracle

经验帖可用来发现：

- 系统尚未采集的变量；
- chain/launchpad regime；
- 早期钱包模式；
- 社交传播阶段；
- creator/dev 行为；
- 流动性失败模式；
- 退出经验；
- 反例。

每条经验必须记录 `published_at` 和当时已知事实，拆成可证伪 hypothesis。事后“金狗总结/最高市值榜”只能贡献**候选特征词典**，不能算作者预测命中。

## 0.7 买入后当前没有 position-aware 持续 Agent/news watch

当前 BUY 后会调用一次 Token Context。之后：

- 全局 RSS/X/Trend Scout 正常继续；
- 持仓约每 15 秒用确定性行情/安全/退出逻辑监控；
- 但没有“持仓期间持续定向追踪该 Token + Narrative + creator”的 Agent 闭环。

正确升级不是“每分钟调用一次 LLM”，而是：

- 持仓时提高该 exact Token、creator、Narrative 的确定性采集优先级；
- 只有新原帖、新独立来源、新纠错/否认、creator/LP/钱包状态重大变化、Narrative state transition 才触发 Agent 增量复核；
- Agent 不负责价格轮询、止损或算术退出。

## 0.8 “池子被撤/流动性没了”必须变成独立风险问题，但不能把所有流动性下降叫 rug

至少区分：

1. `lp_withdrawal`：LP owner 真实撤出流动性；
2. `sell_drain`：大量 Token 卖入 AMM，把 quote reserve 抽干/价格打崩，但 LP 未撤；
3. `migration_or_pair_switch`：launchpad 迁移或主池切换；
4. `provider_unobservable`：DexScreener/API 暂时或永久不再报告；
5. `unknown`。

Pump.fun 尤其必须区分：

- Bonding curve；
- 由 Pump `migrate` 创建的 **canonical PumpSwap pool**；
- 普通 non-canonical PumpSwap pool；
- Raydium/Meteora/Orca 等其他池。

官方 Pump 文档明确：bonding curve graduation 后流动性自动、原子、不可逆迁入 canonical PumpSwap，LP token 被烧毁，canonical liquidity 由协议控制，Pump.fun 不再主动 seed/remove。普通 PumpSwap pool 则有 LP token，可 `withdraw`。

所以 RugCheck 的 `LP unlocked` 等 vendor flag 必须结合 `market_surface/canonical_status` 解释，不能机械硬拒绝。

---

# 1. 研究方法与事实边界

本轮同时使用：

1. 当前 `E:\memeTrader` 代码；
2. 当前 r6 SQLite，只读；
3. 当前非敏感运行配置；
4. 官方协议/API 文档；
5. 同行评审/USENIX/高质量学术研究；
6. 成熟 social-intelligence 平台方法；
7. 开源研究数据与代码；
8. X/KOL 经验只作 hypothesis discovery。

禁止：

- 用历史赢家回填规则；
- 以 ATH 当标签；
- 从本轮探索性统计直接修改生产阈值；
- 以 project metadata/KOL promotion 当独立事实；
- 以“池流动性下降”直接断言开发者撤池；
- 打开 Live。

研究截止 r6 快照：

- tokens：160,695；
- events：5,968；
- decisions：2,975；
- WAIT 2,607 / REJECT 364 / CANDIDATE 4；
- trades：8；
- main Paper realized PNL ≈ -$4.3188，cash ≈ $995.6812，0 open positions；
- information-first cohorts：112；
- onchain-only shadow cohorts：2,059；
- Token Context assessments：843；
- source-fact results：48 / bindings 51；
- Solana holder shadow cohorts：89；
- active information-first outcome targets：24，attempts/results 12/12，terminals 14，其中 `scheduler_missed_deadline=4`。

这些数字会继续变化；只代表研究 cutoff。

---

# 2. 当前系统怎样从“新闻 + Token”走到模拟买入

## 2.1 Event 准入

`runtime.evaluate_events_once()`：

- Event attention 默认需 ≥35，除非已有 official direct CA；
- Decision 使用的外部 Observation 必须在决策前已 observed/ingested；
- 当前配置 source age ≤30 分钟；
- stale/future/non-feature/non-confirmation 不作为 Decision evidence。

这是正确的因果边界。

## 2.2 候选 Token 获取

`CandidateEvaluator.discover_and_decide()` 当前综合两种方向：

1. Event 文本提取 Solana/EVM CA；
2. official social 明确给 CA 时形成 official CA/chain constraint；
3. Token Context 中满足多独立来源 + exact address binding 的 Token 先 quote；
4. explicit CA 先查 DexScreener；
5. 最多搜索 4 个 aliases；
6. 最近已发现 Token 若 name/symbol 与 Event overlap，也进入候选；
7. 过滤 malformed metadata、非 distinctive name、official mismatch、时间错误、弱 reverse-only 关系。

因此当前代码已经不是纯 News-first，而是**混合 information-first + token-first candidate retrieval**。

## 2.3 Identity match

当前 `_match()`：

- exact CA → 100；
- 否则用 Event terms 与 Token name/symbol 词交集与 substring；
- 非 exact 最高 94。

当前 `min_match_score=52`。

优点：exact CA 始终强于复制名字。

缺点：

- 泛词/同名 clone 仍可能进入；
- image/logo 未成为正式 identity 特征；
- exact source-link identity set 尚未进入生产 scorer；
- clone/fanout lineage 未成为正式 gate；
- asset 是否真正属于 Meme 类型没有被清楚建模。

## 2.4 Candidate quality

当前 `_quality()` 大致：

- match ×0.45；
- event attention 最多 +15；
- external source count 最多 +10；
- liquidity 最多 +10；
- 5m volume 最多 +8；
- 5m tx 最多 +7；
- buy > sells 最多 +5；
- attention / market-cap gap 最多 +5；
- Token 相对 Event 的创建时点最多 +5。

当前：

- min candidate score =67；
- canonical margin =5。

结构问题：

- identity、market state、narrative、execution 的经济含义不同；
- 一个“正确但尚未启动”的 Token 与“名字勉强相关但已经热”的 Token 被同一总分排序；
- score 可以隐藏某个维度完全失败。

建议未来保持向量，不急于生产 composite。

---

# 3. 当前安全检查：做了什么，没做什么

## 3.1 通用硬门

当前正式 candidate 进入安全检查时：

- price >0；
- liquidity ≥ $12,000（窄 route probe 例外）；
- market cap ≤ $25m；
- 5m tx ≥8；
- buy ratio ≥0.55；
- honeypot != true；
- sellable != false；
- buy/sell tax ≤12%。

## 3.2 EVM

GoPlus / Honeypot.is：

- require 至少一个 EVM security report；
- honeypot；
- cannot_buy；
- hidden_owner；
- take back ownership；
- owner change balance；
- selfdestruct；
- blacklist；
- transfer pausable；
- slippage modifiable；
- same-creator honeypot；
- closed source 可拒绝。

BSC 支持 Honeypot simulation，但当前 `require_evm_simulation=false`。

## 3.3 Solana

GoPlus Solana / RugCheck：

- require 至少一份报告；
- freezable；
- mintable；
- closable；
- balance mutable authority；
- default-account-state upgradable；
- transfer fee/hook upgradable；
- non-transferable；
- RugCheck `rugged=true`；
- RugCheck normalized risk score >79。

## 3.4 当前不足

GoPlus 官方 API 已经能返回 EVM：

- holder_count；
- top10 holders；
- creator_address / balance / percent；
- LP holder count / top LP holders / lock；
- pool fee；
- malicious address information。

当前生产检查只用了其中一小部分。

Solana 也存在 holder/DEX/LP/creator 相关数据，但当前正式策略没有把它们正确 surface-adjust 后使用。

结论：现有 security 是**合约/权限安全层**，不是完整 Meme behavioral integrity layer。

---

# 4. 四个历史 CANDIDATE 的失败模式审计

样本极少，只能用于 failure-mode audit，不能做统计推断。

## 4.1 ROMAN / NASA Telescope

- score≈81；match≈61；
- liquidity≈$111k；mcap≈$70k；
- 5m volume≈$18k；115 tx；
- RugCheck normalized≈52，报告 `Large Amount of LP Unlocked` danger；
- 实际为 PumpSwap；
- 历史 Paper round 小幅正，liquidity emergency 退出。

**修正后的教训**：不是“LP unlocked 应硬拒绝”，而是 vendor risk flag 没有与 Pump canonical/noncanonical surface 对齐。

## 4.2 Mimikyu / Pokémon movie

- score≈67；match≈52；
- 5m volume≈$82k；820 tx；
- RugCheck normalized≈52，类似 LP risk；
- PumpSwap；
- Paper 小幅正，liquidity emergency。

教训：高 tx/volume 不能证明 liquidity survival 或 organic demand。

## 4.3 Lake America / Lake Ontario 新闻

- 合约/holder 表面更健康；
- RugCheck normalized≈1、LP locked≈100%；
- 但 Narrative binding 本身可疑；
- Paper 约 -$3.84，hard stop。

教训：**合约安全和 Narrative identity 是正交问题。**

## 4.4 cbZEC / Coinbase Base announcement

- exact CA；score≈92；
- 这是 Coinbase wrapped ZEC，不是目标 Meme；
- Paper 约 -$1.97，narrative+flow decay。

教训：当前系统缺少 `meme_asset_type / launch_surface / cultural narrative fit`；否则“新闻相关可交易币”会混入“新 Meme 投资机会”。

---

# 5. Meme Token 应增加哪些特征

不要先建一个“万能 Meme Score”。先冻结多维特征。

## 5.1 IdentityConfidence — gate

- exact CA in primary/independent evidence；
- exact source-link identity set；
- CA/name/symbol/image 与 Narrative 的一致性；
- clone fanout；
- same-name/symbol competition；
- chain；
- launchpad；
- pool surface；
- official direct CA；
- project metadata vs independent confirmation。

Fanout 无法区分时 WAIT。

## 5.2 MemeAssetType

至少区分：

- fresh community meme；
- celebrity/public-figure derivative；
- news/event derivative；
- animal/character/cultural meme；
- political meme；
- AI/gaming/internet meta；
- CTO/community revival；
- wrapped/utility/stable/stock/tokenized asset（通常排除 Meme 策略）；
- pure ticker clone / promotion-only。

这能解决 cbZEC 这类“正确新闻、正确 CA、错误资产类别”。

## 5.3 NarrativeQuality — prediction feature

适合 LLM 结构化抽取：

- compressibility；
- emotional arousal；
- novelty；
- cultural familiarity；
- remixability / visual clonability；
- tribe formation；
- continuation potential；
- cross-community portability；
- chain cultural fit。

这些只做前向特征，不能写死“满足 N 条就买”。

## 5.4 Factual/CatalystState

独立于 Meme 质量：

- confirmed fact / probable report / rumor / satire / correction / impersonation / promotion；
- actor identity；
- primary source；
- independent reporting；
- public figure 是原创、repost、引用、玩笑、否认还是其它动作；
- 默认不推断 endorsement。

## 5.5 SocialHeat

成熟 social-intelligence 平台共同启示：不要只数 likes/views。

应逐步采集/计算：

- unique creators；
- duplicate-filtered unique messages；
- mention velocity；
- engagement velocity；
- cross-platform breadth；
- reputation-weighted creators；
- independent KOL breadth；
- social dominance；
- propagation depth；
- spam/duplicate ratio。

Santiment 的 Unique Social Volume 会去掉重复文本；Trending/attention 类方法强调相对历史 baseline 和独立用户。LunarCrush 在计数前做 topic classification、spam/bot filtering、creator profiling。Kaito 也明确强调 reputation-weighted、原创、相关内容，而不是 raw impressions。

当前 browser watch 不是全 X firehose，因此任何 Heat 都必须带 `coverage_scope`，不能假装“全球 social volume”。

## 5.6 HeatAcceleration / NarrativeState

建议状态机：

`Dormant -> Ignition -> Emerging -> Expansion -> Crowded -> Exhaustion/Decay`

保存：

- H(t)；
- dH/dt；
- d²H/dt²；
- unique creator growth；
- duplicate ratio；
- social dominance change；
- price already-advanced/crowding。

“热度极高”不必然是好事：P&D 研究和成熟平台经验都表明热度可能是 FOMO/分发阶段。

## 5.7 OrganicSpread vs Manipulation

- duplicate wording；
- repost-only ratio；
- creator concentration；
- 同一时间大量低质量账号；
- paid Dex boosts/ads；
- shill/referral language；
- KOL 同步出现；
- social growth 是否伴随独立买家增长；
- price pump 是否先于 public discussion。

---

# 6. 链上 Market Microstructure：比当前 momentum score 更重要

## 6.1 当前 `_momentum_score`

主要把：

- liquidity；
- volume；
- tx；
- buy/sell count imbalance

全部视为正向加分。

在 578 个 strict 15m Jupiter round-trip Solana Shadow 样本上，当前总分与结果方向不稳定。

因此建议从“一个 momentum score”改为分量：

### Activity
- tx count；
- volume；
- unique buyers/sellers；
- average trade size；
- trade-size dispersion。

### Intensity normalized by size
- volume/liquidity；
- tx/liquidity；
- liquidity/market cap；
- buyer growth / existing holders。

### Direction
- buy/sell counts；
- buy/sell notional；
- net order flow。

### Price path
- price velocity/acceleration；
- realized volatility；
- max drawdown from local high；
- price relative to launch/bonding curve；
- crowding / already-pumped distance。

### Liquidity
- liquidity level；
- liquidity growth/decay；
- quote reserve；
- amount-specific price impact；
- route availability；
- pool concentration。

### Lifecycle
- token age；
- bonding curve progress；
- graduation/migration；
- market surface age。

按 `chain × launchpad × surface × token_age × regime` 做 percentile / rolling normalization，而不是四条链共用固定 volume 阈值。

## 6.2 当前 strict Jupiter Shadow 告诉我们的分布

15m 有效 round-trip 578：

- median ~0%；
- ≥90% loss ~23%；
- ≥100% gain ~14%；
- 极端右尾存在。

60m：

- median ~-98%；
- ≥90% loss ~55%。

240m：

- median ~-99.97%；
- ≥90% loss ~77%。

这说明新 Meme 的“活着的窗口”非常短，死亡率极高。优化目标不能是平均收益或未来 ATH；至少要同时评价：

- median；
- catastrophic-loss rate；
- positive rate；
- p10/p90；
- MFE/MAE；
- route failure；
- drawdown；
- capital lock；
- expected utility / risk-adjusted PNL。

---

# 7. Creator / Developer / 买家地址 / 老鼠仓 / Sniper

## 7.1 Address ≠ economic entity

同一操作者可通过多地址、bundle、shared funding、同步下单伪装成“分散持仓”；AMM pool、bonding curve PDA、burn、locker 又可能持有大量供应却不是内幕钱包。

因此真正需要的是：

`wallet address -> economic entity / coordination cluster`

而不是简单 Top10。

## 7.2 当前已经拥有的 launch 数据

PumpPortal create 原始事件通常已有：

- `traderPublicKey`；
- `initialBuy`；
- `solAmount`；
- `bondingCurveKey`；
- launch signature；
- virtual reserves；
- pool；
- marketCapSol。

当前仍保留 `pumpportal:create` raw 的约 6,389 Token：

- distinct creator ≈3,032；
- creator ≥2 launches：868；
- ≥5：238；
- ≥10：88；
- 最大：95；
- ~81% create event 有非零 self-buy；
- solAmount median ~0.099 SOL，p75~1，p90~3.46，p95~5。

这些只能做设计证据，因为 `tokens.raw_json` 会被后续 upsert 覆盖。

## 7.3 第一项必须修的数据完整性问题

`Store.upsert_token()` 当前会用后续 hydration raw 覆盖 `tokens.raw_json`，因此 launch creator/initialBuy 不是永久 immutable truth。

优先新增 append-only `token_launch_facts`（或等价 immutable exposure payload），在 create 时冻结：

- token_id；
- chain；
- launchpad/surface；
- creator；
- create signature；
- initial self-buy；
- initial quote amount；
- bonding curve/pool；
- create time；
- observed/ingested/recorded time；
- raw hash/version。

`decision_eligible=0 / affects=none` 起步。

## 7.4 第一阶段 creator risk — 当前机器可做

只用现有或低成本公开数据：

- creator past launch count as-of；
- inter-launch interval；
- factory-like behavior；
- creator initial self-buy size；
- creator 过去 Token 的 survival/graduation/liquidity-collapse/route outcomes；
- creator 是否被 GoPlus malicious-address / scam-creator 标记；
- creator current direct balance（若可靠）；
- creator fee collection 要与 token sell 分开。

任何“creator 发过很多币就拒绝”“creator 卖光就拒绝”都必须先做前向验证。

## 7.5 “开发者是否清仓”应怎样定义

不能只看 creator 地址余额变 0。

需要：

- direct creator token balance；
- creator outbound transfers；
- related-wallet cluster；
- actual DEX sell instructions；
- transfer to pool/locker/burn/fee vault 的语义；
- net related-entity exposure；
- creator sell notional / liquidity；
- creator fees separately。

状态建议：

- `creator_direct_holding`
- `creator_related_holding`
- `creator_net_sold_pct`
- `creator_transfer_uncertain`
- `creator_fully_exited_direct_only`
- `creator_entity_exited`

“dev 清仓”既可能是 abandonment，也可能减少后续直接砸盘能力；必须学习，而不是先验硬门。

## 7.6 First-N buyer / sniper / rat

优先指标：

- first 10/20/50 buyer economic entities；
- creator 是否在 first buyers 中；
- buyer interarrival times；
- same slot/block/bundle；
- shared funding source；
- repeated cross-launch co-occurrence；
- top buyer entity concentration；
- independent buyer growth；
- early buyer sell-through；
- circular/wash flow；
- repeated known sniper cluster；
- average/dispersion of buyer size。

外部 RED-COHORT 研究表明 repeated early-wallet cohorts 确实可检测，但 activity-matched placebo 的 buyer-flow lift 更高，说明“重复出现的钱包组”本身有很强 selection bias。**所以 cohort 是风险特征，不是自动内幕罪证。**

## 7.7 当前单机如何实现 first-N buyers

不建议立即全链 Yellowstone firehose。

先用**有界 targeted Shadow**：

1. deterministic market/launch filter 把 16 万 Token 缩到少量 cohort；
2. Solana 官方 RPC：`getSignaturesForAddress` + `getTransaction`，只追 shortlist Token/bonding curve/pool；
3. 复用 Pump 官方 IDL/SDK 解码 create/buy/sell/migrate；
4. 只保存研究所需的地址/交易 lineage 与 aggregate cluster；
5. 记录 RPC missing/rate-limit/late；
6. 若公共 RPC 延迟/历史缺失使前向覆盖不够，再评估 Yellowstone/Geyser。

开源 Yellowstone/Triton 可作为后续升级；MELT/RED-COHORT 用作 feature/method reference，不直接把大数据基础设施搬进个人 PC。

---

# 8. Holder concentration：当前已有，但还不能直接用

`solana_holder_shadow` 已用官方 public Solana RPC 在 0/15/60/240m 保存：

- unique owner count；
- top1/top10 supply share；
- dust owner rate；
- aggregate only，不保存地址；
- `decision_eligible=0`。

当前 89 cohorts / 333 results，观察到的 top1/top10 中位接近 100%，owner 中位 1–2。

这不是“绝大多数币 developer 持 100%”的证据；很可能混入 bonding curve、pool/PDA、program/custody 结构。

下一步必须增加 `holder_entity_role`：

- bonding_curve；
- canonical_pool；
- noncanonical_pool；
- burn；
- locker；
- creator；
- program/treasury；
- unknown user entity。

然后才计算 `circulating_user_top10_share` / `economic_entity_top10_share`。

---

# 9. “池子被撤 / 流动性消失”的系统性研究

## 9.1 协议层语义

### Pump bonding curve → canonical PumpSwap

Pump 官方：

- graduation 自动、原子、不可逆；
- bonding curve liquidity 全部迁到 canonical PumpSwap；
- Pump Program 文档还说明迁移后 LP tokens 被 burnt；
- canonical pool 由 Pump migrate 创建；
- Pump.fun 不再 seed/remove canonical liquidity。

因此 creator 不能把 canonical migrated LP 当普通 LP token 直接 withdraw。

### 普通 PumpSwap

官方 PumpSwap 支持：

- `create_pool`；
- `deposit`；
- `withdraw`；
- 普通 pool creator 获得 LP tokens 并可用来 withdraw。

所以必须识别 canonical status。

### Raydium

CPMM 支持 Deposit/Withdraw；CLMM 支持 IncreaseLiquidity/DecreaseLiquidity。

### PancakeSwap

V2 Router 明确有 `removeLiquidity*`；用户 LP 可以撤部分或全部。V3 同样有 position liquidity removal。

### Uniswap/Aerodrome/其它 EVM AMM

通常 LP position 可 decrease/remove；需按协议事件/position 语义识别。

## 9.2 本机同 pair 60m 描述性审计

为了避免把 pair migration/主池切换误判，按固定：

`chain + dexId + pairAddress`

取该 pair **第一次达到 $12k liquidity** 的当时快照，然后要求至少有 >=30m 后的同 pair observation，标签：60m 内同 pair liquidity 是否 ≤ baseline 10%。

成熟 pair：2,864；其中 1,072（37.4%）满足“60m ≥90% 同池流动性崩塌”描述性标签。

分 surface：

- BSC PancakeSwap：~850，~84.5%；
- Solana PumpSwap：748，~43.0%；
- Solana Raydium：171，0%；
- Robinhood Uniswap：~852，~1.4%；
- Solana Meteora：69，~18.8%；
- Base Uniswap：81，~4.9%；
- Solana Orca：36，~5.6%。

**这些差异高度 confounded**：Token population、发现时间、provider semantics、market surface 都不同，不能说“Pancake 一定会 rug”。

但它证明：liquidity survival 是当前系统非常重要且高频的研究目标。

## 9.3 当时特征与 collapse 的探索关系

全体/主要 surface 的回顾比较出现：

- 更年轻 Token 更脆弱；
- 较低 market cap 更脆弱；
- 较高 tx/liquidity、volume/liquidity 反而常与后续 liquidity collapse 同时出现；
- 高 buy ratio 并不代表安全。

例如 BSC/Pancake 样本中低 mcap 半组 60m collapse 约97%，高半组约71%；高 tx/liquidity 组约93%，低组约76%。PumpSwap 中高 tx/liquidity 组约54%，低组约33%。

这些仅说明“狂热交易也可能发生在极不稳定池子里”，不是生产规则。

## 9.4 建议新增 `liquidity_survival_shadow/v1`

严格未来注册，固定同 pair/surface：

- baseline；
- 1m/5m/15m/60m；
- reserves/liquidity；
- route amount-specific min output；
- pool canonical status；
- LP owner/lock evidence；
- creator/related entity；
- relevant onchain Mint/Burn/Deposit/Withdraw/Sync/DecreaseLiquidity/migrate events；
- terminal `lp_withdrawal / sell_drain / migration_or_pair_switch / no_route / provider_unobservable / unknown`。

只在链上 event/LP ownership 足以证明时标 `lp_withdrawal`；否则只写 observed liquidity collapse。

---

# 10. 新闻、叙事和市场本来就是双向反馈

学术结果不支持“永远单向”：

- Finance Research Letters 2023：Narrative attention 上升与相关币收益上升有关；币价格上涨又吸引更多 narrative attention，整体表现为双向动态关系；
- International Review of Economics & Finance 2021：多数 crypto 的 Twitter/Google attention 与 returns 存在双向 Granger causality；Twitter 影响更短期；
- Journal of Banking & Finance 2025：abnormal Twitter attention 与 contemporaneous/next-day returns 正相关，预测性来自 investor ticker tweets，而不是项目官方账号；
- Twitter P&D 研究：promotion 会推高关注和价格，但晚到 Twitter 参与者在 dump 后卖得更迟，损失更大。

因此正确架构必须保存**lead-lag 和 lifecycle**，不能只保存“新闻存在/不存在”。

---

# 11. NarrativeEpisode：比 Event→Token 更适合 Meme 的逻辑抽象

建议不更换 SQLite，只新增轻量表/视图：

`narrative_episodes`
- episode id/version；
- canonical semantic key；
- category；
- created_at/first_available；
- state；
- decision_eligible=0 起步。

`narrative_observations`
- source observation；
- claim/action type；
- author/entity；
- exact post/repost/original；
- duplicate fingerprint；
- narrative role；
- available_at。

`token_narrative_bindings`
- token_id；
- episode_id；
- identity confidence；
- binding basis；
- fanout/clone context；
- as-of time。

这能自然表达：

- 一个 Narrative 对很多 clone；
- 一个 Token 同时吃多个 Narrative；
- Narrative 先发生但 Token 后创建；
- Token 先动、Narrative 后出现；
- 同一叙事从 ignition→crowded→decay。

不要上 Neo4j；SQLite 足够。

---

# 12. Social/Narrative 评分不应直接使用一个分数

第一阶段保存向量：

- `narrative_quality`
- `factual_confidence`
- `unique_creator_count`
- `unique_message_count`
- `duplicate_ratio`
- `creator_growth_rate`
- `mention_velocity`
- `engagement_velocity`
- `cross_platform_breadth`
- `watchlist_reputation_weight`
- `social_dominance_proxy`
- `promotion_fraction`
- `manipulation_risk`
- `heat_state`
- `heat_acceleration`
- `price_lead_lag`
- `coverage_scope`

如果 UI 最后需要一个 Edge Rank，可以生成，但生产 gate 不能只看它。

---

# 13. KOL 经验帖如何系统化利用

## 13.1 不是“跟单”

每条 KOL 内容进入 `KOL Hypothesis Library`：

- author/entity；
- post URL/status id；
- published_at；
- ex-ante / retrospective；
- claim type；
- chain；
- launchpad；
- regime；
- metric；
- proposed direction/threshold；
- rationale；
- evidence scope；
- promotion/conflict markers。

LLM 负责抽取 hypothesis，不负责证明。

## 13.2 验证标签

以后新 Token 上：

- executable 15/60/240 return；
- realized dynamic-exit PNL；
- MAE/MFE；
- liquidity survival；
- route failure；
- catastrophic loss；
- canonical error；
- rug/manipulation label。

禁止用 future ATH。

## 13.3 KOL utility

成熟后可学习：

- early lead；
- incremental recall；
- incremental precision；
- forward net-EV contribution；
- false positive；
- post-pump lateness；
- promotion conflict；
- sample size shrinkage。

小样本神预测不能高权重。

## 13.4 当前实际可实现性

最现实的是从现有 browser watch / priority X 收集的公开 KOL 开始，做局部 corpus。不要假装已有全 X 覆盖，也不需要立即买昂贵 social API。

---

# 14. 买入后持续关注新闻/热点：应该怎样实现

建议 `position_information_watch/v1`，**event-driven**：

## 持仓开启时

冻结：

- token_id；
- narrative_episode_id；
- creator/entity；
- exact source links；
- primary claims；
- entry narrative state；
- entry heat state；
- entry market state。

## 持仓期间 deterministic watch

提高：

- exact token X links；
- creator/public figure exact posts；
- narrative keywords；
- correction/retraction/denial；
- liquidity/route；
- creator/related-wallet state。

## Agent 触发条件

只在：

- new exact source revision；
- new independent origin；
- contradiction/correction；
- important public-figure action；
- narrative state transition；
- creator/LP anomaly 需要语义解释

时运行增量 Agent。

## 退出 challenger

可研究：

- narrative decay；
- correction/denial；
- social acceleration sign flip；
- creator/entity net sell；
- organic-to-promo transition；
- liquidity survival deterioration。

但真实退出仍由 deterministic route/price/risk 层执行。

---

# 15. 多链：Solana / BSC / Base / Robinhood

## 15.1 发现层

四链发现可以继续；但 Candidate/Paper promotion 必须按链独立成熟。

## 15.2 Solana

- Pump/PumpSwap/Raydium/Meteora 等 surface-aware；
- Jupiter amount-specific quote 已有 Shadow 资产；
- Pump fees 现在动态且 creator fee 存在；不能永远固定 125bps；
- priority/network fees需纳入；
- targeted RPC first-buyer/developer data可做。

## 15.3 BSC

- 当前合约安全基本可用；
- Honeypot simulation 应成为 Shadow 必选候选；
- Pancake LP withdrawal/creator/LP holder 是优先风险；
- 0x 支持 BSC amount-specific routing；
- 本地 liquidity-collapse 频率提示 BSC 更应优先补 liquidity survival / LP proof，而不是先放宽交易门。

## 15.4 Base

- GoPlus/0x 均可覆盖；
- 网络费必须包括 L2 execution + L1 security/data fee；Base 官方 GasPriceOracle 可给 L1 fee；
- 当前 main Paper 曾把 cbZEC 纳入，说明资产类型门需补。

## 15.5 Robinhood Chain

- 0x 2026-07-31 已支持 chain 4663，且覆盖很多 native DEX/bonding curves；
- GoPlus 2026-07-28 已加入 4663；
- 当前代码 `SafetyChecker` 仍明确 `execution_safety_unsupported_chain`，属于实现落后，而非外界无能力；
- 先研究-only quote/safety/cost，不能直接 Candidate promotion。

---

# 16. 主 Paper 执行升级

优先目标不是“更精确的固定 slippage”，而是：

## Solana

- amount-specific Jupiter BUY minimum output；
- acquired quantity = minimum output；
- SELL exact acquired/remaining amount -> USDC min output；
- provider/request/response clock；
- quote age；
- route failure/no-route；
- platform fees + priority/signature/rent；
- Pump dynamic pool fees。

## BSC/Base/Robinhood

- 0x `/price` 可作研究 indicative；
- firm `/quote` 需要 API key/taker 等部署设计，需注意不把 secret 写入项目；
- Shadow 应保存 sellAmount/buyAmount/minBuyAmount、token taxes、totalNetworkFee、gas、gasPrice、route/source；
- Base 额外核对 L1 fee；
- no route / fee-on-transfer / max sell 失败都保留。

在 Shadow 证明后，才替换主 Paper mark±4%。

---

# 17. 最终建模：不要急着让 LLM 直接决定买卖

推荐职责：

## Deterministic code

- polling；
- timestamps；
- CA；
- exact pair；
- price/volume/tx；
- wallets/flows；
- route；
- fees；
- risk gates；
- sizing；
- exits。

## LLM

- Narrative episode；
- semantic binding；
- meme type；
- factual/claim state；
- sarcasm/repost/original/denial；
- narrative quality；
- KOL hypothesis extraction；
- contradiction summary；
- explanation。

## Statistical model — 等样本成熟后

先用可解释模型：

- regularized logistic / ordinal；
- survival/hazard；
- gradient boosting；
- calibrated probabilities。

标签：

- executable net return；
- survival；
- catastrophic loss；
- dynamic exit PNL；
- no-route；
- liquidity failure。

严格 temporal train/validation/test，不用 future ATH。

---

# 18. 开源/成熟项目应怎样用

## MELT

GitHub `git-disl/MELT`：pre-migration transactions + bundle traces + high-risk launch features/model。非常适合**借鉴 feature definitions、bundle/wash/manipulation detection**。

注意 license/data体量；不要把 >1TB 数据流程直接搬进本项目。

## RED-COHORT-2026

公开 1,012 sniper cohorts + detection code + placebo/robustness。适合借鉴 early-wallet co-occurrence graph 和因果反例。

## Pump official docs/SDK/IDL

优先复用来解码：create/buy/sell/migrate、canonical PumpSwap、creator fees。

## Solana RPC

`getSignaturesForAddress` + `getTransaction` 足以先做 shortlist targeted first-N buyer/creator behavior。公共 RPC 不够时再上 Yellowstone/Geyser。

## Yellowstone/Geyser

适合以后需要 sub-second / 全量交易流时；不是当前第一步。

---

# 19. 研发优先级

## P0 — 先修会改变真实性/安全性的断点

1. **完成 active outcome sampler deadline correctness**：当前已有 4 个 natural `scheduler_missed_deadline`，不能把 provider/host blocking 与 deadline finalizer 串在同一无界 await 路径。
2. **Immutable launch facts**：冻结 Pump creator/initial buy/curve/signature/surface，防止 token raw overwrite。
3. **Market-surface classifier**：chain/dex/pair/launchpad/canonical/noncanonical/liquidity ownership semantics。
4. **Liquidity survival / failure-mode Shadow**：固定同 pair，分类 LP withdrawal vs sell drain vs migration/provider missing。
5. **Main Paper execution research parity**：Solana Jupiter amount-specific；EVM 0x research-only quote/cost；不直接改现有 Paper 直到验证。

## P1 — Meme behavioral integrity + Narrative

6. GoPlus rich holder/creator/LP fields append-only Shadow；surface-aware normalization。
7. Solana targeted first-N buyer / creator transaction Shadow；公开 RPC first，Yellowstone later。
8. NarrativeEpisode + neutral lead-lag ledger。
9. Social Heat/Acceleration/duplicate/creator-count local coverage features。
10. Position-aware incremental narrative monitoring。

## P2 — 学习与策略 challenger

11. KOL Hypothesis Library；
12. ChainRegime；
13. Statistical challenger；
14. behavioral risk 通过前向样本后才可成为 hard gate；
15. Base/Robinhood Candidate promotion 需独立 execution/safety/cost maturity。

---

# 20. 每个新模块的因果边界

第一版一律：

- append-only；
- activation point；
- no historical backfill；
- `decision_eligible=0`；
- `affects=none`；
- fixed as-of clocks；
- complete denominators；
- missing/error/no-route terminals；
- 不按后来赢家选 cohort；
- 不改生产 gate；
- 不启动额外 Agent 并发。

只有未来样本跨日期成熟，且：

- coverage 足够；
- false-positive/false-negative 可解释；
- route/cost 可执行；
- catastrophic loss 下降或 risk-adjusted EV 提升；
- holdout 仍成立；

才单独评审 promotion。

---

# 21. 关键外部证据与来源

以下用于研究，不代表任何单一来源直接决定策略：

### Narrative / social attention
- Nguyen, Nguyen & Do, *Narrative attention and related cryptocurrency returns*, Finance Research Letters 56 (2023), DOI 10.1016/j.frl.2023.104174.
- Maître, Pugachyov & Weigert, *Social media-based attention and the cross-section of cryptocurrency returns*, Journal of Banking & Finance 178 (2025), DOI 10.1016/j.jbankfin.2025.107518.
- Li, Goodell & Shen, *Comparing search-engine and social-media attentions in finance research: Evidence from cryptocurrencies*, International Review of Economics & Finance 75 (2021), DOI 10.1016/j.iref.2021.05.003.
- Ardia & Bluteau, *Twitter and cryptocurrency pump-and-dumps*, International Review of Financial Analysis 95 (2024), DOI 10.1016/j.irfa.2024.103479.
- Santiment Academy, Unique Social Volume / Social Dominance / Trending methodologies, https://academy.santiment.net/
- LunarCrush methodology/docs, https://lunarcrush.com/support/how-does-lunarcrush-analyze-social-media-data
- Kaito Yaps methodology, https://faq.yaps.kaito.ai/support/yap-faqs

### Manipulation / rug / sniper
- Mongardini & Mei, *A Midsummer Meme’s Dream: Investigating Market Manipulations in the Meme Coin Ecosystem*, USENIX Security 2026, https://www.usenix.org/conference/usenixsecurity26/presentation/mongardini
- Cernera et al., *Token Spammers, Rug Pulls, and Sniper Bots*, USENIX Security 2023, https://www.usenix.org/conference/usenixsecurity23/presentation/cernera
- Li et al., *Catching the Rug: Early Prediction of Fraudulent Memecoins on Solana via Machine Learning*, arXiv:2608.20271.
- Kamat, *Coordinated Sniper Cohorts on Pump.fun*, arXiv:2607.02795 + RED-COHORT-2026 Zenodo.
- MELT GitHub, https://github.com/git-disl/MELT

### Pump / liquidity / execution
- Pump.fun bonding curve docs, https://pump.fun/docs/bonding-curve
- Pump.fun fees, https://pump.fun/docs/fees
- Pump public docs / PumpSwap / IDL, https://github.com/pump-fun/pump-public-docs
- PancakeSwap V2 router/remove liquidity, https://docs.pancakeswap.finance/to-delete/smart-contracts/pancakeswap-exchange/v2-contracts/router-v2
- Raydium docs, https://docs.raydium.io/
- 0x supported chains & Swap API, https://docs.0x.org/docs/introduction/supported-chains and https://docs.0x.org/
- Base network fees, https://docs.base.org/base-chain/network-information/network-fees
- GoPlus Token Security API, https://docs.gopluslabs.io/
- Honeypot.is API, https://docs.honeypot.is/ishoneypot
- Solana RPC getSignaturesForAddress/getTransaction, https://solana.com/docs/rpc/

---

# 22. Lead 最终架构判断

**REVISE，而不是推翻。**

当前 memeTrader 已经有相当不错的严格时序、完整分母、两向发现、基础安全、Paper、Jupiter Shadow 和 source-fact 结构。真正的下一阶段不应再继续围绕“多抓几条新闻/加几个 Agent/调 candidate 分数”做局部优化。

应该把系统升级成：

```text
Narrative/Event Radar ────────┐
                              │
Token / Launch / Pool ────────┼──> TokenIdentity + NarrativeEpisode
                              │
On-chain Market Ignition ─────┘               │
                                               ├─ Identity Gate
                                               ├─ Contract Safety Gate
                                               ├─ Behavioral Integrity / Insider Risk
                                               ├─ Market-Surface / Liquidity Survival
                                               ├─ Amount-specific Execution / Cost Gate
                                               │
                                               └─ Alpha State Vector
                                                  ├ Narrative Quality
                                                  ├ Social Heat / Acceleration
                                                  ├ Organic vs Manipulated
                                                  ├ Market Microstructure
                                                  ├ Chain Regime
                                                  ├ Lead/Lag / Crowding
                                                  └ Execution Edge
                                                        │
                                                      Paper
                                                        │
                                  Fixed horizon + Dynamic Exit + Failure labels
                                                        │
                                                   Forward Learning
```

这既保留“信息领先价格”的机会，也让“顺着币找原因”的路径天然获得 exact CA，并允许纯链上机会在未来被独立证明。最重要的是：**它把 Meme 真正的风险——clone、操纵、sniper、creator、池子、route、叙事生命周期——变成可测的状态，而不是继续压进一个粗总分。**
