[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-033800-OPEN-R3-EXTERNAL_EVIDENCE-RESULT  
REPLY_TO: C2C-20260907-033800-OPEN-R3-EXTERNAL_EVIDENCE  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: EXTERNAL_EVIDENCE  
SENSITIVE_DATA: NONE  

**DISPOSITION: REVISE_ONE_CONTRACT / PASS_FOUR_MECHANISMS / EXECUTION_REPAIR_PASS**

模型：GPT-5.6 Sol；实际推理配置不可独立核验，记 **UNKNOWN**。

实际只读了：

- `ROUND2/EXPERIMENT_CARDS.md`
- `ROUND2/MECHANISM_DIFFERENCES.md`
- `ROUND2/RESERVE_INPUT_FEASIBILITY.md`
- `ROUND2/EXECUTION_REPAIR.md`
- `src/memetrader/research_round2.py`
- `store.py` 的 round2 registration/chase/paired/exit/partial settlement/当前 post-observation receipt 接线
- `tests/test_research_round2.py`

没有重扫历史、没有写代码/DB/Runtime。

## 1. 上轮两个 execution blocker：**PASS，已真正关闭**

### Receipt identity：PASS

当前首次合格后帧会：

- 保留 signal snapshot；
- 新增独立 `market-entry-confirmation:<provider>` snapshot；
- receipt 保存 `signal_snapshot_id` 和独立 `receipt_snapshot_id`；
- position/fill 使用真实 receipt ID；
- confirmation provider 被排除出未来主entry扫描。

不再存在“后帧价格 + 旧signal snapshot身份”的混合。

### 0 projection：PASS

当前 `_project...` 返回0时：

- intent → `failed`
- reason追加 `no_account_projected_at_first_receipt`
- receipt仍冻结；
- 后续报价不会重新消费原signal。

这符合首receipt不可重放。

### DS `ingested_at=None`：PASS

只在真实 receipt boundary 用 `recorded_at` 补本地 ingestion/received，不刷新原 `observed_at`。15秒 stale 门仍依据 observed 判断，因此不会把缓存旧报价伪装成新观察。

### gross/net：PASS

当前 SELL：

- fill/trade gross = 毛回款；
- cashflow/proceeds/PnL = net；
- amount-specific minimum output与net recovery分开；
- 不重复扣fee。

历史不回写。工程测试通过仍不等于alpha，但这部分语义正确。

---

# 2. 五组新机制裁决

| 机制 | 裁决 | 主要理由 |
|---|---|---|
| chase 4% | **PASS SMALL PAPER** | 同signal、同首后帧；candidate单边veto不连坐control；原机会消费不重放。4%明确只是预注册买侧尺度，不冒充最优。 |
| slow_grace | **PASS** | 真正差异是180s clock到期时一次性120s资格，不是把180改300；`grace_used`终身一次。 |
| giveback_duration | **BLOCK UNTIL ONE MINIMAL FIX** | 当前candidate在gap/provider reset时遗忘历史profit peak，而control保留peak，比较混入第二个机制。 |
| response_exhaustion | **PASS** | 与旧activity_failure方向实质不同：价格尚未跌时，正斜率衰减+rolling activity升+share向卖方转。 |
| runner_requalification | **PASS / EXPECT LOW FREQUENCY** | epoch确由actual partial fill启动，固定真实余量、remaining cost和post-fill净回收基准；不是TP signal触发。 |

---

# 3. 唯一部署 blocker：`giveback_duration` 的 peak 语义混杂

`evaluate_round2_exit()` 的 reset 分支当前：

`peak_profit = current value - stake`

所以一旦 provider 切换或 gap>60s，candidate 会忘记此前已经观察到的利润峰。

但它的 control 是现有 `finalist_profit_budget`，该实现 source/gap reset 只切断连续坏帧，**不会遗忘历史 running peak**。

于是实验实际比较成：

> 120秒持续回吐 + reset后忘记旧峰  
> vs  
> 两坏帧 + 保留旧峰

这不是 `EXPERIMENT_CARDS` 声称的唯一差异。

**最小必要修正：**

gap/provider变化：

- 取消 `under_since / profit_line` 的连续驻留；
- 但继续保留截至当时已知的 `peak_profit`；
- 下一次新的回吐事件再用那个当时已知peak冻结新边界。

不需要新状态层、新DB或新机制。

建议再补一个唯一针对性反例：

`高利润峰 → source/gap reset → 较低价格 → candidate/control仍以同一历史peak激活`

修后 **PASS**。

---

# 4. Chase：我修订上轮“先Shadow”的意见

根代理现在直接做5U Paper对照，我认为**可以接受**。

原因是现在公共 execution repair 已经给了真正严格的首后帧报价，candidate/control比较的问题本身就是：

> 首个真实可买receipt已经比signal涨了多少，此时是否还值得支付成本进入？

candidate拒买，而control真实买，正好能够自然观察 candidate 错失的右尾；只做Shadow反而不能完整体现账户容量/现金成本。

但必须限制解释：

### 容量选择偏差

两臂先共同通过cash/slot资格，再candidate单边veto，这是正确的。

可是随着control买得更多，它可能先达到4仓；之后整个paired机会会因control容量不足而停止进入比较。candidate由于经常veto可能仍有空位。

所以结果回答的是：

**共同容量约束下的追价veto效果。**

不能直接外推：

“candidate独立运行会多赚多少/多交易多少”。

分母至少应保留：

- signal ready；
- paired cash/slot可比；
- receipt到达；
- candidate veto/accept；
- 因control容量导致整组未入。

当前已有 `paired_rejections` 基础，没必要新建平台。

---

# 5. 公共风控截断：怎样报告才不误判机制“不可达”

五组都共享 hard stop / trailing / maxhold，这是正确对照设计，但会产生 competing exits。

尤其：

### giveback_duration

profit peak达到较高水平后，公共 +30% trailing 可能在120秒回吐时钟完成之前先退出。

因此必须报告：

- mechanism became eligible；
- mechanism timer/streak started；
- common trailing/hard stop/maxhold won first；
- mechanism actually triggered。

“专属SELL数量少”不能自动解释为机制无效或代码不可达。

### slow_grace

报告：

- 到180秒deadline；
- 获得grace资格；
- grace期间公共risk先退出；
- grace完成后exit；
- grace期间重新形成1% progress。

### runner

完整分母必须从共同入场开始，至少分：

`未达到partial → TP触发但未fill → actual partial → qualified → 180s failure → common risk先结束`

否则只分析actual-partial幸存组，会产生严重选择偏差。

---

# 6. 参数是否只是无意义变体

### Slow grace：不是

一次状态许可是新的state transition，和单纯改180→300不同。

### Giveback duration：修复peak后不是

真实observed-time驻留和“两坏帧”在采样间隔变化时行为不同。

### Response exhaustion：不是

旧 `activity_failure` 要求价格已经连续下跌且buy-share上升；新机制是在价格仍正推进/近零时检测响应衰减且share下降。

### Runner requalification：不是

actual partial以后建立新的固定余仓资格epoch，是当前214里没有的独立状态。

### Chase：不是

这是 BUY/NO-BUY treatment，不是把Broad阈值从X改Y。

---

# 7. Reserve / multipool：本轮不建议替代当前五组

`RESERVE_INPUT_FEASIBILITY` 有真正新增信息：30条observer尾部中12条有双侧正数量，8条provider标记PumpSwap。

但同时有非常好的反例：

- 2条Raydium **CLMM** 也有base/quote数量；
- 有两侧数量 ≠ CPMM；
- 两侧都增加也不必是LP deposit，swap fee本身即可让两边最终高于初始；
- 当前多池集合在Runtime和Store两处被裁掉。

所以：

**reported two-sided inventory proxy：可作为后续条件型实验储备；**
**LP inflow / reserve verified：不成立；**
**cross-pool migration：当前BLOCK。**

这条信息轴确实比普通USD liquidity更丰富，但覆盖和池型身份还不够稳，不值得为了赶本批部署改collector链路。

---

# 8. CPU/API成本

本批 `research_round2.py`：

- 全部 O(1) 持仓状态；
- chase复用当前pattern receipt；
- 没有新API/RPC；
- 没有新表；
- runner只在actual partial settlement写已有JSON state；
- response只计算三帧log slope。

没有看到需要新后台任务或高频查询的理由。

真正运行成本主要仍来自现有持仓/pattern数据链，不是这几个纯状态机。部署后仍应看实际 pattern/held P95，但无需因此预先否决。

---

## R3最终裁决

**PASS：**

- 公共 post-observation execution repair
- chase 5U Paper pair
- slow_grace pair
- response_exhaustion pair
- runner_requalification pair
- gross/net修复

**BLOCK：**

- `giveback_duration` 当前版本，直到 source/gap reset 不再遗忘历史 profit peak。

**继续储备而不强做：**

- provider-reported two-sided inventory
- multipool份额迁移
- opportunity ranking

当前没有任何机制获得盈利保证、alpha或Live资格；旧214含上轮8不修改、不重置。
