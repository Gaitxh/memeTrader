# 修复部署后的有限自然验收

范围：根代理提供修复代码 `03ace85`、重启 `2026-09-07T05:14:03.4322224Z`。只检查 `477064 < trade.id <= 477096` 且 created_at 不早于部署的 **32 笔**，成交时间 `05:14:45.227217Z–05:15:18.481823Z`。按初次观察的上限固定样本，没有循环等待更多交易，也没有重做全历史审计。逐笔证据见 [NATURAL_REPAIR_ACCEPTANCE.json](NATURAL_REPAIR_ACCEPTANCE.json)。

| 检查 | 实际分母 | 结果 |
|---|---:|---|
| BUY / SELL / WRITEOFF | 30 / 2 / 0 | 保留零核销分母 |
| BUY：post observed > 原 signal decision | 30 笔，5 个原 signal evaluation、7 个 cohort | 30 通过；间隔 13.047440–27.555056 秒 |
| SELL：post observed > pending trigger | 2 笔 | 2 通过；间隔 2.134975 / 0.956906 秒 |
| 本窗完整终结仓位：净回款−成本=PNL | 1 仓 | ledger 与 position 均一致 |

BUY 全部是 pattern 路径，decision 取 `chain_meme_trader_v6_entry_evaluations.evaluated_at`，由 cohort 冻结的 `fill_signal_snapshot_id` 找到；post observed 取明确 receipt snapshot。没有把后帧到来后的 cohort allocation 时间当作先前 decision。**主入口 immutable entry receipt 路径在本样本没有自然 BUY，仍未自然验证。**30 笔 BUY 共用 5 个 signal，不是 30 个独立市场实验。

SELL `477084` / fill `222127` / mark `241775`：pending `05:14:45.079643Z`，post observed `05:14:47.214618Z`。SELL `477096` / fill `222128` / mark `241776`：pending `05:15:17.522896Z`，post observed `05:15:18.479802Z`。trigger 用 mark 原 `recorded_at`，observed 用其 `post_confirmation.observed_at`，两笔均可恢复。

完整闭仓：`common_funding_adjusted_breadth_5u_v1`、cohort `53246`、BUY `476952` → SELL `477084`；净回款 `6.362811358154421U` − 成本 `5U` = `1.362811358154421U`，与 ledger/position realized PnL 一致。另一 SELL 不计入本固定窗口的新完整闭仓分母。核销没有自然样本，不宣称验证其部署后行为。

## 错误保留与 observer 范围归因

在 `05:19:17Z` 的有界错误尾读取中，最近 128 条 occurrence 最早 `03:47:59.515514Z`，覆盖部署起点；其中部署后 **14 条**，包含上游 HTTP 429/HTTPStatusError、RPC/limit 错误及一次 pattern observer TimeoutError。没有出现 NULL observer/TypeError 记录，**不等于零运行错误**。

TimeoutError 为 case **48**，component=`chain-meme-pattern-observer`，本次 occurrence **2534**=`05:16:32.329965Z`，安全上下文仅 `{"source":"chain-meme-pattern-observer"}`。同 case 最初 `2026-09-05T11:35:17.095597Z` 已存在，部署前最近 occurrence **2502**=`2026-09-07T05:04:23.105255Z`，同样上下文；本次不是新生成的错误类别。

当前 `runtime.py:7176–7182` 对非持仓低优先级补抓使用 `asyncio.wait_for(..., timeout=3)`，捕获 HTTPError/TimeoutError 后记 heartbeat，继续已有 targets。结合上述 component/错误类型，本条证据对应**被处理的源请求/observer 预算超时**，不是未捕获的 NULL observer 或本地计算崩溃；不能据此断言底层网络根因或保证后续不超时。该补抓路径本轮未改，归因亦由根代理独立确认。

文件元数据还显示新 Paper stderr/stdout、Web stderr 为 0 字节，旧 runtime-crash.log 最后写入在 `2026-09-02T19:59:52Z`；只支持所读时点没有新的该类进程崩溃日志，不证明错误采集绝无遗漏。

## 资源与边界

生产均 `mode=ro`，每 SQL 2 秒截止、显式主键/既有 definition+arm+cohort 索引、短读取；无 Store 构造、DB/应用/运行状态写入。有效验收读取 **77 SQL / 0.0253 秒**，最长 SQL **0.0149 秒**；补充 case48 用 **3 SQL**，最长 **0.0119 秒**。这些精确计数不含前置 schema/源码检查及一次因过大 JSON 输出截断而弃用的读取；弃用结果没有用于结论，随后只保留固定 32 笔的必要字段。

本次没有重新验证所有池身份、被拒机会、未成交原因、当前估值或策略有效性。旧异常交易 **473261/473262 未改写、未纳入修复后样本，仍保留原问题，不能由本次通过消除其历史异常**。结论仅为 32 笔可恢复时序无新异常、1 个完整闭仓账务通过；主入口、核销等未覆盖路径明确未自然验证。
