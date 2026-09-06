# 持仓采集动态路由增量：SOL/RH 过期与失败

范围：274195c 时序修复部署后，2026-09-06 19:32:57–19:41Z 的现有运行证据；沿 FOUNDATION 18:39Z 基线增量。只读 `/api/performance`、指定 kv/source health/error case、当前资金期开放原池和少数 token 的部署后 history/receipt。SQLite URI `mode=ro`，单 SQL 2 秒 progress 截止，使用主键/既有索引及 LIMIT；没有 Store 构造、生产写入、额外行情 API、测试、重启、全历史聚合或新策略审查。唯一外部文档查询是 HTTP 缓存规范。

## 结论

当前不是泛称的“网络波动”：SOL 大量失败是 DexScreener 完整原池响应缺流动性；RH 大量是主源原池覆盖缺口。公共 Gecko 原池能恢复两者，但部署后持续出现真实 HTTP 429，产生至少 60 秒共享退避；第三路 CoinGecko Demo 已被本地 240 次日预算关闭。另发现一个可以小改、直接影响可取得下一帧的本地延迟：Gecko client 将响应 `max-age=30, s-maxage=60` 取最大值，单用户本地缓存被延长到 60 秒。

建议先修正这个已证实的 TTL 语义，不提高请求并发、不取消限流、不把缺值报价重新计成功、不放宽 15 秒执行有效性。它只能消除额外的本地缓存等待，不能承诺免费源达到 15 秒更新，也未证明因此获得更高收益。

根执行追加：已按上述方式仅选客户端 max-age 并保持 Age/代际/429 限制；最近相关 `tests/test_market_api.py -k public_exact_pool` 4项通过。部署事实由最终发布记录补充，以下为修复前只读调查。

## 运行快照与分母

`/api/performance` 在 19:36:02.311585Z 返回（包含页面定义的在管历史期，不等同仅当前资金期）：

| 链 | 持仓 token | 缺完整历史帧 | 失败 | 主源覆盖缺口 | last_success age P50/P95 秒 |
|---|---:|---:|---:|---:|---:|
| SOL | 101 | 0 | 43 | 19 | 9.18 / 101.51 |
| RH | 24 | 0 | 0 | 20 | 91.28 / 170.20 |
| BSC | 10 | 0 | 0 | 1 | 3.13 / 275.07 |

页面 failure 是任一必需原池的 `failure_kind` 非空且非 coverage gap，不等于一次 HTTP 请求失败。19:37:37 前后只按当前 funding+open 查询，DISTINCT 原池返回133条，LIMIT200未截断：SOL 39完整、43 `DATA_REJECTED:quote_liquidity_unavailable`、20 coverage gap；RH 4完整、14 gap；BSC 12完整、1 gap。这是原池/时点分母，不能和前一 token/多资金期分母直接相减。

19:32:57 的120样本时序：held fetch P95=3.385秒、apply=.092秒，held实际interval P95=4.638秒、main=1.339秒；对应 FOUNDATION 基线为3.233/.072、3.818、1.216秒。当前循环继续推进，不能用相差数百秒的完整帧年龄归因于这几十分之一秒的本地处理变化；持仓数量/构成已变，也不能声称这是新策略导致的性能回归。held retrieval 的 failed_tokens=0只覆盖传输失败，不能推翻43个字段不完整拒绝。

## 实际路由失败与限制

### 主源：缺字段和身份覆盖，而非本窗传输全停

代码事实：`runtime.py:6805–6870` 按冻结原池匹配返回池；有效池清 gap，缺字段保留旧完整帧并排入补源，缺原池写 `DEX_SOURCE_COVERAGE_GAP`。`_held_pool_quote_rejections()` 要求有限非负流动性，不能从价格正数推断 liquidity 存在。此行为修复了此前虚假成功，不应回退。

运行样本：

- SOL `7c3LBvq424f3BCcrnjVdEbh6UFMF3C5ZPRLkKbPcpump`，原池 `9gQvYzcm6hZKnJ88z2PvtAcqTGrdsqzLGngHX2cYcCB1`：19:37:37.846880仍有主源 attempt，但最后完整GT观察19:34:20.791573、接收19:34:20.801634，失败明确为 `quote_liquidity_unavailable`。部署后完整history为2663790@19:25:54、2665460@19:28:14、2668303@19:32:49、2669257@19:34:20，补源确实能给出同原池price=1.3380575974421291e-6、L=1031.1104。
- SOL `4eDBNRGniHYUcQ4Xs1Zf4onTyUM97G8gpLX7qYYdcQHW`，原池 `4D5NX9TScHHfemY8ABg3e94PPEAr1JZY42d1C3ohAiVE`：同次attempt为coverage gap，最后GT完整帧也为19:34:20；部署后选定history仅2663930@19:26:03和2669238@19:34:20。未把无完整history期间解释成链上无交易。
- RH `0x7c32096c11591b68c296eb0339c48d90ea77902b`，原池 `0x14e295482e8a962723b2fc608245c777cae39c77`：19:37:37.753465主源仍gap，GT却已19:37:25.505116恢复完整帧（history2670746），此前2664202/2666542/2668433/2669384分别在19:26:24/19:29:57/19:32:59/19:34:31。这证明“gap”是主源覆盖，不是该池在所有提供方不可见或已死亡。

同原池GT receipt到recorded延迟约6–10毫秒；这里的数分钟间隔主要发生在完整外部帧到达之前，非 SQLite apply 队列数分钟积压。

### 第二路：真实 429 与至少60秒共享退避

`system_error_cases.id=127` 为安全归并的 `geckoterminal:original_pool / HTTPStatusError:429`；部署后已有 occurrence：19:27:07.535810、19:28:40.089571、19:30:16.773844、19:31:40.244531、19:33:19.935099、19:36:15.781104，随后 last_seen19:37:46.113705（累计148含旧窗，不当作本窗148次）。RH discovery case129最新19:34:39，BSC case130最新19:27:03。

`runtime.py:2383–2402` 原池异常、`:2131–2146`源错误处理均按429设置共享backoff至少60秒，尊重更大Retry-After；`_poll_gecko_network()` 在同一backoff期间也跳过。`self.gecko_pools`和new-pool discovery确实共用 `self.http`（1423/1442/2490），`collectors.py:1175`同host请求开始间隔至少2.1秒；不是发现另用了一个无节流客户端。当前保留的错误上下文没有实际Retry-After/上游计数，不能断言其真实quota阈值、他进程/出口IP共享额度或具体每分钟请求量。429本身已是精确外部限流证据，而不是无根据的网络猜测。

### 第三路：本地日预算用尽，不是密钥失效或已证明云端额度耗尽

精确kv `market_api:coingecko-demo:status` @19:36:23.631093：`local_daily_budget_exhausted`，240/240，本月480/8000、剩7520；cache_count=0，cooldown=null、disabled=false、last_error=null，pending_original_pools=95。`coingecko:gap_recovery`最后item仍09:53:31.134333。

`market_api.py:336–347` 本地可用性检查先于请求，`:439`实际发出前计数；本地日界是UTC。故当前每一次第三路跳过都有明确本地预算原因，不应显示为成功补源；也不能把它写成供应商全日quota或要求换key。保留预算本身是授权成本边界，本审查不主张无证据提高240或绕过它。

## 已证实的最小本地改进：客户端缓存误用 s-maxage

生产 receipt snapshot1278586、1278587、1278588、1278589（SOL不同token，同真实补源batch）：provider=`market-entry-confirmation:geckoterminal`，observed=19:35:53.119235，原 `raw.pair.raw.http_cache` 为：

```
cache-control: max-age=30, public, must-revalidate, s-maxage=60
age: null
date: Sun, 06 Sep 2026 19:35:53 GMT
generation_reused: false
local_cache_hit: false
received_at: 2026-09-06T19:35:53.119235Z
```

代码事实：`market_api.py:232–239` 收集max-age和s-maxage后取max，因此该真实响应的本进程TTL=60秒；`:214`在到期前直接返回旧帧。这个程序是单用户client，不是多用户代理共享cache。RFC9111规定先考虑s-maxage的条件是共享缓存，否则max-age；`public`允许缓存存储，不会将应用本地cache变成共享代理。[RFC9111 §4.2.1](https://www.rfc-editor.org/rfc/rfc9111.html#section-4.2.1)、[§5.2.2.10](https://www.rfc-editor.org/rfc/rfc9111.html#section-5.2.2.10)。

最小改法：原分支 `name.lower() in {"max-age", "s-maxage"}` 改为仅选 `max-age`，保留原Age扣减、无显式值默认30及其余代际语义。真实例子从60秒回到30秒；不是把业务15秒门放宽到30，也不是伪造observed。如果上游此时仍同ETag+同Date，依旧返回原observed，必须继续等待。

最近夹具 `tests/test_market_api.py:184 test_public_exact_pool_client_preserves_cache_generation_and_identity` 已使用相同头且Age5，但错误断言54秒仍cache。定向改为24秒cache hit、26秒实际请求；同代际观察时间不变、新代际才前进。已有`:239 test_public_exact_pool_unchanged_content_with_new_response_date_is_new_observation`继续保证静池新Date不被无限冻结。无需新fixture项目、宽测试或新的缓存层。本代理只提出定位，未改代码或运行测试。

改善边界：可消除最多额外30秒的本地缓存强制等待，但重查可能仍遇到CDN相同代际或429，并可能增加实际请求频率；同host pacing/backoff必须保留，部署后只比较一个同负载窗口的完整帧年龄与429增量，不以缓存命中次数或成功HTTP数宣告实时性改善。

## 排队与尚未核验项

`runtime.py:2314–2344`每次只取最早到期的一条链、最多30池，然后next_attempt+10；`:8177`本任务10秒周期。95个pending至少4批，在静态无移除情况下遍历一轮至少约40秒，分链碎片还会增加批数；覆盖缺口进入精确DS60秒、GT共享backoff、Demo60秒的独立到期分支。既有due排序及 `tests/test_market_api_runtime.py:758` 已避免永远卡在同一条缺覆盖链，未找到已证实的无限饥饿/队列对象更新丢deadline（旧对象复用已存在）。

95个是运行队列总量，未导出进程内每项deadline，因此不能把每个样本的分钟级缺口精确分摊成缓存/429/轮转各多少秒。也没有证据支持直接全链并发或全批每10秒重试；这会增加限流风险。当前可以先做上述单点TTL修复，保留现有公平轮转和公共预算。待实际证据确认某个急需退出池被无可用路由的chunk占位，才考虑已有队列按可尝试源/实际待退出优先；本次不借此建设新scheduler。

当前部署out/err文件均0字节；`runtime-crash.log`最后修改2026-09-03，尾部旧TypeError不是本轮崩溃证据。19:37Z主持仓/主交易心跳继续，最近主源market异常时间仍18:16Z；本窗与持仓刷新直接有关的已记录异常集中于GT429。`/api/performance.sources`目前只列GT discovery，没有exact-pool/Demo路由，因此仅看该sources字段会漏掉本次根因；这属于诊断覆盖说明，不是必须再建UI或监控功能的要求。
