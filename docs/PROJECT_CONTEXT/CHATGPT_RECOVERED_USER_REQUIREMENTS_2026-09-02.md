# 从 Codex 主线程恢复的用户需求与执行约束 · 2026-09-02

状态：`RECOVERED / SANITIZED / PENDING_CONTINUOUS_RECONCILIATION`

来源：本机 Codex 结构化 thread history 中目标线程 `01a0514b-bbb5-7400-baf9-d9feb4dc603d` 的 139 条 `userMessage`，按时间顺序恢复并与当前 `AGENTS.md`、`CURRENT_OBJECTIVE_AND_PLAN.md`、`REQUIREMENT_LEDGER.md` 对照。本文件只保存脱敏后的需求、意图、后续修正和执行含义；历史消息中出现过的任何凭据、钱包材料、token、cookie、密码或临时连接信息均不复制。

本文件不是新的平行需求源。发生冲突时仍按项目既有 authority order：最新用户明确指令 / 安全边界 → `AGENTS.md` 冻结契约 → 当前 Objective/Requirement Ledger → 当前代码/r6 SQLite/测试/运行事实 → 本恢复记录与历史建议。

## 1. 北极星目标：不是“做完功能”，而是持续提高真实赚钱概率

用户在主线程中反复表达的最终目的可以稳定归纳为：

- 这是一个实时、持续学习、持续调整、持续优化和持续迭代的新 Meme Token 系统；
- 目标不是增加页面、Agent、Decision、Paper 成交数或历史回测收益，而是更早发现真正具有传播/叙事/资金驱动力的机会，正确绑定可交易 Token，并在真实近似成本下形成可重复的正向经济结果；
- 用户多次用“为了赚钱”“不要偏离方向、目的和目标”纠正 Codex 的局部优化；
- 当新需求、补充提醒、工具问题或 UI 问题出现时，默认不能抢占当前主线，除非它确实改变当前最高影响的盈利链路断点。

因此，每个实施动作开始前必须能回答：

> **它将改变 `Source/Token discovery → Event↔Token evidence → exact CA/canonical → executable Decision → Paper execution → forward learning` 中哪一个当前已经观察到的瓶颈？**

如果回答不出来，保留想法，但不得替代当前 P0/P1。

## 2. 用户反复强调而执行不稳定的规则

### 2.1 不要因为新问题忘记旧需求

用户多次要求：全面、深入、细致回顾本聊天；区分已实现、未实现、明确跳过、被后续要求取代、描述不清需重新提炼的事项；新补充不能覆盖旧的长期要求。

执行含义：

- 新提示首先分类为 `SUPERSEDE / PROMOTE_NOW / NEXT_CYCLE / PRESERVE_CANDIDATE / REJECT`，不能默认“最新一句话 = 整个项目的新主线”；
- 已完成项不反复做；连续项不能误标 DONE；明确被后续要求取代的历史项不复活；
- 每次 context compaction、新聊天或长周期恢复后，应从 E 盘权威状态重建当前目标，而不是依赖对话记忆。

### 2.2 不要避重就轻，不要用容易完成的工作替代赚钱链路

用户明确指出过执行方向偏移，并多次要求“不要偏离”“不要避重就轻”。历史中 Codex 自己也承认曾把过多注意力放在 ChatGPT 协同机制和 Jupiter 防错细节，而不是解释为什么交易少、漏掉哪些上涨 Token、候选漏斗如何修复、Paper 如何真实执行。

执行含义：

- UI、美化、文档、审计、额外 provenance、流程性 review 只有在直接影响当前 acceptance 或真实运行断点时才优先；
- 修完一个局部安全/正确性问题后，应立即回到当前经济瓶颈，不继续层层加审计；
- “测试全绿”不是业务目标完成。

### 2.3 避免不必要的防御性、审核性、复核性、测试性工作

用户至少两次明确纠正：不要做太多不必要的防御性操作/测试；后来更强地指出“太多太多不必要的防御性、复核性、审查性行为，重点不在这里”。

恢复后的执行规则：

- 防御/审核/复核必须绑定一个真实观察到的故障、污染风险、资金风险、明确 acceptance criterion 或不可逆发布门；
- 同一问题最多做必要的最小验证；通过后停止，不为“更放心”再做等价复核；
- 一个失败路径连续两轮只产生类似修补时，必须重新检查因果假设，而不是继续加 guard/reviewer/test；
- 高强度三路 ChatGPT 复核只用于关键架构、策略、实验设计、重大部署/资金风险门；普通局部修复不得机械复制“三审”。

### 2.4 开源/官方/成熟经验优先，避免重新发明轮子

用户在多个时点明确要求：信息采集、社交平台、Telegram 替代、工具缺口、实现不了的能力，都应先去 GitHub/开源社区/成熟工具中查是否已有可用实现或经验；如果直接路径不行，寻找合法合规的“曲线”实现方式达到真实目的。

恢复后的执行规则：

1. 遇到工具/实现瓶颈，先判断是否属于通用问题；
2. 通用问题优先查：官方文档 → 成熟开源项目 → 上游 issue/discussion → 有真实运行经验的社区资料；
3. 复用候选要按维护活跃度、许可、依赖复杂度、安全边界、平台条款、运行成本和当前架构适配性筛选；
4. 已有成熟方案能解决时，不自建大型替代系统；
5. 外部方案只是候选，最终仍以当前代码、r6 前向事实、成本/收益和安全边界验证；
6. 平台原路径不可用时，不应因工具限制直接放弃业务目标，而应寻找最小合法合规替代路径。

## 3. Agent / 模型成本：生产 Agent 与开发 Agent 必须分开治理

用户多次要求：不同复杂度任务使用不同智能程度和推理强度；节省 agentic 花费，同时兼顾完成度、准确性、有效性和速度；困难任务可以升级更强模型。

### 3.1 生产 memeTrader Agent

当前 `AGENT-001/002` 已覆盖 Trend / Source / Context 的有限并发、预算和模型阶梯。历史中用户曾提出极大增加甚至取消日预算，但后续项目事实表明预算不是当前主要瓶颈，因此当前“高但有限 + 有证据再提高”的规则优先于早期泛化的“取消预算”。

### 3.2 Codex 开发过程的子 Agent

这是现有台账覆盖不足的独立成本面。对目标 Codex thread 的结构化 history 检查发现：

- 共有 112 个 turn、21,808 个结构化 item；
- 发生过 99 次 context compaction；
- `subAgentActivity` 中有 91 次 `started`，且 91 个不同 agent path；
- 仅按 path 名称包含 `audit/review/recheck` 的保守口径，就有 48 个 review/audit 类启动。

这些数字不等价于“48 次都浪费”，但与用户多次反馈“过多复核/审查、推进慢、agentic 成本高”方向一致，足以要求独立治理开发 Agent，而不能只管理运行时 Agent。

恢复后的默认路由：

- **T0 确定性/机械工作**：本地代码、搜索、SQL、脚本、计算直接完成；不启子 Agent。
- **T1 窄范围读取/格式/已知模式修改**：最低足够模型 + low reasoning；能单线程完成就不并行。
- **T2 局部调试/跨少量文件实现**：中等能力/medium；只有真正可并行且互不写同一文件的子任务才开子 Agent。
- **T3 因果、统计、架构、交易经济学、实验设计、根因长期卡住**：升级 Lead ChatGPT 高强度推理；Codex负责读当前事实、实施和测试。
- **T4 会改变资金风险、生产边界、核心策略或实验 estimand 的重大 gate**：最多三条职责明确且互补的高强度 ChatGPT 独立复核，由 Lead 合并；不是三个 Codex 子 Agent，也不是三个泛泛重复 reviewer。

默认原则：**能用确定性代码完成的，不花模型；能用一个便宜 Agent 完成的，不开三个；需要高智能判断时，宁愿让一个/少数强 ChatGPT 做真正的推理，也不堆低价值 reviewer。**

## 4. ChatGPT 高智能协同：应当是“扩展思路 + 反证 + 决策”，不是流程装饰

用户反复要求：当问题复杂、不确定、多方案、卡在局部最优、需要广泛调研/新思路/独立讨论时，使用项目中的高智能 ChatGPT Chat；关键问题可开多个独立聊天，最高实际可用推理强度，并排除明显降级/路由异常结果。

正确协作拓扑：

- Codex：唯一 active checkout writer，负责代码、测试、SQLite-affecting operation、部署、重启和最终事实核验；
- Lead ChatGPT：目标守护、广泛研究、策略/架构/统计/交易经济性推理、反证、替代路径和 reviewer 综合；
- Reviewer：只在 material gate 开启，角色必须互补，默认只读；
- 双方采用事件驱动低延迟同步：决策点、重大新证据、自然样本、因果假设变化、部署/重启门立即通信；普通编辑不 ping；
- Direct channel 失败才落 durable mailbox；禁止为“发消息”启动第二个 Codex writer。

## 5. 信息发现：用户始终强调“早”，且信息-first 与 Token-first 都要有

恢复出的稳定需求包括：

- 新闻、舆论、热点、名人/KOL/机构动态可能先于价格和链上动量；不能要求所有候选先达到 momentum 门才调查；
- 新 Meme Token 的详情、官网、X/社交链接、provider metadata 可作为调查入口，但项目方自述/推广/identity 不是决策证据；
- DexScreener/Pump/Gecko/公开新池/新币入口都可帮助发现 Token，再向外溯源其叙事、社区、名人和独立报道；
- 用户明确提出研究 OKX/Pump 新币页面、smart-money/wallet 行为及其他自己没想到的路径；应客观研究，而不是把某一种入口硬编码为唯一答案；
- 用户反复指出每天存在不少大幅上涨的新 Pump/Solana Token，因此主问题不能被解释成“没有机会”；应持续测量系统漏掉了哪里；
- 用户反复问 Paper 为什么交易极少，要求判断是合理严格还是采集/调度/映射/证据/报价/执行链路存在阻隔。

这些需求与当前 P0 “及时信息/精确原帖 → 独立事实 → Token 集合 → exact CA → 可执行 Decision”一致，不应被当作历史杂项。

## 6. 浏览器/X 采集时效：恢复后的新 P0 候选

用户早期要求社交/X 更高频，随后又纠正“不用这么高频”；这不是简单矛盾。结合后续“学习哪些来源值得关注，而不是全面关注”的要求，正确解释是：**价值/事件自适应频率，而不是所有账号统一极高频。**

当前代码核验（2026-09-02）：

- `background.js` 的 queue flush、账号轮换和 priority-post 轮换均为 30 秒 alarm；watchlist sync 2 分钟；
- `content.js` DOM 变化会在约 750ms 后触发 scan，heartbeat 30 秒；60 秒 `setInterval(scan)` 只是兜底全页扫描；
- live settings 有 100 个 enabled watch account：4 critical、96 normal；
- 单个账号轮换 tick 每 30 秒只导航一个账号，lane 为 `critical → normal → critical`；
- 因此在理想无延迟情况下，4 个 critical 每个约 3 分钟一次；96 个 normal 完整轮回约 144 分钟；
- 这比“60 秒兜底 scan”更可能构成 fresh-post 捕获延迟；修改兜底 scan 本身不会解决 profile coverage；
- 当前 options UI 仍写“critical 与普通账号各每分钟轮换一个”，与现实现不完全一致，应视为显示语义陈旧，不是业务主问题。

当前推荐方向：

1. 不先改 60 秒兜底 scan；DOM 变更已经有亚秒级触发。
2. 把“账号覆盖延迟”作为候选 P0，直接测 `account visit → fresh post observed` 延迟与 missed exact post 分母。
3. 使用**分层、自适应调度**：exact priority-post / fresh high-impact事件进入短时 surge；critical KOL 保持短回访；普通 96 个账号根据前向 source utility、priority 和最近命中动态采样，而不是等权 144 分钟轮回。
4. 任何加速不得把 identity/promotion 升级为交易证据，也不得增加生产 Agent 并发或放宽 Decision/Strategy 风险门。
5. Chrome MV3 后台调度应继续以 alarms/event-driven 机制为主，不能依赖 service-worker `setInterval` 获得可靠高频。正式参数修改前用真实页面负载、X 可达性、内存、观察新鲜度做一个最小 A/B 或短窗口验证。

## 7. Paper / 执行经济学：用户关心的是“真实近似”，不是漂亮回测

恢复出的持续要求：

- Paper 是必要阶段，必须持续运行并用真实前向数据改进；
- 禁止未来数据/未来函数；
- 买入/卖出要考虑不利滑点、实际或近似实际手续费、真实 route/sellability、资金占用；
- 研究买多少、买几次、卖几次、分批止盈、runner、长期持有与不同叙事/人物/社区强度的关系；
- 退出规则和仓位管理应由前向经济结果学习，而不是事后挑赢家；
- 历史“只接私钥即可无缝实盘”的表述已被当前安全契约 supersede：Live 仍需单独 broker/小额链上验收，当前保持锁定。

## 8. 持续学习，而不是一次性静态规则

用户明确表示：应学习哪些信息、平台、名人/KOL、新闻、热点、链上结构真正值得注意，而不是永久全面盯所有来源。对应工程含义：

- source/account/topic/platform 必须有前向 exposure/zero-yield/failure/latency/outcome 分母；
- 关注频率可以随前向价值自适应，但不能用未来赢家训练；
- “买入后/高价值信息后是否临时提高关注”是值得研究的 challenger，不应默认每个 Token 启一个常驻 Agent；
- 低价值来源逐步降频，高价值/正在爆发的来源短时升频，同时保留探索槽，防止学习锁死。

## 9. UI、存储与操作要求：保留，但不应抢 P0

仍有效：

- 中英文、动态更新、事件来源可点击、来源/人物/平台/影响信息清晰；
- 关键可调参数有设置入口；
- Paper 账户/PNL/曲线和真实状态要可见；
- 所有 memeTrader 项目持久数据、日志、上下文、测试产物、Agent 工作空间保存在 E 盘项目内；
- Codex 能自行完成的操作不要反复要求用户介入；确实需要登录、验证码或物理操作时再请求用户；
- Git push 当前无必要。

但用户后来明确把 UI 深化后置，因此除非 UI 正在误导/缺数据/阻碍运行，它不得抢占信息→证据→Paper 主线。

## 10. 被后续约束修正或 supersede 的早期要求

- “Agent 越多越好/更高频” → 修正为：按价值/复杂度/瓶颈自适应，成本与信息增益并重；生产并发当前最多 2，开发 Agent 也需分级治理。
- “取消/无限生产 Agent 预算” → 修正为：预算不是当前主瓶颈；保持高但有限，只有真实 limiter 阻断高价值任务时再提高。
- “所有账号都全面高频” → 修正为：学习哪些来源值得关注，critical/surge 高频，普通池探索+价值加权。
- “直接 Telegram 自动正文摄取” → 当前受平台条款边界约束，保留合法替代路径，不直接抓取受限内容。
- “加私钥后直接实盘” → 当前 Live 锁和 broker 验收规则优先；历史暴露的任何测试密钥不得复用或传播。
- “持续优化 UI” → 后续明确后置，除非影响真实性或操作能力。

## 11. 当前最值得重新提升的遗漏/弱执行项

按当前事实与用户历史意图，以下不是因为“历史上提过”而晋级，而是因为它们与当前 P0 有直接因果联系：

1. **浏览器账号覆盖延迟 / exact-post capture latency**：当前 4 critical + 96 normal 的轮换周期可能直接解释大量 priority exact URL 未在早期形成 browser Observation。建议 `PROMOTE_NOW` 候选，但先由 Codex读取实时采集分母验证。
2. **开发侧 Agent 成本与 review/audit 过度**：目标 thread 曾启动 91 个不同 subagent path，48 个 path 名含 audit/review/recheck；应立即作为执行效率约束，不需要新增业务实验。
3. **Open-source-first implementation rule**：用户多次明确且当前 AGENTS 只间接覆盖，应成为 Codex 工具/实现问题的默认动作顺序。
4. **自动防遗忘注入**：目标 thread 有 99 次 context compaction；仅靠文件“存在”不足。应在 Codex session/resume/compact/prompt 边界自动重新注入 E 盘极小北极星状态，但不得让这项基础设施继续挤占 P0。

## 12. 本文件的停止条件

需求恢复不是新一轮无限审计。本轮结构化主线程 139 条 userMessage 已完成一次全量时序扫描。后续只在出现新的用户明确要求、发现未纳入的历史附件、或 authority conflict 时做增量更新；不要重复全量考古来获得“更多信心”。
