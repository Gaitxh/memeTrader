# Opportunity master：冻结离线机会

固定截点 2026-09-07T13:38:59.399800Z。全期45872 cohort / 1815 Token、25063仓 /1553 Token。修复后原始纳入6305 cohort；有效源帧合并后6064机会/93 Token，其中6058有共享v6 receipt记录，只有404个机会存在账户策略BUY；严格三时钟后帧子集6041机会/82 Token。

研究单位=chain/Token/原池/冻结signal snapshot，重复cohort挂接而不复制路径。全期实际交易另有7435个Token/cohort机会，不等于本次修复后可建标签子集。无成交机会留在master，不能因缺标签当失败。

预测时刻明确选用信号快照本地recorded_at，即三时钟均已可用的离线信息锚；它不是伪造的原策略decision_at。共享receipt的observed必须严格晚于此锚，receipt recorded不晚于共享fill。模型因此只检验现有observer已选择、可恢复共享receipt且具备后续行情的子总体前置L0信息，不能估计完整发现universe的选择价值，也不是全部已成交账户样本。cohort.decided_at只用于原始纳入，未作信号时间。

标签帧按recorded到达顺序，丢弃不能前进的老observed；observed<=ingested<=recorded，年龄<=120秒，原池匹配，流动性字段已知。最大连续观察缺口120秒，超过便删失。EVM池地址忽略大小写，Solana保留。

主标签：15分钟内首次净正触发，在trigger真实recorded之后首次严格新observed帧退出，扣当时卖侧成本后是否仍正。失败的首次退出不事后挑第二次高点；先成功后核销也不以未来核销抹掉先前成功。固定15m退出作为独立对照；30/60m仅敏感性。原池fresh低于当期floor是模拟吸收核销，不是链上rug或真实卖出证明。

买数量以实际v6 execution_price为锚，不能重复扣买滑点。卖滑点/fee取对应immutable activation；raw return另以entry_market_price计算。原始缓存只使用token_snapshots三时钟，没有用market_mark_history.observed冒充ingested。120秒是分析预注册容差，不是关于真实逐笔市场完整性的保证。

标签缺失可能非随机，持仓后采样更密。可观察门槛标签不能被称为真正amount-specific执行利润。研究窗口同一天，未知日期/市场状态不会被填作稳健。

覆盖分母：`{"15": {"COMPLETE": 4731, "CENSORED": 951, "NOT_MATURE": 359, "UNKNOWN_ENTRY": 23}, "30": {"COMPLETE": 3174, "CENSORED": 2352, "NOT_MATURE": 515, "UNKNOWN_ENTRY": 23}, "60": {"CENSORED": 3543, "COMPLETE": 1407, "NOT_MATURE": 1091, "UNKNOWN_ENTRY": 23}}`。

可重算输入hash：`ccf65bf7edc44a77f945de2b8097ba40218b047a161ab67f9ecc0a4ff9e3c2ce`。逐机会CSV、raw extract及成本epoch位于data/research/alpha_diagnosis_20260907/opportunities；没有写运行库。
