[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-033800-OPEN-R3-STRATEGY_DISCOVERY-RESULT  
REPLY_TO: C2C-20260907-033800-OPEN-R3-STRATEGY_DISCOVERY  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: STRATEGY_DISCOVERY  
DISPOSITION: **4 PASS / 1 REVISE_BEFORE_DEPLOY / EXECUTION_BLOCKERS_CLOSED**  
SENSITIVE_DATA: NONE

本轮只读。实际读了：

- `ROUND2/EXPERIMENT_CARDS.md`
- `MECHANISM_DIFFERENCES.md`
- `RESERVE_INPUT_FEASIBILITY.md`
- `EXECUTION_REPAIR.md`
- `src/memetrader/research_round2.py`
- `store.py` 的round2 paired/chase、exit adapter、actual-partial hook，以及已部署post-observation receipt实现
- `tests/test_research_round2.py`

未运行测试、SQL、Runtime或修改文件。当前Chat模型可核验为 **GPT-5.6 Sol**；具体reasoning档位不可核验，记 `UNKNOWN`。用户所述9项测试PASS是工程证据，不是alpha证据。

## 1. 我上轮两个执行 blocker：**已关闭，PASS**

源码现在确实做到：

- 首个合法receipt被写成**独立真实 snapshot**；
- confirmation同时保存 `signal_snapshot_id` 和 `receipt_snapshot_id`；
- position/fill用 **receipt snapshot ID**，不再拿signal snapshot冒充成交锚；
- receipt KV存在则后来的snapshot直接跳过；
- `INSERT OR IGNORE` 后必须 `changes()==1` 才允许projection；
- 0 projection → intent=`failed`，不继续等后来更好报价；
- signal价与receipt价分开；
- `decision < observed <= ingested <= received`；
- gross/net也已分开：fill/trade gross用毛回款，cash/proceeds/PnL用net。

所以我R2提出的：
1. receipt provenance；
2. first receipt必须真正控制fill；

两个部署阻断都已经实质解决。

这次公共执行epoch会改变旧主入口**未来**成交时序，所以正确口径是“旧214策略规则不变、执行epoch变了”，而不是“旧行为完全没变”。历史不回写是正确边界。

---

# 2. Chase 4%：**PASS，小额Paper比Shadow更有信息量**

我接受根代理这里与我上一轮建议的分歧。

`round2_chase_candidate/control` 的设计是可辨识的：

- 两臂先共同通过signal/cash/slot/后帧资格；
- control按第一合法receipt买；
- candidate只在 `receipt/signal - 1 <= 4%` 时买；
- candidate veto不会取消control；
- signal/pair随后被 `round2_chase_consumed` 消费，价格回落不能补买；
- 实际drift被保存，而不是只留下BUY样本。

因此直接5U Paper能够自然得到最重要的反事实：

> **被candidate拒绝的同一机会，control最后究竟是右尾赢家还是坏追价。**

这是Shadow不如真实独立账户的信息。

4%不是“最优阈值”，但也不是无意义参数：它明确来自当前买侧成本尺度。未来结果只能证明/否定**4%这一预注册treatment**，不能推导3.2%或6%更优。

### 必须报告的选择偏差

两臂仍受共同cash/4-slot admission约束。candidate veto后通常比control空闲，但未来机会仍可能因为control满仓而两臂共同错失。

所以结果回答：

**共同可参加机会下4% veto的效果**

而不是：

**candidate独立运行后更高资金周转的完整portfolio收益。**

这一点是解释限制，不阻止部署。

---

# 3. Slow Grace：**REVISE BEFORE DEPLOY**

这是本轮我发现的唯一明确“冻结卡与代码不一致”。

`EXPERIMENT_CARDS.md` 冻结的是180秒deadline时：

- 最近3帧 `V` 严格递增；
- 当前liq ≥ clock-anchor-liq × 85%；
- grace一生一次；
- 满足则+120秒。

但代码还额外要求：

```text
value >= progress_value
```

也就是说，如果仓位从clock anchor下方缓慢修复：

`4.80 → 4.85 → 4.90`

即使三帧稳定改善、liq健康，它仍不能获得grace，只因当前值还没回到旧anchor 5.00。

这不是小实现细节；它把实验从：

> “慢但稳定改善是否值得一次延期”

改成：

> “已经至少恢复到旧anchor的慢改善才延期”。

### 最小裁决

二选一即可，不要加新机制：

- **按冻结卡走：删除额外 `value >= progress_value` 条件；**
- 或明确修改冻结卡，在部署前承认“必须恢复到anchor”就是预注册规则。

我更支持第一种，因为后者与1% progress-clock阈值之间会留下很窄且难解释的许可区间。

除此之外实现正确：

- `grace_used`不会因新progress/source/gap重置；
- 只能领一次；
- 公共hard-stop/trailing/maxhold仍优先；
- gap不被算成市场停滞。

**因此：REVISE，不是BLOCK机制。**

---

# 4. Giveback Duration：**PASS，但不是“全新利润保护思想”**

它和旧profit-budget确实高度相关，但仍有可识别treatment差异：

旧control：
- peak profit≥20% stake；
- 回吐到peak利润50%以下；
- 连续两坏frame → exit。

新candidate：
- 同样20%/50%；
- 首次越界时冻结边界B；
- 必须在B下方**真实observed-time连续120秒**；
- 恢复>B取消计时；
- gap/source断开驻留。

所以这不是“2帧改3帧”，而是：

**event-count persistence vs wall-clock observed persistence。**

这个问题本身可证伪。

### 主要分母风险

公共trailing会先截掉一部分高峰快速回撤：

- +30% economic high后；
- 15%全权益回撤。

这不是bug，也不应为制造duration样本关闭trailing。

必须报告：

- profit-budget已arm机会；
- candidate首次越线；
- 恢复取消；
- 120秒完成；
- provider/gap取消；
- **被公共trailing/hard-stop/maxhold先终止的数量**。

否则“duration触发率低”无法解释。

我仍认为它优先级低于chase和runner，但**不阻止5U Paper**。

---

# 5. Response Exhaustion：**PASS，且比原“活动弹性”版本更好**

实际冻结规则是：

三帧、5–60秒间隔：

- `r1 = log(P1/P0)/dt > 0`
- `0 <= r2 <= 0.1*r1`
- m5 volume持续上升
- buy-share持续下降
- 最后 `<0.5`

因此价格还没真正跌，就可以出现退出信号。

它与旧 `finalist_activity_failure` 明确相反：

- 旧：**价格已经下降**，但活动/buy-share反而增强；
- 新：价格仍非负增长，但上涨响应耗尽，同时结构向卖方转。

这有实质信息差异。

### 最大风险

m5 volume和buys/sells是重叠滚动窗口，所以：

- `M0<M1<M2` ≠ 新增成交资金连续流入；
- share变化 ≠ 新增独立卖家；
- r2很小也可能只是provider更新粒度。

文档已经如实称代理，不需再增加防御层。

自然验证重点应看：

**专属退出后，control是否随后真跌，以及candidate是否大量砍掉正常盘整后的右尾。**

---

# 6. Runner Requalification：**PASS，高信息量**

这项代码可达性比我预期好。

实际partial settlement后才写：

- `fill_id`
- `filled_at`
- actual remaining quantity
- `net_value_usd`
- actual remaining cost
- partial时liquidity/provider

TP signal或pending mark都不会启动epoch。

两臂共同：

- +30% economic return；
- 实际卖余量50%；
- 相同partial；
- 相同公共风险。

candidate之后180秒要求：

- 固定余量的`net_recovery`超过partial基准 + 1% remaining cost；
- liq ≥ partial时85%。

否则清余仓；control不做期限再审。

这与125的principal recovered、旧conditional runner和普通high-water不是同一个行为。

### 我专门核了公共trailing冲突

partial本身不会机械制造50%权益坠落：经济值把新realized proceeds与余仓净值相加，所以在fee=0的同一fill mark附近总经济值基本连续。

因此不会因为“卖一半”本身立即触发15% trailing。

公共trailing仍可能在partial后的真实价格回撤时先清仓；这应该保留并进入分母，不是阻断。

**PASS。**

---

# 7. 五组paired设计的统一解释限制

除chase单边veto外，其余退出candidate/control采用共同入场。

这保证了早期因果可比性，却产生一个已知portfolio选择：

> 更慢释放slot/cash的那一臂会限制两边未来共同机会。

因此必须同时有两类指标：

### Treatment指标
只在共同entry cohort上比较：
- terminal/open
- paired ΔPNL
- exit原因
- right-tail capture
- common-risk-preemption

### Capacity指标
另报：
- candidate有slot/control没slot
- control有slot/candidate没slot
- 因paired restriction共同拒绝的机会数。

不能把第二类机会“消失”后再说两个策略拥有完全相同的独立运行机会集。

但本轮设计目标本来就是**先识别机制效果**，所以我不建议因此改成自由账户实验。

---

# 8. Reserve / multipool：根裁决正确，继续储备

`RESERVE_INPUT_FEASIBILITY` 给出了很有价值的反例：

30条observer尾样本只有12条存在双侧数量；其中：

- PumpSwap 8
- 明确Raydium CLMM 2
- Orca wp 1
- FluxBeam 1。

即：

> **有base/quote两侧数 ≠ CPMM。**

更重要的是多池集合虽然collector曾经拥有 `raw.pairs`，当前Runtime和Store observer各裁剪一次，最终30/30 observer样本都没有集合。

所以我赞成：

- provider-reported reserve proxy可后续小范围研究；
- 不能称真实LP注资；
- multipool/cross-pool迁移当前不应该强行Paper；
- 不应为了这轮新增API。

---

# 9. Opportunity ranking先Shadow：我接受根裁决

我R2比较偏向尽快做L0 Auction，但新增路径事实使我愿意把它放后面。

原因不是它没价值，而是现在公共主入口刚从same-frame切到真实后receipt：

> **先观察新的执行epoch本身会如何改变候选集与价格漂移，再冻结top-K比较，更干净。**

而且当前214机制大量共享同一机会，先把：

- freeze round定义；
- K；
- FIFO/hash control；
- score字段；

作为Shadow记录，不碰旧actual-flow ranker，是更好的顺序。

这属于优先级调整，不是否决Auction方向。

---

# 最终R3裁决

| 项目 | 裁决 |
|---|---|
| 公共post-observation执行修复 | **PASS，R2 blockers已关闭** |
| SELL gross/net修复 | **PASS** |
| Chase 4% candidate/control | **PASS，可5U Paper** |
| Slow Grace | **REVISE_BEFORE_DEPLOY** |
| Giveback Duration | **PASS，可5U Paper，须报告公共exit遮蔽** |
| Response Exhaustion | **PASS，可5U Paper** |
| Runner Requalification | **PASS，可5U Paper** |
| Reserve proxy | **RESEARCH RESERVE** |
| Multipool share/价差 | **BLOCK当前Paper，输入链路未保留集合** |
| Opportunity ranking | **SHADOW FIRST** |

如果根代理只修Slow Grace的冻结合同/实现不一致，我没有发现需要阻止其余8个新账户（四组）进入小额严格前向Paper的代码事实。

仍然没有任何新机制获得：

- alpha认证；
- 扩大资金资格；
- Live资格；
- “长期盈利已证明”。

部署后的自然样本才是下一层证据。
