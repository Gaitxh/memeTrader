# R3 STRATEGY

Source Chat: 6a9d94a3-6898-83e9-b5ce-9c598543fabf

Actual response; model/reasoning not independently verified. Snapshot review, not deployment certification.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R3-STRATEGY-RESULT
REPLY_TO: C2C-20260907-R3-STRATEGY
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
STRATEGY: STRATEGY
DISPOSITION: **REVISE_MINIMALLY_THEN_DEPLOY_BOUNDED_PAPER / BLOCK_ALPHA_PROMOTION**
SENSITIVE_DATA: NONE

本轮只读。未运行SQL、测试、Runtime、部署或写文件。指定 `ws_48a6e004-...` 不能作为本工具会话已打开workspace直接复用，因此通过官方隧道重新只读打开同一 `E:\memeTrader` checkout，实际workspace为 `ws_4273c509-...`。Chat实际reasoning档位无法核验，不冒称GPT-6/xhigh。

### 实际读取

- `RESEARCH_2026-09-07/FINAL_CONTRACT.md`
- `EFFECTIVE_POLICY_CORRECTIONS.md`
- `TOKEN_PRECURSOR_EVIDENCE.md`
- `EXTERNAL_CORRECTIONS.md`
- `R2_CAUSAL_STATISTICS.md`
- `R2_MICROSTRUCTURE.md`
- `src/memetrader/research_finalists.py`
- `tests/test_research_finalists.py`
- `store.py`：
  - finalist注册
  - 80帧history构造
  - `max_concurrent_positions`
  - `paired_entry_size`
  - cash/slot admission
  - `_capital_exit_result`
  - 通用exit→finalist exit优先顺序
- `capital_exits.py::_begin`

## 一、明确撤回我R2的旧判断

1. **撤回对 `l0_profit_lock` -62.54U paired delta 的机制反证解释。**
   当前实际 `principal_recovered/cost_covered` 状态不可达，93仓全部principal=0、0次L0 lock触发；结果主要混合了“25%半卖 vs control全卖”。它不能证明“正确实现的连续恶化锁利”失败。

2. **撤回 migration=精确迁移金额吸收、participation=真实钱包扩散的描述。**
   当前V002分别已经是：
   - young-absorption L0三帧承接；
   - early-quality L0成交强度/买方count代理。
   不能再拿旧名字解释当前收益。

3. R2原8+8草案已由 `FINAL_CONTRACT.md` 正式替换，本R3不再建议部署那16个。

---

# 二、13重点账户逐项裁决

| 机制 | R3裁决 | 关键限制/反例 |
|---|---|---|
| 190 滚动L0衰退退出 | **继续小额Paper** | 已有115 BUY/3次真实L0衰退触发；只是少亏线索，不是entry alpha |
| 187 volatility | **继续Paper，仅代理解释** | pressure=`方向count×volume/liquidity`，不是实际净资金流 |
| 196 局部韧性 | **只限条件型证据解释/继续既有运行** | 仅1 BUY；3–4成员局部集合，不是全市场regime |
| 185 cycle reset | **只限条件型证据解释** | 要≥720秒；observer最多80帧/20分钟，密采样可能根本装不下所需序列。不能把缺历史当静默 |
| 194 symbol leader | **只限条件型证据解释** | 当前0 BUY；只是同规范symbol局部冻结集，不是语义同题材 |
| boundary retest | **可部署5U Paper** | 实现确实冻结A上沿→B突破→C回访→再升；不是纯连续上涨 |
| seller absorption | **可部署，但名称只能作“卖笔份额翻转/价格承接代理”** | count不是金额；滚动m5窗口可能因旧交易滚出产生假翻转 |
| price→depth | **可部署，但只称provider-reported liquidity追认** | 同源限制已实现；仍不能证明LP注资、真实深度或净流 |
| profit budget exit | **最小修正后部署** | 净经济值计算正确；公共trailing在较高利润时可能先触发，这是已知可报告遮蔽 |
| progress clock | **最小修正后部署** | 连续可观察180秒逻辑正确；source/缺帧必须严格断时钟 |
| depth divergence | **最小修正后部署** | 价跌+经济值跌+liq连续>1%增长，确实与旧“liq不增”衰退相反 |
| activity failure | **最小修正后部署** | count-share+m5 volume仅活动代理；不能称金额买压 |
| baseline | **与4退出一起部署，不算alpha机制** | 必须保持共同受限entry；否则退出比较失真 |

---

# 三、代码合同核验

### 3个新entry：总体通过R3代码审查

`finalist_signal()` 的关键时序边界是真实存在的：

- 从最新向后抽9个≥15秒间隔帧；
- 总跨度120–600秒；
- 所选窗口内部**所有实际帧**都检查，不允许删除坏中间帧造图形；
- `activated <= observed <= ingested <= recorded <= decision`；
- token/pair必须一致；
- provider必须非空且全窗口一致；
- 相邻实际帧0–60秒；
- 最新≤30秒；
- price/liquidity/count/volume完整；
- 当前执行流动性门槛进入判断；
- 后一独立帧才真正成交。

因此我没有发现未来frame、跨source拼接或“断采=静默”的明显入场漏洞。

### 80帧限制

对**新3 entry**不是阻塞：它们只需要120–600秒、9帧。

对**185 cycle-reset**是真实coverage风险，因为旧合同要≥720秒。继续运行可以，但不能把0 BUY解释为机制失败。

---

# 四、5臂paired entry：实现确实是“共同受限入口”

代码不是名义配对。

- 5臂均 `paired_entry_group=finalist_exit_matched_v1`
- `paired_entry_size=5`
- 任一臂未进入 `admitted_arms` → 整组移除
- 任一臂cash不足 → 整组从实际投影中移除
- 任一臂达到4仓上限，会先被 `strategy_open_slot_limit` 阻塞，随后整组不进
- 测试还验证前三链、同token五仓共享同 `source_entry_fill_id`、5U和4仓上限。

所以“快退出者释放槽位后能自由得到更多机会”的收益被有意抹掉。该实验只能回答：

> **相同共同可接受机会下，不同exit treatment哪个更好。**

不能宣称独立运行时的资金周转收益。

### 但有一个最小可观测性缺口

cash不足导致整组过滤发生在实际逐arm decision写入之前，其他四臂未必获得清晰的 `paired_group_cash_blocked` 类原因。

这不会错误成交，但会损坏以后要求的“为什么五臂整组没进”的分母解释。

**最小必要修正：复用现有entry-decision/outcome字段显式记录paired group阻塞原因。不要新表、新平台。**

---

# 五、4个新exit的两个部署前小问题

### 1. provider非空应成为有效连续帧硬条件

Store会把 `mark_provider` 送入 evaluator，但 `evaluate_finalist_exit()` 当前完整性检查没有要求provider非空。

结果：

- depth/activity因为`bad`要求provider truthy，通常不会误触发；
- **profit-budget和progress-clock却可能在provider=None的连续frame上继续累计状态。**

这与最终合同“来源改变/不明时断开连续序列”不完全一致。

**最小修正：provider为空 → WAIT，不推进accepted/progress/peak连续状态。**

这是我认为部署前唯一明确代码语义修正。

### 2. 实际Store退出接线仍缺最终定向证明

代码路由已经存在：

`capital_exit_kind ∈ EXIT_KINDS → evaluate_finalist_exit → SELL → CAPITAL_EXIT → next valid original-pool frame`

而且：

- economic value = 已实现净回款 + 剩余数量按当前Paper卖出成本后的净额；
- future/duplicate/out-of-order/stale由 `_begin()` 拒绝；
- source变化会重置连续确认；
- 通用hard-stop/trailing先于finalist处理，finalist只在没有更早公共动作时接管。

**代码审查看起来正确，但当前 `test_research_finalists.py` 主要证明纯exit evaluator和实际entry接线；没有看到一个完整Store position→mark→capital state持久化→next-frame SELL的finalist集成生命周期。**

用户已经说“正在补实际退出接线检查”，我支持只补这一个窄测试即可；**不要求扩大测试体系。**

---

# 六、公共exit遮蔽不是bug

通用exit先运行，然后finalist exit：

- hard stop可先出；
- +30%后15% trailing可先出；
- 3个新entry还有标准TP；
- 4个exit+baseline无TP。

因此profit-budget在足够大的运行高点下确实可能被通用trailing遮蔽。`FINAL_CONTRACT` 已正确披露这一点。

**不要为了让finalist“多触发”而关闭公共安全退出。**

评价时报告：

- finalist触发数；
- 被hard-stop/trailing先行终结数；
- baseline对应结果。

即可。

---

# 七、外部v3与本地证据

采用 `EXTERNAL_CORRECTIONS.md`，不采用旧Chat citation：

- Pump.fun `0.198%` 是约**6分钟采集窗**结果/24h下界，不能称24h毕业率；
- 钱包论文v3修正后，30分钟买方数关联约+16.1%，SOL流入+6.3%的区间**包含0**；旧的巨额提升数字不能使用；
- BONK日期仍应区分airdrop/launch/first-pool等事件，不拿模糊日期构造本地t0。

更重要的是，本地 `TOKEN_PRECURSOR_EVIDENCE.md` 已完成而不是“仍进行中”：

- universe 12,000 hash样本里只有4,412能60m四分类；
- chain-meme 60m只有506 observed，另1,447 UNKNOWN、776 pending；
- 高volume/buy-ratio/count的边际差异在chain/time/age/liquidity分层后方向并不稳定；
- 暴涨vs失败甚至**0个**冻结分层能同时达到双方各3个样本。

因此外部论文和本地数据共同支持的只是：

**继续检验有序L0状态变化；不支持把volume/buy ratio/count直接升级为alpha阈值。**

---

# 八、与另一R2的实质分歧

我现在明确修正 `R2_CAUSAL_STATISTICS` 和 `R2_MICROSTRUCTURE` 对 profit-lock 的判断。

两份R2都把 `-62.54U / 59 paired` 当成当前profit-lock机制的负反证；代码和 `EFFECTIVE_POLICY_CORRECTIONS.md` 证明这是**错误归因**：

`l0_profit_lock` 所需的回本状态从未接通，0次实际two-frame lock触发。

所以正确裁决不是：

> “profit-lock被59组自然样本证伪”

而是：

> “该历史ID没有实际执行声称的L0锁利机制，因此其delta对该机制不可解释。”

这也是为什么最终采用新的 `profit_budget`，直接从**净经济值−stake**定义利润预算，比修旧principal布尔状态更干净。

---

## R3最终裁决

**BLOCK_ALPHA_PROMOTION: YES**
**BLOCK_LIVE: YES**
**BLOCK_RESET: YES**
**KEEP_OLD_206_AND_HISTORY: YES**

**3个新entry：可部署5U严格前向Paper。**

**4个新exit+baseline：在以下两件极小事项完成后可部署：**
1. provider为空不得推进连续exit状态；
2. 补一个真实Store退出接线定向生命周期检查。

另建议在现有entry reason中显式记录五臂因paired cash/slot导致的整组拒绝，以保证未来分母真实；**无需新表或新研究平台。**

除此之外，我没有发现需要扩大架构或阻止本轮8个新增账户部署的事实依据。所有自然收益、alpha、长期赚钱结论仍然**未核验/未成立**。
