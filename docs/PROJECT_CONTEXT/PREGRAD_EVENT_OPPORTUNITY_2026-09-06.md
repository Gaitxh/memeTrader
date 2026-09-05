# 预毕业、无CA事件与主动机会实验

## 部署与补款回执

8e3cc74已推送Git。后台与8790于20:13:23Z受控重启；新4臂实际激活20:13:26.410020Z–20:13:26.506943Z、snapshot frontier906746，178策略，原funding-20260905-fixed-1000保留。20:23Z最近1000条输入中有85条pregrad_watch，不代表85个独立币或有效资金速率，实际输入状态仍逐条明确。

20:16:31.231352Z执行用户授权实际工程损失补款：BUY412305、broad_cost_coverage_scaleout_v1、cohort12377，20U。此前原池漏报/补源额度耗尽被错误计为撤池，现已修正。只恢复实际闭仓净亏损，不声称反事实可卖利润。原trade hash a29dd3e6fea26d2f3debe6dc5b2f333975ea6f117a27209fcc51e21958a45212 保持不变，原PNL -20U不改。此前7518.807662700746U→7538.807662700746U，source BUY唯一，防重复。

延迟补充：periodic的WSOL/观察任务时长含active-idle等待，不是纯网络时长；但空quote任务同样迟调度证实还有同步拥塞。逐币让出+独立pattern_token_compute计时已通过最小调度回归，尚待下一次部署。不能把这一局部修复提前说成全部延迟消失。

2026-09-06。独立来源仍见 TWO_INDEPENDENT_DISCUSSIONS_2026-09-06.md，旧174策略、原资金期和历史保留。

## 实际行为

- B03 PREGRAD WATCH：免费真实创建/迁移事实；按最初实际SOL和后续净曲线储备速率优先最多3币。确认RPC每30秒、3秒请求期限、300秒TTL，只保留两帧；未知报价币不计算SOL速率。毕业/迁移移出，实际新迁移可重新唤醒补全一次。不是毕业前BUY，不伪造毕业收益。
- B18 no_ca_event_flow_leader_v1：官方无精确CA事件的单一可解析symbol，首次Dex检索冻结同symbol候选集合及时间。每个冻结成员都要有同30秒轮的真实完整金额流，净USD流唯一正数第一才能选择。并列/缺源WAIT。首次选择后不重排赢家；选择之后新行情才形成信号，下一帧5U BUY。候选地址绝不标成官方CA，旧事件不重复买。
- prebreakout_net_accumulation_v1：至少60秒、4帧的窄幅价格内，两个相邻非重叠完整实际资金窗口持续净流入，参与广度和集中度合格，5U探测价格启动前资金积累。不是事后筛选上涨币。
- liquidity_leads_price_v1：至少120秒价格仍窄幅，Dex报告流动性增长25%、末端不回落，5U探测深度先行。报告流动性不等同LP锁仓或真实可卖深度，规则/成本仍显式。
- fast_stop_reclaim_v1：当前资金期已有真实、无工程污染的闭仓hard-stop证据；60–600秒内记录至少30秒/4帧收复，以真实止损成交价和原入场价作为阈值，5U下一帧试验。每个自然止损cohort只消费一次，原亏损不改写。

4新臂均保留当前双侧4%费用/滑点模型与固定自身风险规则，独立1000U账户。代码通过不等于已有自然收益，更不等于证明优越。

## 工程与UI

少于10条的既有实际交易查询由串行变成最多2并发，原请求数/顺序/5秒外层期限不变；取满10条仍记录截断为不完整，不补造完整资金流。最近20个实际资金窗口0完整，部分USD转换缺失，免费RPC覆盖瓶颈是真实限制，不把信号0解释成策略无效。WSOL参考失败增加安全HTTP状态和异常类别，禁止输出密钥或URL。

“再次活跃”之前只计旧reawakening入口，漏计pattern机制。现在生产者明确记录新复苏ready（资金门之前），统计端按分钟/币去重；不把普通重复发现算复苏，不回填历史未记录flag。单币检索图和发现图桌面并排，窄屏堆叠；沿用20秒和有界120点。

## 最小验证

已通过：pregrad纯13；运行迁移/补全接线1；无CA纯9；无CA真实Store/Runtime接线2；机会3；真实止损→恢复信号→下一帧5U→不重复消费集成1；新增复苏计数1；RPC两并发/顺序1。JS语法通过。个别失败来自测试状态约束、同快照唯一键和注册数量预期，已修正测试并仅重跑失败项。

部署前20:10Z现有174运行窗口：held fetch P95 13.207秒，apply/exit .053秒；策略工作P95 1.707秒，启动间隔10.344秒。这不是秒级全币SLA，延迟根因及后续改善需实际核对。

## 剩余事项

两篇的全合格持仓共享Vault/Recovery Shadow、DirectLP完整可卖性组合、完整早期持有人/隐藏簇及完整生存风险模型需逐项继续；不可把4新名称抵扣。已确认工程实际损失补款必须独立资本事件、不记盈利、不重复原7518.807662700746U，反事实收益不补造。最终自然样本和性能报告、错误监督状态仍待收口，不提前语音宣布全部完成。

## 后续同批实现：Direct LP、时长风险和真实调度瓶颈

- direct_lp_amount_specific_confirmed_v1：新独立5U；NORMAL_DIRECT、实际完整正资金流和金额广度、固定5M raw USDC买入报价最低输出作为反向原池SELL输入。两腿quote仅预检不是fill；预检后+15秒信号/+30秒下一Dex帧BUY可达，35秒是该新策略预检窗口，不更改公共行情新鲜度。未来转换参考、不一致5M输入、跨腿倒序无效；优先级位于真实待退出之后。3项定向测试通过。
- duration_competing_risk_v1：新独立5U，旧频率模型不改。仅本次部署之前最多1024cohort/256个去重币，按chain×入场流动性分组封存；SELL释放成本从不可变net-realized复原，partial SELL按未结束处理；WRITEOFF使用其账本时间。无需当前mutable closed_at；未来记录不能变成过去标签。开放仓有新鲜原池价作行政截尾，否则明确data_gap，完全没可用原池价排除。每bin至少20样本，5分钟获利终局累计概率需高于损失/核销/失联保守情景之和；已有退出参数保持。不是无偏市场死亡概率，混合旧策略退出和失联相关删失均有限制。原始CIF与失联敏感性分开，不改ledger。真实Store下一帧5U、封存不重训、partial/未来mutable/污染/去重/同刻删失及失联敏感性相关测试通过。
- 方法参考：[lifelines Aalen–Johansen官方文档](https://lifelines.readthedocs.io/en/latest/fitters/univariate/AalenJohansenFitter.html)，竞争事件不能简单作普通删失；本项目使用离散时间风险集计算，不增加依赖。报价数量语义参考[Jupiter官方quote](https://developers.jup.ag/docs/swap/v1/get-quote)。参数为可证伪实验，不是实证最优值。
- 逐币已买检查EXPLAIN原按definition_version扫历史，三个独立币单次456/94/88ms（非P95，首个可能冷缓存）；新增(definition_version,token_id,arm_id,shadow_cohort_id)覆盖索引。observer逐币yield，新增纯计算计时；held_fetch和observer_fetch_with_wait分开。三项最小回归已通过。
- 精确池6槽共享观察优先held；超过6时至少120秒驻留后公平轮换，每轮最多2个原resolver请求。保留池复用原对象/frontier/双窗，只有新resolver成功才替换；换出清连续性。相关真实Runtime定点测试通过，未扩大API预算。
- 20:46:27Z部署前178：判断周期P95 11.119s/自身1.737s；held获取旧混合口径14.000s、apply .0497s；observer总P95 33.179s。52去重held（Sol48/RH3/BSC1），Sol1失败最大1997s、RH1缺池，仍需查原池覆盖。DB9.94GB/WAL381.8MB/余55.1GB。不得把短窗口或分母改变伪称全部性能提升。
- Lead已ACK C2C-20260906-045000-DURATION-HELD并指出失联非独立删失；采纳每bin失联比例/单独保守情景。该信封手填20:48 cutoff晚于真实20:46–47发送时间，特此更正；实现与样本均使用程序实际UTC，不使用手填信封时间。
- Shared Recovery：复用已有Jupiter预算最后优先级，当前Solana开放仓按token/原池/真实剩余数量合并，30秒以上轮转。真实tokens×mint decimals，而非synthetic units；同额双策略测试仅一次报价；独立shadow_quote_lane不变更旧exit状态，证据kind=shadow/quote_only/is_fill=false，不改现金、PNL或SELL。4%最低输出已计，不重复扣。金额组变化后旧quote不再代表新数量。
- 精确原池补采饥饿：WOFI原J8nqhT4BouweCytSBz4FNgHmzqNAzC6Vv11ZejYnXpS7池1仓20U最后成功20:13:10；20:48:23只读精确HTTP200仍有同池价，但RH重复missing每10秒到期，总先选字典首链，Sol长期无机会。改按next_attempt最早到期排序，原一链/30池/10秒预算不变。RH持续缺失仍保证Sol下一tick补采的真实Runtime测试通过。该币另17仓340U原PumpSwap池持续新鲜，不能把18仓都算漏采损失。部署后观察新行情退出，不倒填该公开查询。
