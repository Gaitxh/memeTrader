# START HERE — memeTrader 项目上下文

最后更新：2026-08-31（Asia/Shanghai）

这个目录是给后续开发者和 Agent 使用的**版本控制内项目记忆**。它保存产品意图、架构、安全边界、已实现状态、未完成事项和运行手册，但绝不保存密码、Cookie、Session、验证码、私钥、钱包材料、Bridge Token、公开入口口令、数据库内容或日志。

## 权威顺序

发生冲突时，按以下顺序判断：

1. 根目录 [AGENTS.md](../../AGENTS.md) 的安全和工程规则；
2. 当前工作区代码、测试和被 Git 忽略的本机 `config.json`；
3. `config.json -> database` 指向的当前 SQLite；
4. 本目录中最新的日期快照；
5. 旧版验收文档和聊天摘要。

不要用本目录覆盖运行事实。本目录解释“为什么”和“当前应当怎样继续”，运行状态仍应通过 Web `/api/health`、计划任务、当前配置和 SQLite 只读查询确认。

## 必读地图

- [REQUIREMENT_LEDGER.md](REQUIREMENT_LEDGER.md)：长期逐项需求台账；区分 DONE、PARTIAL、CONTINUOUS、BLOCKED、SUPERSEDED，保存当前证据、断点和下一步。
- [PRODUCT_AND_REQUIREMENTS.md](PRODUCT_AND_REQUIREMENTS.md)：产品目的、非目标、完整需求和界面语义。
- [REQUIREMENTS_ACCEPTANCE_2026-08-30.md](REQUIREMENTS_ACCEPTANCE_2026-08-30.md)：本轮对整段需求的逐项验收，区分已实现、部分实现、未实现、明确跳过和人工步骤。
- [ARCHITECTURE_AND_DATAFLOW.md](ARCHITECTURE_AND_DATAFLOW.md)：组件、数据流、关键代码路径、SQLite 表和实时更新方式。
- [SAFETY_AND_INVARIANTS.md](SAFETY_AND_INVARIANTS.md)：Paper/Live、时间门、账号、Agent、钱包和公开 URL 的硬边界。
- [SNAPSHOT_2026-08-31.md](SNAPSHOT_2026-08-31.md)：最新的全量需求复核、首笔 Paper 闭环审计、学习缺口和当前推进状态。
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

## 一句话产品定义

memeTrader 是一个运行在个人 Windows 电脑上的、仅前向证据驱动的 meme-token 研究与 Paper 交易系统：它把新闻/社交事件与新 Token/新池双向关联，通过确定性评分、安全门和 Paper 风控做出 `WAIT / REJECT / CANDIDATE` 决策，并在深色双语 Web 控制台中实时、可审计地展示全过程。

## 当前不可突破的状态

- 常驻自动策略只能为 `paper` 或 `shadow`；当前为 Paper。
- `live.enabled=false`，网页没有 Mainnet Live 开关。
- Solana Devnet 钱包页只用于本机人工真链测试，不连接常驻策略。
- 自主 Agent 最多同时 2 个；六个界面角色是职责视图，不是六个常驻进程。
- Trend Scout 与 Token Context 的 Agent 网页结论只是 `identity/context-only` 待核验上下文；URL/时间/域名可达不等于事实已独立验证。
- `source-item-revision/v1` 只从注册时刻前向记录来源条目 baseline/edit/明确删除/撤回/纠正/恢复，固定 `affects=none`；缺项、404 和 DOM 消失绝不是删除证据。
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
