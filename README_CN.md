# memeTrader 0.6.3：个人电脑上的自主信息源 Meme 机器人

后续开发者和 Agent 请先阅读 [docs/PROJECT_CONTEXT/START_HERE.md](docs/PROJECT_CONTEXT/START_HERE.md)。这里保存无敏感信息的产品需求、架构、安全边界、当前状态与运行手册，避免关键上下文只存在于聊天窗口。本轮对整段聊天需求的逐项验收见 [docs/PROJECT_CONTEXT/REQUIREMENTS_ACCEPTANCE_2026-08-30.md](docs/PROJECT_CONTEXT/REQUIREMENTS_ACCEPTANCE_2026-08-30.md)，信息先于市场的独立前向研究规则见 [docs/INFORMATION_FIRST_SHADOW_CN.md](docs/INFORMATION_FIRST_SHADOW_CN.md)，主路径受限时的合法替代链与证据差距见 [docs/PROJECT_CONTEXT/CONSTRAINT_SUBSTITUTION_MATRIX.md](docs/PROJECT_CONTEXT/CONSTRAINT_SUBSTITUTION_MATRIX.md)。

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

1. **登录态浏览器扩展**：被动读取你已打开页面中新渲染的公开帖子，支持 X、Truth Social、Bluesky、Reddit、Threads、Instagram、TikTok 和 YouTube。Telegram 项目内授权已记录，但当前官方 Content Licensing/API 条款仍阻止面向 AI 的抓取与聚合；因此只保留人工目录和外部原始来源，不自动读取、入库或送入 Agent。
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

项目同时维护一份可审查、可版本控制的 [118 条公开社交信息源目录](docs/SOCIAL_SOURCE_CATALOG.json)，覆盖 X、Truth Social、YouTube、Instagram、TikTok、Threads、Bluesky、Telegram 和 Reddit；分类、优先级与跨平台去重原则见 [目录说明](docs/SOCIAL_SOURCE_CATALOG_CN.md)。这只是候选种子，不是每轮扫描全部账号，也不使账号内容自动具备决策资格。13 个 Telegram 候选全部关闭自动摄取、Agent 处理和交易影响，未核验或非官方入口会明确标为 quarantine/transport。Trump、Elon Musk、CZ 等少量高影响实体使用 `critical` 观察轮换标签；最多保留 4 个 critical 账号槽位，且该标签不提高权威、证据角色、热度或决策资格。实际启用的当前观察清单由用户导入/选择后保存在 Git 忽略的 `data/web_console/console_settings.json`，可以与目录版本不同。

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

Web 控制台直接读取当前 `config.json` 指向的 SQLite，不复制策略、不生成演示成交。它提供 Overview、实时事件、Token 发现、候选/决策、Paper Portfolio、Agent Operations、Sources、Audit、安全 Settings、Wallet 和事件/Token 详情共十一个工作区。

Overview 与 Paper Portfolio 展示追加式账户时间曲线、现金/持仓市值/权益/当日 exposure、报价缺失区段、逐笔报价与模拟执行价、滑点、每笔场地费、已知 Token 税和模拟执行失败原因。当前每侧 4% 是早期 meme 的保守不利执行压力，不冒充必然发生的真实滑点；通用场地费估计为每笔 60 bps，报价明确识别为 PumpSwap 时使用 125 bps 保守上限。链费与 priority fee 没有可验证路由时明确保持未建模。零成交时显示真实的平坦现金状态，不生成假仓位或假成交。执行与未来 Live 的严格边界见 [Paper 前向执行与未来 Live 验收](docs/PAPER_FORWARD_EXECUTION_CN.md)。

顶部可在“中文 / English”之间即时切换；选择只保存在当前浏览器本地，刷新后仍会保留。事件标题、Token 名称和来源原文不会被自动翻译。

十一个工作区都会在页面可见且没有未保存表单时自动刷新当前页；Overview 约 10 秒、事件约 12 秒、Token/决策/组合/Wallet 约 15 秒、Agent/Sources 约 20 秒、Audit 约 30 秒、Settings 约 60 秒。当前采用低成本轮询，不需要 Redis、消息队列或额外 WebSocket 服务；切回浏览器标签时会立即取一次新快照，打开的事件/Token 详情也随当前页一起更新。

Overview 顶部的动态采集脉冲不是装饰性计时器。它从 SQLite 已持久化时间戳分别计算“新闻/社交/Agent 信息”和“新 Token/池及快照”两条通道的最近 60 秒数量、5 分钟写入速率、最近写入时间与 active/waiting/stale 状态。只有近期确有写入时才播放脉冲动画；没有新数据会如实显示等待或陈旧，不会伪造“实时运行”。

Token 页另显示详情补全队列的 `pending / hydrated / no_pair / error`、尝试次数、真实 pair 覆盖率和社交链接命中数。Token Context 采用三类调查入口：链上动量、本机浏览器桥已实际接收并精确归因的高影响力账号原帖，以及新鲜高热事件与 Token 的高匹配持久化关系。项目附带的同一帖子链接只是关联种子，查询参数与片段会在送入 Agent 前移除。调查拆成项目附带社交声明、社区扩散、公众人物关联候选、独立报道和触发时链上快照；社区“热度”不合成主观总分，公众人物候选绝不自动解释为支持或背书。只有通过原有时间、相关性、可访问性和至少两个独立域名检查的报道，才可能进入 confirmation 链；其他分栏全部只作审计语境。

每次新的 Token Context 调查还会在当时存在本地正价格快照时冻结一个前向 cohort，并只用后来实际采集到的 15/60/240 分钟快照描述调查后的市场延续。`no_context`、Agent 错误、未核验候选和 missing 同样保留；历史调查和缺失窗口不回填。重复调查保留在审计账本，但标签成熟度每个 Token 只使用最早的前向 cohort，普通标签至少需要 30 个不同 Token，不能用同一价格路径重复抬高样本。未核验人物姓名不进入实体标签，只有浏览器精确原帖实体可被分组，且仍不代表背书。Token 详情显示单次随访，Sources 显示跨样本汇总；该账本固定不影响 Agent 调度、证据、候选、风控、Paper 或 Live。详见 [Token Context 前向结果学习](docs/TOKEN_CONTEXT_FORWARD_LEARNING_CN.md)。

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

事件详情把全部来源按决策用途、已知权威层级、新鲜度、来源链接和可观察热度排列，并逐条显示**平台、发布者、账号类型、官方/认证状态、已知关注者/覆盖与可见互动、本地观察优先级**。未知字段明确显示为未知，绝不根据平台或显示名猜测影响力。`feature/confirmation` 与 `identity/promotion` 分组展示；后两者始终是仅上下文，影响力再高也不能单独触发决策。这是审计用的**证据优先级**，不是对媒体权威性或事实真假的自动裁决；每项仍显示安全来源链接、发布时间、本机观察/入库时间和当时决策资格。

`event-attention-trajectory/v1` 从部署后为每个新关联 Observation 与事件当前 attention 原子追加一个不可更新、不可删除的本机记录点；旧事件不回填。事件列表、Overview 和详情显示累计分数曲线、本机 10 秒/30 秒/1 分钟/5 分钟新观察到达率下界、分数速度/加速度及覆盖状态，固定标记 `affects=none`。覆盖不足返回 `null/under_resolved`，不会填零或画假平线。当前采集仍没有全平台曝光分母、完整互动修订轨迹和稳定作者分母，因此全网 mention、reply/quote/repost、跨社区和完整跨平台扩散仍明确为 unavailable，绝不冒充已完成。

`event-claim-assessment/v1` 从注册上线后的新 Observation 开始，另外追加不可更新、不可删除的事实状态账本，区分 `confirmed_fact / probable_report / unverified_rumor / false_claim / correction / retraction / satire / impersonation / promotion / unassessed / excluded_future`，并保留事实、身份、attention、Meme 催化和纠正风险五类置信度。事实状态、上面的本机传播轨迹和纠正/撤回状态在事件详情中分栏展示，三者都固定 `affects=none`。Trend Scout 与 Token Context 的 Agent 输出即使 URL、DNS、时间和独立域名检查通过，也只是 `identity/context-only` 的结构化待核验判断，不会再直接成为 `feature/confirmation` 决策证据；相邻评估可能来自不同来源，因此界面只称“评估标签变化”，不把它冒充同一 claim 的证实或推翻。旧事件不回填。

`agent-fact-verification/v1` 为通过本地 URL、时间和可达性门的新 Trend/Token Context 候选启动第二个独立 Codex 上下文，检查精确来源正文是支持、反对还是仅提供语境。Trend 每轮批量一次，Token Context 每次最多一个；它不是新常驻循环，仍共享最多两个 Agent 槽位。调用按 `fact_verifier + model + reasoning_effort` 单独统计。不同域名支持只是独立来源下界，结果固定 `decision_eligible=false / affects=none`，原 Observation 仍是 identity/context-only，不改变策略或 Paper。详见 [docs/AGENT_FACT_VERIFIER_CN.md](docs/AGENT_FACT_VERIFIER_CN.md)。

`source-item-revision/v1` 另行从部署时刻向前保存原始来源条目的不可变版本链。RSS/Atom 使用 `guid / id / link`，Bluesky 使用 post URI，Mastodon 使用 status ID/URI，浏览器桥使用永久链接作为稳定身份；连续相同抓取不追加，正文/标题/来源时间变化、来源明确删除、明确撤回、明确纠正和再次出现分别记录。只有平台或发布方的明确标记可形成删除/撤回；轮询缺项、429、403/404、页面虚拟滚动和 DOM 节点消失都不能生成删除 tombstone。删除、撤回、事实为假是三个独立含义，origin 与 transport 未被证明分离时保持 `unknown`。版本账本固定 `decision_eligible=false / affects=none`，不增加 Observation、attention、候选分数或仓位；旧条目只在部署后再次真实抓取时建立 baseline，不做历史回填。纠正后的市场反转结果仍待前向样本，因此不能把工程核验器称为绝对事实裁判。

`observation-provenance/v1` 从部署后为每条新 Observation 追加不可更新、不可删除的 `Origin → Transport → Local capture` 路径断言。浏览器桥或公开平台 API 实际拿到的精确永久帖子可标记为 `proven_direct_item`；RSS source 元素只是上游声明，Agent 搜索只证明候选 URL 当时可访问，域名推断与单次出现都不等于独立来源。事件详情逐条展示路径，并只对至少两个已证明且不同的原始条目显示“不同原始条目下界”；旧的“来源字符串只出现一次即独立”的加分已移除。账本不回填历史，隐藏内部 root key，固定 `decision_eligible=false / affects=none`，不会改变现有策略或 Paper。

Sources 页另有“主题通道覆盖与影子学习”和“来源学习与观察优先级”。Trend Scout 使用五个版本化稳定通道；每轮把实际选中通道、完成/失败、空结果、事件产出和 Observation 数写入追加式账本，Agent 返回的事件必须带本轮有效的 `lane_id`。`trend-attention/v2-experiment-gated` 把这些相关性统计降为描述性假设：即使通道暴露和 60 分钟随访成熟，实际调度倍率仍固定为 `1.00×`，不能自行改变通道分配。普通运行继续按 round-robin 探索，surge 覆盖全部五类；任何未来有限倍率都必须先经过预注册随机实验和独立时间顺序复验。已平仓 Paper 结果只作可选次级验证；所有值绝不进入证据、决策、风险、仓位、退出或 Live。

Sources 的“来源轮询暴露”从 `source-poll-exposure/v1` 上线后，为每一次真正发出的 RSS、Bluesky、Mastodon 和 Token→Google News 反查请求追加一行；成功但无新增、重复、过滤、仅上下文、质量暂停和错误都保留。禁用、冷却或尚未到期不计为一次尝试。账本只保存由无参数 URL 或查询哈希生成的稳定脱敏 ID 与错误类型，不保存原始查询词、带参数 URL 或异常正文。完成轮、零新增、错误、获取数、新 Observation/事件及 F/C 与 I/P 数可在中英文页面查看；至少 20 个完成轮和 5 个不同日期只表示可人工复核，不会自动改变频率、Agent 路由、证据、候选、Paper 或 Live，历史轮询不回填。

Sources 的“完整 Token 总体前向结果”从 `token-universe-forward-outcomes/v1` 注册后，为每个本机首次发现的新 Token 建立一次且仅一次 cohort，不选择性排除后来没有进入事件/决策的 Token。Runtime 会在发现后 5 分钟内主动取得基准价，并在 15/60/240 分钟目标窗口通过现有 DexScreener 批量报价补充固定时点快照；没有基准、没有结果、no-pair 和报价错误仍保留在发现账本中。页面分开显示固定时点原始回报和本机稀疏采样峰值，后者不是市场 ATH；同时显示当时 WAIT/CANDIDATE/Paper 召回。旧 Token、用户事后列举的赢家和错过窗口绝不回填，结果固定 `decision_eligible=false / affects=none`。

Sources 的“逐 Token 报价尝试”从 `token-discovery-quote-attempt/v1` 注册后，为上述完整总体的每次 DexScreener 批量报价逐 Token 冻结 `running → success/no_pair/error/interrupted` 终态、时点角色、请求延迟、排队年龄、重复次数、错误类型、下一次允许重试时间和截止错失。批次异常不再只有一个 round 级错误，也不会绕过冷却立即热重试；失败使用最长 15 分钟的有限指数退避和确定性抖动。市场报价使用独立 HTTP 连接池，避免新闻、社交、安全或 Agent 请求占满同一连接池。该账本只影响报价调度，不改变事件证据、Decision、Paper、仓位或 Live，注册前批次不回填，Web 不返回逐 Token 标识。

Audit 的 `token-universe-outcome-quality/v1` 是部署后才生效的追加式质量覆盖层，保留上述 v1 原始结果不变。它把 provider、chain、DEX、pair、quote、流动性、报价年龄和 PumpFun→PumpSwap 迁移路径一起冻结，分别展示原始混合路径峰值、同 pair、同 route、迁移调整和满足流动性门后的成本估算；只有卖出能力、honeypot 和税费均已有当时安全证据时才显示“确认可执行净回报”。`NULL` 流动性不是零流动性，跨池跳变也不是可成交收益。覆盖层从自己的注册点向前运行，不回填旧结果，固定 `decision_eligible=false / affects=none`。

Audit 的“完整总体漏检账本”使用 `missed-opportunity-audit/v1`，从自身注册后为上述每个新结果追加一条不可变审计记录；低涨幅、缺基线和缺结果同样留在分母。只有本机采样路径达到预注册的 +25% 层且目标时点前没有 Paper 买入时才标记为 `potential_miss`，再按 `no_entry_snapshot / no_outcome_snapshot / no_decision / wait / reject / candidate_no_paper_buy / paper_bought` 展示可证明的粗断点。它不是市场 ATH、可成交收益或已证明的策略错误，不回填注册前案例，不改写历史决策，也不影响策略、Agent、Paper 或 Live。

同页的“账号选择性关注策略”会为每轮实际选中的公开账号保存完成、失败和零产出暴露。只有合格事件中的原始帖子 URL 能与平台和账号路径精确匹配时才归因；转述、同名人物和登录受阻均不猜测为账号命中。`watch-attention/v3-experiment-gated` 只用成熟相关性生成实验假设，实际倍率固定为 `1.00×`。`attention-experiment/v1` 可在一对同平台、同优先级、非 critical 的普通账号之间随机分配一个观察槽位：第 1 阶段固定每组 60 个 assignment，2:2 平衡区块在 Agent 调用前持久化，错误、调用前中止、零产出、跨组碰撞与 60 分钟缺失均保留在 ITT 分母。全部样本终结前不允许显示通过；通过后仍需独立时间顺序 holdout，不自动提高倍率。critical 固定且总槽位至少 40% 继续探索。

浏览器桥还会为与配置 URL、平台、handle 和 `entity_id` 完全一致的公开账号页建立 30 分钟前向暴露窗口，并把本机收到的原帖 Observation、事件 ID、同事件 60 分钟随访和同事件 Paper 平仓保存为可回链关系。X 首页、搜索页、登录页、同名账号、Telegram 手工发现和旧数据回填均不计入。Sources 页的“同源前向学习闭环”按不同单位诚实展示每一阶段，不把全库无关总数拼成转化率。
人物与平台不会被重复建立一套脱节的账号排名：只有稳定且无冲突的 `entity_id` 才能复用同一人物的跨平台市场随访；缺少人物映射时不再回退到平台总体结果。每个具体账号路径仍必须自己达到暴露门槛，未测试的账号不得继承同人物或同平台其他账号的倍率。Web 分开显示“具备启用资格”与“上轮选择实际因学习改变”，避免把成熟建议误报为已发生调度变化。

来源学习同时展示平台、信息类型、具体来源、已持久化实体以及事件/热点类型在前向样本中的 `feature/confirmation/identity/promotion` 数量，并且只有 observed、ingested、published 三个时间都不晚于该事件首个最终 CANDIDATE 的 feature/confirmation 才计入“决策时合格率”和候选前关联。事件类型只在事件第一次被本机接受时冻结；旧事件保持 `unknown`，不按后来结果回填。前向分类会识别明确的体育语境，以及 `goes viral`、`viral clip/video` 等互联网文化传播标记；这不会追改已冻结的 `other/unknown`。Mastodon Collector 也只从新采集记录开始冻结 `platform=mastodon`；旧的泛化 `social` 记录保持原样。新 Paper 买入把最终 `decision_id` 和已准入 `cohort_id` 同时冻结到持仓、每笔成交和执行尝试；完全平仓后仅把该 cohort 决策时冻结的最早合格 feature/confirmation 记为 `discovery_lead`，并按记录的手续费、滑点和已知卖出税计算净结果。缺少 decision/cohort 的平仓或旧执行尝试会明确标为未链接；旧的事件时间窗归因保留为 `legacy-event-window/v1`，但不进入学习。平台平均表现不能替代具体账号，实体缺失或冲突时保持基线；同一事件后续 WAIT/REJECT/CANDIDATE 仍保留在动作账本，但不重复抬高人物/平台样本。描述性排名不能直接改变轮换，只有预注册随机实验可以交替一个普通槽位；总共 12 个候选观察槽位中至少 40% 始终轮换探索，critical 最多占 4 个且不应用实验倍率。Overview 直接显示当前版独立事件、动作分母、固定时点缺失、独立 Token、精确 Paper 链和 Phase 2 数据门；“正在收集”不能显示成“已经学会”。学习不进入 `CandidateEvaluator`、证据权重、canonical margin、安全检查、仓位公式或退出规则。详见 [DexScreener 溯源与前向来源学习](docs/DEXSCREENER_PROVENANCE_AND_SOURCE_LEARNING_CN.md)。

OKX Web3 Meme Pump 可提供 launchpad 阶段、社交、开发者、bundle 和同车钱包等补充字段，但核心接口需要官方签名凭据且属于 Premium；当前不抓取网页内部请求，也不把 `SMART_MONEY` / `INFLUENCER` 标签当交易信号。评估与未来接入边界见 [OKX Meme Pump 与聪明钱来源评估](docs/OKX_MEME_PUMP_AND_SMART_MONEY_ASSESSMENT_CN.md)。

为避免只从“实际买入并完全平仓”的事件学习，Runtime 使用 `shadow-event-followup/v3-strategy-labels` 建立前向随访：每个独立事件的首次 WAIT、REJECT、CANDIDATE 分别冻结样本；CANDIDATE 后因已有持仓或执行门产生的 WAIT 不会重复采样。除平台、人物、来源和热点类型外，还冻结事件热度/新鲜度、来源组合、链、Token 年龄、流动性、市值、5 分钟量、买卖压力、安全状态、评分层、canonical margin、请求仓位和拒绝原因。从 v3 起 `token_snapshots` 同时保存本机 `ingested_at`；entry 必须在决策时已入库，15/60/240 分钟结果快照必须在 target 后才真实入库。预先写入未来时间戳、升级前没有入库证明的快照和错过窗口均不能回填。该数据不含手续费、滑点或可成交性，不是 Paper PNL；所有人物关联仅作上下文分层，永不解释为背书、加仓或交易信号。

`shadow-event-admission/v2-all-actions` 同时为每个新 WAIT/REJECT/CANDIDATE decision 只写一条前向准入记录，区分已创建、同动作已有样本、WAIT 已被 CANDIDATE 覆盖、缺少决策时已入库价格、缺少来源引用和没有当时合格证据。Sources 分开显示三类动作、执行成交/拒绝和历史/未受监测候选；旧 decision 不补造跳过原因，也不冒充新 cohort。

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
