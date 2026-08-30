# 累积需求验收 — 2026-08-30

本文件把本轮聊天、附件和当前工作区事实统一归档。它不是运行状态的永久保证；发生冲突时仍以 `AGENTS.md`、当前代码、被 Git 忽略的 `config.json`、当前 SQLite 和实时 API 为准。本文不保存任何密码、私钥、Cookie、Session、验证码、Bridge Token 或公开入口口令。

## 1. 验收时真实状态

- 项目位于 `E:\memeTrader`，版本 `0.6.3`，权威前向数据库为当前 `config.json` 指向的 r6 SQLite。
- `/api/health` 实测 `ok=true`，模式为 `paper`，Live 为 `enabled=false / locked=true / available=false`，SQLite `quick_check=ok` 且使用 WAL。
- Windows 计划任务 `memeTrader Paper Bot` 正在运行，`IgnoreNew` 防止重复实例；浏览器桥端口可达。
- 验收快照约有 1,184 observations、758 events、19,511 tokens、340 decisions、0 trades、0 open positions；Paper 现金/权益均为 1,000 美元。数字会继续变化，不能用于表现结论。
- 信息与 Token 两条 SQLite 活动通道均为真实 `active`；页面动画来自持久化时间窗，不是假心跳。
- `autonomous_search.enabled=true`；旧的语义平局 `agent.enabled=false` 不代表自主搜索关闭。Agent API 实测启用，使用本机已登录 Codex 会话，不使用 API Key，并发上限为 2。
- 本机 X 与 Telegram Web 登录页已通过只读页面结构核验为已登录；没有读取私信或聊天正文。memeTrader Sources 同时显示 X `not_observed`，说明登录尚未形成浏览器桥采集心跳。Telegram 在产品中仍为 `manual_directory_only`。

## 2. 已实现并有当前代码或运行证据

### 核心采集与决策

- RSS、Google News、Mastodon、PumpPortal、GeckoTerminal、DexScreener 及安全服务组成前向采集链；SQLite 保存事件、Token、快照、决策和 Paper 数据。
- `feature / confirmation / identity / promotion`、独立来源、首次本机观察时间、future/stale 拒绝和 r5/r6 审计规则已经实现。
- Event→Token 与 Token→Event 双向关联、候选排名、canonical margin、安全门、`WAIT / REJECT / CANDIDATE` 和 Paper 仓位/退出由现有 Runtime/Strategy 决定，Web 不复制策略。
- 每个新观察到的 Solana Token 进入持久化 Dex 详情补全队列；项目附带链接只作 identity/promotion 调查种子。
- Token Context 不再只有动量入口：本机浏览器桥实际接收、精确归因且与 Token 种子 URL 对应的高影响力账号原帖，或新鲜高热事件与 Token 的高匹配 WAIT/CANDIDATE 持久化关系，也可在低动量时触发调查。项目方元数据中的帖子 URL 只能作调查种子，不能单独触发；名称、头像、主页、蓝勾和项目自报也不能绕过门槛。未来时间与 REJECT 关系会被排除，Agent 结果仍须通过两个独立可访问域名的本地验证。

### Web 与可视化

- 深色、响应式、中英文控制台已经实现 Overview、Events、Tokens、Decisions、Paper、Wallet、Agents、Sources、Audit、Settings。
- 页面采用 10–60 秒低成本 polling；页面恢复可见时立即刷新，失败显示 STALE。
- Overview 展示运行、Paper/Live 锁、SQLite、Bridge、计划任务、现金/权益/exposure、持仓和计数；实时脉冲只使用 SQLite 的 60 秒/5 分钟真实活动。
- 事件详情展示平台、发布者、账号类型、影响力已知/未知状态、角色、新鲜度、资格、全部来源链接、排序依据和时间线。
- Token 页面展示 CA、chain、创建/首次观察、流动性、5m volume、买卖、momentum、Dex 附带链接、详情补全和 Agent 调查分栏。
- WAIT 使用中性语义且 Paper 仓位为 0；Paper PNL 明确标为模拟。
- Paper 账户曲线、成本与执行尝试现为前向审计数据：账户点 append-only；零成交显示 cash-only/not-observed；入场和退出均使用有年龄上限的重新报价；新成交记录报价/执行价、滑点、双边手续费和已知 Token 税。路由费、链费、priority fee、gas、MEV 与部分成交尚无可验证 Broker，不声称已覆盖。
- Settings 只开放安全白名单；不返回 secret，网页没有 Live 开关。公开入口的钱包操作被禁止，本机 Wallet 仅限隔离 Devnet。

### Agent 与成本

- 三类真实 Agent 任务为 Trend Scout、Source Discovery、Token Context；六个界面角色只是职责视图，共享最多两个进程槽位。
- 基础复杂度路由已实现：热点扫描/搜源为 Spark/low→Luna/low；Token 语境为 Luna/low→Terra/medium→Sol/medium。
- 使用量按任务、模型、推理强度和 input/cached/output/reasoning/total token 记账；Web 显示调用、预算、下一运行、最后结果和 fallback。
- 调用次数、Token 双预算、全局/单 Token 冷却、quiet/surge、错误退避继续有效；`--force` 不能绕过预算。

### 来源、账号和长期学习

- 公开账号目录覆盖 X、Truth、YouTube、Instagram、TikTok、Threads、Bluesky、Reddit 和 Telegram 目录；Trump、Musk、CZ 的 critical 只保留观察轮换，不提高证据权重。
- GitHub 开源采集、Telegram 频道/机器人、Dex model1/model3 方案均已有审查文档；没有照搬多池混合、伪 Token 年龄或推广榜单逻辑。
- 来源、账号、实体、平台、主题通道的追加式学习账本、15/60/240 分钟 shadow follow-up 和前向成熟门已实现；学习只允许小幅改变观察轮换，绝不进入证据、候选、风控、仓位、退出或 Live。

## 3. 部分实现或依赖当前设备状态

- **X/其他社交采集**：平台已登录或账号已在清单中，不等于正在采集。Runtime 已能把精确配置账号页的 Bridge heartbeat、原帖 Observation 与 event ID 写入独立前向暴露账本；X 首页、搜索/登录页、同名账号、Telegram 和历史数据均排除。当前 r6 是否已有真实账号页暴露必须以重启后的数据库/API 实测为准，不能因代码已实现就宣称采集已跑通。
- **Agent 难度自适应**：任务级模型/推理分层和失败回退已实现；当前强模型升级主要处理模型/额度不可用。基于语义冲突、低质量输出或证据复杂度自动升级，同时避免对有效空结果浪费额度，尚未形成完整质量策略。
- **公开 URL**：受口令保护的 Cloudflare Quick Tunnel 架构已实现并在本机配置；Quick Tunnel 地址是临时的，不是稳定域名。
- **Devnet 真链验证**：钱包连接、集群核验、余额和受限人工操作已实现；faucet 未取得测试 SOL，因此没有成功链上 signature。
- **长期学习**：机制已实现但样本不成熟。2026-08-31 当前运行证据为 watch-account exposure 0、Trend lane 1 个完成 run/3 个 lane exposure/0 个接受事件、5 个 shadow cohort（1 complete）、2 笔 Paper 成交形成 1 个闭仓结果；不能声称已经学出最优平台、人物或信息类型。
- **Token Context 学习闭环**：五轨 assessment 已接入独立的 15/60/240 分钟前向描述性结果账本。它包含 `no_context`、Agent 错误、未核验候选和 missing，历史数据不回填；只有浏览器精确原帖可产生人物实体标签。当前仍须等待新版本真实 cohort 和固定时点结果，且该账本不改变调度或交易。

## 4. 未实现

- 可审查的 Mainnet Broker、签名边界、小额真实成交和实盘自动策略没有实现。
- 固定自有域名/长期 Cloudflare Tunnel 没有配置；当前只有临时受保护入口。
- 社交桥的“页面心跳 → 账号暴露 → 精确原帖命中 → 事件归因 → 60m 随访 → Paper 结果”已具备同源持久化与 Web 分阶段展示；真实运行仍需在扩展打开精确配置账号页后产生第一批样本，后半段必须等待同事件的未来观察，不能回填。
- 学习可视化已覆盖 Token Context 冻结标签、observed/missing、正/非正结果和成熟状态；账号/主题策略仍可继续补充更完整的统计不确定性与 baseline 对照，但不能用尚无真实样本的估计填充界面。
- 按结果质量动态提升模型/推理强度的通用路由尚未实现；任何未来实现都必须把“没有热点”视为可能的正确答案，不能为追求非空结果反复升级。

## 5. 已明确跳过、禁止或不应照做

- 不做 Mainnet Live 网页开关，不把用户粘贴过的私钥写入项目，不把 Paper PNL 当真实利润。
- 不接受“只接私钥即可直接实盘”为当前完成项；Mainnet Broker、交易模拟/签名/广播/确认、失败/重试、防重复、路由成本、余额回执对账、紧急停机与一次性小额真链验收仍需单独发布审查。
- 不自动读取、导出或保存密码、Cookie、Session、验证码、私信和历史聊天；不自动注册账号、绕过 CAPTCHA/MFA/短信、批量关注、点赞、发帖或私信。登录失败的平台直接跳过，不阻塞其他来源。
- 用户最终要求“不要 API 级别、不要无意义极高频”。因此不引入 X/Telegram 私有 API、Telethon/TDLib 会话或大量常驻 Agent；并发上限保持 2，频率采用适度加快和退避。
- Telegram 自动抓取、批量索引、长期保存正文、自动转发或把消息直接送入 Agent 保持关闭。新闻/搜索/新币机器人只可人工发现；机器人结果必须回到官网原文、原始社交帖、CA 和链上数据。
- 不把名人名字、头像、粉丝数、蓝勾、Boost/Ads、同名 Token、社区喊单或 Telegram 新币机器人直接解释为背书、权威确认或买入信号。
- 不复制 `E:\P5_completeSystem` model1/model3 的错误语义；只借鉴 Dex 发现入口和链接溯源思路。
- 不生成假事件、假 Token、假心跳、假成交或演示利润来让界面看起来活跃。

## 6. 需要用户人工完成

- 在用于常驻采集的 Chrome/Edge 中加载 `E:\memeTrader\browser-extension`，在本机扩展选项中配置 Bridge Token，并保持允许观察的公开 X/其他平台页面打开。当前在 Codex 侧栏登录并不能自动给该扩展提供心跳。
- CAPTCHA、MFA、短信、手机号、条款确认和任何平台风险检查必须由用户本人处理；无需把密码或验证码发给 Agent。
- 若要完成 Devnet 真链闭环，需要在本机 Wallet 页给隔离测试钱包领取少量 Devnet SOL；只有出现可在公开浏览器核验的 signature 才能标记成功。
- Telegram 官方频道和经核验机器人可以由用户人工加入，但不应授予管理员、连接钱包或提交内部关键词/敏感 CA。memeTrader 当前不会自动读取这些聊天。

## 7. Telegram 机器人客观结论

- 确实存在成熟新闻频道：CoinDesk、Cointelegraph、The Block、Decrypt、Bloomberg、Wu Blockchain 等；它们适合发现，最终证据应保存媒体原文和其引用的一手来源。
- Tree News、BWEnews、WatcherGuru 等速度快，但多为聚合标题；没有原始链接时只能是 discovery-only。BWEnews 若提供公开 RSS/机器 feed，应优先评估该外部 feed，而不是抓 Telegram。
- Junction Bot 确实支持多源、去重/过滤和定时 AI Digest，但其免费模式使用第三方默认模型，私有源还要求连接个人 Telegram 账号；它不会使用本机 Codex agentic 额度，也会把来源、消息和 prompt 交给第三方服务。
- The Feed Reader Bot 确实支持 RSS、YouTube、X 等投递，但刷新频率约为 10–30 分钟且功能与本机采集重复；它适合个人阅读，不是 memeTrader 的第一手数据层。
- Liveuamap 官网明确链接 `@liveuamap`，可作为地缘冲突 discovery-only；其事件仍来自多种外部来源，必须回到原始链接。
- `@reutersnews_bot` 页面自称非官方；本轮仍未从 BNO 官网核验 `@BNONews`，`@OSINTdefender` 的精确 handle/所有权也不稳定。这些条目不能按“高权威官方源”接入。
- Birdeye 官方文档列出 `@birdeye_alert_bot`，并列出合作方 Telegram New Pairs bot。前者只投递用户配置的提醒，后者仍是第三方合作来源；二者都不能证明 Token 安全或叙事真实。
- `@PumpFunNewPools`、`@SolanaNewListing`、各种 caller/sniper/trending/volumize 机器人与当前链上采集重复且利益冲突明显，默认不加入、不连接钱包、不进入决策链。
- 对“新币提醒”，PumpPortal 流、DexScreener 和 GeckoTerminal 比 Telegram 转发更直接、可去重、可保存首次观察时间和 CA，因此继续作为主路径；Telegram 只可能提供冗余发现或社区传播线索。

## 8. 直接来源失败时的固定降级顺序

1. 同一发布者的官网、RSS/Atom、GitHub、状态页、监管公告和可核验链上交易。
2. 已登录浏览器桥观察 X 等已打开的公开页面；失败必须显示 `not_observed/degraded`，不能当成“没有事件”。
3. 受预算的本机 Codex Trend Scout 搜索原始页面和相互独立的公开来源；它使用本机 agentic 额度。
4. Junction Bot、The Feed Reader Bot、Liveuamap Telegram 等仅作为用户侧人工提醒与候选发现。用户点击原帖后，系统仍回到第 1–3 层核验。
5. 非官方 Reuters、未从官网核验的 BNO/OSINT handle、匿名频道和新币 caller 只能进入人工待核验清单，不能自动形成 Observation、attention 或候选分数。

把 RSS/X 先转发到 Telegram、再让 memeTrader 自动读取 Telegram，并没有消除采集限制，只会增加第三方、延迟和来源归属丢失。因此它只作为人工可见的故障备用，不作为新的机器主链。

## 9. 原始表述的歧义与可执行需求

| 原始想法 | 问题 | 提炼后的可执行目标 |
|---|---|---|
| “全面关注所有平台、名人和热点” | 覆盖越广，重复、噪声、限频和上下文成本越高，也无法证明价值 | 保留高信噪比策展基线和受控探索槽位；按前向 exposure、60m shadow 和成熟 Paper 结果学习观察优先级，不追求穷尽 |
| “Agent 数目可以多一些” | 逻辑角色数与同时运行的进程数被混为一谈 | 允许增加职责和队列，但物理并发最多 2；任务复杂度决定模型和推理强度，本地确定性工作不调用 Agent |
| “确保 Agent 一定完成” | 搜索可能因外部网页、额度或真实空结果失败，不能保证每次产生非空答案 | 用任务级路由、结构化输出、本地质量门、可用性回退、预算和失败状态保证过程有效；有效空结果保留为空，不能为完成感伪造结论 |
| “频率高一些”与后来“不要这么高频” | 固定极高频会重复搜索、烧额度并触发限流 | 使用适度加快的基线、事件 surge、连续空结果 quiet、fallback/high-token 下限和每日双预算；Web 刷新不触发采集 |
| “所有事件来源” | 无法证明已经穷尽互联网，且重复转载不等于独立来源 | 展示本机在决策时已观察并保存的全部来源；按实体去重，并明确还有未知外部来源的可能 |
| “按权威和热度排名” | 权威、传播量与决策资格是不同维度，合成单分会误导 | 分开显示 Authority、Reach/Heat、Freshness、Independence、Decision eligibility，并给出排序理由 |
| “名人效应可以直接调查/确认” | 调查、确认和背书被混在一起，容易被同名/头像或项目自填链接碰瓷 | 浏览器桥本机实收且精确归因的原帖，或高匹配事件关系可提前触发调查；只有新鲜、可访问、独立来源可进入 confirmation，名人候选永不自动成为背书 |
| “每个新币都让 Agent 查询” | 新币量巨大，逐币 Agent 成本高且会被垃圾币耗尽 | 每个 Solana Token 都做低成本确定性详情补全；只有动量、本机实收精确高影响力原帖或新鲜高热事件关系触发 Agent 深查 |
| “登录账号就能采集” | 登录会话、页面渲染、扩展连接和 bridge heartbeat 缺一不可 | 登录与采集分别验收；Sources 必须显示每个平台 `not_observed/active/stale` 和最后心跳 |
| “给你所有权限” | 泛化授权不能替代明确目标，也不能取消 secret、平台和交易边界 | 允许完成当前范围内的普通只读/可逆操作；发帖、私信、加群、注册、转账和降低安全锁只在具体必要且明确授权时执行 |
| “私钥接口与真实交易” | 用户粘贴的私钥已暴露，且公开 Web、Mainnet 自动策略和测试钱包被混在一起 | 只在 loopback Devnet Wallet 本机录入一次性测试密钥，DPAPI 保存且不回显；Mainnet 需独立设计审查和新授权，当前网页永远不能开启 |
| “公开 URL” | 公开端口、临时隧道和稳定域名是不同交付物 | 当前使用 loopback 后端 + 鉴权 Quick Tunnel；若要固定 URL，另配用户自有 Cloudflare Tunnel/Access，仍不暴露 origin |
| “动态实时界面” | 纯动画可能制造系统正在运行的错觉 | 所有脉冲和状态来自 SQLite 最近写入、bridge/task/DB health；无数据时显示 waiting/degraded/stale |
| “Telegram 聚合后交给 AI” | 第三方服务会接触来源、消息和 prompt，且不使用本机 Codex 额度 | Telegram 工具只做人工备用；机器分析回到允许读取的官网/RSS/X/链上原文，再由本机 Codex Agent 处理 |
| “长期学习哪些来源更值得关注” | 用少量结果直接优化交易会产生选择偏差和自我强化 | 先冻结 exposure 和 shadow/Paper 标签，只在样本成熟后小幅调整观察轮换，保留探索；永不让学习直接改证据权重或仓位 |

## 10. 剩余推进优先级

1. 完成当前低动量直接调查入口的发布门禁、单实例重启和 Web 验收。
2. 让浏览器扩展真正连接一个已登录 X 公开页面，产生第一条真实 platform heartbeat 和 watch-account exposure；这是人物/平台学习链当前最前端的断点。
3. 继续 Paper 前向运行，收集 WAIT/CANDIDATE 的 15/60/240 分钟随访及真实闭仓样本；样本未成熟前不调学习倍率。
4. 等待新的 Token Context cohort 形成 15/60/240 分钟真实结果，审查 missing 比例、各 assessment 状态覆盖和是否存在选择偏差；不得在成熟前启用任何优化。
5. 在实际失败样本出现后，再实现质量驱动的 Agent 升级策略；避免为正确空结果无意义地反复调用强模型。
6. Devnet 有可用测试 SOL 时完成最小人工链上签名验证；Mainnet Live 继续锁定。
7. OKX Meme Pump 仅列为待明确授权的可选研究源：核心详情/开发者/bundle/同车钱包接口需要官方签名凭据并属于 Premium，当前不得逆向抓取页面。若未来接入，social 仍是 `provider_metadata` 身份线索，聪明钱标签只进入前向 shadow 研究，不进入确定性交易。
