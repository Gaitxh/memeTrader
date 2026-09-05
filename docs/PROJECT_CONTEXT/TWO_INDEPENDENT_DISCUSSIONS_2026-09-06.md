# 两次独立讨论的逐项实现边界

来源：用户指定“设计新策略”聊天中的两个独立回合。主Agent已分别完整阅读；第一回合60289881、第二回合6c12cb02。下面两张表分别追踪，第二篇的建议顺序不取消第一篇方向。原文不作为私聊导出提交。编号是需求编号，不是策略ID；同一真实机制可被两个需求引用，但名称相近不能代替行为等价。

## 第一篇：独立清单

|项|方向|已有实现与尚缺部分|
|---|---|---|
|A01|Vault Hazard Exit|vault_hazard_v1、实际Vault和下一份amount-specific quote已接；同BUY专门候选/对照和全部合格持仓共享Shadow覆盖待补|
|A02|Earn-the-Hold|earn_the_hold_v1机制、实际金额流已接；专门同BUY对照待补|
|A03|Failed-Continuation Profit Lock|failed_continuation_profit_lock_v1已接；专门同BUY对照待补|
|A04|Wave Reset Re-entry|wave_reset_reentry_v1：真实旧仓关闭后10–240分钟、新流/深度/结构确认及下一帧；不是持旧仓等后来上涨|
|A05|Migration Flush→Absorption|migration_absorption_v1已接原始迁移、精确canonical池、冲高回落/吸收；完整早期持有人抛售与资本广度扩张证据仍有限|
|A06|Executable-Recovery Decay|executable_recovery_decay_v1实际数量和时点quote已接；全部合格持仓Shadow覆盖待补|
|A07|Capital-Velocity FirstMover|capital_velocity_v1已接毕业后真实资金速率；预毕业WATCH与曲线净储备速率是另一缺口，不能称同义|
|A08|Effective-Breadth Flow|effective_breadth_v1使用实际金额参与广度，不以地址数冒充独立人类|
|A09|Price-to-Flow Fragility|price_to_flow_fragility_v1已接实际流/价格退出；实收源覆盖不足保持UNKNOWN|
|A10|Churn/Wash Resistant|churn_resistant_v1使用真实金额中位数、dust比例、净流，不宣称确定识别洗盘|
|A11|Creator/Early Holder Distribution|creator_early_holder_distribution_v1已接真实creator；完整早期持有人/隐藏控制簇未覆盖，不能宣称完整|
|A12|Bundle-Adjusted Breadth|bundle_adjusted_breadth_v1只覆盖真实同交易原子组；未公开跨交易bundle/共同控制不可凭空推断|
|A13|Finite-Capital Ranker|finite_capital_ranker_v1有界已观察池排序、独立现金/槽位；不是全市场排序|
|A14|Market Regime Throttle|market_regime_throttle_v1为有界横截面深度/广度实验，不是已验证跨日宏观模型|
|A15|Competing-Risk Model|competing_risk_v1当前为封存清洁终局样本的利润/死亡/普通亏损频率；尚非完整时间到事件生存模型|
|A16|HighRecall→EarnHold→Harvest→DeadWaveExit→WaveReset|high_recall_exit_pipeline_v1可运行；与第二篇池类型分流不是同一机制|

## 第二篇：独立清单

|项|方向/能力|对应与差异|
|---|---|---|
|B01|Exact Surface Classifier|pool_surface.py已有exact PDA、LP、mint、vault分类；未知权限或LP锁定不伪造|
|B02|Direct LP Float-Constrained Scout|direct_lp_float_constrained_v1已运行5U，池内供给份额与Vault退出；金额特定入场可卖性/资本确认的完整组合仍待补|
|B03|PREGRAD Capital-Velocity WATCH|待接：免费create/migration真实事件与初始SOL已有；有限优先观察、连续曲线净储备采样属于可实现缺口，不借口全部需付费|
|B04|Migration Absorption|可复用A05部分机制；持有人flush、实际资本广度/可执行回收改善的完整确认仍有限|
|B05|Vault shared Shadow→ExitIntent与同BUY实验|A01独立账户不等价全部合格旧持仓只读观察层，待补|
|B06|Executable-Recovery shared Shadow|A06独立账户不是共享观察全覆盖，待补|
|B07|Earn-the-Hold候选/对照|A02退出机制复用；待专门同BUY控制|
|B08|Failed-Continuation候选/对照|A03退出机制复用；待专门同BUY控制|
|B09|Wave Reset|A04可等价复用，保留该独立来源关联|
|B10|Event Reawakening / Mature Event|event_reawakening_v1本阶段代码/集成通过：新官方精确CA事件→成熟池新价格/深度/实际流→下一帧，事件键消费；旧事件不能重复开仓|
|B11|Price-to-Flow Fragility|复用A09，覆盖限制保留|
|B12|Creator/Early Holder Distribution|复用A11部分，非完整持有人追踪|
|B13|Effective Breadth|复用A08，实际金额和有效参与者|
|B14|Churn Resistant|复用A10，不以交易笔数充当真实资本|
|B15|Bundle Adjusted Breadth|复用A12，仅可观察原子组|
|B16|Wallet economic structure|现有金额集中度/重复/creator组件；共同资金来源与隐蔽簇未覆盖，不冒充smart-money复制|
|B17|Authoritative Event Shock|现有OKX精确CA官方事件入口；通用事件后的金额流确认及无CA路径不是现有名称自动覆盖|
|B18|No-CA Event→冻结clone CA集合→资本排序|待接；冻结已有检索候选、实际流排名/并列WAIT可实现，候选集不允许事后补赢家|
|B19|Finite Capital Ranker|可复用A13有界版本，非全市场|
|B20|Market Regime|可复用A14有界版本，未验证状态分类收益|
|B21|Competing Risk|可复用A15频率实验部分；完整时间到事件模型未完成|
|B22|Surface-specific Lifecycle Pipeline|surface_lifecycle_pipeline_v1本阶段接线/集成通过：canonical走迁移吸收、direct走供给份额+真实流、成熟事件走事件复苏，随后共享EarnHold/Harvest退出；PREGRAD仍只应WATCH，等待B03接线|

## 本地自然结果提出的额外实验

截点2026-09-05 18:50:22Z；排除已有工程污染/资本补款/成交纠正所关联的整笔仓位。不能将不同策略重复持有同一币的结果当独立样本或系统收益。

- serial_conditional_runner_v1：原conditional runner在131个清洁终局中29胜、净-528.002U；检验单槽是否减少资本被同时占用和高度相关暴露。入场/退出不改，拒绝被占槽期间的机会，不排队补单。不是由这组结果证明单槽获利。
- sustained_breakout_earn_hold_v1：原突破24终局/8胜、净-142.743U；检验突破后必须持续满足真实资金支持才获得更长持有资格。只接已验证PumpSwap输入，未证明改善。

上述两条已在19:18:52Z、snapshot891956增量部署，当前166，原164完整保留。B10/B22尚待本阶段部署；不能据此宣布两篇全部实现。

## 工程修复与剩余交付

2026-09-06本阶段补充：A01/A02/A03与B05/B07/B08所需的专门同BUY候选/对照已经实现三组共6臂，使用`paired_*_candidate/control_v1`新ID。每组入场信号相同且共享同一个实际Paper entry fill、数量、时间，资金不足或任一方不满足入场时不纳入该对照；仅候选启用目标资金退出机制，其余退出规则与对照一致。与B10/B22一同形成8项待部署增量，测试通过。上表的共享全合格持仓Shadow仍是独立待办，不能用这六臂抵扣。

1. 已部署：原持仓池被Token批量接口漏报时，独立精确pair队列补采；CG仅补仍缺的池。批量漏报/HTTP失败/额度耗尽不能直接当池消失。7项最小回归通过。<1U新原池证据仍照既定规则核销。
2. 已部署：单币检索耗时曲线；10秒桶、120点、20秒Web刷新，批次耗时按币数加权，不除以币数造低延迟。
3. 已部署：观察名单年龄重新分桶，held不占非held3/4/3候选槽；释放到期对象，预算不增加。
4. 本阶段测试发现并修：同一观察同时出现5U与20U策略时，旧唯一cohort-snapshot约束冲突。不同金额使用同一源行情的明确allocation副本，分别记录真实规模；副本不能作为新市场观察或旧策略机会。无额外API请求。
5. 补款：只按可确认工程异常关联BUY补实际账本损失；原损益不改，补款不计收益，无未来最佳卖点/假想利润。后续仍须实际入账与对账。
6. 用户最新低优先级项放最后：错误监督已修项更新状态；耗时与发现图并排紧凑；核查再次活跃全0的统计/源覆盖原因。

阶段提交：da2d9f2（检索/watch）；1a7674d（精确池及两个本地新实验）；2bd972c（缺失证据修正）。未完成方向继续实施，不以统计报告代替策略，不恢复自动两小时复盘，全部工作完成后才语音。
