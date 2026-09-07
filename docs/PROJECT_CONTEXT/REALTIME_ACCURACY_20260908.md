# 后台优先：稳定性、准确性、实时性优化

用户连续要求：在允许范围越快越好；检查计算、特征、判别、结果指标；修复原池行情过期；资源优先后台。此前资金期与策略退休决定保持。

## 已改变的实际问题

1. 新币补全的15秒任务遇持仓忙直接返回，实际数轮空转。改为等待持仓通道空闲后继续，保留共享退避及每轮30目标上限，不额外扩大默认180目标/90秒规模。
2. 存在待执行BUY时，资金预留查询可能从整个历史决策版本驱动JOIN。新增 `(definition_version,shadow_cohort_id,status,arm_id)` 索引并从pending intents CROSS JOIN精确查cohort，不改参与账户/现金预留公式。
3. 形态候选查询每轮按token分组历史evaluation且做JSON过滤。新增与过滤匹配的partial索引，保留最新记录、候选排序、数量及原池规则。生产只读同函数单次耗时从10.5276秒降为1.1355秒，各返回30目标；不同采样时间，不是严格同负载因果基准。
4. 原池A已取得有效Dex行情，却等待同批B的Gecko/Demo fallback结束再写入，可能过期。现每个provider成功后立即更新已成功池并检查退出，未覆盖项继续补查；单轮去重成功写入，不重新标记旧数据为fresh。
5. 前台初始 `/api/live` 和策略合同表会并发重复计算同份cold compact state。改为先实时状态、后合同表复用cache。隐藏页面暂停实时轮询，切回立即刷新；可见页面仍5秒。性能API及系统页说明同步。

## 准确性复核

特征审查核实pattern从raw.pairs按锚定pair取数，cohort以(token,pair)隔离状态/信号，无当前可复现跨池混帧错误。没有据“original_pool”名称错误地施加“只许Gecko首池”门槛。

对strategy230/resource_profit_structure_candidate_v1独立读取72笔交易、36终结仓、824全期快照：cash977.0844463281786，PNL−22.91555367182138，expectancy−0.636543157550594，PF0.5428980812743203，胜率30.5555556%，DD26.14161774133629均匹配API；逐仓回款−成本−PNL最大差0。范围是一个完整终结账户，不声称核验所有历史/全部开放仓。

## 验证与部署

16个不同定向Python用例通过：补全等待1、flat2、资金预留1、原池路由及fallback10、新early-apply1、Web诊断1。新增预留测试读取生产方法内的真实SQL，覆盖pending/filled/SELL、admitted/rejected、跨version；EXPLAIN确认cohort精确索引。JS语法、既有策略展示测试及隐藏页零fetch/零重排计时测试通过。

索引与等待先于2026-09-07T16:35:47Z重启Paper；首次建索引引入启动等待，约16:36:44恢复进度。最终含原池/前台补充改动于16:43:49Z按原launcher重启Paper及8790 Web，未碰8787/8788。注册、追加合同、activation摘要保持一致，Live锁定，无初始化。

16:44:36Z短窗：health running；补全实际间隔p50=15.0038秒；flat实际5.0578秒（此前p50约11.17秒）；主策略1.0116秒；持仓1.1577秒/p95=2.0161秒。新增BUY1、SELL11，仅证明自然运行接线，不证明盈利或长期速度稳定。

## 原池过期的剩余边界

实际案例RH `0x537eb9003797323550a9c730dd4f02167d538e78` 原池 `0x91d0a52786cf75286f93181a55a187f2e5a172c7` 有主源coverage gap；SOL `FsmotAayZVCuYEGrErmaLMmcEXpFXUrtehvz7LTGpump` 原池 `GX9GtAQrrWezCMGMVyaLEgSXGSbdav77vhok9U6FL36W` 及 `FjY1upxoYdt5r4mtcuDH8zutkmcoRy9gcBbgiQSmpump` 原池 `F2SEgEryBRKvYcBB28dka64BcAFsrfQq9a8cBRp5TUbg` 主源缺流动性。UI与后端pool marks身份和15秒过期口径一致，不是错误join。

最终采样RH最老30.0456秒、SOL最老19.5324秒，仍有coverage/缺字段。已修复本地“成功结果被其他请求拖延”，尚未消除所有源端缺失、缓存代际及额度约束。保留告警、真实观察时间和缺失状态；不以改阈值、换池代替原池、旧liq配新价或伪造fresh消除提示。

原始短窗与性能工件在忽略目录data/research/speed_next_baseline.json、flat_query_before_index.json、flat_query_after_index.json、realtime_accuracy_after.json。没有新增Agent后台任务、定时研究或自动策略扩张。

## 用户要求回顾与追加核验

已覆盖本轮连续要求：频率/实际速度、计算与判别、特征准确性、结果指标、原池过期、后台资源优先。交易量曲线与启动下降诊断仍保留在data/research/trade_volume_20260908/；没有以提高交易笔数作为工程验收条件。旧新策略扩张和初始化授权不因此恢复。

追加源端实测（约16:48Z，使用现有HttpClient与适配器）：RH原池0x91d0...精确Dex查询返回空字典；上述两个SOL原池Dex精确查询有价格但liquidity=None。Gecko同批返回两池流动性2303.9309与2378.7658 USD，响应Cache-Control明确`max-age=30, public, must-revalidate, s-maxage=60`，本机收件16:48:17.766496Z。这直接证实15秒有效期与当前补源缓存存在空窗，非本地提示写错。

针对两SOL例，SQLite最新原始pair为dexId=pumpfun、quote mint=So11111111111111111111111111111111111111112。已有PumpSwap vault观察器不能直接当成这两个池的完整实时USD行情源；现有WSOL参考还受30秒内复用及共享请求预算约束。未新增未经核验的储备定价adapter、拼接旧流动性、绕过缓存代际或自动购买API。

追加计算/消费者复核：entry_batch短窗p50/p95约0.0111/0.0171秒，净现金流已每批一次，未冒险加TTL资金缓存；cohort和sealed风险模型仍有有效策略消费者，旧ranker被替代后已早返回。未为省一个小字典或两次小查询新增缓存层，未删除有用的前向观察。

剩余未解决项明确为：部分原池目前免费源没有持续、完整、15秒内的价格与流动性。解决它需要满足当前身份/时间/估值合同的实时数据来源；加快本地循环不能单独补出不存在的数据。现有补查继续运行，失败与过期如实保留，不能宣称所有问题已清零。
