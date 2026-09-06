# ROUND2：五个机制、十个新账户的冻结实验卡

状态：根代理本批实现合同；**本页不是已实现、已部署或盈利认证**。部署时间、frontier、hash、测试与自然观察由实际发布记录确认。本批五个具体机制各有新候选与新对照，共10臂；不是以后策略数量上限。旧214个定义、资金、历史及上轮8臂全部保持不变。

依据：[PATH_AND_REGIME.md](PATH_AND_REGIME.md)、[MECHANISM_DIFFERENCES.md](MECHANISM_DIFFERENCES.md) 与根代理本轮明确参数裁决。没有重算历史、查生产DB或网络；没有 MAE/MFE、峰值择时或假想历史成交。设计时已看过的20个共享机会属于研究/设计材料，不能再次当独立验证集。

## 共同合同

- **资金与执行**：每新账户独立1000U、每笔5U、最多4仓。Solana/BSC/Robinhood 只用已有支持的同 Token、同原池L0；后帧 BUY/SELL，普通Paper仍是模拟。当前成本默认买+4%、卖-4%、额外每fill 0U、原池最低1000 USD；手工设置变化归入新的 execution activation，不改写历史。
- **成本解释**：同价往返损失约7.6923%，报价需上涨约8.3333%才能覆盖当前双侧摩擦；4%追价预算只是买侧成本尺度的预注册假设，不是往返盈亏平衡线，也不是最优点。部分成交与最终余仓退出各按真实当期配置处理费用，不能把多次fill视为一次。
- **因果输入**：决策只用已 observed、ingested、recorded 的帧；BUY receipt 的 observed 严格晚于冻结 signal decision，SELL receipt 严格晚于 trigger。独立帧指 observation 时间推进，不是重读缓存；同池不能由兄弟池代替。序列帧按现有15秒新鲜门、5～60秒独立间隔接受；gap/source 变化不拼成连续证据。
- **公共风险层**：候选/对应对照的硬止损、通用追踪和最长持有一致。普通基线沿用 -20%经济硬止损、经济高水位+30%激活/15%回撤追踪、30分钟max_hold；runner组另有下述共同首次partial。已知新鲜原池低于有效floor按现行合同核销余量；缺失、失败、陈旧不是核销证据。候选新增状态不得取消共同风险/时限。
- **不伪造不同输入**：m5 volume/buys/sells是报告滚动聚合，不是净资金流、独立钱包或LP存取。USD liquidity 不是可卖深度保证。所有缺输入保留 WAIT/原因和分母，不为产生交易放宽因果或身份。
- **机会与对照边界**：对照均是新ID、新账户，不修改或拿旧8账户混作同部署对照。本批所有Broad entry（含chase）继承各臂对同一Token/原池一次入场机会的合同，不是卖出后再入场的Wave Reset。chase按共同机会资格后允许单边veto；pair-consumed只是消费该一次性机会，没有额外阻断本批合同允许的合法再入场。成对现金/容量筛选后的可比较对象，是**双方共同有资格承接的Broad一次性机会中的机制差异**；容量仍可能选择哪些其他Token机会可进入，必须保留共同资格拒绝分母，不能外推无耦合限制的独立资金周转收益。
- **频率与结论**：五组的 expected frequency 全部 **UNKNOWN**。没有预定收益、胜率或“达到若干笔必有效”的承诺。工程触发可达、自然覆盖、经济改善、alpha 是四种不同结论。

| 机制 | 新候选ID | 新对照ID | 对照内容 |
|---|---|---|---|
| 追价预算 | `round2_chase_candidate_v1` | `round2_chase_control_v1` | 同Broad signal、同首个合格后帧；不设追价veto |
| 慢稳定一次延期 | `round2_slow_grace_candidate_v1` | `round2_slow_grace_control_v1` | 新复制 progress_clock 原合同 |
| 利润回吐驻留 | `round2_giveback_duration_candidate_v1` | `round2_giveback_duration_control_v1` | 新复制 profit_budget 原合同 |
| 活动响应耗尽 | `round2_response_exhaustion_candidate_v1` | `round2_response_exhaustion_control_v1` | 同入场、无该专属退出的公共基线 |
| partial后余仓资格 | `round2_runner_requalification_candidate_v1` | `round2_runner_requalification_control_v1` | 同真实partial规则、无余仓期限再审 |

## 1. chase：冻结信号到首次后帧的追价预算

**假设与适用状态。** 年轻池 Broad 信号到可执行后帧间的上跳，可能消耗过多成本后空间；单次追价veto能否少买短命尖峰，同时不过度错失真正右尾。三链都适用，须按 chain、池龄、liq、m5活动、receipt延迟和execution epoch分层；钟点只作描述，不是择时信号。

**实际输入与as-of。** 冻结 Broad signal 的 decision time、signal snapshot ID及该帧原池价格；首个合格后帧 receipt 的ID/observed/ingested/received、同池价/liq；两账户的现金/容量。必须用真正的 `fill_signal_snapshot_id` 对应 signal，不能用可能已经是成交报价的 `entry_signal_price` 冒充信号价。不得扫描未来帧找最低追价。

**唯一候选差异。** 在两臂共同现金/容量及普通后帧资格通过后，计算 `drift=P_receipt/P_signal-1`。candidate 若 `drift>0.04` 拒绝本次BUY；`drift<=0.04`沿普通合同，control不设这道veto。4%为本批固定预注册预算，来源是当前买侧成本尺度而非赢家拟合。

**状态和风控。** candidate veto不能取消control；该signal及对应Token/原池的一次性Broad机会被消费，后续回落不得重放、排队或迟买，也不在任一臂卖出后自动生成Wave Reset机会。因此pair-consumed不是另加的“禁止合法再入场”处理。负drift不是自动安全证明，仍需全部普通资格。两臂退出、stake、风控相同，不附带改TP/止损。普通signal过期、源失败、共同现金/容量不足与追价veto分开记录；候选效果限定于成对资格筛选后的机会，而非无容量限制的全市场效果。

**与旧策略差异。** 信号后帧是全系统正确执行边界，不算新alpha；新机制只是首个真正后帧的独立成本尺度追价veto，不改Broad信号，也不把工程修复效果归到候选。

**来源与反证。** `PATH_AND_REGIME` 显示旧主入口有同帧可能性，不能拿旧高收益直接预测真正后帧结果；旧大赢家及新20机会的孤立赢家说明拒绝快涨可能恰好删掉右尾。保留Chat分歧：追价控制可能提升中位数却恶化总收益，不能预先裁决。

**失败条件 / 需要样本。** 完整分母必须从冻结signal开始，列共同资格通过、普通拒绝、candidate veto、两臂实际BUY/terminal/open，不只统计被candidate接受的仓位。记录被veto时control的自然完整结果，包含上行右尾和全损；候选缺仓不是“0成本盈利交易”。需要多个独立Token和不同日期/市场状态，按共同机会与Token聚类评估成本后差异、尾部与删最佳1/3 Token；仅短窗减少亏损不能证明有效。预计频率 **UNKNOWN**。

## 2. slow_grace：无进展deadline的一次慢稳定持有许可

**假设与适用状态。** 缓慢、持续但未达到“大进展”的价格过程，可能被180秒无进展时钟提前剔除；允许一次受限延期能否保留慢赢家，而不过度增加晚崩损失。目标是低到中等响应速度、原池仍留存的状态，不是所有亏仓统一延长持有。

**输入。** held同原池/provider的新鲜L0、经济值 `V=累计已实现净回款+余仓净回收值`、stake `S`、每个已接受帧的观测时刻与liq；clock锚的V/time/liq。当前冻结版不另加m5活动门：早期提案的“活动不恶化”不能悄悄成为额外未裁决阈值。

**共同clock。** 相对clock锚经济值有 `V>=V_anchor+0.01*S` 的大进展时，两臂均按原规则更新clock时间和V锚，并**同步更新liq锚**。180秒没有达到该进展时，control触发原progress_clock退出；gap/source按原规则重建连续观察。

**候选状态差异。** 在无进展180秒deadline到达时，若最近连续3个独立同源帧V严格递增、**当前 `economic_value>=progress_value`（V不低于当前clock进展锚）**、当前liq≥当前clock锚liq×.85，并且 `grace_used=False`，只给一次+120秒延期，随后置 `grace_used=True`。否则按clock退出。进展锚限制保留当前代码行为：尚未回到上次进展水平的恢复型亏仓，即使最近三帧上涨，也不获额外宽限；它不要求经济值已经覆盖全部本金。1%大进展仍执行原reset；**grace_used为position lifetime一次，不因进展、换源或gap重置**，不能反复领取延期。共同硬止损/追踪/max_hold照常优先。

**新旧区别。** 旧progress_clock只有大进展reset，没有一次性许可；earn_the_hold是初次60～120秒actual-flow/depth资格、不是未完全回本的L0慢漂移；190/191是10分钟复核，不是这段状态。只把180改300不是本机制，必要差异是状态有条件授予且一生一次。

**来源与反证。** 上轮16对成熟案例中，clock两次避免baseline全损，也把三个慢小赢家提前变为小亏。三个普通小赢家早期固定时点均尚未覆盖往返成本；最终亏损的部分幸存者却早期涨价/liq增加。因此“微升且liq保留”仅是假设，不是安全证据。

**失败条件 / 需要样本。** 若延期主要增加writeoff/尾损，或只偶然留下单Token右尾，假设不成立。分别报告达到180秒的机会、满足三帧/liq门、实际授予一次、延期内大进展、延期失败、共同风险先退出、缺证据重置、仍open；不能只看授予后的赢家。成对样本需共同入场且同成本，按Token/日期/chain/activity分层，保留全部未成熟机会。预计频率 **UNKNOWN**，没有已验证改善。

## 3. giveback_duration：利润回吐线下的真实持续观察

**假设与适用状态。** 净盈利后的短暂回吐与持续回吐可能不同；固定观察驻留是否比“两坏帧”更能保留短暂回撤后的延续。适用于已盈利状态，不为尚未盈利仓位增加等待。

**共同输入和激活。** 同原池/provider的已接受帧、净经济值V、stake S，以及**当前连续同源观察段内**截至当时的running profit `H=max(V-S)`；H不是position lifetime峰。保持旧profit_budget：H达到S×20%才有利润回吐激活，回吐幅度50%。gap>60秒或provider变化时，candidate与control均将本专属H重置为新段首帧的 `V-S`，并重置相应连续证据，与 `research_finalists.py:174–180` 的control一致；不得跨断流保留旧专属峰/计时。**公共trailing使用的生命周期高水位不因此改变。**

**control。** 新复制旧profit_budget：`profit<=当前已知H×.5` 连续两坏帧触发；恢复取消坏帧streak。这已经是幅度加两帧确认，不能称它是纯瞬时止盈。

**candidate。** 当前观察段H满足激活门后，第一次满足 `profit<=当时H×.5` 时，冻结本次边界 `B=当时H×.5` 和首次越界观测时间。后续有效连续观察中持续处于 `profit<=B`，达到120秒才触发SELL；`profit>B`取消本次计时，之后的新事件重新冻结当时边界。**等于B启动/延续，严格大于B取消**。本次驻留期间不借后来的峰移动原冻结线；gap>60秒或provider变化取消旧冻结边界/连续计时，并按共同合同重置本专属H。缺观测不算在线下驻留，新观察段不得借旧段盈利峰取得激活。

**风险与可达性。** 硬止损、通用追踪、30分钟上限优先；高峰后回吐可能已先触发公共trailing，因此不是每次profit-budget事件都能观察满120秒。须记录被公共风险截断的状态，而不能说duration未触发便不可达，也不能取消trailing来强造样本。trigger仍不是fill，SELL须后续新鲜原池帧。

**与旧差异/成本。** 相同20%激活和50%幅度，仅比较observed-time驻留状态与bad-frame计数；不是改一个利润门槛或把两帧换三帧。净值使用同实际执行成本，不依赖192旧L0profit-lock不可达的回本flag，不要求已经卖回本金。

**来源、失败与样本。** 上轮共同大赢家是max_hold，不是预算退出；不能用它为120秒背书。Chat分歧保留：计时与两帧没有显著性证据，等待可能放大尾部下行；新时间预算未证明最优。需要完整盈利激活分母、每次首次越线/恢复/持续达时/缺流重置/公共退出、candidate与control两边终结及open，并覆盖不同自然采样间隔、Token与日期。只看已熬满120秒的幸存者会有选择偏差。预计频率 **UNKNOWN**。

## 4. response_exhaustion：尚未跌价时的活动响应耗尽

**假设与regime。** 更多报告活动却不能带来相称价格改善、同时买笔结构向卖方移动，可能比等待实际跌价更早表露持续性减弱。适用原池观察连续、活动可见的阶段；不要求真实钱包/净金额流，也不覆盖缺字段/长间隔数据。

**输入与精确规则。** 连续3个同源同池新鲜帧 `F0,F1,F2`，每段独立间隔5～60秒。取正价格Pi、m5量Mi、`bi=buys_i/(buys_i+sells_i)`、真实观测间隔dt：

`r1=log(P1/P0)/dt01`，`r2=log(P2/P1)/dt12`。

candidate在 **`P1/P0-1>=.01`**、`r1>0` 且 `0<=r2<=.1*r1`、`M0<M1<M2`、`b0>b1>b2` 且 `b2<.5` 时触发；control无此专属退出。首段简单报价涨幅至少1%是单个固定幅度门，用于避免极小价格量化变化形成伪响应衰减；不是成本回本线，不是优化所得参数，斜率仍按上述log-return/实际间隔计算。明确允许末段零或小正斜率，**不要求已经跌价**；也不额外要求b0>.5，不能把“share逐降”偷改为“必须跨越.5”的另一个门。缺值、零总笔数、非独立/过长间隔不合格。之后SELL仍后帧执行。

**与旧差异。** 上轮activity_failure要求价格和经济值连续下降、buyshare反而上升、volume增加；本批是未跌价前正响应耗尽且share下降。旧8个balanced-harvest V002只在持有15分钟后看一次buy_ratio<.45，不需三帧响应序列。本批把原“活动响应”和“卖笔扩张价稳”合并为一个明确定义的机制，不再额外克隆第二个近义账户。

**成本和保护。** 经济PnL按共同成本；信号的log价格斜率是研究代理，不是扣费收益、价格冲击或真实资金效率。硬止损/追踪/max_hold同对照；本机制不能导致control也提前退出。

**来源与反证。** 完整路径显示部分早期价格/liq上升、buyshare高的Token最终仍亏，反驳简单单帧持续性；但这些材料没有证明“响应耗尽”这个新三帧条件有效。首段1%门只限制极小幅度，不消除重叠5分钟窗口、API更新粒度、交易笔数机械变化、残余量化误差及良性整理造成的误报。不得把rolling量差叫新增资金流，或把卖笔占比叫独立卖家分配。

**失败条件 / 需要样本。** 若未跌价的正常整理被频繁退出、成本吞掉改善或共同风险先退出占绝大多数，新机制可能无经济价值。需要全部三帧可得/不可得与满足各子条件的分母，跨独立Token/多个日期，按链、liq、活动和采样间隔分析；完整保留随后继续上行的反例及counterpart真实结果，不以未来峰定义是否正确。预计频率 **UNKNOWN**。

## 5. runner_requalification：实际partial后的余仓新资格

**假设与适用状态。** 第一次分批兑现不自动赋予余仓长期持有权；actual partial 后限定时间内，固定余量能否带来新的成本尺度净回收改善，应与旧整仓高点分开。适用于已真实部分成交且仍有余量的仓位，未到partial的两臂行为完全相同。

**共同partial与风险。** 经济净收益达到+30%时，两臂都触发卖出当时余量50%，必须后帧实际fill才成立；只设这一档，**没有第二TP**。硬止损、通用追踪和30分钟max_hold相同且优先。首次partial下单、pending、拒绝或失败都不是资格epoch。

**candidate的真实fill锚。** 实际partial settlement后冻结 `fill_id/filled_at`、原始post observed/provider/liq、实际remaining quantity `Q0`、该余量扣当前卖出成本的初始净值 `N0`、实际分摊后的remaining cost `C0`。epoch不依赖 `principal_recovered`：+30%净收益卖一半通常尚未回收全部本金，使用125专用回本门会使本机制逻辑错接。

**新资格判定。** 以实际partial后180秒可观察预算为期限，后续固定Q0的净回收 `N_t` 需同时满足：

`N_t>N0+.01*C0`，且 `liq_t>=.85*liq_partial`。

满足即本epoch取得资格；control不设这个期限审查。可完整观察到期限而未取得资格，candidate触发清余仓，仍等下一合格原池帧成交。数量固定，不能把累计已实现回款的增加、partial前峰值、价格单位变化或更新后的名义余量拼成进展。

**缺证据处理。** gap>60秒或provider变化，重启可观察180秒计时，但保留actual partial的固定Q0/N0/C0/liq及原始observed/provider/filled_at；后续新源不是一个假partial，不覆盖原始基值。不把停采耗时判成资格失败，不使用旧报价刷新时间。共同hard_stop/trailing/30分钟上限继续优先，缺证据不允许取消这些约束；到共同时限仍须符合实际退出证据合同。

**已有动作与真正新点。** 125已在真实回本partial后重置高点；executable-recovery已有amount_epoch峰重置；conditional-runner已在首次TP按两帧活动决定留一半还是全卖。这些不是本批新发现。**新增是actual partial后、独立于旧高点和本金flag的余仓期限资格状态**。对照必须同partial、同后续保护，不能和整仓提前兑现相比后把差异全归再资格。

**成本、反证与regime。** 使用actual quantity/allocated cost和当期真实Paper费用，不能套用初始5U作余仓风险预算。30%首卖后3分钟小幅改善可能常见，也可能对快崩无保护；免费源缺口可能不断延后资格审查，最终主要由公共风险退出。初次利润本身可能由同Token右尾驱动；本轮尚无其独立自然收益证据。适用partial后价态需按chain/liq/activity、partial到下一帧延迟和execution epoch分层，不能按历史日期挑有利时段。

**需要样本 / 失败条件。** 完整分母从共同入场开始，分别列未到partial、partial触发未成交、actual partial、资格获得、连续可观察期限失败、gap/source重开、公共风险先退出、仍open。需要相同真实partial起点的成对余仓结果，分清已实现首卖收益与candidate随后余仓增量；一笔Token复制多arm不增加独立证据。若改善只来自错误用更小余量/混合高点、额外费用未扣、缺流误失败或孤立赢家，结论无效。预计频率 **UNKNOWN**。

## 本批未新增的方向与报告停止线

- **下行冲击修复**：现有fast_stop_reclaim/panic_reclaim已有近等价行为，本批不再加近义账户；继续按其真实有效规则观察。
- **reserve / multipool**：输入覆盖、池类型与稳定同次pool集合不足，暂列储备，不把缺失当0，不用兄弟池代成交。
- **opportunity ranking**：先Shadow设计；不改旧ranker实际flow合同，不为排名新建昂贵全局重排。

两帧与120秒、180秒与一次120秒延期、1%余仓改善和4%追价预算均是事前固定研究合同，不是最优参数、统计显著性或alpha。未来评估需保留全部机会、未触发、拒绝、open和缺证据，按独立Token、版本/执行epoch及时间块报告，并检查中位数/尾损/删最佳Token后的方向。不得以短窗均值、工程PASS、当前未实现占位值或事后最高价宣布晋级。

## R3 裁决与证据边界

1. 本批Broad是各臂同Token/原池一次性机会，chase消费标记并未另行压制合同内合法Wave Reset；成对容量/现金仍限定了被评估的机会集合。不同账户不受共同容量限制时的周转效果不在本批直接结论内。
2. slow_grace保留当前代码的 `economic_value>=progress_value`，只宽限已回到进展锚的慢改善，不宽限仍在锚下的反弹亏仓；这是规则边界，不是历史已证实的收益筛选。
3. giveback候选与原profit_budget对照都在gap/source变化时重置**专属观察段peak**。部分Chat称control保留该peak的说法与 `research_finalists.py:174–180` 不符，不予采纳；公共trailing的生命周期高水位是另一状态，继续保留，不能混淆。
4. response新增单个固定首段涨幅≥1%门，其余三帧条件不变；这是根批准、由根代理落实代码的噪声幅度约束，不是1%成本线、参数搜索结果或收益证明。

本次只同步实验卡，不宣称已经完成新增门的实现、测试或部署，未重算任何历史结果。Chat意见按明确合同和代码证据裁决，不按多数票判断；追价错失右尾、计时与两帧效果未明、延期可能增加晚崩及新机制未获自然验证等反证全部保留。
