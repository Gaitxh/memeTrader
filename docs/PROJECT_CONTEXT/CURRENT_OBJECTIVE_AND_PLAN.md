# 当前目标与执行计划

## 当前交付阶段：第二篇入口和同BUY退出对照（2026-09-06）

完整独立双清单：`TWO_INDEPENDENT_DISCUSSIONS_2026-09-06.md`。event_reawakening_v1、surface_lifecycle_pipeline_v1及Vault/EarnHold/FailedContinuation三组同入场候选与对照共8个增量已接代码并通过最小相关测试。相同事件不重复入场，新事件需在原仓关闭之后，成熟事件需后续价格/深度与真实资金确认；候选/对照共用同一个BUY fill及规模，只有两边可参与才纳入配对。旧策略不变。

测试发现并修复同帧5U/20U分组cohort源快照唯一约束：不同规模生成注明原始source id的allocation快照，分别计算数量与成本，不新增API、不当新行情重复观察。新事件集成/配对同fill/原有DirectLP 5U及事件20U集成均通过。待本阶段部署从166到174；此时不是两篇全方向完成。

接续：PREGRAD优先观察与曲线净储备速度；无CA事件冻结集合排名；共享风险观察/剩余资源边界；更主动的独立机会策略（突破前净流积累、快速止损收复、深度先行和轮动等）。只凭真实时点输入，不未来函数，不恢复自动复盘。最后处理错误监督状态、图表并排、再次活跃0诊断、可证实工程补款与性能交付。原池修复及两个本地结果实验已在19:18:52Z/frontier891956部署，原账期保留。

## 原池补采及结果驱动两项增量（2026-09-06）

随后确认重启丢失内存补源集合、CG额度耗尽时，Token批量接口漏池会被误计原池缺失。公共基础修正：批量漏报仅failure，精确原池HTTP成功且补源无可用池后才记missing；网络失败/额度耗尽不作为撤池证据。7项补源回归通过，历史交易不改。不能因后来池仍存在但liquidity<1就宣称之前本来可以卖回本金。

真实缺口：GsW9…AP38L 原持仓池 EJ7d…DwBd 已长时间缺更新，但精确 Dex pair 接口返回同币同池、流动性0.84U。独立缺口队列改为先请求精确原池，仍缺身份有效数据才用CG补源；复用限流，每10秒最多一链30个缺口，CG每池60秒/原额度，主held循环不等待。新采样交原退出判断，不倒填旧价格。相关6测试通过（新增测试表名修正后单测通过）。

本地清洁自然样本18:50:22Z形成两个新假设：serial_conditional_runner_v1仅限制一个同时开放仓，不排队旧信号；sustained_breakout_earn_hold_v1保持原突破入场、精确PumpSwap输入下检验EarnHold退出。父策略不变，新ID真实部署起点，未证明优越。两项注册/幂等/单槽无重放及原池下一帧双侧4%测试通过。待本阶段部署后166。此前检索曲线/watch修复da2d9f2已于18:58:46Z部署，原164/账期保留，曲线已收到新桶。

尚未完成：第二次独立讨论中的PREGRAD WATCH、成熟事件再激活、无CA冻结候选资本排名、surface-specific组合，以及首篇同入场对照/共享风险观察覆盖。不是资源全不可得，也不以18个名称宣称全部覆盖。工程补款只给可证实实际损失，当前新增原池延迟正在核对。自动复盘仍暂停，完成全部后才语音。

## 继续实施：分别覆盖两次独立讨论（2026-09-06 北京时间03:00）

两次“设计新策略”聊天必须分别提取，第二篇不是第一篇的修订/替代。既有18只能作为逐项比对的实现证据，不是把原需求缩为18个名字；行为确实相同才复用并逐项标明，资源受限保留具体原因。现有164/原账期/开放仓和历史不变；新增方向及本地结果驱动假设增量追加，不修改旧合同。

本阶段已修观察名单的年龄桶不更新：持仓豁免TTL却永久占早期槽位，导致真实年轻候选无法进入。改为按当前池年龄重分桶，持仓复用主行情、不占非持仓3/4/3名额；非持仓容量与TTL不扩大，过期释放内存。总览新增单币检索耗时曲线：批次排队至返回耗时按币数加权，而不是除以批大小；10秒桶、最多120点，成功原池覆盖/失败币次分别计，独立20秒Web刷新，复用已有单行计时存储，不增加外部请求或历史扫描。8项相关回归和JS语法通过，待本阶段受控部署。

18:50真实新18已3笔BUY（Effective Breadth、Bundle-adjusted Breadth、Wave Reset），不能继续称全零。18:56后台工作集96.7MB/Web222.2MB，DB9.65GB/WAL381.8MB、E盘剩余55.63GB；两枚持仓原池接近10分钟未更新待定位，其余约5秒。后台真实性/低延迟优先，未决原池不能用其他池价补造。后续独立双清单与两条本地结果驱动试验未完成，暂不语音宣称全部完成。

## 02:03 当前部署与已知限制（2026-09-06 北京时间）

全部18个资金/生命周期方向已于17:21:37Z–17:21:38Z、frontier873998增量注册，当前effective Registry及8790 API均164个策略；原146、资金账期和开放仓/历史保留，无初始化、无Live开启，自动复盘仍PAUSED。全方向合同、输入、资源限制、测试与真实证据：`CAPITAL_18_DIRECTIONS_2026-09-06.md`。各方向是可证伪Paper实验，不能把注册或短时0 BUY当盈利/失败证明。

API补源及分链新发现/再次活跃曲线已部署，60个分钟桶，20秒UI节拍，非后台节拍。最新性能根因修复e023a96于17:45:02Z部署：0待BUY时不再联查全部历史entry_decisions，单次约0.987秒的无用扫描消失；17:52窗口策略周期耗时P95约0.95秒，held获取4.49秒、写入退出0.069秒。工作集后台94.1MB/Web176.6MB、DB9.50GB/WAL381.8MB、剩余约55.9GB，非长期SLA。

实际链上解析发现并修复合法24byte BUY被拒绝、合法SELL费用腿误当异常导致raw丢失；Creator在surface之后等待held空闲再取一次来源，短暂失败最多一次60秒重试；WSOL已有新鲜参考，不作Token执行价。最后修复4c7eaea于18:01:25Z部署，18:01:43Z Creator verified复用、18:02:57Z WSOL真实新鲜引用；完整资金流仍受热池截断/静默窗口覆盖限制，新18尚无自然BUY，不宣称已验证收益。补款已确认7518.807662700746U，不重复；新延迟cohort12154缺合格历史原池中间帧，尚不可确证赔款，不用其他池/后来峰值伪造。现金耗尽自然停买、028/096历史执行未决与当前缺价区别保留。

代码/相关回归/真实原始交易解析/部署与UI更新记录已完成。18:03:09Z当前68个去重持仓币，一枚BSC原池待价及一次失败、最大年龄24.5s，其余当时无缺价；不能称全源永不失效。策略耗时P95=.826s、held批次获取2.827s、apply=.071s，80/120个短窗口样本。自然样本、付费/不可得输入及额外赔款证据仍按报告限制保留；后续手动复盘，不恢复自动研究、不强制参数变体，也不重复已完成测试和初始化。

## 00:15 最新补充与实施边界（2026-09-06 北京时间）

用户要求同一“设计新策略”聊天增量全部方向实施，仍覆盖之前15+1；附件 aa9f93e3 已由主Agent完整阅读，新增 Direct/Normal LP Float-Constrained Scout、Authoritative Event Shock，不能因为聊天建议“只三条/其余延后”缩小用户范围。吸收其真实机制纠正：canonical migration 与 normal/direct Pool 必须 exact 区分；缺 migration fact 不是 noncanonical 证明；capital velocity 预测毕业不代表毕业后盈利；migration absorption 不得退化成迁移追涨。各方向必须分别实现、接入真实输入和前向实验；已测纯模块仍未注册，不算完成。

本阶段接通用户提供的 CoinGecko/Jupiter 密钥（仅本机DPAPI密文，Git忽略）、配额内原池缺口补源与已有Gecko新池响应直接补全。Jupiter实际只读quote、CoinGecko Robinhood exactpool请求均200；无跨API重复比价。主held通道不等待补源，CG日240/月8000本机预算及60s缓存不冒充秒级源。总览新增每分钟新发现/再次活跃分链曲线，ALL/Solana/BSC/Robinhood选择；Web独立20s缓存+有界rowid尾读取，不改后台采集节拍。记录及部署证据见 `API_COMPLEMENT_AND_DISCOVERY_2026-09-06.md`。

接续：剩余全部新策略entry/exit/actual量级quote/部署集成；完成后核对指标、性能、内存与存储。任务期间可证实系统故障造成的损失用原BUY唯一独立资金事件补偿，不改原PNL、不重复此前7518.807662700746U已补款、不把未证实反事实收益直接当补款。保留146旧策略/账期/全部历史与开放仓，无再次初始化、无Live开启、自动复盘仍暂停；仅全部完成后语音。

## 当前推进：全方向新策略与数据覆盖（2026-09-05 14:38Z）

当前active goal要求完整实现用户指定“设计新策略”讨论中的15个方向及第20节组合方向，不受“下一批仅三条”建议限制。全范围：Vault Hazard、Earn-the-Hold、Failed Continuation、Wave Reset、Migration Absorption、Executable Recovery、Capital Velocity、Effective Breadth、Price-to-Flow Fragility、Churn Resistant、Creator/Early Holder Distribution、Bundle-adjusted Breadth、Finite-capital Ranker、Market Regime、Competing Risk，以及High Recall→Earn Hold→Harvest→Exit→Wave Reset组合。只有实际资源不可用且留证才可跳过；纯函数/注册名不等于生产接通或自然效果已验证。

最新补充“后来很少交易可能在数据端”已多agent只读分层：14:08—14:38Z新Token Sol509→补全445→BUY85、BSC158→157→30、Robinhood281→16→8。551现金拒绝逐条均为真实匹配账户不足20U，非空eligible误标；Robinhood无池及hydrated后缺普通后续快照则是独立覆盖瓶颈。持仓当前无长期missing，但全轮配置1s/实际P95约8.79s。完整证据与分母见`HELD_CATALOG_AND_CAPITAL_CREDIT_2026-09-05.md`最新节。

执行接续：先用已有采集、amountful转账与严格时点框架补全新策略需要的连续输入；分阶段接入新entry/exit、同Fill对照与production调度，最小相关测试后增量部署，分别报告代码/源覆盖/自然交易。已有146、固定1000U账期、开放仓位、已到账补款和历史不重置不重复；未决历史成交不伪造；Live锁定、自动复盘保持PAUSED。当前并行纯模块尚未接入Runtime，不宣称新方向已部署。

## 最新修复结果（2026-09-05 14:02Z）

9eac92c/664ea9a已推送并于13:58Z部署：漏采Robinhood一币四仓已恢复且用两份新原池行情完成退出；当前账期372笔/49策略dust入场补7440U，另4笔确认漏采仓实际净亏损补78.80766270074568U，总7518.807662700746U。原交易与PNL不改写，补款独立资本事件、不重复，保留146策略/旧账期/全部历史、不初始化。028/096历史SELL证据未决明确展示待核查，不用现价冒充历史成交。多agent实查934条主判断中84.4%现金拒绝、0过期，判断P95约10秒；Robinhood存在Gecko有池而Dex无池的覆盖差异，不能说全是余额或采集端完全正常。详细账本、原因、实测和限制：`HELD_CATALOG_AND_CAPITAL_CREDIT_2026-09-05.md`。工程漏采已补款样本同样不用于策略优劣判断；定时复盘保持暂停。

## 当前修复（2026-09-05 13:35Z）

用户已授权修复持续缺价，并明确给当前资金账期内“入场池<1仍BUY”的策略补本金；这是新增外部Paper资金授权，覆盖此前“不退款”的限制，但不改写原交易或把补款算盈利。预核对376笔中4笔已被有效现金隔离，余372笔/49策略/7440U；按source BUY唯一记账，重复执行不重复补，不补旧账期。observer缺Token目录使Robinhood一币四仓漏进held采集；已补登记及原始入场身份恢复。历史未决成交保持UNKNOWN，页面改为明确待核查。三链入场→目录→held→下一帧退出、补款现金与原PNL分离、完整曲线回撤的最小测试通过，准备受控部署，不初始化。用户新增“广泛缺价/启动后不交易”排查由三个只读子agent分别检查覆盖、资金/机会/拒绝、队列与调度；不要把余额不足或样本稀疏直接判成bug，不改策略门槛制造交易。定时复盘仍暂停。

## 当前实施（2026-09-05，九方向实践）

13:01Z用户确认：不恢复两小时定时复盘，今后由用户手动提醒；现有automation保持PAUSED，不创建替代任务。此决定覆盖下方旧ACTIVE及“等待是否恢复”的描述，不暂停行情采集、持仓监控、策略交易或已部署的有界信息采集。九方向各候选/对照共18臂已实现、测试并部署，首次自然样本、空轮、基础核算和性能检查已记录；本轮实施验收完成不等于盈利验证。D1/D6/D7仅适用于已验证Solana PumpSwap输入，其余覆盖与样本限制见九方向报告。后续复盘由用户触发，不重置旧账户或历史。

12:48Z阶段验收：7e51bae两处覆盖/频率小修已于12:44:51Z仅重启后台部署，8790旧进程保留；12:45:51Z仍146策略/18臂/原资金账期，心跳年龄.383秒，行情与策略判断继续推进。没有改旧合同或初始化；旧账户自然又退出一仓，不能把自然变化说成“余额完全不变”。工作集截点后台83.7MB、Web122.3MB，不代表长期内存无泄漏。九方向实现和机制测试已具备，首次自然数据/空轮/配对失败结果已报告；盈利有效性仍未确认。重要更正：本机既有两小时复盘automation实际PAUSED（12:48核实），不是旧文档所称ACTIVE；已向用户询问是否恢复，未擅自恢复或复制任务。当前后台交易持续不受此暂停影响。

12:40Z自然验收推进：D1免费RPC已seed并生成完整参与窗口，D8首轮实际于12:27:04—12:27:30Z完成、0事件；空结果留存，不强制创造交易。D2/D4逐帧复算定位零BUY为已采样范围无联合形态，并非代码条件不可达；仅成熟观察槽TTL15→20min以扩大静默后检测窗口，仍3槽/链且不续期，其他预算/旧合同不变，定向测试通过。另修复研究结果显示30min与实际至少60min的差异，最小测试通过。两小修待本批正常部署，不重置。自然41组runner同入场闭仓候选-187.404U/对照-171.441U，未证明优越；完整原始研究、反例与计量边界见九方向报告。

12:27Z部署已成功：用户再次明确授权重启后，正常进程管理于12:26:54.501Z执行成功，未绕过执行限制。7102626代码生效，最后D1/D8四臂于12:26:57Z/frontier844074增量注册，现146策略，九方向各候选/对照共18臂全部部署。原账期07:37:08.842373Z和旧142保留；旧账户示例现金10.933201102786825/开放仓3前后相同。8790健康，心跳年龄1.193s，行情与判断成功时点12:27:19Z，Live锁定。尚需最后两方向真实输入覆盖及自然经济观察，部署不等于盈利证明；下文12:24重启阻断已解除。不再为本批重复初始化或重启。

12:24Z部署阻断：7102626已推送，最后D1/D8代码和调度回归通过，但本轮Stop-Process/Start-Process命令在执行前被工具层policy拒绝，未停止任何进程；不得换shell/工具绕过。12:23:41Z只读确认8790健康，仍142策略、19:54进程与原账期。待本机允许正常服务重启后才能146及最后两个方向自然输入验收；不宣称已全部完成。最近策略周期P95=1.548s、按批写入退出=.0835s、外部获取=4.866s，外部采集仍非全量秒级。无初始化、Live锁定。

12:22Z代码阶段：02e04c0已于11:54Z部署，142策略运行、原账期保留。方向1实际签名地址参与和方向8独立信息输入、四个新臂的代码及最小集成已通过；部署前发现并修复新任务错误合并到一个create_task的启动问题，调度回归通过。准备受控部署后146，不重置。九方向需分别区分代码/部署/源覆盖/自然经济证据；输入未覆盖或短窗口无成交不等于策略失败。D6/D7自然输入覆盖仍在检查，具体证据在同一九方向报告。

最新用户授权先修显式入场池<1仍BUY，历史只标工程异常而不退款/重写收益；随后逐一实现九个研究方向与必要机制对照，结合自然数据、公开研究及Chat讨论持续实践。执行清单与阶段事实：`NINE_DIRECTION_IMPLEMENTATION_2026-09-05.md`。当前128策略/1000U账期保留、不重置；规则变化新ID增量，不能用只出报告代替实现，也不伪称短窗口证明盈利。后台优先。

11:15Z阶段：用户明确授权由Codex重启后，11:14:44Z已成功重启后台与8790；a2e6f15五方向十试验实际于11:14:49Z/frontier835569增量注册，现在138策略。原128与资金账期保留，不清仓、不初始化。8790健康，新观察任务已调度；短窗口策略周期P95=1.024秒，批次写入退出P95=.105秒，尚非长期SLA。钱包参与/Vault/迁移/信息四方向的输入集成仍未完成，不得把本批称为九方向全部完成。

## 最新阶段结果（2026-09-05 17:14，以本节覆盖下方旧截点）

工作流提交769dc47、系统修复15b4d73、同仓多SELL纠正合计3883c0b均已推送并生效。当前账期仍是`chain-meme-trader/funding-20260905-fixed-1000`，没有重复初始化。入场池身份绑定已部署，现存127策略定义保留；独立试验`broad_cost_coverage_scaleout_v1`于09:00:51.814712Z/frontier833371加入，当前128策略，各自1000U普通20U，Live锁定。新策略已有自然BUY/SELL，尚未证明alpha。

已修复分链发现/漏斗刷新、账户余额+持仓总价值、全账期增量采样曲线、基于有效账户快照的最大回撤和多种排序。曲线采样只影响显示，不反推回撤；不可比较的历史估值留空。增量索引已确认范围SEARCH。

09:00暂停写入截点追加4笔跨池SELL纠正、隔离86个资金污染后续样本；原15,900笔源交易未改写。09:07检查305笔部署后新SELL，未再发现跨池/顺序错误。2个受历史纠正影响的账户仍有未决估值，不能伪造反事实成交或总PNL。同仓多笔SELL纠正被最后一笔覆盖的展示缺陷已改为逐笔合计，Store/Web一致性最小回归通过，不覆盖源交易。

短窗口策略周期P95约1.10秒、批次写入退出P95约0.10秒，与部署前接近；外部获取P95约8.42秒，原入场池数据年龄仍可达30秒。核心实时性优先，不能宣称全部每币秒级或实盘上线就绪。完整记录：`POOL_IDENTITY_AND_UI_REPAIR_2026-09-05.md`。

## 当前执行队列（2026-09-05 16:08）

用户最新补充先优化项目 AGENTS/skill/workflow，再继续系统任务。已删除过时的每推送全套测试、旧端口强制验证和反复重开高档 Chat 规则；新增项目技能 `.agents/skills/memetrader-forward/SKILL.md`，保留最小验证、独立判断与生产单写者。已有原生/MCP能力覆盖当前任务，不新增重复插件或修改全局模型/生产Agent路由。

随后执行：修复已经定位的跨池行情导致错误PNL；核对受影响历史资金并隔离污染；修复发现漏斗更新与ALL/Solana/BSC/Robinhood筛选；展示账户总价值/现金、全账期累计PNL曲线、完整历史最大回撤及多种排序；保持持仓与退出低延迟；通过现有接口新增有明确假设的受控Paper策略。新策略值得试验不等于已证明盈利，不因缺少alpha证明无限延后实验，也不使用工程污染作为参数依据。

本轮不初始化、不改旧合同、不启用Live。当前127策略自然前向继续，已完成部分不重做。下方部署事实为此前截点；后续修复与实测逐阶段记录。

## 最新运行事实（2026-09-05 15:40，以本节覆盖下方旧阶段摘要）

本次一次初始化已执行，不得重复。当前账期 `chain-meme-trader/funding-20260905-fixed-1000`，起点 `2026-09-05T07:37:08.842373Z`，快照前沿829428，127个原ID/合同哈希保持；初始现金每策略1000U。旧仓继续退出，旧卖出回款不混入新账期；新BUY/SELL已自然产生且无部署前回填。

已推送并部署 `f23611e`、`8b3ed82`。结果与未完成项见 `RELIABILITY_FUNDED_DEPLOYMENT_RESULT_2026-09-05.md`；05运行系统有真实速度，08更新历史有问题/改动/目的/验证/部署记录。当前短窗口循环正常但旧高负载长尾仍须观察；不承诺全部币每秒更新。Live继续锁定，Paper成交镜像的独立资金/退出耦合尚未完成，不可宣称真实上线就绪。研究证据不足，本轮未强行新增策略。

原有两小时任务 `memetrader` 已更新并恢复为ACTIVE，未创建重复任务。规则包含1000U/普通20U、旧回款隔离、取消MAE/MFE、先工程后研究、后台优先及禁止再次初始化。

## 本次执行授权（已执行，保留依据）

用户已批准 `EXECUTION_PLAN_RELIABILITY_AND_UI_2026-09-05.md` 并要求实施、验收后语音通知。先保证持仓采集、按批退出和真实核算；随后完成资金账期、界面及更新历史等已批准缺口。本次最终允许一次统一独立 1000 USDC 新账期，旧策略 ID/规则/历史保留，旧开放仓继续退出且回款留旧账期；不得将旧卖出注入新资金。未来新增策略仍 append-only。

Paper 普通单笔保持20U，现金不足不自动缩量；Live按实际余额缩量并独立保留原生手续费，实盘总开关保持关闭。取消 MAE/MFE，不做近期手动策略选择/三库重构。不用受工程延迟污染的结果研究alpha；没有合格证据时记录候选，不强行新增策略。原两小时任务待核实更新后恢复，不重复创建。下方无限资金、自动循环已启用与“全部正常”等旧快照不能代表当前状态。

## 当前阶段（2026-09-05）：v22 增量运行、基础计算与事件循环阻塞修复完成，等待自然证据

当前已验证事实：保留旧 124 个策略，v22 以 append-only 方式运行 127 个策略；不重置、不回填、不删除历史。Paper 研究资金不再因虚拟现金余额阻断机会，策略自身仓位与退出规则仍有效。PNL、池价值小于 1 的剩余仓位核销、有效 SELL 语义、持仓行情优先级、批量去重、数据库/运行时指标和内存边界已完成对应阶段并推送。

本轮基础核算复核进一步修复了 `correction ∩ contamination` 重复进入正式统计的问题；污染行继续可审计，但不进入 PNL、终局、胜率或持仓指标。最大回撤现以完整有效的已实现终局序列计算，不再随 Web 曲线截断变化；unconstrained Paper 不制造固定本金百分比。持仓详情展示真实 Token quantity，不再把 synthetic `amount_raw` 当成币数。后台退出评估只处理本轮成功刷新的 Token，健康检查保持轻量；Web compact 汇总缓存为 6 秒，5 秒轮询的热缓存实测约 42ms，冷汇总约 2.8–4.1 秒但不影响后台行情和退出。

最终性能复核确认，真正造成 60–90 秒周期性停顿的不是 DexScreener、PNL、OOM 或 SQLite 锁，而是 Flat Compression Shadow 目标查询的相关 `NOT EXISTS`：约 4,298 个候选会反复扫描约 90,918 条持仓索引。现增加仅覆盖开放仓的 `chain_meme_trader_positions_open_token_idx(token_id) WHERE status='open'`，不改变“任意版本只要仍持有就排除 Shadow”的业务语义。生产查询计划已由 `SCAN` 变为按 `token_id` 的 `SEARCH`，目标查询实测 0.2741 秒；重启后 63 个新前向 evaluation 的 `observed→evaluated` P50/P95/最大值为 24.454/49.335/54.769 秒，0 个 `entry_snapshot_too_old`，此前最近 5,000 条的 P95/最大值约为 129.121/404.661 秒且有 669 条超过 90 秒。

持仓行情目标此前存在固定 `ORDER BY token_id LIMIT 600`，在 1,000+ 个不重复开放 Token 下会永久饿死字典序尾部。现已改为开放持仓优先、从未尝试/最久未尝试优先的公平轮询；30 Token/请求保持不变，4 批并发仍受每主机 0.25 秒起始间隔约束，失败批次只记录 provider failure 和尝试时间，不伪造撤池/价格/PNL，并由后续目标让位轮转。每个成功批次即时更新健康心跳，不再等待整个 600 目标轮次结束。生产验收中无任何 market mark 的开放 Token 从 237 降到 0；外部 DexScreener 超时仍可能拉长全覆盖周期，但不会再形成固定尾部饥饿。

Flat Compression Breakout 当前仅为有界、去重、严格前向的 observer-only Shadow，不产生交易或 PNL；继续积累自然证据，成熟前不晋级、不合成新策略。定向测试、完整 524 项测试和 `compileall` 通过；最新一次 `doctor --online` 因外部网络探测 50 秒无输出而停止，未宣称通过。实际 Runtime、market marks、Flat Shadow 心跳、数据库增长、8790 health 与 127 策略 API 已验证正常，Live 仍锁定。

两小时复盘、基础健康检查与证据驱动的增量策略循环已启用；没有足够自然证据时只记录 Shadow/研究方向，不强制制造新策略，也不重置既有策略。

更新时间：2026-09-05 09:16 +08
状态：`ACTIVE / CONTINUOUS`

## 0F. 2026-09-04 21:58 +08 已部署：v21 保留旧 124，并增量运行本金回收 Runner 与 Vault Shadow

当前 Paper 运行态已切换为 `chain-meme-trader/v21-additive-principal-lock-runner-clean-forward`：旧 124 个策略定义、账户、历史与 lineage 全部保留，新增第 125 个独立策略 `broad_principal_lock_runner_v1`。激活 frontier 为 snapshot `817128`，首个 v21 source snapshot 为 `817129`，没有回填旧快照；v20 停止新入场，但旧开放仓继续退出。Live 仍由配置锁定。

Runner 沿用 Broad Launch 入场，-20% hard stop，+80% 时目标卖出剩余仓位 60%，保留 40% runner，partial Fill 后以实际 post-fill mark 重置 high-water，50% trailing，最大 240 分钟。`principal_recovered` 只在累计实际回收达到原始 20U debit 后成立；当前五个已触发 partial TP 的自然前向仓位中，三笔真实回收达到20U、两笔没有，状态没有按目标价伪造。

有界 Vault Shadow 已复用现有 PumpSwap `accountSubscribe`，仅覆盖新 runner 的去重持有池，`decision_eligible=0 / affects=none`。截至 `2026-09-04T13:58:35Z` 已有 3 个 resolved pool target、15 个严格前向 frame；它不会触发买卖或核销。v20/v21 synthetic `amount_raw` 未被当作真实 mint raw；未来任何 exact-Vault 退出必须先取得严格晚于触发点的 amount-specific executable quote/fill。

低频审计不支持现在统一放宽：Broad/market-visible 分母充足，但 Flow Burst 只有 2 个自然输入，Reawakening 为 0；另有 137 个输入缺有效时点价格/池龄而应拒绝，51/124 个旧账户现金已低于20U。前两者是短窗口覆盖不足，后者是独立账户资本耗尽，不是共享现金或通用门控故障。旧策略不改；只有形成 coverage-distance 证据后，才注册单变量继承策略。详细结果：`docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CODEX_TO_CHATGPT/C2C-20260904-215800-CODEX-V21-ADDITIVE-RUNNER-VAULT-SHADOW-RESULT.md`。

## 0C. 2026-09-04 08:54 +08 最新运行纠偏：先退役 v10 shared-cash veto，激活 v11 independent-arm cash

Lead 通过用户指定且唯一权威的 `@笔记本量化MCP-官方隧道` 再次核对当前 checkout、测试与 8790 运行态。**源码已经包含** `chain-meme-trader/v11-entry3-exit4-independent-arm-cash-forward`：同一 entry family 的每个策略账户独立计算现金，低于20U的账户单独拒绝，同一 cohort 仍只创建一个 authoritative Jupiter BUY intent，Fill 时再次按实际现金把同一 Fill 只投影给仍有资格的账户；针对性测试 `test_chain_meme_trader_independent_cash_keeps_solvent_arms_trading` 已通过。**但是部署中的 8790 `/api/state` 仍报告 v10** `chain-meme-trader/v10-entry3-exit4-route-surface-forward`，其冻结定义仍是 shared-cohort cash reservation。结合最新自然时期出现的 weakest-arm/shared-cash veto，这构成当前最高影响的代码—运行态漂移：一个 Broad Launch 账户亏损/现金不足不得锁死其余三个账户或整个 family。

因此当前最小发布顺序更新为：**(1) 原子冻结 v10 新入场并受控激活 v11；旧 v10 仓只继续退出；(2) 立即停止已越过前向边界且同时改变 activation 与 drawdown 的 Stage4 executable-equity v2 新 enrollment，历史保留并标 `CONFOUNDED_TWO_VARIABLE_TREATMENT / LEARNING / UNRANKED`；(3) 继续 actual-Fill PositionEquityFrame + all-position current-PumpSwap RiskKernel + critical SELL 抢占；(4) 再注册只改变 28% vs 15% executable-equity drawdown 的干净同 Fill 比较；(5) 后续才扩展 MarketFrame、Reawakening、Agent、Cockpit、L0–L4 与 BSC/Robinhood。**这不是放松 strict-forward/identity/protocol/execution truth，而是删除不必要的跨策略共享资金 veto，把“买入机会召回”和“持仓风险退出”分开。**

本轮 Codex 执行门铃：`docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260904-005400-CHATGPT-V11-INDEPENDENT-CASH-PROFIT-KERNEL-EXECUTE.md`。Codex 是唯一代码/Runtime writer；Live 继续锁定。

## 0D. 2026-09-04 18:35 +08 用户 supersession：当前 P0 完成后，保留旧 124 行为族并增量加入新策略组合

**执行顺序不变：先把当前 coherent P0 做到真实 stop condition，不因本节中断当前实现。** 当前 P0 完成后，本节成为强制下一周期，优先于无关的可选优化。届时先按真实订单行为整理现有 156 个版本化实例 / 124 个行为合同族：行为等价者合并，参数表面不同但实际很少改变 BUY/HOLD/SELL/SIZE/EXIT 的不得重复计为独立策略；真正改变候选、入场、仓位、持仓、止损止盈、流动性/可卖性或退出路径的才保留为独立行为。

**更正前述替换语义：不要抛弃原来的 124 个行为合同族。** 旧 registration、Fill、Position、terminal、失败与审计证据继续不可变保存；在行为整理后，旧 124 个行为族仍作为历史/基线/可继续前向运行的既有策略集合保留在系统中。新研究、实现和测试出的策略只作为**额外策略**增量加入当前 Strategy Registry/Runtime/UI，不得以“新体系替换”为理由删除、隐藏或停掉旧 124。行为等价策略仍需在统计与组合 PNL 中去重，避免重复样本/重复利润，但这不等同于删除旧 lineage。

新策略阶段允许并要求广泛使用当前本地数据、严格前向结果、历史失败/成功模式，以及公开互联网、官方资料、成熟开源项目与社区经验进行研究。目标不是堆数量，而是形成行为机制真正不同、风险收益互补的组合，包括但不限于高风险高收益、平衡、超短线/scalping、first-mover、momentum/breakout、pullback/continuation、reversal/mean-reversion、trend hold、快速兑现、非对称尾部、流动性/资金流、regime、生命周期和多阶段建仓/退出，并继续主动寻找尚未覆盖的机制。若自然窗口没有成交，可用当时真实可得数据、报价和流动性做 point-in-time Paper/模拟买卖来检验行为；仍严禁未来 ATH/事后最高最低价等 lookahead。所有测试计入手续费、滑点、价格冲击、流动性衰减和真实可卖性。

不要把“安全”理解成无限叠加统一硬门。严格时序、身份/协议/账户真值、amount-specific execution、exact dead/no-reentry 等底线继续硬；其他不确定风险优先作为策略特定 sizing、软过滤、监控和动态退出变量。系统需要足够交易频率来学习，不能因为防御性门堆叠导致一天几乎无交易。

Codex 同时恢复并主动使用既定 ChatGPT 协作协议：先读 `CHATGPT_CONTACT.md` 与 `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json`，主通道为 `GXH_C2C_V3`；Codex 用 `codex_app.send_message_to_thread` 向指针中的精确 Lead ChatGPT conversation 发送 compact envelope，并用 `codex_app.read_thread` 在同一 conversation 收取回复。详细状态机见 `docs/PROJECT_CONTEXT/CHATGPT_CODEX_BIDIRECTIONAL_CHANNEL.md`，耐久邮箱为 `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC.md`。不要启动第二个 Codex writer，也不要把大日志/diff/secret 粘贴到聊天；ChatGPT负责研究、策略/经济/因果复核与方案比较，Codex核验本地事实并负责实现、测试和运行结果。

强提醒/队列合同：`docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260904-093244-CHATGPT-FORCE-REMINDER-POSTP0-AND-DIRECT-CHAT-PROTOCOL.md` 与 `C2C-20260904-091100-CHATGPT-QUEUE-STRATEGY-REBUILD-AND-NEW-RESEARCH.md` 中凡涉及“旧 124 退出/被替换”的内容均被本次更晚用户纠正 supersede；其余“当前 P0 完成后立即进入行为整理、新策略研究/实现/测试、恢复 ChatGPT 直连协议”的执行顺序继续有效。当前 P0 到达 stop condition 时，Codex 必须 ACK 本次纠正并把本节提升为下一 active cycle。

## 0E. 2026-09-04 19:50 +08 后续最小策略增量：本金回收 Runner → v20 Vault Shadow → 结果驱动合成

当前 P0 顺序不变，不中断正在执行的核心任务。P0 到达真实 checkpoint 后，以 `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260904-115000-CHATGPT-FINAL-MINIMAL-ADDITIVE-STRATEGY-V20-FLOW-PLAN.md` 作为本轮策略研究的最新实施合同。旧 124 策略全部保留；新策略只增量加入。

第一步不做大架构：直接在现有 v20 policy/market-mark/Strategy Registry 上新增 `BROAD_PRINCIPAL_LOCK_RUNNER_V1`，以现有 Broad Launch 为入场，+80% 经济收益时锁定 60% 仓位、剩余 40% 用宽 Runner 捕捉尾部，并从新前向 frontier 独立测试。第二步才复用已经运行的 `SolanaHeldAccountCollector.accountSubscribe`，给新策略持仓增加有界 PumpSwap Pool/base-vault/quote-vault Shadow 派生层；不先建全量逐笔/Geyser平台、不堆新通用入场门。规律性买卖只形成描述性 `REGULARITY/SYNTHETIC_SUPPORT/UNWIND` 特征；真实 reserve/effective-depth 急剧恶化是独立的 exact 风险事实。

重要实现边界：v20 `amount_raw` 是 `paper_quantity*1e9` 的 synthetic unit，绝不可直接作为链上 mint raw amount；未来 exact quote 必须用 `remaining_quantity_tokens × 10^RPC-verified decimals` 的 decimal-safe 转换。Exact-Vault 触发在有严格的 post-trigger amount-specific executable quote/fill 之前保持 Shadow，严禁在真实 reserve 已崩时仍按滞后的 DexScreener 高价结算 Paper SELL。等新策略取得真实前向结果后，再按当前真实决策行为 hash、底层 cohort 去重和成功/失败域设计 A+B→C 类综合新策略；C/D 等仍全部作为新策略加入，不覆盖父策略。

此前 `C2C-20260904-104900` 的广泛微观结构研究继续作为背景，但其“先建完整逐笔 TradeMicrostructureFrame”的实施顺序被本节和 `C2C-20260904-115000` 收缩为 Vault-WebSocket-first 的最小路径。

## 0. 2026-09-04 02:17 JST 最新 authority：官方隧道、单主升浪假设与市场级 v6

用户明确纠正：本项目本地访问**始终允许且只以 `@笔记本量化MCP-官方隧道` 为权威插件**；其他连接面不得写入或改变本项目 authority。用户同时提出“新 Meme 基本只有一波，最高点回撤后大概率结束”的交易假设，并再次要求以挣钱为目标、不要用过度防御压低机会覆盖、把系统做到可上市水准。

Lead 已用官方隧道对当前 r6 做只读检验。对 Solana 正价格快照不少于10个、跨度不少于30分钟、先有至少25%上涨的约4,084个 Token group，首次30%回撤后在15/60/240分钟内再创新高约为8.33%/11.93%/13.82%；若要求回撤在3分钟内由第二个观测确认，Pump地址子集在60/240分钟再创新高约2.90%/6.82%。另一严格口径的133个持续30%回撤事件只有12个后来再创新高，0个在10分钟内发生；多数例外在10分钟以后，支持“先退出、真正复苏时用新 `REAWAKENING` cohort重入”，而不是长期扛过深回撤。该统计受当前四日窗口、稀疏/条件采样和右删失影响，只能作为 active hypothesis，不能直接把30%写成所有策略的最终阈值。

更重要的自然样本是v5 cohort `2286`：Stage1在Dex表面约317k流动性、buy/sell 238/114、canonical PumpSwap与静态mint安全正常时入场；全仓可执行最低回收从约20.5434U在约20秒内跌到0.0062U，最终约-19.9937U。exact vault后验核验显示quote vault约从1,512 SOL降到约1.10 SOL、base vault从约11.5M Token增到约951M Token，属于大规模卖入池抽干SOL，而非LP removal。Stage1因现有代码只给Stage11/12挂held-account targets而没有实时风险监听。这证明当前最高影响断点是**所有持仓共享的低延迟Pool/Vault/flow/recovery风险内核和退出抢占**，不是再加一层静态买前硬门。

随后自然样本进一步收敛断点：cohort `2298` 虽有五类exact targets，真实WSOL vault仍在入场后约19.65/19.98/20.46秒分别降到raw baseline的38.83%/16.66%/5.37%，约24秒低于1%，base vault同时增至约7.25倍；现有风险状态因只认“单步直接跌90%”或“双边Vault都耗尽”而始终为HEALTHY，最终等Dex liquidity<3000才以每账户约-19.6643U退出。当前官方Pool另有约17.5845 SOL virtual quote reserve；按`real + virtual`的effective depth，2298同期约从46.97%降到13.69%，仍是约86.3%的严重深度崩塌，但raw flow与effective price depth必须分开。cohort `2306` 又证明每步不足10%的渐进恶化会被mutable state覆盖，无法形成1s/3s/10s/30s斜率。另有13/13 v5 LP mint实际为Token-2022 owner，目标却硬编码legacy Tokenkeg而产生固定误报。P0因此不仅是coverage，还包括**连续reserve-flow语义、append-only risk frame、正确program owner与增量订阅**。

收益去重也推翻了表面盈利：在一个10个底层机会均已结束的截面，代表性20U路径合计约-13.5799U、3胜7负、中位数约-1.9758U；最大赢家+37.9134U，移除后约-51.4933U。相同市场路径复制进多个策略账户后却显示正的账户合计。`strategy_counterfactual_pnl`、unique/netted `portfolio_paper_pnl`和future `live_confirmed_pnl`必须永久分开；行为等价账户不得增加样本或系统利润。

当前 authority：

1. v5已有真实分母，保留为`ORDER_KERNEL_PILOT`；v6激活前可继续自然运行，v6激活时停止v5新入场，旧仓继续退出，不修改v5历史。
2. v5虽然实现了Decision→OrderIntent→Attempt→quote-simulated Fill，但仍沿用历史Stage门，未完成3×4独立策略；cohort2285把同一底层赢家复制到12账户，每账户+37.913424U，不能把合计+454.961088U称为系统利润。v6必须区分strategy counterfactual、portfolio paper与future live confirmed PNL，并检测behavioral equivalence。
3. v6采用`Broad Launch / Flow Burst / Reawakening × Fast Escape / Balanced Harvest / Peak Guard / Post-buy Research`十二策略矩阵。Broad Paper可以宽，但所有仓位必须共享exact targets、post-fill full-size SELL heartbeat、风险状态和RED/DEAD抢占通道。
4. 峰值退出只使用当时运行中高点。持续回撤、failed reclaim、sell-flow、quote-vault、large-sell burst与全仓recovery slope联合形成Peak-Death hazard；未来ATH只作outcome。真正第二波另行重入。
5. 当前5秒Runtime与15–20秒估值不足以应对20秒collapse。P0恢复PumpSwap transaction decoder和低延迟Geyser/Yellowstone provider benchmark，形成250ms–5m MarketFrame；风险线程不得等待Agent、DexScreener或Web。
6. quote-only minimum output只能标`L0_QUOTE_ONLY/QUOTE_SIMULATED_FILL`。市场级Paper/Live内核要继续到taker/buildable transaction、RPC simulation、confirmation、balance/fee reconciliation；Live工程现在做，资本开关仍锁定并需用户显式授权。
7. 当前Python SQLite为3.51.0、主库约5.7GB、WAL约930MB；SQLite官方WAL-reset修复要求升级到3.51.3+或官方backport。先Online Backup、隔离副本校验、升级、WAL/reader telemetry与restore drill，不在活动库盲目VACUUM/TRUNCATE。
8. 当前官方PumpSwap IDL/SDK又暴露协议正确性门：抽样18个exact pool均为301-byte account，当前Python只解前211 bytes，忽略`coin_creator/is_mayhem_mode/is_cashback_coin/virtual_quote_reserves`；18/18 virtual reserve非零。新monitor/surface版本必须先完整解码、冻结IDL/SDK hash、获取GlobalConfig/FeeConfig，并用官方SDK公式做本地direct holding-surface risk quote。该本地quote用于每个Vault事件后的亚秒风险估计，Jupiter full-route仍是实际执行权威。
9. v5延迟审计：source baseline→下一BUY quote-simulated fill p50/p95约8.607/16.249秒，而provider调用p50/p95仅约0.526/2.819秒；首个全仓估值p50约208.79秒，27个cohort只有3个在10秒内获得。主要延迟在本机调度与风险覆盖，不应只提高provider并发。
10. v5动态退出还存在账户基准错误：当前止损、止盈和trailing以成交前DexScreener `entry_signal_price_usd` 为锚，而不是实际指定金额BUY Fill的成本。对23个自然Stage-4入场只读核验，`信号价 / 保守Fill有效单价` 中位数约0.946339，范围0.721314–1.507246；3/23偏差超过10%，2/23超过25%。cohort `2314` 的信号价为0.000287，但20U保守Fill得到105,034.589879枚，真实有效成本约0.000190413463；旧控制只把后续0.0003437视为约+19.76%，事实上相对Fill成本约+80.50%，全仓可执行权益高点为41.283448U。v5历史必须保留并标记`legacy_pre_fill_signal_anchor`；v6及干净Stage-4 v2的return/hard-stop/TP/trailing/high-water必须统一基于实际Fill成本和`已实现回收 + 当前全部剩余数量最低可执行回收 - 未嵌入成本`，Dex价格只作速度/交易流信号。
11. 详细研究与实施合同：`docs/PROJECT_CONTEXT/CHATGPT_SINGLE_WAVE_PEAK_EXIT_AND_MARKET_GRADE_PROFIT_PLAN_2026-09-04.md`。P0顺序冻结为：authority/v5 truth→官方301-byte Pool decoder + all-position risk/EXIT fast lane→Fill成本/总可执行权益账户真值→冻结缺公共安全包络的Stage-4 v1并注册干净v2→v6 3×4→PumpSwap transaction flow/MarketFrame→execution L0–L4→learning/storage/Cockpit→BSC/Robinhood。

## 0C. 2026-09-04 09:59 CST 用户纠正：开放式策略注册表、禁止学习退化与资源/OOM硬约束

用户进一步纠正：策略数量**不局限于12个**。最初的12个Stage策略是永久`Baseline-12`策略库；后续`Broad Launch / Flow Burst / Reawakening × 4 exits`只是新的Challenger集合之一，不能语义上替代Baseline-12。前向学习可以基于任何已有策略进行组合、拆分、特征/入场/退出/执行改进，也可以提出第13、第20或更多全新策略；每次改变都创建新的不可变strategy/version/lineage，不能看完结果再原地改策略。新版本不因“更新”自动优于旧版本，必须采用`Baseline/Champion -> Challenger -> strictly-forward experiment -> maturity review -> Promote/Reject/Pause/Rollback`，保留旧基线作为持续benchmark。工程正确性修复可淘汰错误机制，但不能被宣传为alpha提升。

主页排名必须恢复且永远有诚实输出：已实现终局结果可形成`REALIZED ROBUSTNESS`排序；当前开放仓位可执行权益另按fresh exact quote覆盖率形成`EXECUTABLE EQUITY`排序；低样本/估值不完整可显示`PROVISIONAL / LOW-N / INCOMPLETE-COVERAGE`，不能把UNKNOWN补0，也不能因为一个开放仓缺Jupiter报价就让整个Top榜空白。没有通过成熟门的策略不称Champion，但仍可显示暂定排名；全策略页展示Baseline-12、所有Challenger和历史Retired lineage。

资源约束同步提升为生产发布硬条件。当前r6主库约5.8GB、WAL约888MB，策略和高频RiskFrame继续增长会带来OOM/读放大/锁和页面卡顿风险。所有新增策略/学习/MarketFrame/Risk/Web功能必须使用有界内存ring-buffer/缓存、队列上限与backpressure、分页/分块DB读取、bounded Web queries/materialized projections、cohort级公共证据去重，禁止全表`fetchall()`和每策略复制RPC/Jupiter/Agent/市场证据。高频非决策原始事件不得无限写入SQLite；决策/Fill/terminal证据永久保留，其余只保留有界聚合或版本化冷归档。持续监控Runtime RSS/private memory、queue/cache sizes、DB/WAL bytes、write/checkpoint latency和Web latency；高水位时先停低优先级Agent/enrichment/history aggregation并释放可重建缓存，保护RED/DEAD/SELL和交易状态。必须完成Online Backup/restore drill和已批准SQLite修复升级后再做破坏性WAL维护，禁止在活动库盲目VACUUM/TRUNCATE。

详细执行纠正：`docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260904-015900-CHATGPT-STRATEGY-REGISTRY-RANKING-RESOURCE-GUARD.md`。该纠正不改变当前P0顺序：先v11 independent cash、停止污染实验、实际Fill/可执行权益/RiskKernel/critical SELL，再修排名和开放式Strategy Registry；内存/存储/OOM约束从现在起对每一步都生效。

## 0B. 2026-09-04 早先 supersession：Profit-First 多策略自动交易学习系统 v5

用户进一步明确：最终目标是盈利，当前 12 个 Stage 必须被理解为 12 个独立策略账户，而不是历史工程演进卡；买入候选覆盖不能被越来越严格的统一硬门压到极少交易，卖出反而必须更敏感、更快；撤池/死亡前若存在可重复的前向可执行盈利窗口，应允许独立高风险 Paper 策略学习；买后 Agent 可快速多角度调查，但不得阻塞机械/紧急退出；Paper 与未来 Live 必须共用 Strategy -> Signal -> OrderIntent -> ExecutionPlan -> Fill -> Position -> Exit 状态机，只允许 Executor/Signer 不同，Live 继续锁定且密钥永不进入 config/UI/SQLite/Agent。长期还要纳入 `REAWAKENING` 独立 cohort、BSC/Robinhood execution adapters、延迟/存储/重复工作和 8790 Trading Cockpit 优化。

因此，2026-09-03 的 single canonical-PumpSwap focus **只在已经验证有价值的 execution-truth / held-account / confirmed-rug 基础设施层继续有效**；其“把越来越多风险事实变成所有 Stage 共同硬入场门、把 12 Stage 解释成 cumulative evolution”的产品/策略定义被本轮更具体用户要求 supersede。旧 v4 registration/rows 必须冻结保留，不回填、不改写；新行为通过 v5 新 registration 生效。

当前 P0 改为：

1. **冻结 v4，注册 12 个真正独立的 v5 StrategyAccount/PolicyVersion。** 至少包含 Broad Launch 高召回、Momentum+Flow 和独立 Reawakening entry family；不同策略拥有 Fast Escape、Balanced Dynamic、Local-Top Peak Guard、Post-Buy Research Runner 等独立 exit policy。旧 Stage evolution 移到历史页。
2. **统一 Paper/Live 交易状态机。** v5 禁止 Strategy admitted 后直接写 Trade；必须通过 `OrderIntent -> amount-specific ExecutionPlan/Attempt -> Fill -> PositionEvent -> ExitIntent -> Reconciliation`。Paper/Live 只替换 execution adapter；Live interface 完整但 hard locked。
3. **BUY 宽、SELL 紧。** 严格时序、数据一致性、unsupported/协议无效、exact dead-surface no-reentry 仍是公共硬合同；momentum/liquidity/creator/rug/recovery 等大多数风险变成 strategy-specific soft facts。保留一个明确 `paper_only / not_live_eligible` 的高风险 Scout，用前向 writeoff/no-route 分母验证是否因过度防御错过盈利机会。报价缺失、过期、`no_route` 或 provider error 时，可执行权益与未实现 PNL 必须是 `null / UNKNOWN`，既不得借用屏幕价伪造，也不得写成 0；只有 exact pool/account 已确认死亡且随后一次新鲜 full-remaining SELL 仍不可执行，才把剩余仓位核销为全损。
4. **建立持仓 fast lane。** exact account WebSocket、Pump/PumpSwap flow、本地短窗派生特征触发 GREEN/YELLOW/ORANGE/RED/DEAD；价格长期不动只作 suspicion trigger，先请求 full-remaining SELL，不单独判死池；confirmed terminal 继续需要 exact pool/account + full-remaining sellability 真值。紧急 SELL 优先级高于估值、研究和 Agent。
5. **持续研究局部顶部退出。** 只用 strict-as-of 的 price velocity/acceleration、高水位回撤速度、volume/flow 反转、trade interval、buyer breadth、liquidity/vault delta、Jupiter recovery/route deterioration 等派生特征；禁止 later ATH 作为实时输入。
6. **买后 Agent 去重并异步。** 每 Token/cohort 一个共享 ResearchCase；最多两条生产 Agent lane，数值链上事实走本地 deterministic code；结果只影响 completed_at 之后的 runner/risk，绝不覆盖 RED/DEAD 或硬机械退出。
7. **复用公共执行内核后再扩链。** BSC 与 Robinhood 使用 firm 0x quote、exact sell amount、simulation、allowance/tax/gas/L1 fee 等 EVM adapter；Robinhood 先排除 Stock Token/RWA，不复制 Solana 费率。
8. **8790 变成 Trading Cockpit。** 首页显示运行心跳、discovery/order/exit pulse、延迟、open risk、真实 executable equity 和成熟 Top 3；未成熟策略 `LEARNING/UNRANKED`。全部 12 策略、Token 深链、Execution、Risk、Learning、Chains、System、History 分页展示。

详细实施合同已写入 `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-162000-CHATGPT-PROFIT-FIRST-V5-STRATEGY-EXECUTION-PLAN.md`。Codex 仍是代码/测试/部署唯一执行 owner；当前 v4 Paper Runtime 不要求停机，Live 继续锁定。

## 0A. 2026-09-03 12:00Z 用户优先级重分配：Solana 纯链上盈利闭环（历史当前周期，已被 2026-09-04 v5 产品/策略定义部分 supersede）

用户明确要求以“尽可能多挣钱”为最终目标，并指出一旦**真实池子被撤/端掉**就不考虑恢复。结合当前 r6、Runtime 和最新前向证据，本轮新增工程/研究资源正式重分配为：约 70% Solana 安全/执行/机械持仓监控与死亡池终态、20% 严格前向链上 alpha 数据工厂、5% 轻量运行可观测性、5% 信息链 maintenance mode。信息/热点/人物/社区线不删除，但不再占据当前主工程和 Agent 预算中心；只有新的前向转化/经济证据证明其边际价值重新上升时再扩张。

当前决定由 `docs/PROJECT_CONTEXT/CHATGPT_ONCHAIN_CORE_REALLOCATION_AND_EXECUTION_PLAN_2026-09-03.md` 详细定义。它 supersede 的是**实施优先级与资源配置**，不删除任何旧 registration/row，也不倒灌历史结果。

当前 P0 顺序：

1. **先修 execution route 与 holding surface 的安全语义错位。** 最近 100 个有效 Solana Jupiter baseline BUY 抽查中，31 个实际 route 不包含触发 DexScreener snapshot 的 pair；当前安全层不能再把“snapshot pair 已验证”隐含为“实际 Jupiter route 全部已验证”。Holding surface custody/mint safety 与 amount-specific execution route 必须分层、时点有效、可审计。
2. **直接 RPC 解码 SPL Mint / Token-2022 危险能力。** GoPlus/Rugcheck 改为 cross-check，不再是 mint/freeze/transfer-fee/permanent-delegate/transfer-hook 等关键控制的唯一事实来源。
3. **实现 exact held-account 事件驱动监控与 `POOL_DEAD_TERMINAL_NO_RECOVERY`。** 确认死亡只能来自 exact pool/account 的链上事实，不能由一次 `no_route`/API error/Dex `liquidity=0` 推断；确认死亡后最多一次立即 remaining-size SELL，失败则 write-off，永不 re-arm/恢复该 dead surface。后来出现的新 pool 是新 market surface/cohort，不回写旧 PNL。
4. **PumpSwap on-chain flow decoder + strict-as-of alpha frames。** 保留现有 `_momentum_score` 为 immutable control，新增 value-flow、trade-size、burst、creator、liquidity/route、holder 等研究特征；先透明 challenger，后模型。
5. **大 UI、多链、额外 venue 暂缓。** 当前 `onchain-only-shadow/v2-20usdc` 的 Solana cohort 32 个中 31 个为 PumpSwap、1 个 Meteora；因此本轮唯一主动策略开发/Paper promotion 目标收敛为 **canonical PumpSwap**。已完成的 Raydium CPMM v3 decoder/证据保留为 Research Lab 资产，但本轮不继续扩展；CLMM/AMM-v4/Meteora/Orca 继续 fail-closed WAIT。BSC/Robinhood 研究资产保留但暂停扩张。Web 大重构不阻塞主线，必要实时状态优先用只读终端 cockpit。

信息线进入 **passive maintenance mode**：保留 deterministic ingestion、exact CA/post/provenance、不可变分母和未来可复盘 optionality；本轮暂停主动 `trend_scout / source_discovery / token_context / fact_verifier / WATCH / S3 post-entry narrative` Agent dispatch。只有被动证据达到已固化 reactivation gate 后才另注册主动预算版本；不得增加 production Agent concurrency。

纯链上当前**尚未证明稳定盈利**。任何晋级仍必须保留 no-route/dead/writeoff 在 ITT 分母，报告全成本 PNL、可执行权益、回撤、尾部、writeoff/no-route、资金时间效率、Top1/Top3 贡献以及 remove-best-1/remove-best-3 后结果；不得因当前少数大赢家调参或扩大 Live 风险。

## 1. 最终目的

持续提高新 Meme Token 的**样本外、扣除真实近似费用后的风险调整收益**。系统要更早发现可能驱动 Meme 传播的信息，把它与正确且可交易的 Token 建立可审计关系，在 Paper 中验证买入、退出、滑点、费用和尾部风险；只有成熟前向证据成立后，才另立小额真实交易发布线。

“为了赚钱”在工程上具体等于同时改善：

- 有价值机会的及时召回；
- 误报、同名币、推广和陈旧信息过滤；
- exact CA/canonical Token 正确率；
- 报价、流动性、安全和实际成本后的可执行性；
- 最大回撤、尾部损失、集中度和资金占用；
- 多日期、不同市场阶段的样本外稳定性。

不能用更多页面、更多 Agent、更多 Decision、更多 Paper 成交或历史高收益代替上述目标。

## 2. 当前事实判断

系统骨架已经存在并运行：信息-first 与 Token-first 采集、Event 聚类、Event↔Token、Strategy/WAIT/REJECT/CANDIDATE、Paper、SQLite、双语 Web、Agent 与来源审计、15/60/240 分钟前向账本。当前配置是 Paper，Live 硬锁。

主目标尚未完成。2026-09-02 15:31（Asia/Shanghai）的严格最近 24 小时截面里，采集链记录 55,634 个新 Token、2,105 个新 Event，但 Decision 只有 1 个 CANDIDATE、336 个 REJECT、797 个 WAIT；主 Paper 仍只有 1 次 BUY 与随后 1 次 SELL。Token Context 准入账本有 5,224 次评估，其中 365 次 admitted；主要跳过原因为 `no_eligible_trigger=1,885`、`global_cooldown_active=1,725`、未核验 provider-X metadata `599` 和无 metadata seed `572`。当日 Agent 调用与 Token 预算没有形成阻塞。

这说明“新币和事件很多，但及时、独立、精确、可决策的绑定转化率极低”是当前数据支持的判断。采集轮次、provider 返回数和 context-only 条目不能等同于独立事件证据；Agent 准入也不能等同于有效机会。

新的前向结构证据进一步收窄了断点。初算的 `130 组/548 Token` 使用了可变 `token_source_links.first_observed_at`、完整 URL 分组和组内最早链接时间门，不能作为未来注册口径。Lead 独立复核以固定 cutoff `2026-09-02T07:32Z`、X Snowflake `status_id` 去 URL 参数、每个 Token 单独执行 `[-5,180]` 分钟门，并要求不可变 `token_discovery_exposure_source_links.recorded_at` 后，得到更严格的 **103 个帖子 episode、529 个帖子—Token membership、528 个不同 Token**；其中 37 个单 Token episode、36 个 2–4 Token、30 个至少 5 Token，最大 82。全部关系仍是 `provider_metadata / identity`，约 78.8% membership 集中于 `@solana` 与 `@elonmusk`，因此不能当作独立样本或背书，但“同一热点出现大量 CA 分叉”是真实结构。

在按 `status_id` 去重的 106 个帖子中，65 个没有任何 browser-watch Observation，37 个是 Token 链接先到、浏览器正文后到，只有 4 个 browser Observation 不晚于首个 Token 链接。当前 v3 只从触发正文抽显式 CA，3 个自然 cohort 全部为 `no_seed_at_signal`；进一步逐 cohort 核验又表明这 3 个 v3 帖子在信号时 provider-linked Token 数也都是 0。因此，新 shadow 不是“修复 v3 的漏 seed”，而是另一个 Token-first estimand：项目 metadata 引用重点帖子时形成的 CA 歧义与蹭热点风险。两者必须并行、不得合并分母。

仅用于设计、不进入未来新版本分母的严格回顾统计还表明：以首个不可变 exposure-link 为 `T0`，最终 180 分钟 episode 集合在 `T0/30s/60s/120s/300s` 已完整的比例约为 `35.9%/53.4%/64.1%/68.0%/73.8%`。529 个 membership 中只有 16 个在自身链接到达时已有本地快照，只有 3 个同时有完整价格和流动性；约 521 个到 5 分钟才出现首个快照。固定多时点集合轨迹比“首个链接即完整集合”更诚实，也证明 DexScreener `liquidity_usd` 不能替代 Pump/Jupiter 的真实可路由性证据。

因此当前主断点是：

`及时信息/精确原帖 → 新鲜独立事实 → Token 候选集合 → exact CA/canonical → 可执行 Decision → 扣费 Paper 结果`

它不是新币供给不足，也不能仅靠提高轮询、扩大账号表、增加生产 Agent 或降低门槛解决。

## 3. 冻结的不变量

- 严禁未来数据、未来函数、旧赢家回填和后来证据倒灌。
- 每个研究版本必须有 activation point、不可变分母、固定目标时点和 missing/error/zero-yield 终态。
- identity、promotion、项目自述、单源 KOL 帖子不能直接成为交易证据。
- WAIT 必须如实显示，不美化成信号。
- Paper 使用当时可得报价、next-observed/trigger-anchored 执行、滑点和费用；Paper 结果不能称真实利润。
- 当前 Live 保持锁定；网页、插件和 Agent 均不得解锁。
- 生产 autonomous-search 并发保持最多 2；是否增加只能由前向排队和有效产出证据支持。
- 所有项目持久数据保存在 `E:\memeTrader`；不清空或改写 r6，不推送 Git。
- UI 深化后置；只有数据缺失、误导或操作不可用时才优先修 UI。
- ChatGPT 高智能协同当前始终使用用户最新指定的 `@笔记本量化MCP-官方隧道`；它是本项目唯一权威本地连接面，除非用户以后明确 supersede。关键架构、策略和实验在确属 material gate 时默认使用一条有实质内容的最高强度 Lead 复核；只有结论冲突、信息不完整或影响特别重大时才增加独立会话，普通局部实现/验证不得机械复制多审。ChatGPT 负责研究、反证、方案比较与综合，Codex 验证当前事实、实现和测试。

## 4. 当前执行优先级

### P0：修复信息到证据的真实转化

1. 继续验证 priority request → browser observation → Event → Agent dispatch 的自然前向链。
2. 统计精确原帖的新鲜捕获率、独立 confirmation 产出率、exact CA/canonical 成功率和端到端延迟。
3. 区分 `no_context`、来源不可达、查询 zero-yield、冷却未准入、同名歧义、Token 未发现和安全/执行拒绝。
4. 不用调用量或轮询轮次冒充有效产出。

### P0 实验候选：重点人物低注意力 Token 探针

三条 ChatGPT 独立复核已完成。原始“ticker/叙事词 → Dex 候选 → 事后涨幅”方案为 `NO-GO`。旧 v1 的一个自然 cohort 原样保留；base v2 因读取可变 `events.attention`，在首个 cohort 前明确废弃。当前基线是 `kol-token-addressability-lag/v3-immutable-attention`：只从 exact `(event_id, observation_id)` 的不可变 attention point 冻结注意力定义、数值与记录时间。旧 route v1 与 v3 不兼容并在首个 attempt 前停用；当前 `kol-token-addressability-route/v2-compatible-deadline-edf` 已绑定 v3 version/hash 严格前向注册，区分 pair/request/response 时序与 surface 关系，并纳入共享后台 Jupiter 请求预算。所有记录仍为 `decision_eligible=0 / affects=none`，不能证明盈利、成交、背书或安全。

2026-09-02 新发现的多 CA 分叉不能修改或重解释上述 v3。当前只进入候选设计审查：若三路独立复核支持，则另建 append-only shadow 版本，以“本机首个精确帖子链接可见时点”为入口，保存当时可见集合及固定延迟检查点的完整 CA 集合、克隆分叉、route/容量/成本和 15/60/240 终态；不选择赢家、不回填、不接 Strategy/Paper/Live。若污染、分母或经济价值无法成立，则保持 v3，不为增加样本创造新实验。

### P1：形成可审计主 Paper 样本

只有现有证据门、canonical margin、安全和真实报价均通过时才产生主 Paper；持续记录 BUY/SELL、滑点、费用、部分退出、stop、trailing、narrative decay、runner 与资金占用。交易少时先归因断点，不为增加数量降低门槛。

### P2：前向学习与 challenger

按来源、人物、信息类型、链、触发路径和策略 cohort 比较 15/60/240 分钟及完整持仓结果。至少跨多日期、含正负样本、扣费后且尾部可接受，才预注册一个最小 challenger；保持基线/探索隔离，不逐笔自我改写。

当前 Portfolio 的产品模型冻结为**三个模拟账户、两种入场逻辑**：

1. `策略 1｜信息 + Token`：新闻、热点、人物、社区与 Token 数据共同决定独立入场；
2. `策略 2｜纯链上基线`：只用 Token 链上/市场数据入场，当前 Solana 以特定金额 Jupiter 最低输出作为成交语义；
3. `策略 3｜同入场·买后叙事增强持有`：精确复制策略 2 激活后的新 BUY（同 Token、时点、金额、数量和成本），只研究买后已观察到的叙事是否值得延长 runner。

策略 3 不是第三个选币器，也不能把现有动态止损实验改名充数。正面叙事不得覆盖安全、流动性、硬止损、移动止盈、最长持有和不可交易终态；所有买卖均须扣除当时可得的滑点、路由/平台费和链费。策略 2/3 只使用策略 3 激活后的 exact paired cohort 比较，旧赢家不回填。

策略 3 的第一阶段已进入生产前向采样：`onchain-paper-narrative-context/v1-forward-only` 只对 context registration 后的新 exact pair 发起一次买后 Token Context 研究。当前研究结果只进入 assessment/audit，不进入主 Event/Decision，也不改变仓位或退出；Seed 后未形成 admission 的中断可用同一 transition 恢复。生产注册点为 Strategy 2 BUY `133`，现有 8 个 Strategy 3 仓位全部作为 `pre_registration_not_backfilled` 排除，等待下一笔自然新 BUY 才形成第一个有效样本。

持续学习采用 append-only、point-in-time、版本化 baseline/challenger：阈值、信息源权重、人物/社区/热点量化和持有规则可以持续研究，但只能在预注册成熟门后发布新版本；不得让在线结果逐笔自改当前基线。

### 当前执行周期：P0-E 多链指定金额执行真实性

当前最高影响断点不是 Token 数量、Agent 数量或 UI，而是 Solana 之外“发现到 Token”无法转换成时点有效、指定金额、可买且可卖、成本完整的执行证据。第一阶段已部署 BSC/Base/Robinhood Chain 的固定区块 Uniswap V3 双向 Quoter 观察层；它只回答 pool math 是否存在，不回答完整交易是否可执行或盈利。

下一步顺序冻结为：

1. 等待第一个 activation cohort `2112` 之后的自然 EVM cohort，验证 attempt/result、错误分类、固定区块和无回填；没有自然样本时保持 0，不手工塞赢家。
2. 为各链补充同区块 gas price、L1 data fee（适用时）、Router 交易模拟、allowance/transfer-tax/blacklist 与指定数量卖出能力；仍先进入 research-only challenger。
3. 只有完整往返成本和失败语义跨日期积累后，才讨论将 BSC/Base/Robinhood 任一链加入 Paper；主 Paper 当前仍仅允许 Solana amount-specific Jupiter 路径。
4. 策略 3 继续与策略 2 exact-paired：买后信息只研究延长持有，不覆盖安全、流动性、硬止损或不可卖状态。当前 runner 继续禁用。
5. UI 仅维持真实、可读和动态；后续视觉深化不抢占执行真实性和 Event↔Token 转化率主线。

### P3：后置事项

- 深化 UI 设计与长期固定公网域名；
- 更广平台登录或 Telegram 自动摄取；
- 通用按证据复杂度动态升级模型；
- Devnet/小额 Mainnet broker、签名、广播、确认和对账。

这些事项保留在累积需求中，但不能抢占 P0/P1。Telegram 自动正文摄取、自动注册/绕 MFA、读取凭据、社交互动自动化仍受平台与安全边界限制。

## 5. 下一可执行步骤

1. 已部署 `kol-token-addressability-lag/v3-immutable-attention`：activation Observation `6499`，registration hash `f90c852666b1cf7d3d29df0b89474d0d346dad432e704c3ca746cf124917b3b4`。Runtime 以不可变 registration JSON 和 exact attention point 为准，严格 attention `<35`，本地可见时间使用 durable snapshot `recorded_at`，裸 EVM CA 保留为显式跨链歧义；主分母保留 no-seed，且固定 `decision_eligible=0 / affects=none`。
2. v1 历史 cohort 原样保留；base v2 标记为 `registered_abandoned_before_first_cohort`；route v1 标记为 `registered_abandoned_before_first_attempt`。route v2 于 `2026-09-02T06:23:40.203809Z` 注册，activation cohort `1`，definition hash `79ca058b7ae38bfccfbf260e19a5a5b315c3538ebb0127d59ff1b91d349d2c42`，compatible base hash 与 live v3 完全一致。
3. route v2 已实现并验证：registration/cohort hash、route-version 去重、canonical Solana 32-byte CA、完整 cohort→milestone→mint→pair→attempt→result lineage、pair/request/response timing、single-hop/multi-hop/unmapped、bounded unresolved refresh，以及后台 Jupiter 三请求共享 epoch 与逐请求释放生产 quote 锁。下一步只等待 v3 自然 cohort、route/confirmation 终态与端到端延迟；足够前向样本前不启动同 pair/surface 成本后 15/60/240 随访，不接 Strategy/Paper/Live。
4. 浏览器运行健康已拆为两个独立事实：8765 Bridge 服务是否可达，以及扩展采集器是否在 `source_stale_minutes.browser` 窗口内留下真实平台心跳。外部 Chrome 关闭后曾短暂保留新鲜心跳，但最终超过窗口并变为 stale，证明内置浏览器不能替代 unpacked Chrome 扩展常驻；要持续采集 X/KOL，仍须保持外部 Chrome 运行。priority request 现会排除已经存在 `local_receive + raw.browser` 精确 Observation 的帖子，避免已捕获页面反复占用轮换槽；继续追踪真正未捕获的精确原帖、confirmation、exact binding、Decision 与 Paper，不得回填注册前 Observation。
5. 首个新鲜 v3 候选输入是 Elon 在 `06:50:38Z` 对 Tunguz 旧帖的 repost，7 个新 Solana Token 同时引用 exact repost URL。扩展 v0.6.6 重载后已证实 actor/original-content lineage 与 repost Snowflake 时钟进入生产；源码随后升至 v0.6.7，把三个自动轮换页面压缩为两个页面以降低浏览器内存。Chrome 关闭时 X/KOL 精确正文采集会在 3 分钟后显示 stale，但 RSS、链上、Agent、Paper、Web 与 SQLite 不受影响。不得把 repost 冒充 Elon 原创或 endorsement。
6. Lead、交易经济性与因果统计三条最高强度独立复核均给出 `REVISE`，并形成一致边界：第一阶段只运行 local-only、append-only 的 provider-post ambiguity/fanout census，不发新网络请求、不挑赢家、不接 Strategy/Paper；若以后另行注册经济版本，每个帖子最多一个预注册候选和一份固定资本，主要研究 `fanout>=5` 是否应 abstain。Phase A 已从 exposure-link `451913` 之后注册，旧 103 个严格 episode 只作设计证据，绝不进入新实验分母。
   首个自然窗口已形成 2 个 episode、2 个 membership 和 9 个到期 checkpoint；两个帖子均先被浏览器捕获，随后才出现注册后的新 Token membership。记录保持 `decision_eligible=0 / affects=none`，证明前向账本运转，不证明经济价值。
7. 首个自然窗口还暴露出 hydration FIFO 吞吐断点：859 个已到期项中，两个 exact high-impact-post Token 前面分别有 436/491 项，等待约14–15分钟仍 `attempts=0`。调度现只把配置内重点账号的 exact social-post Token 提到 hydration 队首，不放宽触发、证据、Agent 冷却或交易门。部署后两者在首轮同时 hydrated 并形成 `high_impact_account_post` trigger；一个经 deferred retry admitted，Luna/low 使用 88,380 tokens 后返回 `no_context`，另一个继续等待全局冷却槽。没有生成 Decision/Paper，证明修复的是及时调查能力而不是强造信号。
8. 最新终态抽查又定位到 `exact browser Observation → deferred Token Context` 的正文交接损失：直接调查已携带本地正文，但延期重试只恢复 URL，且提示词要求二次访问 X，导致不可访问时否定已有本地精确内容。现按不可变 trigger transition 恢复原 `observation_id/observed_text/published_at/observed_at`，并明确本地正文只证明帖子内容，不构成背书、独立确认、社区扩散或 Token 绑定。三项定向测试通过并已部署；下一步等待新的自然 deferred retry，比较来源可达性与 independent-reporting yield，不能把“正文可用”直接升级为 Decision。
9. 最新120次 Token Context 中，99次携带帖子 URL 但仅47个不同 URL，首轮后重复52次，重复 URL 调用约消耗6.126M tokens；其中未核验 metadata 同等级重复43次、约5.220M tokens，是当前比预算更直接的调查覆盖损失。现已部署 source-fair 调度：X/Twitter 同帖 canonical 化，metadata 与 exact-browser 分开，exact 还绑定正文 fingerprint；每个 high-impact lane 先排不同且未调查的 source key，再排已调查的不同 source，最后才排同轮 clone。它不跳过或复制 Token assessment，不改变每轮上限、冷却、证据门或交易；下一步以新自然轮次比较首个 admitted 的 distinct-source 比例、重复 URL 间隔和独立来源 yield。
10. 用户于 2026-09-02 明确补充 `Solana + BSC + Base + Robinhood Chain` 多链需求，因此旧的“发现层仅 Solana+BSC”结论已被部分 supersede。GeckoTerminal 新池与 DexScreener pair/social hydration 范围现扩为四链；高写入量的全局 Profile/Takeover/Ads/Boost 面仍只覆盖正式候选链，以避免大库事件循环饥饿。正式 `candidate.chains` 暂保持 `Solana+BSC`。Base/Robinhood 只保存新池、Token、快照、来源链接和 `research_only` 漏斗，不派发 Agent、不写 Decision/Paper。只有建立各链 amount-specific router quote、协议费、动态 gas/L1 data fee、安全报告与失败语义后，才可另行前向升级为候选链；不得把 Solana 的 Jupiter/固定费用假设复制过去。
11. 新自然窗口确认 source-fair 只能在存在其他帖子时改善排序，不能消除同帖多 Token 的完整重复调查：同一 Solana 帖子被6个 Token分别调查，合计404,124 tokens，全部 `no_context`。当前关键设计候选是把帖子/事件事实与 Token 名称/CA 绑定分开；帖子级不可变事实可在同一证据版本内复用，Token 绑定、独立确认、exact CA、安全、报价和交易资格绝不跨 Token 复制。该方案必须先通过三条高强度独立复核，并以 append-only、available-at、证据升级/纠错版本和负结果有限刷新为边界；在复核完成前不改 Runtime。
12. 样本未成熟时保持基线，不以单笔赢家、单日亏盈或空结果改变 Strategy。
13. source-fact/token-binding 三路最高强度复核已完成，结论一致为 `REVISE`：过去 24 小时双 Agent 槽同时繁忙仅约 1.3%，队列 p95 约 0.001 秒，增加并发不是当前解法。现已部署 `source-fact-single-flight/v1`：同一 canonical URL、证据等级与 exact content revision 只调查一次；每个 Token 仍独立重算 exact CA binding、assessment 与证据角色，不复制安全、报价、Decision、仓位或交易资格。首个自然事实被 4 个 Token 复用，3 个 follower 均为 0 tokens；随后按真实前向数据把 `no_context` 复用窗口调整为从完成时刻起 30 分钟、reused Token 写入正常冷却，并允许被 Runtime 重启中断的只读调查在租约加既有 10 分钟错误退避后追加重试。真实 attempt `11` 已证明永久饥饿解除，result `10` 证明 30 分钟完成时锚点生效。下一步只观察 distinct-source 覆盖、decision-evidence yield 与相同 source revision 的实际 Agent 节省，不通过增加 Agent 数量掩盖绑定和证据问题。
14. 链上探索 Shadow 与主 Paper 继续分账但统一展示：Shadow 是更宽候选集合的反事实研究，主 Paper 是当前策略通过后的模拟组合，二者准入与成交假设不同，直接混账会污染归因。Portfolio 已补充 Shadow 现金曲线、成交/胜负、胜率、平均/中位已平仓 PNL、最大现金回撤、网络费估计与未定价仓位的零回收下界；所有值明确标为 simulated。止损/追踪/止盈应由本地市场数据触发并以实际 amount-specific SELL quote 结算，Agent 不负责数值行情或卖出判断。
15. `onchain-paper-exit-challenger/v1` 已从固定 Shadow 的 exploration BUY trade `99` 之后严格前向注册。它与固定 15/60/240 分钟基线共享后续新入场、但独立记录退出：DexScreener 15 秒标记只产生意图，下一笔特定剩余数量的 Jupiter 最小输出才结算；`no_route` 不假装止损成功，240 分钟仍无路线才 write-off。默认规则冻结为 hard stop `-35%`、trailing `+60%/-28%`、流动性紧急 `$3000`、5 分钟零活跃、`+80/+180/+350/+700%` 分批退出和 240 分钟上限。Portfolio 已显示动态 cash/equity/realized/unrealized/total PNL 曲线；当前尚无注册后的自然成对入场，保持 `$1000` 空账本，不回填旧仓位。下一步只等待自然 paired sample，比对相同入场下固定周期与动态退出的扣费 PNL、route failure、回撤和尾部，不按单笔结果改规则。
16. Token 详情里的普通 X status 已接入现有单页 priority 采集，不再要求它先属于人工 watch account。新精确 Observation 会 append-only 关联所有当时已引用该帖的 Solana/BSC Token 并优先重做 hydration；普通 Context lane 又已修正为精确本地原文优先于未核验 provider metadata。首个修复后自然样本已完成 `exact post → admission → Agent → no_context`，没有制造 Decision 或交易。新的13-Token自然 handoff 又证明只选择1个普通候选会在 hydration 后静默丢失其余样本，因此已增设每轮最多4个的 source-fair exact-browser lane，超过上限者持久重排；不增加Agent并发或放宽任何门。自然验证中 owner admission `9490` 使用 `62,851` tokens，follower admission `9491` 以 `source_fact_reused` 独立形成 `0-token` assessment，超限精确 Token 保持 pending，证明 bounded lane 与同源复用均已进入真实前向流量。下一步统计这些 exact-post 样本的独立来源产出率、Token exact-binding 率、端到端延迟及 Decision/Paper 转化；只有其中一层出现证据支持的损失时才调整该层，不通过增加 Agent、降低门槛或回填赢家追求更多 Paper 成交。
17. 外部 Chrome 继续作为 X 精确采集载体，但内存治理只针对真实异常 renderer：本轮单 renderer 曾升至约 `3.68 GB`，精确终止后采集自动恢复且登录/扩展未丢失。Web health 现以 heartbeat 或最新真实 browser Observation 判断 collector 活性，避免 Bridge 忙时误报 stale。该运维事项服务于信息召回，不改变策略、Agent 数量、证据门或交易门；后续只有再次出现单进程异常增长或采集停滞时才介入，避免把浏览器维护变成主线。
18. 新 Decision `2948` 将下一断点收敛到 canonical identity：两个同名新币几乎并列，只有一个在决策前直接链接 Event 内精确帖子。严格24小时 as-of 诊断共找到5个类似多候选 Decision，但另一个 Event 同时有5个 Token 链接同一帖子，说明 exact source link 只能证明 identity set，不能总能选出唯一 Token。未来 `WAIT` 已改为同时披露低分与 canonical ambiguity；生产评分保持不变。下一步按 `CHATGPT_REVIEW_HANDOFF_EXACT_SOURCE_LINK_CANONICAL_IDENTITY_2026-09-02.md` 完成架构、因果和交易经济性三路独立复核，再决定是否注册一个只读 append-only identity-set Shadow；复核前不以 metadata identity 提升交易资格。
19. Information-first Shadow 的被动采样缺口已通过独立、严格前向的 `information-first-active-outcome-sampler/v1` 处理。版本于 `2026-09-02T14:46:49Z` 注册，activation shadow cohort `104`；只为之后新 cohort 建立15/60/240分钟目标，在目标 `+0/+30/+120/+300s` 主动请求 DexScreener，并于5分钟硬截止记录 observed mark、no pair、限流、HTTP/timeout/protocol error 或 scheduler-missed terminal。它不写通用快照、不调用 Agent、不使用 Jupiter、不接 Strategy/Paper/Live，所有记录固定 `decision_eligible=0 / affects=none`。部署时最大 cohort 仍为104，所以当前目标与结果为空；下一步等待自然新 cohort，检查各 horizon 的覆盖率、错误构成和延迟，不手工制造样本。
20. X 文章《2026年，Meme链上还有机会吗？》已按原文读取。其“娱乐/抽象、冲突/反叛、情绪共鸣、天然流量、社区传播”等叙事观察只进入可检验的研究词表，不直接加分或买入；文章同时含 GMGN/FOMO 推广链接和 KOL 经验，必须与项目方 promotion、独立事实、实际传播加速度、Token fanout/canonical 歧义和扣费结果分离。后续按链比较叙事类别、首次可见时间、跨平台扩散、克隆数、流动性/买卖广度和15/60/240分钟结果，保留所有空结果与亏损样本。
21. `C2C-20260903-MEMETRADER-SYSTEM-RESEARCH-IMPL-001` 已成为当前有序实施主线，完整研究见 `CHATGPT_MEMETRADER_SYSTEM_RESEARCH_2026-09-03.md`，执行合同见 `CHATGPT_CODEX_IMPLEMENTATION_HANDOFF_MEMETRADER_SYSTEM_RESEARCH_2026-09-03.md`。P0-A 已完成代码与定向测试：active outcome 的最多 4 个 DexScreener 请求改为同周期有界并发，每个请求最多 15 秒且绝不越过冻结 deadline；到截止时先写 `terminal_missing`，随后迟到结果只能 append `late_response`，不得覆盖 terminal。当前 r6 为 27 targets / 13 attempts / 13 results / 15 terminals，历史 4 个 `scheduler_missed_deadline` 原样保留。下一阶段按 P0-B/C 实施 immutable launch facts 与 market-surface classifier，均从新 activation 起 `decision_eligible=0 / affects=none`，不改变 Strategy/Paper/Live。
22. P0-B/C 已前向上线：Pump WebSocket receipt clock 与 immutable launch facts 不再被 hydration 覆盖；market-surface v2 只描述具体 pair，并将 bonding curve 与 AMM 分开。PumpSwap canonical 在缺少真实 pair-account IDL/RPC 证明时保持 unknown。P0-D 当前正式版本为 `liquidity-survival-shadow/v3-version-isolated`；v1 partial 与 v2 contaminated 均原样冻结并排除。v3 固定 exact pair、$12k baseline、1/5/15/60m 与 missing/error 终态，只做 Shadow，不影响 Strategy/Paper/Live。当前自然截面已有 384 cohorts、1,085 attempts、1,200 outcomes，调度/索引工程门已经跨过；继续增加同类基础设施不再是主线，下一工程断点转为 P0-E amount-specific execution。
23. Paper 真值边界已经收紧：开放纯链上仓位只有 DexScreener 价格时，只显示受容量限制的 `indicative` 参考值；没有特定剩余数量的有效卖出报价时，账户 `equity/unrealized/total PNL` 保持未知，不再把零/未知流动性的表面涨幅算成可实现 PNL。Portfolio 的纯链上说明也改为真实准入语义：当前是冻结的 on-chain momentum cohort + 时点有效 Jupiter 指定金额买入报价；流动性、成交、买卖结构与安全字段尚未全部成为硬门。两项定向测试通过。
24. Robinhood Chain 已作为第四条独立研究链纳入，而不是 BSC/Base 的别名。官方事实为 chain id `4663`、Arbitrum L2、ETH gas；GeckoTerminal network id=`robinhood` 已验证，0x 已支持该链的 Swap/Cross-chain route。本机最近 24 小时已采集约 9,942 个 Robinhood Token，说明它不是空规划。但 Robinhood 官方 `/rhj/assets` 当前 194 个 Stock Token 合约中已有 103 个出现在本机 Robinhood Token 总表，证明必须先做 Meme 与 Stock Token/RWA 的官方地址级分类。当前继续保持 `research_only`：只收新池/Token/快照/来源，不派 Agent、不写 Decision/Paper；先建立 append-only `stock_token/rwa_excluded` 分类，再做 0x amount-specific Shadow、动态 L2/L1 费用与安全成熟门。
25. P0-E 第一阶段已实现 `event-route-execution-challenger/v1-entry-preflight`。它只接收注册后新的 route-backed WAIT：固定最大仓位 probe 继续只证明容量，最终 policy size 再冻结为 USDC raw amount，随后新发 exact-size BUY，并以 BUY minimum token output 做即时 SELL preflight。每个 attempt 保存两腿最低输出、时钟、route-only cost、费用完整性及失败终态；当前一律 `no_fill_research_only / affects=none`，不写旧 `paper_account/positions/trades`。Quote-only 网络费字段或同时点 SOL/USD 转换不完整时明确 `cost_unknown`，不会叠加旧 4%/125bps 假装精确成本。下一阶段只在出现自然前向 attempt 后补独立 remaining-raw position/SELL ledger；成熟前保持主 Paper WAIT 与 Live 锁定。
26. 策略 3 已从 exploration BUY trade `123` 后严格激活；首个核验截面为 4 个新 BUY / 4 个 exact pair，浏览器 QA 截面已自然增长为 7 / 7，始终为 0 mismatch、0 backfill。Token、时间、金额、raw 数量、入口网络费与源 quote result 全部一致。叙事 runner 仍为 0，状态明确为 `not_mature_not_enabled`，因此当前只证明公平同入场账本运转，不证明买后叙事能改善收益。退出报价又发现一项真实语义错误：Jupiter Swap V2 官方用 HTTP 400 `Failed to get quotes` 表示无法找到报价，旧客户端误记为 `JupiterQuoteError`。修复后首个自然结果 `410` 已变为 `no_route`；历史错误行不改写，无法成交仍不生成 SELL 或 PNL。
27. 策略 3 买后调查 v1 已形成 11 个不可变 seed（7 coverage gap / 4 triggered），并证明首次 60 秒无刷新快照就永久终结会制造系统性覆盖损失。v2 从策略 2 BUY `155` 后重新注册：优先使用买后刷新快照，否则使用入场前已完整入库且与 exact cohort 一致的 trigger snapshot 启动调查；调查时钟仍晚于入场。延期重试只服务仍开放的 exact-paired 仓位，并排在精确原帖/新鲜高热 Event 后、批量 metadata 前。旧 v1 不回填，runner、Decision/Paper/Live 均不改变。同期 active outcome v1 的真实已终态缺失率为 9/153（5.88%）；v2 将最后重试从硬截止 `+300s` 提前至 `+240s`，保持 300 秒右闭 deadline。下一步只等待 v2 的自然 paired entry、snapshot basis、admission/assessment 与策略 2/3 同入场扣费退出结果，不用增加 Agent 或降低门槛制造样本。
28. 启动者历史研究已按 P1-B 的最小前向切片上线。`creator-launch-risk-shadow/v1-local-history-lower-bound` 只为 activation launch fact `10533` 之后的新 Solana Pump create 建 cohort；每次冻结当时已入库的同地址历史发币数、24 小时发币数、距上次发币时间、既有 240 分钟链上结果与 60 分钟流动性存活结果。它明确是 PumpPortal provider observation，不是 RPC 验证，不做多地址实体聚类，历史为本机记录下界。首个自然截面 68 个合格新 create 全部入组，其中 46 个地址已有本机先前发币、27 个先前发币数不少于 10；这些只是待检验暴露，绝不自动解释为恶意、风险分或交易拒绝。Token 详情已折叠显示该证据；Decision/Paper/Live 完全不变。下一步等待结果成熟后按预先冻结的频率桶比较，而不是立即按创建者次数改交易。
29. Strategy 3 延期调查的共享重试槽已修复真实假饥饿：`reused/source_fact_reused` 现在终止 exact intent，仍在有效期内的 `token_cooldown_active` 按 Token-wide 语义阻止同一 Token 的全部延期 intent 再占槽；全局/错误冷却继续按 exact lineage，优先分数、4 分钟周期、最多 2 个 Agent、预算和交易门均未改变。部署后首轮自然 active retry 已成功 admission 一条 post-entry intent 并生成 `no_context` assessment，证明调度恢复但不证明叙事 alpha。当前 v2 的 3 个开放 seed 仍待自然处理；在 assessment 与 paired executable exits 成熟前，策略 3 继续 `decision_eligible=0 / affects=none`，runner 不启用。
30. 对上一条自然结果完成版本归属复核后，确认其属于旧 context v1，不能代表 current v2。已将 post-entry active retry 严格限定为当前 context version + exact seed/transition/source BUY/open paired position；旧版本保留审计但不再抢槽。退出监控从 `opened_at` 固定队首改为未标记优先、随后按最旧 mark 公平轮换；退出报价也改为未尝试 pending mark 优先、随后按最旧尝试轮换，修复同一失败仓 16 次重试而多个待退出仓 0 次的垄断。部署后 cohorts `2130/2137/2138/2139` 已全部得到首个 mark，原 0-attempt 的 `2110/2112/2113/2117` 已获得首个真实卖出尝试，current-v2 seed `12` 已产生 assessment `1044/no_context`。这恢复了当前版本的价格/叙事/执行观察分母，但没有启用 runner，也没有证明 alpha；下一步继续收集另外两个 v2 assessment、Strategy3 amount-specific exits 和费用完整性，再冻结可检验的叙事处理规则。
31. 当前执行范围按用户最新决定收敛为 Solana-only；BSC/Base/Robinhood 的既有只读研究账本保留但暂停进入新发现、Agent、Decision、Paper 与 PNL。三种 Paper 策略已从 `fair-comparison/2026-09-03-20usdc-v2` 公平重启，统一采用 `$20` 入场、BUY/SELL 各 `4%` 不利滑点、每次实际成交固定 `$0.40`。链上策略使用新的不可变 v2/v4 版本链，旧版本不回写；主信息策略的新成交使用相同成本，但仍需补独立 machine-readable policy version。近期主线是收集该成本版本的 Solana 前向样本与可执行退出，不扩张多链。

32. 2026-09-03 最新执行目标再次 supersede 第 31 条的长期链范围：当前产品模型固定为三个策略家族 `information_plus_token`、`token_only`、`token_then_information`，买入金额、加仓、止损、止盈、runner 与退出均是各家族内部可版本化 policy arm，不是额外策略。后端 `/api/portfolio.strategy_model` 已提供 `three-strategy-families-policy-arms/v1` 机器可读契约，列出 signal/entry/sizing/exit/cost/chain-execution 版本、research state、decision eligibility 与 affects。Strategy 3 的新 `v3-fixed-baseline` 控制臂精确复制 Strategy 2 的买入及固定 15/60/240 分钟退出，买后信息 `affects=none`；旧 dynamic-exit 对照数据保持不改写。近期真实执行仍先修复并收集 Solana Jupiter amount-specific 前向样本；BSC 与 Robinhood 是下一批必须实现完整路由/成本/安全语义的链，Base 历史研究数据保留但不阻塞。Live 始终锁定。

## 6. 完成判定

本长期目标不能因网站可用、代码测试通过或出现少量 Paper 成交而关闭。至少需要：

- 关键采集与证据链在真实前向数据中稳定运行；
- 能解释机会召回、误报和漏检，而非只统计成功样本；
- 主 Paper 获得跨日期、包含亏损、扣费后的足够样本；
- 收益、回撤、尾部、集中度和执行可行性达到预注册成熟门；
- challenger 在严格前向样本中相对基线有可复核改善；
- 仍保持无未来数据、无回填、Live 锁和完整审计。

在这些条件满足前，状态保持 `ACTIVE / CONTINUOUS`。

## 2026-09-03 动态退出与多链执行增量

用户进一步明确：每个策略家族都必须具有动态退出，固定周期只能作为可比较基线或因果控制。机器可读契约已据此固化：策略 1 当前 `deterministic-paper-exit/v1` 为动态退出；策略 2 的 15/60/240 分钟臂标为 `fixed_comparison_baseline`，与现有动态止损/移动止盈/分批止盈/流动性退出 challenger 并存；策略 3 当前固定臂只用于隔离买后信息增量，未来动态 information treatment 必须另行预注册、前向激活，成熟前不得假装已经启用。

首个当前 v2 自然 Solana cohort 已形成 Strategy 2/3 精确配对的 `$20` BUY，并在 15 分钟取得金额特定 Jupiter SELL；两账本均以 `-$0.51209` 扣费 Paper 结果闭合。0x Swap v2 金额特定 `/price` 观测客户端及 append-only Store/Runtime/Web overlay 已实现、测试并部署；只有本机环境凭据存在时才从当时 activation 开始观测，当前凭据不存在所以生产明确为 `not_registered`，不会回填或伪造结果。该层仍为 indicative、`affects=none`；没有 firm `/quote`、taker、完整安全与成本证据前，BSC/Robinhood 不得进入 Paper。

双向协作从本周期起统一使用 `GXH_C2C_V3`。消息工具返回 success 只记 `SEND_ACCEPTED`，目标线程回读相同 ID 才记 `DELIVERED`，显式 ACK 后才记 `ACKNOWLEDGED`，验收完成需要 RESULT 与结果确认。详细研究留 Common Space，Codex等待 Lead 时继续不冲突 tranche；协作在根因明确、实现完成、最小测试通过、前向观察启动后停止无新增证据的循环。

### 2026-09-03 P0-A S1 检索转化效率

`exact-source-link-identity-and-unchanged-wait/v1` 已部署。当前 Event 的精确 public-item URL 只使用决策时已存在的 Token exposure/source-link 建立有界 identity set，不增加分数、不充当独立证据；同帖多币继续显式 fanout 和 canonical ambiguity。对 `no_matching_token`，证据、identity 和本地候选集合未变化时复用既有宽检索结果，最长 300 秒后强制重跑；任何新 Observation、identity membership 或本地 overlap Token 会提前失效。阈值、风控、交易与 Agent 并发未改。下一主线转入 P0-B：严格前向的 Token-first WATCH → 有界入场前信息确认；P0-A 同时等待自然转化数据。
### Active next tranche — preserve S3 authority and measure the WATCH observer

The new Solana Token-first 120-second WATCH and deterministic confirmation classifier are deployed forward-only as a separate research observer. The user's later, more specific Strategy-3 definition remains authoritative: exact Strategy-2 entry followed by post-entry information research and, only after preregistered evidence matures, a dynamic holding/exit treatment. The WATCH therefore remains `entry_enabled=false / decision_eligible=false / affects=none`; it must not create another Paper cash ledger or be relabeled as product Strategy 3. Next measure natural WATCH coverage/terminal yield alongside S1 exact-link conversion, while continuing the existing Strategy-2/3 exact-paired, amount-specific exit evidence. A future confirm-before-entry challenger requires a distinct preregistered research version and explicit promotion decision.

### 2026-09-03 10:07 UTC current execution delta

- The coordination guard, Runtime→Store startability and Strategy-2 Jupiter-v2 dispatch are verified by current code, targeted tests and natural forward attempts. The old zero-attempt snapshot is obsolete.
- Strategy 3 v3 is now a clean causal control: r6 contains five exact-paired BUYs and one SELL matching Strategy 2 in time, amount, modeled fee and cash flow. Post-entry information remains observational and no narrative treatment is preregistered.
- Every concrete Paper policy arm now exposes machine-readable family/signal/entry/sizing/exit/cost/execution/activation/role/promotion fields.
- Current implementation priority is BSC and Robinhood amount-specific firm routing, sellability/safety and chain-specific cost semantics. Base code/history stays research-only and does not block these chains; Solana continues collecting the current forward cohort.

### 2026-09-03 10:26 UTC user supersession — rug safety / realtime mechanical exit / UI

The user explicitly elevated sudden liquidity withdrawal / unsellable-rug defense, adaptive post-BUY monitoring, BUY-funnel bottleneck correction and UI/live-equity simplification above the prior next implementation tranche. Current P0 is therefore: **(A)** venue-aware pretrade pool-custody/rug safety and exact-size sellability, **(B)** adaptive Agent-free held-token/pool monitoring with immediate amount-specific emergency SELL and a new dead-pool retry scheduler version, **(C)** Strategy-1 exact-size Jupiter BUY/SELL execution parity including the existing exact-identity route-addressability seam, and **(D)** an incremental Live Cockpit UI that separates executable from indicative equity. BSC/Robinhood remain required multi-chain work but must not displace this Solana safety/execution P0.

This supersession does **not** authorize looser safety gates or online parameter chasing. Current-v4 dynamic-exit rules remain frozen while paired forward samples accumulate; the natural 2179/2194 outcomes are evidence to continue studying dynamic exits, not permission to retune them. Any BUY-threshold widening comes only after rug/execution semantics are complete, one variable at a time in a preregistered Shadow challenger. Live remains locked.

Detailed research and ordered implementation contract: `docs/PROJECT_CONTEXT/CHATGPT_RUG_SAFETY_REALTIME_EXIT_UI_RESEARCH_2026-09-03.md` and `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-102646-CHATGPT-RUG-SAFETY-REALTIME-EXIT-UI-P0.md`.

### 2026-09-03 11:58 UTC user supersession — one on-chain primary, confirmed rug never recovers

Finite engineering and runtime resources are now concentrated on one active development and Paper-promotion path: **Solana canonical Pump.fun → PumpSwap, pure on-chain momentum, RPC-verified pool custody/LP burn, exact `$20` Jupiter BUY→immediate exact-size SELL preflight, and deterministic dynamic exit**. The existing Raydium CPMM decoder is preserved as Research evidence, but AMM-v4/CLMM/Orca/Meteora and BSC/Base/Robinhood expansion pause for this focus cycle. S1/S3 historical ledgers and passive information collectors remain, while high-cost Trend/Source/Token-Context/Verifier/WATCH/post-entry narrative Agent dispatch and new non-primary Paper promotion pause at a forward focus frontier.

A confirmed on-chain liquidity withdrawal/rug is now terminal. It may receive at most one immediate full-remaining-size emergency SELL attempt; absent an economic route, the position is written off and the exact mint/pool/policy lineage is permanently non-rearmable and non-reenterable for that version. A provider timeout, one Jupiter no-route, or a DexScreener zero alone is not sufficient to classify a rug; transient failures retain capped backoff. Scheduler v1 recovery semantics must therefore be superseded by a new terminal-aware version.

The primary entry version must also fix the current preflight weakness: `net_recovery_usd > 0` cannot admit a `$20` trade that can immediately recover only pennies. It must reuse a preregistered round-trip cost floor derived from Jupiter minimum output, configured adverse slippage/applicable pool fee and entry/exit fixed costs. Current momentum threshold and dynamic TP/stop parameters remain frozen; fixed 15/60/240m remains the same-entry comparator. Capital, chain and venue expansion remain blocked until at least 100 closed primary positions across 15 dates, including losses/dead cases and top-winner-removal robustness.

Full strategic review: `docs/PROJECT_CONTEXT/CHATGPT_ONCHAIN_FIRST_STRATEGIC_CONVERGENCE_2026-09-03.md`. Urgent execution contract: `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-115826-CHATGPT-ONCHAIN-FIRST-PRIMARY-P0.md`.

### 2026-09-03 12:00 UTC incremental correctness — holding surface != execution route

The on-chain-primary focus remains unchanged, but pretrade safety must explicitly separate **Holding Surface Safety** from **Execution Route Truth**. A read-only sample of the latest 100 quoted baseline BUY rows found the DexScreener snapshot pair absent from 31% of actual Jupiter route plans and multi-leg routing in 69%; therefore RPC custody proof for the selected PumpSwap holding surface must not be described as proof for every aggregator leg. Persist route-to-surface relation and route verifiability as a new forward-only evidence layer before any new primary version claims complete route/surface safety. Do not require the best Jupiter route to contain PumpSwap merely to preserve the focus; amount-specific minimum-output truth remains authoritative while opaque/unsupported route semantics are labeled honestly. Incremental execution directive: `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-120100-CHATGPT-ONCHAIN-CORE-REALLOCATION-P0.md`.

### 2026-09-03 12:31 UTC execution boundary — focus first, young pools, no penny recovery

The strategy-focus stop has not yet become a runtime fact: after `12:00Z`, r6 recorded 11 additional valid Token Context calls using 597,015 tokens plus one valid Trend fallback using 44,200 tokens, and no focus registration table exists. Before another engineering tranche, Codex must activate `strategy-focus/v1-solana-onchain-primary` and stop new high-cost information-model dispatch while leaving passive RSS/browser/PumpPortal/Dex/RPC/Jupiter collection intact.

Primary v1 is further bounded to exact on-chain Pump migration/pool age `<=600s`; current evidence shows 32/34 Solana high-momentum cohorts are PumpSwap, all eight current v4 Paper entries were approximately 2.0–8.5 minutes old, while several old-pool revival cohorts were about 6.8–7.5 hours old. Jupiter timing supports queue `<=5s` and completed preflight `<=10s`. The existing positive-penny sellability condition is replaced by transparent no-double-count ratios: quoted net immediate recovery `>=0.90` and stress minimum recovery `>=0.85`, after separate modeled network cost only. New primary capacity is capped at 5 open positions and `$100` daily new exposure; any pending ALERT/dead emergency exit blocks new entry. Detailed delta: `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-122440-CHATGPT-ONCHAIN-PRIMARY-AGE-COST-ADDENDUM.md`; immediate stop blocker: `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-123119-CHATGPT-FOCUS-STOP-NOT-ACTIVE.md`.
