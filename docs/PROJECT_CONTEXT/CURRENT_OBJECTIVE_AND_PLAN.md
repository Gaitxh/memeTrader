# 当前目标与执行计划

更新时间：2026-09-03
状态：`ACTIVE / CONTINUOUS`

## 1. 最终目的

持续提高新 Meme Token 的**样本外、扣除真实近似费用后的风险调整收益**。系统要更早发现可能驱动 Meme 传播的信息，把它与正确且可交易的 Token 建立可审计关系，在 Paper 中验证买入、退出、滑点、费用和尾部风险；只有成熟前向证据成立后，才另立小额真实交易发布线。

“为了赚钱”在工程上具体等于同时改善：

- 有价值机会的及时召回；
- 误报、同名币、推广和陈旧信息过滤；
- exact CA/canonical Token 正确率；
- 报价、流动性、安全和实际成本后的可执行性；
- 最大回撤、尾部损失、集中度和资金占用；
- 多日期、不同市场阶段的样本外稳定性。

不能用更多页面、更多 Agent、更多 Decision、更多 Paper 成交或历史高收益代替上述目标。

## 2. 当前事实判断

系统骨架已经存在并运行：信息-first 与 Token-first 采集、Event 聚类、Event↔Token、Strategy/WAIT/REJECT/CANDIDATE、Paper、SQLite、双语 Web、Agent 与来源审计、15/60/240 分钟前向账本。当前配置是 Paper，Live 硬锁。

主目标尚未完成。2026-09-02 15:31（Asia/Shanghai）的严格最近 24 小时截面里，采集链记录 55,634 个新 Token、2,105 个新 Event，但 Decision 只有 1 个 CANDIDATE、336 个 REJECT、797 个 WAIT；主 Paper 仍只有 1 次 BUY 与随后 1 次 SELL。Token Context 准入账本有 5,224 次评估，其中 365 次 admitted；主要跳过原因为 `no_eligible_trigger=1,885`、`global_cooldown_active=1,725`、未核验 provider-X metadata `599` 和无 metadata seed `572`。当日 Agent 调用与 Token 预算没有形成阻塞。

这说明“新币和事件很多，但及时、独立、精确、可决策的绑定转化率极低”是当前数据支持的判断。采集轮次、provider 返回数和 context-only 条目不能等同于独立事件证据；Agent 准入也不能等同于有效机会。

新的前向结构证据进一步收窄了断点。初算的 `130 组/548 Token` 使用了可变 `token_source_links.first_observed_at`、完整 URL 分组和组内最早链接时间门，不能作为未来注册口径。Lead 独立复核以固定 cutoff `2026-09-02T07:32Z`、X Snowflake `status_id` 去 URL 参数、每个 Token 单独执行 `[-5,180]` 分钟门，并要求不可变 `token_discovery_exposure_source_links.recorded_at` 后，得到更严格的 **103 个帖子 episode、529 个帖子—Token membership、528 个不同 Token**；其中 37 个单 Token episode、36 个 2–4 Token、30 个至少 5 Token，最大 82。全部关系仍是 `provider_metadata / identity`，约 78.8% membership 集中于 `@solana` 与 `@elonmusk`，因此不能当作独立样本或背书，但“同一热点出现大量 CA 分叉”是真实结构。

在按 `status_id` 去重的 106 个帖子中，65 个没有任何 browser-watch Observation，37 个是 Token 链接先到、浏览器正文后到，只有 4 个 browser Observation 不晚于首个 Token 链接。当前 v3 只从触发正文抽显式 CA，3 个自然 cohort 全部为 `no_seed_at_signal`；进一步逐 cohort 核验又表明这 3 个 v3 帖子在信号时 provider-linked Token 数也都是 0。因此，新 shadow 不是“修复 v3 的漏 seed”，而是另一个 Token-first estimand：项目 metadata 引用重点帖子时形成的 CA 歧义与蹭热点风险。两者必须并行、不得合并分母。

仅用于设计、不进入未来新版本分母的严格回顾统计还表明：以首个不可变 exposure-link 为 `T0`，最终 180 分钟 episode 集合在 `T0/30s/60s/120s/300s` 已完整的比例约为 `35.9%/53.4%/64.1%/68.0%/73.8%`。529 个 membership 中只有 16 个在自身链接到达时已有本地快照，只有 3 个同时有完整价格和流动性；约 521 个到 5 分钟才出现首个快照。固定多时点集合轨迹比“首个链接即完整集合”更诚实，也证明 DexScreener `liquidity_usd` 不能替代 Pump/Jupiter 的真实可路由性证据。

因此当前主断点是：

`及时信息/精确原帖 → 新鲜独立事实 → Token 候选集合 → exact CA/canonical → 可执行 Decision → 扣费 Paper 结果`

它不是新币供给不足，也不能仅靠提高轮询、扩大账号表、增加生产 Agent 或降低门槛解决。

## 3. 冻结的不变量

- 严禁未来数据、未来函数、旧赢家回填和后来证据倒灌。
- 每个研究版本必须有 activation point、不可变分母、固定目标时点和 missing/error/zero-yield 终态。
- identity、promotion、项目自述、单源 KOL 帖子不能直接成为交易证据。
- WAIT 必须如实显示，不美化成信号。
- Paper 使用当时可得报价、next-observed/trigger-anchored 执行、滑点和费用；Paper 结果不能称真实利润。
- 当前 Live 保持锁定；网页、插件和 Agent 均不得解锁。
- 生产 autonomous-search 并发保持最多 2；是否增加只能由前向排队和有效产出证据支持。
- 所有项目持久数据保存在 `E:\memeTrader`；不清空或改写 r6，不推送 Git。
- UI 深化后置；只有数据缺失、误导或操作不可用时才优先修 UI。
- ChatGPT 高智能协同当前统一使用用户最新指定的 `@笔记本mcp20260902-2`。关键架构、策略和实验在确属 material gate 时默认使用一条有实质内容的最高强度 Lead 复核；只有结论冲突、信息不完整或影响特别重大时才增加独立会话，普通局部实现/验证不得机械复制多审。ChatGPT 负责研究、反证、方案比较与综合，Codex 验证当前事实、实现和测试。

## 4. 当前执行优先级

### P0：修复信息到证据的真实转化

1. 继续验证 priority request → browser observation → Event → Agent dispatch 的自然前向链。
2. 统计精确原帖的新鲜捕获率、独立 confirmation 产出率、exact CA/canonical 成功率和端到端延迟。
3. 区分 `no_context`、来源不可达、查询 zero-yield、冷却未准入、同名歧义、Token 未发现和安全/执行拒绝。
4. 不用调用量或轮询轮次冒充有效产出。

### P0 实验候选：重点人物低注意力 Token 探针

三条 ChatGPT 独立复核已完成。原始“ticker/叙事词 → Dex 候选 → 事后涨幅”方案为 `NO-GO`。旧 v1 的一个自然 cohort 原样保留；base v2 因读取可变 `events.attention`，在首个 cohort 前明确废弃。当前基线是 `kol-token-addressability-lag/v3-immutable-attention`：只从 exact `(event_id, observation_id)` 的不可变 attention point 冻结注意力定义、数值与记录时间。旧 route v1 与 v3 不兼容并在首个 attempt 前停用；当前 `kol-token-addressability-route/v2-compatible-deadline-edf` 已绑定 v3 version/hash 严格前向注册，区分 pair/request/response 时序与 surface 关系，并纳入共享后台 Jupiter 请求预算。所有记录仍为 `decision_eligible=0 / affects=none`，不能证明盈利、成交、背书或安全。

2026-09-02 新发现的多 CA 分叉不能修改或重解释上述 v3。当前只进入候选设计审查：若三路独立复核支持，则另建 append-only shadow 版本，以“本机首个精确帖子链接可见时点”为入口，保存当时可见集合及固定延迟检查点的完整 CA 集合、克隆分叉、route/容量/成本和 15/60/240 终态；不选择赢家、不回填、不接 Strategy/Paper/Live。若污染、分母或经济价值无法成立，则保持 v3，不为增加样本创造新实验。

### P1：形成可审计主 Paper 样本

只有现有证据门、canonical margin、安全和真实报价均通过时才产生主 Paper；持续记录 BUY/SELL、滑点、费用、部分退出、stop、trailing、narrative decay、runner 与资金占用。交易少时先归因断点，不为增加数量降低门槛。

### P2：前向学习与 challenger

按来源、人物、信息类型、链、触发路径和策略 cohort 比较 15/60/240 分钟及完整持仓结果。至少跨多日期、含正负样本、扣费后且尾部可接受，才预注册一个最小 challenger；保持基线/探索隔离，不逐笔自我改写。

当前 Portfolio 的产品模型冻结为**三个模拟账户、两种入场逻辑**：

1. `策略 1｜信息 + Token`：新闻、热点、人物、社区与 Token 数据共同决定独立入场；
2. `策略 2｜纯链上基线`：只用 Token 链上/市场数据入场，当前 Solana 以特定金额 Jupiter 最低输出作为成交语义；
3. `策略 3｜同入场·买后叙事增强持有`：精确复制策略 2 激活后的新 BUY（同 Token、时点、金额、数量和成本），只研究买后已观察到的叙事是否值得延长 runner。

策略 3 不是第三个选币器，也不能把现有动态止损实验改名充数。正面叙事不得覆盖安全、流动性、硬止损、移动止盈、最长持有和不可交易终态；所有买卖均须扣除当时可得的滑点、路由/平台费和链费。策略 2/3 只使用策略 3 激活后的 exact paired cohort 比较，旧赢家不回填。

策略 3 的第一阶段已进入生产前向采样：`onchain-paper-narrative-context/v1-forward-only` 只对 context registration 后的新 exact pair 发起一次买后 Token Context 研究。当前研究结果只进入 assessment/audit，不进入主 Event/Decision，也不改变仓位或退出；Seed 后未形成 admission 的中断可用同一 transition 恢复。生产注册点为 Strategy 2 BUY `133`，现有 8 个 Strategy 3 仓位全部作为 `pre_registration_not_backfilled` 排除，等待下一笔自然新 BUY 才形成第一个有效样本。

持续学习采用 append-only、point-in-time、版本化 baseline/challenger：阈值、信息源权重、人物/社区/热点量化和持有规则可以持续研究，但只能在预注册成熟门后发布新版本；不得让在线结果逐笔自改当前基线。

### 当前执行周期：P0-E 多链指定金额执行真实性

当前最高影响断点不是 Token 数量、Agent 数量或 UI，而是 Solana 之外“发现到 Token”无法转换成时点有效、指定金额、可买且可卖、成本完整的执行证据。第一阶段已部署 BSC/Base/Robinhood Chain 的固定区块 Uniswap V3 双向 Quoter 观察层；它只回答 pool math 是否存在，不回答完整交易是否可执行或盈利。

下一步顺序冻结为：

1. 等待第一个 activation cohort `2112` 之后的自然 EVM cohort，验证 attempt/result、错误分类、固定区块和无回填；没有自然样本时保持 0，不手工塞赢家。
2. 为各链补充同区块 gas price、L1 data fee（适用时）、Router 交易模拟、allowance/transfer-tax/blacklist 与指定数量卖出能力；仍先进入 research-only challenger。
3. 只有完整往返成本和失败语义跨日期积累后，才讨论将 BSC/Base/Robinhood 任一链加入 Paper；主 Paper 当前仍仅允许 Solana amount-specific Jupiter 路径。
4. 策略 3 继续与策略 2 exact-paired：买后信息只研究延长持有，不覆盖安全、流动性、硬止损或不可卖状态。当前 runner 继续禁用。
5. UI 仅维持真实、可读和动态；后续视觉深化不抢占执行真实性和 Event↔Token 转化率主线。

### P3：后置事项

- 深化 UI 设计与长期固定公网域名；
- 更广平台登录或 Telegram 自动摄取；
- 通用按证据复杂度动态升级模型；
- Devnet/小额 Mainnet broker、签名、广播、确认和对账。

这些事项保留在累积需求中，但不能抢占 P0/P1。Telegram 自动正文摄取、自动注册/绕 MFA、读取凭据、社交互动自动化仍受平台与安全边界限制。

## 5. 下一可执行步骤

1. 已部署 `kol-token-addressability-lag/v3-immutable-attention`：activation Observation `6499`，registration hash `f90c852666b1cf7d3d29df0b89474d0d346dad432e704c3ca746cf124917b3b4`。Runtime 以不可变 registration JSON 和 exact attention point 为准，严格 attention `<35`，本地可见时间使用 durable snapshot `recorded_at`，裸 EVM CA 保留为显式跨链歧义；主分母保留 no-seed，且固定 `decision_eligible=0 / affects=none`。
2. v1 历史 cohort 原样保留；base v2 标记为 `registered_abandoned_before_first_cohort`；route v1 标记为 `registered_abandoned_before_first_attempt`。route v2 于 `2026-09-02T06:23:40.203809Z` 注册，activation cohort `1`，definition hash `79ca058b7ae38bfccfbf260e19a5a5b315c3538ebb0127d59ff1b91d349d2c42`，compatible base hash 与 live v3 完全一致。
3. route v2 已实现并验证：registration/cohort hash、route-version 去重、canonical Solana 32-byte CA、完整 cohort→milestone→mint→pair→attempt→result lineage、pair/request/response timing、single-hop/multi-hop/unmapped、bounded unresolved refresh，以及后台 Jupiter 三请求共享 epoch 与逐请求释放生产 quote 锁。下一步只等待 v3 自然 cohort、route/confirmation 终态与端到端延迟；足够前向样本前不启动同 pair/surface 成本后 15/60/240 随访，不接 Strategy/Paper/Live。
4. 浏览器运行健康已拆为两个独立事实：8765 Bridge 服务是否可达，以及扩展采集器是否在 `source_stale_minutes.browser` 窗口内留下真实平台心跳。外部 Chrome 关闭后曾短暂保留新鲜心跳，但最终超过窗口并变为 stale，证明内置浏览器不能替代 unpacked Chrome 扩展常驻；要持续采集 X/KOL，仍须保持外部 Chrome 运行。priority request 现会排除已经存在 `local_receive + raw.browser` 精确 Observation 的帖子，避免已捕获页面反复占用轮换槽；继续追踪真正未捕获的精确原帖、confirmation、exact binding、Decision 与 Paper，不得回填注册前 Observation。
5. 首个新鲜 v3 候选输入是 Elon 在 `06:50:38Z` 对 Tunguz 旧帖的 repost，7 个新 Solana Token 同时引用 exact repost URL。扩展 v0.6.6 重载后已证实 actor/original-content lineage 与 repost Snowflake 时钟进入生产；源码随后升至 v0.6.7，把三个自动轮换页面压缩为两个页面以降低浏览器内存。Chrome 关闭时 X/KOL 精确正文采集会在 3 分钟后显示 stale，但 RSS、链上、Agent、Paper、Web 与 SQLite 不受影响。不得把 repost 冒充 Elon 原创或 endorsement。
6. Lead、交易经济性与因果统计三条最高强度独立复核均给出 `REVISE`，并形成一致边界：第一阶段只运行 local-only、append-only 的 provider-post ambiguity/fanout census，不发新网络请求、不挑赢家、不接 Strategy/Paper；若以后另行注册经济版本，每个帖子最多一个预注册候选和一份固定资本，主要研究 `fanout>=5` 是否应 abstain。Phase A 已从 exposure-link `451913` 之后注册，旧 103 个严格 episode 只作设计证据，绝不进入新实验分母。
   首个自然窗口已形成 2 个 episode、2 个 membership 和 9 个到期 checkpoint；两个帖子均先被浏览器捕获，随后才出现注册后的新 Token membership。记录保持 `decision_eligible=0 / affects=none`，证明前向账本运转，不证明经济价值。
7. 首个自然窗口还暴露出 hydration FIFO 吞吐断点：859 个已到期项中，两个 exact high-impact-post Token 前面分别有 436/491 项，等待约14–15分钟仍 `attempts=0`。调度现只把配置内重点账号的 exact social-post Token 提到 hydration 队首，不放宽触发、证据、Agent 冷却或交易门。部署后两者在首轮同时 hydrated 并形成 `high_impact_account_post` trigger；一个经 deferred retry admitted，Luna/low 使用 88,380 tokens 后返回 `no_context`，另一个继续等待全局冷却槽。没有生成 Decision/Paper，证明修复的是及时调查能力而不是强造信号。
8. 最新终态抽查又定位到 `exact browser Observation → deferred Token Context` 的正文交接损失：直接调查已携带本地正文，但延期重试只恢复 URL，且提示词要求二次访问 X，导致不可访问时否定已有本地精确内容。现按不可变 trigger transition 恢复原 `observation_id/observed_text/published_at/observed_at`，并明确本地正文只证明帖子内容，不构成背书、独立确认、社区扩散或 Token 绑定。三项定向测试通过并已部署；下一步等待新的自然 deferred retry，比较来源可达性与 independent-reporting yield，不能把“正文可用”直接升级为 Decision。
9. 最新120次 Token Context 中，99次携带帖子 URL 但仅47个不同 URL，首轮后重复52次，重复 URL 调用约消耗6.126M tokens；其中未核验 metadata 同等级重复43次、约5.220M tokens，是当前比预算更直接的调查覆盖损失。现已部署 source-fair 调度：X/Twitter 同帖 canonical 化，metadata 与 exact-browser 分开，exact 还绑定正文 fingerprint；每个 high-impact lane 先排不同且未调查的 source key，再排已调查的不同 source，最后才排同轮 clone。它不跳过或复制 Token assessment，不改变每轮上限、冷却、证据门或交易；下一步以新自然轮次比较首个 admitted 的 distinct-source 比例、重复 URL 间隔和独立来源 yield。
10. 用户于 2026-09-02 明确补充 `Solana + BSC + Base + Robinhood Chain` 多链需求，因此旧的“发现层仅 Solana+BSC”结论已被部分 supersede。GeckoTerminal 新池与 DexScreener pair/social hydration 范围现扩为四链；高写入量的全局 Profile/Takeover/Ads/Boost 面仍只覆盖正式候选链，以避免大库事件循环饥饿。正式 `candidate.chains` 暂保持 `Solana+BSC`。Base/Robinhood 只保存新池、Token、快照、来源链接和 `research_only` 漏斗，不派发 Agent、不写 Decision/Paper。只有建立各链 amount-specific router quote、协议费、动态 gas/L1 data fee、安全报告与失败语义后，才可另行前向升级为候选链；不得把 Solana 的 Jupiter/固定费用假设复制过去。
11. 新自然窗口确认 source-fair 只能在存在其他帖子时改善排序，不能消除同帖多 Token 的完整重复调查：同一 Solana 帖子被6个 Token分别调查，合计404,124 tokens，全部 `no_context`。当前关键设计候选是把帖子/事件事实与 Token 名称/CA 绑定分开；帖子级不可变事实可在同一证据版本内复用，Token 绑定、独立确认、exact CA、安全、报价和交易资格绝不跨 Token 复制。该方案必须先通过三条高强度独立复核，并以 append-only、available-at、证据升级/纠错版本和负结果有限刷新为边界；在复核完成前不改 Runtime。
12. 样本未成熟时保持基线，不以单笔赢家、单日亏盈或空结果改变 Strategy。
13. source-fact/token-binding 三路最高强度复核已完成，结论一致为 `REVISE`：过去 24 小时双 Agent 槽同时繁忙仅约 1.3%，队列 p95 约 0.001 秒，增加并发不是当前解法。现已部署 `source-fact-single-flight/v1`：同一 canonical URL、证据等级与 exact content revision 只调查一次；每个 Token 仍独立重算 exact CA binding、assessment 与证据角色，不复制安全、报价、Decision、仓位或交易资格。首个自然事实被 4 个 Token 复用，3 个 follower 均为 0 tokens；随后按真实前向数据把 `no_context` 复用窗口调整为从完成时刻起 30 分钟、reused Token 写入正常冷却，并允许被 Runtime 重启中断的只读调查在租约加既有 10 分钟错误退避后追加重试。真实 attempt `11` 已证明永久饥饿解除，result `10` 证明 30 分钟完成时锚点生效。下一步只观察 distinct-source 覆盖、decision-evidence yield 与相同 source revision 的实际 Agent 节省，不通过增加 Agent 数量掩盖绑定和证据问题。
14. 链上探索 Shadow 与主 Paper 继续分账但统一展示：Shadow 是更宽候选集合的反事实研究，主 Paper 是当前策略通过后的模拟组合，二者准入与成交假设不同，直接混账会污染归因。Portfolio 已补充 Shadow 现金曲线、成交/胜负、胜率、平均/中位已平仓 PNL、最大现金回撤、网络费估计与未定价仓位的零回收下界；所有值明确标为 simulated。止损/追踪/止盈应由本地市场数据触发并以实际 amount-specific SELL quote 结算，Agent 不负责数值行情或卖出判断。
15. `onchain-paper-exit-challenger/v1` 已从固定 Shadow 的 exploration BUY trade `99` 之后严格前向注册。它与固定 15/60/240 分钟基线共享后续新入场、但独立记录退出：DexScreener 15 秒标记只产生意图，下一笔特定剩余数量的 Jupiter 最小输出才结算；`no_route` 不假装止损成功，240 分钟仍无路线才 write-off。默认规则冻结为 hard stop `-35%`、trailing `+60%/-28%`、流动性紧急 `$3000`、5 分钟零活跃、`+80/+180/+350/+700%` 分批退出和 240 分钟上限。Portfolio 已显示动态 cash/equity/realized/unrealized/total PNL 曲线；当前尚无注册后的自然成对入场，保持 `$1000` 空账本，不回填旧仓位。下一步只等待自然 paired sample，比对相同入场下固定周期与动态退出的扣费 PNL、route failure、回撤和尾部，不按单笔结果改规则。
16. Token 详情里的普通 X status 已接入现有单页 priority 采集，不再要求它先属于人工 watch account。新精确 Observation 会 append-only 关联所有当时已引用该帖的 Solana/BSC Token 并优先重做 hydration；普通 Context lane 又已修正为精确本地原文优先于未核验 provider metadata。首个修复后自然样本已完成 `exact post → admission → Agent → no_context`，没有制造 Decision 或交易。新的13-Token自然 handoff 又证明只选择1个普通候选会在 hydration 后静默丢失其余样本，因此已增设每轮最多4个的 source-fair exact-browser lane，超过上限者持久重排；不增加Agent并发或放宽任何门。自然验证中 owner admission `9490` 使用 `62,851` tokens，follower admission `9491` 以 `source_fact_reused` 独立形成 `0-token` assessment，超限精确 Token 保持 pending，证明 bounded lane 与同源复用均已进入真实前向流量。下一步统计这些 exact-post 样本的独立来源产出率、Token exact-binding 率、端到端延迟及 Decision/Paper 转化；只有其中一层出现证据支持的损失时才调整该层，不通过增加 Agent、降低门槛或回填赢家追求更多 Paper 成交。
17. 外部 Chrome 继续作为 X 精确采集载体，但内存治理只针对真实异常 renderer：本轮单 renderer 曾升至约 `3.68 GB`，精确终止后采集自动恢复且登录/扩展未丢失。Web health 现以 heartbeat 或最新真实 browser Observation 判断 collector 活性，避免 Bridge 忙时误报 stale。该运维事项服务于信息召回，不改变策略、Agent 数量、证据门或交易门；后续只有再次出现单进程异常增长或采集停滞时才介入，避免把浏览器维护变成主线。
18. 新 Decision `2948` 将下一断点收敛到 canonical identity：两个同名新币几乎并列，只有一个在决策前直接链接 Event 内精确帖子。严格24小时 as-of 诊断共找到5个类似多候选 Decision，但另一个 Event 同时有5个 Token 链接同一帖子，说明 exact source link 只能证明 identity set，不能总能选出唯一 Token。未来 `WAIT` 已改为同时披露低分与 canonical ambiguity；生产评分保持不变。下一步按 `CHATGPT_REVIEW_HANDOFF_EXACT_SOURCE_LINK_CANONICAL_IDENTITY_2026-09-02.md` 完成架构、因果和交易经济性三路独立复核，再决定是否注册一个只读 append-only identity-set Shadow；复核前不以 metadata identity 提升交易资格。
19. Information-first Shadow 的被动采样缺口已通过独立、严格前向的 `information-first-active-outcome-sampler/v1` 处理。版本于 `2026-09-02T14:46:49Z` 注册，activation shadow cohort `104`；只为之后新 cohort 建立15/60/240分钟目标，在目标 `+0/+30/+120/+300s` 主动请求 DexScreener，并于5分钟硬截止记录 observed mark、no pair、限流、HTTP/timeout/protocol error 或 scheduler-missed terminal。它不写通用快照、不调用 Agent、不使用 Jupiter、不接 Strategy/Paper/Live，所有记录固定 `decision_eligible=0 / affects=none`。部署时最大 cohort 仍为104，所以当前目标与结果为空；下一步等待自然新 cohort，检查各 horizon 的覆盖率、错误构成和延迟，不手工制造样本。
20. X 文章《2026年，Meme链上还有机会吗？》已按原文读取。其“娱乐/抽象、冲突/反叛、情绪共鸣、天然流量、社区传播”等叙事观察只进入可检验的研究词表，不直接加分或买入；文章同时含 GMGN/FOMO 推广链接和 KOL 经验，必须与项目方 promotion、独立事实、实际传播加速度、Token fanout/canonical 歧义和扣费结果分离。后续按链比较叙事类别、首次可见时间、跨平台扩散、克隆数、流动性/买卖广度和15/60/240分钟结果，保留所有空结果与亏损样本。
21. `C2C-20260903-MEMETRADER-SYSTEM-RESEARCH-IMPL-001` 已成为当前有序实施主线，完整研究见 `CHATGPT_MEMETRADER_SYSTEM_RESEARCH_2026-09-03.md`，执行合同见 `CHATGPT_CODEX_IMPLEMENTATION_HANDOFF_MEMETRADER_SYSTEM_RESEARCH_2026-09-03.md`。P0-A 已完成代码与定向测试：active outcome 的最多 4 个 DexScreener 请求改为同周期有界并发，每个请求最多 15 秒且绝不越过冻结 deadline；到截止时先写 `terminal_missing`，随后迟到结果只能 append `late_response`，不得覆盖 terminal。当前 r6 为 27 targets / 13 attempts / 13 results / 15 terminals，历史 4 个 `scheduler_missed_deadline` 原样保留。下一阶段按 P0-B/C 实施 immutable launch facts 与 market-surface classifier，均从新 activation 起 `decision_eligible=0 / affects=none`，不改变 Strategy/Paper/Live。
22. P0-B/C 已前向上线：Pump WebSocket receipt clock 与 immutable launch facts 不再被 hydration 覆盖；market-surface v2 只描述具体 pair，并将 bonding curve 与 AMM 分开。PumpSwap canonical 在缺少真实 pair-account IDL/RPC 证明时保持 unknown。P0-D 当前正式版本为 `liquidity-survival-shadow/v3-version-isolated`；v1 partial 与 v2 contaminated 均原样冻结并排除。v3 固定 exact pair、$12k baseline、1/5/15/60m 与 missing/error 终态，只做 Shadow，不影响 Strategy/Paper/Live。当前自然截面已有 384 cohorts、1,085 attempts、1,200 outcomes，调度/索引工程门已经跨过；继续增加同类基础设施不再是主线，下一工程断点转为 P0-E amount-specific execution。
23. Paper 真值边界已经收紧：开放纯链上仓位只有 DexScreener 价格时，只显示受容量限制的 `indicative` 参考值；没有特定剩余数量的有效卖出报价时，账户 `equity/unrealized/total PNL` 保持未知，不再把零/未知流动性的表面涨幅算成可实现 PNL。Portfolio 的纯链上说明也改为真实准入语义：当前是冻结的 on-chain momentum cohort + 时点有效 Jupiter 指定金额买入报价；流动性、成交、买卖结构与安全字段尚未全部成为硬门。两项定向测试通过。
24. Robinhood Chain 已作为第四条独立研究链纳入，而不是 BSC/Base 的别名。官方事实为 chain id `4663`、Arbitrum L2、ETH gas；GeckoTerminal network id=`robinhood` 已验证，0x 已支持该链的 Swap/Cross-chain route。本机最近 24 小时已采集约 9,942 个 Robinhood Token，说明它不是空规划。但 Robinhood 官方 `/rhj/assets` 当前 194 个 Stock Token 合约中已有 103 个出现在本机 Robinhood Token 总表，证明必须先做 Meme 与 Stock Token/RWA 的官方地址级分类。当前继续保持 `research_only`：只收新池/Token/快照/来源，不派 Agent、不写 Decision/Paper；先建立 append-only `stock_token/rwa_excluded` 分类，再做 0x amount-specific Shadow、动态 L2/L1 费用与安全成熟门。
25. P0-E 第一阶段已实现 `event-route-execution-challenger/v1-entry-preflight`。它只接收注册后新的 route-backed WAIT：固定最大仓位 probe 继续只证明容量，最终 policy size 再冻结为 USDC raw amount，随后新发 exact-size BUY，并以 BUY minimum token output 做即时 SELL preflight。每个 attempt 保存两腿最低输出、时钟、route-only cost、费用完整性及失败终态；当前一律 `no_fill_research_only / affects=none`，不写旧 `paper_account/positions/trades`。Quote-only 网络费字段或同时点 SOL/USD 转换不完整时明确 `cost_unknown`，不会叠加旧 4%/125bps 假装精确成本。下一阶段只在出现自然前向 attempt 后补独立 remaining-raw position/SELL ledger；成熟前保持主 Paper WAIT 与 Live 锁定。
26. 策略 3 已从 exploration BUY trade `123` 后严格激活；首个核验截面为 4 个新 BUY / 4 个 exact pair，浏览器 QA 截面已自然增长为 7 / 7，始终为 0 mismatch、0 backfill。Token、时间、金额、raw 数量、入口网络费与源 quote result 全部一致。叙事 runner 仍为 0，状态明确为 `not_mature_not_enabled`，因此当前只证明公平同入场账本运转，不证明买后叙事能改善收益。退出报价又发现一项真实语义错误：Jupiter Swap V2 官方用 HTTP 400 `Failed to get quotes` 表示无法找到报价，旧客户端误记为 `JupiterQuoteError`。修复后首个自然结果 `410` 已变为 `no_route`；历史错误行不改写，无法成交仍不生成 SELL 或 PNL。
27. 策略 3 买后调查 v1 已形成 11 个不可变 seed（7 coverage gap / 4 triggered），并证明首次 60 秒无刷新快照就永久终结会制造系统性覆盖损失。v2 从策略 2 BUY `155` 后重新注册：优先使用买后刷新快照，否则使用入场前已完整入库且与 exact cohort 一致的 trigger snapshot 启动调查；调查时钟仍晚于入场。延期重试只服务仍开放的 exact-paired 仓位，并排在精确原帖/新鲜高热 Event 后、批量 metadata 前。旧 v1 不回填，runner、Decision/Paper/Live 均不改变。同期 active outcome v1 的真实已终态缺失率为 9/153（5.88%）；v2 将最后重试从硬截止 `+300s` 提前至 `+240s`，保持 300 秒右闭 deadline。下一步只等待 v2 的自然 paired entry、snapshot basis、admission/assessment 与策略 2/3 同入场扣费退出结果，不用增加 Agent 或降低门槛制造样本。
28. 启动者历史研究已按 P1-B 的最小前向切片上线。`creator-launch-risk-shadow/v1-local-history-lower-bound` 只为 activation launch fact `10533` 之后的新 Solana Pump create 建 cohort；每次冻结当时已入库的同地址历史发币数、24 小时发币数、距上次发币时间、既有 240 分钟链上结果与 60 分钟流动性存活结果。它明确是 PumpPortal provider observation，不是 RPC 验证，不做多地址实体聚类，历史为本机记录下界。首个自然截面 68 个合格新 create 全部入组，其中 46 个地址已有本机先前发币、27 个先前发币数不少于 10；这些只是待检验暴露，绝不自动解释为恶意、风险分或交易拒绝。Token 详情已折叠显示该证据；Decision/Paper/Live 完全不变。下一步等待结果成熟后按预先冻结的频率桶比较，而不是立即按创建者次数改交易。
29. Strategy 3 延期调查的共享重试槽已修复真实假饥饿：`reused/source_fact_reused` 现在终止 exact intent，仍在有效期内的 `token_cooldown_active` 按 Token-wide 语义阻止同一 Token 的全部延期 intent 再占槽；全局/错误冷却继续按 exact lineage，优先分数、4 分钟周期、最多 2 个 Agent、预算和交易门均未改变。部署后首轮自然 active retry 已成功 admission 一条 post-entry intent 并生成 `no_context` assessment，证明调度恢复但不证明叙事 alpha。当前 v2 的 3 个开放 seed 仍待自然处理；在 assessment 与 paired executable exits 成熟前，策略 3 继续 `decision_eligible=0 / affects=none`，runner 不启用。
30. 对上一条自然结果完成版本归属复核后，确认其属于旧 context v1，不能代表 current v2。已将 post-entry active retry 严格限定为当前 context version + exact seed/transition/source BUY/open paired position；旧版本保留审计但不再抢槽。退出监控从 `opened_at` 固定队首改为未标记优先、随后按最旧 mark 公平轮换；退出报价也改为未尝试 pending mark 优先、随后按最旧尝试轮换，修复同一失败仓 16 次重试而多个待退出仓 0 次的垄断。部署后 cohorts `2130/2137/2138/2139` 已全部得到首个 mark，原 0-attempt 的 `2110/2112/2113/2117` 已获得首个真实卖出尝试，current-v2 seed `12` 已产生 assessment `1044/no_context`。这恢复了当前版本的价格/叙事/执行观察分母，但没有启用 runner，也没有证明 alpha；下一步继续收集另外两个 v2 assessment、Strategy3 amount-specific exits 和费用完整性，再冻结可检验的叙事处理规则。
31. 当前执行范围按用户最新决定收敛为 Solana-only；BSC/Base/Robinhood 的既有只读研究账本保留但暂停进入新发现、Agent、Decision、Paper 与 PNL。三种 Paper 策略已从 `fair-comparison/2026-09-03-20usdc-v2` 公平重启，统一采用 `$20` 入场、BUY/SELL 各 `4%` 不利滑点、每次实际成交固定 `$0.40`。链上策略使用新的不可变 v2/v4 版本链，旧版本不回写；主信息策略的新成交使用相同成本，但仍需补独立 machine-readable policy version。近期主线是收集该成本版本的 Solana 前向样本与可执行退出，不扩张多链。

## 6. 完成判定

本长期目标不能因网站可用、代码测试通过或出现少量 Paper 成交而关闭。至少需要：

- 关键采集与证据链在真实前向数据中稳定运行；
- 能解释机会召回、误报和漏检，而非只统计成功样本；
- 主 Paper 获得跨日期、包含亏损、扣费后的足够样本；
- 收益、回撤、尾部、集中度和执行可行性达到预注册成熟门；
- challenger 在严格前向样本中相对基线有可复核改善；
- 仍保持无未来数据、无回填、Live 锁和完整审计。

在这些条件满足前，状态保持 `ACTIVE / CONTINUOUS`。
