# ChatGPT ↔ Codex 执行效率、Agent 成本与停止规则 · 2026-09-02

状态：`PROPOSED / USER-INTENT-RECOVERED`

目的：减少局部最优、重复 review/audit、无收益防御和 agentic 浪费，把更多时间/预算留给真正改变 memeTrader 前向赚钱链路的工作。本规则不降低资金/未来数据/Live/实验污染等必要安全边界。

## 1. 每个工作单元先做 15 秒价值门

开始任何超过机械修改的任务前，只回答四件事：

1. `BOTTLENECK_CHANGED`：当前哪一个已观察到的端到端断点会被改变？
2. `EXPECTED_GAIN`：预期增加的是召回、时效、证据质量、exact binding、可执行性、成本后收益信息，还是运行可靠性？
3. `CHEAPEST_VALID_PATH`：不用 Agent / 用低档 Agent / 查成熟 OSS / 请求 Lead ChatGPT，哪条是最便宜且足够可靠的？
4. `STOP_WHEN`：什么最小可观察结果一出现就停止继续扩展？

若第 1 项回答不清：不抢当前 active cycle；记入候选即可。

## 2. 先复用，后自研

工具/实现问题默认顺序：

`当前代码/已有依赖 → 官方文档 → 成熟开源实现 → 上游 issue/discussion/社区经验 → 最小自研`

不是每个问题都要联网；但当问题明显是通用工程能力、平台接入、浏览器扩展、数据采集、调度、交易路由、开源基础设施时，应先查是否已有成熟路径。

外部方案筛选只看与当前目标有关的维度：活跃维护、许可、接口稳定性、平台合规、数据时效、资源成本、依赖复杂度、Windows/单机适配和失败模式。不要为了“调研全面”阅读几十个同质项目。

## 3. Codex 开发 Agent 分级路由

| Tier | 任务 | 默认执行者 | 推理/成本原则 | 并行原则 |
|---|---|---|---|---|
| T0 | grep/read/SQL/算数/格式/确定性脚本/已知测试 | Codex 本地工具 | 不启 Agent | 不并行 |
| T1 | 单文件/小范围机械修改、已知 API 用法 | 最低足够能力，low | 首次可完成就停 | 通常不并行 |
| T2 | 跨少量文件实现、局部 bug、有限设计选择 | 中档能力，medium | 只在局部不确定性真实存在时升级 | 仅独立 read-only 或隔离 worktree |
| T3 | 根因不明、架构、统计因果、交易经济、实验 estimand、重要 OSS 选型 | Lead ChatGPT 高强度推理 + Codex 核验 | 少而强，不用一堆低价值子 Agent | 可开互补研究角色，但一个 Lead 汇总 |
| T4 | 核心策略、资金/Live 边界、重大实验注册、发布可能污染前向分母 | 3 个不同职责的高强度 ChatGPT reviewer + Lead 综合 + Codex 验证 | 这是例外 gate，不是日常流程 | reviewers 只读；Codex 唯一 writer |

禁止：

- 为一个简单问题开 3 个 reviewer；
- 用多个 Codex 子 Agent 替代用户要求的高智能 ChatGPT 独立判断；
- 因“额度充足”而主动扩大 Agent 数；
- 一个 Agent 已经给出足够可验证答案后，再开同质 Agent 只为增加信心；
- 同一 dirty checkout 多 writer。

## 4. review / audit / test 预算

### 必做

- 会污染前向分母、使用未来数据、错误交易/资金风险、Live 边界、不可变 registration、严重并发/SQLite 数据损坏风险；
- 与当前 acceptance criterion 直接相关的最窄测试；
- 发布/重启边界需要的相关回归与健康检查。

### 默认不做

- 已经被定向测试证明、代码/数据/假设未变化后的再次等价检查；
- 为一个非关键局部修改做全量仓库审查；
- 给每个新 shadow 建新的审计层、review 文档、第二套 provenance；
- 因为“可能有理论 edge case”而无限加 guard；
- 新 UI/文档完成后再做多轮“总审计”；
- 仅为了让结果更漂亮而增加实验、样本筛选或重复 reviewer。

### 两轮规则

同一失败如果已经做了两次高度相似的修复/复核仍未解决：停止继续局部打补丁，重新问“根因假设是不是错了？”。优先换因果假设、数据入口、调度方式或成熟工具，而不是第三层 guard。

## 5. 信息增益 / EV 优先排序

同时存在多个任务时，按以下近似排序，而不是按“最容易完成”排序：

`Priority Score ≈ (expected forward EV or information gain × probability of changing a decision) / (engineering time + agent cost + runtime risk + displacement cost)`

不要求精确算数；目的是强迫比较边际价值。

通常优先：

- 明确阻断新鲜信息捕获、exact CA、可执行报价或 Paper 的真实断点；
- 可以在短时间内产生严格前向判别信息的实验；
- 明显减少高成本 zero-yield Agent 重复调用的结构性修复；
- 能证明当前策略到底为什么“不交易/漏交易”的归因。

通常后置：

- 纯 UI 美化；
- 仅增加可观测字段但不改变判断的 provenance；
- 已有两个等价 guard 后的第三个 guard；
- 大规模历史 retrospective winner 分析；
- 没有明确晋级/停止门的 shadow 实验。

## 6. ChatGPT 与 Codex 的低延迟协作

默认是事件驱动，不是持续心跳：

- Codex 在以下事件立即联系 Lead：需要改变 active causal hypothesis；重大工具/OSS/架构选型；关键自然样本改变解释；部署/重启门；连续两轮失败；发现用户 frozen rule 与当前实现冲突。
- Lead 可以主动向 Codex发送：方向纠偏、替代方案、关键研究发现、明确 release blocker、一个新 causal hypothesis。
- 普通 edits/tests 不同步；等稳定 checkpoint 一次性 delta。
- 消息只发差异和 artifact pointer，不复制日志/diff/聊天历史。
- direct route 失败才使用 E 盘 durable mailbox；不因通信启动第二个 writer。

## 7. 自动防遗忘所需的最小上下文

每次 Codex startup/resume/context compact 后，以及每个新的用户 prompt 进入当前项目时，至少重新获得以下极小上下文：

- North Star：真实前向、可执行、扣成本、风险调整盈利；
- Active cycle：从 `CHATGPT_CODEX_SYNC_STATE.json` 实时读取；
- Drift gate：新任务改变哪个当前盈利链路瓶颈？
- Safety：no future data / no winner backfill / Live locked / one writer；
- Efficiency：no unnecessary defense/review; targeted validation; open-source-first；
- Model routing：简单任务低成本，复杂/高风险问题升级 Lead ChatGPT；
- E 盘 authority pointers。

不要每轮注入整个 Requirement Ledger；那会重新制造上下文膨胀。

## 8. 用户动作原则

Codex/ChatGPT 能自行通过已授权工具安全完成的操作，不要求用户代做。只有登录/验证码/显式许可/物理浏览器操作/不可自动化步骤确实需要用户时，才请求一个最小动作。

## 9. 当前可观测的效率警报

从目标 Codex thread 的结构化 history：

- 112 turns；
- 99 context compactions；
- 91 次不同 subagent path 启动；
- 至少 48 个 path 名称直接含 audit/review/recheck。

这些指标不能单独证明浪费金额，但足以触发当前规则：**未来不再默认通过增加 reviewer/subagent 解决不确定性。先看真实瓶颈、信息增益和最便宜有效路径。**

## 10. 完成/停止条件

一个局部工作单元达到以下条件即停止：

`named bottleneck changed OR disproved + narrow validation passed + forward observation path exists`

然后回到 active cycle。不要自动追加 cleanup、extra audit、extra docs、full-suite、第三意见或旁支优化。

本效率规则本身也受同样约束：落地自动上下文注入并验证一次后即停止优化“协作系统”，除非它再次实际失效。项目的重点仍是 memeTrader 的盈利链路。
