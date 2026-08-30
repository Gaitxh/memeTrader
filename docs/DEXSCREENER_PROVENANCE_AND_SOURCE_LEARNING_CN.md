# DexScreener 链接溯源与前向来源学习

状态：0.6.3 当前发布线；Paper 自动策略，Mainnet Live 永久锁定。

## 1. 旧 model1 / model3 的准确含义

用户描述的旧路径 `D:\P5\_completeSystem` 与设备实际路径不同；本轮只读核对的是 `D:\P5_completeSystem`，另有冻结审计副本位于 `E:\P5_completeSystem\round2_workspace_large\input_support\D_drive\P5_completeSystem\root_pipeline_sources`。旧项目不被修改。

- `model1` 高频轮询 DexScreener 的 Profile、Community Takeover、Ads 和 Boost 等展示/推广面。它的“新 Token”是首次在这些页面被本机看到的 Token，不是链上全部新铸币，也不是全部新池。
- `model1` 丢弃了原始发现面、项目网站和社交链接，并把 `/tokens/v1` 的扁平 pair 列表误当成嵌套 `pairs` 解析；由此产生的伪造 `pairCreatedAt` 逻辑没有复制到 memeTrader。
- `model3` 不是发现器。它消费 model1 的地址并轮询市场数据；旧格式没有保存 pair identity，多池结果可能混进同一 Token 序列，造成错误价格跳变。
- 两者都没有完成“附带链接 → 原始新闻/发言 → 独立验证”的链路，也没有调用 ChatGPT/Codex Agent。

当前实现只借鉴“从 Token 展示面反向取得链接种子”的方向，不复制上述缺陷。

## 2. 当前 DexScreener 发现面

Runtime 默认每 90 秒读取官方公开端点：

| 发现面 | 保存角色 | 含义 |
|---|---|---|
| Token Profiles | `identity` | 项目方提交/展示的资料与链接 |
| Community Takeovers | `identity` | 社区接管资料；仍是项目相关声明 |
| Ads | `promotion` | 付费展示 |
| Latest Boosts | `promotion` | 最近购买的可见度 Boost |
| Top Boosts | `promotion` | 当前 Boost 排名 |

只使用 DexScreener 官方 API 文档中的端点，不使用旧 model1 的未文档化 `recent-updates` 路径。个人电脑默认每 90 秒轮询一次发现面；每面最多 40 条，每轮最多处理 180 个待补全地址，并由客户端拆成官方 `/tokens/v1/{chainId}/{tokenAddresses}` 的不超过 30 CA 批次（最多 6 个请求）。`max_hydrations_per_cycle` 限制的是地址数，不是 HTTP 请求数；这个吞吐只用于便宜的确定性 Dex 详情补全，不提高 Agent 调用频率。配置位于 `sources.dexscreener_discovery`，Web Settings 只允许安全范围。

各 30 地址批次独立提交结果；某一批发生瞬时网络错误时，只把该批放回退避重试，不丢弃同轮其他成功批次。

官方依据：

- [DexScreener API reference](https://docs.dexscreener.com/api/reference)
- [DexScreener Boosting](https://docs.dexscreener.com/boosting)
- [DexScreener token listing](https://docs.dexscreener.com/token-listing)

Boost 是购买的可见度，不是自然热度、独立新闻或名人背书。Token 信息也可能来自项目方或外部列表，因此 Profile、Takeover、Ads、Boost 和 pair `info` 一律先作为不可信发现种子。

## 3. `token_source_links` 证据模型

SQLite 新表按 Token 保存：

- `provider` 与 `discovery_surface`；
- `role`：只允许 `identity` 或 `promotion`；
- 原始 URL、规范化 URL 与链接类型；
- 平台、标签、验证状态；
- 本机首次/最后观察时间；
- 有上限的原始提供方片段。

链接类型包括 Dex 页面、项目网站、社交主页、社交帖子、搜索页和 `telegram_manual`。同一 URL 在不同发现面保留不同 fingerprint，便于回答“在哪里、何时看到”。Dex 返回的元数据状态是 `provider_metadata`，不是 `verified`。Telegram 链接只在网页作为人工目录显示，不进入自动抓取或 Token Context Agent。

流程为：

```text
Dex 展示面 / pair info
        ↓
identity / promotion 附带链接（发现种子）
        ↓
Token Context 仅把非 Telegram 种子作为不可信搜索提示
        ↓
实时网页搜索寻找独立、当前、可复核的原始来源
        ↓
通过时间、角色、独立性与来源安全校验后形成 Observation / Event
```

项目 URL 不再参与 Token 与事件的词法重叠评分，防止链接路径中的词造成假匹配。多 pair 报价只选择同 chain、同 base token address 且流动性最深的 pair。

### 3.1 新 Token 详情补全队列

每个新写入 SQLite 的 Solana Token 都会进入 `token_detail_hydration` 持久化队列；PumpPortal、GeckoTerminal 与 Dex 发现面共享同一补全路径。队列状态为 `pending / hydrated / no_pair / error`，进程重启后仍保留。Dex 尚未形成可查询 pair 时不会丢弃 Token，而是按 5 分钟、30 分钟、2 小时、6 小时退避重试；网络错误 5 分钟后重试。

`hydrated` 只说明 Dex 返回了同链、同 base CA 的详情，不说明一定存在社交链接，更不说明 Token 安全或叙事真实。Web Token 页分别显示详情补全覆盖率和真正发现社交主页/原帖的 Token 数，不能把 `no_pair` 或空社交资料写成已完成调查。

### 3.2 Agent Token Context 的审计分栏

通过本地流动性、5 分钟成交量、交易数、买卖比和动量门槛的 Token，才可能进入受预算 Token Context Agent。Agent 使用 pair info 中的 `social_profile / social_post` 作为不可信调查入口；项目网站、Dex 页面、搜索页、Telegram 和推广面不会作为社交原帖送入 Agent。调查结果追加到 `token_context_assessments`，固定分为：

- 项目附带社交声明：永远是 `project_attached_unverified`；
- 社区扩散观察：描述可复核的跨平台传播，不主观评价“社区好坏”；
- 公众人物关联：Agent 结果只能是 `unverified_candidate`，不能自动写成支持、背书或因果影响；
- 独立报道：仍需本地重新请求、时间检查、相关性阈值和至少两个独立域名；只有这一路可沿原有 confirmation 链进入事件系统；
- 链上动量触发快照：只解释为什么启动调查，不能替代新闻或社交证据。

评估记录包含本机时间、触发快照、模型、推理强度、token 用量和逐 URL 核验审计。除通过旧有独立报道门的 Observation 外，整个评估保持 `decision_eligible=false`，不进入候选排名、仓位、退出或 Live。

## 4. 不是“全面关注”，而是受控学习

关注清单分三部分：

1. `critical`：少量人工确认的高影响实体保留每轮槽位，例如 Donald Trump、Elon Musk、CZ。critical 账号最多占 4 个槽位；超出的账号回到常规候选池。它只改变观察轮换，不改变证据质量。
2. 策展槽位：按人工 P5–P1 优先级选择高信噪比账号；P5 不再与 P1 获得相同长期频率。
3. 探索槽位：12 个候选观察槽位中至少 40%（当前即至少 5 个）用稳定 round-robin 覆盖尚未证明价值的来源，避免系统只关注既有偏好。

`source_utility_outcomes` 是追加式 Paper 学习账本。只有仓位完全平仓时才记录；WAIT、REJECT、开放仓位和部分平仓不产生结果。归因只给开仓前最早 60 秒窗口内、当时已在本机看到且角色为 `feature/confirmation` 的 Observation；并列来源平分权重。`identity/promotion`、未来/陈旧证据和后来确认不获收益归因。

网页同时显示早期命中、合格证据率和候选关联率，但它们只是描述性研究统计。Paper 标签的成熟门槛为：

- 普通平台/类型/来源：至少 20 个加权已平仓 Paper 结果、10 个结果日、5 个亏损结果；
- 人物实体：至少 30 个结果、15 天、覆盖两个平台，并仍满足亏损多样性；
- 效用为经过 `n/(n+20)` 收缩后的费后平均回报；
- 达标只表示“可作次级验证”，不能单独改变账号轮换；
- 不满足门槛时状态显示“收集样本”。

事件在第一次被本机接受时，还会由固定、可测试的本地规则冻结为一类：政治/公众人物、名人/娱乐、动物/互联网文化、体育、AI/科技/游戏、Crypto 原生或其他。旧事件和迁移前记录保持 `unknown`，不得按后来走势回填。事件/热点类型的 Paper 表现只做描述性统计，当前永远显示“仅观察”，不会改变账号轮换、策略或风控。

Trend Scout 的检索机会另由 `trend-lanes/v1` 五个稳定通道记录。`trend_lane_runs` 保存一次 Agent 调用的选择模式、模型、推理强度、开始/结束、完成/失败和总产出；`trend_lane_run_lanes` 保存本轮每个被选通道的暴露、空结果、事件和 Observation 数。被 Agent 返回的事件必须携带本轮允许的 `lane_id`，该 ID 同时冻结在 Observation 原始元数据中，完全平仓后才可能产生对应的条件性 Paper 结果。

`trend_watch_account_exposures` 同时保存本轮实际选中的平台/账号、人物映射、critical/策展/学习/探索角色，以及完成、失败、精确原帖命中和零产出。原帖归因要求最终公开 URL 的平台和账号路径与本轮账号精确匹配；新闻转述、显示名相同、同平台其他帖子或登录拦截不能产生人物归因。旧轮次不回填。普通账号至少需要 20 次完成暴露、10 个运行日和 5 次零产出，且全局累计 20 个精确原帖命中后，发现效率才成熟。

`watch-attention/v1` 再要求同一人物（不足时回退到平台）具有成熟的 60 分钟 WAIT/CANDIDATE 影子随访；两道门同时通过后，普通账号才可在 `0.80×–1.20×` 内改变 Agent 观察轮换。已平仓 Paper 标签只作可选的次级验证，不能单独激活。critical 账号保持固定，至少 40% 候选槽位继续轮换探索。

跨平台人物使用显式持久化的 `entity_id` 合并市场随访，无实体映射时才使用平台随访。发现效率始终保持在具体的平台 + handle 账号路径上：一个账号即使与已成熟账号属于同一人物，也不能继承它的暴露样本或倍率。策略可启用和上轮实际选择是两个独立状态；只有与不使用倍率的基线排名比较后选中顺序真实改变，Web 才显示“上轮选择已因学习改变”。

主题通道的每轮暴露、空结果和错误/失败结果已经记录。`trend-attention/v1` 仅在每个候选通道均已达到至少 20 次完成暴露、10 个运行日、5 次零产出，并有成熟的 60 分钟 WAIT/CANDIDATE 市场随访，且全局至少已有 20 个已接受事件时评估；必须至少两个可比较的成熟通道同时存在，才可在 `0.80×–1.20×` 内选择性调整 Trend Scout 通道分配。普通运行仍保留至少一个基线 round-robin 探索通道，surge 仍覆盖全部五类。已平仓 Paper 结果可作次级验证，但不是激活条件。当前运行预计仍在收集样本，选择性分配尚未启用。这里的结果只说明“事件通过哪个检索路径被发现后的条件历史”，不证明题材导致收益；即使启用，它也只影响 Trend Scout 通道分配，不改变频率、Agent 数、证据权重、策略、决策、风险、仓位、退出或 Live。

这种结果是关联而不是因果。它只回答“有限资源下一轮先观察谁”，不能回答“谁会让币上涨”。

### 4.1 WAIT/CANDIDATE 固定时点影子随访

完全平仓 Paper 结果只覆盖真正开过仓的事件，单独使用会造成明显选择偏差。`shadow-event-followup/v1` 因此在某个事件首次形成有效 Token 和决策时价格后，为 WAIT 与 CANDIDATE 一并建立一次不可重复的事件 cohort：

- 每个事件只冻结第一次合格 cohort，后来改名、换 Token 或看到结果后不能重选；
- 只保存决策时已观察、已摄入、角色为 `feature/confirmation` 的最早 60 秒来源，未来摄入、未来发布时间、identity、promotion 和后来确认不进入标签；
- 固定观察 15、60、240 分钟，只使用目标时点后 30 分钟内本机实际写入的第一条价格快照；
- 同时记录从入场快照到结果快照之间的最大/最小原始价格回报；
- 窗口超时仍无快照时追加 `missing`，即使后来补进一个旧 `observed_at` 快照也不回填；
- 结果按平台、信息类型、账号类型、来源、人物实体、事件 topic 和 Trend Scout lane 展示。只有成熟的 60 分钟人物/平台结果可与成熟账号暴露共同进入 `watch-attention/v1`；其他维度和时间窗保持只观察。

影子审查的普通标签至少需要 30 个不同事件、15 个事件日和 8 个加权非正结果；人物实体要求 50 个事件、20 天且覆盖两个平台。原始回报没有扣除手续费/滑点，也不证明可成交，因此不能与 Paper PNL、模拟买卖或收益预测混为一谈；其唯一可执行用途是与账号暴露门共同约束观察轮换。

## 5. 不可跨越的隔离边界

来源学习没有调用路径进入：

- `CandidateEvaluator` 的 match/candidate score；
- evidence role、freshness、independent origin；
- canonical margin；
- GoPlus/Honeypot/RugCheck 安全门；
- Paper 仓位金额、止损、止盈和退出；
- Mainnet Live 或钱包签名。

常驻策略继续是 Paper。学习开关关闭、数据库为空或样本不足时，系统仍按 critical + 人工策展 + 探索轮换运行。

## 6. Web 表现

Token 页顶部显示近期 Solana Token 的详情补全、等待/无 pair、错误、社交链接发现数和真实覆盖率。详情抽屉把附带链接放在独立的“发现种子”面板，并新增五路 Agent 语境评估；所有项目声明、社区扩散和公众人物候选均标记 `CONTEXT ONLY`。真正关联到 Event 的 Observation 在下方单独显示，标题为“已关联叙事 / 事件观察”，不能写成“已验证”。

Sources 页显示：

- 五个稳定主题通道的完成/总暴露、失败、空结果、事件产出、最近选择和影子成熟度；
- WAIT/CANDIDATE 事件在 15/60/240 分钟的前向随访覆盖、缺失、正向延续、平均原始回报与区间高低点；
- 平台 / 信息类型 / 人物实体 / 具体来源 / 事件与热点类型；
- 事件数与 Observation 数；
- 早期合格证据、合格证据率、候选关联；
- 已平仓 Paper 数、胜率和费后均值；
- 样本置信度、是否达到激活门槛、当前轮换倍率；
- 固定的非因果、非交易权重双语说明。

空数据库或没有已平仓 Paper 时显示“尚无样本 / 收集样本”，不生成模拟趋势，也不把 0 次结果伪装成 0% 胜率。
