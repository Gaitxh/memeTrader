# 当前 GXH ChatGPT 聊天新增需求与意图 · 2026-09-02

状态：`AUTHORITATIVE USER-INTENT SOURCE / COMPLEMENTS CODEX HISTORY`

本文件保存本次 ChatGPT 项目聊天中用户新增或再次强化的项目级要求。它与指定 Codex thread/history 中恢复的用户需求互补，二者都属于用户意图权威来源；任何一方都不能因为“更方便读取”而被忽略。

冲突处理：最新明确指令、明确 supersession、更具体约束优先于较旧/较一般表达；如果仍无法判断，必须同时保留并记录冲突，不能静默选择自己更喜欢的一条。当前实现/运行事实仍以 E 盘当前代码、r6 SQLite、测试、进程和冻结定义为准。

## 1. 最终目标与角色分工

- 最终目标只有一个：让 memeTrader 系统能够在真实前向、可执行、扣成本和风险调整意义上更有可能持续赚钱；“挣钱”是业务表达，工程上不能被交易数、UI、Agent 数、历史赢家或 raw backtest return 取代。
- Codex 的执行、代码、测试、本地运行能力较强，但容易陷入局部、遗忘长期要求、偏离目的，并可能在分析/研究/调研方面不够强。
- Lead ChatGPT 应成为更强的目标守护、研究、推理、因果/统计、交易经济、架构分析、反证、新思路与方案综合层；Codex 保持 active checkout 的主要执行/集成职责。
- 双方不是单向“ChatGPT 给建议 → Codex 做”，而应能够互相主动唤醒、发消息、讨论、研究和纠偏。
- 可同时使用多个 ChatGPT chat，但数量不是越多越好。应按任务性质决定：一个 Lead 负责统一目标和综合；少量 reviewer 只在真正需要独立高强度意见的 material gate 使用，避免多头指挥和重复花费。

## 2. 防遗忘、防跑偏必须成为机制，而不是提醒

用户明确观察到 Codex 经常遗忘、做着做着偏离方向、目标和目的。项目已经存在大量规则和计划文件，但“写过”不等于“执行时持续可见”。

因此：

- Codex 每个重要工作单元必须先把任务映射到当前盈利链路瓶颈；不能回答“改变哪一段”时，不得自动抢占 active cycle。
- 长上下文、compaction、新 prompt、新 chat 后必须从 E 盘耐久状态恢复 North Star、active cycle、冻结规则和当前下一步。
- ChatGPT 自身也有聊天长度上限，因此 Lead ChatGPT 必须可换代；新 Lead 通过 E 盘强制 boot read set 恢复，而不是依赖旧聊天总结的完整性。
- 旧 Lead → 新 Lead 只能有一个完成校验后生效的 coordinator rebind；禁止两个 Lead 同时向 Codex下 implementation-facing 指令。

## 3. E 盘是项目跨聊天、跨模型的耐久共同记忆

用户明确要求：Lead ChatGPT 的项目相关信息也保存到 `E:\memeTrader`。

保存范围包括：

- 目标判断；
- 关键事实及证据指针；
- 研究结论；
- 假设与反证；
- 方案比较；
- 未解决问题；
- 给 Codex 的重要建议；
- 双方同步状态；
- 当前/历史用户需求恢复；
- Lead rollover checkpoint。

不保存：私有 chain-of-thought、历史聊天中的 secret/钱包材料/凭据、无复用价值的临时草稿。

## 4. Codex 历史与 ChatGPT 聊天都属于权威用户意图

- 指定 Codex thread `01a0514b-bbb5-7400-baf9-d9feb4dc603d` 的完整结构化 history 在本机仍存在，已经确认可恢复。
- 用户在 Codex 中长期提出了大量有价值的需求、建议、规则和纠正，其中有些被实现，有些只被口头 ACK，有些执行中偏离或遗忘。
- 这些历史要求不能被降级成“参考材料”；它们与本 ChatGPT 项目聊天中的明确要求互补。
- 本聊天中的新增要求也必须被耐久保存，不能等到聊天上限才临时总结。

## 5. 全面回顾不是无限审计，而是建立一次可持续的需求谱系

用户多次要求对 Codex 历史和本 ChatGPT 聊天做全面、详细、深入的回顾、理解和明确。

正确结果不是不断重读聊天，而是形成：

`原始要求 → 后续修正/补充 → 是否 supersede → 当前真实目的 → 当前实现状态 → 未完成/偏离 → 下一合理动作`

并按以下类别管理：

- `FROZEN_RULE`
- `LONG_TERM_OBJECTIVE`
- `ACTIVE_PLAN`
- `PROMOTE_NOW_CANDIDATE`
- `PRESERVE_CANDIDATE`
- `SUPERSEDED/SKIP`
- `CONFLICT_NEEDS_RESOLUTION`

完整回顾完成后只做增量维护，避免“为了更全面”再次消耗大量时间。

## 6. Agentic 成本与模型/推理路由

用户明确要求 Codex 节省 agentic 花费：

- 不同复杂度的开发任务使用不同智能程度和不同推理强度；
- 简单、确定性的工作优先本地工具或最低足够模型；
- 真正复杂、统计/因果、架构、交易经济、实验设计、卡局部最优时升级 Lead ChatGPT / 高智能模型；
- 高强度 reviewer 只用于关键 gate；
- 目标函数是“足够高的完成度、准确性、有效性、速度 + 尽可能低的边际 agentic 成本”，不是一味省，也不是一味用最高档。

生产 memeTrader Agent 与 Codex 开发过程子 Agent 必须分开治理。

## 7. 减少无收益的防御、审核、复核和实验

用户在 Codex 历史和本聊天中再次强调：项目推进过慢，原因之一可能是大量不必要的防御性、审核性、复核性行为、实验和验证。

因此：

- review/test/audit 必须绑定真实观察故障、未来数据/资金风险、前向分母污染、明确 acceptance 或不可逆发布门；
- 通过最窄必要验证后停止；
- 不因“再放心一点”重复同质 reviewer；
- 两轮类似补丁仍失败时，优先重新检查因果假设或更换实现路径；
- 不得用 review/audit 数量作为进展。

## 8. 工具/实现问题优先调查官方与成熟开源社区

用户在 Codex 中反复强调，并在本聊天再次明确：遇到工具或实现问题时，应先调查开源社区、官方文档、成熟项目、上游 issue/discussion 和真实经验，看是否已经有人解决。

执行含义：

- 不必要从零造轮子；
- 直接路径不可用时，优先寻找合法合规的替代/曲线实现；
- 外部工具只作为候选，最终仍需按当前架构、维护性、许可、平台条款、成本、Windows/单机适配和前向价值判断；
- 不为“调研完整”阅读大量同质项目。

## 9. 浏览器/X 信息捕获需要更快，但应优化真实瓶颈

用户提出浏览器插件一分钟是否太慢，希望更快获得信息。

当前只读核验发现：

- priority post 与账号轮换 alarm 已为约 30 秒；
- DOM 变化约 750ms 后触发 scan；
- heartbeat 30 秒；
- `setInterval(scan, 60000)` 是兜底全页 scan；
- 当前 100 个 enabled watch account，4 critical / 96 normal；
- 单旋转 tab + `critical → normal → critical` 的理想覆盖意味着 critical 每个约 3 分钟回访一次，而 96 normal 完整轮回约 144 分钟。

因此用户“更快”的真实问题更可能是**profile/account coverage latency**，而不是单纯把 60 秒 fallback scan 改成 15 秒。

推荐进一步验证并考虑：

- exact priority post 短时 surge；
- critical KOL 高频回访；
- fresh high-impact episode 临时升频；
- normal 大池按 source utility/priority/最近命中价值加权，同时保留 exploration；
- 不因为采集加速就放宽 identity/promotion→Decision 证据门。

## 10. Chat ↔ Local ↔ Codex Common Space

用户提出建立一个三方共同空间：ChatGPT 和 Codex 都可随时浏览、编辑、补充详细内容；如果发现另一方当前做法有问题或有更好方法，可以立即提醒。

接受的设计原则：

- Common Space 放在 `E:\memeTrader`；
- 详细研究、假设、反证、方案、状态、待解问题放 Common Space；
- 实时消息只负责“敲门 + 指向具体 topic/finding”，避免反复复制大段上下文；
- 多读、多写，但不让两个 agent 频繁覆盖同一 JSON；
- ChatGPT 与 Codex 各自拥有 writer-owned 状态/notes，topic 级讨论分开记录，Lead 负责 synthesis；
- 重要最终决定仍进入现有 Objective/Requirement/Sync authority，不把 Common Space 变成第二套执行计划；
- Common Space 的存在不能导致新的流程官僚化或偏离 memeTrader P0。

## 11. 实时沟通的期望

“实时”定义为低延迟、事件驱动，而不是持续烧 token 的 heartbeat：

值得立即互相唤醒的事件包括：

- 发现对方当前方向可能偏离 North Star / active cycle；
- 新证据推翻当前因果假设；
- 找到明显更优的实现/开源路径；
- material architecture/experiment/trading-economics decision；
- 首个关键自然前向样本改变解释；
- deploy/restart/release gate；
- 连续两轮失败需要重新想方法；
- 用户新增/修改冻结规则。

普通 read/edit/test 不需要实时 ping。

## 12. 当前聊天新增需求的已落地状态

已落地：

- Lead durable state / journal；
- Codex 139 条用户消息的一次完整时序恢复与脱敏要求谱系；
- 开发侧 Agent 成本/效率/停止规则；
- Lead rollover state；
- 双向运行手册的 chat 换代机制；
- E 盘 project-context guard 脚本原型；
- 浏览器账号覆盖延迟的候选根因量化；
- 本文件，作为当前 ChatGPT 聊天新增权威用户意图的耐久记录。

后续核验中又发现一个更直接的防遗忘根因：指定 Codex thread 的 cwd 是 C 盘 ChatGPT-project mirror，而该 mirror 的生成 `AGENTS.md` 明确写着项目没有 custom instructions；它自动继承的是全局“最小动作”政策，而 `E:\memeTrader\AGENTS.md` 才包含冻结北极星和执行契约。由于 mirror 文件只读且可能被同步替换，不应把真实状态复制到 C 盘。

因此已新增一个极薄的全局 Codex `hooks.json` bootstrap，仅调用 E 盘 `scripts/codex_project_context_guard.cmd`；guard 对非 GXH/memeTrader cwd 空返回，对目标 cwd 在 `UserPromptSubmit` 以及 `SessionStart(resume/compact)` 注入 compact E:-resident context，并在 `attention_required=true` 时指向 pending alert。一个 read-only ephemeral probe 无 hook 配置/信任错误，但花费约 19k input tokens，因此不再重复模型 probe。当前 active Desktop session 是否热加载新 hook 等下一次自然 prompt/resume/compact 观察。

仍待落地/验证：

- Codex 在稳定 checkpoint 对上述新增规则、Common Space alert 和 mailbox 项的 ACK/采纳；
- 当前 active Desktop Codex 是否自然热加载新 hook；若不热加载，只在自然 restart/session boundary 生效，不为此强行中断当前工作；
- ChatGPT→Codex same-thread 低延迟 transport 的安全官方入口。当前 Desktop 内部有 `codex_app.send_message_to_thread`，但本 ChatGPT tool surface 未暴露；不要用第二 CLI/app-server 冒充，因为近期上游存在 active-writer 冲突且 `turn/start` 可意外 steer active turn；
- 用 live 前向分母确认 browser coverage latency 是否应 PROMOTE_NOW；
- 确保任何协作基础设施工作完成最小闭环后立即停止，不继续挤占交易主线。

## 13. 新聊天必须直接继承，避免重复解释

用户于 2026-09-03 明确要求：因为单个 ChatGPT 聊天存在长度上限，项目必须保证在 GXH coin 中打开新聊天后可以直接继承当前最新目标、需求、研究、策略架构、Codex 协作状态和执行指针；不要反复要求用户重述，也不要在每个新聊天重复强调此前已经固化的整套背景。

执行含义：

- E:\memeTrader 是跨聊天耐久来源；新增 `CHATGPT_CURRENT_HANDOFF_2026-09-03.md` 作为当前最小续接入口，并加入 rollover mandatory boot read set。
- 用户在新 GXH chat 中只输入 `继续` 应足以启动恢复：读取 handoff、`CHATGPT_CODEX_SYNC_STATE.json` 和必要的当前代码/SQLite事实后直接推进。
- 除非用户明确要求“回顾/总结”，新 Lead 不应先输出长篇历史复述；恢复动作应主要在内部/工具层完成，然后从当前最高价值未解决任务继续。
- 每轮 material 新结论、用户 supersession、执行交接和关键 blocker 必须增量写回 E:，而不是等聊天临近上限才总结。
