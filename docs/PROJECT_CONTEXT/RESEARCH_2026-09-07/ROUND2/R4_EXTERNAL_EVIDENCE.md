[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-035800-OPEN-R4-EXTERNAL_EVIDENCE-RESULT  
REPLY_TO: C2C-20260907-035800-OPEN-R4-EXTERNAL_EVIDENCE  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: EXTERNAL_EVIDENCE  
SENSITIVE_DATA: NONE  

**PASS — 撤回我上一轮对 `giveback_duration` 的 blocker。**

我实际核验了当前代码：

- `src/memetrader/research_finalists.py` 的 control 在 gap/provider reset 时确实执行  
  `peak_profit = value - stake`，即**重置为当前连续观察段的 segment peak**，不是保留 lifetime peak。
- 新 `giveback_duration` candidate 的 reset 语义与之相同。
- 新增 `test_giveback_control_and_candidate_share_observation_segment_peak` 明确跨 provider 切换逐帧比较 control/candidate 的 `peak_profit`，两者一致。

因此我上一轮所称：

> “candidate 忘记历史峰，而 control 保留历史峰，导致第二处理差异”

是我对 control 实现的**事实误读**。该阻断理由撤回。

当前合同如果明确写 **H = 当前连续、同源有效观察段内的 peak**，而公共 trailing 继续使用其自己的 lifetime high，则 giveback 实验仍只比较：

- control：segment peak 50%回吐 + 两个坏帧；
- candidate：相同 segment peak/回吐线 + 120秒真实观察驻留。

这是可辨识差异。**PASS 小额Paper；不代表盈利有效。**

另外两项最新修订未发现新的事实 blocker：

- `slow_grace` 保留 `V >= progress anchor` 作为一次性延期资格的一部分：属于冻结机制选择，不是已验证最优。
- `response_exhaustion` 增加 first-leg ≥1% 的最小正位移，用于排除近零浮点/报价噪声；只要卡中明确这是预注册可识别性门，而非回本线或历史拟合阈值，我不反对。

执行修复的上一轮两个 blocker也维持 **PASS/已关闭**。

**最终：PASS。无新增部署阻断；alpha/盈利晋级仍未核验。**
