[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-024100-OPEN-R1-STRATEGY_DISCOVERY-RESULT  
REPLY_TO: C2C-20260907-024100-OPEN-R1-STRATEGY_DISCOVERY  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: STRATEGY_DISCOVERY  
SENSITIVE_DATA: NONE  
DISPOSITION: **OPEN_NEW_MECHANISMS / NO_ALPHA_CLAIM / READ_ONLY**

本轮实际通过官方隧道只读 `E:\memeTrader`。未修改代码、DB、Runtime，未跑全历史SQL，未创建writer/平台。当前Chat可核验模型为 **GPT-5.6 Sol**；具体reasoning档位没有可靠运行元数据，记 **UNKNOWN**。

实际重点读取：

- `ROUND2/RESEARCH_REQUEST.md`
- `CURRENT_OBJECTIVE_AND_PLAN.md`
- `src/memetrader/capital_policies.py`
- `capital_entry.py` 相关机制索引
- `capital_exits.py` 的 `earn_the_hold / failed_continuation_profit_lock / price_to_flow_fragility`
- `capital_cross_section.py` 机制入口
- 当前 `research_finalists.py`、上一轮已知12机制合同通过前序R3事实复用
- 对当前代码做定向grep，核对 `reentry / reclaim / ranker / fragility / runner / liquidity_leads_price / progress_clock` 等已存在行为，避免换名重复。

事实边界：当前214策略、上轮8臂已部署；ROUND2其他本地新统计/外部报告此刻尚未落目录，因此以下是**代码机制缺口+冻结历史证据驱动的首轮假设**，不是新统计结论。

## 一、我认为当前真正遗漏的首要行为：**Signal→Fill 追价否决**

### 1. `post_signal_chase_guard`

**行为：信号成立后，不保证下一有效帧一定BUY。**

当前严格前向模式普遍是：

`signal frame → next independent frame → BUY`

这是因果正确的，但缺一个很实际的经济问题：

> 如果下一帧已经暴涨很多，原信号的edge可能已经被市场吃掉，系统仍按新市场价再+4%买。

代码已经保存 `entry_signal_price_usd` 与实际后帧市场价，但我没有找到通用“signal→fill涨幅太大则取消本次机会”的策略机制。

**假设：** Meme的很多信号在15–60秒内高度凸；追到第二段末端会把正确方向判断变成负EV。

**最小数据：** 已有signal snapshot、next original-pool frame、当前成本配置。零新API。

**严格时序：**
- signal冻结；
- 下一有效同池frame出现；
- 计算 `post_price/signal_price-1`；
- 如果已经消耗了预注册的大部分成本后空间，则 `REJECT_THIS_OPPORTUNITY`，不排队、不回补；
- 其他账户照旧。

**反证：** 被取消的机会后来仍大量继续暴涨，且买入后扣成本收益显著好于guard。

**下一自然验证：** 与完全同signal的普通next-frame entry做paired **BUY vs NO-BUY opportunity outcome**。

这是我本轮优先级最高的新方向之一，因为它不是预测更多赢家，而是直接攻击**真实可执行时点的负选择**。

---

## 二、**L0价格脆弱性 No-Buy**，不是再做momentum

### 2. `l0_mark_fragility_v1`

已有：

- volatility-normalized momentum；
- actual-flow `price_to_flow_fragility` exit；
- price→liquidity追认。

但缺一个只用现有L0的：

> **价格涨得“太容易”时不买。**

定义不是“涨太多”，而是近期：

`价格位移 / (rolling volume ÷ liquidity)`

异常高。

直觉：同样+15%，如果伴随大量成交和可见深度，和少量活动就把薄池mark推飞是两种市场。

**事实来源：**
- 当前已有 `volume`, `liquidity`, price序列；
- `capital_policies.py` 有真正actual-flow的fragility，但它依赖金额证据，不能覆盖普通L0；
- volatility策略反而寻找强位移，不承担“过度脆弱则否决”的角色。

**假设：** 极高L0 price elasticity的上涨更易回吐/被20U轻量模型高估。

**实现：** observer已有历史纯函数；5U candidate与原signal baseline配对，不新增请求。

**反证：** 极高fragility组反而贡献稳定右尾，guard主要删赢家。

注意命名必须是 `reported-market fragility`，不能叫真实price impact。

---

## 三、**边际活动失效**：在价格真正下跌之前退出

### 3. `marginal_response_decay_exit`

上一轮 `activity_failure` 是：

> 活动增强 + 价格已经连续下降 → EXIT。

我认为还漏了更早的阶段：

> 成交/买笔继续增加，但每一份新增活动带来的价格增量越来越小，最后接近0。

即：

`Δprice / Δactivity` 连续衰减，

但尚未要求price<prior。

这是典型的“越来越多成交却推不动价格”。

**与已有行为差异：**
- 不等于activity_failure，因为价格还没跌；
- 不等于progress_clock，因为它明确要求活动上升；
- 不等于price-to-flow fragility，后者研究“涨得太多而资金支持不足”，这里是反方向“投入活动增加但边际响应消失”。

**最小输入：** 连续price、m5 volume、buys/sells；无需真实资金流。

**风险：** m5是滚动窗口，机械滚入滚出可能制造假导数。需要连续多帧且时间间隔固定范围，不用单delta。

**验证：** shared-entry exit paired；重点看是否在公共hard-stop前减少下尾，同时是否过早杀掉盘整后的第二腿。

---

## 四、**流动性收缩但价格暂时没跌**的风险机制

### 4. `depth_contraction_price_resilience_guard`

现有上一轮有：

`price↓ + liquidity↑ → exit`

也有旧Vault真实withdraw类机制。

缺的是L0层：

> `reported liquidity` 连续下降，而价格仍平/涨，活动没有同步消失。

我不把它解释为“LP正在rug”；这可能是：

- 报价尺度变化；
- 价格机械影响美元liq；
- LP调整；
- 池逐渐变薄。

但对当前轻量Paper而言，它有一个直接意义：

> **市场mark看起来还强，但线性±4%成交假设的可信余量正在恶化。**

可做两种独立行为，我建议先只做一种避免重复：

**已有持仓风险退出 challenger**，而不是入场硬门。

**反证：** liquidity contraction经常只是上涨过程中正常美元口径变化，候选持续砍掉最大赢家。

零新API，O(1)持仓state。

---

# 五、当前runner体系真正的空白：**部分兑现以后重新取得持有资格**

### 5. `post_harvest_runner_requalification_v1`

当前有：

- conditional runner；
- principal-lock；
- earn-the-hold；
- profit-budget；
- trailing。

但这些主要决定“什么时候第一次留runner”或通用持有。

缺一个明确状态机：

`首次部分兑现 → runner进入PROBATION → 必须重新证明自己值得继续占资本`

例如第一次半卖以后：

- 不立即看之前的峰值；
- 重置runner epoch；
- 后续一定时间内必须产生**新的净经济值高点**，并保持基本activity/liquidity；
- 未重新qualify则卖余仓；
- qualify后再使用普通trailing。

这与“profit lock”不同：

> profit-lock在保护已有利润；  
> runner requalification问的是**已经收割一次以后，这个余仓还值不值得继续作为runner存在**。

**最小实现：** 现有partial SELL、realized proceeds、economic value、mark历史即可；无需修旧profit-lock布尔状态。

**反证：** 被probation卖掉的余仓恰好是右尾主要来源。

这是我认为很有价值的动态持有实验。

---

# 六、**机会成本退出**，而不是单币自己决定一切

### 6. `slot_replacement_challenger`

当前已有 `finite_capital_ranker_v1`，但主要是**新机会入场选择**。

我没有看到明确机制：

> 4个仓位已满时，一个旧仓长期无进展，而此刻出现明显更强的新候选；是否应该卖掉旧仓释放slot？

现在的position exit主要由自己的：

- stop；
- TP；
- trailing；
- maxhold；
- L0状态

决定。

但真实有限资本目标还存在：

`hold old mediocre position` vs `pay another round of cost to enter stronger new opportunity`

这是不同的组合问题。

### 第一版不要自动换仓

我建议先 **Shadow challenger**：

当：
- 旧仓满足“弱进展但未触发exit”；
- 新机会被slot拒绝；
- 现有cross-section ranker认为新候选显著更高；

只记录：

`WOULD_REPLACE incumbent → challenger`

然后固定5/15分钟比较：
- 保持旧仓的实际后续价值；
- 新机会的冻结next-frame模拟路径；
- 额外一轮交易成本。

如果长期明显支持，才设计真正Paper换仓。

**原因：** 直接实现自动switch会把entry/exit/portfolio三件事耦合得太快。

这是214机制中我认为明显缺少的**组合层行为**。

---

# 七、同Token反复交易的成本问题：**Churn Budget**

### 7. `same_token_roundtrip_budget_v1`

项目已有：

- fast-stop reclaim；
- wave reset reentry；
- reawakening。

它们允许正确的新episode再次交易，这是合理的。

但缺的约束是：

> 同一个Token已经连续贡献多次小亏时，新的“正确形态”是否值得继续重复支付8.33%左右的round-trip成本带？

这不是永久黑名单，也不是“亏过就不买”。

建议建立**前向成本预算**：

- 每个arm/token保留本资金期已实现交易成本后PnL及完成episode数；
- 新episode仍必须独立成立；
- 若此前多次roundtrip全部未跨成本，下一次先进入Shadow，而不是继续Paper；
- 一旦Shadow形成足够强的新episode，再重新开放。

**假设：** 某些币在噪声阶段不断产生技术上不同的reclaim/reset，却每次都不够支付成本。

**反证：** Meme右尾主要来自同token第3/4次重启，budget会系统性切掉大赢家。

**注意：** 不能把历史亏损当未来价格特征；它只是**有限资本/重复交易成本状态**，因此更适合作为独立Paper/Shadow treatment，而非“alpha信号”。

---

# 八、不同时间尺度：**速度自适应持有，但不按钟点找alpha**

### 8. `impulse_duration_class_v1`

现在大量规则各自固定：

- 5m
- 15m
- 30m
- 60m
- 240m

但市场的真正差别可能不是UTC时间，而是：

> **这次impulse用了多长时间形成？**

例如同样+20%：

- 30秒完成；
- 6分钟完成；

其后续风险可能完全不同。

新机制不是重新调maxhold，而是在入场前/入场时冻结：

`signal formation duration`

再映射到**预注册的不同持有处理**：

- very-fast impulse → 更短probation/更快利润保护；
- slow orderly impulse → 给更长时间；
- control统一固定hold。

已有80帧/20分钟足够做数分钟尺度。

**假设：** 市场“速度”本身决定最合理的exit horizon。

**反证：** duration分层没有稳定增量，只是换了一种描述volatility的方法。

这个方向比“北京时间几点赚钱”更符合用户要研究的时间差异，也不做事后最佳小时搜索。

---

# 九、一个我建议明确不做的新方向

**不要再增加 `volume / buys / liquidity ≥ X` 类硬阈值策略。**

事实依据：

- `TOKEN_PRECURSOR_EVIDENCE`上一轮已经显示这些边际关联在chain/time/age/liquidity分层后很不稳定；
- 当前代码已经有大量volume/count/buy-share/pressure/relative/volatility组合；
- 再加阈值大概率只是parameter spray，而不是新机制。

同样暂不增加：

- 新KOL总分；
- “聪明钱包score”；
- 当前网页叙事分；
- 新的LP-rug万能门；
- entry×exit全笛卡尔积。

---

# 首轮优先级

如果只选择最有信息增量、当前架构最便宜的4项，我排序：

**P1 — `post_signal_chase_guard`**  
直接解决信号正确但成交太晚的问题；零新增数据，最贴近成本后真实盈利。

**P2 — `post_harvest_runner_requalification`**  
解决“第一次赚钱以后余仓为什么还值得继续拿”的空白。

**P3 — `marginal_response_decay_exit`**  
尝试比price真正转跌更早识别动量衰竭。

**P4 — `l0_mark_fragility`**  
专门攻击薄池“涨得太容易”的假强势，不重复普通momentum。

第二梯队：

- depth-contraction resilience risk；
- impulse-duration hold treatment；
- slot replacement Shadow；
- same-token roundtrip budget。

所有这些都应：

- 新ID；
- 新真实frontier；
- 5U；
- 优先共享同机会对照；
- 无新API；
- old214全部保留；
- 不初始化；
- 不Live；
- 不用历史赢家重算阈值；
- 自然结果成熟后才讨论经济有效性。

本首轮没有任何新策略获得alpha/放大资金资格。
