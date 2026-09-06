# Gecko 原池响应时效修复

## 问题与证据

持仓原池行情曾出现 BSC 数据年龄812–843秒，而主持仓采集约1秒。具体池为 `bsc:0x241950fa9411804556e3511d290c5e335fc8ffff`：Dex返回带`:4meme`后缀的场所且没有流动性，不能直接替换原池。CoinGecko Demo本地日预算已耗尽，Gecko公开精确池是可用补源。

两次有界公开请求均HTTP200、同一精确池、liquidity=3515.1741：响应Date分别为2026-09-06 10:59:20和11:07:25 UTC，ETag均为`W/"2d5bbc9a88d38f6c56807834d803b88e"`。旧客户端只要ETag不变，就无限保留首帧observedAt，把内容没有变化误判为始终没有新响应。

## 最小修正

同时有ETag和Date时，只有二者均未改变才继续沿用旧观察。Date推进的真实HTTP响应即使内容相同，也成为新的本地API观察；本地缓存命中和同一响应缓存仍保留原时间。没有Date时保留原ETag保守行为。未放宽原池/Token身份，不剥离`:4meme`后缀，不填造流动性、不提高额度、不追加轮询。

ETag是表示内容的验证器，不是行情年龄。依据：[RFC9110 ETag](https://www.rfc-editor.org/rfc/rfc9110.html#section-8.8.3)、[RFC9111响应年龄](https://www.rfc-editor.org/rfc/rfc9111.html#section-4.2.3)。新的API观察也不等于链上价格发生了新交易；不能宣称外部供应商数据完全实时。

## 验证与范围

`pytest tests/test_market_api.py -q -k 'public_exact_pool_client or public_exact_pool_unchanged_content'`：4个实例通过，包括恒定ETag/推进Date、旧响应不更新、本地缓存不更新、池身份及429不重试。

该修正不改变策略参数、历史PNL、账户余额和100美元共享池门槛。代码检查通过；实际部署与数据年龄变化在本轮联合运行验收记录，不把测试通过等同运行已恢复。
