# 18 个资金与生命周期方向：实现与运行记录

## 范围与边界

本轮按用户补充全部 18 个方向实施，不采用聊天中的“只先做三条”缩减范围。保留原 146 个策略、1000U 资金账期、历史和开放仓；18 个新 ID 从实际部署前沿增量加入，不回填。

这些是可证伪的 Paper 假设，不是已验证盈利策略。新策略普通 20U，Direct LP 5U，独立现金与风险限制不变。入场 +4%、普通退出 -4%；Jupiter amount-specific 最低输出已含 400bps，不再重复扣 4%。Live 不开启。

| 方向 / 独立 ID | 实现与实际输入 | 覆盖限制 |
| --- | --- | --- |
| vault_hazard_v1 | 两份原池 confirmed-slot Vault 净流出证据，触发后再取实际余仓数量报价退出 | 当前 exact PumpSwap / Solana；不是 Dex 屏幕价成交 |
| earn_the_hold_v1 | 新池宽入口；60–120秒后用价格、实际资金流和原池流动性审核继续持有 | 真实转账金额输入可用的观察池 |
| failed_continuation_profit_lock_v1 | 盈利100%先兑现一半，真实回本后两帧弱化退出 | 不把 partial 意图当已收回本金 |
| wave_reset_reentry_v1 | 已实际平仓后10–240分钟的新资金流、流动性重建和结构重夺 | 仅当前有界观察覆盖，未承诺全币持续四小时扫描 |
| migration_absorption_v1 | 确切 canonical migration、先冲高回落，再观察吸收/卖压衰减/深度重建 | 不是“迁移后等几秒就追涨” |
| executable_recovery_decay_v1 | 实际 mint 精度和余仓量的最低可执行回收率，运行高点回落触发 | 每仓估值不快于30秒；退出任务优先，另取触发后报价 |
| capital_velocity_v1 | 实际资金流速率、金额加权广度和集中度 | 当前已毕业池版本；毕业前付费流单独受限，不能冒充完整 pregraduation 捕获 |
| effective_breadth_v1 | 按真实买入金额计算有效地址数及最大地址份额 | 地址不是独立自然人 |
| price_to_flow_fragility_v1 | 45–75秒前价格基准与当前涨幅、实际资金流/深度/广度背离 | 做持仓退出，不做不支持的空头 |
| churn_resistant_v1 | 实际成交金额中位数、小额买入金额占比、净资金流 | 不用交易次数替代资金流 |
| creator_early_holder_distribution_v1 | 官方 Pump create 指令验证的 token creator 卖出金额与两帧市场弱化 | Pool.creator 不等于 token creator；全量早期持有人/隐蔽身份未覆盖 |
| bundle_adjusted_breadth_v1 | 按实际同一 transaction 原子交易组重新计算广度 | 未公开跨交易 bundle 仍 UNKNOWN |
| finite_capital_ranker_v1 | 同轮实际资金流、价格、流动性百分位排名；前三名、最多三开放仓 | 至少两个有效观察对象；非全市场排名 |
| market_regime_throttle_v1 | 同轮观察池价涨且净流入广度、流动性健康比例 | 观察池横截面，不冒充全链情绪 |
| competing_risk_v1 | 真实已闭合净账本的盈利/核销/普通亏损，按链和入场流动性封存分组 | >=20个去重复 Token；closed-only 经验终局频率，不是因果生存模型；缺路线观测不写0 |
| high_recall_exit_pipeline_v1 | 宽入口→Earn Hold→真实分批回本→两帧 Dead Wave→平仓后新 Wave Reset | 下一帧卖价变化导致回本不足时重新审核，不卡死等待虚构回本 |
| direct_lp_float_constrained_v1 | 完整 NORMAL_DIRECT Pool PDA/LP/Mint/Vault 实证、池占供应量、5U小仓 | 缺 migration 不是 direct 证明；LP持有集中度不是锁仓证明 |
| authoritative_event_shock_v1 | 匿名官方 OKX 公告、明确 explorer 合约地址、下一份原池行情入场 | 每120秒最多两篇文章；无CA/多CA歧义只记诊断，不瞎匹配 |

## 输入与成本

- 复用既有 Pool/Vault accountSubscribe、最多6个 exact观察池；surface每15秒最多一池、每池至少60秒。
- 实际 transfer 参与采集每15秒最多两池，最多两份相邻完整窗口、每窗口128条交易。缺失、截断和乱序不得变成完整资金流。
- WSOL→USDC 单位换算参考每30秒最多一次，共享已有 Jupiter 后台预算；参考价格不是实际 Token 卖出价。
- exact quote lane 每2秒最多一任务、共享3次/5秒后台预算；持仓主采集优先，普通估值30秒、待退出2秒重试。
- 官方事件先写不可重复的 URL+发布时间+CA，再进入已有 hydration 队列。没有重复轮询刷新旧事件时间。
- CoinGecko/Jupiter 凭据仅本机 DPAPI 密文；本报告及 Git 不含密钥。

资源证据：PumpPortal 新币/迁移公开通知可以继续使用；逐笔 Token/Account trade 需要付费 key 和关联余额。官方[费用说明](https://pumpportal.fun/fees/)与[数据接口说明](https://pumpportal.fun/data-api/bonk-fun-data-api/)列明此限制。本轮不充值或购买，因此毕业前完整资本流策略保留资源限制，已毕业资本流实验独立明确标注。Creator 身份以官方[Pump IDL](https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump.json)指令证据为准。

## 系统性能与验证

发现已有 Flat Shadow 全期 latest-evaluation GROUP BY 单次同步查询1.226秒，会占用主事件循环。仅移动该只读查询至独立连接/线程，保留SQL和业务语义；新竞争风险封存查询约6.3秒也只在首次部署后台读取一次，重启复用已封存模型，不在持仓主循环训练。没有大架构改造。

最小相关测试：18注册幂等且旧146/hash/frontier保留；官方事件和Direct LP先意图后新帧20U/5U真实记账；closed601秒再入场且开放仓不重复；Earn真实金额触发→新原池帧退出；exact real raw amount、数量epoch、部分退出成本/最低输出/幂等；模型无未来/污染/重复样本；只读后台线程不挡事件循环与写连接。4%双侧独立算例通过。上线状态另记，不把单元测试或注册数量冒充自然收益。

## 工程补偿边界

此前已确认并到账7518.807662700746U（7440U异常dust入场本金，78.80766270074568U四笔目录漏采实际净损失），不重复。

新增只读候选 cohort12154：真实BUY ledger411232 / 411233，原池9Hn6MBrAYPm8b9RutSsxSr2nGorQRyvJwNgSaQgo22Hb；TP触发至确认约77秒，后续核销，净损约9.182193U / 20U。另12143、12146、12147出现108–126秒延迟。它们证明延迟与亏损共现，尚未证明反事实可成交回收额或明确漏采原因；不能凭之后峰值重写收益或直接认定所有亏损为工程赔款。仍开放仓剩余成本是stake-allocated_cost，不是allocated_cost，未实现亏损与实际已确认工程损失分开。

## 部署验收

1211a42 已推送并于17:21:34Z受控部署。18臂于17:21:37.883917Z–17:21:38.110312Z、快照前沿873998增量注册，现164策略，原资金账期与旧146保留。尚无新臂自然成交不能当作策略失败或盈利验证。

17:26实际输入核验：Pool/Mint/Vault surface已完整落库，资金流窗口仍有超过10签名的预算截断及非截断解析失败。针对一笔成功链上BUY取证，真实指令24bytes，旧parser只认25bytes，导致完整交易被丢弃；已按官方可选track_volume兼容24/25bytes，25byte仍验证合法bool，SELL/身份/实际transfer约束不变。真实quote成交raw21224，而指令上限21500，测试没有把二者混淆。parser相关51项通过。

Creator获取失败此前只留内存且永不重试，现写已有证据表，并仅对HTTP/超时允许60秒后一次重试。WSOL参考成功/失败写已有心跳；独立调度每5秒寻找空闲，但实际外部请求仍不快于30秒、共享预算不变。17:37Z一次实际Jupiter只读报价0.661秒成功，不生成交易。Origin/WSOL相关5项通过。入场批次/账户快照分别纳入已有计时，以定位剩余长尾，而不是把所有卡顿归咎外部API或PNL。

未恢复自动两小时复盘。上线后继续确认输入覆盖与核心延迟；完整成果与外部资源限制分开说明，不把WAIT-only伪称经济验证。

17:41分段测量账户快照P95约0.60s、入场批次P95约3.68s，一轮可能连续8批。因此不能用“单批不到15秒”排除入场阻塞。实际查询计划显示，即使待买单为0，pending_by_arm的join仍先按全部历史entry_decisions逐项查订单，单次0.987秒；现明确0待单时空预留，跳过联查，非零待单算法不变。无待单不扫描且自然20U入账/独立余额门2项回归通过。

独立生产核算：旧策略broad_cost_coverage_scaleout_v1/cohort12309于17:30:07BUY、17:30:22HARD_STOP，未受纠正/污染/补款。信号1.59e-6→买价1.6536e-6（+4%）；20U所得12094823.41557813 Token，后续原池9.082e-7×数量×.96回收10.545137880986937U，净亏9.454862119013063U。账户现金21.76016655405→1.76016655405→12.30530443504，快照一致；该账户此前340U补款未混入PNL。

cohort12154进一步取证：触发至首份留存合格原池post-frame77.267秒，但新帧出现后0.924毫秒即fill、9.717毫秒后trade落库；中间有行情但属于另一池，不能代替原池执行。当前不能确证内部成交故障或更早可成交价，因此不追加赔款，不把缺失证据解释成健康证明。
