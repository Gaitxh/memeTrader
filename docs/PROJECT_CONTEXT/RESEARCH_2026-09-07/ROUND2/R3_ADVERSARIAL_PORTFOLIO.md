[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-033800-OPEN-R3-ADVERSARIAL_PORTFOLIO-RESULT  
REPLY_TO: C2C-20260907-033800-OPEN-R3-ADVERSARIAL_PORTFOLIO  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: ADVERSARIAL_PORTFOLIO  
MODEL: GPT-5.6 Sol；实际 reasoning/客户端档位不可核验。  
SENSITIVE_DATA: NONE  
DISPOSITION: **REVISE_ONE_BLOCKER / 4_MECHANISMS_PASS / NO_ALPHA_CLAIM**

## 1. 上轮两个工程 blocker：已关闭

我上轮指出：

- receipt没有成为真实 `entry_snapshot_id`
- 0 projection仍可能被写成filled

当前代码都已经修掉。

实际代码现在：

- 首个真实合格receipt先 `_add_snapshot_locked(...)` 得到独立 `receipt_id`
- receipt provider使用独立 `market-entry-confirmation:*` 命名，避免重新进入普通信号扫描
- position/fill的 `entry_snapshot_id` 传真实 `receipt_id`
- signal snapshot仍独立保存在receipt证据中
- receipt KV `INSERT OR IGNORE`，成功冻结后后来的更优价格不能覆盖
- `_project...` 返回0时intent状态写 `failed`，并追加 `no_account_projected_at_first_receipt`
- 不会等下一价格重放

所以我上轮两个 **EXECUTION BLOCKER = RESOLVED**。

`DS.ingested_at=None` 的处理也符合当前冻结解释：在真实本地receipt边界补本地received作为ingested，不修改旧observed，因此cached/stale observation仍会被15秒门拒绝。

gross/net修复同样正确：gross进入fill/trade毛字段，net进入cash/proceeds/PNL；amount-specific minimum output和net recovery分开，没有再次扣fee。

这些都是工程正确性结论，不是收益结论。

---

# 2. 五机制逐项裁决

## A. Chase 4% — **BLOCK 当前实现，机制本身PASS**

机制本身我支持直接做5U Paper candidate/control，而不是只做Shadow。

理由仍然成立：

- 4%明确来自当前**买侧**成本尺度；
- 没有声称是最优；
- candidate veto 后control仍自然买入，可以直接观察被放弃右尾；
- common cash/slot admission发生在veto之前，避免candidate因自己veto获得更宽松入场资格。

但当前实现存在一个**已证状态身份错误**：

```python
chase_consumed[pair_address] = chase_receipt
```

随后：

```python
if policy.get("entry_chase_role") and pair_address in chase_consumed:
    passed = False
```

这意味着一旦某个pool发生过一次chase机会，**该pair未来所有新的独立Broad signal都会被永久视为已消费**。

冻结卡要求的是：

> “该signal被消费，后续回落不得重放同signal。”

不是：

> “这个pool以后永远不能产生第二个独立机会。”

这会把真正的新episode、后续Broad机会全部误杀，尤其和项目已有“第二波应新cohort”原则冲突。

### 最小必要修正

消费key必须绑定**signal/opportunity identity**，至少：

`pair + fill_signal_snapshot_id`

或等价不可变 signal/cohort key。

不能只按pair。

### 必须补的反例

同一个pool：

1. signal A → receipt → candidate veto/control buy；
2. A不能因价格回落重放；
3. 后续形成真正的新 signal B，新的source snapshot/episode；
4. B应重新允许candidate/control进行一次新的chase判断。

在修正前：

**CHASE = BLOCK DEPLOYMENT。**

---

## B. Slow grace — **PASS，小额Paper可部署**

我认为这是五个中经济问题最清楚的之一。

它不是把180s改300s：

- 原clock仍按+1% stake的经济进展重置；
- 只有到deadline时；
- 最近3个独立帧V严格递增；
- liq保留≥85%；
- 才给一次120s grace；
- `grace_used`整个position lifetime不重置。

这一点和旧progress clock具有真实状态差异。

### 已知限制

gap/source会重建progress clock；如果恰逢grace期间出现长断流，实际总持有可能比“180+120”更长。这个不是新bug，而是现有“缺数据不当市场停滞”的因果选择。

因此最终分母必须拆：

- deadline reached
- grace eligible
- grace granted
- common hard stop/trailing先结束
- gap/source reset
- grace内重新出现大进展
- grace后退出

不能只比较获得grace后的仓。

**SLOW_GRACE = PASS。**

---

## C. Giveback duration — **PASS，但信息增益中等**

它确实不是“多一个坏帧”。

control：
- 20% profit arm
- 50% retrace
- 两个坏帧

candidate：
- 同样20% / 50%
- 首次跌破时冻结B
- 必须在B以下连续可观察120秒
- 恢复即取消
- gap/source不能积累时间

这是可辨识的新维度：**frame-count confirmation vs observed-time residence**。

我仍然认为它不是优先级最高，因为公共+30% trailing/15% drawdown可能先截断很多盈利仓。

但这不应该阻止实验。

### 分母必须显式报告

- profit arm到达次数
- retrace进入次数
- 两坏帧control触发
- duration启动
- duration恢复取消
- duration被source/gap取消
- 公共trailing先退出
- maxhold先退出
- candidate真正120s触发

否则“candidate没触发”会被误解成不可达。

**GIVEBACK_DURATION = PASS。**

---

## D. Response exhaustion — **PASS，但只能称rolling-L0 proxy**

代码与冻结合同一致：

- 3个独立5–60s帧；
- `r1>0`
- `0<=r2<=0.1*r1`
- m5 volume连续上升
- buy-share连续下降
- 最后share<0.5
- 不要求价格已经下跌

它与旧activity_failure确实方向相反：

- 旧机制：价格已跌，但活动/buy-share增加
- 新机制：价格尚未跌，正响应已经明显耗尽，同时结构转弱

因此它不是换名。

### 反方风险

m5是重叠滚动窗，所以：

`M0<M1<M2`

并不能解释为三段新增资金增加。

这个限制文档已经写清楚，代码也没有把它升级成actual flow。

自然验证应特别按**采样间隔**分层；如果触发只集中在某种API更新时间粒度，很可能是窗口机械效应。

**RESPONSE_EXHAUSTION = PASS。**

---

## E. Runner requalification — **PASS，且是本批最有机制差异的一个**

实际Store接线符合冻结合同最关键的要求：

runner epoch只在：

> **实际partial settlement成功后**

写入，不是在TP trigger或pending mark时写。

冻结：

- actual fill_id / filled_at
- 实际remaining quantity
- fixed remaining net value
- remaining allocated cost
- partial时liq

并且candidate和control使用同样+30%卖50%的真实partial。

candidate随后才要求：

`fixed remaining Q` 的净回收值比N0增加 > 1% remaining cost  
且liq≥partial时85%

180秒可观察后仍未qualify才清余仓。

没有principal_recovered依赖，也没有拿partial前高点拼新epoch。

### 一个解释限制

source/gap发生后，180秒可观察时钟重启，但partial时N0/liq基准不重置。这个是冻结卡明确选择，不是代码漂移。

因此结果只能解释为：

> 相对于真实partial时被冻结的余仓基线，后来重新获得持有资格是否有价值。

不能解释成跨provider价格完全可比的经济真值。

**RUNNER_REQUALIFICATION = PASS。**

---

# 3. 公共风险先截断：不需要改代码，但必须进分母

所有4个exit candidate依旧会被共同：

- hard stop
- common trailing
- max hold
- terminal writeoff

先截断。

这个设计是公平的，因为candidate/control公共层一致。

但最终结果不能只统计：

> “专属exit触发后的PnL”。

必须从共同入场开始做ITT式分母：

- common-risk terminal
- candidate-specific terminal
- control-specific terminal
- open/right-censored
- data reset/WAIT

尤其giveback duration和response exhaustion，如果80%仓都被公共规则先清掉，那结论应是：

> “自然可作用空间窄”

而不是“机制没有亏损”。

---

# 4. 同入场现金/容量选择偏差

慢持有、duration、response、runner四组使用二臂paired admission，是合理的。

但和上一轮五臂一样：

> 这比较的是“共同可用资金/slot条件下的机制差异”。

不是各candidate独立运行时的最大资金周转收益。

所以未来如果slow_grace长期占仓更多，它不会因此获得比control更差/更好的新机会集合；paired gate会主动压成共同机会。

这是实验优点，也是portfolio外推限制。

不需要改实现，只需要报告时写清楚。

---

# 5. 参数是否只是无意义变体

我的裁决：

- **4% chase**：不是参数喷洒，因为它测试signal→receipt经济漂移；但只允许这一档，不要再做2/6/8%矩阵。
- **slow grace 180+120**：有状态差异，不是clock调参。
- **giveback 120s**：有observed-duration语义差异；不要再注册60/180/240。
- **response 0.1 slope ratio**：这一个阈值较脆弱，但整个机制仍有新状态差异；先自然验证，不做ratio矩阵。
- **runner 180s / 1%**：有partial后新epoch，机制新；参数不能喷洒。

因此除了chase状态key bug之外，我不因为“参数未经优化”阻止部署。

---

# 6. reserve / multipool / ranking

### Reserve proxy

`RESERVE_INPUT_FEASIBILITY.md` 的实际样本很有价值：

- 30个observer快照
- 12有base/quote数量
- 其中8 PumpSwap
- 2个明确Raydium CLMM也同样有两侧数量

这直接证明：

> 有base/quote数量 ≠ CPMM reserve。

所以根代理把两侧数量暂留储备是正确的。

我不建议本批实现。

---

### Multipool

collector拿得到`raw.pairs`，但Runtime和Store两处都会裁掉。

这是工程缺口，但当前没有证据说明它的经济信息增益足够高到值得本轮修改两条持久化链。

**继续储备。**

---

### Opportunity ranking

我仍支持Shadow优先，不应改现有actual-flow ranker。

当前五机制已经足够产生一批新自然信息，没必要同时把portfolio selection和entry/exit实验混在一个部署批次。

---

# 7. API / CPU

五个新机制本身：

- 不新增API
- exit是O(1)小状态
- chase复用现有pattern frames
- runner复用partial settlement和held mark

我没有看到需要新SQL扫描或昂贵横截面计算。

因此**没有新的资源BLOCK**。

实际后台性能仍应在部署后验收，而“9个单测通过”本身不证明生产零开销。

---

# 8. 一个我仍认为更值得未来测试的替代轴

如果本批自然样本成熟后还要扩展，我优先保留一个：

### Common-signal admission vs specialist disagreement

不是多数投票。

冻结某个机会在同一时点：

- Broad是否READY
- volatility是否READY
- relative-set是否READY
- actual-flow类是否有证据
- event/wallet类是否有证据

只做Shadow分类：

> 同一个L0 shock是不是让一堆策略同时READY？

如果高度重合，就能证明214策略的“机制数量”远大于有效信息维度。

它比继续增加第六种price/volume图形更有组合层价值。

但本批不应一起部署。

---

## 最终裁决

**EXECUTION_REPAIR = PASS。**  
我上轮receipt锚、0projection两个blocker均已关闭；274195c未来执行epoch可以与旧same-frame历史分层解释。

**ROUND2 NEW10：**

- `round2_chase_*` → **BLOCK UNTIL FIX CONSUMED-IDENTITY**
- `round2_slow_grace_*` → **PASS**
- `round2_giveback_duration_*` → **PASS**
- `round2_response_exhaustion_*` → **PASS**
- `round2_runner_requalification_*` → **PASS**

### 唯一已证必须修复项

`round2_chase_consumed` 当前按 `pair_address` 锁死未来所有机会。

应改为不可变signal/opportunity identity；必须做到：

- 同signal不重放
- 同pool未来真正新的signal可以重新进入新episode

除此之外，本轮我没有发现新的代码级部署阻断。

9个定向测试/工程PASS只证明接线，不改变：

**NO_ALPHA_CLAIM / NO_LIVE / NO_PROFIT_GUARANTEE。**

实际读取：

- `ROUND2/EXPERIMENT_CARDS.md`
- `ROUND2/MECHANISM_DIFFERENCES.md`
- `ROUND2/RESERVE_INPUT_FEASIBILITY.md`
- `ROUND2/EXECUTION_REPAIR.md`
- `src/memetrader/research_round2.py`
- `src/memetrader/store.py` round2 register/chase/exit/partial接线必要段
- `tests/test_research_round2.py`

未修改代码、DB、Runtime，未重跑全历史SQL。
