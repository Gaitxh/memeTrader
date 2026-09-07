# Alpha诊断：独立评审共同事实与预注册

最新用户明确要求停止策略扩张；本轮只读核验、离线统计、Chat独立R1及交叉R2/R3，最终Court为建议，不执行冻结/退役/注册/重置/Live。不得用旧研究任务恢复生产修改。

统一截点2026-09-07T13:38:59.399800Z；当前r6资金期 `chain-meme-trader/funding-20260906-v002-final-1000`。现有230策略，103追加合同；本期25063仓位/1553Token，45872cohort/1815Token，51937交易。计数不是独立样本数。

边界见 `data/research/alpha_diagnosis_20260907/BOUNDARY.json`。历史及上一轮增量文件均位于 `E:/memeTrader/docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/`，不是当前 Alpha 目录：`HISTORICAL_EVIDENCE_MAP.md`、`HISTORICAL_STATISTICS.md`、`RESOURCE_BOUND_ECONOMICS.md`、`RESOURCE_BOUND_STRATEGY_MAP.md`、`RESOURCE_BOUND_ACCEPTANCE.md`。旧汇总不得冒充本轮重跑或最新结果。本目录统计文件在R1期间仍生成中，R1读到的中间结果必须在R2用最终工件替换，尤其latency的历史receipt键关联曾错误，不作为证据。

预注册方法：优先使用最新09:19:47Z修复后可核验原池/三时钟的独立机会，较早时期分开研究，不宣称所有旧仓都被证明有bug。模型主目标为未来15分钟可观察且后观察执行的成本跨越；30/60分钟仅敏感性，不选最好horizon发布。特征只能来自决策时已observed/ingested/recorded的源帧，缺失不回填；标签可用未来但必须与特征隔离。实际每期成本无法重建时不套用今天4%/4%。

Logistic和固定小树模型只作诊断；按时间分块、训练标签必须在测试起点前成熟，测试Token从训练剔除。预处理只拟合训练，报告校准、AUC/PR-AUC/Brier、净结果上下分位、Token聚类区间和移除右尾敏感性。不把移除最大赢家后仍须正收益设为晋级门。多日期/干净独立样本不足须允许E判决，不能用漂亮块内AUC代替跨日期证据。

路径中短暂峰值只是事后上界，不能直接当可交易收益或确定“退出失败”；失败/缺帧/未覆盖窗口不能填零、当死亡或当未跨越。Gate保留拒绝机会的控制结果，Exit只比较同实际入场。比例分母同时列独立Token、机会、仓位和未分类覆盖。

R1各Chat独立分析，不读取其他本轮reviewer结果；可以挑战以上方法。优先指出为什么200+账户未证明alpha、最可能瓶颈、伪样本量、右尾/日期/链驱动和可证伪实验。禁止brainstorm新策略或向执行线程发送生产修改命令。R2/R3由Codex提供已核验统计与异议，按证据裁决，不投票。报告无法读取的文件、未知事实及实际可核验的模型设置。
