# 深度优化151：三轮工程记录与证据边界

当前代码与项目：`H:\OpenTrader\memeTrader_2`。本文件优先于旧电脑 E: 路径及历史聊天建议。
最终运行回执：`deployment/postexit151_final.json`，PID19136于04:38:36.737368Z加载；04:40全部源码哈希匹配、旧合同/基础定义完全一致、Paper/Live=false。以下时间段数据分开，不以重启清零冒充改善。
任务边界：Paper only；Live=false；不重置账户、改写历史或覆盖已有策略。信息采集以现有 DexScreener 为主，不引入收费 API、精确路由/深度作为普通 Paper 新门槛。

## 第一轮：真实基线与根因

基线读取 2026-09-13 03:34–04:11 UTC；发布前进程 PID 34800、启动于 2026-09-12 23:42:16 UTC。共有 457 个有效定义（127 基础 + 330 追加）；238 个受既有退出/暂停控制，其余并非都具备当帧入场条件。账户独立1000U、普通20U/最多8仓为当前执行设置；部分策略描述保留旧1U/2U文字，不能用这些文字代替有效执行金额。

### 架构及统计口径

发现源 → canonical token/原池行情 → hydration与共享报价批次 → bounded trajectory特征 → alpha/其他族信号 → cohort与策略准入 → 普通Paper后帧成交/原生Paper协议模型 → 仓位与现金账本。

此系统不是一条所有策略共享的线性订单管道：普通Paper有共享源成交再向策略投影，原生Paper直接记协议模型仓位，`order_intents`并不覆盖所有普通Paper开仓。因此“有仓位但该表没有BUY intent”不自动是丢单。新的报告按定义版本+token+cohort关联，不把策略扇出当独立样本。

发现表缺原池/cohort外键，历史全链路池级分母不能可靠恢复。现有工具同时提供：①同token的发现→入库→基础评估；②同cohort的准入→源成交→投影仓位；③共享调度计数。它们不是同一个分母，不能连成虚假的100%漏斗。发现登记时间可能晚于某些已有快照，负时差单列；缓存/旧快照不算新采样。基础评估触达不等于所有策略完成判断。

| 三小时同Token样本 | 发现 | 有快照/基础评估 | 触达率 | 发现→基础评估 p50/p90/p99 秒 |
|---|---:|---:|---:|---|
| Solana | 3583 | 3083 | 86.0% | 133.53 / 312.22 / 329.57 |
| BSC | 1922 | 1835 | 95.5% | 6.85 / 18.80 / 304.64 |
| Robinhood | 1642 | 1475 | 89.8% | 0.59 / 2.51 / 159.57 |

另一个三小时统计中：8094个已评估Token仅62个出现策略准入记录（0.77%），3614次臂决策、2070个仓位只涉及49个Token。原因不能解释成“需要更多策略”或“开仓队列全部故障”。

### 按证据强度排序的瓶颈

1. **已证实不可得的特征阻断**：近两小时 `strategy-observer:dexscreener` 33716个快照、1083个token-pair键，`buyers_5m` 非空0；直接Dex快照8525条亦为0。依赖其派生买家增长/独立买家占比的两个participant臂实际不可达。“解析器存在”不是“API有数据”；已推翻第一次子审查的错误可达判断。
2. **连续有效行情不足**：运行内信号阶段计数中 `await_distinct_dex_trajectory_frame` 62497 / signal_received 84220；这些是臂×机会计数，不是独立Token拒绝率。Solana大量Pump创建事件先于Dex可报价池产生，no_pair与5分钟再尝试占较大等待，不能全归因CPU。
3. **已复现参考时钟竞态**：native退出在等待fee RPC期间，被并发刷新为晚于该quote的WSOL参考价格，引发 `native_reference_clock`。使用更精确数据并不能修复这个时序错误。
4. **已复现取消占用泄漏**：低优先级Dex请求取消没有释放shared lease，最多等45秒过期；不是永久丢失，但会占用连续采样机会。
5. **计算不是主要瓶颈**：基线特征p95约0.00075秒、入场batch p95约0.08秒、持仓拉取p50约0.47秒/p95约2.27秒，队列当时dropped=0。提高全局并发/全面提频没有容量依据，故未实施。
6. **仍需分别验证**：按链的cohort源成交差异，尤其Robinhood有admitted但缺源成交；限流/RPC/WS瞬时错误；历史退出后报价覆盖不足。不得以缺行情推定可安全交易或按当前价卖出。

`pattern_observation`、`cohort_observation`是观察路由标签，不计成真正拒绝；`no_spare`曾混合“批次满”和“没有到期候选”，第一次性能审查把它全当满批次，已用新计数拆分纠正。

## 第二轮：最小工程修复及前向运行

| 文件/变更 | 影响范围 | 测试与回滚 |
|---|---|---|
| runtime.py冻结native reference；quote/fee后复核因果和30秒有效期 | 只修原生Paper时序；过期等下一次新quote，不拿新参考给旧quote补价 | 并发刷新fee测试复现旧异常并验证修复；还原本次函数diff |
| runtime.py取消时释放SharedBatchCoverage claim | 取消正确传播、不生成数据/成交、不新增请求 | 实际取消Runtime请求测试；还原CancelledError分支 |
| shared_batch148.py允许现有Gecko正规回执仅作为额外候选seed | 只占已有Dex批次剩余地址位，返回仍须同原池Dex新行情 | 30地址批次、错池、失效/低活动、取消测试；移除新增allowlist值即退回 |
| shared_batch148.py计数拆分；runtime_timing.py补p90/p99 | bounded内存指标，不改策略阈值 | 缺样本仍null；8项timing测试 |
| forward_review151.py + scripts/deep_cycle_report.py / review_metrics151.py | 两小时报告、每天深入报告，低优先级单子进程，SQLite只读30秒budget，子进程120秒超时、取消回收 | 已实际运行两小时报告及日报；config.optimization151.review_enabled=false并重启可停 |

部署生效：**2026-09-13 04:11:56.161806 UTC / 北京12:11:56**，PID32988。所有manifest文件哈希与磁盘一致；旧策略JSON摘要及基础定义保持不变；新追加3个arm，总目录460。数据库和原资金期不变。

前向04:13左右：新增seed7、admitted5、精确新Dex回执12，额外候选复用已有批次。新计数把22次`no_due_candidate`从满批次中分开。该短窗口只能证明机制触达，不能证明全天延迟或盈利改善。前后流量、源构成、运行累计计数不同，禁止用重启清零计数声称错误率下降。

## 第三轮：可用数据替代与组合退出

新增arm（追加API、独立账户、真实部署frontier，旧臂不改）：

1. `alpha149_trade_activity_growth_proxy_v1`：母臂participant_growth；不可得的独立买家增长改为同池相邻快照滚动5分钟成交笔数增长>10%，成交额不下降；保留买笔占比≥55%、深度≥3000U/≥前帧98%。这是成交活跃度，不是新钱包数或净资金流。失败模式：自成交/刷量、滚动窗口边界、短暂活跃无后续趋势。
2. `alpha149_buy_pressure_no_breadth_v1`：母臂participant_breadth；仅去掉独立买家数/买笔数条件；保留买笔占比≥60%、深度≥3000U且不下降。不能识别捆绑或持仓集中度。该版本明确不再声称参与广度。
3. `alpha149_confirmed_recovery_decay_v1`：母臂moonbag_steady同入场；独立组合退出包。快照实际波动率保护（不是ATR）；持仓至少5分钟、15秒采样、最长90秒断档；价格、买笔占比、滚动笔数、USD流动性代理中至少3项衰减，连续两次不同原池新帧确认后触发最小净回本。下一真实可用模拟成交帧重新计算卖出raw；累计净回款足以覆盖成本才标记回本。保留母臂阶梯与runner机制，紧急/原有保护退出优先。该组合还改变硬保护宽度，**属于组合包对照，不是单变量归因**。

第三臂不会把API失败、无路由、数据缺失视为LP撤出或零价格。没有OHLC不用ATR；沒有社交/钱包不虚构聪明钱/社交衰减。母臂已有时间退出/独立安全退出保持，部分派生特征缺失不投负票，不阻断共有安全逻辑。

普通Paper仍使用当前4%买入、4%卖出、额外每笔0U的模拟成本设置（启动时生效的有效设置为准），不是保证真实可执行报价；原生Paper协议模型成本单独列示。新策略停止条件：身份/因果/会计回归立即停新入场；稳定性显著恶化回滚公共补丁；经济劣势需独立、成熟、共同时间窗样本后判断。不会自动调整旧参数或升级Live。

### 可核验的自然结果与未验证事项

04:13首次自然观察：buy_pressure替代臂5仓/5Token，trade_activity替代臂4仓/4Token，均非测试注入。证明缺失买家特征的替代路径可以开仓；尚无足够终局样本。组合退出已注册且12项纯函数/Store集成测试通过，但自然持仓和衰减退出样本需继续积累，不能称为“已经解决金狗拿不住”。

测试包含：原池/时间/缺失/重复/恢复重置、真实pending→下一帧SELL、raw数量守恒、净回款下界、下一帧不足回本不伪造principal_recovered、重启JSON恢复。发布组117项通过；新增定向组25项通过；固定窗口报告新增一项因果/错池测试亦通过。完整命令见部署回执与本文件末尾。

## 参数择优与少量对照

原有177个暂停新入场、61个重复退出控制保留；没有重新激活退出策略。真正相同的行为可汇总展示，但不改历史证据。

审查t10/t15/t20/t25这一小组：t10对t25共有41对终局、40个独立Token，累计净收益差+126.06U；但30对完全相同，仅7正4负，sign-test p=0.5488，最大3个绝对差值贡献48.5%。固定seed bootstrap均差区间虽为正，不能忽略稀疏有效差异和集中度。**撤回首次子审查的暂停t25建议，保留四个小规模阈值对照**；其他full/bank组合同时改变trailing，不能叫单参数实验。不是每次优化都必须淘汰策略。

后续选择优者需共同部署后配对、独立Token/入场事件聚合、成交成本一致、成熟终局、时间块一致性与成本敏感性。达到这些标准后仅停劣势版本新开仓，已有仓位仍由旧合同退出。

## 可运行的监督闭环

`kv.forward-review151`保存实际完成时间、产物路径、下次7200秒周期、日报状态。首次two_hour于04:13:00Z、daily于04:13:05Z实际完成。report不调用市场API/模型、不写交易DB、不自动修改参数；出错记录error并120秒后重试。

报告包含有界同Token漏斗、同cohort路径、真正拒绝原因、队列与分位时延、策略控制、当前/归档独立经济统计，以及预定义+5/+15分钟至+60秒窗口的同池观察。观察须VISIBLE、正价格、观察早于入库且年龄≤15秒。窗口未完整成熟单列maturing；没有退出/后续行情单列missing。≥20%非风险退出反弹只能叫市场价格代理候选，不能称为成本后可执行洗出。

当前报告仍不能恢复没有记录过的逐阶段历史排队/特征时点、每个发现源的完整池级漏斗和退出后的连续行情。没有引入为了“更准确”而变重的采集栈；优先复用共享报价的自然样本。收益结论等待自然观察，不能用“已设定周期”冒充“已验证盈利”。

## 未完成验证 / 后续优先级

### 04:20 UTC 补充回放及短窗结果

Robinhood cohort1555/1549/1547、BSC1554/1553/1552并非缺少后帧：均有数秒内的新Dex观察。阻断在`preentry_obvious_scam_v1`证据：RH `CHECKED_UNKNOWN`（无usable safety fact）；BSC `WAIT_WEAK/CHECKED_WEAK`（仅honeypot_with_same_creator=false）；最终90秒`EXPIRED_SECURITY_OR_NEXT_FRAME`。这是安全数据不足，不是金额quote/资金错误。不得从“没有order_intents”反推出safety未被执行；主审已纠正子审查的这一错误，普通Paper投影确实先过safety。没有普遍放松安全门，也不新增重型API。

截至04:20左右，两个替代臂各9个独立Token仓位；其中分别2/3个closed，已实现净结果约-5.54U/-14.7343U，其余未结。早期样本证明链路触达，不支持盈利结论，负结果如实保留。组合退出尚无自然仓位，不冒充完成自然退出。

同进程已处理1101个passive批次，dropped0、队列深2；队列p50/p90/p99=1.344/1.988/2.529秒。held_fetch p50/p90/p99=0.672/1.753/2.734秒；held_apply_exit=0.047/0.063/0.369秒。shared精确回执100，未增加HTTP批次。短窗与基线流量并不相同，不能据此宣称显著提速。旧native_clock计数35未增，但没有足够新native held样本，仍标待自然验证。

错误开放8项、high0：新增一次capital-quote超时重开旧case24，其余旧RPC/WS/429/身份检查案例未强制关闭。这属于未完成的持续可靠性观察，不是“所有错误已解决”。

历史审阅新增`archive_branch/CHAT_HISTORY_REQUIREMENTS_REVIEW.md`（两页更早对话、turnID）。采用成本/独立样本/旧状态隔离经验，拒绝照搬旧参数、重置、接管命令与不可获得附件内容。普通买卖笔数不能解释为organic需求；151明确是待证伪代理实验，不继承历史否定过的“仅凭量价即证明非操纵”主张。

P0：核对Robinhood admitted无source-fill的真实执行语义；追踪当前7个历史错误案例，不能靠隐藏/改状态清零。native_clock代码缺陷已回归验证，但部署后的自然native held样本必须单列。

P1：按同负载窗口观察替代臂覆盖、已有策略退出时效与错误增量；至少一个完整2小时周期再比较频率/延迟。继续保持有界并发和退出优先，不提高全局扫描频率。

P2：新退出包与母臂成熟配对、成本敏感性、固定窗口反弹覆盖及尾部风险；参数差异不足不淘汰。当前没有证据证明持续净盈利。

## 工件、复核与回滚

### 04:38 UTC 最终补充：成熟样本与退出后观察

发现并修复报告抽样缺陷：高扇出下最近200个平仓可能全部尚未成熟，周期报告因此一直错过已有成熟观察。现在只从至少16分钟前平仓中取最多200项，未成熟仓位另列；截止时间后的平仓不计入。EVM原池比较规范化大小写，Solana保留大小写。

实测修复后的04:28报告：200个成熟仓位、33个Token/入场标识；+5分钟有效36、缺164，+15分钟有效2、缺198，另有472个未成熟仓位。该结果揭示真实观察覆盖不足，不是198个退出正确或被洗出的证据。抽查缺样本Token的token_snapshots同窗亦无数据，排除只查错表。

最小采集补丁`post_exit151.py`：每15秒后台线程只读查询已经平仓的+5/+15分钟固定窗口，300ms查询预算、最多96个窗口；复用已有允许共享的低优先级新鲜Dex请求，在已有共享入场候选之后最多借1个地址空位，不新增HTTP批次、不碰高优先级。只接受同链同Token同原池、因果可用且≤15秒的新观察；只追加market_mark_history，不更新live mark、策略特征、仓位、订单或PNL。相同Token/池一帧覆盖多策略窗口；重启从持久平仓和已有证据恢复，已完成窗口不重复入队。未赶上窗口仍诚实报告missing。退出时间索引只加速读取，不改变历史交易。

当前数据库首次只读选窗耗时16ms。补丁与共享批次/报告共59项测试通过；组合退出与报告18项通过（有交集，不相加冒充独立测试量）。独立审查确认返回值隔离和观察写入边界。关闭`optimization151.post_exit_enabled`并重启可单独回滚观察器，历史证据保留；无需改策略或删除索引。这个观察器改善研究覆盖，不承诺真实卖出可执行性或收益。

组合退出可达性反证：新版本生效至04:28:34，123个cohort、296个机制帧中survivable_steady入口为真0次，母臂/子臂均无新信号或仓位。不是新模块路由断点；不为制造样本放宽入口。原先的Robinhood/BSC source-fill疑问已由安全UNKNOWN/WEAK回放解决，上方P0历史排查项不再待重复诊断。

04:40最终自然回执：6条研究历史覆盖9个窗口，额外地址6、额外HTTP批次0、reload6次无错误，pending0；含SOL/BSC真实Dex同池观察，非注入。passive处理186批、丢弃0、当前队列5；队列p50/p90/p99=1.391/2.032/4.798秒。held_fetch100样本中5次失败，p50/p90/p99=.712/2.116/6.344秒；held_apply_exit95样本0失败，p50/p90/p99=.032/.063/.987秒。这是含启动/网络尾部的短窗，不能宣布性能全面改善，也不能证明借1地址造成回归；周期报告保留容量/失败率作后续同负载比较。开放错误7项high0，由原有错误生命周期自然变化，未人为清零。

三轮工程交付的验收边界：代码修复、独立策略追加、测试、真实部署、替代臂自然开仓及项目周期报告已经落实。持续净盈利、新组合退出自然成交、native参考修复的新持仓样本、跨时段同负载统计仍等待自然证据。所有外部错误绝对不再发生不属于可承诺验收；旧8个开放案例保持可见，未伪造关闭。周期报告继续记录新旧错误、样本和风险，禁止自动修改旧策略或升级Live。

- 当前回执：`data/reports/deep_cycle_20260913/deployment/{before,after_start,forward_1}.json`。
- 周期产物：`data/reports/deep_cycle_20260913/reviews/`，JSON含详细样本/记录ID，Markdown人读摘要。
- 五个独立视角：`data_branch/DISCOVERY_FUNNEL_DIAGNOSIS.md`、`data_branch/PERFORMANCE_STABILITY_REPORT.md`、`strategy_branch/STRATEGY_SIGNAL_INVENTORY_20260913.md`、`strategy_branch/RISK_POSITION_REPORT.md`、`exit_branch/EXIT_COMPOSITE_AUDIT.md`。其中首次性能`no_spare`及字段可用性结论已由本文件的反证覆盖，不照搬。
- 缺失数据、参数配对反证：`strategy_branch/PARTICIPANT_FIELD_AVAILABILITY_20260913.md`、`PAIRED_EXIT_PARAMETER_ADDENDUM_20260913.md`。
- DeepSeek两个ZIP按可见对话提取后的建议筛查：`archive_branch/lessons.md`。参考ChatGPT `20260910_2`只当历史经验；不重复已存在315/321/学习模型，不继承未经证实收益或秘密材料。
- 公共补丁回退：部署目录`release151-tracked.patch`保留本次tracked diff；维护者先暂停新151臂新入场（保留其退出代码），再针对已确认目标文件反向应用该补丁；不能删除注册/仓位/数据库。已有新臂仓位未清完前不卸载对应退出模块。周期报告可单独关`optimization151.review_enabled`，无需停交易。
- 定向命令：`.venv/Scripts/python.exe -m pytest tests/test_market_proxy151.py tests/test_forward_review151.py tests/test_runtime_timing.py tests/test_composite_exit151.py -q`。
- 发布组：`.venv/Scripts/python.exe -m pytest tests/test_alpha149.py tests/test_alpha149_wave42.py tests/test_shared_batch148.py tests/test_shared_batch149.py tests/test_native_execution138.py tests/test_age_rate_revision_store.py tests/test_deep_cycle_report.py -q`。
- 运行回执：`.venv/Scripts/python.exe scripts/verify_release151.py --label <receipt>`；只读报告：`.venv/Scripts/python.exe scripts/deep_cycle_report.py --minutes 120 --label <label>`。

官方边界：[DexScreener API](https://docs.dexscreener.com/api/reference)；[GeckoTerminal公共限制](https://apiguide.geckoterminal.com/faq)；[SQLite WAL并发读](https://www2.sqlite.org/wal.html)。批量上限/数据源限额以官方现行文档为准；本次未新增HTTP批次或修改限额。
