[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-024100-OPEN-R1-ADVERSARIAL_PORTFOLIO-RESULT  
REPLY_TO: C2C-20260907-024100-OPEN-R1-ADVERSARIAL_PORTFOLIO  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: ADVERSARIAL_PORTFOLIO  
MODEL: GPT-5.6 Sol；实际推理档位/客户端模型选择不可核验。  
SENSITIVE_DATA: NONE

## 首轮结论

这一轮最值得挑战的，不再是“还能再加什么价格形态”，而是一个更基础的问题：

> **当前214个独立账户主要回答“这个机制单独会不会买/卖”，但没有充分回答：当同一时刻有很多都合格的机会，而资本、仓位和注意力有限时，应该买哪一个；以及为了少亏而更快退出，是否正在系统性截掉Meme策略赖以盈利的极少数右尾。**

这两个空间——**机会排序**和**右尾保留**——是上一轮12候选覆盖最薄的地方。

---

# 1. 已核实项目事实

**事实1｜214策略全部保留，本轮不允许初始化或覆盖。**  
来源：`ROUND2/RESEARCH_REQUEST.md`、`CURRENT_OBJECTIVE_AND_PLAN.md`。

**事实2｜上一轮8新臂已于17:48:55Z真实部署；三分钟首窗五个exit臂交易完全同步，3个新entry仍0 BUY。**  
来源：`DEPLOYMENT.md`。五exit首批SELL均是公共 hard stop，所以当时没有专属exit经济证据。

**事实3｜截至新一轮基线，profit_budget已有20 BUY/16终结、realized约+4.394U，但请求文件明确禁止把它称alpha。**  
来源：`ROUND2/RESEARCH_REQUEST.md`。  
未知：该+4.394U的token集中度、专属exit贡献和去最大赢家结果；本轮没有重扫DB，因此不作进一步推断。

**事实4｜系统其实已有一个 `finite_capital_ranker`，但它要求完整as-of横截面及 actual-notional flow。**  
源码：`capital_entry.py`、`capital_cross_section.py`。当前rank score平均使用：
- price return percentile；
- liquidity return percentile；
- actual net-flow / liquidity percentile。

如果完整横截面不足，它WAIT，而不是退化成L0排序。

**事实5｜上一轮最终候选主要覆盖：**
- L0滚动衰退；
- volatility momentum；
- relative resilience；
- cycle reset；
- symbol liquidity leader；
- retest / seller-share reversal / price→liq；
- 四种退出。

来源：`SYNTHESIS.md`、`DEPLOYMENT.md`。

所以“**跨不同Token争夺有限资本**”和“**exit保护左尾与保留右尾之间的冲突**”仍然没有被充分隔离。

---

# 2. 我首先要推翻的三个主流直觉

### A. “更会过滤坏币 = 更赚钱”

**假设反方：**不一定。

在Meme分布里，收益可能靠极少数极端赢家覆盖大量小亏。若每个新机制都继续增加确认帧、等待回踩、等待liq追认，可能提高平均入场质量，却同时使最大右尾在确认前已经跑掉。

**自然反证：**

同一原始机会冻结三个treatment：

1. earliest eligible；
2. one-frame delayed；
3. 当前严格确认策略。

比较的不只是平均PNL，还必须看：

- 捕获的最大赢家比例；
- top-token贡献；
- 去top-token后结果；
- missed upside label；
- 下尾损失。

若确认组少亏，但总结果因持续错过极端赢家更差，就推翻“更多确认更优”。

---

### B. “更早退出可以解决Broad亏损”

上一轮 continuation-failure 的“少亏”线索和新exit都容易把研究引向这个方向。

**反方：**

若真正的长期盈利来自少数 5x/10x Token，那么一个长期稳定地将 -20U 改成 -8U、却把 +200U 改成 +25U 的退出，可能看起来胜率/PF改善，最终经济价值反而下降。

所以exit必须额外报告：

> **right-tail capture ratio**

而不只报告减少了多少hard stop。

---

### C. “同一个Broad门后的candidate/control天然公平”

入口相同时，exit实验确实较干净；但在有限资金下，不同exit导致不同资金释放速度。时间一长：

- 快exit臂重新有slots/cash；
- 慢exit臂仍占仓；
- 它们后来看到的机会集合开始不同。

上一轮五臂通过“任何一臂没槽/没钱则全组不进”解决了配对纯度，却引入另一选择：

> 实验测的是 **共同最慢资金周转约束下的exit效果**，而不是每种exit独立运行的portfolio效果。

这已经在 `FINAL_CONTRACT/DEPLOYMENT` 中披露。第二轮不要把这种设计直接推广给所有策略组合。

---

# 3. 建议新增的6个真正不同机制/对照

不是要求全做；这是首轮反方候选空间。

## P1. L0 Opportunity Auction —— 同时机会排序

**机制**

在一个固定短round内，把所有已经通过同一个基础交易门的候选冻结，不问“买不买”，而问：

> **只能买K个时买谁？**

只用当前已有L0：

- 相对自身近期波动的价格位移；
- liquidity retention；
- volume/liquidity；
- buy-share；
- pool age；
- observation freshness。

不使用未来结果，不要求amountful flow。

**关键对照**

- Candidate：L0 score top-K；
- Control：确定性hash/random或first-eligible K；
- 同一冻结候选集、同样K、同样5U。

**为什么能推翻主流**

如果“精心选最好”长期不优于随机/first eligible，则大量entry feature工程其实没有选币价值。

**失败条件**

排名优势只由单token、单时段或一个链贡献；去top-token后消失。

**资源**

现有有界横截面即可；不要改现存 `finite_capital_ranker`，应作为独立L0实验，因为现存ranker合同要求 actual flow。

---

## P2. Anti-Chase Delay —— 延迟一帧到底值不值

**机制**

同一Broad/突破信号产生后：

- A：现有下一帧立即Paper BUY；
- B：强制再等一个独立原池frame，只要求没有发生灾难性跳价/liq崩坏，不加复杂图形门。

这是一个**等待成本实验**，而非另一种形态策略。

**反证目标**

直接回答：

> 当前大量“确认再确认”究竟是在减少false breakout，还是纯粹让买价更差/错过右尾？

如果B的损失减少不足以补偿entry lag，则应该减少后续复杂确认策略，而不是继续堆序列。

---

## P3. Convexity Sentinel —— 防止聪明退出杀掉超级赢家

这不是新的买入门。

当任何快速退出准备触发时，如果仓位此前已经出现明显成本后正收益且仍有新高形成，建立一个**小比例runner challenger**，而不是全部卖光。

注意：项目历史已经有principal runner/scaleout，所以不能简单复制“卖一半留一半”。

真正的新问题应是：

> **“原本应全退出的失败信号，是否对曾经进入右尾状态的仓位过于激进？”**

Candidate只改变“已进入右尾状态后的失败信号处理”，control仍全卖。

**推翻条件**

runner增加的尾部收益不足以覆盖额外writeoff/回吐；则彻底否定“给赢家更多空间”。

---

## P4. Opportunity Replacement —— 新机会是否值得踢掉旧弱仓

当前slot满时通常只能拒绝新机会。

但有限资本真正的问题可能是：

> 手上一个已经180秒没有经济进展的仓，和一个刚刚出现高质量新机会，应该继续持旧仓还是换仓？

**Candidate**

只有当旧仓满足已经存在的“无进展/弱化”状态，而新候选在同轮L0相对排名明显更高时，退出旧仓，**下一独立frame后**才允许新仓。

**Control**

保持旧仓直到自身exit，新机会拒绝。

这是“机会成本”机制，不是更严的risk gate。

**风险**

频繁换仓会被双侧4%摩擦吃死。

**死亡条件**

replacement turnover增加，而成本后portfolio PNL下降。

---

## P5. Loss-Budget Portfolio —— 不是每个币独立亏20U

214账户每个策略内部主要按仓处理。一个值得反证的新结构是：

> 同一个策略在短时间连续错3次后，是否还应该用同样速度继续下注？

不是按小时优化，也不是“坏时段不交易”。

设计成**状态相关风险预算**：

- 连续若干已实现成本后失败 → 后续新机会临时用更小5U/WAIT；
- 一旦观察到新的独立盈利终局或预定冷却结束，恢复；
- 不使用市场未来标签。

**对照**

固定5U。

这测试的是亏损聚集是否体现短暂失效regime。

**关键反证**

若缩仓只是恰好在大赢家前发生，导致右尾损失更大，则否决。

---

## P6. Mechanism Disagreement Portfolio —— 专买“机制一致”未必是对的

当前许多策略在同一个Token上会同时触发。

很自然的做法是“多个机制一致才买”，但我建议反过来检验它。

冻结同一Token同一时刻各现有机制的 READY/WAIT：

- consensus candidate：≥N个机制同时READY；
- specialist candidate：只有一种机制READY、其他互不冲突；
- deterministic control：基础gate。

**目的不是做投票系统，而是回答：**

> 多机制共识是否真的有增量，还是所有机制本质上都在重复读同一个 volume/price shock？

如果共识没有优势，就能直接推翻“组合更多信号更可靠”的主流思路。

---

# 4. 我暂不建议的新方向

以下现在信息增益低：

- 再造 buy ratio 55/60/65；
- 再造 liquidity 1k/2k/5k；
- boundary retest 再加第四阶段；
- profit_budget 50% retrace 改40/60；
- cycle-reset只修改秒数；
- 用当前“最赚钱的小时”做regime；
- 214个账户做简单多数投票。

这些都是参数/相关策略膨胀，不是新机制。

---

# 5. 组合层最容易出现的虚假盈利

**同门选择偏差**：只比较最终成交者，忽略因为某臂没slot/cash而共同被拒机会。

**右尾幸存者偏差**：只看退出后少亏，不看被退出机制截断的后续5/15分钟上涨。退出后标签只能作为研究结果，绝不能回填exit。

**复制收益**：一个Token被几十个策略同时赚，不能当几十次证据。

**资本周转混淆**：快exit产生更多后续可交易机会，本身也是策略经济效果；严格paired实验会有意消掉这一效果，所以需明确问题不同。

**机会排序后的条件选择**：top-K ranker不能和“全部eligible”直接比较平均收益；必须和相同K、相同冻结候选集的随机/hash/FIFO control比较。

---

# 6. 我认为优先级最高的三项

如果只选择三项进行后续R2/R3，我建议：

**第一：P1 L0 Opportunity Auction。**  
这是当前架构明显缺失且最贴近真实有限资本的问题。

**第二：P2 Anti-Chase Delay。**  
它可以直接验证上一轮越来越复杂的确认逻辑到底值不值钱。

**第三：P6 Mechanism Disagreement Portfolio。**  
它能判断214策略究竟提供了多样信息，还是大量相关读数换名字。

P3/P4/P5更接近portfolio资本管理，价值可能很高，但对真实自然样本要求更高，应在前3项之后看证据。

---

## 下一自然验证标准

所有候选都应从真实deployment frontier起，至少同时报告：

- eligible opportunity / selected / rejected / no-data；
- unique token/pool/episode，而非账户笔数；
- 同冻结候选集的paired control；
- 净成本后PNL、median、下尾；
- top1/top3 token贡献及移除后结果；
- 最大赢家捕获率；
- 资金/slot占用时间；
- 对未选择机会的固定5/15分钟研究标签；
- 数据缺失与工程污染。

**任何一个方向若只有“少交易所以少亏”而没有同K/同机会对照，不算有信息增益。**

### 实际读取

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/ROUND2/RESEARCH_REQUEST.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md` 当前首段
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/DEPLOYMENT.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/SYNTHESIS.md`
- `src/memetrader/capital_entry.py` ranker/regime段
- `src/memetrader/capital_cross_section.py` as-of cross-section/score段

ROUND2目录此时只有 `RESEARCH_REQUEST.md`；后续统计/工程/外部报告尚未落地，所以本结果没有伪称读过它们，也没有等待它们才提出独立假设。

未运行全历史扫描、大SQL；未改代码、DB、Runtime；未建立第二writer。
