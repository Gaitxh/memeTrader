# Exit mechanism marginal value：严格同 entry-fill 配对

冻结范围同 [BOUNDARY.json](../../../data/research/alpha_diagnosis_20260907/gate_exit/BOUNDARY.json)。Exit 只有同时满足同 token、cohort、`source_entry_fill_id`、stake、初始金额、entry execution price，且双方在截止前 `closed/written_off`，才进入差额。`deltaPnL=candidate-control`；open、缺失或 entry 不同均为 unknown。CI 对每个 token 先聚合再 bootstrap 10,000 次，避免把同一 token 的复制账户作为独立样本。

## 修复后清洁窗口

每项 entry identity mismatch=0；所有列出的终结对都通过实际 entry-fill/金额/执行价合同。时间块覆盖 09–13 UTC，Finalist/Round2 为 5/11/9/7/3 对；resource-profit 为 0/0/9/7/3 对。该窗口仍短，CI 跨零的结果不可称 alpha。

|机制|终结配对/独立Token|行为分歧|候选优/对照优/相同|ΔPNL U|95% token CI U|持有时长 Δ秒|尾部回款比均值|候/对核销|裁决|
|---|---:|---:|---:|---:|---|---:|---:|---:|---|
|profit_budget|35/35|3|1/2/32|-1.7769|[-0.1359, 0.0085]|-44.2|接近1|7/7|不足，偏负|
|progress_clock|35/35|12|6/5/24|+9.0985|[-0.0545, 0.6845]|-339.3|接近1|6/7|行为真实变化，但 CI 跨零|
|depth_divergence|35/35|0|0/0/35|0|[0,0]|0|1|7/7|未触发，不是有效证据|
|activity_failure|35/35|0|0/0/35|0|[0,0]|0|1|7/7|未触发，不是有效证据|
|slow_grace|35/35|12|0/0/35|0|[0,0]|0|1|6/6|有内部状态差异但无实际经济差异|
|giveback_duration|35/35|3|2/1/32|+1.1598|[-0.0085, 0.0995]|+31.5|接近1|7/7|不足，CI 跨零|
|response_exhaustion|35/35|0|0/0/35|0|[0,0]|0|1|7/7|未触发|
|runner_requalification|35/35|1|0/1/34|-0.1293|[-0.0111,0]|-8.9|接近1|7/7|不足，单次不利分歧|
|resource_profit_structure|19/19|4|0/0/19|0|[0,0]|0|1|3/3|未出现经济差异|

“接近1”表示逐对 tail-retention（candidate/control terminal proceeds）在绝大多数相同终结中为 1；完整逐对值保存在 [exit.json](../../../data/research/alpha_diagnosis_20260907/gate_exit/exit.json)。它不是未观察到的退出后路径或理论 ATH。

## 更早历史（隔离）

较早记录在同 entry 合同下有更大样本，但发生于不同执行/修复边界，不能用于认证当前策略。它只提供方向反例：progress_clock +125.8524U、229 token 独立均值 CI [0.2510,0.8494]，而本清洁窗的同机制 CI 跨零；giveback_duration −0.9749U，runner −1.8806U。跨期方向不一致本身就是不把更早结果外推的理由。

所有写核销只是当前 Paper 合同下余仓归零，不代表链上 rug、真实成交或无价值。共同 partial 的减损也不会归因给 runner requalification；只有表中的差额归属候选 Exit 行为。

## 给最终裁决的边界

- 清洁窗口里唯一有非零信号的是 progress_clock、profit_budget、giveback-duration 和 runner；前三者的 token CI 均跨零，runner 只有一宗不利实际差异。没有一个 Exit 达到可靠可推广的实证门槛。
- “无差异”可能是未触发、共同退出，或尚未形成可辨认行为，不能改写成机制被证伪。
- 详细逐行、时间块、tail retention、writeoff 和 isolated 历史见 [exit.json](../../../data/research/alpha_diagnosis_20260907/gate_exit/exit.json)。
