# 外部实证证据：Meme 上涨、衰退、操纵与可证伪方向

研究日：2026-09-07；用途：本轮全历史策略重设计的外部证据输入。本文只新增研究文档，没有访问生产 SQLite、跑回测、安装依赖、调用付费 API、下载大型数据集或修改 Runtime。案例不是交易推荐，也不是已经验证的 alpha。

## 1. 结论和证据分层

外部资料支持优先研究“注意力事件发生后，新增需求是否继续扩散，以及最初一波上涨何时开始失效”。但“名人、热门话题、早期高涨幅、很多交易、上交易所”均不能单独证明后续可盈利。真正缺少的是包含普通、失败、未毕业、被拒绝和缺报价币的共同分母，以及在同一可观察时点、相同成本与退出合同下的对照。

本文用四种标签区分结论：

- **项目事实**：来自本轮读取的项目文档；没有在此子任务内重新查询运行数据库。
- **外部观察**：发行方、浏览器、交易场所或数据提供者公开记录的事件、身份、价格。今日查到历史高低价，只能作事后案例标签。
- **外部统计**：论文作者在其特定数据与方法下报告的结果；本轮未复现。
- **研究推断**：由前述证据提出的待检验机制；不是已被证实的预测规律。

历史数据需要同时区分 `event_time/block_time`、来源首次发布/可取得时间和本地 `observed_at/ingested_at`。事后能从链上重建，不意味着本系统当时已收到；实验必须明确是在评估“可重建的历史假想策略”还是“当时真实可用的前向策略”。不能混合两者的收益。

## 2. 十二个案例：先核对身份，再讨论涨幅

表内“峰值”是数据商历史统计，通常不保证是原池、同一交易规模或可实现成交；未找到可靠起点时不填写从发行价到峰值的收益倍数。所有网页于研究日检索。项目介绍和社区自述只作叙事线索，不把网页上的“公平发行”“强大社区”“官方关联”当审计事实。

| 案例与链 | 核实的时间/外部观察 | 上涨之前或进行中可能观察到什么；本轮证据限度 | 对照与实施意义 |
|---|---|---|---|
| 1. BONK / Solana | CoinGecko 研究记录 2022-12-25 发布，2023-01-02 首 8 天收益 +305.8%，2023-01-05 首 11 天阶段高点 $0.00000487、+3,649%。这是其历史口径，非本系统收益。[研究](https://www.coingecko.com/research/publications/bonk-shiba-doge-growth) | 初始分配/转账、池建立和逐时行情在链上原则上可重建；社交传播在相应发布时可见。但本文没有取得 2022 年完整原池分钟数据及本地接收记录，也没有证明“空投多”预测上涨。 | 检验分配触达能否转成持续新增买方；免费领取账户不能直接等同付费需求。与同链、相近发行期和起始流动性的全部新币比较。 |
| 2. dogwifhat / Solana | CoinGecko 2024 Q1 报告记录 2023-11 发布，2024-03 初市值超过 BONK；历史页记录 2023-12-12 低点 $0.001555、2024-03-31 高点 $4.83。[季度报告](https://assets.coingecko.com/reports/2024/CoinGecko-2024-Q1-Report.pdf)、[历史价格口径](https://www.coingecko.com/en/coins/dogwifhat) | 梯次突破、同池流动性和交易者扩散是可定义的实时特征；帽子形象和后来的 Sphere 筹款故事不能反填到 2023 年买点。两个极值不是一笔可实现交易。 | 区分持续数月传播与微盘首波；不把成熟币走势用于支持“所有新币必须长持”。在观察到的新一波建立独立事件。 |
| 3. PNUT / Solana | 数据商记录 2024-11-04 $0.03187 至 11-13 $2.44 的历史极值。Binance 自身公告确认 11-11 10:00 UTC 开放 PNUT/USDT，并给出准确 Solana 合约。[价格](https://www.coingecko.com/en/coins/peanut-the-squirrel)、[交易场所公告](https://www.binance.com/en/square/post/16083152447162) | 动物事件和上市公告各有自己的发布时间；11-11 公告绝不是 11-04 可用特征。公告给出的“交易开始时间”也不是系统“读到公告的时间”；确切提前量本轮未核实。 | 信息先行臂应比较同新闻的所有地址候选及同批 ACT，而非只选后来胜出的 PNUT；研究公告后相对延续，不能声称预测上市。 |
| 4. FARTCOIN / Solana | 已核对 Solana mint。CoinGecko 历史字段为 2024-10-29 $0.02003 低点、2025-01-19 $2.48 高点。[价格](https://www.coingecko.com/en/coins/fartcoin)、[浏览器身份](https://solscan.io/token/9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump) | AI/病毒式叙事需要当时的原帖和首次接收记录；今天的故事说明不能当当时热度。链上成交与持仓变化可以按区间重建，但原始交易历史获取成本未实测。 | 适合检验话题扩散与净需求是否互补；极端成功案例不可主导阈值和权重。需要同日 Pump.fun 普通、失败及未毕业币。 |
| 5. TRUMP / Solana | 官方网站当前明确 Solana 合约与 80% 关联方分配/三年解锁安排；这是当前可核对的身份/条款，不保证网页在发行时文字完全相同。CoinGecko 记录 2025-01-19 高点 $73.43；Galaxy 2025-03 报告按另一数据口径写 $75.35 高点、03-04 $12.17。保留差异，不混成同一原池行情。[官方](https://gettrumpmemes.com/)、[CoinGecko](https://www.coingecko.com/en/coins/official-trump)、[Galaxy](https://am.galaxy.com/insights/research/march-2025-market-commentary) | 官方发文、精确地址、可见分配、开池和成交流可观测；“后来赚最多的钱包”不可倒推为最初的聪明钱标签。 | 同一事件同时是巨大上涨与大幅回撤样本；应比较早期/延迟发现、供应集中软风险层、首波结束退出，不能只计算峰值覆盖率。 |
| 6. MELANIA / Solana | 已核对 mint；历史页记录 2025-01-19 $13.05 高点、2026-06-06 $0.06625 低点。长期峰谷属于后验回撤证据，不是固定期限回报。[价格](https://www.coingecko.com/en/coins/melania-meme)、[浏览器](https://solscan.io/token/FUAfBo2jgks6gB4Z4LfZkqSZgzNucisEHqnNebaRxM1P) | 名人身份、上市与可见开池能够成为调查触发；它们不能保证持续资金需求。发行分配、发布延迟、流动性变动需要历史版数据。 | 对照 TRUMP：相近生态、相邻时间、相似身份热度，结果与持有路径仍可显著不同。二者彼此影响，不能当独立宏观样本。 |
| 7. LIBRA / Solana，事件身份已核实，准确 mint 本轮未完成独立绑定 | Galaxy 记录 2025-02-14 推文后约一小时市值 $4.5B，发行约两小时后下跌 80%。Bubblemaps 的 2026 回顾声称其当时一小时内发现大规模关联持仓并发出警示；该回顾时间晚于事件。[Galaxy](https://am.galaxy.com/insights/research/march-2025-market-commentary)、[分析方回顾](https://blog.bubblemaps.io/the-libra-playbook-how-one-cluster-drained-87-million-in-a-single-hour/) | 可考察推文、开池、早期地址关系和移除流动性；但“当时一小时内发警示”仍需原始警示时间/全文核验，不能让 2026 年回顾进入 2025 年分钟特征。 | 对“政治身份=可靠”“LP 不卖 token 就不会退出”构成反例。准确 mint 未绑定前只保留事件研究，不接交易重放。搜索结果的 `libra-2` 为星座主题另一币，已排除。 |
| 8. TST / BSC | BNB Chain 2025-03-24 周报列入其前十 Meme 项目；CoinGecko 记录 2025-02-09 $0.5113 高点、2026-03-29 $0.007755 低点，起始成交价未核实。[同期链方周报](https://www.bnbchain.org/en/blog/bnb-chain-weekly-ecosystem-report-march-17th-march-24th)、[价格和合约](https://www.coingecko.com/en/coins/test-2) | 教程/名人关联是事件线索；本轮没有核实最早原视频、首帖与地址出现的精确时间，故不宣称提前捕获。3 月排名不得用于 2 月特征。 | 检验强注意力但基本面解释薄弱的事件能否形成短期净需求；官方频道出现不等于发行背书、长期质量或做市保障。 |
| 9. BROCCOLI714 / BSC | 同期链方周报明确写的是 `(714)`；CoinGecko 对应 `czs-dog`，历史高点 2025-02-14 $0.2580、低点 2026-06-06 $0.01024。[周报](https://www.bnbchain.org/en/blog/bnb-chain-weekly-ecosystem-report-march-17th-march-24th)、[价格/身份](https://www.coingecko.com/en/coins/czs-dog) | 新闻主题可能同时匹配多个 Broccoli 合约。必须以各地址首次独立证据、池建立及资金扩散来比较；后来“714 胜出”、上市和流动性支持不能赋予初始地址正确答案。 | 天然的同叙事竞争研究：份额是否向一个地址持续集中，而其他克隆没有同样净需求。不能只保留最终龙头。 |
| 10. BROCCOLI080 / BSC，对照而非“同一个 Broccoli” | CoinGecko `broccoli-2` 绑定另一个合约，记录 2025-02-17 高点 $0.006000；其 2026-03-27 极低值异常，需原池真实交换复核后才可作为经济标签，不能直接当零价。[身份/价格](https://www.coingecko.com/en/coins/broccoli-2) | 与 714 共享主题不代表共享团队/池/收益；“首发、公平分配、社区接管”在当前介绍中只是项目自述。首发时间与早期集中度仍待链上核实。 | 属于被热门叙事遮蔽的同题材对照。观察覆盖和稀疏报价本身应单列；不能把未报价都计作全损或删掉。 |
| 11. SQUID / BSC | CertiK 2021-12-17 复盘确认 2021-11-01 前后的暴涨与 rug pull，并描述买入后无法卖出的限制。其不同文章/排版的峰值及涨幅口径不一致，因此不采用极端宣传倍数。[CertiK](https://www.certik.com/blog/Rugpull)、[合约浏览器风险标记](https://bscscan.com/address/0x87230146e138d3f296a9a77e497a2a83012e9bc5) | 当时合约权限、卖出限制与失败交易原则上可检查；本文未在历史区块模拟。最终盗取/处罚标签只作事后结果。 | 价格暴涨不等于可变现收益。此类已知不可转售事实应归协议/执行不可行；不要拿市场价乘持仓制造虚假赢家。与普通价格崩跌的机制分开。 |
| 12. SIREN / BSC，近期历史事件 | CoinGecko 记录 2025-03-10 $0.02635 历史低点和 2026-04-17 $2.23 高点，构成近期大幅波动案例；不是发行价到可成交高点的策略回报。2025-03-24 链方周报已列 SIREN，早于此 2026 高点。[价格/合约](https://www.coingecko.com/en/coins/siren-2)、[早期周报](https://www.bnbchain.org/en/blog/bnb-chain-weekly-ecosystem-report-march-17th-march-24th) | 2025 年存在记录可证明其不是 2026 才出现的新币；是否经历静默后复苏必须用当时滚动基线验证。本轮未核实“做市商操纵”等当前网页叙述，不当成事实。 | 用于反驳“只需研究发行前几分钟”的覆盖假设；成熟币复苏应重新登记事件，不能以未来第二波为首波长期套牢辩护。 |

上述十二例有意覆盖成功和失败机制，**它们仍是目的性抽样，不是无偏普通币样本**。补充背景对照：同一 CoinGecko 2024 Q1 报告列出 SAMO 约 $60M、WIF 约 $4.6B 的期末市值；只能证明当时狗主题币分布不同，不能推出 SAMO 未上涨或把它当同龄新币对照。普通币的统计结论必须来自下文的完整枚举分母。

### 身份表：只使用本轮实际绑定的地址

| 案例 | 地址 | 绑定证据强度 |
|---|---|---|
| BONK | `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` | [Solscan 名称及官网链接](https://solscan.io/token/DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263)；当前身份，非历史持仓特征 |
| WIF | `EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm` | [Solscan](https://solscan.io/token/EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm)；排除同名新 mint |
| PNUT | `2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump` | 上述交易所公告和 Solscan 双来源 |
| FARTCOIN | `9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump` | CoinGecko 外链落到同名 Solscan token |
| TRUMP | `6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN` | 官方网站；其当前 TRON 地址不是本案例 |
| MELANIA | `FUAfBo2jgks6gB4Z4LfZkqSZgzNucisEHqnNebaRxM1P` | CoinGecko 外链落到同名 Solscan token |
| LIBRA | `UNVERIFIED_IN_THIS_RESEARCH` | 搜索同名冲突；不猜地址 |
| TST | `0x86bb94ddd16efc8bc58e6b056e8df71d9e666429` | CoinGecko 完整合约字段 |
| BROCCOLI714 | `0x6d5ad1592ed9d6d1df9b93c793ab759573ed6714` | CoinGecko 明确指向的浏览器地址；BscScan 直接访问返回 403，链上独立复核未完成 |
| BROCCOLI080 | `0x12819623921be0f4d5ebfc12c75e6d08a1683080` | CoinGecko 明确指向的浏览器地址；同样 403，未声称链上复核通过 |
| SQUID | `0x87230146e138d3f296a9a77e497a2a83012e9bc5` | BscScan token 名称及 drained/heist 风险标记 |
| SIREN | `0x997a58129890bbda032231a52ed1ddc845fc18e1` | CoinGecko 完整合约字段 |

身份数据商与发行方可以用于定位，但进入历史重放前仍须补齐该次事件的具体池、mint/chain、创建交易和历史协议版本。符号、域名、今日最佳池及今日聚合价格不能替代它们。

## 3. 外部统计：真正有用的分母与限制

### 3.1 四链 Meme 与操纵：USENIX Security 2026

Mongardini、Mei 的 *A Midsummer Meme's Dream* 收集 34,988 个 Ethereum/BSC/Solana/Base Meme，初始来源为 2024-10 中旬聚合器与 DEX 列表，并扩展名称分类。作者在三个月跟踪中识别 707 个收益超过 100% 的币，其中 82.89% 呈现其定义的人工增长迹象，包括 wash trading 和小资本推高薄池价格的 LPI。**分母是该研究的高收益子集，不是所有 Meme；检测迹象不是司法事实，也不是可交易预警精度。** 聚合器收录、名称分类、初始存活及最高价筛选均限制外推。[会议论文与摘要](https://www.usenix.org/conference/usenixsecurity26/presentation/mongardini)、[方法 PDF](https://www.usenix.org/system/files/conference/usenixsecurity26/sec26_prepub_mongardini.pdf)

论文提供 [代码/数据 DOI](https://doi.org/10.5281/zenodo.17830943)。本轮 Zenodo 页面访问被工具安全策略拒绝，没有绕过；因此文件清单、大小、许可和原始分钟记录完整性未核实。可优先用于审查操纵模式与外部抽样设计，不能声称已取得可回测数据。

### 3.2 MemeTrans 已更名 MELT：明确的毕业选择偏差

2026-02 论文报告超过 40k 个**成功迁移到公开 DEX** 的 Solana 新币，含迁移前约 30M、迁移后约 180M 交易和 122 个特征，涵盖活动、持仓集中、时序与 bundle。作者声称其任务下减少损失 56.1%；本轮未复现，不等于正期望交易策略，且未毕业币不在该定义的主分母。[论文](https://arxiv.org/abs/2602.13480)

当前 [MemeTrans](https://github.com/git-disl/MemeTrans) 仓库仅指向 [MELT](https://github.com/git-disl/MELT)。新 README 写明原始交易大于 1 TB，提供 Google Drive 上的解析交易/bundle，以及可跳过重算的 `feature.pkl`；许可为 CC BY-NC 4.0，商业用途需作者另行许可。没有下载或运行文件。应只借鉴有明确定义的少量可实时特征；不能默认整包适合生产或把“当前已发布的 feature.pkl”当每一分钟可用特征。

### 3.3 新近 Solana 风险论文：五分钟模型不能覆盖五分钟前死亡

2026-08 的 *Catching the Rug* 声称研究 7 个月、6.4M 个 Solana token，并用最初 5 分钟交易训练树模型、讨论 PumpFun/Raydium 跨来源泛化。这是新近预印本；此处只确认论文公开摘要，没有独立核实完整数据、标签规则和代码可得性。五分钟输入必须在五分钟结束后决策，不能把成果写成发行瞬间安全识别；首五分钟已死亡样本的处理是关键审查点。[论文](https://arxiv.org/abs/2608.20271)

### 3.4 BSC/Ethereum 的短寿命与重复发行者

USENIX Security 2023 的 *Token Spammers, Rug Pulls, and Sniper Bots* 覆盖两链从起始至 2022-03 的 token/pool，报告约 60% token 活跃少于一天，以及极少数地址反复发行。其“活跃”定义和链/时代不同，不能直接套成本项目死亡率。它支持把**发行者截至当时的历史**和短寿命普通币纳入枚举，而不是只读知名币。[论文页面](https://www.usenix.org/conference/usenixsecurity23/presentation/cernera)

### 3.5 Wash trading 研究是机制参考，不是跨链现成分类器

Victor、Weintraud 研究 Ethereum 的 IDEX/EtherDelta，识别自成交、双账户与复杂循环结构。研究对象是早期订单簿 DEX，不能把其阈值直接当 PumpSwap/Four.meme 的 AMM 判据；共同资金来源也可能是交易所、路由器或合法分发。[论文](https://arxiv.org/abs/2102.07001)

### 3.6 大量策略/版本的选择偏差

Bailey 等的 PBO 和 Deflated Sharpe Ratio 讨论重复试验、选择偏差与非正态收益造成的绩效膨胀。对本项目的直接推断是：206 个槽位或多个版本不能当 206 份独立证明；应记录所有尝试并以共享 token/event 和日历时间分块，冻结选择后只在新时间段评价。DSR/PBO 不能在极少样本、缺交易、非共同回报面板上机械生成可信概率。[PBO](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)、[DSR](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)

## 4. 免费获取、成熟实现与单机成本

| 来源/实现 | 本轮实际可确认 | 最小可用方式与成本边界 |
|---|---|---|
| 已有本地 L0 / outcome | 项目 `L0_OUTCOMES_RELEASE_2026-09-06.md` 记录原池价格/流动性退出及 0/15/60/240 分钟 outcome；未知保留，使用既有快照、不补历史队列。此为文档事实，实际全历史覆盖由主任务另核实。 | 优先复用，零新增外部请求；可研究延续失败和退出。不存在的金额流/钱包广度不能从成交次数推造。 |
| DEX Screener 官方 API | 当前参考文档列 latest profiles/boosts/ads、paid orders 和现时 pair；pair 类 300 req/min，profile/boost 类 60 req/min。不是历史 rank/boost 档案服务。[参考](https://docs.dexscreener.com/api/reference) | 可前向低频登记注意力/推广事件并记首次接收时间；广告/boost 是付费推广，不是自然关注。限额是上限，不能变成应当打满的目标。 |
| GeckoTerminal / CoinGecko | keyless 公共入口存在并受 IP 限流；官方变更说明超过最近六个月的 onchain OHLCV 属付费档，取决于池开始跟踪时间。[公共入口](https://docs.coingecko.com/docs/keyless-public-api)、[历史限制](https://docs.coingecko.com/changelog/10122018) | 旧案例全分钟回测不能假定免费可取。公开历史高低价适合核对案例，不等于原池精确路径。无需为此次研究购买 API。 |
| Solana 原生 RPC | `getSignaturesForAddress` 返回地址在 accountKeys 中出现的签名，带 slot、可能为空的 blockTime；不是自动给出 token 的所有 swap。[方法](https://solana.com/docs/rpc/http/getsignaturesforaddress)；公共 RPC 有可变限流。[公共端点](https://solana.com/docs/references/clusters) | 地址历史分页加 getTransaction 解析是按交易数增长的成本；热门币全历史可能很重。mint、池、vault、路由账户需正确映射，缺档不能算无活动。先做少量身份/指定时间窗，不扫全链。 |
| Pump 官方文档/SDK | 官方维护 [pump-public-docs](https://github.com/pump-fun/pump-public-docs)，包含 Pump、PumpSwap、IDL 和版本变更，当前已有新的 v2 trade 指令/quote 支持。 | 复用官方布局定义而非猜字段。历史解析要按当时程序/布局；2024 Raydium 迁移与后续 PumpSwap 路径不可混算。此次仅浏览，不安装。 |
| Four.meme 官方集成 | [Protocol Integration](https://four-meme.gitbook.io/four.meme/brand/protocol-integration) 发布版本化 API 文档与 TokenManager/Helper ABI；[机制说明](https://four-meme.gitbook.io/four.meme/guide/how-it-works) 包含曲线完成后迁移与开发者同交易先购机会。 | 用当时 ABI/事件检查真实过程；“平台公平发行”不代表无 bundle/预买。公共 RPC/日志限制须实测，不能由文档宣称已接通，当前机制/门槛不能回套旧版本。 |
| MELT / USENIX 数据 | 有公开论文/数据入口，但 MELT 非商业许可，解析包规模未核验；USENIX DOI 文件入口受访问阻止。 | 当前仅适合文献/字段参考；不下载 >1 TB，不擅自扩大算力/许可范围。轻量元数据清单若后续依法可取得，再逐字段审查。 |
| 交易所官方公告 | 本轮已取到带日期、交易时点和精确地址的 PNUT/ACT 官方账号公告。 | 公告可低成本成为信息事件；“公布时间”“开始交易时间”“本地发现时间”分别保存。正文删除/改版要保持当时抓取文本；不能靠后来的上市名单。 |

项目已有 PumpSwap flow 规格提出 signed quote flow、有效钱包广度、top-1/top-3 份额、衰退和复苏。**规格存在不证明当前每个 token 都有这些输入**；本文没有读取 SQLite 或宣称全链金额流覆盖。模型和硬门槛必须等实际字段覆盖核实后再决定。

## 5. RH：当前确有主网，但没有凭空补出的历史牛币

Robinhood 2026-02-10 发布的是测试网；截至此次检索，官方当前连接文档已列主网 chain ID `4663`、测试网 `46630`、主网公共 RPC 与 Blockscout，Q2 2026 财报材料也提及主网发布。不能继续用旧的“只有测试网”判断今天。[测试网历史公告](https://robinhood.com/us/en/newsroom/robinhood-chain-launches-public-testnet/)、[当前连接文档](https://docs.robinhood.com/chain/connecting/)、[Q2 官方材料](https://investors.robinhood.com/static-files/2f42ce10-59b7-4880-8371-7d52ede7c22e)

本轮没有找到可独立核实的 RH Meme 主网历史大涨/普通币成组数据、完整 pool 分母或预先可观察的叙事时序。搜索中的 PONS 活动页面有明确**测试网**标签，不能拿测试币金额和价格证明真钱盈利。当前连接文档也注明公共端点限流，历史索引建议 archive provider；此处没有调用任何付费节点。RH 的合格下一步是主网身份与数据覆盖研究，经济结论仍为 **NOT_ESTABLISHED**，不是“已失败”也不是“可迁移 Solana alpha”。

## 6. 研究设计：普通/失败币必须和赢家共享分母

以下是研究推断与可执行设计，不是本轮已经完成的数据实验。

1. **先冻结事件全集**：按链 × 场所 × 程序版本 × 日历窗口枚举所有可观察 create/first-pool/first-discovery；保留未毕业、无成交、只买无卖、被拒、下架和数据缺失。以 first-seen 条件构建 cohort，不能用未来交易次数、ATH 或未来存活作纳入条件。若受资源限制抽样，用预先固定的地址 hash 或时间采样，并报告分母和采样率。
2. **区分三类研究入口**：创建即观察、池迁移后观察、新闻触发后观察。每类 t0 对应其实际发现时间。新闻发生前币尚不存在、发现延迟和身份歧义都有单独状态；不让提前得到结果的 arm 获得隐性优势。
3. **共同历史窗口**：特征使用右闭合 `[t-w,t]` 的已接收观测；冷启动缺历史保留缺失标记。按 token/event 分组并按时间切分；钱包信誉只来自 t 前已成熟、已收录结果。训练归一化、阈值、话题字典及选币/退出参数只在训练窗确定。
4. **普通币与崩跌不是一个类别**：普通 = 在固定 horizon 未达预注册上涨阈值且数据足够；崩跌 = 达预注册跌幅/原池流动性事件；不可交易 = 协议或卖出路径不可行；UNKNOWN = 观测不足；未成熟 = 截止日未到。不能把所有“不赚钱”都叫 rug，也不能把 UNKNOWN 删除来改善胜率。
5. **对照只匹配 t0 已知变量**：同链、同场所、同时间段、相近观察年龄/原池流动性/发现路径。题材组保留全部 competing mint。不要匹配未来交易量、毕业、上市、最高价或后验最佳钱包，否则会消除待检验机制或引入选择偏差。
6. **结果分三层**：发现覆盖/延迟；可交易/数据覆盖；已执行策略收益。价格达到 2x 只说明路径存在，不说明买入后卖得出。固定 15/60/240 分钟等窗口优先复用当前 outcome；若扩展 24h，必须先确认跟踪覆盖，不补造缺点。
7. **策略比较**：相同可观察 t0、相同下一原池观察执行和资金/费用合同下做配对。报告 token/event 数，而非只报多个策略重复成交数；报告净收益中位数、下尾、亏损比例、平均数、贡献最大的几个事件、去掉最大贡献事件后的结果和分期稳定性。按事件/日历块估计不确定性，不能把同币多笔和多策略当独立样本。
8. **退出专门对照**：同一组入场，比较现有退出与候选退出；使用当时 running high、已回收本金和下一帧时点。不能用未来峰值选最好的退出时间。只买到一帧后无报价的记录仍是覆盖风险，不能一律补按最后高价卖出。

本轮历史赢家用于提出机制、测试身份和防未来泄漏，不用于估计无条件胜率。全市场普通币数量、可交易赢家比例、任何候选的收益优势，在完成上述配对实验前均为未知。

## 7. 最有理由先验证的候选与停止条件

| 优先级/候选机制 | 最小字段、对照 | 可证伪预测 | 不成立时怎么处理 |
|---|---|---|---|
| A. 首波延续失败退出 | 已有原池新鲜价格/流动性、持有时间和账本回收；同入场父策略为对照 | 最初短窗后价格/流动性共同恶化时，提前退出降低下尾损失，且净收益改善不只依赖一个 rug 个例。 | 若只是普遍更早卖出导致赢家截断、均值与下尾无稳定改善，停止该机制；不无限微调秒数。 |
| A. 注意力事件 × 价格/流动性确认 | 已有 timestamped 官方事件 + L0；比较事件单独、L0 单独和组合 | 新鲜且身份明确的信息在同市场状态内，增加随后固定 horizon 的净可实现延续；延迟后优势应衰减。 | 若早已被价格反映、只提高新闻赢家召回却净收益无改善，就将其保留为发现工具。 |
| A. 单题材多合约竞争 | 新闻事件地址候选集合、当时原池快照；全候选保留 | 某地址需求份额持续上升相对“最早名字匹配”降低错币率，同时不过度延迟入场。 | 若只有用未来榜首才有效，否定；不要训练 LLM 记住历史赢家地址。 |
| B. 金额净流入 × 有效参与广度 | 真实 quote amount、可去重地址、窗口完整性；与 txn count/总 volume 对照 | 持续净流入且贡献分散，比单钱包/循环交易的同幅涨价更可能继续，尤其是成本后。 | 若实际输入稀疏或延迟，先标 coverage；若覆盖充分但无增量，停止增加钱包/聚类成本。 |
| B. 发行者历史/关联集中作为软风险层 | t 前发行史、已成熟失败、转账关系；保留未过滤高召回臂 | 历史重复短命发行与集中出货对下尾风险有增量信息，且收益损失不来自过度拒绝大赢家。 | 若把合法分发、路由器或交易所来源误聚类，修定义；不默认一共同来源就是一人。 |
| B. 原池流动性减少但价格未明显下跌 | 新鲜原池连续观测、真实移除事件若有；同入场配对退出 | 对退出风险的提示早于价格止损，净回款改善。 | 当前普通 Paper 不增加精确深度/冲击要求；若只有事后链上信息才识别，不能称可提前退出。 |
| C. 成熟币重新活跃 | 冻结静默基线，当前活动/价格/流动性偏离；与同龄普通币对照 | 在新的独立事件入口能区分复苏与随机单笔跳价，且成本后改善。 | 缺基线则不伪造；不能为继续持有首波大回撤寻找事后理由。 |

这些优先级基于机制、项目已记录的字段和资源成本，不是新收益排名。A 类无需先引入大型模型或全链归档；B/C 类须等实际覆盖确认。LLM 适合提出话题、解释身份歧义、寻找官方来源，金额、时序、风险计算、账户与退出仍应保持确定性。

## 8. 本轮明确未证明的事

- 没有证明任何新策略正期望、可实盘、能提前抓住上述所有赢家，或能规避所有 rug。
- 没有取得 2021–2026 所有案例的完整原池高频数据；历史行情聚合口径与本系统执行口径不同。
- 没有取得当年完整社交/boost/rank 档案；今日快照、后验钱包标签、未来 ATH、后来的上市和当前叙事均未用作历史决策特征。
- 外部文献数据没有在此任务复算；全历史生产结果、各版本与污染区间由主任务的独立量化分析负责。
- Nansen 的 LIBRA 历史文章搜索索引可见，但直接访问已重定向到通用 blog；本文未采纳其无法完整直读核验的细分钱包统计。
- Zenodo 访问被阻止、两条 BscScan 地址页返回 403；没有绕过。LIBRA 精确 mint、RH 主网历史赢家/普通币分母、Broccoli080 极低价格的真实成交性仍是具体缺口。

最小研究交付已完成：公开来源、案例身份边界、选择偏差、免费资源限制及候选反证条件均已列出。下一步的策略取舍应由本项目清洁历史与严格前向对照决定。
