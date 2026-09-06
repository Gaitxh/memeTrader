# ROUND2 底座可靠性独立审查

审查日期：2026-09-07（Asia/Shanghai）；运行证据主要为 2026-09-06 18:39–18:46 UTC。审查 HEAD `f128389`，生产资金期 `chain-meme-trader/funding-20260906-v002-final-1000`，214 策略。本文件是只读研究及修复建议，未修改应用、配置、数据库或策略，未重启、运行测试、提交。遵循仓库 AGENTS、memetrader-forward 与 windows-project-ops 技能。

## 核心结论

1. **已见执行语义缺口：旧主入口仍用同一帧做决策与 BUY。** 最近 700 笔交易中有 103 个 BUY 投影、26 cohort，三链均有实例。特征在决策前已知，故不是未来特征污染；但不满足本轮要求的“决策之后实际可得报价”，必须与严格后帧结果分层。不能据此断言全部收益虚假或金额偏差已知。
2. 新八臂中已自然成交的五个退出臂，100 BUY、60 SELL 均通过本次后帧时间核验；另外三个新入口尚无自然 BUY。旧 pattern 路径抽到的 196 BUY 与旧 298 SELL 也通过。本次样本无晚到旧报价被新五臂接受的实例；不能外推全历史无缺陷。
3. `finalist_profit_budget_v1` 的 +42.7276746242U 赢家能以同一原池连续报价和双侧 4% 账本重算；实际因 30 分钟最长持有退出，**不是 profit-budget 机制的成功触发**。仍是轻量 mark 模拟，不是链上真实成交证据。
4. 三链账本、一个部分卖出账户及一个账户快照前沿独立重算吻合。暂未发现本次样本存在错池、负/缺失流动性成交、重复入账或成本双扣。
5. 当前性能没有显示新八臂造成主循环停滞；瓶颈证据仍偏向上游覆盖与观察任务耗时。未建立可归因的部署前后负载对照，不能声称新八臂资源开销为零。

## 证据边界与方法

- `config.json` 仅解析 `database` 字段，目标 `data/memetrader_forward_20260830_r6.sqlite3`；连接为 SQLite `file:...?...mode=ro`，不构造 Store。
- 每条 SQL 配置 2 秒 progress-handler 截止，读取主键区间、策略/时间索引、token/时间索引或开放仓索引；无全历史聚合、完整性扫描、checkpoint、VACUUM 或备份。
- 主交易窄窗冻结为 ID **454434–455133**，实际时间 **18:29:27.169883–18:41:45.900747Z**。新八臂分别按 `(definition_version, arm_id, created_at)` 索引读取真实激活后至该前沿；每臂最多 201 行，实际最多 39，未触上限。
- 赢家单 token 的历史窗 17:52–18:24Z 为 160 行，按现有 token/recorded 索引。其后的经济统计交由独立统计 Agent，未重复扩大扫描。
- `/health` 与 `/api/performance` 只读；不重新访问已知重型 `/api/state`。未进行外部新报价、真实卖出或交易模拟器建设。
- 下文分别标注【代码事实】【运行样本】【未核验】，避免将工程通过等同盈利。

## A. 旧主入口同帧 BUY：最高优先的最小改进

【代码事实】`src/memetrader/store.py:27832` 的 `enroll_chain_meme_trader_v6()` 冻结入场 cohort 与参与 arm。`store.py:28336` 的 `dexscreener_snapshot_4pct_adverse_fill` 分支直接调用 `_project_chain_meme_trader_market_entry()`，传入信号 `snapshot_id`、信号 `features["price_usd"]`、`filled_at=decision_at`。没有后帧等待。

【运行样本】上述 700 笔窄窗里，103 个 BUY 投影都满足 `snapshot.observed_at < cohort.decided_at == trade.created_at`，分属 26 cohort：SOL 101 投影、BSC 1、Robinhood 1；全部入场 liquidity 非 NULL 且 >=1000。它们不是 103 个独立 token 机会。

| 链 / trade / cohort | 策略 | 信号 observed_at | decision 与 fill_at |
|---|---|---|---|
| SOL / 455127 / 24216 | l0_profit_lock_control_v1 | 18:41:36.126578Z | 18:41:36.778607Z |
| BSC / 455038 / 24140 | canonical-ca8f32cf0d565e07 | 18:40:06.512683Z | 18:40:06.977945Z |
| Robinhood / 454964 / 24076 | broad_flash_tail_first_mover_v1 | 18:39:03.891379Z | 18:39:04.367507Z |

三例 reason 均为 `broad_launch_asof_pass:dex_mark_paper_fill`。例如 SOL snapshot1246243 的 observed/ingested/recorded 分别为 18:41:36.126578 / .126578 / .209641Z，决策 .778607Z；没有把尚未收到的数据当作特征，但使用了决策前已存在的价格。

### 可复用状态与建议改动

【建议，未实现】公共执行适配修复无需改变任何策略 entry/exit 规则、hash 或旧账本：

1. 保留 `v6_cohorts` 的信号 snapshot、原池、`decided_at`、冻结参与组，以及 `entry_decisions(status=admitted)`。将该分支的即时 `_project...` 改为现有 `order_intents` 的唯一 `ENTRY_BUY:{cohort_id}` 待执行记录，复用 `ready/retry/submitted`、`created_at`、`expires_at`。
2. 复用 `store.py:28167` 起的 pending 数量与独立 arm 现金预留，以及 `max_pending_buy_intents` 上限。当前代码虽有这套限制，market BUY 没有 pending，不能只改入队而忽略预留/释放。
3. 在现有主循环消费有界 pending BUY，选第一条真实可得的同 token、同原池后帧：`observed_at > intent.created_at`，`observed_at <= ingested_at <= recorded_at <= now`，保持既有新鲜度和有限正价/完整流动性/原池门槛。只使用已经取得的本地数据；不新增 exact quote API。无合格帧等待，到既有 expiry 记 failed，不倒填早期价格。
4. 继续调用 `store.py:27727` 的 `_project_chain_meme_trader_market_entry()`：已有唯一 cohort fill、`INSERT OR IGNORE` position 与现金二次检查。保持 cohort 的信号 snapshot；position 的成交 snapshot 指向真正后帧，使两个 frontier 可独立复核。成功或终止后更新 intent，避免永久保留现金预留。
5. **已有重要接线陷阱：** `due_chain_meme_trader_execution()` 在 `store.py:29206` 左右对 `sell_execution=dexscreener_market_mark_only` 会取消本期所有 ready/retry intents 后返回。必须将 market BUY 的本地后帧消费纳入这个分支，保留隔离 Jupiter 的目的；不能仅复制下面 exact-quote 的入队代码，否则队列立即被取消。`runtime.py:6453` 已每轮调用该入口，可复用，无需新后台任务。
6. 明确新执行 epoch/启用前沿，旧成交保留 same-frame 标签。`activate_chain_paper_execution()` (`store.py:7351`) 目前只识别四个手工设置；四值相同直接返回旧 activation。不能声称已有四参数 activation 自动记录了新时序语义。应以最小独立执行语义版本表达前向变化，不修改旧策略定义或资金期，不改上轮新八臂机制。

【查询计划已核验】`SELECT ... FROM token_snapshots WHERE token_id=? AND observed_at>? ORDER BY observed_at LIMIT 8` 使用 `token_snapshots_lookup_idx (token_id=? AND observed_at>?)`。主入口新鲜原池后帧是否主要来自 `token_snapshots` 还是现有 pool mark 接收点，应由实现者选择最短接线；不能为了取后帧把发现间隔或 source 覆盖问题隐藏掉，也不能用 latest 帧跳过第一可得帧而不记录。

【定向测试建议】一个参数化 SOL/BSC/RH 生命周期覆盖当帧不买、晚收到但 observed<=decision 不买、真实后帧买一次；错池/NULL/stale 留 pending，expiry 后不买；独立账户预留与不足现金、重复调用/重启不重复投影；旧定义/hash/funding 与新八臂不变。执行前沿新增后，核验一笔自然 BUY 的 signal 与 fill 两条时序即可，不需全套回测。

## B. 新旧后帧语义：实际通过与代码剩余边界

【运行样本】按真实 signal evaluation 而不是 BUY 投影时刻作为入场决策起点：

| 组别 | SOL BUY / SELL | BSC BUY / SELL | RH BUY / SELL | observed 严格晚于 signal/trigger 的反例 |
|---|---:|---:|---:|---:|
| 新五退出臂全部自然记录 | 60 / 39 | 30 / 11 | 10 / 10 | 0 |
| 最近 700 交易中的旧 pattern BUY / 旧 SELL | 140 / 221 | 41 / 50 | 15 / 27 | 0 |

旧主入口 103 BUY 单独归于 A，不混入“后帧通过”分母。这里的每臂投影有共享 cohort，不能用于独立市场样本置信区间。

【代码事实】新八臂 `research_finalists.py:42` 显式 `require_post_decision_observation=True`；入场在 `store.py:27003` 核对 fill observed > previous evaluated；退出在 `store.py:33423` 核对 post observed > pending recorded，同时要求新 sample sequence、15 秒新鲜度、正确原池与有效流动性。

【代码边界，未见本窗失败实例】上述两处 observed 后帧保护仍受策略 flag 控制，旧206默认不要求；旧退出只要求后帧 recorded/last_success 晚于 trigger，理论上仍能接受 trigger 前 observed、trigger 后 received 的迟到报价。A 的公共执行时序修复应同时评估把“后帧 observed”作为新的公共执行 epoch 语义，而不是另加策略条件。推荐复用本次已存在的新八臂迟到帧回归场景，覆盖一条旧策略；不要声称本次 298 旧 SELL 已发生这一污染。

【代码事实】新三入口要求九个间隔至少15秒的观察、整段身份/source 连续和 as-of 时间；NULL 中间帧不被简单过滤拼接。新退出对 provider 切换或 gap>60 秒重置连续状态/利润峰值。此为本地接收观察的独立性，不能证明上游每次都产生独立成交状态。

## C. +42.7277U 赢家的完整审查

【运行样本】`finalist_profit_budget_v1`，cohort22330，token `bsc:0xd3c28b63fae40edbcca41eba73546d38fa9b8bed`，原池 `0x229248a9337ff128b2c067faa8f25eb0faaa7f18`。EVM mixed-case history 地址规范化后一致。

| 环节 | 记录与实际值 |
|---|---|
| 信号 | snapshot1217160 observed17:53:20.759367Z；evaluation17:53:21.421495Z |
| 后帧 BUY | snapshot1217216 observed17:53:31.827978Z，ingested17:53:33.077637Z，recorded/fill17:53:33.087729Z |
| 投入与数量 | trade452360，5U；market price7.83e-7；execution price8.1432e-7；quantity6,140,092.346988899 |
| 退出触发 | mark229165，18:23:34.394108Z，`TIME_EXIT / market_mark_max_hold` |
| 后帧 SELL | post observed18:23:36.601388Z，recorded18:23:36.601729Z；sequence663→664；price8.097e-6；liquidity69,880.65U |
| 退出账本 | fill211583、trade454104；回款47.72767462422635U；allocated cost5U；PnL42.72767462422635U；剩余数量0 |

独立公式：`5 / (7.83e-7 × 1.04) × 8.097e-6 × 0.96 = 47.72767462422635`。无额外手续费；position、BUY/SELL cashflow 和 realized PnL 一致。

17:52–18:24 的 160 条 local market history 均为 Dexscreener 同原池，价格逐级上升，中间有小幅回撤：例如7.83e-7→1.504e-6→1.432e-6→2.455e-6→2.352e-6→5.654e-6→8.097e-6；未见10倍 decimal 瞬跳、provider 切换或错池接价。入场 liquidity21,675.04U，退出69,880.65U，均通过当时门槛。

该笔 state 最后 `bad_streak=0`；profit-budget 没有触发。其对基线的增量盈利不能由这一笔证明。统计 Agent 已获得完整 token/pool/记录 ID，继续处理共享 cohort 与后续对照，避免重复原池路径审查。

【未核验】这160帧是同一上游的本地持久化证据，没有独立链上 reserve/swap/税费证明；未验证真实卖出、MEV、代币税、可出售权限或撮合/路由。因此可以说“模拟账本与当时保存报价自洽”，不能说“已在链上赚到42.7U”。

## D. 三链与部分卖出账本

【运行样本】除上面的 BSC 闭仓，再独立核验：

- Robinhood `finalist_profit_budget_v1/cohort22512`：BUY5、回款5.73573670755、已分配成本5、PnL0.73573670755、剩余0；两条 trade cashflow 与 position 一致。
- SOL `finalist_profit_budget_v1/cohort23900`：BUY5、WRITEOFF0回款、成本5、PnL-5、剩余0。mark229574 保存了原池 `6QqkPouXjR6zVmAWku4wPzLnsds4hJrAXEnFwMYj7qpc` 的 fresh liquidity0.1U：observed18:36:08.716440、recorded.718085、核销.730258Z。不是 NULL/超时推导核销。之前该池显示100,855.62U，后来18:36:18历史仍0.1U；只证明按既定原池门槛核销，不能冒充真实卖出或证明钱包不可回收。
- Robinhood `broad_principal_lock_runner_v1/cohort17275` 部分卖出：初始20U、quantity1,652,965.94222155；剩余413,241.485555388（25%）；allocated cost约15U；回款24.912079926427；realized9.912079926427；剩余成本约5U。`20 × (1 − remaining/original)` 与成本字段在浮点误差内一致，未把整笔20U重复计入本次已实现损益。
- `finalist_profit_budget_v1` account snapshot1456867（18:42:52.828833Z，ledger frontier455190）按该账户38条已部署交易重算：`1000 + Σcashflow = 979.3944507135383`，`Σrealized = -0.6055492864617125`，与snapshot一致；4开放仓，indicative equity998.6933152318184。不能把18:41较早的+4.39445U realized与18:42较新账户混算。

【代码事实】`paper_execution.py:93` / `:111` 将买价乘1.04、卖出回款乘0.96，每fill扣一次额外费；固定同价往返损失7.6923%，盈亏平衡需价格上涨约8.3333%。普通 mark 模型没有深度/冲击估计，也没有自动补算 gas/税/MEV。这个边界是用户保留的轻量模型，不建议借审查扩建精确报价框架。synthetic raw 以1e9归一，真实 token quantity 字段用于经济计算，不能将该 raw 当链上 decimals；同样，WRITEOFF/SELL intent 不等于成交。

## E. NULL、stale、错池与动态补源

【运行样本】18:43附近当前 pool marks 中：

- SOL `29f8jx…Vpump` 保留完整 Gecko 帧 liquidity2378.1502、observed18:42:54.101341、success18:42:54.111402Z；后续 attempt18:43:18.879163、failure=`DATA_REJECTED:quote_liquidity_unavailable`，未刷新旧 success/observed。这是上一轮NULL修复在实际运行中的正确失败语义。
- Robinhood `0xc5c183…6a01f` 状态UNKNOWN、liquidityNULL、successNULL，failure=`DEX_SOURCE_COVERAGE_GAP`；没有将“轮询尝试”当成功。
- BSC `0x91c6dc…affff` 原池地址为token地址的特殊场所，Gecko完整帧保留，DS主源仍记coverage gap。不能直接删除特殊后缀或把另一个池的流动性补在原池上。

【代码事实】`market_api.py:94` 说明 Gecko observed 为本地接收时刻，provider 时间只保存在raw。`market_api.py:245` 附近保持同HTTP generation的旧 observed，ETag相同且Date推进允许新的接收帧；这能避免本地cache假刷新，但不能保证上游链上状态新鲜。`runtime.py:5545` 的不完整主源60秒重试及原有精确池Gecko/Demo/429退避依旧在用，本轮未新增API。

【边界】当前“动态市场补源”是预先实现的 DS→Gecko→Demo 有界路由；`autonomous_search.discover_sources()` (`autonomous_search.py:2816`) 搜索/验证的是公共RSS信息源，不是自动为未知DEX API写适配器。`runtime.py:3073` 在strategy-focus下明确暂停这条通用source-discovery。不能把新闻source discovery的存在解读为所有缺报价池会被Agent自动修好。

## F. 资源与 Agent 经济路径

【运行样本】18:39:02Z `/health` running，仍原资金期；`/api/performance` 本次响应约0.057秒：

| 组件 | 实际间隔 P95 | 耗时 P95 |
|---|---:|---:|
| 主交易循环 | 1.216s | 0.256s |
| 持仓mark循环 | 3.818s（配置1s） | 3.636s |
| held fetch / apply-exit | — | 3.233s / 0.072s |
| pattern observer | 15.172s | 11.760s |
| cohort observer | 10.149s | 6.818s |
| multichain发现 | 90.173s | 43.602s |

RH当次78 token、73 coverage gaps、age P95858.169s；SOL128 token、2 missing、68 failure、16 coverage gaps，age P9551.728s。指标口径是每token所需原池中最旧者；failure可包含数据拒绝，不是等量网络失败。新的三个入口要求及时、连续原池特征，因此这些时效缺口可能导致等待；不能把零BUY直接判经济失败。

18:39:27Z：Paper PID35088启动17:48:54，working set约111.9MiB、累计CPU2706.7s（约其运行期0.89核平均）；Web PID22232约239.8MiB、累计CPU583.3s。数据库约14.281GB、WAL约196.347MB，WAL模式；接口报告磁盘free约52.35GB。未发现本次连接阻塞或停滞；单点内存/WAL与累计CPU不足以证明泄漏、锁竞争或新八臂因果增量。没有执行全库检查、checkpoint或新压力测试。

【代码事实】新机制纯函数不自行请求网络/数据库，其接线复用现有observer与持仓mark。当前pattern/发现任务耗时明显大于exit apply，但尚无可归因证据支持削弱退出、加线程或新索引。先完成A的窄执行改进，保留现有有界循环与持仓优先。

【Agent运行记录】UTC2026-09-06 `autonomous_search` 已记录trend_scout17次、1,007,277 tokens；同日source_discovery与token_context quota key无记录，按`usage()`实现缺省为0。source-discovery最后保存运行是9月3日，不能算当前期带来的新覆盖。postbuy research最后case/result均9月3日旧v5，最近case `decision_eligible=0, affects=none`，result `no_context`；未发现本期该旧postbuy路径的新增交易贡献。该检查不覆盖所有pattern narrative证据，**不能声称全系统Agent完全未贡献信号**，也不能把已消耗tokens等同获利。

【最小经济改进建议】使用既有cohort/entry理由将新闻/趋势/上下文实际参与的决策与覆盖记录连接起来，在用户触发的研究中评估贡献；先弄清哪条消费路径被启用，避免因看到百万tokens就新增Agent轮询或自动部署。本轮不恢复暂停的source research/自动复盘。

## 交付裁决

建议优先实施A的公共、前向 market BUY 时序修复，并在同一窄执行改动中处理B已定位的旧退出迟到帧边界；不改214策略定义、不初始化、不重写历史、不更改新八臂机制。其余样本账本与异常赢家已核验到轻量mark模型所能支持的程度。上游可实现性与覆盖仍不足以宣布alpha、Paper盈利稳定或Live可用。

## 追加：R1 之后的最小接线设计检查（只读，未实现）

已完整阅读 `R1_STRATEGY_DISCOVERY.md`、`R1_ADVERSARIAL_PORTFOLIO.md`；不重复运行性能或数据库统计。以下行号以本次读取的应用代码为准，后续实现可能移位。

### 待执行 BUY 的输入与现有采集路径

- `store.py:30690` 的 `chain_meme_trader_market_mark_targets()` 已将 pending intent 纳入held轮询，但其 `entry_pair_address=NULL`。最小接线是该分支按 definition/cohort JOIN `v6_cohorts`，输出冻结 `c.pair_address`，使既有精确原池补源也覆盖pending；保留开放仓最高优先。
- `apply_chain_meme_trader_market_mark_batch()` (`store.py:31009`) 接收实际 `TokenSnapshot`，更新pool/market marks，不写每帧 `token_snapshots`。主发现约90秒，而既有signal expiry也是90秒，因此仅等待主发现快照可能白白过期。优先复用该接收点的真实pending原池snapshot或同轮pool mark消费，不增加请求。
- 最小有效性：intent未终止/未过期；冻结参与组与原池不变；chain/token/base/pool身份一致；`observed > decision`，`observed <= ingested <= recorded <= now`；原有15秒新鲜度；price有限且>0、liquidity完整有限且>=有效floor。错池/缺值/迟到旧观察等待，不拿当前其他池冒充。
- `latest_snapshot()` (`store.py:12388`) 只按observed截止取最新，不保证recorded截止或第一后帧，不能直接当新settler。原池图表history经过采样且仅保留6小时，也不能当完整接收序列。首个合格接收即消费最简单；如用snapshot fallback，以现有token/observed索引有界升序，排除allocation复制，保留真正原观察时间，不按后来的最新/更优价选fill。
- `pool_marks` 没有ingested字段；若使用它，保留真实observed/recorded证据，不能把自行构造时间称为已独立核验的ingested。既有接收点的TokenSnapshot能直接保留完整时间链。

### gross/net 语义修复范围

`store.py:32668` 将 `sell_execution['net_usd']` 赋给变量gross，其后同时用于fill/trade.gross、cashflow与累计proceeds。当前额外fee0，因此没有金额差异；fee非零时净现金/PnL算法已经正确，错的是gross字段语义。

最小改法：分开gross与net。fill/trade.gross及毛兑出量使用 `sell_terms.gross_usd`；cashflow、realized proceeds/PnL、`formal_net_recovery_usd`继续用net。特殊amountful分支已有 `minimum_output_raw`（毛最低兑出）和 `net_recovery_usd`，不能再扣一次fee。历史行保持原样，执行版本说明分界。

定向夹具 `tests/test_paper_execution.py:84` 的 `test_activation_is_immutable_and_market_ledger_uses_frozen_execution` 已有买10%/卖5%/每fill1U情形及净现金/PnL断言；在同一测试加gross=net+1及fill毛输出断言即可。辅助 `_snapshot` 在28、`_mark` 在43。

### post-signal chase guard 的最小实现点

R1“position.entry_signal_price_usd已经保存真正信号价”的表述需修正：`_project_chain_meme_trader_market_entry()` 将传入的实际fill market_price同时写为该字段，pattern亦如此。追价幅度必须从冻结signal snapshot读取：observer的 `previous_features.source_snapshot_id`，或fill cohort中的 `fill_signal_snapshot_id`；不能使用position里这个字段冒充前置信号价。

新增guard/control ID可复用当前conditional-runner signal和5U后帧fill；最小处理点在 `observe_chain_meme_pattern()` 的 `admitted_arms`（约27002）形成后、`by_notional`投影前，读取一次signal snapshot主键，计算 `post_price/signal_price-1`，按预注册阈值只拒绝候选，记录到既有evaluation.feature_json。阈值不是本次工程审查能推导的盈利事实。

该实验是同机会BUY与NO-BUY，**不能把guard拒绝放进现有all-or-none paired检查**，否则control也被拒绝。应先让新二臂完成共同slot/cash/source admission，再仅对candidate执行经济拒绝；记录拒绝机会并在已有evaluation state保留consumed signal/episode，避免后续价格回落时补买原机会。不要把这个guard加到旧214或上轮8的公共执行门。

### 新paired exit 与 runner 的最小接入点

- 保留原 `finalist_policies()` 八份输出；新增独立factory/IDs，再用 `append_chain_meme_trader_policy()` (`store.py:25659`) 与 `register_chain_meme_research_finalists()` (`26016`) 的真实时点、幂等append模式接入，runtime注册点现为1349。新paired group不能加入旧 `finalist_exit_matched_v1`，否则改变旧五臂机会集。
- `observe_chain_meme_pattern()` 已按 `paired_entry_group/size` 做共同机会、slot、cash admission，并按notional共享cohort与fill。新增二臂无需新entry kernel。注意拒绝原因写入目前部分分支特判 `expected=={5}` / `len(arms)==5`；新二臂若只复用配对条件，可能有正确拒绝却缺逐臂原因，应在既有feature_json上泛化该诊断，而非新增表。
- marginal-response decay / depth-contraction exit 所需price、liquidity、m5 volume、buys/sells、provider已在 `_capital_exit_result()` (`31546`) 的L0 adapter输入。新增kind与纯函数、O(1)接受状态即可；通过现有capital exit结果→pending mark→后帧SELL (`33730`)。保持缺值/source/gap reset；不能把rolling m5导数称实际新增资金流。
- post-harvest requalification需要真实partial fill之后才起runner epoch。最小hook是 `_settle_chain_meme_trader_market_exit()` 成功fill后的 `new_amount/new_proceeds/remaining_quantity` 与position更新（32758–32850）附近，只对新kind向现有 `capital_exit_state_json` 写实际 `fill_id/completed_at` 和余仓经济值基线。没有真实partial fill不进入probation；旧峰值不能与新的proceeds拼成当时未存在的值。后续评估复用现有L0 adapter，不修旧profit-lock flag来冒充这个新机制。
- 如果采用“快速退出时保留小runner”的sentinel，现有capital结果仅在ordinary `action is None`时替代，不能期待普通capital evaluator自动截获已选中的full exit。需新策略专属、在最终mark创建前对允许的失败退出reason调整sell_fraction；公共核销/硬终止不能被不明覆盖。它与post-harvest是不同机制，不应同时隐式加入一个ID。

定向复用：`tests/test_forward_patterns.py:87` 三链同fill/现金/隔离；`tests/test_research_finalists.py:141` 幂等注册/共同入场/slots，`:184` matched exit与baseline不变，`:260` pending→晚到旧帧拒绝→后帧SELL，`:309` 新入口真实Store时序；`tests/test_capital_store_integration.py:225` 等额配对共享fill，`:247` 无pending时不扫历史预留，`:553` earn-exit后帧；`tests/test_core.py:8195` `_seed_chain_market_position` 与`:8999` partial经济high-water。选实际改动直接命中的夹具，不重复整套测试。

## 未提交执行修复的独立部署复核

本段仅审查当前 `store.py`、`runtime.py`、`test_paper_execution.py` 的执行diff及直接采集调用者；未运行测试、生产SQL或性能检查。主执行代理报告6项execution测试已通过，本审查未重复执行，未将其当作真实采集覆盖证明。

**当前读取版本有一个具体部署阻断：正常DexScreener fresh报价缺ingested_at，被新settler全部跳过。**

- `collectors.py:1978` 的 `DexScreenerClient._snapshot()` 创建TokenSnapshot只填 `observed_at=utcnow()`，没有ingested；`models.py:138` 默认None。
- `batch_quote()` / `batch_quote_fresh()`、`runtime.py:1560` 的 `_dex_batch_quote()` 原样返回；现有 `_held_pool_quote_rejections()` 校验不补ingested。
- `runtime.py:6831` 将主持仓snapshot.ingested_at复制到pool_snapshot，因此仍为None。
- 新 `store.py:27865` 的 `_settle_pending_market_entry_observation()` 遇到None直接return。结果是主源已获得有效新鲜原池报价，pending仍无法成交，随后90秒expiry；只靠备用源偶然补字段不能算主路径正常。
- 新测试使用的 `_snapshot` 夹具始终显式填ingested，所以三链测试没有经过这个真实采集形状。

最小修复是在真实接收边界补本地接收时间（保持原observed不变），或在settler缺ingested时明确用传入received/recorded时间作为本地接收证据，再把该值写入receipt snapshot；有ingested则保持原值和时序校验。补一条用真实 `DexScreenerClient._snapshot(raw_pair)` 构造数据、经过pending→原池接收→成交的定向测试即可，不需扩大审查。

已读diff中未发现其他明确部署阻断：receipt经同事务 `_add_snapshot_locked()` 保存，position指向真实receipt而cohort保持signal；`market-entry-confirmation:%`已从普通enrollment排除，避免receipt重新产生入场；唯一receipt key、唯一cohort fill、position幂等和intent终态防重放；0 projected写failed并保留participant outcomes；pending原池加入既有watch targets，expiry与现金预留沿用已有状态；注册采用独立kv时序epoch而非覆盖定义/资金；SELL gross与net已分开，proceeds/cash/PnL仍使用net，amountful没有再扣一次费。上述是代码复核结论，不是生产部署验收。

### 部署阻断关闭（274195c）

上述缺 `ingested_at` 阻断已关闭：独立读取274195c确认真实receipt边界仅在None时使用 `recorded_at` 补本地接收时间，保持原 `observed_at`；定向测试已改用真实 `DexScreenerClient._snapshot(raw_pair)` 的None形状并参数化三链。主执行代理报告6/6通过，未重复运行宽测试。主代理另报告已推送、原资金期重启，时序epoch=`2026-09-06T19:25:25.323327Z`、frontier1272816，真实DS及Gecko receipt已推进；旧定义、87追加政策hash和资金activation均不变。此部署运行验收来自主代理，本独立复核确认代码与fixture修正，没有遗留的已证实部署阻断；不把模拟receipt称作链上真实成交。
