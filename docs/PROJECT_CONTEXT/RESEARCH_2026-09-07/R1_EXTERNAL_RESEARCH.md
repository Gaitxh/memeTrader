# R1 EXTERNAL_RESEARCH

Source Chat: 6a9d94ca-7b7c-83ee-885b-1cad2a17c7c6
Retrieved: 2026-09-07 Asia/Shanghai
Actual Chat response; self-described model is not host-verified metadata. External citations embedded in this response require independently resolved primary URLs before reuse.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R1-EXTERNAL_RESEARCH-RESULT
REPLY_TO: C2C-20260907-R1-EXTERNAL_RESEARCH
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: EXTERNAL_RESEARCH
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

### 1. 执行边界

已按 R1 独立评审执行。实际只读访问 `E:\memeTrader`，没有修改代码、数据库、Runtime，没有运行大规模 SQL，没有读取 secret，也没有读取其他 reviewer 的结论。

**实际读过的本地路径：**

- `AGENTS.md`（workspace 打开时加载）
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/REVIEW_SCOPE.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md`
- `docs/PROJECT_CONTEXT/NEXT_STRATEGY_PROPOSAL_2026-09-06.md`
- `docs/PROJECT_CONTEXT/EVIDENCE_COMPLETION_2026-09-06.md`

明确**没有读取/引用仍在生成的** `HISTORICAL_EVIDENCE_MAP.md`、`HISTORICAL_STATISTICS.md`、`EXTERNAL_EMPIRICAL_EVIDENCE.md`，因此下文不声称知道本轮尚未完成的全历史统计。

Chat 模型/推理档位作为项目审计证据：**UNVERIFIED**。当前会话运行身份为 GPT-5.6 Sol，但无法从项目侧独立核验推理档位，因此不冒称 GPT-6/xhigh。

---

# 2. 项目事实

1. 当前生产资金期是 `funding-20260906-v002-final-1000`，206 个独立策略账户；当前已部署 122 个 V002，但这绝不能解释成 122 个独立 alpha。
2. 当前轻量 Paper 合同默认买入 4% + 卖出 4%，额外每 fill 0U，原池门槛 1000U。历史策略必须按**各自当时执行合同**评估，不能把今天的 8% round-trip 机械倒灌进历史。
3. 当前系统已经有相当丰富的、与外部研究直接对应的数据能力：价格、原池流动性、成交量/参与、部分 amountful flow、迁移、first-observed buyer、部分资金来源关系、0/15/60/240 outcome、事件与再次活跃等。
4. 但系统并没有“全量真实钱包图”：项目自己记录过，精确交易观察最多只有少量池/有限签名窗口，48 个参与样本中曾出现 22 个截断、仅 7 个完整、1 个完整双窗。完整 initial holder、隐藏控制关系、全场所逐笔仍不可得。因此外部论文中很漂亮的 wallet features **不能原样假装本系统已有**。
5. 这反而支持当前架构继续优先研究 **L0/L1 可持续取得的数据**，而不是依赖昂贵的全钱包历史。

---

# 3. 外部统计发现：目前最强的一组证据

## A. Pump.fun “成功”本身是极低基率事件

Marino 等对 Pump.fun 研究采用严格时序特征，样本期内约只有 **0.63%** token 达到 graduation。论文最值得本项目注意的不是某个神奇阈值，而是：

- 到达相同 bonding-curve 状态的 Token，未来命运仍然明显不同；
- **以更少交易、更快速度积累真实 SOL** 是最强预测因素之一；
- bot-like activity 较重的币在中后段反而 graduation probability 较低；
- 历史成功交易者出现仅有较弱、非单调改善；
- 所有变量都明确按当时已有信息构造。citeturn171223view0

原文：[Marino et al., Predicting the success of new crypto-tokens: the Pump.fun case](https://arxiv.org/abs/2602.14860?utm_source=chatgpt.com)

**对 GXH 的含义：**

> “涨得快”还不够。更值得分辨的是：达到同样涨幅/曲线位置需要多少笔交易、多少真实资本、多少独立参与，以及这种推进是否是持续承接而不是大量机器人换手。

这与项目已有的 amount-rate、breadth、migration absorption、participation 等方向相当一致，但也提示可以把**路径效率**独立成机制，而不是继续做普通 momentum 的阈值变体。

---

## B. 2026 年 regime 已经和 2025 年明显不同

另一份 832,941 个 Pump.fun launch 的 2026 年研究发现，2026-05-08 至 06-10 的 24h graduation rate 只有 **0.198%**，稳态约 **0.207%**；而前述 2025 样本是约 0.63%。也就是说，同一机制的绝对成功率能跨时期变化超过 3 倍。citeturn135581view4

更有意思的是：

- 有 Telegram：1.485% graduation
- 无 Telegram：0.166%
- 三种 social channel 都存在：1.919%
- 一个都没有：0.110%
- initial market cap > 30 SOL（作者作为 creator self-buy proxy）也有明显更高 graduation hazard。citeturn135581view4turn135581view5

原文及数据：[Pump.fun Graduation Regime Windows study](https://arxiv.org/abs/2607.02823?utm_source=chatgpt.com)

但这里**不能推出**“有 Telegram 就买”或“dev 买得多就买”。Social presence、自买和项目投入程度/操盘能力/营销预算高度混杂。

这项结果强烈支持用户此前观察到的：

> **不同日期、不同时间段、不同市场阶段，策略表现确实可能发生结构性变化。**

因此 GXH 的 regime 设计应当是策略实验的一部分，而不是只在最终报告里按日期解释亏盈。

---

## C. “聪明钱包/早期钱包”是目前最需要降温的故事

2026 年一项研究覆盖：

- 166,098 个 Pump.fun launches
- 1,578,333 个 buyer observations
- 找出 1,012 个长期共同出现的 wallet cohorts。

表面看相当惊人：cohort-touched token 的前 30 分钟 buyer count 提高约 **132%**，SOL inflow 提高约 **136%**。

但是作者加入 activity-matched placebo 后，随机匹配的活跃钱包组对应 buyer-flow lift **反而达到约 216%**，比“真正协同钱包”更强，因此不能把前者解释为 cohort-specific causal alpha。citeturn171223academia0

原文：[Coordinated Sniper Cohorts on Pump.fun](https://arxiv.org/abs/2607.02795?utm_source=chatgpt.com)

**这是对当前 C01/S05/S06 wallet 方向非常重要的约束：**

钱包应该继续研究，但至少要有：

- 同机会对照；
- wallet activity matching；
- 钱包在本系统首次被列入观察之后的严格 forward reputation；
- 不按赢家回溯“聪明钱”名单；
- 不把不同钱包地址自动当不同真人；
- 最终评价的是**复制后、扣成本后还能赚钱吗**。

单纯“几个厉害钱包早买了”暂时不足以进入核心策略。

---

## D. 失败币最危险的地方不是价格跌，而是 Paper 看起来还能卖

2026 年最新 Solana rug 研究使用 **640 万 Token、7 个月数据**，报告大量 fraudulent/rug-like token 在**发行后一小时内**就表现出来，并且只用最初 **5 分钟交易数据**已经能取得相当强的分类能力；跨 PumpFun/Raydium 融合还能降低 domain shift。citeturn845680view0

原文：[Catching the Rug: Early Prediction of Fraudulent Memecoins on Solana](https://arxiv.org/abs/2608.20271?utm_source=chatgpt.com)

这支持一个重要方向：

> 风险模型不应该只检查“买入时 pool > 1000U”，而应该研究买入后前几分钟流动性、卖压、参与、路径突然恶化的**动态状态转移**。

不过论文当前只给出了 ML 结果摘要，我没有获得足够细的 feature importance，故不能杜撰“哪个五分钟变量最重要”。

---

# 4. Ethereum 对照揭示了一个 Paper 回测陷阱

Naviglio/Tarantelli/Lillo 对 2024-10 至 12 月 Uniswap V2 新币研究了 **17,194** 个 Token，其中约：

- 15,114 / **88%** 被两家 honeypot provider 的并集识别为 honeypot；
- 只有约 2,080 / 12% 始终可卖。citeturn845680search1

更重要的是，他们展示了一个看似巨赚的简单策略，但深入检查后发现：

- 最高“收益”大量来自根本卖不出去的 honeypot；
- 一部分其余超额收益依赖 sandwich transaction 中实际上无法外部复制的精确执行位置；
- 低流动性使 sandwich 更有利可图；
- rug 时撤 LP 后，价格数学值甚至可能异常上升，但现实退出能力已经消失。citeturn845680search0turn845680search1

原论文：[Price manipulation schemes of new crypto-tokens in decentralized exchanges](https://doi.org/10.1140/epjds/s13688-025-00602-5?utm_source=chatgpt.com)

这与 GXH 现有“SELL intent / WRITEOFF ≠ 真实链上成交”的项目边界高度相关。

**因此任何漂亮策略如果主要利润来自：**

`极低liq → 极大paper price → 模拟卖出`

应直接进入高危复核，而不是先解释为 alpha。

---

# 5. 真实赢家案例：只保留事前确实可见的部分

| Token | 地址 / 时间 | 暴涨前或暴涨过程中可确认的事前信息 | 不能倒推的内容 |
|---|---|---|---|
| **WIF** | `EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm`; 2023-11-20 | Solana、纯 Meme、已有病毒式 dog-wif-hat 叙事及社区传播 | 本轮没有可靠恢复它最初几分钟的 liq/flow/buyer 快照，因此不能用今天的 holder/community 规模充当早期信号。citeturn908518search0 |
| **BONK** | `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`; 2022-12-08 | Solana 社区型 Meme；早期分发/生态社区本身就是传播机制 | 今天的生态整合数量、持币规模属于后来结果，不能回填。citeturn264076search3 |
| **GOAT** | `CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump`; 2024-10-10 | AI/Truth Terminal meme narrative；第三方部署后，Truth Terminal 的传播/认可成为可观测催化；10/14 已有 CEX listing | 不能说 Truth Terminal 创建了币；这种“外部 narrative actor → 已存在 CA”的时间顺序反而非常适合作为 event experiment。citeturn640559search1turn640559search5 |
| **PNUT** | `2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump`; 2024-11 | Peanut 真实事件形成巨大社会传播；在 Binance announcement **之前**市场估值已经约 $128–129M，随后 listing 又形成清晰的新 event shock | Binance 后达到 $1B/$2B 是结果，不能拿它来证明发币第一小时就该买。citeturn721029search5turn721029search12 |
| **TRUMP** | `6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN`; 2025-01-17 | 极高可信度的一方人物/品牌直接发布，随后极快形成巨大 volume/liquidity/attention | 后来 $14.5B peak、巨额交易费以及最终暴跌都属于未来结果；官方身份不是“长期上涨”保证。citeturn264076search0turn721029news56 |
| **MELANIA** | `FUAfBo2jgks6gB4Z4LfZkqSZgzNucisEHqnNebaRxM1P`; 2025-01-19 | 同样是高度可信一方发布；30 分钟内已快速达到数十亿美元级关注，并明显分流 TRUMP | 它恰好说明“官方+巨大传播”能产生强 impulse，却完全不能保证持续性。citeturn264076search5 |
| **FARTCOIN** | `9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump`; 2024-10-18 | Truth Terminal/AI meme narrative 在数周传播中持续存在；到 12 月在整体 altcoin 下跌时仍显示相对强势 | 47k holders、$1B cap 等是已经走出来后的状态，不是发行时的预测变量。citeturn640559search0turn640559search6 |

地址来源原页：

[WIF identity/launch record](https://www.coindesk.com/en/price/dogwifhat?utm_source=chatgpt.com)
[BONK identity/launch record](https://www.coindesk.com/price/bonk?utm_source=chatgpt.com)
[GOAT listing and contract record](https://support.poloniex.com/hc/en-us/articles/27044550720279-New-Listing-Goatseus-Maximus-GOAT?utm_source=chatgpt.com)
[PNUT early listing/contract record](https://www.bitget.com/asia/support/articles/12560603817829?utm_source=chatgpt.com)
[TRUMP identity/launch record](https://www.coindesk.com/price/trump/platforms?utm_source=chatgpt.com)
[MELANIA launch/contract record](https://www.okx.com/en-eu/learn/melania-trump-coin-launch?utm_source=chatgpt.com)

---

# 6. 上涨币 vs 普通/失败币：目前最可信的事前差异

综合论文和案例，我认为有证据继续前向验证的不是某一个神奇指标，而是以下**组合状态**：

**第一层：资本推进效率。**
相同生命周期/相似初始状态下，更短物理时间、更少交易就能获得更多真实 SOL/quote 资本，比“交易笔数很多”更有意义。机器人制造大量 turnover 甚至可能是反向信息。citeturn171223view0

**第二层：参与扩散，而不是单地址狂买。**
buy count/volume 只有与 distinct participation/breadth、真实资本和持续性联合才值得看。早期 smart wallet 本身不可靠。citeturn171223academia0

**第三层：流动性和价格同步扩张。**
价格快速上涨而 liquidity 不跟、甚至下降，是需要单独作为危险形态研究的。特别是 low-liquidity 环境非常容易产生不现实的 paper return。citeturn845680search0

**第四层：冲击后的承接。**
PNUT、GOAT、TRUMP 等最有价值的不是“有新闻”，而是：事件已发生以后，市场是否出现真实资金、参与扩散、流动性保持/扩张，然后价格继续接受更高水平。只看到帖子就买和等到上涨完成才买都不是理想设计。

**第五层：市场相对强度。**
FARTCOIN 在 broader altcoin selloff 中仍明显上涨，是典型的“市场逆风中自身 demand 独立存在”状态。citeturn640559search0 这给当前 S09 比单纯绝对 momentum 更好的机制依据。

**第六层：传播存在，但传播应是条件变量而非万能门。**
大样本数据显示 social presence 与 graduation 强相关，但这是 association，不足以单独交易。citeturn135581view4

---

# 7. 建议进入 R2/R3 的机制候选

这不是要求 Codex 全部实现，而是外部证据支持程度排序。

1. **Capital-Per-Trade Acceleration**
   同生命周期下测 `Δquote capital / distinct trade`、`Δquote capital / second`，与普通 volume momentum 做同机会对照。直接对应目前最强 Pump.fun 实证。

2. **Broad Organic Absorption**
   价格↑ + liq↑ + distinct participation↑ + buy capital concentration 不恶化。目的不是增加门，而是区分“一两个地址推价格”和“市场接受”。

3. **Price-Liquidity Divergence Rejection/Exit**
   price 急升、liq 不升/下降，独立候选或退出实验。不是永久 hard gate。

4. **Fast Capital → Pause → Second Acceptance**
   第一 impulse 后不追；只有回撤没有摧毁 liquidity/participation，并再次出现净承接才入场。与“第二波/reawakening”相近但应按 episode 独立。

5. **Event → Market Acceptance**
   官方/KOL/真实世界事件本身不直接 BUY；冻结 CA 后观察数分钟 flow/breadth/liq，再下一独立帧成交。GOAT/PNUT/TRUMP 都提供机制案例。

6. **Regime-Conditional Runner**
   只使用当时已经成熟的全市场 cohort outcome 判 HOT/NORMAL/COLD，然后单独测试 runner；不要同时改变 entry+size+exit。

7. **Relative Strength Under Weak Tape**
   当前 S09 值得保留。评价对象应是 observed-set relative strength，不能声称全链 market factor。

8. **Graduation/Transition Path Efficiency**
   对 Pump/Four 的生命周期状态，研究“达到同状态用了多少真实资本时间/交易/参与者”，而非只看 curve completion。

9. **Creator/Self-Buy Shadow，暂不直接交易**
   外部有强 association，但 confounding 太大。作为 feature 收集，并与 creator 后续 sell、participation、liq 路径交互研究。

10. **Wallet Confirmation with Activity-Matched Control**
    可以继续，但必须保留同机会无 wallet 基线和 activity-matched placebo；在这种设计之前不应升为核心。

11. **Early Rug-State Transition**
    首 5 分钟 price/liq/buy-sell/participation 的动态恶化用于独立风险臂，而非仅静态 `liq>=1000`。

12. **Impulse Exhaustion Exit**
    强第一波之后，价格不再创新高 + liquidity 不增长 + participation/flow 减弱，两次独立观察触发早退；直接与当前 S01/S02 类方向兼容。

---

# 8. 我反对目前直接采纳的几类“漂亮特征”

- “聪明钱包买了，所以买。”
- “social channel 多，所以买。”
- “dev 自买，所以买。”
- “交易笔数突然很多，所以买。”
- “已经涨了 300%，所以它是 winner。”
- “当前 holder 很分散，所以发行时就安全。”
- “后来上 Binance，所以发行时能提前判断它会上 Binance。”
- “Paper 最后还能按显示价格卖，所以极低流动性暴涨是真利润。”

这些都有明显的选择偏差、时间穿越或成交可实现性问题。

---

# 9. 可证伪条件

建议最终 10–20 个候选统一要求：

- **全部从真实 deployment frontier 开始。**
- 同一 Token / 同 event / 同 clone family 不能当多个独立市场样本。
- 至少报告 opportunity denominator，而不是只有成交赢家。
- 特征必须记录 `observed_at/ingested_at <= decision_at`。
- UNKNOWN 不转成安全或失败。
- 价格/liq/flow/social/wallet 每一类都保留缺失覆盖率。
- 对 event/wallet 条件策略报告**等待造成的买价变差和错失右尾**。
- 评价成本后净收益，而不是 graduation rate 或涨幅命中率。
- 单独报告 catastrophic sellability/writeoff tail。
- regime 必须用已经成熟的过去 cohort 构造，不能用当日最终赢家反推。
- 不以“删掉最大 1/3 笔以后赚钱”作为晋级证据；尾部本身就是 Meme 策略经济性的核心组成部分。
- 样本不够就是 `INSUFFICIENT_EVIDENCE`，不能为凑 10–20 个“终极策略”制造结论。

---

# 10. 待 Codex / R2-R3 裁决的问题

**Q1.** 当前已有 flow 数据能否可靠计算“capital accumulation per trade/per second”，还是部分链只能退化为 volume proxy？两者必须分版本，不能混称。

**Q2.** distinct buyer/breadth 当前覆盖是否足够稳定？若只覆盖少数精确池，应该只建立 eligible subset，不扩大为全策略 universal gate。

**Q3.** 当前 S09 relative strength 应否成为主要候选之一？外部案例和 regime 研究都支持继续验证，但尚无本项目收益证据。

**Q4.** wallet 系列是否降级为 Shadow/5U experiment，直到 activity-matched placebo 有成熟结果？我的票是 **YES**。

**Q5.** 当前静态 1000U pool floor 是否需要另加动态 liquidity deterioration 实验？我的票是 **YES，但作为行为不同的风险实验，不再提高统一硬门。**

**Q6.** 官方/KOL event 最合理的作用是“候选发现/episode 起点”还是 entry hard evidence？我的票是 **前者**；真正入场仍看事件后的市场 acceptance。

**Q7.** 是否把“达到同样涨幅所需真实资本/交易数/时间”正式作为一个独立 family？我的票是 **YES**，这是本轮外部研究里机制依据最扎实、且与现有数据最匹配的新方向之一。

---

## EXTERNAL_RESEARCH 裁决

**结论：REVISE / CONTINUE EXPERIMENTATION，不支持现在宣布任何“终极盈利策略”。**

目前外部证据最一致地指向的不是“更严门控”，而是四件事：

**真实资本推进效率 + 参与扩散 + 流动性同步 + 催化后的持续承接。**

同时最需要防止的是：

**机器人/钱包选择偏差 + 极低流动性的虚假 Paper 利润 + 赢家事后特征回填 + regime 漂移。**

从本项目已经具备的数据能力看，这四个正向机制大部分可以在**不大改架构、不购买重型数据**的条件下形成严格前向候选，所以值得进入 R2 交叉质疑和最终候选收敛；wallet/social 则应保留，但优先级应低于上述纯市场结构信号。

Codex 保持唯一 writer 与最终裁决。
