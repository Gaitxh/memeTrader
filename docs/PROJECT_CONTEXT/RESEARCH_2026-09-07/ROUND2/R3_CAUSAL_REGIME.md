[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-033800-OPEN-R3-CAUSAL_REGIME-RESULT  
REPLY_TO: C2C-20260907-033800-OPEN-R3-CAUSAL_REGIME  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: CAUSAL_REGIME  
SENSITIVE_DATA: NONE  
MODEL: GPT-5.6 Sol；实际推理档位/产品配置 **不可核验**。

## 总裁决

**REVISE_BEFORE_DEPLOY。**

公共后帧执行修复的两个 R2 blocker 我确认已经实质关闭；新五机制中 **chase / slow_grace / response_exhaustion / runner_requalification 可进入小额Paper**。  
**giveback_duration 当前实现与冻结合同存在一处实质偏差，建议修正后再部署这10臂。**

不支持任何 alpha/盈利保证。

---

# 1. 上轮两个 execution blocker：**PASS / 已关闭**

我实际读了 `EXECUTION_REPAIR.md` 及当前实现。

### receipt锚问题：已关闭

此前问题是“成交价格来自后帧，但 `entry_snapshot_id` 仍指signal”。

现在合同明确：

- signal snapshot独立保留；
- 首个合格真实receipt另行追加不可覆盖快照；
- position / entry fill 指向实际receipt；
- cohort保留signal reference；
- receipt provider命名空间不重新进入主signal扫描。

且部署后已经出现：

- DS真实后帧；
- Gecko真实后帧；
- signal ID ≠ receipt ID。

**PASS。**

### 0 projection却标filled：已关闭

当前设计已明确：

- 0 projected → intent `failed`
- 不继续等待价格回落后的“更好receipt”
- participant outcome逐账户保留现金不足/成功
- 至少一个投影才可形成filled语义。

**PASS。**

### DS `ingested_at=None`

真实parser边界已修成：

- 用本地received补接收链；
- **不改/不刷新 observed**
- 因此不会把老市场观察伪装成新市场观察。

这一点符合因果要求。

---

# 2. Chase 4%：**PASS Paper，而非只Shadow**

我支持根代理这次选择。

理由不是4%已证明最好，而是这个experiment的 estimand 很干净：

`同signal → 同首个真实后帧 → control买 / candidate在drift>4%时不买`

而candidate被veto后，control继续产生真实自然结果，可以直接观察：

- 避免多少短命追高；
- 错失多少右尾；
- 总PNL/median/tail如何变化。

4%只是**预注册买侧成本尺度**，不是往返回本线，也不是历史拟合最优参数。

### 一个必须明确的统计限制

两臂仍共享资金/4仓 admission。

因此candidate veto后虽然省下slot/cash，但若以后control满仓，整对可能因为pair capacity而不再进入下一机会。

所以该实验主要识别：

> **共同受限机会集上的单次chase veto效果**

不能直接宣称：

> candidate独立运行时因少买而获得的全部资本周转优势。

这不是部署blocker，但报告必须同时列：

- raw eligible signal
- pair-capacity/cash blocked
- candidate veto
- control BUY
- veto后的control terminal结果。

---

# 3. slow_grace：**PASS，参数不是无意义变体**

它不是简单把180秒改300秒。

代码真实增加了：

- deadline到达后；
- 最近3帧经济值严格递增；
- 当前经济值不低于progress anchor；
- liq保留≥85%；
- lifetime仅一次 `grace_used`;
- 给一次120s grace。

这构成真实状态差异。

### 解释限制

gap/source reset 后：

- `grace_used`不会恢复；
- 但progress clock会重新开始。

所以实际**墙钟持仓时间**可以因数据断流超过“180+120”。

这是合理的“只按可观察市场时间判断”，但必须报告：

`observable-time grace`，不能称严格墙钟+120秒。

共同 hard-stop/trailing/max-hold 先触发的机会必须进入 denominator，不能只统计成功领到grace的仓。

---

# 4. giveback_duration：**BLOCK 当前实现，需最小修正**

这是本轮我发现的唯一明确实现/冻结合同冲突。

冻结卡要求：

> running profit `H=max(V-S)` 是截至当时已知的高水位；gap/provider变化只应中断“在线下驻留时间”，不应抹掉已经观察到的盈利峰。

但 `evaluate_round2_exit()` 当前在任何 reset 时执行：

- `peak_profit = value - stake`

也就是**把历史已知peak重置成当前利润**。

例子：

- 曾经净利润 +2U；
- 回吐到 +0.8U；
- provider切换；
- reset后 `peak_profit` 变成 +0.8U。

之后50%回吐线也随之大幅下移，甚至不再满足原来的回吐事件。

这会系统性让source/gap事件“擦掉过去的盈利峰”，与冻结的：

`截至当时 running H=max(...)`

不一致。

### 最小修正

gap/source时：

- 清 `under_since`
- 清冻结的本次 `profit_line`
- 重建连续驻留证据

但**保留position lifetime已知 `peak_profit=max(old_peak,current_profit)`**。

不需要新状态层、新表或新需求。

修完后 **PASS**。

---

# 5. response_exhaustion：**PASS，但必须按proxy解释**

当前规则确实和旧 `activity_failure` 不同：

旧：
- price/value已经下降
- buy share反而上升
- volume增加

新：
- 第一段价格log斜率>0
- 第二段仍非负，但≤前段10%
- rolling m5 volume连续上升
- buy-share连续下降并最终<0.5

因此它是：

> **尚未跌价前的正响应耗尽**

不是换名复制。

不过：

`M0<M1<M2`

仍然只是重叠5分钟窗口代理。

禁止表述为：

- 新增资金流不断增加；
- 边际资本效率下降；
- 独立卖家扩张。

正确解释只能是：

**reported rolling activity增加，而局部价格响应衰减。**

共同risk若频繁抢先触发，不代表机制无效；报告要列：

- 三帧完整机会
- 满足response条件
- 被公共risk抢先
- 专属trigger
- next-frame fill
- counterpart结果。

---

# 6. runner_requalification：**PASS，实质新机制**

实际代码满足最关键的因果点：

- 只有**真实partial fill完成后**才创建runner epoch；
- 保存真实 `fill_id / filled_at`;
- 保存实际 remaining quantity；
- remaining cost按实际allocated cost计算；
- 初始余仓净值来自partial后的剩余数量；
- 不依赖旧 `principal_recovered`；
- 不拿partial前高点冒充新runner进展。

candidate与control还有完全相同的首次：

`+30% → 后帧卖50%`

所以能比较的是：

> partial发生后，余仓是否需要180秒内重新取得资格。

这是新行为，不是“已有partial确认”换名。

### 公共risk遮蔽

+30%本身同时已经进入通用trailing激活区域。

所以不少runner可能在180秒前由共同 trailing/maxhold/rug 退出。

这必须视为**正常竞争风险**，不能为了让requalification多触发而关闭公共risk。

报告应包含：

- common entry
- TP trigger
- partial pending
- actual partial
- runner epoch
- qualified
- 180s fail
- common-risk preemption
- open/right-censored。

---

# 7. 参数喷洒判断

当前五组我不认为属于无意义参数喷洒：

- chase：BUY vs NO-BUY
- slow_grace：一次状态许可
- giveback：frame-count → observed-duration
- response：未跌价前响应耗尽
- runner：actual partial后新资格epoch

都有行为状态改变。

但我明确反对立刻再注册：

- chase 2%/4%/6%/8%
- grace 60/120/180
- giveback 60/120/180
- runner 120/180/300

先让这一份冻结合同产生自然结果。

---

# 8. reserve / multipool：根裁决正确

`RESERVE_INPUT_FEASIBILITY.md` 给了实质新事实：

- 30个observer snapshot中12个有两侧正数量；
- 8个是provider标记PumpSwap；
- 2个明确Raydium CLMM也有base/quote数量。

所以：

> **有两侧数量 ≠ CPMM reserve已验证。**

轴9目前最多可叫：

`provider-reported bilateral quantity proxy`

不能叫：

- LP注资；
- 真实reserve增长；
- 可执行深度增长。

我支持**暂不纳入本10臂**。

轴11更明确：

- collector曾有 `raw.pairs`
- Runtime裁剪一次
- Store isolated raw再裁一次
- 当前observer历史没有可用多池集合。

因此当前 **DEFER** 正确，不应为凑机制强行新增。

---

# 9. API / CPU成本

这10臂本身：

- 无新API；
- 无新后台任务；
- exit是O(1)小状态；
- response只保留3帧；
- chase复用现有pattern history与首后帧；
- 注册append-only。

因此我没有发现结构性API成本blocker。

但生产当前 pattern/held本来就比主循环重，所以部署后仍应比较：

- held fetch P95
- apply/exit P95
- pattern interval/duration
- pending BUY count/expiry rate

这是运行验收，不是新增设计需求。

---

# 10. 还有一个值得保留、但不应抢本批部署的新轴

从 CAUSAL_REGIME 角度，我仍认为：

**mature prior-outcome hazard regime**

比小时/day策略更有信息：

只用当前机会之前已经成熟的独立episode，形成：

- recent dead/writeoff fraction
- recent median cost-adjusted outcome
- recent right-tail concentration

再看下一批机会。

但现在公共execution epoch刚变化，立即再加入regime-conditioned trading会混淆：

`执行修复效果 × regime效果`

所以我建议仍停留Shadow/研究，不加入当前10臂。

---

## 最终 PASS / BLOCK / REVISE

**公共execution repair：PASS，R2两个blocker已关闭。**

**chase：PASS Paper。**

**slow_grace：PASS Paper。**

**response_exhaustion：PASS Paper，proxy解释。**

**runner_requalification：PASS Paper。**

**giveback_duration：BLOCK，先修“source/gap reset抹掉历史peak_profit”这一处合同偏差。**

**reserve expansion：DEFER。**

**multipool share：DEFER。**

**opportunity ranking/regime：Shadow first。**

修掉giveback这一点后，我没有发现需要继续阻止这10个新账户严格前向小额部署的因果问题。测试通过只证明可达性；是否赚钱仍完全未知。
