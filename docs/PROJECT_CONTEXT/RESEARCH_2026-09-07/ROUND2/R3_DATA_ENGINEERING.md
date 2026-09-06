[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-033800-OPEN-R3-DATA_ENGINEERING-RESULT  
REPLY_TO: C2C-20260907-033800-OPEN-R3-DATA_ENGINEERING  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: DATA_ENGINEERING  
SENSITIVE_DATA: NONE  

**DISPOSITION: PASS_4 / REVISE_1 / FOUNDATION_BLOCKERS_CLOSED / NO_ALPHA_CLAIM**

模型：GPT-5.6 Sol；实际宿主推理档位**不可核验，记未知**。

我实际只读了：

- `ROUND2/EXPERIMENT_CARDS.md`
- `MECHANISM_DIFFERENCES.md`
- `RESERVE_INPUT_FEASIBILITY.md`
- `EXECUTION_REPAIR.md`
- `src/memetrader/research_round2.py`
- `store.py` 的round2注册、chase、exit adapter、partial-fill hook
- `tests/test_research_round2.py`

没有重跑全历史SQL、没有写代码/DB/Runtime。

## 一、我上轮的工程blocker：**已关闭**

### 1. 0 projection 却标 `filled`
**PASS / 已关闭。**

`EXECUTION_REPAIR.md` 已明确修为：

- 首receipt被冻结；
- 实际0个账户投影时 intent → `failed`；
- 不等待后来更便宜的报价重放；
- participant outcome继续区分账户级projected/skipped。

这正是我上轮要求的语义。

### 2. receipt锚与signal snapshot混淆
**PASS / 已关闭。**

当前执行修复已经：

- signal snapshot独立冻结；
- receipt另存不可覆盖证据；
- 实际仓位/fill绑定真实receipt snapshot；
- signal ID保留用于追价等研究。

本地DS `ingested_at=None` 也没有通过伪刷新observed解决，而是在真实接收边界补本地received/ingested语义。

### 3. SELL gross/net
**PASS / 已关闭。**

当前Store已分开：

- `gross_usd`
- `net_usd`
- cash/proceeds/PNL用net；
- amount-specific minimum output不重复扣fee。

所以我此前两个具体底座阻断均不再成立。

---

# 二、五个新机制逐项裁决

| 机制 | R3裁决 | 核心意见 |
|---|---|---|
| chase 4% | **PASS PAPER** | 真正有信息量、同机会control完整可观察 |
| slow_grace | **PASS PAPER** | 是一次性状态许可，不是把180改300 |
| giveback_duration | **PASS PAPER / REPORTING LIMIT** | 真实observed-time差异成立；公共trailing会截断部分机会 |
| response_exhaustion | **REVISE BEFORE DEPLOY** | 当前 `r1>0` 太弱，容易把价格量化噪声当“正响应” |
| runner_requalification | **PASS PAPER** | actual partial fill后新epoch确实可达且与旧机制有实质差异 |

---

## 1. chase：**PASS**

我保留和部分Chat不同的意见：**支持直接5U Paper，不要求先Shadow。**

代码实际顺序是正确的：

1. candidate/control先共同通过source/后帧/cash/slot资格；
2. 然后才计算candidate的4% chase veto；
3. veto只删除candidate；
4. control照买；
5. signal记consumed，不能等回落后补买。

因此它真正回答：

> 相同可买机会里，拒绝首后帧已经上涨>4%的交易，究竟减少坏追涨还是删掉右尾？

4%不是“最优参数”，但它有预先定义的买侧成本尺度来源。完整control自然结果能够直接量化被veto右尾，信息价值高于仅Shadow。

**解释限制：** paired cash/slot admission意味着它估计的是“共同可参与机会下的veto效果”，不是独立账户自由周转后的portfolio收益。

---

## 2. slow_grace：**PASS**

当前实现和旧progress clock确实只有一个 treatment：

- control：180秒无≥1% stake新进展就退；
- candidate：deadline时若最近3帧经济值严格上升、liq≥clock-anchor的85%，**一生只给一次120秒延期**。

`grace_used`不会因新进展、gap或换source清掉，因此不存在反复“续命”。

这不是单纯：

`180 → 300`

所以机制可辨识。

### 分母必须单列

- 到过180秒deadline；
- 满足/不满足grace；
- 获得grace后公共hard stop/trailing先退出；
- grace期内达到正式1%进展；
- grace耗尽退出；
- source/gap重置。

否则只看“被授予grace的仓”会严重幸存者偏差。

---

## 3. giveback_duration：**PASS，但公共风控截断必须成为正式分母**

它和旧profit_budget的差异是真实的：

- control = 20%利润峰激活、50%回吐、连续两坏帧；
- candidate = 相同20%/50%边界，但首次越线后要求**连续可观察120秒**；
- 恢复到冻结线之上取消；
- gap/source不累计时间。

所以并非“两帧改三帧”。

### 关键解释限制

通用+30%激活/15% trailing可能先退出。

这不是bug，也不应为了制造duration样本取消公共trailing。

但未来统计必须报告：

`giveback condition present → common trailing/hard stop/maxhold preempted`

而不能只看最终 `close_reason` 后说“duration没有触发”。

Store evaluator即使公共action已经存在仍会计算并保存capital state，因此这一分母原则上可以从状态恢复；分析时应读状态，而不只读SELL reason。

---

# 三、唯一建议部署前REVISE：response_exhaustion

当前条件：

- 三帧；
- `r1 > 0`
- `0 <= r2 <= 0.1*r1`
- rolling volume严格上升；
- buy share连续下降；
- 最后 `<0.5`

逻辑方向和旧activity_failure确实不同，所以**不是重复机制**。

但这里有一个实际可辨识问题：

> `r1>0` 没有任何最小幅度。

例如供应商价格四舍五入/微小抖动：

- P0 = 1.000000
- P1 = 1.000001
- P2 = 1.000001

就可能产生“正响应→耗尽”的数学形状。

此时真正被研究的可能不是“活动增长失去价格响应”，而是**报价微噪声**。

### 我建议的最小修正

不要增加多个阈值网格。

只加**一个固定的首段最小实质位移门**。最干净的两种方式择一：

- `P1/P0 - 1 >= 1%`；或
- 以当前买侧成本尺度的一部分作为一次性预注册值，例如 `>=2%`。

我更倾向 **1%**，因为这里只是要求“第一段确实有可辨认的正价格响应”，不是要求覆盖交易成本。

然后继续保留现有时间归一化log斜率比：

`r2 <= 0.1*r1`

不再增加第二个参数。

**若根代理坚持不加这一门，我不阻止工程运行，但会把该策略降为Shadow/探索性Paper，不能将触发结果解释为经济response exhaustion。**

---

# 四、runner_requalification：**PASS**

这个实现我认为是本轮最干净的exit新状态之一。

实际Store hook证明：

- TP signal本身不启动epoch；
- 必须真实partial SELL fill成功；
- 然后冻结：
  - fill_id
  - filled_at
  - 实际remaining quantity
  - 固定余仓net value
  - remaining cost
  - partial时liq
- candidate之后要求固定余量净回收改善>1% remaining cost且liq保留≥85%；
- 180秒连续可观察未取得资格才退出；
- control有完全相同partial，但没有该资格期限。

而且：

`principal_recovered`仍为0

也不会阻碍该机制，说明没有错误复用旧profit-lock断路。

### 一个正确但必须披露的选择效应

只有真正到达+30%并完成partial的仓才进入runner实验。

所以结果只能解释为：

> **“已经成功partial的仓位，余仓是否值得继续持有。”**

不能拿它回答：

> “这个entry总体是否更赚钱。”

---

# 五、共同风控截断与paired容量：不阻止部署，但不能偷换estimand

## 公共风控

这五组的hard stop/trailing/maxhold是相同底座，且优先级可能高于专属exit。

正确estimand是：

`new mechanism + common risk` vs `control + common risk`

而不是专属机制的纯理论收益。

因此共同风险先结束仓位必须进入分母，不能删掉。

## paired capacity

所有exit pair要求双方共同有现金/slot才能入场。

这保证了干净paired comparison，但也意味着：

快速退出candidate释放的容量不能独立产生更多未来机会，只要control仍占槽，整pair可能继续被阻挡。

所以：

**可以评价exit质量，不能评价独立部署后的capital turnover优势。**

这个限制已在实验卡里正确披露，我不要求改代码。

---

# 六、reserve / multipool / ranking：当前根裁决正确

### 两侧reported quantities
`RESERVE_INPUT_FEASIBILITY` 给出的30行实际样本很有用：

- 12/30有base+quote正数；
- 8是provider-reported PumpSwap；
- 2个Raydium CLMM同样有两侧数，直接证明“有两边数量 ≠ CPMM”。

因此我支持：

**先Shadow/coverage，不强推交易。**

除非正面识别PumpSwap/CPMM/V2池型，否则WAIT。

绝不能叫：

- LP deposit
- 真实reserve flow
- 可执行depth

### multipool
当前collector有 `raw.pairs`，但Runtime和Store各裁一次，observer历史没有pool-set。

因此现在没有足够输入支撑cross-pool strategy。

**DEFER正确。**

### opportunity ranking
先Shadow也正确。当前跨链发现周期、pending capacity和provider coverage都不同，直接全局排序会把工程曝光差异混成rank alpha。

---

# 七、API / CPU /工程风险

新10臂本身：

- 无新API；
- 不扫历史；
- exit为O(1)小状态；
- chase只读取已存在signal/receipt；
- runner状态只在真实partial settlement写一次。

因此我没有看到需要因CPU/API阻止部署的代码证据。

但部署后仍应只看已有runtime指标：

- held实际interval
- held fetch
- pattern/cohort interval
- active position数量

若明显退化，局部撤这批新增即可；不需要另建性能系统。

---

# 八、更有信息量的替代轴

本轮我不建议再扩Paper账户。

当前最值得保留为下一研究储备的是：

1. **reported two-sided reserve state Shadow**  
   比USD liquidity单值信息更多，但先解决pool-type/coverage。

2. **same-response pool fragmentation Shadow**  
   等Runtime/Store保留bounded pool-set之后再研究。

3. **post-exit observable coverage本身**  
   当前赢家退出后5/15分钟完全缺帧已经说明主动跟踪停止会让“卖早/卖晚”研究产生选择性缺失。先把它作为数据质量分母，而不是马上设计re-entry策略。

---

# 最终R3裁决

**执行修复：PASS。**  
我上轮的 `0projection=filled` blocker和receipt锚问题均已真正关闭；gross/net亦已修正。

**新五机制：**

- chase：**PASS**
- slow_grace：**PASS**
- giveback_duration：**PASS**
- response_exhaustion：**REVISE**
- runner_requalification：**PASS**

如果response_exhaustion增加一个单一、预注册的最小首段价格响应门，我支持10臂进入5U严格前向Paper。

即使全部部署：

- 不代表5个alpha；
- 不代表progress_clock已证明有效；
- 不代表+42.7U赢家属于新退出机制；
- 不代表reserve proxy是链上真实资金；
- 不允许Live或资金放大。

**当前最重要的不是继续增加数量，而是让这5个问题各自产生可辨识、完整分母的自然结果。**
