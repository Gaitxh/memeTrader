# memeTrader 0.6.3：个人电脑上的自主信息源 Meme 机器人

后续开发者和 Agent 请先阅读 [docs/PROJECT_CONTEXT/START_HERE.md](docs/PROJECT_CONTEXT/START_HERE.md)。这里保存无敏感信息的产品需求、架构、安全边界、当前状态与运行手册，避免关键上下文只存在于聊天窗口。本轮对整段聊天需求的逐项验收见 [docs/PROJECT_CONTEXT/REQUIREMENTS_ACCEPTANCE_2026-08-30.md](docs/PROJECT_CONTEXT/REQUIREMENTS_ACCEPTANCE_2026-08-30.md)。

`memeTrader` 常驻运行在普通 Windows 电脑上，目标不是全网毫秒级抢跑，而是以现实可行的**几十秒到几分钟**速度完成：

```text
国际社交/新闻/社区出现新事件          Pump/新池先出现 Token
             ↓                              ↓
        事件 → 找币                    Token → 反查事件
             └────────── 双向汇合 ──────────┘
                              ↓
              主叙事币识别 + 链上动量 + 安全门槛
                              ↓
                 Shadow / Paper 自主买入与仓位
                              ↓
          持续报价 → 止损 / 分批止盈 / 移动止盈 / 到期退出
```

项目刻意保持简单：**一个 Python 进程、一个 SQLite 数据库、一个 JSON 配置、一个可选浏览器扩展**。默认不调用付费 API；会启用有严格频率和额度上限的自主搜索 Agent，但交易语义平局 Agent 默认关闭，系统不接触真实资金。

## 关键规则

- 生产运行只使用本机从现在开始记录的 `observed_at`。
- 网页声称的 `published_at` 不能倒推为“机器人当时已经看到”。
- 首次轮询或首次打开页面时发现的旧内容会保留为 `identity` 资料，但注意力记为 0，不能触发买入。
- PNUT、TRUMP、MOODENG、LUCE、Broccoli、TST 等历史案例只测试匹配、主盘选择、等待和未来信息隔离；不会加载为生产别名、阈值或赢家先验。
- 只有 Token/价格拉升、还没有独立新闻、社交或官方触发时，机器人只观察，不买入。
- 常驻策略只支持 Shadow/Paper；另有与策略隔离的 Solana Devnet 真链测试页。Mainnet Live 在代码和网页层永久锁定，Devnet 私钥存在也不会解锁 Mainnet 或自动交易。

## 免费信息源

### 快车道

1. **登录态浏览器扩展**：被动读取你已打开页面中新渲染的公开帖子，支持 X、Truth Social、Bluesky、Reddit、Threads、Instagram、TikTok 和 YouTube。Telegram 只保留人工目录链接，不自动读取、入库或送入 Agent。
2. **PumpPortal 免费 WebSocket**：只订阅新 Token 和迁移事件，不使用付费交易流。
3. **GeckoTerminal 新池**：分钟级发现 Solana、BSC 新池。
4. **DexScreener 展示面发现**：每 90 秒读取官方 Token Profile、Community Takeover、Ads、Latest Boost 与 Top Boost 页面，保存 CA、发现面和项目附带链接；它补充项目方主动展示的 Token，不等于全量新币或新池流。

### 候选确认

- DexScreener：关键词找币、按 CA 报价、流动性、成交和买卖方向；每个新观察到的 Solana Token 进入持久化详情补全队列，并通过官方最多 30 地址批量端点补全 pair info。项目网站、社交主页、帖子、搜索页、Telegram 人工入口和 Dex 页面按类型保存。Profile/Takeover 只作 `identity`，Ads/Boost 只作 `promotion`，均不是已验证新闻、独立确认或名人背书。
- GoPlus + Honeypot.is：EVM/BSC 候选的合约权限、可卖性、税率和 honeypot 交叉检查。默认至少要求一个 EVM 安全报告；显式要求交易模拟时 Honeypot.is 仍是硬门。
- GoPlus + RugCheck：Solana 候选的权限和风险交叉检查，默认至少要求一个报告可用。
- CoinDesk、Cointelegraph、BBC、Google News 专题 RSS 与 Mastodon 公共时间线：补足国际事件证据。
- 普通 Token→新闻名称反查仍要求名称足够独特且已有真实流动性/成交动量；但本机浏览器桥已经实际接收并精确归因到已配置高影响力账号的同一原帖，或已与新鲜高热事件形成高匹配持久化关系的 Token，可在动量形成前优先进入 Agent 调查。Dex 详情补全后会立即检查前一种精确原帖关系，并且每轮最多调查一个最高优先级候选；调用仍受原有全局/单 Token 冷却、每日次数和 Token 预算限制。Dex/项目方填写的帖子 URL 只能作为调查种子，不能单独绕过门槛；名称、头像、主页链接或项目自报同样不能。调查后仍要求独立来源确认，避免把 `Gang`、`Bees` 之类通用名称连接到无关新闻。

Bluesky 公共搜索接口在部分网络会返回 403。本机配置遇到这种情况时应关闭 API 轮询，继续通过已登录浏览器页面采集，不让常驻进程反复报错。

浏览器扩展不读取 Cookie、密码、私信或浏览器历史，不自动滚动、点赞、发帖或登录。它只能看到实际打开并加载的公开页面。因此实际使用时，建议常驻少量高价值页面：名人/项目官方账号、X Lists、Truth Social 账号页、Reddit/Bluesky 重点社区。Telegram 链接只能由用户按需人工打开。

项目同时维护一份可审查、可版本控制的 [82 条公开社交信息源目录](docs/SOCIAL_SOURCE_CATALOG.json)，覆盖 X、Truth Social、YouTube、Instagram、TikTok、Threads、Bluesky、Telegram 和 Reddit；分类、优先级与跨平台去重原则见 [目录说明](docs/SOCIAL_SOURCE_CATALOG_CN.md)。这只是候选种子，不是每轮扫描全部账号，也不使账号内容自动具备决策资格。Trump、Elon Musk、CZ 等少量高影响实体使用 `critical` 观察轮换标签；最多保留 4 个 critical 账号槽位，且该标签不提高权威、证据角色、热度或决策资格。实际启用的当前观察清单由用户导入/选择后保存在 Git 忽略的 `data/web_console/console_settings.json`，可以与目录版本不同。

## Windows 安装

```powershell
Set-Location E:\memeTrader
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
```

安装脚本会建立 `.venv`、安装项目和测试依赖，并在缺少 `config.json` 时生成一个带随机本地桥令牌的配置。

运行测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_tests.ps1
```

检查本机配置和免费端点：

```powershell
.\.venv\Scripts\python.exe -m memetrader doctor --config config.json --online
```

运行一次采集：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_once.ps1
```

安装为当前 Windows 用户登录后启动的单一计划任务，并立即启动常驻 Paper：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_scheduled_task.ps1
```

兼容入口 `install_startup.ps1` 会调用同一个计划任务安装器。`run_paper.ps1` 以前台附着方式监督 Python；子进程异常退出后会等待 5 秒重启。计划任务使用 `IgnoreNew`，程序内部仍有文件锁，因此不会同时运行两个交易实例。运行日志位于 `data\logs`。

仅手工前台启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_paper.ps1
```

移除计划任务并停止机器人：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\remove_scheduled_task.ps1
```

兼容入口 `remove_startup.ps1` 会调用同一个移除脚本。

查看事件、决策、仓位和成交：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\status.ps1
```

## 本机 Web 控制台

Web 控制台直接读取当前 `config.json` 指向的 SQLite，不复制策略、不生成演示成交。它提供 Overview、实时事件、Token 发现、候选/决策、Paper Portfolio、Agent Operations、Sources、Audit、安全 Settings 和 Wallet 十个工作区。

Overview 与 Paper Portfolio 展示追加式账户时间曲线、现金/持仓市值/权益/当日 exposure、报价缺失区段、逐笔报价与模拟执行价、滑点、双边手续费、已知 Token 税和模拟执行失败原因。零成交时显示真实的平坦现金状态，不生成假仓位或假成交。执行与未来 Live 的严格边界见 [Paper 前向执行与未来 Live 验收](docs/PAPER_FORWARD_EXECUTION_CN.md)。

顶部可在“中文 / English”之间即时切换；选择只保存在当前浏览器本地，刷新后仍会保留。事件标题、Token 名称和来源原文不会被自动翻译。

十个工作区都会在页面可见且没有未保存表单时自动刷新当前页；Overview 约 10 秒、事件约 12 秒、Token/决策/组合/Wallet 约 15 秒、Agent/Sources 约 20 秒、Audit 约 30 秒、Settings 约 60 秒。当前采用低成本轮询，不需要 Redis、消息队列或额外 WebSocket 服务；切回浏览器标签时会立即取一次新快照，打开的事件/Token 详情也随当前页一起更新。

Overview 顶部的动态采集脉冲不是装饰性计时器。它从 SQLite 已持久化时间戳分别计算“新闻/社交/Agent 信息”和“新 Token/池及快照”两条通道的最近 60 秒数量、5 分钟写入速率、最近写入时间与 active/waiting/stale 状态。只有近期确有写入时才播放脉冲动画；没有新数据会如实显示等待或陈旧，不会伪造“实时运行”。

Token 页另显示详情补全队列的 `pending / hydrated / no_pair / error`、尝试次数、真实 pair 覆盖率和社交链接命中数。Token Context 采用三类调查入口：链上动量、本机浏览器桥已实际接收并精确归因的高影响力账号原帖，以及新鲜高热事件与 Token 的高匹配持久化关系。项目附带的同一帖子链接只是关联种子，查询参数与片段会在送入 Agent 前移除。调查拆成项目附带社交声明、社区扩散、公众人物关联候选、独立报道和触发时链上快照；社区“热度”不合成主观总分，公众人物候选绝不自动解释为支持或背书。只有通过原有时间、相关性、可访问性和至少两个独立域名检查的报道，才可能进入 confirmation 链；其他分栏全部只作审计语境。

每次新的 Token Context 调查还会在当时存在本地正价格快照时冻结一个前向 cohort，并只用后来实际采集到的 15/60/240 分钟快照描述调查后的市场延续。`no_context`、Agent 错误、未核验候选和 missing 同样保留；历史调查和缺失窗口不回填。未核验人物姓名不进入实体标签，只有浏览器精确原帖实体可被分组，且仍不代表背书。Token 详情显示单次随访，Sources 显示跨样本汇总；该账本固定不影响 Agent 调度、证据、候选、风控、Paper 或 Live。详见 [Token Context 前向结果学习](docs/TOKEN_CONTEXT_FORWARD_LEARNING_CN.md)。

从 `token-context-admission/v1` 起，每次实际进入 Token Context 检查的 Token 还会前向记录 `admitted/skipped` 与稳定原因：无合格触发、错误退避、全局/同 Token 冷却、每日调用上限、Token 预留预算不足或成功准入。记录只含安全的触发类别、时间、计数和预算快照，不保存 prompt、Agent 原文、项目描述、密码、Cookie、Session 或 secret。Token 详情显示最近一次原因，Sources 显示跨 Token 汇总；跳过不是 `no_context`，也不是正面或负面信号。旧调用不回填原因。

双击：

```text
E:\memeTrader\OPEN_WEB_CONSOLE.cmd
```

或运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_web_console.ps1
```

本机访问地址：

```text
http://127.0.0.1:8787/
```

需要临时远程查看时，可双击 `SHARE_WEB_CONSOLE.cmd`。它通过本机已安装的 Cloudflare Quick Tunnel 创建带随机访问口令的临时 HTTPS 地址；后端仍只监听 loopback，不开放路由器端口。地址和登录提示只写入 Git 忽略的 `data\web_console\PUBLIC_ACCESS.txt`。公开入口通过随机口令保护，只能读取数据并修改后端白名单内的安全设置；钱包区域始终脱敏只读，不能录入私钥、申请测试币或发送交易。它也不会返回 bridge token、平台登录、Codex 会话或任何 secret。

Settings 只允许修改轮询频率、Agent 周期/预算、事件与候选阈值，以及本地平台、公开名人/账号和主题观察清单。Agent 并发仍遵守项目规则，只允许 `1–2`、默认 `2`；Live 页面只有 `LOCKED / Unavailable`，没有启用接口。自主搜索继续使用本机已登录的 Codex/ChatGPT agentic 额度，不要求 OpenAI API Key。

Wallet 只在 `127.0.0.1` 接受私钥录入和 Devnet 操作。私钥不会回显，通过当前 Windows 用户的 DPAPI 加密后保存在 Git 忽略的本机文件中；公开 URL 只能看到脱敏账户状态。该页只允许人工执行 Solana Devnet 测试，不能驱动常驻策略，也没有 Mainnet 开关。

最新真链验证记录见 [docs/WALLET_DEVNET_VALIDATION_20260830.md](docs/WALLET_DEVNET_VALIDATION_20260830.md)。当前钱包连接与 Devnet 集群校验已通过，但官方 faucet 返回 RPC unavailable，因此尚无可声称成功的公开 Devnet 交易签名。

事件详情把全部来源按决策用途、已知权威层级、新鲜度、原始链接和可观察热度排列，并逐条显示**平台、发布者、账号类型、官方/认证状态、已知关注者/覆盖与可见互动、本地观察优先级**。未知字段明确显示为未知，绝不根据平台或显示名猜测影响力。`feature/confirmation` 与 `identity/promotion` 分组展示；后两者始终是仅上下文，影响力再高也不能单独触发决策。这是审计用的**证据优先级**，不是对媒体权威性或事实真假的自动裁决；每项仍显示原始链接、发布时间、本机观察/入库时间和当时决策资格。

Sources 页另有“主题通道覆盖与影子学习”和“来源学习与观察优先级”。Trend Scout 使用五个版本化稳定通道；每轮把实际选中通道、完成/失败、空结果、事件产出和 Observation 数写入追加式账本，Agent 返回的事件必须带本轮有效的 `lane_id`。主题通道只有在本通道至少 20 次完成暴露、10 个运行日、5 次零产出，且全局至少 20 个已接受事件，并具有成熟的 60 分钟 WAIT/CANDIDATE 市场随访后才可参与选择性分配；至少两个可比较通道同时成熟才会启用。倍率限于 `0.80×–1.20×`；普通运行始终保留至少一个按 round-robin 的探索通道，surge 覆盖全部五类。已平仓 Paper 结果只作可选的次级验证。当前运行预计仍在收集样本，尚未启用选择性分配；无论是否启用，它只影响 Trend Scout 的通道分配，绝不进入证据、决策、风险、仓位、退出或 Live。

同页的“账号选择性关注策略”会为每轮实际选中的公开账号保存完成、失败和零产出暴露。只有合格事件中的原始帖子 URL 能与平台和账号路径精确匹配时才归因；转述、同名人物和登录受阻均不猜测为账号命中。至少 20 次完成暴露、10 个运行日、5 次零产出且全局已有 20 个精确命中后，才算发现效率成熟；还必须同时具备成熟的 60 分钟 WAIT/CANDIDATE 市场随访，普通账号才可在 `0.80×–1.20×` 内小幅改变观察轮换。critical 固定且至少 40% 槽位继续探索。

浏览器桥还会为与配置 URL、平台、handle 和 `entity_id` 完全一致的公开账号页建立 30 分钟前向暴露窗口，并把本机收到的原帖 Observation、事件 ID、同事件 60 分钟随访和同事件 Paper 平仓保存为可回链关系。X 首页、搜索页、登录页、同名账号、Telegram 手工发现和旧数据回填均不计入。Sources 页的“同源前向学习闭环”按不同单位诚实展示每一阶段，不把全库无关总数拼成转化率。
人物与平台不会被重复建立一套脱节的排名：有稳定 `entity_id` 时优先复用同一人物的跨平台市场随访，否则才回退到平台级随访；但每个具体账号路径仍必须自己达到暴露门槛，未测试的账号不得继承同人物或同平台其他账号的倍率。Web 分开显示“具备启用资格”与“上轮选择实际因学习改变”，避免把成熟建议误报为已发生调度变化。

来源学习同时展示平台、信息类型、具体来源、已持久化实体以及事件/热点类型在前向样本中提供合格/最早证据的描述性统计。事件类型只在事件第一次被本机接受时冻结；旧事件保持 `unknown`，不按后来结果回填。前向分类会识别明确的体育语境，以及 `goes viral`、`viral clip/video` 等互联网文化传播标记；这不会追改已冻结的 `other/unknown`。Mastodon Collector 也会从新采集记录开始冻结 `platform=mastodon`；旧的泛化 `social` 记录保持原样，不能因代码升级追改。新完全平仓的 Paper 结果分为 `discovery_lead`（事件最早 60 秒合格来源）与 `decision_support`（开仓前每个独立实体/来源最近一条合格证据，避免重复发稿放大）：只有前者可在达到普通标签 20 个/10 天/5 个亏损、人物 30 个/15 天/两个平台后作为联合关注策略的次级验证；后者永久只作入场证据审计，历史闭仓不回填。实际轮换由 `watch-attention/v1` 要求账号暴露效率和 60 分钟 WAIT/CANDIDATE 市场随访共同成熟后才允许。总共 12 个候选观察槽位中至少 40% 始终轮换探索，critical 最多占 4 个且不应用学习倍率。学习不进入 `CandidateEvaluator`、证据权重、canonical margin、安全检查、仓位公式或退出规则；样本不足时网页明确显示证据缺口，不能宣称已学会。详见 [DexScreener 溯源与前向来源学习](docs/DEXSCREENER_PROVENANCE_AND_SOURCE_LEARNING_CN.md)。

OKX Web3 Meme Pump 可提供 launchpad 阶段、社交、开发者、bundle 和同车钱包等补充字段，但核心接口需要官方签名凭据且属于 Premium；当前不抓取网页内部请求，也不把 `SMART_MONEY` / `INFLUENCER` 标签当交易信号。评估与未来接入边界见 [OKX Meme Pump 与聪明钱来源评估](docs/OKX_MEME_PUMP_AND_SMART_MONEY_ASSESSMENT_CN.md)。

为避免只从“实际买入并完全平仓”的事件学习，Runtime 使用 `shadow-event-followup/v2-event-action` 建立前向随访：首次带有效 Token/价格的 WAIT 冻结一个样本；若同一事件后来真实升级为 CANDIDATE，再冻结升级时的价格和当时合格来源。同一事件每种动作最多一个 cohort，CANDIDATE 后因已有持仓或执行门产生的 WAIT 不会重复采样，旧 v1 记录也不会回填。随后只用本机之后真实观察到的 15/60/240 分钟快照计算原始价格延续与区间最高/最低回报。缺失窗口永久记为 missing，不用后来补录的旧时间戳回填。该数据不含手续费、滑点或可成交性，不是 Paper PNL；只有成熟的 60 分钟人物/平台随访可与成熟账号暴露共同进入观察轮换，15/240 分钟、热点类型和主题通道仍只供研究，所有随访永不进入交易。

`shadow-event-admission/v1` 同时为每个新 WAIT/CANDIDATE decision 只写一条前向准入记录，区分已创建、同动作已有样本、WAIT 已被 CANDIDATE 覆盖、缺少决策时价格、缺少来源引用和没有当时合格证据。Sources 分开显示新版本的 CANDIDATE 覆盖率与历史/未受监测候选；旧 CANDIDATE 不补造跳过原因，也不冒充新 cohort。

详细说明见 [docs/WEB_CONSOLE_CN.md](docs/WEB_CONSOLE_CN.md)。

## 浏览器扩展

1. 先启动机器人；
2. Chrome/Edge → 扩展管理 → 开发人员模式 → “加载已解压的扩展”；
3. 选择 `E:\memeTrader\browser-extension`；
4. 在扩展选项中填入 `config.json` 内的 `bridge.token`；
5. 打开需要长期观察的公开页面。

扩展把待发送帖子保存在 `chrome.storage.local`。浏览器 Service Worker 休眠或机器人短暂离线时，队列不会立刻丢失；恢复后会补发。扩展每 30 秒发送页面心跳。

## 机器人怎样买入

买入必须同时满足：

1. 有独立社交、新闻或官方事件；
2. 找到匹配 Token；
3. 同事件第一名超过最低分，并明显领先第二名；
4. 报价、流动性和近期交易可用；
5. 合约/税率/可卖性等硬门槛通过；
6. 账户、持仓数和流动性冲击允许。

仓位由本地公式决定：账户风险预算、止损距离、机会分数、单币上限、现金和流动性冲击上限取最小值。Agent 无权改写金额或绕过风控。

## 机器人怎样卖出

当前 Paper 退出包括：

- 硬止损；
- 四档分批止盈；
- 从峰值回撤后的移动退出；
- 流动性快速恶化或安全状态恶化时退出；
- 叙事长期没有新增证据且链上买盘转弱时退出；
- 最大持仓时间退出。

买入侧限额不会阻止已有仓位卖出。

## Codex / GPT 自主搜索

`autonomous_search.enabled=true` 时，机器人会自己完成三类 Agent 工作，不要求用户事先列完信息源：

1. 主动搜索近两小时内正在加速的国际热点、名人、动物、网络文化、体育、AI、游戏和 Crypto 社区事件；
2. 定期寻找并实际验证新的免费 RSS/Atom 信息源，通过后自动加入动态源注册表；
3. 对链上动量足够强，或具有浏览器桥本机接收的精确人物原帖/高热事件关系的新 Token 反向搜索现实事件，并要求至少两个独立可访问来源。

默认最多同时运行 2 个搜索 Agent 槽位。全球快搜和搜源优先使用 Spark/low，额度不可用时回退 Luna/low；复杂 Token 身份核验使用 Luna/low，必要时才升级 Terra/medium，Sol/medium 仅作为最后回退。普通状态每 12 分钟快搜一次，并按稳定通道轮换覆盖 5 个主题中的 3 个；重大信号期间每 3 分钟覆盖全部主题，连续三次空结果退到 30 分钟。Settings 的自由文本主题只可作为当前已选通道内的提示，不能扩展或注入未选通道。Spark 不可用或单次调用超过 18,000 tokens 时，普通状态最短间隔自动拉长到 30 分钟，重大信号仍保留 10 分钟级回退。Token 专项 Agent 受 5 分钟全局冷却、240 分钟同 Token 冷却和双重入口约束：普通名称反查要求动量分≥80；本机浏览器桥实际接收的精确高影响力账号原帖，或新鲜高热事件高匹配关系可以提前进入调查。项目元数据中的帖子链接不能单独触发。失败时仅进入 10 分钟短退避。调用次数、已使用 token 和下一次调用预留量共同限制预算，`--force` 也不能越过预算。自动发现的 RSS 连续 3 次失败，或近期内容至少一半是 Market Wrap、价格更新、Presale、Top/Best/100x 榜单时，会自动暂停并由后续搜源补充。全部频率、并发、模型、推理强度和上限都可在 `config.json -> autonomous_search` 修改。

上段是源码示例配置的默认值；本机 2026-08-30 已应用一个适度加快但仍适合个人电脑的运行配置：主采集轮询 `60→45` 秒、Token 反向新闻 `45→30` 秒、Trend Scout 普通/热点/空结果退避为 `8/3/20` 分钟、Source Discovery 为 `12` 小时、Token Context 全局/同 Token 冷却为 `4/180` 分钟。实际运行以 Git 忽略的本机 `config.json` 为准，和源码默认值可以不同；保存 Runtime 设置后需要安全重启单一常驻任务才会生效。Agent 并发硬上限仍是 2，没有随频率上调而增加。

界面把采集与分析职责呈现为 6 个逻辑角色：News Radar、Social Pulse、Named Account Watch、Evidence Verifier、Token Context 和 Source Discovery。它们是共享队列中的职责，不是 6 个永久并发进程；仍共同遵守最多 2 个 Agent 子进程的硬上限。Agent Operations 会按任务、模型和推理强度分别累计调用次数、输入/缓存/输出/推理 token、回退与预算，不把不同智能程度的消耗混成一个数字。每个任务还会校验 Agent 返回的 JSON 结构：结构无效时照常计费并记录为 `invalid_output`，随后使用该任务配置的后备模型；通过时记录为 `valid_output`，合法的空事件/空来源仍是有效结果，不会为了制造活动而升级。只有新门生效后的这两类记录参与界面“结构通过率”，旧 `completed` 不冒充已校验样本；结构通过率也不等于事实准确率或投资有效率。

需要登录的平台只在专用的本机 Chrome/Edge 配置中处理，并保持目标公开页面打开。账号密码、Cookie、Session 和验证码只归浏览器/平台所有，memeTrader 不读取、导出或保存；登录不成功的平台直接跳过，并继续使用公开页面、RSS、Agent 搜索和其他可访问来源，不让单个平台阻塞整套采集。登录缺失或页面未打开时，Sources 会显示对应状态。

常规计算、去重、时间判断、评分、仓位和卖出仍全部由本地代码完成。四字母短名称可以触发 Agent 搜证，但不能只靠文字重合直接连接新闻；证据不足时返回 `WAIT`。EVM 使用 GoPlus/Honeypot.is、Solana 使用 GoPlus/RugCheck：每个链族默认至少要有一个外部安全报告，两者都不可用时失败关闭；缺失结果不会被当作安全。语义平局 Agent 的 `agent.enabled` 继续默认关闭。

查看自主搜索状态：

```powershell
.\.venv\Scripts\python.exe -m memetrader status --config config.json --limit 10
```

手工诊断命令（常驻运行无需手工执行）：

```powershell
.\.venv\Scripts\python.exe -m memetrader scout-trends --config config.json --force
.\.venv\Scripts\python.exe -m memetrader discover-sources --config config.json --force
```

完整说明见 [docs/AUTONOMOUS_SEARCH_CN.md](docs/AUTONOMOUS_SEARCH_CN.md)。所有搜索 Agent 使用 ephemeral、只读沙箱，不接触钱包、Broker、私钥或项目写权限。

## 历史测试与未来信息隔离

```powershell
.\.venv\Scripts\python.exe -m memetrader replay examples\historical\temporal_guard.synthetic.json --decision-at 2026-01-01T00:05:00Z
```

该回放只验证：决策时刻之前真正观察到的证据可用；之后的交易所上线、最高价、最终赢家和收益等必须拒绝。真正检验收益只能依赖从现在开始积累的 Forward Shadow/Paper 日志。
