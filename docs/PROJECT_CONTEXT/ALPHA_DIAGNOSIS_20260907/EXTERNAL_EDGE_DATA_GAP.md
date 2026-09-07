# 外部机制与数据缺口诊断（2026-09-07）

## 结论边界

这是一次只读、资源受限的字段诊断，不是策略设计、回测、收益认证或采集授权。结论仅比较外部机制可观察性与当前源码中已接入的前向投影；没有读取配置、密钥或运行数据库，没有补历史、增加请求、改变策略或生产代码。

当前系统**已有且可作前向候选输入**的是：同原池的价格、报告流动性、5 分钟成交额及买/卖笔数、`observed_at`/`ingested_at`、局部有界历史、pair 创建时间，以及少量严格完整的 PumpSwap 已解析逐笔流。它并不等于完整链上 order flow。`TokenSnapshot` 虽预留 `buyers_5m`、`holders` 等字段，不能据此声称当前每个 token 都有这些新鲜值。持有人 Shadow 和 vault microstructure Shadow 均显式为 `decision_eligible=false`。

本次的可用性口径：**有数据**必须是当前源码已写入的字段或明确消费者；**新鲜**必须能在决定前以本地 observed/ingested 时间证明；**免费/可行**只表示公共接口原则上提供，不表示当前限额、延迟、覆盖或解析已验证。所有链上地址都只是地址，不是人；所有聚合 volume 都不是净资金流。

## 外部资料（8 项一级来源）及其能证明的范围

1. [Pump 官方 bonding curve 文档](https://pump.fun/docs/bonding-curve)：曲线以储备决定报价；毕业时曲线关闭并原子迁移至 PumpSwap。它证明生命周期状态与报价机制，**不证明**毕业、储备变化或任何阈值可预测收益。
2. [DEX Screener API reference](https://docs.dexscreener.com/api/reference)：最新 pair/token 查询可给 `pairCreatedAt`、price/liquidity/volume/txns 与 profiles/boosts 等接口；它是聚合市场面，**不提供**地址级买家、资金图或逐笔可审计流。
3. [Solana `getTransaction`](https://solana.com/docs/rpc/http/gettransaction)：确认交易可返回 slot、blockTime、交易和 metadata；这使逐笔解码可行，但需要签名发现、协议解析及完整窗口。
4. [Solana `accountSubscribe`](https://solana.com/docs/rpc/websocket/accountsubscribe)：账户变化可推送并带 slot；适合已知账户低延迟观察，不能倒推错过的首分钟交易。
5. [Solana `getTokenLargestAccounts`](https://solana.com/docs/rpc/http/gettokenlargestaccounts)：返回某 mint 的前 20 token accounts；这些账户的供应占比是所观测账户集合占比，不能直接给全部 owner 或识别关联钱包，也不能直接当作实体集中度的上界。
6. [Victor & Weintraud, 2021](https://arxiv.org/abs/2102.07001)：在 DEX 交易图中，循环、往返金额和重复 SCC 可识别部分 wash-trading；该论文需要地址级双边交易图，且结果是操纵识别，不是收益预测。
7. [Xia et al., 2021](https://arxiv.org/abs/2109.00229)：Uniswap 样本显示 scam token/池和协作地址的存在；样本、链和标签均非当前 Solana PumpSwap，支持风险机制假设，不支持迁移出正负 alpha。
8. [Cernera et al., 2022](https://arxiv.org/abs/2206.08202)：Ethereum/BSC 长面板中 token creator 的重复发行与短寿命、sniper/rug 生态有关；是相关性和生态描述，不能把 creator 的历史次数直接当当前 Solana 的因果标签或盈利预测。

## 对照表

## 根代理补充核验：近期直接预测研究

以下均是作者报告，未在本机复现论文数据、代码或PnL，不构成本项目alpha证据。

- [Catching the Rug，2026-08-20](https://arxiv.org/html/2608.20271v1)：前5分钟交易特征预测1小时TVL/Idle标签，采用按发行时间滚动划分。原文Table III确实包含unique buyers/sellers、SOL买卖金额、价格路径等，远多于本项目通用m5计数。Table VI显示跨平台迁移明显下降；作者也明确尚不足实盘部署。标签中的停交易/TVL大跌不等于可执行净收益。文中同时出现“多数rug”与“rug为少数”的不一致叙述，因此不移植其正类先验或以其AUC背书。优先价值是对现有完整逐笔窗口作覆盖诊断，而非立即上线XGBoost。
- [Predicting the success of new crypto-tokens: the Pump.fun case，2026-02](https://arxiv.org/html/2602.14860v1)：研究曲线状态、交易步数、参与者和creator对毕业概率的条件信息；部分钱包/creator按前后半月隔离。其经济模型明确忽略gas、协议和creator费用，且毕业是协议结果，不能当本项目4%/4%成本后的收益。多数non-bot条件曲线仍低于简化回本线；最强creator子组样本稀少。它支持“当前曲线状态不足，参与结构可能增量”的待检验假设，不能证明更多creator即更好，也不能用当前赢家钱包回填过去。
- [Hour-Aware Adaptive Risk Management，2026-08修订](https://arxiv.org/abs/2606.08232)：作者的190笔Paper样本中，事后最差时段比较p=0.5634；删去前三笔累计结果转负。拒绝追踪亦存在大量删失。该研究主要价值是披露拒绝机会、时段探索和尾部敏感性；不支持把小时本身作为alpha。未下载运行所附外部脚本。

这些近期来源与旧Uniswap/BSC操纵研究一起说明：存在可研究的信息维度，但风险识别、毕业概率、Paper收益及可兑现利润必须分开。下一小时优先级是条件式证据修复建议，**不是已经测得各工程方向的盈利ROI排序**。

| External Mechanism | Evidence | Current System Has Data? | Fresh Enough? | Free/Feasible? | Already Tested? | Worth Adding Data? |
|---|---|---|---|---|---|---|
| Launch / bonding curve state | Pump 说明确定性曲线、卒业和原子迁移；是机制事实，非预测证据 | **部分**：`token_launch_facts`、`token_market_surfaces` 有 launch/surface/pair 时间；原始 pair 也有 dex/pair 字段 | 仅已记录 surface/launch 且时间不晚于决定；曲线进度/储备不是通用快照字段 | 公共 RPC 可读，当前数据路径是否覆盖首分钟**未核验** | 现有 migration 141/142 与 surface 风险；非本机制的收益检验 | **P1 条件式**：先只核对已发现 token 的曲线→迁移连续性与时间差；不要扩大 discovery 或建立新策略 |
| Migration / canonical pool continuity | Pump 原子迁移；因此同 token 跨 surface 的 identity 需要链上证明 | **部分**：`migration_lineage` 字段当前填充边界未知；已有 `pool_rpc_verified` 消费点 | 未证明对每次迁移在首后帧前收到 | 公共 RPC 原理可行，当前 RPC 限额/解析/延迟**未核验** | 有 migration candidate，策略图明确仍是输入缺口 | **P0 诊断**：一小时只测量现有池的“已知迁移事件→原池/新池绑定→本地可用时间”，无数据不添加行为 |
| LP ownership / withdrawal / reserve change | AMM 机制说明储备影响报价；Uniswap 研究把抽池作为 rug 行为 | **部分且异质**：surface 有 `lp_position_owner`/`liquidity_control`，已持仓有 accountSubscribe reserve/vault Shadow；普通候选只有报告 USD liquidity | 已持仓 websocket 可快；候选池没有通用订阅。报告 USD liq 不等于 LP 赎回 | 对已知账户公共 RPC 可行；完整 LP 解析和及时覆盖**未核验** | liquidity survival/风险退出已有；非 LP-owner 入场预测 | **P2**：优先修补现有原池 L0 的观察年龄与 identity；不因 LP 机制重新引入全量 quote/depth 或通用硬门 |
| Transaction flow (amount, side, signer) | Solana confirmed transaction 足以提供解码原料；wash 论文说明仅 volume 不足 | **局部**：PumpSwap held collector 能在完整窗口写 `side/signer/amount/slot`，缺失即丢弃；聚合主通道只有 m5 volume/买卖笔数 | 仅已有完整、连续、原池匹配窗口；目前不是所有新 token 的首分钟流 | 公共 RPC 可行但每签名解析成本高；吞吐、完整率和延迟**未核验** | 154/156/183 等 amountful-flow 路线已有，策略图说不保证全 token 有输入 | **P1 条件式**：先度量现有已订阅样本的完整率、首个可用延迟、RPC 成本；若不能在决定窗内完整，保留 Shadow |
| Unique buyers / breadth | wash 论文需要交易图的交易对手，而非计数；地址非人 | **否（通用）/局部**：`buyers_5m` 仅模型槽位；amountful flow 可算 signer 去重但仅局部完整窗 | 聚合 `buys_5m` 不是 unique buyer；局部 signer 仅在窗口完整时新鲜 | 公共 RPC 理论可行，持续全池解析**未核验** | effective breadth 154、bundle-adjusted 158 已有消费 | **P2**：先复用局部完整窗口的 shadow 覆盖分母；不把 `buys_5m` 改名 unique buyers，也不新增钱包图 |
| Holder concentration / issuance distribution | `getTokenLargestAccounts` 只给前 20；不能识别所有 owner/关联账户 | **Shadow only**：holder observer 存 top1/top10、unique owner 等，但采样桶 2/1000、`decision_eligible=false` | 有 h0/15/60/240 观测设计，但未证明完成率与入场时可得性 | 公共 RPC 可行；全 owner 需 token-account 枚举，成本/时延未核验 | 189 issuance-holder 与 holder Shadow 已存在，策略图明确非当前通用输入 | **P3**：不要扩为决策数据；先看现有 Shadow 的完成率/时延，且把 top-20 限为下界代理 |
| Creator history / repeated launches | Cernera 等发现重复 creator 与短寿命/rug 生态相关；跨链历史相关性，不是因果信号 | **部分**：不可变 `token_launch_facts` 和 creator 历史 lower-bound Shadow | 本地开始收集后才有右截断但左删失历史；新 token creator 可及时，历史不完整 | 本地已有；全链 creator 回填不在本次授权 | 157 creator 与 creator-risk Shadow 已覆盖 | **不加数据**：当前是左删失低界，先维持 Shadow/风险说明；不能用后验 rug 标签或全链回填补齐 |
| Funding graph / common funding | wash/SCC 与 rug 协作研究说明关联地址可能重要，但需要实体/边完整性 | **局部**：只暴露已取得 tx 内显式 `observed_funding_transfer`，没有扩张图 | 仅完整 parsed window；未知边不能当无关联 | 公共 RPC 可做局部邻接，广图成本/召回/身份误差**未核验** | 158 bundle-adjusted breadth、common-funding consumer 已有 | **不加数据**：现有项目明确禁止新钱包图；先报告覆盖而不让缺边变安全标签 |
| Bundles / coordinated bots | 研究表明 sniper/bot 与短寿命/rug 生态共同出现；不是 bot=坏/可交易的预测 | **否（通用）**：没有 Jito bundle 身份或首发全量交易序列；vault Shadow 的 `interval_regularity` 只看已持仓 reserve 变化 | 无通用 token-level first-minute 记录，无法及时判定 | 公共 chain 不保证 bundle attribution；免费及时性**未核验** | bundle-adjusted breadth 名称存在，但不等于 bundle 标签 | **不加数据**：缺少可靠、及时、免费 bundle ground truth；不得用固定间隔或 m5 笔数替代 |
| First-minute microstructure | Pump 曲线与逐笔 RPC 说明储备/交易序列可表述；wash 研究显示需要逐笔结构 | **部分但非 entry 通用**：m5 volume/buy/sell、约 20 分钟有界 snapshots；1/3/10/30 秒指标只在 held vault Shadow | 5m 聚合不足以称 first-minute；已知持仓 websocket 不代表发现阶段 | 逐笔 RPC/subscribe 原理可行，发现→订阅→解析抢时能力**未核验** | 现有 v21 vault Shadow，`decision_eligible=false` | **P1 诊断**：只测已有发现 token 从首次本地见到到首个可解析事件的延迟/漏失；未达标不做 microstructure feature |
| Relative strength / breadth across tokens | 这是横截面机制假设；所列资料没有对当前 universe 的可交易预测证明 | **局部**：同 symbol leader、局部 resilience；没有冻结的全市场同批可比集合 | 同批、同 source、同截止才新鲜；当前全市场同步性未证明 | 不新增采集下只能局部；完整 universe 及时性**未核验** | 194–198 和 ranker 已覆盖局部版本 | **P3**：先定义现有同批集合覆盖率，不能把异步聚合榜单称市场相对强度 |
| Latency / receipt ordering | RPC 的 slot/blockTime 与 websocket notification 可记录链上与本地接收差；它们不保证 provider 延迟 | **是（基础）**：snapshot 有 observed/ingested，交易流有 block/received/recorded；但链路全段指标不必然每类都有 | 可检验，前提是按同一 source/pool 比较并保留缺失 | 免费记录本地时钟；跨 provider 到达质量**未核验** | 项目已有三时钟与性能诊断 | **P0**：先量化现有 discovery→identity→first eligible observation 的 P50/P95 和缺失，不增加外部数据 |

## 最值得投入的有条件优先级

1. **P0，下一小时、零美元：迁移连续性和三时钟覆盖诊断。** 目标不是新增信号，而是确认当前原池在 Pump curve/PumpSwap 交界是否会丢失或错绑。交付条件是每个现有样本均能给出 `launch/curve or migration evidence → canonical pair → observed_at → ingested_at → decision eligibility`，不能证明的写 `UNKNOWN`。这是当前 discovery→identity→decision 链中的可观测工程缺口，且不会扩大采集。
2. **P1，下一小时、零美元：在已经收集的 PumpSwap flow 样本上计算覆盖/延迟，不加订阅。** 只报告完整窗口比例、从首次发现到首个完整 flow 的延迟、每个窗口的签名/解析错误。若首分钟大多不可完整获得，unique buyers、net flow、bundle/bot 都应继续是 Shadow 或未知，而非引入代理阈值。
3. **P1，最多一小时、零美元：验证已持仓 vault Shadow 的数据实际只覆盖 held pools。** 若证实，其 1–30 秒 `reserve_slope/regularity` 只适合退出研究，不可回填成 entry microstructure edge。
4. **P2：保留现有 holder/creator/funding Shadow，先看自然完成率。** 在样本、时效、左删失和地址关联不清楚前，任何转为 entry filter 的提议均不成立。
5. **P3/停止：bundle、bot 标签与全市场相对强度。** 当前没有被证实的免费、及时、完整输入。这里继续投入会先产生昂贵数据工程和选择偏差，而不是已被实证的 edge。

## 不能跨越的推断

- 论文/协议证明某类行为存在，不能证明它在本系统、此链、此成本合同下预测净收益；因此本报告没有任何“应当交易”的结论。
- 任何后来的 graduation、rug、死币、top-holder、creator 关联或赢家路径都不能写回较早决定。
- 聚合买卖笔数、volume、报告 liquidity 和 price endpoint 只能是代理；它们不能声称 unique buyers、真实净流、LP 提取、bundle 或真实可成交深度。
- 在 `observed_at` 或 `ingested_at` 晚于决定、窗口不完整、原池不匹配、或 source age 过期时，该字段必须是未知，不得用当前链状态补齐。

本诊断建议先修证据可得性与时效的测量，再决定是否存在值得独立前向验证的特征空间；它不授权新增策略、参数搜索、历史回填或运行采集任务。
