# API互补与发现曲线阶段

## 问题与改动

- Gecko新池响应已经包含行情，但原路径只登记Token，之后必须等Dex补全；Robinhood大量无Dex池记录浪费补全额度。现在复用同一次响应的完整池身份和行情，写原有snapshot/funnel，标记geckoterminal来源，不额外比价。
- 用户提供CoinGecko Demo/Jupiter Free密钥。用现有Windows DPAPI加密，保存在Git忽略的本机data路径；不进入配置API、报告或提交。环境变量仍可覆盖。
- Jupiter沿用现有只读quote客户端和串行速率器，认证后1.05秒请求起始间隔。未提供taker，不生成/发送交易。
- CoinGecko只查询Dex缺失/失败的原入场池；10秒独立任务，最多30池/次，同池至少60秒，队列最多300。主持仓获取不等待补源。每日240/月8000次本机预算持久化，错误请求也计费；429退避，401/403进程内停用。余额数字仅本机预算，非声称该账号其他应用消耗已知。
- 补源缓存保留原接收时间，同时间不推进样本序号；身份不匹配不接受。CG未列出池不是撤池证明。已确认CG覆盖的池缺Dex数据时记源覆盖失败而不是据此核销。
- 发现曲线独立20秒更新，以每分钟首次本地发现和每分钟达到复苏门槛的去重Token计数，含因资金不足未下单的复苏机会。ALL显示三链曲线；不是146份策略投影、不把重复曝光算再次活跃。
- 曲线查询只读取最多20,000 rowid尾范围，缓存不执行额外SQL；不足完整小时则缩短显示开始点，不能伪造缺失时间为0。不增加运行后台定时历史扫描。

## 验证

- 实际Jupiter只读quote HTTP200，无transaction；CoinGecko ping与Robinhood指定池批量接口HTTP200、返回1池。没有做跨源价格一致性检验。
- `test_market_api.py` 8项通过；Runtime补源集成5项和相邻held/Gecko路径合计8项通过。错池回归曾真实失败，修正原池绑定后通过。
- `test_discovery_activity.py`通过，验证首次去重、复苏事件不受现金门影响、重复策略不计倍、缓存命中无SQL。JavaScript语法通过。
- 同批amountful SPL实际成交解析的59项定向测试由子Agent完成，包含真实公开交易形态；不增加RPC次数。market_flow和capital纯模块的测试不代表这些新策略已注册。

## 限制与部署

CoinGecko免费源不是秒级报价源，补源只能改善覆盖，不能保证所有持仓秒级新价格。数据缺失仍为UNKNOWN而非伪造0。Jupiter token级价格不能当作精确池可卖证据；本阶段没有增加Price轮询。

部署前16:12Z（北京时间00:12）126个持仓不重复Token，Sol100/BSC11/RH15；一RH原池数据年龄352秒。最近窗口持仓轮间隔P50/P95=3.27/12.94秒，策略轮1.01/2.22秒，held应用退出P95=.092秒；外部HTTP长尾仍是真实瓶颈，不声称原系统所有行情秒级。

本文件初始提交时部署待执行；之后追加实际验证。旧策略和账期不重置。全部新增策略、最终计算/资源复核及故障补偿仍在继续，不宣称整个用户目标完成。

接口依据：[CoinGecko Demo pools](https://docs.coingecko.com/demo/reference/pools-addresses)、[CoinGecko密钥](https://docs.coingecko.com/docs/setting-up-your-api-key)、[Jupiter plans](https://developers.jup.ag/docs/portal/plans)。具体账号有效额度以供应商后台为准，不自动购买。
