# 有界严格前向经济复核

冻结截止：2026-09-07T10:49:01.093654Z，trade frontier 479970。当前资金期 `chain-meme-trader/funding-20260906-v002-final-1000`。

## 范围与方法

以2026-09-07T09:19:47Z实际修复部署为分界。SQL用主键范围 `id>479129 AND id<=479970 ORDER BY id LIMIT 5000` 获取候选，再严格筛选 `created_at>=boundary`；479130–479139在部署前，已排除。新入场再要求positions.opened_at>=boundary。只读mode=ro，不构造Store、不测试、不回测、不初始化。原注册127+追加97=224账户均列在配套JSON accounts中。

账户快照每arm按版本和arm取最后一行；它是全资金期累计状态，不是修复后新收益。仓位仅按新交易出现的version/arm/cohort主键点查，source_snapshot按ID点查；无全历史重扫、无长事务。425个新仓的源快照observed_at与ingested_at均不晚于opened_at；此检查不等于穷尽证明所有派生特征正确。池龄来自当时source snapshot raw pairCreatedAt与该观察时间，不取现在元数据。

## 全账户与新样本

831笔部署后交易：425 BUY、359 SELL、47 WRITEOFF。425新仓涉及33独立Token，51/224账户有新BUY；369终结、56开放。另9个部署前入场、部署后交易的旧仓全部终结，累计PNL47.8042U单列，不能混入新机制窗口。

全账户最新快照有6账户现金<5U、77账户<20U；这不是全部零交易账户的因果解释，也不能在未核验单策略stake/配对资金之前称其资金不足。173账户本窗零BUY不等于173无效策略。

369终结仓描述性PNL相加+145.5639U，median -0.3854U，149赢/220亏，PF1.2761。它跨stake和重复账户，不是一条可投资组合收益。最佳SOL Token贡献+415.5879U，占正Token收益78.21%；移除最佳后-270.0240U，移除最佳3后-345.1044U。开放56仓不填0、不纳入终结胜负。

## 同Token/cohort配对

配对按完全相同cohort+Token，只有双方终结才计算delta；候选没有入场的机会另报。所有对比中位差均0。

|候选→对照|共同机会|共同终结|改善/恶化/相同|终结差U|
|---|---:|---:|---|---:|
|round2_chase_candidate_v1 → round2_chase_control_v1|13|11|0/0/11|0.000000|
|round2_slow_grace_candidate_v1 → round2_slow_grace_control_v1|15|13|0/0/13|0.000000|
|round2_giveback_duration_candidate_v1 → round2_giveback_duration_control_v1|15|13|1/1/11|0.833026|
|round2_response_exhaustion_candidate_v1 → round2_response_exhaustion_control_v1|15|13|0/0/13|0.000000|
|round2_runner_requalification_candidate_v1 → round2_runner_requalification_control_v1|15|13|0/1/12|-0.129282|
|finalist_profit_budget_v1 → finalist_baseline_v1|15|13|1/1/11|-0.833026|
|finalist_progress_clock_v1 → finalist_baseline_v1|15|13|3/2/8|4.398552|
|finalist_depth_divergence_v1 → finalist_baseline_v1|15|13|0/0/13|0.000000|
|finalist_activity_failure_v1 → finalist_baseline_v1|15|13|0/0/13|0.000000|

finalists+round2共225账户位置，仅17 Token；194终结、31开放。PNL+48.7421U，去最佳Token后-265.7358U；最佳Token占正Token收益90.16%。三个新entry为boundary_retest 1已终结(+.5395U)、seller_absorption 1开放、price_then_depth 0，仍是稀疏覆盖。

## 具体盈利、失败与早退反例

1. 共同右尾：SOL `HpGF5s8iZKYVNqjFd9H1fp4TnhQxR3hLPvM9Nc8BfUpr`，cohort56861，原池`Hs3Fr94Decr1eRjWrBdoYciyd8t7Gw3aVsTDYt1pfbL7`。baseline在09:31:43Z入场5U，10:01:45Z max_hold净回款29.0510U、PNL24.0510U。所有复制账户不增加独立Token数。runner同机遇PNL12.9329U，说明分批兑现也可能削弱右尾。

2. 追价过滤反例：同56861 signal snapshot1512599价格.0001463，receipt1512691价格.0001746，漂移19.3438%；cohort feature_json明确candidate因4%预算拒绝，control最终+24.0510U。另BSC `0x004cf648f3ab44bdec61565478c4565a2dec58cd` cohort57425，signal1515687→receipt1515781漂移6.8094%，同样拒绝，control后来−5U核销。候选确实避开一个失败，也错过一个大赢家；这2个拒绝机会的control净结果+19.0510U，不能只用共同11对delta0声称两臂等效，也不能当无资金约束的组合反事实。

3. progress clock减少随后损失：RH cohort57943（0x49bb…）candidate+.2690U、baseline−1.1633U；RH cohort58670（0xd453…）candidate+.0136U、baseline−2.9288U；候选分别提前约6和9分钟退出。该窗口支持时间预算有独立行为，不证明它预测抽池。

4. progress clock错失慢收益：SOL `3Y5M5uCXje5L8mZodkt7n3uokGLy5t3rHo7rK1AyRU6H` cohort57646，10:05:51Z clock退出+.7229U，baseline10:28:02Z退出+1.6796U；budget10:15:24Z退出+.6970U。giveback duration候选保留到baseline结果，在此改善+.9825U；但PH5… cohort57581反向损失.1495U。统一延长或统一提前均有反例。

5. 分批减损而非成功逃顶：BSC cohort57425 baseline核销−5U，runner此前partial回收3.3408U后余仓核销，累计−1.6592U；SOL `2rwhRdRqDNDvQhihCnn3oD41fLBkzysrrFEg6Z79fY8X` cohort58553，baseline−5U，runner此前回收3.2550U后余仓核销，累计−1.7450U。requalification候选/对照这两例相同，减损来自共同partial，不能归因新增余仓资格。

47个新仓终结核销原因全部为配置原池floor，未看到旧missing原因。写核销只表示本地合同下余仓归零，不能称链上确认rug或真实零可卖；未复审每次底层流动性证据。

## 链、池龄、入场时段分层

以下仅描述分层，不选择事后最好链/小时作交易门。样本跨账户重复，时间块不足且后块右删失，不能推断时间alpha。

|分层|仓/Token|终结/开放|终结PNL U|去最佳Token U|
|---|---|---|---:|---:|
|chain:bsc|38/3|37/1|-83.9848|-83.3564|
|chain:robinhood|177/18|157/20|-207.0085|-219.8364|
|chain:solana|210/12|175/35|436.5573|20.9694|
|age_bucket:1-6h|21/9|18/3|-21.2016|-22.4935|
|age_bucket:15-60m|64/12|63/1|-57.2585|-70.0864|
|age_bucket:5-15m|110/9|109/1|-52.9815|-63.5613|
|age_bucket:<5m|227/12|176/51|289.8447|-119.5320|
|age_bucket:>=6h|3/2|3/0|-12.8391|-6.5338|
|entry_utc_hour:2026-09-07T09|164/18|164/0|365.4051|-50.1828|
|entry_utc_hour:2026-09-07T10|261/19|205/56|-219.8411|-229.2714|

所有新仓属于post_0919执行期，旧9仓另分post_0514_pre_0919或更早；不把前两次修复的行为混为同一执行版本。池龄<5m看似盈利主要由同一SOL大赢家驱动，去掉后−119.5320U。09时段去最佳后−50.1828U。

## 最值得决策实验的线索

- 第一优先：保持共同入场，比较“有限持有许可”的增量状态，而非简单延长max_hold。已有clock有3改善2恶化，slow_grace本窗与clock完全一致；新方案必须引入确实不同且可观察的信息，否则只是在复制账户。
- 保留高召回对照，检验接收延迟与上跳速度的交互，记录拒绝机会结果。4%追价门同时排掉赢家与失败，本窗净代价较大，不能推广成通用门；不能用本窗赢家拟合阈值。
- partial的风险收益权衡值得独立保留：已出现两次真实减损和同一赢家收益折半。不要把共同partial效果计作requalification新机制收益；若新增，应比较实际回款、余仓新高/停滞状态，保持总stake与公共退出相同。
- 暂不增加只靠同一L0价格/流动性重新组合的账户：depth_divergence、activity_failure、response_exhaustion在13终结共同机会中无经济差异。应优先验证专属事件频率和独立输入是否存在。

## 旧工件与未覆盖

复用SYNTHESIS.md的25期/1897版本×策略/223306仓/444765交易、v22单Token占94.14%等旧冻结结论，以及ROUND2/RESEARCH_SYNTHESIS.md截至2026-09-06T18:41:40Z的20个共同Token、clock避损/慢赢家反例；这些均不是本轮重新计算或当前实时总数。

本轮未取退出后固定+5/+15m价格，不冒称完整市场路径或最大后悔值。早退/后亏仅用同cohort仍在持有的对照实际后续终结证明；未看见的第二波保持未知。没有把当前池数据、后续ATH、结果标签回填决策特征。没有外部Chat、自动任务、生产修改或策略部署。全224账户的定义字段、累计快照、新窗经济、全部434相关仓及配对生命周期见RESOURCE_BOUND_ECONOMICS.json。

## 拟新增方向的现有自然覆盖

仅复用上述冻结窗口，零覆盖不是机制无效证据；不同机会分母不能直接相减。

|现有方向|新仓/终结/Token|终结PNL U|
|---|---|---:|
|broad_mature_continuity_control_v1|0/0/0|0.000000|
|experiment_pullback_reclaim_candidate_v1|6/6/6|-0.827619|
|experiment_pullback_reclaim_control_v1|0/0/0|0.000000|
|experiment_panic_reclaim_candidate_v1|7/7/7|-16.618115|
|experiment_panic_reclaim_control_v1|9/9/9|-12.488521|
|prebreakout_net_accumulation_v1|1/1/1|-1.221787|
|mature_new_acceptance_5u_v1|0/0/0|0.000000|
|finalist_boundary_retest_v1|1/1/1|0.539518|

成熟/压缩新候选应说明尚无当前自然覆盖支撑；panic与pullback已有少量路径可供设计，但远不足以筛选阈值或证明新策略收益。
