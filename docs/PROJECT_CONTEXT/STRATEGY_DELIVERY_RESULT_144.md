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
