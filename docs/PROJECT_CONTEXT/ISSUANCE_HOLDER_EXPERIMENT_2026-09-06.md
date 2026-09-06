# 发行创建后持有人派发：独立5U前向实验

## 问题与假设

原有首次观察买家策略只封存进入观察后的BUY签名地址，无法知道发行时已分配给谁。
现有token_origin已经一次性取得精确Pump创建交易，却只提取creator参数。
因此本实验复用同一响应的发行后余额，检验这些owner后续实际派发是否提供不同的退出信息。
这不是盈利结论，也不替换原creator或首次观察买家策略。

## 已冻结规则

- 新ID：`issuance_holder_distribution_5u_v1`；独立1000U Paper资金、单笔5U，保留自身资金与风险限制。
- 输入：精确已验证Pump create/create_v2；原mint创建前余额必须为零，SPL Token/Token-2022净MintTo减Burn必须等于同交易全部post token balances之和；时间、slot、owner、账户索引或parsed指令不完整则UNKNOWN。
- 记录完整owner余额、原始单位供应量、slot和签名；已验证曲线PDA及其他off-curve owner单列。不是LP持有人，不是全市场top账户，也不推断隐藏控制。
- 交易子集最多32个正余额on-curve owner；后续只匹配owner本人签名的已抓实际SELL。代理交易、托管和隐藏资金关系不冒充已覆盖。
- 入场：该策略激活以后首次取得的完整origin，真实金额流完整、新鲜、同池同币，池龄0–900秒且已有至少3笔买卖，再等下一独立原池帧买入。
- 派发退出：连续两个已观察非重叠窗口，匹配SELL至少100U且占总SELL至少35%，净流不正、深度衰减至少10%、有效广度衰减至少20%，触发退出意图；随后独立新鲜原池帧成交。
- 保留继承的止损/分批兑现/最长持有退出及共享100U原池门槛（用户最新修订）、双侧4%成本。旧策略定义不动。
- 创建交易的blockTime是历史事件时间，新的observed_at/recorded_at是实际取得时间。只在后者之后决策，禁止向旧决策回填。

## 成本与覆盖边界

不新增RPC请求、定时任务、订阅槽位或全链账户扫描；仅解析原有最多6池低优先级origin通道的一次交易响应。
原有已缓存56条origin不回查补录；新输入依靠自然进入通道的对象。仅适配已解析SPL supply指令，其他格式记录UNKNOWN。
入口使用现有索引有界取token_origin，退出在同轮同池共用读取；无高频历史聚合。

## 验证与评估

子任务token_origin定向14项通过；整合owner pubkey/on-curve/PDA与slot约束后，受影响10个解析实例通过。
新策略时序/完整性边界、旧首次观察买家对照与新实验完整5U下一帧BUY→两窗派发→下一帧SELL共3项通过。
其中旧派发测试的正常深度由1000→800更正为10000→8000，以保留20%衰减且不再与新的1000全损门槛冲突。

后续评价必须区分输入覆盖不足、正常未触发、自然交易和扣成本结果；不是以测试通过证明赚钱。
18:01:10.146383北京时间在真实snapshot frontier1044784加入，新总数189。
原61项追加定义/activation/frontier/全部行哈希保持69e5329e717a5796669528c21f96f87769e082ca707294582bde68a451bfc1ce不变；
原127基础定义未编辑，原资金期保留。没有新数据回填、历史交易作废、补款或账户初始化。
原始规则先冻结，任何进一步规则变体等用户下一轮方案确认，不自动部署。

来源：[Solana交易元数据](https://solana.com/docs/rpc/json-structures)、
[Mint语义](https://solana.com/docs/tokens/basics/mint-tokens)、
[Burn语义](https://solana.com/docs/tokens/basics/burn-tokens)。
