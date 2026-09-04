# Meme 单主升浪、峰值回撤退出与市场级盈利系统方案

日期：2026-09-04（Asia/Tokyo）  
状态：`PROMOTE_NOW / LONG-RUN ACTIVE CYCLE`  
本地访问：**始终使用 `@笔记本量化MCP-官方隧道`**  
执行 owner：Codex（唯一代码、测试、部署 writer）  
研究与目标守护：Lead ChatGPT  
Live：继续 `LOCKED`；本文件要求现在完成 Live-ready 架构，不授权 Mainnet 签名或广播

---

## 1. 核心结论

用户提出的判断——“Meme 币基本上就是一波，最高点回撤以后大概率结束”——**作为新发、超小盘 Meme 的先验，方向上基本正确；作为无条件规则则不完整。**

更准确的交易表述是：

> 对多数新发 Meme，第一次强主升浪之后一旦出现**持续而非单点的深回撤**，再次突破此前运行中高点的条件概率会迅速下降。此时继续持有通常是在用大量左尾风险换少量二次创新高概率。更优架构不是“永远不再买”，而是**先退出，把以后真正的第二波作为新的 `REAWAKENING` cohort 重新进入**。

因此系统应默认采用：

1. **One-wave prior**：第一次主升浪是主盈利窗口；
2. **Peak-death guard**：使用当时可得的运行中高点、回撤深度、回撤速度、资金流、Vault、可执行回收率判断主升浪是否结束；
3. **Exit then re-enter**：深回撤后不长期硬扛，真正复苏时由独立 Reawakening 策略重新买；
4. **宽入场、快退出**：Broad Scout 可以放宽 soft risk，但持仓监控必须更快、更强；
5. **概率状态而非单指标**：价格回撤不是死亡证明；exact Pool/Vault/route/flow 决定是否升级为 RED/DEAD。

这不是过度防御。相反，它允许高召回 Paper 继续捕捉右尾，同时把最危险的“从浮盈到归零”路径交给低延迟机械退出，而不是靠更多入场拒绝来避免亏损。

---

## 2. 本项目自己的证据：单主升浪先验得到初步支持

以下均是本轮通过 `@笔记本量化MCP-官方隧道` 对当前 r6 的只读描述性分析，不写回策略，不修改历史。时间窗口仅覆盖当前数据库 2026-08-30 至 2026-09-03，因此是**设计证据，不是最终参数训练集**。

### 2.1 分析口径 A：首次深回撤后的再创新高概率

样本筛选：

- Solana Token；
- 正价格快照不少于 10 个；
- 观察跨度不少于 30 分钟；
- 从本机首个快照起，运行中峰值至少上涨 25%；
- 检测首次从运行中峰值回撤 10%–90%；
- 只有目标 horizon 已完整经过且存在后续快照才进入该 horizon 分母。

共有约 4,084 个覆盖合格 Token group。首次 30% 回撤后：

| 后续时限 | 可评估样本 | 再创新高 | 恢复到旧峰值 90% | 后续跌到旧峰值 50% 以下 |
|---|---:|---:|---:|---:|
| 15m | 156 | 8.33% | 21.15% | 62.18% |
| 60m | 176 | 11.93% | 23.30% | 63.64% |
| 240m | 123 | 13.82% | 22.76% | 65.85% |

首次 40% 回撤后，240 分钟再创新高约 8.57%；80% 回撤后约 9.09%。深度并非严格单调，原因包括小样本、稀疏快照、价格源跳变、later reawakening 和筛选偏差，但总体基率已经很低。

### 2.2 分析口径 B：要求回撤持续，排除单个坏 tick

更严格口径：

- 至少两个后续观测仍低于回撤阈值；
- 第二个确认观测必须在首次触发后 3 分钟内；
- 分别检查不同最少快照数、首段涨幅和 Pump 地址子集。

持续 30% 回撤后的结果：

| 口径 | 60m 再创新高 | 240m 再创新高 |
|---|---:|---:|
| ≥5 快照、先涨 ≥10% | 1.88%（n=320） | 6.25%（n=112） |
| ≥5 快照、先涨 ≥25% | 2.49%（n=241） | 7.61%（n=92） |
| ≥10 快照、先涨 ≥25% | 4.55%（n=110） | 8.82%（n=68） |
| ≥10 快照、先涨 ≥50% | 3.66%（n=82） | 5.77%（n=52） |
| Pump 地址子集、≥10 快照、先涨 ≥25% | 2.90%（n=69） | 6.82%（n=44） |

这比“单次碰到 30% 回撤”的结果更有交易意义：**持续 30% 回撤后，约九成以上样本在 240 分钟内没有再创新高。**

### 2.3 二次创新高的时间结构

在另一组满足持续 30% 回撤的 133 个事件中：

- 只有 12 个后来再次创新高，约 9.02%；
- 0 个在 10 分钟内再创新高；
- 6 个在 10–60 分钟；
- 2 个在 60–240 分钟；
- 4 个在 240 分钟以后；
- 二次创新高等待时间中位数约 104 分钟，但尾部可达 20–34 小时。

这直接支持 `exit-then-reenter`：以后真有第二波，多数也不是必须在第一次深回撤中一直扛着才能捕捉。Reawakening 可以用新的资金流和可执行性触发重新买入。

### 2.4 哪些条件更接近“已经结束”

对持续 30% 回撤事件做探索性分层：

- 若回撤时 liquidity 仅剩峰值时的 25% 或更低：60m/240m 再创新高均为 0；约 73% 在 60m 内进一步跌到峰值 10% 以下；
- 若当时 5m buy share 低于 45%：60m 再创新高为 0，240m 约 4.35%；
- 若 10 分钟内能重新站回旧峰值 90%，再创新高概率明显提高；但此组样本只有 3 个，不能据此定量；
- 回撤后的快速 reclaim、流动性保持和买方占优可能是少数例外的必要但不充分条件。

这些数据说明：

> `drawdown depth × persistence × failed reclaim × flow reversal × liquidity/vault deterioration × executable recovery` 比单独的回撤百分比更有用。

### 2.5 当前 v5 的真实自然样本更强烈地暴露了问题

Codex 最新结果确认 v5 已产生自然 BUY/SELL。cohort `2286` 只被最宽的 Stage 1 接纳：

- 入场 momentum 约 83.71；
- Dex 表面 liquidity 约 317k USD；
- buys/sells 约 238/114；
- baseline price impact 约 -79 bps；
- canonical PumpSwap、mint/freeze/Token-2022 静态安全事实正常；
- SELL preflight 因共享预算为 `budget_deferred`；
- Stage 1 没有挂 exact held-account targets。

其完整剩余仓位的 Jupiter 最低回收：

- 16:50:18Z：约 20.5434U；
- 16:50:37Z：约 0.006235U；
- 16:50:54Z：hard-stop 最终约 0.006285U；
- 最终约 -19.993715U。

链上 exact vault 对比表明：

- quote vault 从入场附近约 1,512 SOL 降到约 1.10 SOL；
- base vault 从约 11.5M Token 增到约 951M Token；
- 这是大规模 Token 卖入池并抽走 SOL 的交易流 collapse，而不是 LP 被撤；
- 约 20 秒内可执行回收从约 20.54U 归零。

这条样本的结论不是“Stage 1 永远不能买”，而是：

1. 静态池安全不等于价格安全；
2. Dex 5m 聚合值可以滞后或被操纵；
3. 15–20 秒轮询在极端 Meme collapse 中太慢；
4. Broad Scout 必须比保守策略**更快监控和更快退出**；
5. exact quote/base vault delta、same-slot sell burst、全仓 recovery slope 应成为所有仓位的共同风险事实。

### 2.6 cohort 2298：已有监听仍漏掉 20 秒连续单边抽干

cohort `2298` 更直接证明“有 WebSocket”不等于风险系统已经有效：

- 12 个账户均于 `17:11:16.959935Z` 入场；
- 入场后约 97 秒因 Dex `liquidity_below_3000` 才退出；
- 每账户回收约 0.335702U，PNL约 `-19.664298U`；
- exact Pool/base vault/quote vault/mint/LP五类 target 均已注册。

需要区分两种储备口径。原始 WSOL vault 相对首个 confirmed baseline 的轨迹为：

- 入场后约 19.65 秒：剩 38.83%；
- 再过约 0.32 秒：剩 16.66%；
- 再过约 0.48 秒：剩 5.37%；
- 入场后约 23.93 秒：剩约 0.59%；
- 随后约 0.44%。

这些是**真实 Vault 资金流比率**，不是完整定价深度。当前官方 Pool 结构另有约17.5845 SOL `virtual_quote_reserves`；该pool在观察窗口内账户hash未变。加入virtual reserve后，effective quote reserve相对effective baseline约为46.97%→27.75%→17.96%→13.82%→13.69%。因此正确结论不是“有效储备跌到0.44%”，而是：约20秒内真实WSOL几乎被卖压拿走，同时有效定价深度下降约86.3%。

同一时间 base vault增至基线的约2.13×、3.61×、5.58×、7.25×，这是连续大额卖入 Token、拿走 SOL 的明确方向性流量。系统必须同时保存`real_vault_flow_ratio`和`effective_price_depth_ratio`，不得互相冒充。

现有 `record_onchain_held_account_update()` 只在：

- 单一步骤直接跌到前一步的10%以下；或
- 相对baseline≤10%且另一侧Vault也同样耗尽；

才形成严重告警。于是原始WSOL vault连续的61%→57%→68%→88%单步下降虽然总计约20秒内几乎被抽空，风险状态仍为`HEALTHY`。即便按包含virtual reserve的有效深度，跌幅也达到约86.3%。这不是阈值略微不理想，而是状态语义错误：

- **单边 quote-vault depletion + base-vault accumulation**是价格/资金流`RED`，应立即抢占式卖出；
- **双边耗尽、账户失效、pool identity变化 + full-remaining不可卖**才是`DEAD`；
- `RED`允许概率性敏感，`DEAD`保持精确终态。

### 2.7 当前 PumpSwap Pool 解码落后于官方协议结构

本轮通过官方隧道下载当前 Pump AMM IDL，并核验官方 `@pump-fun/pump-swap-sdk 1.19.0`：

- 官方SDK导出`POOL_ACCOUNT_NEW_SIZE=300`；当前抽样18个mainnet exact pool account实际均为301 bytes；
- 项目`SolanaHeldAccountCollector.decode_account()`只要求`len>=211`并仅解码到offset 211；
- 当前官方Pool在后续字段保存`coin_creator`、`is_mayhem_mode`、`is_cashback_coin`和signed i128 `virtual_quote_reserves`；
- 18/18抽样pool的virtual quote reserve均非零，通常约17.584505288 SOL；2/18为cashback，0/18为mayhem；
- 项目代码当前没有任何`virtual_quote_reserves`或Pump FeeConfig实现。

官方SDK的`sellBaseInput`使用：

`effectiveQuoteReserve = realQuoteVault + virtualQuoteReserves`

随后按constant product计算输出，结合GlobalConfig/FeeConfig、market cap、canonical identity、creator/cashback语义计算动态费，检查真实vault能否覆盖输出，最后再应用slippage。

因此v6的direct holding-surface风险估值必须：

1. 使用完整当前Pool layout并冻结IDL/SDK hash/version；
2. 分开real vault、virtual reserve、effective reserve与real-reserve coverage；
3. 获取/版本化GlobalConfig与FeeConfig；
4. 用官方SDK golden/differential fixtures验证本地公式；
5. 明确本地direct quote只是持仓面风险估计，Jupiter full-route仍是实际执行权威。

该本地报价可在每次Vault事件后亚秒更新，解决所有仓位不断请求Jupiter不现实的问题；只有post-fill baseline、稀疏校验、ORANGE/RED和真实退出才消耗聚合器请求。

### 2.8 cohort 2306：小步连续恶化不会进入 append-only 事件

cohort `2306`：

- 12账户同入场；
- 约87秒后hard stop；
- 每账户约`-11.881309U`；
- quote vault从baseline降到约62.7%，base vault升到约149%；
- Dex价格先小幅上冲，再在约20秒内由0.0001115跌至0.00006648。

每一次Vault变动都小于现有10% material threshold，因此mutable `onchain_held_account_states`不断被覆盖，append-only risk event中没有保留完整连续路径。结果是：

- Runtime能看到最后状态，却不能计算可靠的1s/3s/10s/30s reserve slope；
- 学习层无法重放“许多小卖单累计形成崩盘”；
- Web会把实际正在恶化的路径显示为HEALTHY。

v6必须建立append-only/windowed `PositionRiskFrame`，至少保存：

- account slot/time、raw amount与delta；
- baseline/high-water/短窗比率；
- quote-out/base-in方向；
- 1s/3s/10s/30s slope与acceleration；
- 与交易流和full-size recovery的同窗关联。

高频原始更新可进入cold Parquet，hot SQLite只保留window aggregate和material state transition，不能继续只留mutable latest state。

### 2.9 LP mint 13/13 固定误报

当前13个具有v5 exact targets的canonical cohort，LP mint账户实际均由Token-2022 program `TokenzQd...`拥有；目标注册却统一写成legacy SPL Token program `Tokenkeg...`，因此13/13初始状态都是：

`ALERT / account_program_owner_mismatch`

该原因当前未被 severe集合触发卖出，但会污染：

- 风险状态和Cockpit；
- 未来hazard特征；
- 错误率/告警率；
- DEAD与rearm研究。

future-only修复应从exact LP mint账户或已冻结surface facts解析真实program owner；历史事件不修改，只在新monitor version中纠正。

### 2.10 当前真实盈利去重后为负且由一个赢家主导

本轮在稍后的自然截面中，v5已有21个底层Token cohort。只对10个所有相关账户均已结束的底层机会取一条代表性20U路径：

- 合计PNL约`-13.579866U`；
- 3胜7负；
- 中位数约`-1.975839U`；
- 均值约`-1.357987U`；
- 最大赢家`+37.913424U`；
- 移除最大赢家后约`-51.493290U`。

同一时点，把策略账户复制结果全部相加却显示约`+225.812907U`已实现PNL。最极端的cohort `2285`只有一个底层Token/一组共享执行报价，却被12账户各记`+37.913424U`，复制合计`+454.961088U`。

因此当前v5不能宣称盈利。它证明执行内核开始工作，同时证明：

- unique opportunity PNL与strategy counterfactual必须分开；
- 12个账户行为等价时必须标记`BEHAVIORALLY_EQUIVALENT`；
- 排名和成熟度只按unique cohort/date/regime与实际策略差异；
- Top1/remove-best分析必须出现在主页，而不是藏在审计页；
- 本轮最需要优化的是左尾和退出延迟，而不是继续复制相同策略卡片。

### 2.11 当前主要延迟在本机调度，不在单次provider响应

对27个v5底层cohort的下一报价链做只读统计：

- source baseline quote完成→下一次BUY quote-simulated fill：p50约8.607s、p90约14.418s、p95约16.249s、最大约22.909s；
- provider单次调用本身：p50约0.526s、p90约2.588s、p95约2.819s、最大约2.852s；
- 最终BUY minimum token output相对source decision quote：6/27恶化超过2%，2/27超过5%，最差约13.95%；
- 27个cohort中仅18个后来取得全仓估值；只有3个在10秒内、8个在60秒内；首次估值p50约208.79s、p95约669.54s。

因此单纯提高Jupiter并发或继续依赖15–20秒轮询不是主解法。应当：

- 缩短source decision→final plan的本地关键路径；
- post-fill立即建立exact local PumpSwap risk quote；
- local event-driven risk连续更新；
- ORANGE/RED时抢占Jupiter full-route；
- BUY、valuation、research和Agent不得挤占SELL；
- 分别记录decision、plan、queue、provider、settlement延迟，不能把所有延迟归给API。

---

## 3. 外部研究与本地结果如何相互印证

### 3.1 Pump-and-dump 的典型价格结构

Li、Shin、Wang 的加密 pump-and-dump 研究发现，操纵事件通常伴随价格、成交量和波动的急升，价格在分钟内见顶并快速反转。Ardia、Bluteau 对 Twitter 与 pump-and-dump 的研究又发现，依赖社交信息的参与者在 dump 后卖得更晚，损失更大。

这与“单主升浪 + 迅速反转”的先验一致，但这些研究不是专门针对当前 PumpSwap 超小盘 universe，因此参数必须以 GXH 自身前向数据校准。

### 3.2 Solana 新 Meme 的风险往往在最早几分钟出现

`Catching the Rug` 使用约 640 万 Solana Token，报告多数高风险特征在发行后一小时内出现，仅前 5 分钟交易特征即可提供很强的早期区分力。`MemeTrans` 覆盖 4 万多个迁移 Token、约 2.1 亿笔前后交易，设计了交易活动、集中度、时序和 bundle 等 122 个特征，并报告模型能够显著降低损失。

这支持把 PumpSwap transaction/account stream 做成 250ms–5m MarketFrame，而不是继续只依赖 5m 聚合 Dex snapshot。

### 3.3 大赢家本身也可能高度操纵

`A Midsummer Meme’s Dream` 对 34,988 个跨链 Meme 分析称，收益超过 100% 的 Token 中约 82.8% 有 wash trading 或 Liquidity Pool-Based Price Inflation 等人工增长迹象，之后常跟随 pump-and-dump 或 rug。

因此不能把“涨得猛”直接当健康。最应该学习的是：

- 它还能否持续吸收真实卖压；
- quote-vault 是否在增长而非被抽干；
- buyer breadth 是否真实；
- 全剩余仓位是否仍能按可接受回收率退出。

### 3.4 极少数右尾决定整体收益

当前项目和外部 Paper 都显示 Meme 策略往往由极少数赢家贡献大部分利润。因此系统必须同时做到：

- 不用过严统一入场门删掉所有右尾；
- 不因一个神币就认为策略成熟；
- 报告 Top1/Top3 贡献和 remove-best-1/remove-best-3；
- 不把同一 Token 复制到 12 个账户后的 PNL 相加为系统利润。

---

## 4. 把“单主升浪”变成严格前向状态机

### 4.1 永远使用运行中高点，不使用未来 ATH

定义：

- `H_t = max(P_s, s <= t)`：截至 t 的运行中可执行或可信价格高点；
- `DD_t = 1 - P_t / H_t`：当前高水位回撤；
- `DDV_t = d(DD)/dt`：回撤速度；
- `TSH_t = t - time(H_t)`：距高点时间；
- `R_t`：指定剩余数量 Jupiter 可执行回收率；
- `QV_t/BV_t`：quote/base vault raw reserve；
- `F_t`：真实买卖资金流向量。

`later ATH` 只能做事后 outcome，不得进入任何当时决策。

### 4.2 交易 regime

1. `DISCOVERY`：Token 被发现，尚无完整 MarketFrame；
2. `IMPULSE`：资金流、交易强度和价格加速；
3. `EXPANSION`：不断创新高且回撤可控；
4. `EXHAUSTION`：价格仍高但 flow/volume/buyer breadth/recovery 不再同步；
5. `PEAK_WARNING`：运行中回撤开始，reclaim 仍可能；
6. `TERMINAL_DECLINE`：持续深回撤、失败 reclaim、卖方流、Vault/recovery 恶化；
7. `DEAD`：exact surface/账户/全仓可卖终态；
8. `DORMANT`：已退出、低活跃观察；
9. `REAWAKENING`：新的独立资金流 burst，注册为新 cohort。

### 4.3 不应只设一个 28% trailing

当前所有动态 Stage 大量共享 `+60% 激活 / -28% trailing`。这既不能代表 12 个策略，也无法适应不同波动和操纵路径。

v6 至少并行四种退出 family：

- `Fast Escape`：早期 recovery/flow/vault 恶化，先减仓或全退；
- `Balanced Harvest`：可解释分批止盈 + hard stop + trailing；
- `Peak Guard`：顶部衰竭 hazard；
- `Research Runner`：仅在机械风险正常时用买后信息决定延长 runner。

### 4.4 推荐的可证伪退出假设，不是最终参数

首轮 challenger 可冻结：

- **A：Persistent-DD**：运行中峰值后持续两帧达到 30% 回撤，且 60–180 秒未 reclaim 90%，全退；
- **B：Flow-confirmed-DD**：20%–25% 回撤 + sell notional reversal + recovery slope/quote-vault slope恶化，先退 50%，继续恶化全退；
- **C：Peak-Hazard**：将 DD、DDV、TSH、flow divergence、volume deceleration、trade-gap expansion、large-sell concentration、Vault 与 recovery slope 合成透明 hazard；
- **D：Exit-and-Reenter**：按 B/C 退出，后续只由 Reawakening 新 cohort重入。

A/B/C/D 共享同一入场才能比较退出。不能从当前少量样本挑一个赢家立即替换 champion。

---

## 5. 12 个真正策略：3 个入场家族 × 4 个退出家族

| Strategy | Entry family | Exit family | 主要问题 |
|---|---|---|---|
| S01 | Broad Launch | Fast Escape | 宽买快跑是否提高期望值 |
| S02 | Broad Launch | Balanced Harvest | 宽买动态基线 |
| S03 | Broad Launch | Peak Guard | 是否减少从高盈到归零 |
| S04 | Broad Launch | Research Runner | 买后信息是否改善 runner |
| S05 | Flow Burst | Fast Escape | 真实资金流触发 + 快逃 |
| S06 | Flow Burst | Balanced Harvest | 纯链 flow 基线 |
| S07 | Flow Burst | Peak Guard | flow + 顶部衰竭 |
| S08 | Flow Burst | Research Runner | flow 入场后信息增量 |
| S09 | Reawakening | Fast Escape | 异动假突破快速退出 |
| S10 | Reawakening | Balanced Harvest | 异动基线 |
| S11 | Reawakening | Peak Guard | 二次浪顶部退出 |
| S12 | Reawakening | Research Runner | 异动后的信息持续性 |

### 5.1 Broad Launch 不应被过度安全门封死

公共 hard blocks 只保留：

- 时序/身份/amount/decimal/program 无效；
- BUY 根本不能形成合法 execution plan；
- exact surface 已 DEAD 且禁止重入；
- dangerous Token capability 导致转账本身不可安全执行；
- portfolio reservation/reconciliation 不成立。

liquidity、creator history、concentration、route opacity、immediate recovery、社交缺失等大部分转成 risk tier/size/exit-speed，不是所有策略统一拒绝。

### 5.2 高风险 Paper 不是高风险 Live

允许 `PAPER_EXPLORATION_ONLY` 账户以固定小 notional 测量被传统安全门拒绝的 Token；它永远不自动获得 Live eligibility。这样既扩大机会，又不把研究结论伪装成可上线资金策略。

### 5.3 Reawakening 独立于首发

必须先有当时可得的 dormant baseline，随后由 volume/trade-rate/buyer breadth/route/recovery/price-flow burst 触发。不能事后看到上涨才补标；不能把 launch Token 填进 Reawakening 增加样本。

---

## 6. 当前 v5 的处置

当前 `chain-meme-trader/v5-order-fill-kernel...` 已有真实自然分母，不得原地改成上述 3×4。

正确处置：

1. 标记 v5 为 `ORDER_KERNEL_PILOT / HISTORICAL-GATE ACCOUNTS`；
2. 保留并继续管理现有仓位；
3. v6 激活时冻结 v5 新入场 frontier；
4. v5 的 Decision → OrderIntent → ExecutionAttempt → quote-simulated Fill 路径作为内核基础继续复用；
5. 不再宣称 v5 已实现 12 个独立策略；
6. 账户 PNL与 unique underlying cohort PNL分开。

cohort 2285 的同一底层路径在 12 个账户各记 +37.913424U，可以用于 policy counterfactual；不能把 +454.961088U 当系统赚到的钱。相同行为必须标记 `BEHAVIORALLY_EQUIVALENT`，不重复排名、不增加独立样本数。

---

## 7. 所有持仓共享 RiskKernel，而不是只有 Stage 11/12 才监控

当前 `enroll_onchain_held_account_targets()` 对 ChainMemeTrader 只选择 Stage 11/12。cohort 2286 因只进入 Stage 1而没有任何 target，这正是架构错误。

v6 的原则：

- Pool/Vault/Mint/LP/route/recovery 是公共持仓风险事实；
- 策略差异决定如何响应，不决定是否拥有雷达；
- position Fill 后原子/立即注册 exact targets；
- 任何 target 缺失必须成为显式 risk coverage gap；
- 同一 pool 只订阅一次，事件 fanout 到全部相关账户；
- Stage/Strategy 不重复订阅。

风险状态：

- `GREEN`：账户与 route fresh；
- `YELLOW`：一个来源 stale 或轻度恶化，提高频率；
- `ORANGE`：flow/recovery/vault组合异常，停止加仓并立即 full-size SELL preflight；
- `RED`：大额 sell burst、quote-vault collapse、recovery collapse，抢占所有非退出任务并全退；
- `DEAD`：exact terminal，最终一次逃生后永久关闭。

任务优先级：

`DEAD/RED SELL > ORANGE preflight > held-position valuation > BUY > discovery hydration > research/Agent/UI`

不能让共享 Jupiter 三请求预算被 BUY、普通估值或研究占满后，把关键 SELL 推迟。

---

## 8. 低延迟：20 秒 collapse 要求事件流，不是更勤快地轮询 Dex

当前 5 秒 Runtime 周期、15–20 秒 DEX/Jupiter 估值无法稳定处理 cohort 2286。

### 8.1 数据面

- primary：Solana Geyser/Yellowstone transaction + account stream；
- secondary：独立 provider 或 RPC WebSocket；
- fallback：当前公共 accountSubscribe/HTTP/DexScreener；
- exact PumpSwap instruction/account decoder；
- 250ms/1s/3s/10s/30s/60s/5m MarketFrame。

Solana 官方材料说明 Yellowstone/Geyser 可推送账户、交易、slot 等更新，典型延迟低于普通 WebSocket。它应作为 provider benchmark 候选，而不是立即绑定单一供应商。

### 8.2 MarketFrame 首批特征

- base/quote vault raw reserve 与 delta；
- signed quote-asset inflow/outflow；
- buy/sell token/notional；
- trade intensity / inter-trade gap；
- same-slot burst；
- largest sell、top3/top10 sell share；
- fee-payer/funder/buyer breadth lower-bound；
- price velocity/acceleration/high-water drawdown；
- recovery ratio/price impact/route quality slope；
- creator/bundle/sniper/wash/LPI proxies；
- feed lag、slot gap、provider disagreement。

### 8.3 目标 SLO（工程目标，不是当前成绩）

- chain event → decoded frame p95 <250ms；
- frame → deterministic risk decision p95 <10ms；
- RED → exit intent p95 <20ms；
- exit intent → build request p95 <100ms；
- build/submit按供应商真实地区基准；
- confirmation与reconciliation显式记录。

---

## 9. Paper 与未来 Live 必须是真正同流程

当前 Jupiter `/order` 不带 `taker` 时只返回 quote；v5 把下一次 minimum output 命名为 Fill，属于 `QUOTE_SIMULATED_FILL`，不是 buildable transaction 或真实成交。

v6 ExecutionQuality 分级：

1. `L0_QUOTE_ONLY`：amount-specific quote；
2. `L1_BUILDABLE`：带 public taker，获得可构建 transaction/instructions；
3. `L2_SIMULATED`：RPC simulation成功，记录 logs/CU/fee/account changes；
4. `L3_PAPER_FILL`：按真实构建延迟、下一可得报价、失败交易成本和 minimum output保守结算；
5. `L4_LIVE_CONFIRMED`：签名、发送、confirmed/finalized、getTransaction、余额与费用对账。

统一域模型：

`MarketFrame → StrategyDecision → StrategyIntent → PortfolioAllocation → ExecutionPlan → VenueAttempt → Ack/Signature → Confirmation → Fill → Position → ExitIntent → Settlement → Reconciliation`

Paper 与 Live 只替换 adapter/signer；不是两套策略代码。

### 9.1 Jupiter 两条路径都要比较

- Meta-Aggregator `/order(taker) + /execute`：多个 router 竞争，Jupiter管理 landing/RTSE/Beam/confirmation；
- Router `/build + /submit` 或自有 sender：更可控，可加入自定义指令，但 route 范围与责任不同。

以 build success、simulation success、landing、confirmed output、latency、成本和 adverse selection做前向 A/B，不预设赢家。

### 9.2 真实费用

- Jupiter 对新 Token 的平台费可能高于一般 pair，并已在 quote 中体现；
- PumpSwap canonical fee 自 2026 年起按 market cap动态变化，不应继续把固定 125bps 当永久真实事实；
- route/pool/platform fee若已进入 outAmount/minimum output不得再双计；
- network fee、priority fee、rent/ATA、失败交易费单列；
- 真实结算以 confirmed transaction balance delta为准。

### 9.3 Signer

- 独立最小 signer process/hardware-backed key；
- Strategy、Agent、Web、SQLite永远不看 private key；
- signer只接受 plan hash、mint、amount、min output、expiry与 allowlisted policy；
- Live仍需用户另行显式授权。

这不是拖延 Live，而是现在把上线必需路径做对，资本开关以后再打开。

---

## 10. 买后 Agent：共享、异步、只有能改变未来动作时才调用

每 Token/cohort 一个 `InvestigationCase`，12 个策略引用同一结果。最多两条角色：

1. Narrative / Identity / Diffusion；
2. Adversarial / Manipulation。

Pool、Vault、flow、route、holder arithmetic全部 deterministic local code。

Agent只在：

- position仍开放；
- runner可能因结果改变；
- 剩余持有时间覆盖调查延迟；
- 同 source/revision没有现成结果；
- 期望信息价值高于成本；

才调用。结果只能作用于 `completed_at` 以后的持有/runner，不得阻止 RED/DEAD SELL。

---

## 11. 盈利统计必须去重

三套 PNL永久分开：

- `strategy_counterfactual_pnl`：12个账户的策略反事实；
- `portfolio_paper_pnl`：同一底层订单净额化后的组合 Paper；
- `live_confirmed_pnl`：Mainnet余额对账后的真实利润。

主要样本单位是 unique `Token/pool/entry-time cohort`。同一 Token 的 12 个账户不是 12 个独立市场样本。

必须报告：

- net executable PNL；
- PNL/capital-hour；
- expectancy、median、profit factor；
- max drawdown、CVaR、连续亏损；
- no-route/build/sim/confirm/writeoff；
- Top1/Top3贡献；
- remove-best-1/3；
- date/regime/creator/pool/entry family；
- rejected/not-evaluable counterfactual；
- opportunity lost to queue/latency。

基础设施缺失（例如 `request_evidence_missing`）应为 cohort-level `NOT_EVALUABLE`，不能扩成12个策略 alpha reject。

---

## 12. 存储、恢复与上市级运行

当前主库约 5.7GB、WAL约 930MB、203 tables、344 indexes；Python SQLite runtime为3.51.0。

SQLite官方2026年说明：WAL-reset bug影响3.7.0–3.51.2，3.51.3及以后修复。当前版本在受影响范围。

P0：

1. Online Backup API创建E盘一致性快照；
2. 副本quick_check/integrity_check；
3. 升级SQLite runtime到已修复版本；
4. 记录`wal_checkpoint(PASSIVE)` busy/log/checkpointed；
5. 找最长Web/read transaction；
6. 设计reader gap和受控checkpoint，不在活动库盲目TRUNCATE/VACUUM；
7. restore drill；
8. hot operational DB / cold Parquet分层；
9. Web只读有界projection，不扫全库。

高频frame/transaction/account delta归档到daily Parquet；研究查询用DuckDB/Polars或后续时序数据库，订单/仓位/风险真值继续留在热库。

---

## 13. Web：Trading Cockpit

首页第一屏：

- Runtime/feed/DB/clock/signer/reconciliation；
- discovery/frame/intent/build/fill/exit pulse；
- unique-cohort executable PNL；
- open positions风险热图；
- RED/ORANGE/SELL queue；
- latency p50/p95/p99；
- feed slot gap/provider divergence；
- Live lock；
- 成熟Top3，否则`LEARNING / UNRANKED`。

页面：

- `/cockpit`
- `/strategies`
- `/execution`
- `/risk`
- `/learning`
- `/tokens/:id`
- `/system`
- `/chains`
- `/history`

浏览器刷新绝不触发RPC/Jupiter/Agent。

---

## 14. 多链

Solana公共内核稳定后，按BSC → Robinhood执行：

### BSC

- 0x `/price` indicative；
- `/quote` firm/buildable；
- taker/allowance/balance/tax；
- simulationIncomplete；
- gas/nonce/replacement/receipt；
- router allowlist；
- round-trip cost与reconciliation。

### Robinhood Chain

- chain id 4663、Arbitrum L2、ETH gas；
- 0x已支持Swap/Gasless/Cross-chain；
- 官方`/rhj/assets` exact address排除Stock Token/RWA；
- L2 gas + L1 data fee；
- sequencer/RPC lag与downtime；
- first-come sequencing；
- 仍走Research → Paper → explicit micro-Live。

不能复制Solana费率或把Robinhood App API和Robinhood Chain混为一谈。

---

## 15. Codex有序执行 Tranches

### T0｜权威与当前版本处置

- 固化官方插件名称；
- v5标记order-kernel pilot；
- v6 activation前v5继续自然运行，v6激活时停止v5新入场、旧仓继续退出；
- 修复unique-cohort vs copied-account PNL；
- infrastructure-not-evaluable语义。

### T1｜所有持仓风险覆盖与退出抢占

- 所有策略仓位挂exact targets；
- 同pool单订阅、事件fanout；
- post-fill immediate full-size SELL heartbeat；
- SELL/RED独立优先预算；
- 将cohort2286做成不可变测试fixture；
- price stall只为suspicion，Vault/recovery collapse可RED，exact terminal才DEAD。

### T2｜v6 3×4策略矩阵

- 新registration/account/activation；
- Broad/Flow/Reawakening；
- Fast/Balanced/Peak/Research；
- behavior equivalence检测；
- no backfill。

### T3｜PumpSwap transaction decoder与MarketFrame

- exact buy/sell/fee/vault flow；
- 250ms–5m窗口；
- low-latency provider benchmark/failover；
- peak-death和reawakening shadow features；
- champion阈值不在线自改。

### T4｜Execution Quality L0–L4

- public taker、buildable order；
- simulation；
- plan/attempt/confirmation/reconciliation；
- external signer interface locked；
-真实fee/TCA。

### T5｜连续学习、存储、Cockpit

- unique cohort outcome；
- champion/challenger；
- rejected counterfactual；
- SQLite升级/backup/restore/hot-cold；
- OTel trace/metrics/log；
- Web重构。

### T6｜BSC与Robinhood

- EVM adapter；
- 0x firm quote/simulation/cost；
- Robinhood RWA exact exclusion；
- chain-specific Paper maturity。

### T7｜显式授权后的Live progression

- Devnet/isolated signer验证；
- Mainnet safe-asset execution-only验收；
- 用户显式授权micro canary；
- TCA/reconciliation通过后逐级扩大。

---

## 16. 本轮最重要的产品决策

1. **用户的单主升浪判断应进入 active hypothesis。**
2. **不是把30%写成所有策略的固定死规则，而是立即注册一组Peak-Death/Exit-and-Reenter challenger。**
3. **一旦持续深回撤且reclaim/flow/Vault/recovery同时失败，默认退出；以后由Reawakening重新买。**
4. **Broad入场继续，但所有仓位共享最高级别风险雷达。**
5. **低延迟退出比再加一层静态买前门更接近盈利目标。**
6. **v5内核有真实进展，但12策略定义仍未完成；用v6纠正，不改v5历史。**
7. **上市级不是更多防御，而是真实订单、确认、对账、恢复、可观测、数据完整性与有界资本。**

---

## 17. 外部依据

- Li, Shin, Wang, *Cryptocurrency Pump-and-Dump Schemes*：分钟级见顶与快速反转。
- Ardia, Bluteau, *Twitter and cryptocurrency pump-and-dumps*：dump后延迟卖出损失。
- Li et al., *Catching the Rug*（2026）：640万Solana Token，前5分钟特征与一小时风险。
- Hu et al., *MemeTrans*（2026）：4万+迁移Token、2亿+交易、122个交易/集中度/时序/bundle特征。
- Mongardini, Mei, *A Midsummer Meme’s Dream*：高收益Meme中的wash/LPI与后续提取。
- Pump官方费用与bonding-curve/canonical-pool文档：canonical liquidity protocol-owned，但交易流仍可抽干quote reserve；fee动态变化。
- Jupiter Swap V2官方`/order + /execute`、`/build + /submit`文档：无taker只有quote；execute包含landing/confirmation结果。
- Solana官方RPC/Geyser文档：sendTransaction不等于confirmed；Yellowstone/Geyser提供账户和交易低延迟流。
- SQLite官方WAL/Backup/2026 WAL-reset修复说明。
- 0x、Robinhood Chain官方文档：firm quote、chain 4663、EVM/ETH gas、Stock Token APIs。

外部研究只用于建立假设；最终策略晋级仍只认GXH自己的严格前向、金额特定、成本完整、unique-cohort结果。

---

## 18. 2026-09-04 03:16 JST 增量：回撤阈值面、Fill 成本真值与干净前向实验

本节冻结于 `2026-09-03T18:16:02Z` 的 r6 只读截面。它只用于设计以后新注册版本，不修改 v5/v1 历史，也不把描述性价格路径当成可执行收益。

### 18.1 先纠正分母：约 4,084 是覆盖组，不是全部先涨组

原分析中的约 4,084 指满足“Solana、正价快照不少于 10 个、观察跨度不少于 30 分钟”的覆盖合格 Token group。当前更新截面为 4,102 个；其中 393 个从首个本地快照到运行中高点至少上涨 25%，才有资格进入本次回撤事件搜索。不得把覆盖分母、事件候选和 horizon 可评估分母混成一个数字。

### 18.2 3 分钟持续回撤阈值面

对 Pump 地址子集，要求首次达到回撤阈值后 3 分钟内至少有第二个观测仍低于同一运行中高点阈值，并保持 horizon 完整经过。结果如下：

| 持续回撤 | 60m 可评估 n | 60m 再创新高 | 240m 可评估 n | 240m 再创新高 |
|---:|---:|---:|---:|---:|
| 15% | 77 | 2.60% | 49 | 10.20% |
| 20% | 75 | 4.00% | 48 | 10.42% |
| 25% | 72 | 4.17% | 46 | 10.87% |
| 30% | 71 | 2.82% | 45 | 6.67% |
| 35% | 62 | 3.23% | 39 | 5.13% |
| 40% | 55 | 1.82% | 34 | 2.94% |

解释：

1. 15%–25% 可以更早保护高水位，但在 240 分钟内约有一成样本后来再创新高；不能直接成为所有策略的无条件退出。
2. 30% 把当前 Pump 子集 240 分钟再创新高率降到约 6.67%，与此前独立复算的 6.82% 基本一致，是可研究的中间点，不是普适常数。
3. 40% 更接近“主升浪结束”，但相对 30% 已额外回吐 10 个百分点；只有在低延迟风险系统缺少其他信息时才可能成为深度兜底，而不是理想盈利退出点。
4. 1 分钟持续确认在当前 Pump 子集的 30% 回撤上得到 60/240 分钟再创新高 0/0（n=43/22），但样本小、采样频率选择性强，不能据此直接冻结生产阈值。
5. 当前所有结果仍基于 Dex 路径而非实际持仓数量的可执行权益；它们只支持 hazard 方向，不支持账户 PNL 参数。

### 18.3 例外更支持 exit-then-reenter

在 3 分钟持续确认的 Pump 子集中：

- 20%/25% 回撤后、240 分钟内再创新高的例外时间约为 14.2、26.0、46.4、157.7、190.8 分钟；
- 30% 回撤后对应约为 14.2、46.4、185.5 分钟；
- 当前没有一个在触发后 10 分钟内再创新高。

因此，第一次持续深回撤中继续持有并不是捕捉第二波的必要条件。更符合资金效率的路径是：退出旧 position，只有新 buyer/flow/liquidity/executable-route impulse 成立时建立新的 `REAWAKENING` cohort、OrderIntent 和成本基准。旧池已 exact DEAD 时，同一 surface 永不 rearm；新 pool/surface 才是新 cohort。

探索性分层又显示：30% 回撤时 Dex liquidity 仅剩峰值 25% 或更低的 Pump 可评估小组 n=8，240 分钟 0 个再创新高且 8/8 继续跌破旧峰值 50%。该结果方向强但样本极小、liquidity 字段缺失多，而且 Dex liquidity 不能替代 exact real-vault/effective-depth；只能作为 Peak-Death hazard 的候选权重，不能立即成为全局硬门。5m buy-share 分层样本同样小且非单调，暂不冻结阈值。

### 18.4 v5 退出经济基准已被证伪

对 23 个自然 `stage_04_dynamic_v1` BUY，实际 20U debit 与保守 Fill token amount 可还原真实 Fill unit cost；`entry_signal_price / actual_fill_unit_cost` 的中位数约 0.946339，范围 0.721314–1.507246，22/23 偏差超过 2%，3/23 超过 10%。当前 v5 却用成交前 `entry_signal_price_usd` 计算 hard stop、TP、trailing 和 running high。

更直接地，12 个有任何 full-initial-amount 可执行估值覆盖的 Stage-4 cohort 中，5 个触发并成交名义 `+80% TAKE_PROFIT_1`，但没有一个已记录的全仓最低可执行权益高点达到 +80%。cohort `2314` 是反方向错误：信号价比实际 Fill unit cost 高 50.7246%，旧控制把实际约 +80.50% 的价格高点只看成 +19.76%，没有 TP/trailing，最后以 `-13.458007U` 平仓；同 Fill 的 executable-decay v1 在全仓 recovery 41.283448U 后回撤，下一 quote 保守成交为 28.263148U，PNL `+8.263148U`。

所以：

- v5/v1 仍保留为真实订单内核和缺陷发现流；
- 所有策略比较标记 `EXIT_BASIS_INVALID / LEARNING / UNRANKED`；
- 历史不重算、不改写；
- `entry_signal_price` 永远只作 alpha/速度/市场状态特征；
- 新版本账户真值必须来自 `total_entry_debit`、实际 Fill amount、realized proceeds、exact remaining raw、timely full-remaining minimum executable recovery 和未嵌入成本。

### 18.5 两条分离的前向实验

#### 实验 A：干净的利润保护 trailing pair

两臂必须：

- 引用完全相同的 source BUY Fill id、时间、20U debit、保守 token amount、mint decimals 与 route evidence；
- 消费同一个 `PositionEquityFrame` 和相同 observation timestamp/cadence；
- 共享 hard stop、liquidity/inactivity/max-hold、所有 partial TP、RED/DEAD 与 next-result Fill；
- 高水位使用 `realized_proceeds + remaining_min_executable_recovery - pending_nonembedded_costs`；
- 共同在 actual economic return `+40%` 后 arm；
- control 仅使用 28% executable-equity drawdown，treatment 仅使用 15%；
- 不同时改变 arm threshold、quote cadence、cost basis、TP 或 Agent。

该 pair 只回答“在相同经济真值和安全包络下，15% 是否优于 28% 利润回吐”；当前 cohort 2314 的 +21.721155U 差值不能被重新包装成该单变量估计。

#### 实验 B：Peak-Death hazard observer→challenger

先 append-only observer，输入只允许当时可见：

- executable-equity drawdown、1s/3s/10s slope/acceleration；
- real quote-vault outflow 与 effective-depth decline 分离；
- base-vault inflow、signed value flow、large-sell burst、trade inter-arrival；
- failed reclaim count/time；
- full-size route/recovery deterioration、quote age/confidence；
- buyer breadth/5m buy-share 仅作低频辅助。

预注册观察候选：

1. `20%–25% early hazard`：只有 drawdown 持续且至少一个 exact Vault/flow/recovery/reclaim 恶化条件成立才升级 ORANGE/RED；
2. `30% persistent fallback`：即使辅助字段缺失，也作为深回撤逃生候选；
3. `40% catastrophic fallback`：研究监控或报价缺失时是否仍能减少归零尾部，但不作为追求峰值捕获的主规则。

先报告 sensitivity/specificity、MFE giveback、peak→intent、intent→request、provider/next-result latency、false-exit 后 reawakening 可重入率；达到严格前向分母后才选择一个 challenger，禁止把整个阈值网格同时上线并事后挑赢家。

### 18.6 当前实施顺序再次确认

1. v1 停止新 enrollment，旧仓受显式版本化 universal safety overlay 管理并标记不可与纯 v1 配对；
2. 当前 301-byte PumpSwap decoder、Global/Fee config、real-flow/effective-depth、本地 exact-remaining risk quote；
3. exact-PASS 之外也必须有显式 all-position coverage state，连续 append-only risk frame 与 RED SELL reservation；
4. actual-Fill `PositionEquityFrame`；
5. 实验 A 的 clean pair；
6. 实验 B observer 和 v6 3×4 真正独立策略；
7. execution L0→L4、unique/netted PNL、storage recovery、Trading Cockpit；
8. 复用内核后扩 BSC/Robinhood。

这条顺序的目的不是增加防御，而是让宽入场产生的右尾能够兑现、让左尾更早停止、并让每次所谓“盈利改善”都有可复核的经济含义。
