# ChatGPT 三路独立复核包：重点人物低注意力 Token 探针

状态：`DRAFT / REVIEW 1 OF 3`
目标版本：`kol-low-attention-dex-probe/v1`
本地项目：`E:\memeTrader`
本地访问插件：`@笔记本mcp20260902`

## 1. 最终目的与本次问题

memeTrader 的最终目的不是增加页面、Agent 或交易数量，而是提高新 Meme Token 的**样本外、扣除费用后的风险调整收益**。当前只运行 Paper，Live 必须保持锁定。

最新 24 小时 r6 前向账本显示：

- 48,718 个新 Token、260,927 个快照；
- 2,398 个 Observation、1,836 个 Event；
- 11,666 个 eligible Token Context trigger，仅 318 个 admitted；
- 312 个 Agent 终态中 `no_context=286`、独立来源不足 20；
- 反向查询覆盖 2,706 个 Token，真正 `reverse_news_matched=13`，约 0.48%；
- 可决策 Event↔Token relation Token 为 0；
- Decision 为 WAIT 797、REJECT 344、CANDIDATE 1；主 Paper 只有一笔 `$14.25` BUY；
- Agent 当日为 280/384 calls、20.36M/50M known tokens，没有当日预算阻塞。

因此当前首要断点不是新币供给或预算，而是：

`新鲜重点人物/机构信息 → 及时正文 → 独立事实确认 → Token 候选集合 → 精确 canonical/CA → 可决策证据`

本次只评审一个隔离观察实验：当重点人物/机构帖子本身足够新鲜、可信，但事件 attention 尚低、市场尚未明显异动时，是否应保存当时能找到的全部 Token 候选并做固定时点随访，以测量信息领先市场的真实分布。

## 2. 不可改变的约束

- 严禁未来数据、事后赢家选择、旧样本回填和后来证据倒灌。
- 只纳入 registration activation point 之后的自然 observation。
- Paper 与 Live 均不得由该探针触发；固定 `decision_eligible=0 / affects=none`。
- 不写 Event→Token 决策关系、Decision、Position 或 Trade。
- identity、promotion、项目自述、单一来源和人物身份本身不能成为交易证据。
- 不能把 Dex 搜索结果中流动性最高的池、同 ticker 或同名 Token 自动称为 canonical Token。
- 所有空结果、错误、歧义、晚到 baseline、缺失 target 都必须留在分母。
- 15/60/240 分钟目标锚定当时 `signal_available_at`，不能锚定后来查询完成时间。
- 不增加生产 Agent 并发，不降低证据门、canonical margin、安全门或冷却。
- 不读取或输出 config secret、钱包、私钥、浏览器 Cookie、私人聊天、数据库原始敏感内容。

## 3. 候选设计

### 3.1 注册时冻结

- 版本、注册时间、activation observation id；
- 精确启用账号，`priority >= 4`；
- 允许角色为 feature/confirmation；
- 最大来源年龄建议 10 分钟；
- 事件 attention 必须低于冻结阈值，候选初值 35；
- 每个 cohort 最多两个由当时 observation/event 生成的查询词；
- 每个查询最多请求 10 个 Dex 结果，候选集合最多保留 10 个唯一 Token；
- 允许链、grace、最大尝试次数与 `affects=none`。

注册定义一经写入不可修改；Runtime 重启后只读取已注册定义。

### 3.2 不可变账本

建议独立表，不复用要求既有 Decision 的 `information-first-shadow`：

1. `kol_low_attention_probe_registrations`
2. `kol_low_attention_probe_cohorts`
3. `kol_low_attention_probe_attempts`
4. `kol_low_attention_probe_candidates`
5. `kol_low_attention_probe_outcomes`

每个 cohort 冻结 observation、event、attention point、browser exposure、账号 priority、published/observed/ingested/recorded/signal-available 时间、attention、source age 和查询词。每个返回候选都保留，不选赢家；每个候选分别随访 15/60/240 分钟。

### 3.3 触发与工作线程

- 在 `Runtime.ingest_observation()` 已产生真实 browser observation、event 和 attention point 后评估 enrollment；不能在网络请求前创建虚假 cohort。
- enrollment 只写不可变本地状态，不在 ingest 路径执行网络 I/O。
- 由现有 30 秒 shadow follow-up tick 每次有界处理一个 initial lookup 和到期 follow-up。
- baseline 晚于 signal 时明确标记 `baseline_late`，但不能移动 15/60/240 目标时钟。
- follow-up 使用目标时点之后首次可用的真实 quote/snapshot；超过 grace 后写 missing。
- Runtime 重启、重复 tick 和 provider 错误必须保持幂等，不能产生重复 cohort/candidate/outcome。

### 3.4 已知实现问题

当前 `DexScreenerClient.search()` 会在 provider 返回的有限 pairs 中按 Token 去重，并为同一 Token 选择最高流动性池。若实验声称保存“完整返回集合”，必须明确它究竟指：

- provider 截断后的原始 pair 集；或
- 去重后的唯一 Token 集。

不能把二者混称。若需要原始 pair 分母，应新增最小只读 snapshot 方法；不应修改现有 Strategy 搜索语义。

## 4. 三条独立会话的不同职责

三条会话都必须选择最高可用模型和最高可用思考强度，并实际使用 `@笔记本mcp20260902` 只读检查必要代码。若路由到低级模型、自述不一致、异常快速或明显降质，该轮作废并新建会话重试。

### 会话 A：因果与统计审查

重点寻找：未来数据、选择偏差、幸存者偏差、denominator 丢失、时间锚错误、重复相关样本、attention 阈值事后选择，以及什么成熟门才能回答“信息是否领先市场”。

期望输出：`GO / MODIFIED_GO / NO_GO`、必须修改项、冻结 estimand、主要/次要终点、最小成熟门。

### 会话 B：对抗性产品/交易审查

重点反驳：这个探针是否只是制造更多漂亮样本；人物帖子与 Meme Token 之间是否存在无法控制的叙事映射歧义；如何保留全部候选又不被同名垃圾币淹没；什么结果才可能支持后续 challenger，什么结果永远不能进入交易。

期望输出：最大错误假设、失败模式、无效结论清单、是否存在更小且更有辨识力的替代实验。

### 会话 C：最小工程实施审查

重点检查 `src/memetrader/store.py`、`runtime.py`、`collectors.py` 与相关测试，判断表结构、触发点、幂等键、工作线程容量、provider 返回集合语义和最小测试是否正确，并寻找对当前 Runtime、Strategy、Paper 的意外副作用。

期望输出：最小可实施变更、具体文件/方法、必须测试、部署与回滚边界；禁止直接修改项目。

## 5. 统一问题

请独立回答：

1. 当前问题陈述是否由真实漏斗证据支持？
2. 该探针能否在不选赢家、不回填、不触发交易的情况下估计“重点信息领先市场”的候选分布？
3. registration、eligibility、query、candidate set、baseline 和 15/60/240 锚点是否因果有效？
4. 如何定义“完整候选集合”，避免 Dex provider 截断/去重语义污染分母？
5. 哪些字段、路径或写入会意外影响现有 Strategy、Paper 或 Live？
6. 最小成熟门是什么？在什么证据出现前绝不能晋升为生产 challenger？
7. 给出明确 verdict 和可验证的最小修改清单。

## 6. Codex 合并规则

ChatGPT 的回答只作为研究与独立复核。Codex 必须：

1. 验证 reviewer 确实使用新插件读取了当前必要文件；
2. 丢弃低级模型、无实读、泛泛或相互复制的意见；
3. 对三条建议的共同点和冲突分别核验；
4. 只实现由当前代码和前向数据支持的最小版本；
5. 运行针对性测试并受控部署单一 Paper Runtime；
6. 在自然前向样本成熟前，不调整 Strategy、仓位、退出或 Live。
