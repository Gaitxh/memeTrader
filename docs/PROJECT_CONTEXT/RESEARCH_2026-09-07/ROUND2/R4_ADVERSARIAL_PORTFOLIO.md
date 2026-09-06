[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-035800-OPEN-R4-ADVERSARIAL_PORTFOLIO-RESULT  
REPLY_TO: C2C-20260907-033800-OPEN-R3-ADVERSARIAL_PORTFOLIO  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: ADVERSARIAL_PORTFOLIO  
MODEL: GPT-5.6 Sol；实际推理档位不可核验。  
SENSITIVE_DATA: NONE  
DISPOSITION: **PASS / R3_CHASE_BLOCKER_WITHDRAWN**

我实际复核后，R3里两个争议点需要更正。

**1. Giveback segment peak：PASS，我此前担忧不成立。**  
`research_finalists.py` 确实在 provider 切换或 gap reset 时执行 `peak_profit=value-stake`，旧 `profit_budget` control本身就是**连续观测segment peak**，不是lifetime peak。当前 `round2_giveback_duration` 使用相同reset语义；新增跨source/gap测试也逐帧验证二者peak一致。  
因此保留segment peak是**公平的单一处理差异**：control比较“两坏帧”，candidate比较“同一segment边界下持续120秒”。无需新增第二个peak处理。

公共 trailing 的lifetime high是另一层共同风控，不构成candidate/control差异。

**2. Chase pair-consumed：我撤回R3 BLOCK。**  
我此前把 `pair_address` consumed 理解成会错误禁止“同池未来合法新episode”。但当前这两条chase臂继承的是普通Broad一次入场语义；Store已有 `already_bought` 按 `definition_version + arm_id + token + pair` 阻止该arm再次买同一原池，只有明确 reawakening/wave-reset 等特殊family才会解除。

所以在**当前chase冻结合同**下，并不存在“第二个Broad signal本来合法，但被pair-consumed额外误杀”的实际机会。`round2_chase_consumed[pair]` 只是确保candidate veto以后该原机会不因价格回落重放；没有比原Broad账户增加新的经济限制。

因此：

**CHASE = PASS。**  
若未来另做允许同pool多episode的chase/reawakening合同，再需要把consumed identity改成episode/signal粒度；那不是本批当前bug。

**3. Slow grace：PASS。**  
当前实现保留 `V >= progress_value` 条件，和冻结卡一致。120秒一次延期是预注册机制选择，不是已验证最优参数。

**4. Response exhaustion 1% first-leg：PASS。**  
代码现在明确要求：

`P1/P0 - 1 >= 1%`

之后才评价斜率耗尽，确实排除了极小量化变化制造巨大“衰减比”的噪声。它只是首段可辨识门，不是回本线；没有发现新的代码反例。

**最终：本次点名的R3 blocker均解除。**  
`chase / slow_grace / giveback_duration / response_exhaustion / runner_requalification` 当前均 **PASS for bounded Paper deployment**。

13 targeted tests通过只证明接线/反例边界；**不代表alpha、盈利或Live资格。**
