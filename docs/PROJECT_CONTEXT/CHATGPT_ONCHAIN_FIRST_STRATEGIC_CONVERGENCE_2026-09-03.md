# GXH / memeTrader：纯链上优先的战略收敛与单一主攻策略

- 决策时间：2026-09-03T11:58:26Z
- 决策角色：Lead ChatGPT（研究、战略设计与独立复核）
- 执行角色：Codex（唯一 active checkout writer）
- 当前模式：Paper；Live 必须继续锁定
- 战略结论：**未来一个完整前向周期只把一条策略作为工程与研究主战线：Solana canonical Pump.fun → PumpSwap、纯链上入场、venue-aware 防 rug、金额特定可卖性、机械动态退出。**

## 1. 决策摘要

用户提出“资源有限，是否应先定下来一个纯链上策略”，客观结论为：**是，但应采用有边界的集中，而不是删除信息能力。**

本周期：

1. 约 85%–90% 的开发、调度、RPC、Jupiter、测试和 UI 资源投入纯链上主策略；
2. 热点/新闻/名人/社区只保留廉价、合规、原始的被动采集和不可变存储；
3. 暂停高成本主动 Agent 搜索、Token Context、WATCH 调查、买后叙事 Agent 和信息策略的 Paper 晋级；
4. S1/S3 既有数据、schema、registration、历史结果全部保留，不删除、不回填、不改写；
5. 等纯链上主策略达到成熟门，或被动信息账本证明足够高的领先价值后，再恢复主动信息路线。

这不是认定信息路线长期无价值，而是承认当前边际资源回报极低。当前首要目标是形成一个可被严格验证、可被成本核算、可被快速迭代的赚钱闭环。

## 2. 优化目标

不要优化：

- 交易次数；
- 表面胜率；
- 不含不可卖仓位的已实现 PNL；
- 单笔或少数超级赢家；
- UI 中漂亮但不可兑现的市值曲线。

真正优化：

> 最大化长期复利意义下的、扣除真实可实现成本后的风险调整收益，同时限制破产概率、流动性死亡损失、尾部回撤和执行失败。

在 Paper 成熟前，固定 `$20` 仓位继续作为公平学习单位；不得因早期盈利样本放大仓位。

## 3. 当前本地证据

事实截止约为 2026-09-03T11:58Z，来自当前 r6 SQLite、现有源码与 Codex 结果。

### 3.1 信息路线的边际产出

从当前公平周期起：

- 132 个信息策略 Decision：125 WAIT、7 REJECT、0 CANDIDATE；
- 主信息 Paper 账户仍为 `$1000`、0 新仓位、0 新成交；
- 189 个 Token Context assessment：176 `no_context`、12 `insufficient_reachable_sources`、1 `insufficient_context_only`；
- 高成本 Agent 使用约 9,802,692 tokens：
  - Token Context 有效 137 次 / 8,138,391 tokens；
  - Trend Scout 16 次 / 1,271,973 tokens；
  - Source Discovery 1 次 / 230,019 tokens；
  - Fact Verifier 1 次 / 84,847 tokens；
  - 另有 1 次无效 Token Context / 77,462 tokens。

当前可观察的转化结果是：大量 Agent 资源没有形成可执行候选。主要问题不是调用上限，而是 timely independent information → exact token → executable route 的结构性低转化。

### 3.2 纯链上路线的当前产出

`onchain-only-shadow/v2-20usdc`：

- 72 个 cohort，71 个时序有效；
- Solana 32、BSC 18、Base 9、Robinhood 13；
- Solana Jupiter v2 激活后 32 个 cohort 中，9 个取得有效 baseline quote，早期 23 个因旧调度路径错过队列时限；最近一段已连续取得新有效报价，旧零尝试结论已过时。

当前 v4 纯链上 `$20` Paper：

- 8 个严格前向入场；
- 固定 15m 基线已有 3 个关闭，合计实现 `+$13.478075`；
- 动态退出已有 2 个关闭，合计实现 `+$90.631865`；另有一个开放仓实现部分 TP `+$1.026781`；
- 其中 cohort 2179 对动态结果贡献极大：固定 15m `-$0.51209`，动态四档 TP `+$78.323105`；
- cohort 2200 则固定 `+$15.777079`，动态 trailing `+$12.308760`，说明动态并非每笔都优于固定；
- 多个开放仓的可执行权益尚不完整，因此不能把当前 realized PNL 当作成熟盈利证明。

旧经济执行 v3 进一步暴露 winner dependence：动态账本 13 个已终结仓合计约 `+$164.969081`，但其中唯一大赢家约 `+$573.259028`；去掉该笔后其余已终结仓合计约 `-$408.289947`，且有 10 个整仓核销。固定 v3 的 22 个已终结仓合计约 `+$20.501449`，中位 PNL 约 `-$2.243533`；去掉最大赢家后合计约 `-$78.870626`。因此任何“已经盈利”的说法都不成立；动态臂被选为 operational primary，是因为它同时保留右尾并能机械响应死亡风险，而不是因为当前样本已经证明其统计优势。

结论：纯链上不是已证明策略，但它已经具备可执行样本、明确因果链和可量化改进面，明显比当前信息路线更适合作为唯一主攻。

### 3.2.1 更宽的严格前向市场结果：支持聚焦，但同时暴露尾部风险

对当前 `onchain-only-shadow/v2-20usdc` 中 Solana cohort 的固定时点、同一路径市场快照结果进行只读复核：

- 15m：32/32 有观察值；raw return 中位数约 `+9.91%`，均值约 `+15.09%`，24 个为正，3 个不高于 `-50%`，12 个目标快照的流动性为 0；
- 60m：23 个有观察值、8 个 error；中位数约 `+26.01%`，均值约 `+100.77%`，17 个为正，4 个不高于 `-50%`，13 个目标快照流动性为 0；
- 240m：22 个有观察值、1 个 error；中位数约 `+15.47%`，均值约 `+119.38%`，12 个为正，8 个不高于 `-50%`，15 个目标快照流动性为 0。

这些数字**不是可执行收益**：对应记录明确是 market snapshot / unsupported execution，且常见“价格仍为正、流动性已经为 0”的组合。它们只能说明两个结构事实：

1. 纯链上高动量候选中确实存在明显右尾机会；
2. 长持同时伴随严重的流动性死亡和接近归零尾部，屏幕价格不能替代可卖收益。

赢家敏感性进一步说明不能被均值迷惑：

- 15m 删除收益最高的 3 个样本后，剩余 29 个 raw return 均值仍约 `+3.65%`、中位数约 `+6.73%`；
- 60m 删除最高 3 个后，剩余 20 个均值约 `+25.37%`、中位数约 `+23.17%`；
- 240m 删除最高 3 个后，剩余 19 个均值仅约 `+4.78%`，且中位数转为约 `-6.34%`。

因此固定 240m 长持不是当前合理主执行策略；动态退出作为 operational primary、固定时点作为 comparator 的方向更合理。但在 amount-specific、费用完整、死亡仓核销的样本成熟前，仍不得称其已证明盈利。

当前 momentum score 也不是成熟排序器：80–85 分组在 15m/60m/240m 的中位 raw return 分别约 `+20.0% / +58.2% / +22.1%`，而 85–90 分组约为 `+3.6% / +24.2% / +1.3%`。这不是“降低分数反而更好”的结论，而是表明现有分数在 80–90 区间饱和、缺少 age/acceleration/turnover/custody 等区分信息。正确动作是保留 threshold=80 作为基线并建立前向 feature ledger，而不是立即上调或下调阈值。

### 3.3 系统资源与 UI 证据

- 当前 SQLite 主库约 5.1 GB，WAL 约 888 MB；
- `/api/portfolio` 当前响应约 390 KB；
- 本机一次只读测量：Portfolio API 约 0.24 秒，Health API 约 3.9 秒；
- 这说明 UI 不应继续把所有研究账本塞入一个高频大 payload，也不应让浏览器刷新触发任何 RPC/Jupiter 工作。

## 4. 三条路线的客观比较

| 维度 | S1 信息 + Token | S2 纯链上 | S3 Token 后信息 |
|---|---:|---:|---:|
| 当前可执行闭环 | 低；route-backed Paper 仍未完成 | 高；Jupiter amount-specific BUY/SELL 已运行 | 低；信息 treatment 未成熟，当前仅同入场控制 |
| 延迟确定性 | 低；采集、映射、Agent、独立来源均可迟到 | 高；链上/DEX/RPC 可机械处理 | 中低；入场同 S2，买后信息仍依赖 Agent |
| 单位资源成本 | 高 | 低到中 | 高于 S2 |
| 因果可解释性 | 低到中 | 高 | 中，但需要成熟对照 |
| 当前前向经济证据 | 0 新候选 | 已有 8 入场和金额特定退出 | 暂无信息增量证据 |
| 未来期权价值 | 高 | 高 | 中高 |
| 当前主攻价值 | 低 | **最高** | 低 |

因此本周期只主攻 S2；S1/S3 保存期权，不平均分配资源。

## 5. 唯一主策略定义

建议新版本：

`solana-pumpswap-rug-safe-dynamic-primary/v1`

或按现有命名体系注册为：

`onchain-paper-primary/v5-canonical-pumpswap-rug-safe-dynamic`

### 5.1 范围

首版只接受：

- Solana；
- 已完成 Pump.fun bonding curve 迁移；
- exact on-chain migration/pool-created time 可得，且最终入场评估时 pool age `<=10 分钟`；缺失或超过窗口即 WAIT；
- exact pool RPC 证明为官方 PumpSwap program；
- canonical migration pool PDA、mint、vault、authority 全部匹配；
- LP burn / currently removable LP 达到冻结门；
- Token 控制权与 exact-size sellability 通过。

Raydium CPMM v3 RPC decoder 已实现并应保留，但不扩大首版主策略范围。Raydium AMM v4、CLMM、Orca、Meteora、BSC、Base、Robinhood 暂停继续开发和 Paper 晋级，继续 fail-closed / Research Lab。

这并不是无依据地砍覆盖：在 2026-09-03T12:16Z 的最新只读截面，34 个当前 Solana 高动量 cohort 中 32 个为 PumpSwap、2 个为 Meteora，PumpSwap 已覆盖约 94.1% 的当前机会面。当前 8 个 v4 Paper 入场的 pool age 均约为 2.0–8.5 分钟，因此 `<=10m` 的主策略边界保留全部当前 Paper 入场，同时排除 4 个约 6.8–7.5 小时的旧池复苏样本，避免把两种不同 estimand 混在一起。

这样做牺牲少量横向覆盖，换来：

- 更小的状态空间；
- 更可靠的 custody 语义；
- 更快的调试与前向样本解释；
- 更低的错误池/错误成本混入概率。

### 5.2 入场信号

首版保持当前 `candidate_momentum_score/v1 >= 80`，不因少量赢家即时修改。当前分数包含流动性、5m 成交量、交易笔数和买卖不平衡，是可用基线，但不是最终 alpha 模型。

入场必须依次通过：

1. first post-registration eligible on-chain trigger；
2. 快照严格 `observed <= ingested <= recorded <= evaluation`；
3. canonical PumpSwap RPC custody PASS；
4. Token authorities / Token-2022 扩展 PASS；
5. creator malicious flag / known deterministic risk PASS；
6. `$20` brand-new Jupiter ExactIn BUY；
7. 使用 BUY minimum token output 立刻做同数量 SELL preflight；
8. immediate round-trip 必须达到冻结的成本底线；
9. 原子写入独立 primary Paper account；任一步失败均无现金突变。

### 5.3 必须立即修正的 sell-preflight 经济门

当前 `solana_pretrade_rug_assessment` 对 sell preflight 只检查：

`net_recovery_usd > 0`

这不足够。一个 `$20` 买入若只能卖回 `$0.50`，仍会被视为正数，但显然是不可接受的入场。

应把“能卖”与“值得买”拆成两个透明门，并避免费用双计：

- Jupiter `outAmount` 已扣除 AMM/platform fee；`otherAmountThreshold` 又在其上应用 slippage tolerance，因此不得再额外重复扣 route/pool fee 或 configured slippage；
- 只在两者之外另计冻结的 entry/exit network fee；
- 冻结 `quoted_net_recovery_ratio = (sell_outAmount_usd - exit_network_fee) / (buy_input_usd + entry_network_fee)`；
- 冻结 `stress_min_recovery_ratio = (sell_otherAmountThreshold_usd - exit_network_fee) / (buy_input_usd + entry_network_fee)`；
- primary v1 建议预注册为：`quoted_net_recovery_ratio >= 0.90`，且 `stress_min_recovery_ratio >= 0.85`；任何值低于 0、结构不完整或 route stale 仍为硬拒绝；
- 低于门槛 => `REJECT_EXCESSIVE_IMMEDIATE_ROUNDTRIP_LOSS`；
- 后续只以前向 Shadow 比较 0.88/0.90/0.92 等候选，不能在线漂移。

这两个比例不是利润预测，而是成本/可卖性预算。当前新自然 PumpSwap 非 canonical 样本的 exact sell minimum 净回收约 `$17.9435`、best-quote 净回收约 `$18.7269`，但 RPC 证明 LP 约 100% 可撤且 migration creator 非 canonical，所以它仍应因 custody WAIT；这说明 custody 与经济门必须同时成立，不能彼此替代。

### 5.4 时效

新 primary entry 不沿用宽松的 30s queue / 45s total 作为最终成交门。建议冻结：

- trigger snapshot 到 provider request：目标 `<=5s`；
- trigger/evaluation 到 quote complete：目标 `<=10s`；
- 超时直接 WAIT，不缩放旧 quote、不复用旧价格。

当前 11 个真实 baseline provider attempt 的只读延迟已支持这一边界：queue p50/p95 约 `3.19s / 4.05s`，total p50/p95 约 `4.18s / 5.79s`，最大约 `7.16s`。因此 primary v1 可直接冻结 queue `<=5s`、trigger/evaluation-to-final-preflight `<=10s`；若未来自然 provider 退化，只记录 WAIT 与 deadline miss，不自动放宽到 45s。

## 6. 动态退出作为 primary，固定退出作为 comparator

### 6.1 为什么选动态为主

Meme 收益高度右偏。固定 15m 能降低等待风险，但会系统性截断少数大赢家；当前 2179 已展示这种可能。与此同时，动态 2200 少赚于固定，说明动态也有机会成本。

因此：

- 动态退出是 operational primary；
- 固定 15/60/240 是同入场、无额外外部资源的 comparator；
- 不删除固定基线；
- 不根据当前两笔关闭样本调参；
- 最大同时开放仓位冻结为 `5`，每日新风险暴露冻结为 `$100`；任一 `ALERT/confirmed-dead` exit 待处理时暂停新入场，把有限 Jupiter/RPC 容量先留给退出。

### 6.2 首版冻结参数

沿用当前 v4，不在线改动：

- hard stop：`-35%`；
- trailing activate：`+60%`；
- trailing drawdown：`28%`；
- staged TP：
  - `+80%`，卖剩余的 20%；
  - `+180%`，卖剩余的 25%；
  - `+350%`，卖剩余的 35%；
  - `+700%`，卖出全部剩余；
- emergency liquidity floor：`$3,000`；
- zero activity grace：5m；
- max hold：240m；
- 每次成交使用实际 remaining raw amount 的 Jupiter minimum output；
- 无经济 route 不得伪造 SELL。

## 7. “撤池即终局”的新语义

用户最新指令明确 supersede 当前 scheduler 的恢复设计：**已确认撤池 / rug 后，不再考虑恢复。**

但要严格区分：

### 7.1 `CONFIRMED_RUG_DEAD`

必须有链上事实，而不是单个第三方页面的 `liquidity=0`：

- 解码到 LP withdraw/remove-liquidity 指令，且 vault/reserve 同 slot 或相邻 slot 出现灾难性撤出；或
- verified noncanonical LP holder 消耗可撤 LP，且 quote/base vault 变化符合撤池；或
- exact pool/vault RPC 证明储备已被抽空，同时 remaining-size Jupiter SELL 为 no-route 或低于 terminal economic floor。

动作：

1. 立即对全部 remaining raw amount 发起一次最高优先级 SELL quote；
2. 有经济 route 就一次性退出；
3. 无经济 route 就 terminal write-off；
4. 追加 `chain + token_mint + pool_address + strategy_version` dead registry；
5. 同一策略版本永不 rearm、永不自动 re-enter、永不再消耗 Jupiter；
6. 后来出现新流动性只能作为研究结果，不恢复该仓位或该版本的交易资格。

### 7.2 `TRANSIENT_ROUTE_FAILURE`

以下不能单独称为 rug：

- provider timeout；
- Jupiter no-route，但链上 vault/reserve 正常；
- DexScreener 暂时缺 pair / liquidity=0；
- RPC 失败；
- 某一次 quote protocol error。

这些继续使用有界 backoff，但不能覆盖 confirmed dead terminal。

### 7.3 修订 scheduler v1

当前 `onchain-paper-exit-quote-scheduler/v1-adaptive-dead-route-backoff` 的 `fresh_liquidity_and_activity_recovery_or_terminal` rearm 只可服务 transient failure。必须注册 v2：

`onchain-paper-exit-quote-scheduler/v2-rug-terminal-no-rearm`

v1 历史不改；v2 明确：

- transient：15/30/60/120/300s，最多 6 次；
- confirmed rug/dead：一次紧急尝试后 0 次重试；
- no rearm；
- terminal registry 防 restart 后重新排队。

## 8. 持仓监控：事件驱动优先，轮询兜底

### 8.1 不使用 Agent

持仓风险、pool/vault、价格、flow、Jupiter route、止损/止盈全部是程序机械过程。Agent 不得进入紧急路径。

### 8.2 订阅

每个开放仓对少量 exact account 建订阅：

- pool account；
- base vault；
- quote vault；
- mint / LP mint；
- 必要时 pool program logs。

Solana `accountSubscribe` 用于账户数据变化；`logsSubscribe` 按 exact pubkey 监听相关交易。订阅事件只唤醒本地检查，不直接判定成交。

### 8.3 状态与频率

| 状态 | 时间/条件 | DEX mark | amount-specific sell quote | RPC subscriptions |
|---|---|---:|---:|---|
| ENTRY_HOT | 开仓后 0–10m | 2–5s | 10–15s | 常驻 |
| OPEN_WARM | 10–60m | 5–10s | 30s | 常驻 |
| OPEN_COOL | >60m | 15s | 60s | 常驻 |
| ALERT | vault/log/reserve/stop/TP 触发 | 立即 | 立即 | 常驻 |
| DEAD | confirmed rug terminal | 低频审计 | 不再请求 | 可退订 |

UI 刷新不能触发这些请求；后台监控器是唯一 producer。

## 9. 纯链上 entry alpha 的下一步

当前 momentum score 太粗：大量强样本会在 80–90 之间饱和，不能区分“刚开始加速”与“已经冲顶”。不要立刻用 ML 替换，而是先建 append-only、严格前向 feature ledger。

每次 trigger 冻结：

- pool/migration age；
- m1/m5/h1 return；
- m1→m5 volume acceleration；
- transaction acceleration；
- buy ratio 及变化；
- average trade size / buy-vs-sell size asymmetry；
- liquidity level、slope、drawdown、volume/liquidity turnover；
- market cap / liquidity；
- creator prior launch count 与 prior collapse rate；
- first buyers / holder concentration / bundle or coordinated-owner lower bounds；
- exact BUY price impact；
- immediate round-trip minimum recovery；
- pool custody/removable LP；
- route venue与 route plan。

先描述分层，不在线学习。未来只允许一次改一个变量的 Shadow challenger，例如：

- threshold 80 baseline vs 85；
- price acceleration positive vs unrestricted；
- turnover band；
- creator-history exclusion；
- concentration exclusion。

新规则未达到成熟门前不得影响 primary。

## 10. 资源分配与暂停内容

### 10.1 本周期资源预算

- 85%–90%：Solana canonical PumpSwap primary、rug safety、Jupiter、monitoring、feature ledger、Terminal/UI；
- 7%–10%：被动 RSS/browser/on-chain 原始采集、不可变 provenance 与健康检查；
- 2%–5%：定期人工/Lead 复核与信息路线 reactivation gate。

### 10.2 立即暂停

通过一个 machine-readable focus registration 执行，不删除配置历史：

`strategy-focus/v1-solana-onchain-primary`

暂停未来：

- autonomous Trend Scout；
- autonomous Source Discovery；
- Token Context Agent；
- Fact Verifier Agent；
- WATCH 新 Agent dispatch；
- S3 post-entry narrative Agent；
- S1 new Paper execution/promotion；
- S3 new Paper entry/treatment；
- BSC/Base/Robinhood route/Paper 工程；
- Raydium AMM v4 / CLMM / Orca / Meteora decoder 扩张；
- broad UI redesign。

### 10.3 继续运行

- PumpPortal / token discovery；
- Dex hydration；
- Solana RPC/Jupiter；
- 当前原始 RSS/browser collectors，限于低成本本地采集；
- immutable observations/source links/events；
- S2 primary + fixed comparator；
- 现有历史 Research Lab 只读展示；
- Live lock。

## 11. Terminal-first 可视化

Web 当前太重，先实现只读终端 cockpit：

`python -m memetrader cockpit --strategy onchain-primary --refresh 1`

要求：

- 标准库/现有依赖，Windows 终端可用；
- 只读 SQLite，1s 刷新；
- 不发 RPC、DEX、Jupiter 请求；
- 不写数据库；
- 不显示 secret。

首屏只显示：

1. primary cash / realized / executable equity lower bound；
2. open positions；
3. 每仓：HOT/WARM/COOL/ALERT/DEAD；
4. entry cost、realized proceeds、remaining raw；
5. DEX indicative value；
6. latest amount-specific sell minimum net recovery；
7. custody class、removable LP、vault balances与最近变化；
8. current exit trigger / pending quote / attempts / latency；
9. latest critical events；
10. fixed comparator paired result。

Web 后续只增加轻量 endpoint，前台可见时 2s polling；重 Portfolio 保持 15s。不要先做大面积视觉重构。

## 12. 数据库与运行性能

5.1 GB SQLite + 888 MB WAL 已经是需要控制的操作风险，但当前不应进行破坏性清理。

Codex 应先：

- 测量主要表增长率、最长查询、payload 大小；
- 给 cockpit/position endpoint 建最小覆盖索引；
- 将 Research Lab 大 payload 从实时 endpoint 分离；
- 不 VACUUM 活跃 5GB 库；
- 不删除历史；
- 只在安全维护窗口做 checkpoint/归档设计；
- 任何性能优化不得阻塞紧急 exit loop。

## 13. 成熟门与防止被少数赢家欺骗

首版 primary 至少达到以下门，才讨论增加仓位或进入 live review：

- >=100 个关闭仓位；
- >=15 个独立 UTC 日期；
- >=20 个亏损样本；
- >=10 个 no-route / dead / terminal 样本；
- 100% entry/exit 使用 amount-specific quote 或明确 terminal write-off；
- 完整费用标签；
- 动态 vs 固定同入场比较；
- 去掉 top-1 与 top-3 盈利交易后仍不过度依赖单一赢家；
- 按日期 block bootstrap / leave-one-day-out 不出现系统性崩溃；
- 最大回撤、尾部损失和连续亏损可接受；
- provider deadline miss 和 execution coverage 达标。

在此之前：

- `$20` 固定仓位；
- 不做 Kelly sizing；
- 不扩大链；
- 不放宽 momentum threshold；
- 不根据单日/单币改 TP/stop。

## 14. 信息路线何时恢复

信息路线不是按日历恢复，而是按 evidence gate 恢复。被动账本至少证明：

- >=30 个严格前向 exact-addressable information events；
- >=10 个独立日期；
- 信息到达领先 on-chain trigger 的分布有实际价值；
- false canonical/fanout 可控；
- 单位 Agent 调用带来的新增可执行候选率显著高于当前近零水平；
- 不需要恢复大规模泛搜才能取得这些结果。

否则继续被动采集，不与主战线争资源。

## 15. Codex 执行顺序

### Tranche 0：战略停火与版本边界

- 注册 focus mode；
- 停止高成本 Agent 与非主策略未来 dispatch；
- 保留被动 collectors；
- 确认 isolated S3 已禁用；
- 不碰 Live。

### Tranche 1：完成 canonical PumpSwap primary entry

- 接受并冻结 `pretrade_rug_safety/v2` PumpSwap RPC custody；
- Raydium CPMM v3 保留 Research；停止继续横向 venue 扩张；
- 修正 sell-preflight `>0` 经济门；
- 新 primary registration/account/activation frontier；
- 仅 post-registration canonical PumpSwap；
- `$20`、momentum 80、严格 freshness、atomic account mutation。

### Tranche 2：rug terminal no-rearm

- 新 scheduler v2；
- decoded rug/dead terminal registry；
- one emergency exact-size exit；
- no retry/no rearm/no reentry；
- transient errors 保留 capped backoff。

### Tranche 3：事件驱动机械监控

- account/log subscription manager；
- HOT/WARM/COOL/ALERT/DEAD；
- quote priority isolation；
- restart/idempotence；
- subscription loss falls back to bounded polling。

### Tranche 4：Terminal cockpit

- 只读、1s refresh、无网络、无写入；
- executable equity 和 custody/exit 状态优先；
- Web 轻量 endpoint 后置。

### Tranche 5：forward feature ledger

- 冻结 trigger feature vector；
- 固定 comparator；
- 单变量 Shadow；
- maturity dashboard；
- 不在线自调。

## 16. 最小验收

1. focus mode 后 Agent 不再产生新调用，低成本原始 collectors 仍写入；
2. 非 primary strategy 不再创建新 Paper 仓位或 Agent treatment；
3. 只有 verified canonical PumpSwap + LP burn/custody PASS 才能进入 primary BUY；
4. `$20` BUY 后只能卖回很小金额时必须 REJECT；
5. assessment WAIT/REJECT/stale 时账户零突变；
6. confirmed rug/dead 最多一次紧急 Jupiter attempt，随后永久 terminal；
7. restart 后 dead pool 不重新排队、不 rearm、不 re-enter；
8. transient provider error 不被误记为 rug；
9. fixed/dynamic 同入场完整配对；
10. cockpit 1s 刷新不增加任何 provider request；
11. critical exit queue 不受 Research/UI/Agent 阻塞；
12. Live 仍 locked。

## 17. 研究依据

外部研究和官方文档支持以下方向：

- Pump 官方文档：bonding curve 完成后迁移至 PumpSwap，收到的 LP token 被 burn；PumpSwap Pool 结构含 LP mint、vault 和 withdraw 语义；
- Solana 官方 RPC：accountSubscribe 和 logsSubscribe 可用于少量开放仓的事件驱动监控；
- Solana Token-2022：Permanent Delegate、Transfer Hook 等扩展可显著改变持有人转账/卖出风险；
- 2026 年 Solana rug 研究：大规模样本表明许多 rug 特征在上线后极短时间内出现，前 5 分钟链上特征具有早期预测价值；
- 2026 年 Solana rug 行为研究：主要模式包括流动性撤出、价格操纵、短生命周期与组织化地址行为；
- 2026 年 Paper trading 研究提示：表面盈利可能由极少数赢家主导，移除 top 3 后可翻为亏损，因此必须做 winner-removal robustness。

## 18. 最终处置

`APPROVE_ONCHAIN_FIRST_WITH_PASSIVE_INFORMATION_OPTIONALITY`

当前最好的行动不是继续并行修三条半成品路线，而是把一条纯链上闭环做到：

**能识别池、能证明控制权、能买、能立即验证可卖、能高频机械监控、能在危险发生时抢先退出、能在彻底 rug 后认亏终结、能用真实成本和完整分母学习。**

达到该闭环并积累成熟样本后，再决定新闻/名人/社区是否值得重新投入主动资源。

## 19. 12:01 UTC later fact-check delta（不改变主方向）

后续只读核验补充了五点，均并入本方案而不创建第二套计划：

1. **旧 `queue_delay_expired` 不是当前实时瓶颈。** 23 个早期 Solana baseline gap 行是在 Jupiter-v2 overlay 上线后一次性终结旧 cohort；overlay 激活后的 9 个自然 baseline BUY provider 请求延迟约 `0.13–4.05s`。因此不要继续围绕“72% 当前机会因 queue miss 丢失”做工程；当前核心已转为买谁、防 rug、何时卖。
2. **PumpSwap 聚焦的机会成本更低。** 最新 33 个 current-v2 Solana cohort 中约 32 个的 as-of market surface 为 PumpSwap，当前 8/8 fair-v4 S2 Paper 入场也是 PumpSwap。canonical PumpSwap-only 可以作为本 Focus Epoch 的 active Paper scope；Raydium CPMM v3 保留 Research 即可。
3. **第一条 rug-v3 自然样本已经 fail-closed。** cohort `2221` momentum `88.9714`，fresh `$20` BUY + exact acquired-size SELL preflight 均可路由，但 RPC 证明该 PumpSwap pool `canonical_migration_structure=false`、burned LP 近零、`removable_lp_pct≈100%`，因此 `WAIT: pool_custody_or_lp_burn_insufficient`，没有新 Paper cash mutation。这是需要持续保存的 safety-abstention 分母。
4. **creator history 不能成为当前 hot-path 必选条件。** 当前 33 个 Solana cohort 仅 5 个有本机 PumpPortal create lineage，当前 8 个实际 S2 入场为 0/8；缺失不能冒充安全或自动 REJECT。该层先做可用即用的 forward feature。
5. **holder RPC 不宜同步阻塞 entry。** 当前 holder-shadow 505 个 observed call 平均约 `5.77s`，并有长尾/错误；hot entry 先用已到达 GoPlus/RPC custody/exact execution，holder/bundle 继续异步/targeted。若需要行为轨迹，新增 bounded M70 **observer-only prewatch**（建议最多 10–20 active），通过 exact pool/vault subscriptions 收集 M80 之前的 reserve/liquidity/flow trajectory；M80 active BUY threshold 不变。

成熟门解释统一：`>=30 terminals / >=15 dates / >=5 positive + >=5 nonpositive` 仅是最早的 research-comparison checkpoint；本文件第 13 节的 `>=100 closed / >=20 losses / >=10 dead-or-no-route terminal` 等条件继续作为放大仓位、扩 venue/chain 或 Live review 的更严格硬门。
