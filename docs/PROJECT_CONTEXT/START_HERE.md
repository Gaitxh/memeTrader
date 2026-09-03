# START HERE — memeTrader 项目上下文

最后更新：2026-09-02（Asia/Shanghai）

这个目录是给后续开发者和 Agent 使用的**版本控制内项目记忆**。它保存产品意图、架构、安全边界、已实现状态、未完成事项和运行手册，但绝不保存密码、Cookie、Session、验证码、私钥、钱包材料、Bridge Token、公开入口口令、数据库内容或日志。

## 权威顺序

发生冲突时先区分“用户意图”与“当前事实”。用户意图以 GXH ChatGPT 项目聊天和指定 Codex thread/history 中最新明确指令为共同权威来源；显式 supersession、较晚/更具体指令优先，仍无法消解时保留冲突。执行与事实按以下顺序判断：

1. 最新明确用户指令与安全约束；
2. 根目录 [AGENTS.md](../../AGENTS.md) 的冻结安全和工程规则；
3. [CURRENT_OBJECTIVE_AND_PLAN.md](CURRENT_OBJECTIVE_AND_PLAN.md) 与 [REQUIREMENT_LEDGER.md](REQUIREMENT_LEDGER.md) 的当前 active scope / supersession；
4. 当前工作区代码、测试和被 Git 忽略的本机 `config.json`；
5. `config.json -> database` 指向的当前 SQLite、进程和真实运行状态；
6. `CHATGPT_CODEX_SYNC_STATE.json` / Lead state / Common Space 只负责路由、连续性和协作细节，不能覆盖更高层 authority；
7. 本目录日期快照、旧版验收文档和聊天摘要。

不要用本目录覆盖运行事实。本目录解释“为什么”和“当前应当怎样继续”，运行状态仍应通过 Web `/api/health`、计划任务、当前配置和 SQLite 只读查询确认。

其中 `AGENTS.md -> Frozen execution contract` 是本聊天反复确认的长期执行契约：后续不得用容易完成的 UI、文档、审计或重复验证，替代对信息覆盖、Event↔Token、候选调度、Paper 执行和前向学习中最高影响真实断点的处理。

## 必读地图

- [REQUIREMENT_LEDGER.md](REQUIREMENT_LEDGER.md)：长期逐项需求台账；区分 DONE、PARTIAL、CONTINUOUS、BLOCKED、SUPERSEDED，保存当前证据、断点和下一步。
- [CURRENT_OBJECTIVE_AND_PLAN.md](CURRENT_OBJECTIVE_AND_PLAN.md)：当前最终目的、真实主断点、冻结不变量、P0–P3 优先级和长期完成判定；执行中先读此文件避免方向漂移。
- [../../CHATGPT_CONTACT.md](../../CHATGPT_CONTACT.md)：Codex 主动唤醒、联系和续接主协调 ChatGPT 的最小联系卡；端点以快速同步指针为准。
- [CHATGPT_CODEX_SYNC_STATE.json](CHATGPT_CODEX_SYNC_STATE.json)：当前 active cycle、`attention_required`、open-group/alert 路由的快速可变指针；每次 substantial cycle 与上下文恢复先读。
- [CHATGPT_LEAD_STATE.json](CHATGPT_LEAD_STATE.json)：Lead ChatGPT 的 E 盘耐久北极星、协作拓扑、已恢复要求与最新关键诊断。
- [CHATGPT_CURRENT_CONVERSATION_REQUIREMENTS_2026-09-02.md](CHATGPT_CURRENT_CONVERSATION_REQUIREMENTS_2026-09-02.md)：本次 GXH ChatGPT 聊天新增/强化的权威用户意图；与 Codex 历史互补。
- [CHATGPT_RECOVERED_USER_REQUIREMENTS_2026-09-02.md](CHATGPT_RECOVERED_USER_REQUIREMENTS_2026-09-02.md)：从指定 Codex thread 的 139 条 userMessage 恢复并脱敏后的长期需求谱系。
- [CHATGPT_CODEX_EXECUTION_EFFICIENCY_POLICY_2026-09-02.md](CHATGPT_CODEX_EXECUTION_EFFICIENCY_POLICY_2026-09-02.md)：Codex 开发子 Agent 成本、review/test 停止规则、open-source-first 与任务复杂度路由。
- [CHATGPT_LEAD_ROLLOVER_STATE.json](CHATGPT_LEAD_ROLLOVER_STATE.json)：Lead chat 达到上下文上限/失效时的新 chat boot read set、单 coordinator rebind 和 checkpoint。
- [COMMON_SPACE/README.md](COMMON_SPACE/README.md)：ChatGPT ↔ Codex 共同研究区；详细想法/反证/方案放 side-owned notes，实时消息只发 alert pointer，不成为第二套执行计划。
- [CHATGPT_CODEX_BIDIRECTIONAL_CHANNEL.md](CHATGPT_CODEX_BIDIRECTIONAL_CHANNEL.md)：双向收发、关联 ID、直接回读、故障转移、多聊天与历史建议治理的详细运行手册。
- [PRODUCT_AND_REQUIREMENTS.md](PRODUCT_AND_REQUIREMENTS.md)：产品目的、非目标、完整需求和界面语义。
- [REQUIREMENTS_ACCEPTANCE_2026-08-30.md](REQUIREMENTS_ACCEPTANCE_2026-08-30.md)：本轮对整段需求的逐项验收，区分已实现、部分实现、未实现、明确跳过和人工步骤。
- [ARCHITECTURE_AND_DATAFLOW.md](ARCHITECTURE_AND_DATAFLOW.md)：组件、数据流、关键代码路径、SQLite 表和实时更新方式。
- [SAFETY_AND_INVARIANTS.md](SAFETY_AND_INVARIANTS.md)：Paper/Live、时间门、账号、Agent、钱包和公开 URL 的硬边界。
- [../SOLANA_HOLDER_BREADTH_SHADOW_CN.md](../SOLANA_HOLDER_BREADTH_SHADOW_CN.md)：Solana holder 聚合数据的低频前向可用性实验、误读边界和升级门。
- [SNAPSHOT_2026-09-01.md](SNAPSHOT_2026-09-01.md)：最新 P0-A/P0-B 前向证据、Paper/非收益边界和未成熟自然样本断点。
- [CHATGPT_REVIEW_HANDOFF_KOL_LOW_ATTENTION_PROBE_2026-09-02.md](CHATGPT_REVIEW_HANDOFF_KOL_LOW_ATTENTION_PROBE_2026-09-02.md)：三路最高强度 ChatGPT 独立复核已完成；原始“ticker/叙事词→Dex 候选→事后涨幅”方案为 `NO-GO`，修订后的前向 addressability-first 探针为 `MODIFIED_GO`，统一使用 `@笔记本mcp20260902`。
- [SNAPSHOT_2026-08-31.md](SNAPSHOT_2026-08-31.md)：上一份全量需求复核、首笔 Paper 闭环审计、学习缺口和推进历史。
- [SNAPSHOT_2026-08-30.md](SNAPSHOT_2026-08-30.md)：上一阶段实现、运行和未完成状态。
- [OPERATIONS_AND_VALIDATION.md](OPERATIONS_AND_VALIDATION.md)：Windows 常驻、Web、浏览器采集、验证与发布检查。
- [UPDATE_PROTOCOL.md](UPDATE_PROTOCOL.md)：以后怎样维护这份项目记忆。
- [CONSTRAINT_SUBSTITUTION_MATRIX.md](CONSTRAINT_SUBSTITUTION_MATRIX.md)：当主路径受平台、权限、数据或安全边界限制时，怎样用合法替代链继续实现真实目的，并明确证据差距。
- [../DEXSCREENER_PROVENANCE_AND_SOURCE_LEARNING_CN.md](../DEXSCREENER_PROVENANCE_AND_SOURCE_LEARNING_CN.md)：旧 model1/model3 修正、Dex 附带链接角色、Token→来源溯源和只影响观察轮换的前向 Paper 学习。
- [../OKX_MEME_PUMP_AND_SMART_MONEY_ASSESSMENT_CN.md](../OKX_MEME_PUMP_AND_SMART_MONEY_ASSESSMENT_CN.md)：OKX Meme Pump 的签名/Premium 边界、与现有免费来源的差异，以及聪明钱只能进入前向 shadow 研究的安全结论。
- [../PAPER_FORWARD_EXECUTION_CN.md](../PAPER_FORWARD_EXECUTION_CN.md)：Paper 禁止未来数据/回填、追加式账户曲线、模拟执行成本和未来 Live 的独立发布门。
- [../PAPER_STRATEGY_FORWARD_LEARNING_CN.md](../PAPER_STRATEGY_FORWARD_LEARNING_CN.md)：热度/人物/社区/链上条件与入场、分批止盈、runner 的前向 cohort 和预注册 Paper 对照实验边界。
- [../TOKEN_CONTEXT_FORWARD_LEARNING_CN.md](../TOKEN_CONTEXT_FORWARD_LEARNING_CN.md)：Token Context 五轨 assessment 的冻结标签、15/60/240 分钟无回填结果和描述性成熟门。
- [../INFORMATION_FIRST_X_REVIEW_20260831_CN.md](../INFORMATION_FIRST_X_REVIEW_20260831_CN.md)：用户补充的 X 账号、历史案例与“信息先于价格”假设的事实审阅、已修正边界和未实现研究项。
- [../INFORMATION_FIRST_SHADOW_CN.md](../INFORMATION_FIRST_SHADOW_CN.md)：独立 information-first 前向 cohort 的冻结时点、缺失分母、描述性市场层和不影响交易的边界。
- [../EVENT_CLAIM_RELATIONS_CN.md](../EVENT_CLAIM_RELATIONS_CN.md)：前向来源版本之间的 supersede/correct/retract 目标关系、唯一 URL 解析、不回填和 `affects=none` 边界。
- [../AGENT_FACT_VERIFIER_CN.md](../AGENT_FACT_VERIFIER_CN.md)：Trend/Token Context 的第二阶段独立正文核验、模型与 Token 记账、无历史回填及 `affects=none` 边界。

## 一句话产品定义

memeTrader 是一个运行在个人 Windows 电脑上的、仅前向证据驱动的 meme-token 研究与 Paper 交易系统。它的商业目的不是生成更多报告或更复杂的界面，而是在控制风险和执行成本后，提高真实前向赚钱概率：更早发现尚未充分定价的叙事机会，正确关联可交易 Token，真实模拟买卖，并从固定时点结果持续学习。系统把新闻/社交事件与新 Token/新池双向关联，通过确定性评分、安全门和 Paper 风控做出 `WAIT / REJECT / CANDIDATE` 决策，并在深色双语 Web 控制台中实时、可审计地展示全过程；任何收益都必须由前向 Paper/实际成交证据证明，不能承诺或用回填结果代替。

## 当前不可突破的状态

- 常驻自动策略只能为 `paper` 或 `shadow`；当前为 Paper。
- `live.enabled=false`，网页没有 Mainnet Live 开关。
- Solana Devnet 钱包页只用于本机人工真链测试，不连接常驻策略。
- 自主 Agent 最多同时 2 个；六个界面角色是职责视图，不是六个常驻进程。
- Trend Scout 与 Token Context 的 Agent 网页结论只是 `identity/context-only` 待核验上下文；URL/时间/域名可达不等于事实已独立验证。
- `agent-fact-verification/v1` 会用第二个独立 Codex 上下文核验新候选来源正文；不同域名支持仍只是下界，结果固定 `decision_eligible=false / affects=none`，不进入策略或 Paper。
- `source-item-revision/v1` 只从注册时刻前向记录来源条目 baseline/edit/明确删除/撤回/纠正/恢复，固定 `affects=none`；缺项、404 和 DOM 消失绝不是删除证据。
- `event-claim-relation/v1` 只在本次真实抓取新增来源 revision 的同一事务内追加目标关系；跨条目只允许精确安全 URL 唯一匹配，未命中、歧义和未来/陈旧时间均不补链，固定 `affects=none`。
- `observation-provenance/v1` 只从注册时刻前向记录 `Origin → Transport → Local capture`；RSS/Agent/域名推断与 singleton 都不等于独立来源，内部 provenance root 不通过 API 暴露。
- `WAIT` 就是没有信号；空结果、零交易和陈旧状态必须如实显示。
- 所有可用于决策的证据必须满足 `observed_at <= decision_time` 且 `ingested_at <= decision_time`。
- 登录凭据由本机浏览器和用户持有，项目与 Agent 不读取、导出或保存。

## 开始任何后续工作前

先执行只读检查：

```powershell
Set-Location E:\memeTrader
Get-Content -Raw .\AGENTS.md
git status --short --branch
git log -1 --oneline
.\.venv\Scripts\python.exe -m memetrader status --config config.json --limit 10
```

随后阅读本目录最新快照。若工作树已有改动，先确认归属并保留；不要覆盖其他 Agent 或用户的修改。
