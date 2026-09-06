[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-033800-OPEN-R3-CHAIN_MICROSTRUCTURE-RESULT  
REPLY_TO: C2C-20260907-033800-OPEN-R3-CHAIN_MICROSTRUCTURE  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: CHAIN_MICROSTRUCTURE  
SENSITIVE_DATA: NONE  
MODEL_STATUS: **未知；项目侧无法核验实际Chat模型/推理档位。**

## 总裁决

**4组 PASS / 1组 REVISE-BEFORE-DEPLOY。**  
不构成 alpha、增资或 Live 资格。

我上轮两个执行 blocker 中，**receipt锚点 blocker 已关闭**：真实后帧现在拥有独立 `receipt_snapshot_id`，position `entry_snapshot_id` 指向该receipt而非signal；signal ID单独冻结，confirmation provider被排除出主入场扫描。DS `ingested_at=None` 也已在真实接收边界补本地received而不刷新observed。0 projection 后 intent=failed、不等待后来更优价。工程上这部分 **PASS**。

我上轮“公共修复改变旧214未来行为”的意见并未被技术上消除，而是现在被正确处理为**显式 execution epoch 改变**：旧hash/资金/历史不回写，同时承认未来普通主入口时序已改变。按epoch分层即可，不应再声称行为完全没变。

---

## 1. Chase 4%：**PASS 小额Paper**

实际接线符合实验卡：

- candidate/control先共同经过slot/cash/后帧资格；
- 然后仅candidate执行4% veto；
- control不被连带拒绝；
- `fill_signal_snapshot_id`取冻结signal；
- veto后 `round2_chase_consumed` 防止价格回落后重放原机会。

4%是买侧成本尺度，代码没有把它冒充8.33%往返盈亏平衡，合理。

### 必须保留的解释限制

一旦candidate频繁veto，它会比control保留更多空槽；但成对 admission 以后仍要求两边都有容量。于是control先占满4仓时，candidate虽然有闲置资本也会被一起挡掉。

因此该实验估计的是：

> **control容量约束下的共同机会 treatment effect**

而不是candidate独立运行时的资本周转收益。

报告必须保留 `paired_group_not_all_eligible / cash_blocked` 分母。不能用candidate更少持仓直接说效率更高。

---

## 2. Slow grace：**PASS，但公共风险造成右删失**

当前实现真正区别于progress_clock：

- 原1%大进展逻辑不变；
- 180秒deadline时要求最近3帧经济值严格递增；
- liquidity保留≥85%；
- 一生只给一次120秒延期；
- `grace_used`不会因source/gap或后来大进展恢复，因此不会无限续杯。

这是实质状态差异，不是把180改300。

公共hard-stop/trailing/max-hold会先截断部分机会，所以后续评价必须报告：

- reached-clock-deadline；
- grace eligible；
- grace granted；
- common-risk-censored；
- grace success/failure。

**没有专属触发 ≠ 机制失败。**

---

## 3. Giveback duration：**BLOCK当前代码部署，需一个最小修正**

机制本身有辨识性：

`旧control = 两个坏帧`  
vs  
`candidate = 固定利润线下连续observed 120秒`

不是单纯阈值微调。

但代码与冻结卡存在一个真实状态错误。

`evaluate_round2_exit()` 在 provider切换或 gap>60s 的 reset 中执行：

`peak_profit = value - stake`

这会把**此前已知的历史利润峰 H 擦掉**。

而实验卡要求：

- running `H=max(V-S)` 是当时已知利润高点；
- gap/source变化只应取消**连续驻留证据**；
- 不应把已经真实观察过的盈利峰当作从未发生。

反例：

1. 仓位曾达到 +40%利润；
2. 回落到 +10%，刚开始under-line；
3. provider切换；
4. 当前实现把peak重置成+10%；
5. 之后即使持续+5%，原本应研究的“从+40%回吐”已经消失。

这会系统性让数据缺口/换源**宽恕历史回吐**。

### 最小必要修复

reset时：

- 清 `under_since`
- 清 `profit_line`
- 清连续window
- **保留 `peak_profit=max(existing_peak, current_profit)`**

不需要新表、新API或新规则。

修完补一条：

`高峰 → 回吐 → source switch → 继续低于原峰50%`

验证旧峰仍存在、但驻留时钟从新source重新开始。

修复前该候选 **BLOCK DEPLOYMENT**；control可注册与否由根统一处理，但为了配对完整性我建议整组一起等修复。

---

## 4. Response exhaustion：**PASS，机制差异成立**

实际规则：

- 3个5–60秒独立帧；
- `r1>0`
- `0 <= r2 <= 0.1*r1`
- rolling m5 volume连续上升；
- buy share连续下降；
- 最终share<0.5；
- 此时价格尚未真正下跌。

这与旧 `finalist_activity_failure` 明显不同：旧者要求价格/经济值已经连续下降且buyshare反而增加。

所以本批把“活动增加但价格正响应耗尽”和“卖方份额翻转”合成一个状态机，我赞成；无需再另注册近义卖压策略。

### 解释限制

`M0<M1<M2` 是**重叠5分钟窗口报告值上升**，不能叫新增成交资金加速。

另一个反例必须保留：

若 r1 极小正数，`0.1*r1`更小，规则可能对供应商量化/价格舍入非常敏感。第一版不建议再加最小r1阈值——那会开始参数喷洒；先观察实际trigger频率和价格精度，再决定是否机制不可辨识。

---

## 5. Runner requalification：**PASS，实际partial锚点可达**

这部分代码接线是本批最扎实的新状态之一。

我确认：

- candidate/control都在+30%时卖余仓50%；
- epoch只在**actual partial settlement**后创建；
- TP trigger/pending mark本身不会创建epoch；
- epoch冻结真实：
  - fill_id
  - filled_at
  - remaining quantity
  - partial后余仓净回收值
  - remaining cost
  - liquidity
- 不依赖旧 `principal_recovered`；
- 不拼partial前经济高点；
- 测试已从真实Store partial settlement走到candidate期限退出、control继续open。

这是实质新机制，不是125已有的“partial后重置high-water”。

### 需要明确的删失

公共trailing/hard stop/maxhold可能在180秒资格窗口之前关闭余仓。必须统计为：

`common-risk-censored-before-requalification`

而不是资格失败。

source/gap会重启**可观察时间预算**但保留partial基值，这与冻结卡一致。

---

# 6. 公共风控遮蔽：不是bug，但必须进分母

Store实际顺序仍是共同：

- hard stop
- trailing
- maxhold / TP等

先有机会占用action；普通Round2 exit只有当公共action尚未选中时才成为最终专属exit。

因此：

- giveback duration尤其容易被+30% trailing遮蔽；
- runner可能在资格deadline前被共同trailing清掉；
- slow grace可能在延期期间被hard stop；
- response exhaustion若稍晚出现也可能已被公共止损抢先。

这是实验设计中的**competing exit risk**。

正确报告不是：

`专属exit触发次数 / BUY`

而至少分：

`eligible state →专属trigger / common-risk-first / data-reset / still-open`

否则“专属trigger少”无法区分没信号还是先被公共保护截断。

---

# 7. Reserve / multipool：继续储备，根裁决正确

`RESERVE_INPUT_FEASIBILITY` 给了一个很有价值的实际反例：

30个observer尾部样本只有12个存在base/quote正数量，而其中2个明确就是Raydium CLMM。

因此：

> 有base/quote数量 ≠ CPMM。

同时当前observer两处裁剪掉`raw.pairs`，所以跨池份额机制目前没有自然历史输入。

根目前：

- reserve仅研究储备；
- multipool不强做；
- 不叫LP注资；
- CLMM不套CPMM；

我同意。暂时不要为了它扩本轮实现。

---

# 8. API / CPU成本

五组机制本身：

- 无新API/RPC；
- exit均O(1)短状态；
- chase复用已有pattern后帧；
- runner仅在真实partial后增加小状态；
- 不新增表或后台任务。

因此从结构上看成本较低。

但**9项测试通过不证明生产CPU无回归**。10新账户尚未部署，因此只能写：

**resource design PASS / runtime delta UNKNOWN**

部署后只需看原有：

- main interval
- held fetch/apply
- pattern observer

短窗是否明显恶化，不需要再造性能平台。

---

# 9. 执行修复最终复核

### PASS
- signal ID与receipt ID已分离；
- receipt snapshot成为真实entry snapshot；
- confirmation snapshot provider排除主扫描；
- first receipt immutable；
- DS无ingested时使用本地received、不改observed；
- observed严格晚于decision；
- 错池/NULL/stale不成交；
- expiry终止；
- 0 projection=failed，不后来重放；
- pending进入原池watch；
- gross/net SELL字段修复正确；
- 历史不回写。

### 仍然必须诚实标记
`market-entry-post-observation/v1` 是一个新的**公共执行epoch**，确实改变了旧主入口未来成交时序。它不是“旧214完全不变”，但旧策略规则/hash/账户/历史保持了原样。

这已经不是我R2时的未解决技术blocker。

---

# 10. 最终 PASS/BLOCK/REVISE

| 机制 | R3 |
|---|---|
| chase 4% | **PASS Paper** |
| slow_grace | **PASS Paper** |
| giveback_duration | **BLOCK，修复source/gap时错误清历史peak后再上** |
| response_exhaustion | **PASS Paper** |
| runner_requalification | **PASS Paper** |
| reserve proxy | **RESERVE** |
| multipool | **RESERVE** |
| opportunity ranking | **Shadow/Reserve** |

**不建议为了“10臂成套”忽略giveback的状态错误。最小修完这一处即可，不需要扩审。**

本轮实际读取：

- `ROUND2/EXPERIMENT_CARDS.md`
- `ROUND2/MECHANISM_DIFFERENCES.md`
- `ROUND2/RESERVE_INPUT_FEASIBILITY.md`
- `ROUND2/EXECUTION_REPAIR.md`
- `src/memetrader/research_round2.py`
- `src/memetrader/store.py` 中Round2注册、chase、配对、exit adapter、partial epoch、pending后帧receipt/gross-net相关段
- `tests/test_research_round2.py`
- 有界定位 `tests/test_paper_execution.py` 的receipt/DS-ingested断言

未跑全历史SQL、未修改应用/DB/Runtime。

**R3结论：执行修复的核心技术blocker已关闭；五个新机制中四个具备可部署的小额前向辨识性，giveback-duration当前有一个具体且局部的状态语义bug，修复后再部署整组最干净。**
