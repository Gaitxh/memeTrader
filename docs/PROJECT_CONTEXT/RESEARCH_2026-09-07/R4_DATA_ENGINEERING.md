# R4 DATA_ENGINEERING

Source Chat: 6a9d94c3-d250-83e8-9ef0-24d6498281ea

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R4-DATA_ENGINEERING-RESULT
REPLY_TO: C2C-20260907-R3-DATA_ENGINEERING-RESULT
TYPE: RESULT
ROLE: DATA_ENGINEERING
CYCLE_ID: ALL_HISTORY_20260907
SENSITIVE_DATA: NONE

**DISPOSITION: R3_BLOCKERS_RESOLVED / ALLOW_SMALL_PAPER / BLOCK_ALPHA_AND_LIVE**

实际模型档位/推理配置：**未核验**。

我只复核了R3提出的两条具体阻断及对应收口代码/测试。结论如下。

### 1. paired拒绝分母阻断：**已解除**

R3担心5臂因某一账户现金不足而整组拒绝时，只出现`projected=0`、没有可解释的拒绝分母。

当前 `store.py` 已在既有 `entry_evaluations.feature_json` 中保存：

- `paired_group_not_all_eligible`
- `paired_group_cash_blocked`

且按5个arm逐臂写入 `paired_rejections`，无新表、无新API。

对应Store测试实际构造：

- baseline账户资金不足；
- 5臂全部0 fill；
- `paired_rejections`正好5项；
- 五项均为 `paired_group_cash_blocked`；
- 资金恢复后同一正常机会5臂一起成交。

**因此该R3阻断解除。**

---

### 2. 四exit真实Store接线阻断：**已解除**

R3要求的不只是纯函数PASS，而是：

`真实Store持仓mark → 专属exit触发 → pending → 后续独立原池观察 → SELL`

当前19项测试已覆盖：

- `profit_budget`
- `progress_clock`
- `depth_divergence`
- `activity_failure`

其中：

- candidate触发后先进入pending；
- 触发前已经observed、但触发后才received的迟到报价**不能作为fill**；
- 只有 `observed_at > trigger/decision` 的后续独立观察才能成交；
- baseline保持open，不被candidate exit污染。

三种新entry也实际走过Store：

`9帧状态成立 → trigger → 决策前observed的迟到帧拒绝 → 真正后续帧BUY`

不是只测纯函数。

**因此第二条R3阻断解除。**

---

### 3. 我额外核对的R3相关边界

这些不是新要求，只确认已有修正成立：

- 新8臂显式 `require_post_decision_observation=True`，旧206默认语义未被全局改写；
- exit的post-frame同时要求 `recorded_at` 和 `observed_at` 都晚于pending trigger，并保持15秒新鲜度；
- NULL中间frame会清连续确认状态，不允许跨缺值拼出两次恶化；
- provider为空时WAIT；
- provider/gap切换会重置连续状态及profit peak，旧source峰值不会带入新source；
- EVM新exit adapter已做canonical pool identity处理；
- 5臂slot限制发生在paired admission之前，某臂满4仓时整组不进入；
- 7机制synthetic计算P95约 **1.1643ms**，且没有API/SQL；这里只能说明纯计算开销很小，不代表Runtime端到端SLA。

---

## 仍有已证代码反例吗？

**针对R3明确提出的两条部署阻断：没有发现仍存在的已证代码反例。**

我没有发现需要继续阻止这8个新增账户进入5U严格前向Paper的代码证据。

现存事项都属于已披露的**解释限制**，而不是部署阻断，例如：

- liquidity是reported USD liquidity，不是LP净流/真实depth；
- m5 volume/count是滚动聚合，不是逐笔金额流；
- provider/coverage不足会产生WAIT；
-公共stop/trailing可能遮蔽部分新exit；
- stage185/194仍有自然覆盖不足；
-普通Paper仍是mark±成本模拟。

这些不构成继续卡住小额Paper的理由。

---

## 最终R4裁决

**小额Paper：ALLOW。**

允许条件仍是最终合同：

- 仅新增8账户；
- 5U；
- 最多4仓；
- 不重置旧206；
- 不新增API/平台；
- 不回填；
- 不Live；
- 从真实新frontier开始；
- 部署、自然成交、经济证据分别报告。

**Alpha/长期盈利宣称：BLOCK。**
**资金放大：BLOCK。**
**Live：BLOCK。**

19项定向测试和约1.16ms synthetic P95只能证明合同/接线与计算成本符合预期，**不证明这12个机制赚钱**。

实际读取：

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R3_RESOLUTION_AND_VALIDATION.md`
- `src/memetrader/store.py` 对应 paired rejection / post-decision fill 段
- `src/memetrader/research_finalists.py` 相关定义定位
- `tests/test_research_finalists.py` 收口后的paired、NULL/source、真实Store entry/exit必要测试段

未运行新SQL、未重复测试、未修改代码/Runtime/DB、未部署。

**R4 DATA_ENGINEERING：R3具体部署阻断已解除，可进入小额严格前向Paper；盈利和Live资格仍完全未建立。**
