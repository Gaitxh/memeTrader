# ERR-20260905-008：Flat Shadow 查询阻塞后台事件循环

## 症状

持仓行情批量请求虽然已发出，但 HTTP 响应会集中延迟约 60–90 秒才被处理；新 Token 从 `observed_at` 到 `evaluated_at` 的最近 5,000 条样本 P95 为 129.121 秒、最大 404.661 秒，669 条因超过严格 90 秒时序门被拒绝。DexScreener 单批直连约 1.0–1.2 秒，SQLite 常规读写和账户快照也不是该延迟的来源。

## 根因

`flat_compression_breakout_shadow_once()` 在第一次 `await` 前同步调用 `due_flat_compression_breakout_shadow_targets()`。该查询对约 4,298 个最新候选逐个执行：

```sql
NOT EXISTS (
  SELECT 1
  FROM chain_meme_trader_positions p
  WHERE p.token_id=e.token_id AND p.status='open'
)
```

原有持仓索引以 `definition_version` 开头，不能服务这个有意跨版本的查询。生产计划因此对约 90,918 条持仓索引执行相关重复扫描，连续占用事件循环约 72 秒；同一循环内已经返回的行情响应、退出与新快照评估只能等待。

## 修复

新增最小 partial index：

```sql
CREATE INDEX IF NOT EXISTS chain_meme_trader_positions_open_token_idx
ON chain_meme_trader_positions(token_id)
WHERE status='open';
```

没有修改查询条件，也没有把它缩成当前版本。旧版本仍有开放仓时，Shadow 仍会排除该 Token；策略、PNL、入场、退出、行情频率和严格前向规则均未改变。

## 验证

- 生产 `EXPLAIN QUERY PLAN`：由相关 `SCAN p` 变为 `SEARCH ... chain_meme_trader_positions_open_token_idx (token_id=?)`。
- 生产同一目标函数：0.2741 秒，返回 30 个有界目标。
- 无重置重启后的 63 个新 evaluation：`observed→evaluated` P50 24.454 秒、P95 49.335 秒、最大 54.769 秒；0 个 `entry_snapshot_too_old`。
- `chain-meme-trader`、`chain-meme-market-marks`、`flat-compression-breakout-shadow` 心跳均持续推进。
- 完整 524 项测试通过；`python -m compileall -q src tests` 通过。
- `doctor --online` 在外部网络探测阶段 50 秒无输出后停止，因此未宣称通过；本地 Runtime、SQLite、8790 和关键来源心跳另行验证正常。

## 资源结论与回归指引

验收时 Paper worker RSS 约 83.7 MB，整机可用内存约 5.5 GB；主库约 7.63 GB、WAL 约 349.7 MB、E 盘可用约 64.9 GB，未发现 OOM、SQLite 锁或 CPU 饱和。若同类停顿复发，先对同一事件循环中的同步 Store 调用计时，并检查相关子查询的 `EXPLAIN QUERY PLAN`；不要通过放宽 90 秒新鲜度门或改变策略规则掩盖工程阻塞。

部署期间未重置、清空或回填任何策略、账户、持仓或历史结果；127 个策略继续 append-only 前向运行，Live 保持锁定。
