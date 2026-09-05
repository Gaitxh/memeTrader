# 两次独立讨论的逐项实现边界

来源：用户指定“设计新策略”聊天中的两个独立回合。主Agent已分别完整阅读；第一回合60289881、第二回合6c12cb02。下面两张表分别追踪，第二篇的建议顺序不取消第一篇方向。原文不作为私聊导出提交。编号是需求编号，不是策略ID；同一真实机制可被两个需求引用，但名称相近不能代替行为等价。

当前部署边界：`fc3c0f3` 已部署180臂，包含 `duration_competing_risk_v1` 与 `direct_lp_amount_specific_confirmed_v1`；共享Recovery Shadow已有真实quote-only帧，不是成交或旧策略退出变更。另4个独立实验已完成代码和真实Store测试，待增量部署至184：`official_event_actual_flow_v1`、`migration_amount_rate_absorption_v1`、`early_observed_buyer_distribution_v1`、`common_funding_adjusted_breadth_5u_v1`。以下“已接”不等于已有自然触发或已证明收益；184不是当前运行数，也不是全方向完成证明。

## 第一篇：独立清单

|项|方向|已有实现与尚缺部分|
|---|---|---|
|A01|Vault Hazard Exit|vault_hazard_v1、实际Vault和下一份amount-specific quote已接；同BUY候选/对照已部署；共享6槽held优先/120秒驻留公平轮转已接，保留池连续帧不重置；仅支持有exact解码输入的池，不是全币同秒覆盖|
|A02|Earn-the-Hold|earn_the_hold_v1机制、实际金额流及专门同BUY对照已部署；6池及有界签名预算可能截断，换池需重新seed，完整双窗缺失不冒充零流，也不全部归因于策略阈值|
|A03|Failed-Continuation Profit Lock|failed_continuation_profit_lock_v1及专门同BUY对照已部署|
|A04|Wave Reset Re-entry|wave_reset_reentry_v1：真实旧仓关闭后10–240分钟、新流/深度/结构确认及下一帧；不是持旧仓等后来上涨|
|A05|Migration Flush→Absorption|原migration_absorption_v1保留；新增migration_amount_rate_absorption_v1待部署：迁移后两完整窗真实SELL raw/秒衰减、净流、breadth及flush/reclaim确认，不再以卖出笔数替代该新臂的金额卖压。完整发行早期持有人flush与amount-specific回收改善仍未接入此序列|
|A06|Executable-Recovery Decay|executable_recovery_decay_v1实际数量quote已接；共享Shadow已部署并产生真实quote-only帧，按原池/真实数量合并、最后报价优先级及30秒轮转，不影响旧退出；免费报价预算下不保证每仓30秒内必有新quote|
|A07|Capital-Velocity FirstMover|capital_velocity_v1已部署毕业后实际买卖总金额/秒，另有净流字段；PREGRAD WATCH也已部署并有真实曲线净储备速率。gross成交速率、net资本积累和预毕业观察是不同语义，不以后一篇覆盖前一篇|
|A08|Effective-Breadth Flow|effective_breadth_v1使用实际金额参与广度，不以地址数冒充独立人类|
|A09|Price-to-Flow Fragility|price_to_flow_fragility_v1已接实际流/价格退出；实收源覆盖不足保持UNKNOWN|
|A10|Churn/Wash Resistant|churn_resistant_v1使用真实金额中位数、dust比例、净流，不宣称确定识别洗盘|
|A11|Creator/Early Holder Distribution|原creator_early_holder_distribution_v1及真实creator输入保留；early_observed_buyer_distribution_v1待部署：封存部署后首次完整BUY观察群、匹配后来真实SELL，两连续派发窗触发后下一原池帧卖出。当前Store封存不传出生fact，coverage明确first_observed_buyers_only，不冒充铸币初始持有人；完整早期分配与隐藏控制仍未覆盖|
|A12|Bundle-Adjusted Breadth|bundle_adjusted_breadth_v1已部署，仅真实同交易原子组；common_funding_adjusted_breadth_5u_v1待部署，补已抓交易中显式资金转账关系的广度调整。共同来源不代表共同控制；未公开跨交易bundle及完整funding历史仍未知|
|A13|Finite-Capital Ranker|finite_capital_ranker_v1有界已观察池排序、独立现金/槽位；不是全市场排序|
|A14|Market Regime Throttle|market_regime_throttle_v1为有界横截面深度/广度实验，不是已验证跨日宏观模型|
|A15|Competing-Risk Model|旧competing_risk_v1终局频率保留；duration_competing_risk_v1已随fc3c0f3部署：右删失CIF及失联独立保守情景、5U；不是无偏市场死亡概率，缺同类清洁样本不能编概率|
|A16|HighRecall→EarnHold→Harvest→DeadWaveExit→WaveReset|high_recall_exit_pipeline_v1可运行；与第二篇池类型分流不是同一机制|

## 第二篇：独立清单

|项|方向/能力|对应与差异|
|---|---|---|
|B01|Exact Surface Classifier|pool_surface.py已有exact PDA、LP、mint、vault分类；未知权限或LP锁定不伪造|
|B02|Direct LP Float-Constrained Scout|原direct_lp_float_constrained_v1保留；direct_lp_amount_specific_confirmed_v1已随fc3c0f3部署，正实际流、5U两腿原池quote-only、下一帧Paper；预检不是成交，未知全流通供给、LP锁定及撤池能力不伪造|
|B03|PREGRAD Capital-Velocity WATCH|8e3cc74已部署：免费create、最多3个精确PDA曲线净储备观察、30秒/300秒TTL优先名单、真实迁移唤醒一次；仅WATCH非买入；已有自然观察记录|
|B04|Migration Absorption|独立对应A05：待部署新臂补真实SELL金额速率/净流/breadth/flush-reclaim；不等价原文“早期holder flush→回收改善”的完整序列。后者仍是待接代码/输入，不仅是等待自然机会|
|B05|Vault shared Shadow→ExitIntent与同BUY实验|同BUY实验已部署；共享观察已接6槽held优先/120秒驻留轮转，旧退出不改；轮换保留已驻留池连续性，换出池不伪造连续双窗；未支持exact解码的池不是仅靠增加配额就能覆盖|
|B06|Executable-Recovery shared Shadow|已部署并有真实quote-only帧：按原池/真实数量去重接合格held，复用现有报价预算、不fill；exact decimals/实际余量缺失保持未知，非支持链/输入不是旧仓全覆盖|
|B07|Earn-the-Hold候选/对照|复用A02机制，专门paired候选/对照已19:38:02Z部署，共用实际BUY|
|B08|Failed-Continuation候选/对照|复用A03机制，专门paired候选/对照已19:38:02Z部署，共用实际BUY|
|B09|Wave Reset|A04可等价复用，保留该独立来源关联|
|B10|Event Reawakening / Mature Event|event_reawakening_v1已在174阶段部署：新官方精确CA事件→成熟池新价格/深度/实际流→下一帧，事件键消费；旧事件不能重复开仓；现有源面不等价所有外部事件|
|B11|Price-to-Flow Fragility|复用A09，覆盖限制保留|
|B12|Creator/Early Holder Distribution|分别复用A11原creator臂和待部署首次观察买家派发臂；首观BUY群不是完整早期持有人，也不是LP holder集合；缺失历史不能用当前余额回填|
|B13|Effective Breadth|复用A08，实际金额和有效参与者|
|B14|Churn Resistant|复用A10，不以交易笔数充当真实资本|
|B15|Bundle Adjusted Breadth|复用A12已部署原子组及待部署显式资金关系补充；可观察联系不等价Jito bundle、完整经济独立人数或共同控制|
|B16|Wallet economic structure|现有金额集中度/重复/creator组件已接；common_funding_adjusted_breadth_5u_v1待部署，复用已抓交易中的显式资金转账关系，不增加RPC。交易之外的钱包资金历史和隐蔽簇仍未覆盖，不冒充smart-money复制|
|B17|Authoritative Event Shock|原OKX精确CA官方事件入口保留；official_event_actual_flow_v1待部署，新增官方事件后的真实金额流确认，不能用原只验事件身份的臂抵扣。无CA路径由已部署B18独立处理；其他官方平台/事件类型未接，不能未经访问验证就称资源受限|
|B18|No-CA Event→冻结clone CA集合→资本排序|no_ca_event_flow_leader_v1已20:13:26Z部署；首次搜索冻结集合、全成员同轮金额流排名、唯一正净流第一；选择冻结后下一帧信号/再下一帧5U；缺源或并列WAIT，无官方CA伪装|
|B19|Finite Capital Ranker|可复用A13有界版本，非全市场|
|B20|Market Regime|可复用A14有界版本，未验证状态分类收益|
|B21|Competing Risk|与A15时长CIF/失联敏感性机制等价复用，保留独立来源映射；自然效益未验证|
|B22|Surface-specific Lifecycle Pipeline|surface_lifecycle_pipeline_v1已在174阶段部署：canonical走原迁移吸收、direct走供给份额+真实流、成熟事件走事件复苏，随后EarnHold/Harvest；B03 PREGRAD已接但仍只WATCH。新独立金额吸收/Direct预检臂不自动改写原pipeline合同|

## 本地自然结果提出的额外实验

截点2026-09-05 18:50:22Z；排除已有工程污染/资本补款/成交纠正所关联的整笔仓位。不能将不同策略重复持有同一币的结果当独立样本或系统收益。

- serial_conditional_runner_v1：原conditional runner在131个清洁终局中29胜、净-528.002U；检验单槽是否减少资本被同时占用和高度相关暴露。入场/退出不改，拒绝被占槽期间的机会，不排队补单。不是由这组结果证明单槽获利。
- sustained_breakout_earn_hold_v1：原突破24终局/8胜、净-142.743U；检验突破后必须持续满足真实资金支持才获得更长持有资格。只接已验证PumpSwap输入，未证明改善。

上述两条已在19:18:52Z、snapshot891956增量部署166；随后B10/B22及6个paired臂于19:38:02Z/frontier897294增量到174。20:13:26Z/frontier906746新4臂加入后178，旧账户/资金期保留。新增机会：prebreakout_net_accumulation_v1（真实净流先于价格）、liquidity_leads_price_v1（报告深度先行）、fast_stop_reclaim_v1（真实清洁止损后收复），另B18无CA事件。规则/测试/限制见PREGRAD_EVENT_OPPORTUNITY_2026-09-06.md，未验证盈利。

## 工程修复与剩余交付

2026-09-06本阶段补充：A01/A02/A03与B05/B07/B08所需的专门同BUY候选/对照已经实现三组共6臂，使用`paired_*_candidate/control_v1`新ID。每组入场信号相同且共享同一个实际Paper entry fill、数量、时间，资金不足或任一方不满足入场时不纳入该对照；仅候选启用目标资金退出机制，其余退出规则与对照一致。这6臂与B10/B22共8项已在174阶段部署，不再是待部署增量。共享观察另行已接，其免费预算及exact支持面限制不能用这六臂抵扣，也不能宣称全币全时刻覆盖。

### 实际剩余能力与最小动作

- **完整早期持有人：代码/输入仍缺。** 现有首次观察BUY集合已可做独立实验，但不能恢复缺失的发行初始分配。可先将已有可验证出生事实接入集合coverage判定；未来新发行若能取得真实初始分配或早期base-token账户快照，再按当时封存、明确样本覆盖率。LP mint持有人不能代替币的持有人，当前快照不能回填过去。
- **迁移完整序列：仍缺回收改善确认。** 新金额吸收臂补SELL速率与资本广度，不等于早期holder归因或入场规模amount-specific回收改善。可复用已有quote-only通道对有界候选前向取得同规模回收证据；报价成本和优先级需显式预算，现有持仓Recovery帧不能直接挪作未建仓候选的可卖性证明。
- **交易外资金关系：代码仍缺，公开访问额度需实测。** 新common-funding只消费已抓交易的显式关系；可对少量优先钱包取有界历史资金转移，按记录时间与slot使用。没有记录不等于独立，公共转账也不证明共同控制；未公开bundle/受益所有人并非可保证恢复的字段。
- **官方事件支持面：适配仍缺。** 当前确定性入口为OKX及其无CA分支；其他交易所、launchpad、链官方公告和非ticker事件需独立解析、身份与时序接线。先接一个明确可访问官方源，并保留空轮、HTTP失败、无CA与歧义诊断；不能仅凭无新事件判断额度不足。
- **共同采样边界：真实资源与代码支持面分开。** 有界6池、签名截断、换池seed及现有quote配额会限制完整窗口和刷新时间；未知协议解码、mint数量来源或缺失持有人逻辑则是代码缺口。资源不足、来源不可访问、自然阈值未达到必须分别报告。跨日模型收益、配对退出增益仍需自然forward积累，工程通过不代表经济有效。

1. 已部署：原持仓池被Token批量接口漏报时，独立精确pair队列补采；CG仅补仍缺的池。批量漏报/HTTP失败/额度耗尽不能直接当池消失。7项最小回归通过。<1U新原池证据仍照既定规则核销。
2. 已部署：单币检索耗时曲线；10秒桶、120点、20秒Web刷新，批次耗时按币数加权，不除以币数造低延迟。
3. 已部署：观察名单年龄重新分桶，held不占非held3/4/3候选槽；释放到期对象，预算不增加。
4. 本阶段测试发现并修：同一观察同时出现5U与20U策略时，旧唯一cohort-snapshot约束冲突。不同金额使用同一源行情的明确allocation副本，分别记录真实规模；副本不能作为新市场观察或旧策略机会。无额外API请求。
5. 补款：20:16:31Z按BUY412305/cohort12377补20U实际闭仓损失，原因原池漏报被错误当missing；新总7538.807662700746U。原trade hash及-20U不变，不计利润，不假设当时能够卖回本金。其余未证实反事实仍不补造。
6. 用户最新低优先级项放最后：错误监督已修项更新状态；耗时与发现图并排紧凑；核查再次活跃全0的统计/源覆盖原因。

阶段提交：da2d9f2（检索/watch）；1a7674d（精确池及两个本地新实验）；2bd972c（缺失证据修正）。未完成方向继续实施，不以统计报告代替策略，不恢复自动两小时复盘，全部工作完成后才语音。
