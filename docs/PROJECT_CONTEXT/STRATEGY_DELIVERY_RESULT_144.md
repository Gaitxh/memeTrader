#144 非Agent多场景策略与有限学习

ACK: C2C-20260910-144-NONAGENT-STRATEGIES-LEARNING。唯一生产实施者仍为当前 Codex。状态 IN_PROGRESS。

最新144取代Agent恢复、浏览器及ModeChat扩建的当前优先级；143余仓已真实Paper关闭，不重复处理。39个用户地址只作外部选择的研究案例，不是交易名单、训练验证集或未来特征。

本轮顺序：独立早期活动与稀疏peer可交易切片 → 承接/确定性趋势runner/严格第二波 → 有界predict-label-learn及自适应新订单选择 → 统一注册、加载、自然漏斗与性能验收。旧139/141策略合同保留；新策略采用144指定2U/max2，普通原池4%/4%成本、统一安全、严格后帧成交。历史资金期和Live锁不变。

确认断点：139 Engine的30秒窗口与HOT至少3个peer、早龄m5/h1寿命重叠、所有模式共用buy-share>0.5会排除部分用户要求机制。采用新独立机制并显式记录输入合同，不能把旧阈值降低后称为修复。

当前运行读取：/health为running，version=chain-meme-trader/funding-20260906-v002-final-1000。此读取不是144部署验收。

## 分阶段事实

- 已读取完整144设计和39地址；未声明策略已注册或自然盈利。
- 源码、定向测试、注册、加载、自然signal/BUY/SELL和学习验收分别补记。整项任务不会以一个函数或一次注册完成关闭。

## 实施及实际加载结果（2026-09-10T15:06:45Z）

代码 `0e82bc4`、时钟/池ID补充 `b3e9324` 已提交推送并实际加载。当前Paper进程42880，启动回执15:02:32Z；所有manifest源码SHA256与当前文件一致。六条新策略14:58:47.477970Z追加在真实当前前沿；未克隆已有策略账户或重写旧policy。

| 注册号 | 精确arm | 机制和退出合同 |
|---|---|---|
|312|trajectory144_early_activity_fast_v1|早龄<300s，实际分段活动变化率加速；2U/max2/5分钟。|
|313|trajectory144_sparse_peer_hot_fast_v1|同链同龄peer足够时排名，稀疏时自身轨迹；2U/max2/5分钟。|
|314|trajectory144_absorption_reclaim_v1|先实际高点/回撤再收复，保留流动性；不要求买入笔数多数；2U/max2/15分钟。|
|315|trajectory144_trend_runner_v1|与312相同冻结机会及后帧，2U/max2；30分钟，真实300秒价格/活动/流动性健康才延至绝对120分钟；无Agent、无15分钟未回本强卖。|
|316|trajectory144_second_wave_v1|首波→显著回落→至少60秒底部→后来新启动；持久episode去重、每原池最多两次；2U/max2/30分钟。|
|317|trajectory144_adaptive_selector_v1|只选择真实可用的第二波/承接/早龄/稀疏HOT；2U/max2，冻结选中模式的5/15/30分钟退出。冷启动固定优先级，后续有限模型只改变新订单选择。|

共用原池、4%双边不利滑点、统一安全等待/拒绝、独立后帧成交、-20%硬止损/+30%激活/15%回撤跟踪及实际池底处理。max hold是退出触发边界，不保证缺行情时能即时成交。待安全查询的预约计入max2。旧139/141和既有策略保持原合同。

输入合同明确为真实3帧、30–90秒跨度、间隔≤60秒；共同成交端仍要求新鲜独立帧，不把缺失5秒或15秒窗口插值。旧窗口算法不修改。早龄m5/h1寿命重叠不再用作新早龄策略的加速度。长持窗口保存实际较老采样点，支持高频持仓的300秒跨度；支持合法40/64位EVM池标识、保留Solana大小写。窗口/字段未知和稀疏peer有独立计数。

## 有限学习实际闭环

`mode_learning144.py`接在原passive和Store快照回调，未新建请求/定时器/训练服务。信号与1/16确定性抽样的无信号样本冻结特征、概率、三个时钟、预测/模型版本。第一个严格后帧才是研究entry；其后5/15/60分钟使用自然同池行情与当前成本模型。缺帧、超时或已观察池底风险保持UNKNOWN，首次障碍顺序仅代表观察样本，不冒称连续价格路径。实际Paper BUY/终局单独按arm/cohort/source fill追踪，绝不把价格代理当真实交易。

128个pending、256个分组、每组256个收益、有限事件队列和已有KV/证据表；有界低优先flush。每horizon只学习一次，重启保留entry、已消费标签、模型及episode。模型冻结发布前沿；最大两个预注册coverage-cost-aware发布，只能从已有可用模式选择，不生成任意代码、阈值网格、重复funded对照或修改旧持仓。晋级要求独立样本/日期、成本后去前三盈利、覆盖、回撤及该机制实际终局经济证据；未达到就保留可交易固定基线。

真实有界历史演练：读取最新范围内128终局，用46笔具有可比冻结轨迹和完整因果时钟的记录训练终局分组；82笔缺可比特征排除，0.101秒。终局不是5/15/60端点，也不是新144策略回测。建议继续固定前向基线，未晋级模型。见 `data/research/strategy_delivery144/historical_training.json`。

实际自然闭环已推进：截至上述cutoff，5个无信号抽样、3个严格研究entry、2个OBSERVED标签、3个UNKNOWN标签，5个标签已一次性学习，4个episode仍等待剩余自然horizon。尚无模型发布；不能将这一小分母称为Alpha。

## 测试与运行保护

35个项目定向用例分批通过：真实producer→cohort→安全WAIT→后帧BUY→hard/time SELL（六arm）、预约上限、JSON重启/学习一次性、冻结成本/未来时钟/缺帧、第二波可达及旧Dex路径。另复用Lead的10个只读纯函数检查全部通过；没有重做原生固定状态证明或全仓库大扫描。

| 指标 | 加载前样本 | 当前样本 |
|---|---:|---:|
|held_fetch p95|4.216s|3.038s|
|held_apply_exit p95|71.1ms|36.3ms|
|passive queue wait p95|3.763s|2.427s|
|cohort_passive_compute p95|2.009s|1.121s|
|passive drops / PoolTimeout|0 / 0|0 / 0|

前后负载与启动窗口不同，这是短期运行保护通过，不是因果提速实验或长期无故障保证。当前运行累计2次held_fetch失败、1次ConnectError，保留原重试/客户代际恢复，不称“零错误”。未增加watch容量、来源额度、网络频率或持仓退出等待。

## 不可变性与自然交易边界

25份注册、原1份资金激活、0份资金恢复、旧311份policy的逐行摘要完全相同；只新增312–317。API Paper-only=true、Live locked=true。旧持仓按原规则正常推进，不改历史PnL。143已关闭余仓不重复。

本轮新引擎累计2764个合格帧；新策略实际BUY/SELL均为0。引擎显示的3个原始adaptive候选因没有可用基础机制被最终selector过滤，不能计作有效交易信号；最终信号/安全/BUY以共同cohort漏斗为准。现有synthetic299仍0自然仓，精确可卖模拟缺失不得伪造；本轮没有放宽它的1U/max1/5分钟合同。

39地址已按要求读取，仅作为Chat并行只读研究案例，未放进规则或模型验证。原16case已完成的47匹配/139回执不重扫；6h覆盖仍UNKNOWN。Agent、浏览器和ModeChat扩建延期。

当前分层状态：**代码/定向链路/注册/加载/有界运行保护已完成；自然交易经济性、15/60分钟覆盖与新模型晋级仍是持续前向观察，不关闭为“已证明盈利”**。工件：`data/research/strategy_delivery144/{before.json,invariants_before.json,historical_training.json,acceptance.json}`。无强制交易、无重置、无历史回填。

## Review144收敛：入口/标签/时钟与一次性训练

ACK `C2C-20260910-144-LEARNING-LABEL-REVIEW`，并合并先前 `C2C-20260910-144-REACHABILITY-REVIEW`，未增加reviewer。

已读取 `STRATEGY144_LEAD_REVIEW.md` 的完整增量。其末段明确记录学习V3接口适配后六项状态迁移回归全部通过；最初80帧滑动entry、回填available_at、raw训练、pending提前删除等属于已被 `0e82bc4` 替换的工作初稿。后续两个真实pool64/future-trend问题由 `b3e9324` 修正。本次当前源码无对应未修复差异，不恢复旧接口或重复重写学习核心。

当前合同逐项对应：

- `capture` 冻结决策、特征与当时成本；`observe` 把首个严格后帧保存在独立 `entry`，不依赖滚动buffer。
- `finish` 分开保存目标三时钟与真实调用生成时间 `available_at`，`train` 拒绝cutoff晚于可用性要求的反向使用；具体为仅消费 `available_at <= cutoff`。
- `buy_terms/sell_terms` 计算成本后收益；raw仅供诊断。每个chain/age/mode/horizon独立分组，记录独立token数量。
- 每个episode的 `learned` horizon和结果一起持久化，只有5/15/60全部处理才移至只读recent历史。训练不遍历recent，不会因其他有界seen集合截断重新消费旧标签。
- token+原池、observed严格晚于decision/上帧recorded、正有限价格和entry/target floor均在observe校验；缺口/缺价/已观测池底保持UNKNOWN。

本次新增并通过5个定向回归（未重复此前已通过整套检查）：

1. 390个每秒输入、首帧price1以后price2；延迟到t+390计算仍固定entry t+1/price1，5m target t+301/price2，label available t+390。raw=100%，当前4%双边成本回报=84.6153846%。t+389训练消费0，t+390消费1；JSON恢复不重训。
2. 继续自然时钟fixture至15/60m，每horizon恰好一个净成本样本；全部完成后仍保留审计label，再次JSON恢复训练消费0。
3. 参数化零/负/NaN/Infinity四项：不能成为入口；不能产生目标OBSERVED标签。

第一项首次断言仅因等价UTC文本 `Z` 与 `+00:00` 比较失败，改为时间值比较后通过；未为通过测试修改生产算法。无实际生产训练、历史重算或模型晋级。

39案例只读初查已完成，作为覆盖诊断保留：37/39本地found、34基础行情合格、16token对应285账户仓位（绝非285独立样本）；8个首个有效池无后帧、18个首后帧间隔>60秒，存在6000快照/2000评估上限与截断。未将名单用于规则、训练或验证总体。

**当前运行边界更新：** 上文15:06Z加载/自然指标是历史验收。用户随后要求重启，实际8790无监听，现有启动器启动操作被工具策略拒绝；本次只读health仍不可用。详见 `SYSTEM_STARTUP_RESULT_20260910.md`。本次只有测试和说明变更，不需要新代码加载；未宣称系统已恢复或已有新的自然学习验收。

### 指定状态迁移脚本实际执行

ACK `C2C-20260910-144-LEARNING-STATE-REPRO`。按本条明确要求，直接使用项目Python执行 `data/research/strategy_delivery144/review_learning144_checks.py`，当前V3 **6/6 PASS，0.018秒，exit0**。无标签pending保留、5m后15/60m保留、精确成本84.6153846%、超期端点UNKNOWN、observed早于decision拒绝、负均值不裁剪晋级全部通过。

这是实际capture→observe→train状态迁移执行结果，不是手填标签替代，也不是新reviewer结论。消息描述的V2五项失败在当前实现不复现；没有为本次检查修改脚本或生产算法，没有回退已修部分。上述源代码集成已完成，实际服务恢复仍受前述独立进程控制阻断，不能把6项测试PASS当作当前已加载/自然运行。

### 指定池身份/趋势时钟最终检查

ACK `C2C-20260910-144-FINAL-IDENTITY-CLOCK`。直接运行指定 `data/research/strategy_delivery144/review144_checks.py`，当前源码 **10/10 PASS，0.085秒，exit0**，包括 `test_supported_64hex_pool_id_is_not_rejected` 和 `test_future_recorded_trend_cannot_extend`。这两处已由 `b3e9324` 修正；本次未修改检查脚本、交易源码或旧合同，未重复运行学习六项。高频300秒路径保持通过，不列为阻碍。此为当前源代码检查，服务恢复/重新运行验收仍是独立边界。

## 自然运行与晋级边界更新 — 2026-09-10T16:04:25Z（北京时间9月11日00:04）

ACK `C2C-20260910-144-REGRESSION-ACCEPTANCE`。此前16项阻断在当前源码已解决，不再等待重复许可或运行相同测试。本轮为只读运行验收及当前检查点更新；没有调用训练/晋级函数、改变策略、发起额外市场请求或重启服务。

### 当前确已运行，旧启动阻断不再代表当前状态

实际Paper PID30748，manifest启动15:53:23.850126Z；当前Web和三个API均正常。`trajectory144.py / mode_learning144.py / runtime.py / store.py` 加载SHA256与磁盘完全一致。当前资金期仍为 `funding-20260906-v002-final-1000`，Paper-only/Live-locked，六arm均 `forward_enabled=true`。原25注册、311旧policy、1资金激活、0资金恢复的摘要与144前基准一致。

启动器的15:53启动日志和当前进程/API形成恢复证据；本轮未执行启动，不能声称绕过此前策略拒绝。恢复操作者未独立确认。没有新增/变更资金期。

### 实际Paper账户结果，不能当独立样本或Alpha

|策略|实际BUY仓位|终局|终局PnL U|仍开仓|
|---|---:|---:|---:|---:|
|312 early_activity_fast|0|0|0|0|
|313 sparse_peer_hot_fast|1|1|-0.422030|0|
|314 absorption_reclaim|4|3|-0.728185|1|
|315 trend_runner|0|0|0|0|
|316 second_wave|2|2|+1.630856|0|
|317 adaptive_selector|7|6|+0.480641|1|

14仓来自4个token、7个共同source fill；12个终局只有3个token、6个共同source fill。账户终局合计+0.961282U包含基础arm/selector同机会重复资本，不能视作14次独立检验。两笔第二波终局也来自同一个token。终局原因8次路径/活动/流动性衰减、2次trailing、2次hard stop。早龄与纯趋势还没有自然BUY；实际长持延期尚无自然验收。

### 学习真实推进，但没有晋级

61个冻结研究episode（19信号、42抽样无信号），32个严格后帧研究入口；143个已生成标签全部一次性训练，29 OBSERVED/114 UNKNOWN，30个episode仍等后续horizon。实际14 BUY/12终局另行追踪，没有与价格代理混合。

|固定horizon|OBSERVED|UNKNOWN|
|---|---:|---:|
|5m|21|37|
|15m|8|46|
|60m|0|31|

全部143标签仍在当前有界pending/recent证据内，没有尾部截断：87个UNKNOWN标签来自29个未在120秒取得研究入口的episode（每episode三个horizon），19个没有自然合格终点、3个路径缺口、5个池底/缺失。87不是87枚币。5/15/60不合并成独立样本量。

分组最多3个有效样本、最多1个UTC日期；与固定晋级要求的20样本/10token/2日期、UNKNOWN≤25%、去前三正收益、回撤及实际终局证据仍有明显距离。模型保持 `fixed_priority/v1`，releases=0；不扩大候选、放宽门槛或为负结果造晋级。当前数据不能证明经济性，尤其60m尚无OBSERVED。

### 连续约192秒运行观察：进展通过，抓取延迟保留告警

16:01:13→16:04:25同一进程：accepted帧21382→22993；无信号抽样41→42，严格研究入口31→32；期间未新增BUY或成熟标签（143→143），不能把仍等待horizon视作训练停机。原交易与其他策略继续自然成交/退出。

|指标|窗口前|窗口后|
|---|---:|---:|
|held_fetch p95|2.4898s|3.1701s|
|held_apply_exit p95|44.07ms|41.23ms|
|cohort_passive_compute p95|1.1895s|1.1823s|
|passive queue wait p95|2.0528s|2.4998s|
|flat target selection p95|0.9543s|0.9055s|
|flat overall p95|7.2464s|6.5814s|
|passive drops / PoolTimeout|0 / 0|0 / 0|

held-fetch相对该短窗上升0.6803s/27.3%，超保守25%或250ms线，**不能判定全部性能保护PASS**。仍为1次累计ConnectError/1次held-fetch失败，未增加；退出计算无回归，当前3个held token没有行情缺失/原池缺口，最旧观察约2.248秒。前后held token4→3，滚动窗口及上游负载不同，本轮无源码/部署变化，不能归因144或据此伪造因果提速/回退结论。保留LATENCY_WATCH，后续使用同负载请求/处理耗时证据定位；不自动暂停策略或修改请求预算。

原39案例14:32冻结汇总继续引用，不重扫、不作为训练验证赢家名单。Agent延期、唯一writer不变。当前结论：**运行/前向进展/账户链路可用；经济证据不足、无晋级；短窗抓取延迟未完全验收，继续观察**。

完整紧凑工件：`data/research/strategy_delivery144/forward_acceptance_before.json`、`forward_acceptance_after.json`。SQLite仅精确KV及小型不可变表；新策略仓位使用现有definition+arm索引，无全库/39案例重扫。

当前检查点已更新revision19，digest `183dca72391df32b1fc71a254d78d1da01661fcf8bddca02733cf46d826922ef`；ONE resume实际读回CONSISTENT，writer仍codex/epoch0、无stop fence。此为本地持久上下文验收，不代表Project memory或新Chat验证；后两项仍UNVERIFIED/REVALIDATION_REQUIRED。没有因ACK再递增语义revision。

## THREE-GAPS-AUDIT-1600 处置 — 2026-09-10T16:23Z

ACK/处置ID：`C2C-20260910-144-THREE-GAPS-AUDIT-1600`。已读指定 `THREE_GAPS_REVIEW_144_20260910_1600.md`。以下覆盖先前“实现边界通过”的过宽表述；不关闭144整体任务，不重复143/native/39案例扫描。

### 已修复源码：已有回执漏接学习观察器

实际调用链为：passive batch → trajectory features/signals → learning capture；原学习 observe 只在 Store 插入 token_snapshot 时调用。新增的实际 Runtime+Store 定向fixture在旧源码稳定复现：没有snapshot写入的已取得后帧不能建立研究entry。这证明接线不一致，不证明历史所有 UNKNOWN 都由此造成；Lead当时自然缓存检查未找到直接反例，保留这一限制。

现于原有batch消费处，先把同身份、合法时钟回执交给已存在的学习episode，再处理本批新信号。缺价/低流动性回执仍可记录负面路径；不通过entry过滤伪造健康样本。观察器额外核对token/raw chain/base identity，保留receipt来源、原取得/记录时间与实际处理时间。label available_at使用真实处理时间；原 strict observed > prior recorded 阻止同回执随后经Store再消费。没有新增请求、snapshot写入、watch额度、定时器或历史补录，pending仍有界。

验证：`tests/test_learning144_callbacks.py`、`test_mode_learning144.py`、`test_strategy_delivery144.py` 合计28项通过。新增覆盖真实被动回调、同批信号不能同帧入场、健康净成本标签、缺价池底证据、Store重复回执、一次性训练及三类身份不匹配。首次新增fixture失败明确显示entry缺失；最终same-batch测试启动时间fixture修正未改变生产启动边界。此前已通过10+6检查未重复运行。

**SOURCE_IMPLEMENTED / TARGETED_TESTS_PASS；NOT_LOADED / NATURAL_EFFECT_UNVERIFIED。** 16:23:44Z manifest仍是PID30748/15:53:23Z，runtime.py与mode_learning144.py磁盘SHA不同，其余所列源码一致。此前启动被工具策略拒绝；未重复或换通道绕过，也未先停止当前健康后台。加载、回调自然分母/归因及性能保护仍是明确待验收项，不能用本次测试当生产改善。

### 三项缺口逐项状态

|项|已落实|仍开放|
|覆盖|回调差异已用真实运行函数复现并修源；无新增数据请求|允许的加载后确认passive entry/label来源与延迟、UNKNOWN原因变化；30/120/300s有界观察供给尚未交付/验收，不能仅因修回调就称覆盖完成|
|趋势/第二波|有独立已注册执行合同；16:23Z第二波5终局/3token，+0.754722U|312/315仍0 BUY、长持延期无自然验收。Lead已逐项定位94921/94926安全transfer_pausable拒绝；不将其当当前转账已暂停的事实，也不绕过安全门。其余原始信号仍需实际漏斗归因|
|学习与晋级|固定5/15/60成本标签、一次训练、有界已有模式选择器|自动生成受限规则组合并追加新策略的DSL/执行链尚未实现；当前max2是selector模型释放上限，不是已交付自动建策略。已释放模型的完整撤回范围也未实现，当前release0无现存错误模型需撤回|

后续应先闭合A回调自然验收，再分别实现/验收有限模式选择的版本撤回与获授权受限规则组合→去重/输入可达/成本测试→新frontier Paper追加；不能靠扩大阈值或等待数据把缺失源码变成“已完成”。这些仍属当前非Agent144范围，未建立新队列或第二writer。

### 最新未加载修复前的自然事实

证据：`data/research/strategy_delivery144/three_gaps_callback_source_readback.json`（有界只读4.6s）与 `callback_preload_performance.json`。21账户终局=10共同source fills/5tokens，合计-1.276522U仍包含重复资本：313一笔-0.422030；314五笔-1.181965；316五笔+0.754722；317十笔-0.427249；312/315零。旧14/12/4是较早有效cutoff，不是当前数量。

81个保留研究episode、29pending；206标签=38OBSERVED/168UNKNOWN：5m27/53、15m11/63、60m0/52。126 UNKNOWN标签对应未在120s建立entry（三horizon计数，不是126独立币）；其余28无自然端点、9路径gap、5floor/missing。最大组4有效样本/1日，baseline fixed_priority/v1/releases0，未自动注册或晋级。

health/live/performance正常，当前资金期仍 `chain-meme-trader/funding-20260906-v002-final-1000`，Paper-only/Live锁定；本次生产操作仅只读，没有不可变policy/账簿/资金历史写入。held_fetch p95=2.651s、apply=57.5ms、passive compute=.729s、queue wait=2.676s，drops0/PoolTimeout0；当前5个held token无缺失/coverage gap，最大行情年龄1.675s。累计held_fetch failures8/connect_errors2较16:04Z的1/1增加；不称全程无错，也不归因尚未加载的补丁。加载后必须做同负载保护验收。

本次唯一语义checkpoint为revision20/digest `c7f9427b73e91701a4c93e541d2044feff6ddfae48fbbf585f3d53f1359fcee6`，144恢复为IN_PROGRESS并写明缺失实现；ONE resume一致、codex/epoch0、无stop fence。未改变pairing/session/memory状态。
