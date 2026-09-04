# ERR-20260905-006：持仓行情固定 600 目标导致尾部饥饿

状态：`FIXED`

## 1. 事件

- 组件：`chain-meme-market-marks`
- 类型：调度公平性与行情覆盖缺陷
- 发现时间：`2026-09-05 05:00 +08`
- 直接证据：活动 v22 一度有 1,077 个不重复开放 Token，其中 163 个没有任何 market mark；目标查询固定执行 `ORDER BY token_id LIMIT 600`。

## 2. 根因与影响

固定按 Token ID 取前 600 个会反复选择相同目标。开放 Token 超过 600 后，字典序尾部可能永久得不到 DexScreener 行情，进而使持仓实时 PNL、动态退出和池状态判断延迟。这是公共行情调度缺陷，不是策略缺陷，也不是 PNL 公式错误。

## 3. 修复

- 开放持仓优先；同类目标按“从未尝试、最久未尝试、Token ID”排序，保持单轮最多 600 个。
- 仍按同链 30 Token 一次请求，同一 Token 只采集一次后投影给全部策略账户。
- 持仓批次并发由 2 提高到 4；每主机请求起始间隔仍为 0.25 秒，不提高到无界并发。
- provider 超时也记录该批目标的尝试时间，但不改变价格、池状态、持仓或 PNL；下一轮让位给更久未尝试的目标。
- 每个成功批次即时更新 source health，不再等完整 600 目标轮次结束才显示恢复。

提交：`128ecae`、`c06197f`、`de61a83`、`e4aa02d`。

## 4. 验证

- 定向测试证明连续有限页最终覆盖全部开放 Token，且失败批次不会中止其他批次。
- 完整 pytest、`compileall`、online doctor 均通过；SQLite integrity 与 DexScreener/GeckoTerminal/Jupiter 等在线检查均为绿色。
- 生产受控切换保留 127 个策略、全部历史与开放仓位，未初始化、未回填。
- 首次公平轮询部署后，无 market mark 的开放 Token 从 237 降到 4，随后降到 0；最终运行状态恢复为 `running`。
- Runtime 约 73 MiB、Chain Web 约 165 MiB；数据库约 7.02 GiB、WAL 约 333.5 MiB，E 盘剩余约 63.6 GiB，没有 OOM 或磁盘耗尽证据。

## 5. 复发时快速排查

1. 统计活动版本 `open distinct token_id` 与没有 `chain_meme_trader_market_marks` 的数量。
2. 按 `last_attempt_at` 检查 30/60/120 秒以上未尝试目标，而不是只看页面刷新时间。
3. 查看 `chain-meme-market-marks` 的成功/错误心跳；区分 provider 超时和固定目标饥饿。
4. 确认失败只更新 `last_attempt_at/failure_kind`，没有改写有效旧价格、制造 MISSING、SELL 或 WRITEOFF。
5. 若在线 doctor 正常但全覆盖周期仍长，先看不重复开放 Token 数和外部响应时间；不要为追求页面秒刷而取消限速或重复请求。

## 6. 剩余边界

在 1,400+ 个不重复开放 Token 和免费接口偶发超时下，完整覆盖周期可能超过 1 分钟。当前修复保证有限、去重、公平和后台优先，但不承诺外部 provider 的固定亚秒响应；该外部延迟不得解释为策略失败或撤池。
