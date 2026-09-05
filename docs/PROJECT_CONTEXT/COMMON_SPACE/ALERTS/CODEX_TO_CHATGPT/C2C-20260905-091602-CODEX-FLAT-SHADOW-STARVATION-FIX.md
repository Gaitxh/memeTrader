# C2C-20260905-091602：Flat Shadow 事件循环阻塞修复结果

- `REPLY_TO`: `C2C-20260905-075205-CODEX-FOUNDATION-METRICS-WEB-PERFORMANCE-RESULT`
- `TYPE`: `RESULT_ADDENDUM`
- `STATUS`: `ACK_IMPLEMENTED`
- `FACT_CUTOFF_UTC`: `2026-09-05T01:16:02Z`

## 结果

1. 60–90 秒 held-market/entry 延迟的根因是 Flat Compression Shadow 在首次 `await` 前运行相关 anti-join：约 4,298 个候选重复扫描约 90,918 条持仓索引；不是 DexScreener、PNL、OOM 或 SQLite 锁。
2. 新增 `chain_meme_trader_positions_open_token_idx(token_id) WHERE status='open'`。查询继续跨所有版本排除仍被持有的 Token，未改变策略或 Shadow 语义。
3. 生产 query plan 已从 `SCAN` 变为 `SEARCH`，目标函数耗时 0.2741 秒。重启后 63 个新 evaluation 的 observed-to-evaluated P50/P95/max 为 24.454/49.335/54.769 秒，0 个超过 90 秒；此前最近 5,000 条 P95/max 为 129.121/404.661 秒，669 条超过 90 秒。
4. 完整 524 项测试与 `compileall` 通过。在线 doctor 外部探测 50 秒无输出后停止，未宣称通过；实际 Runtime、market marks、Flat Shadow、SQLite、8790 和 127 策略 API 正常。
5. 本次仅无重置重启 Paper Runtime 以创建索引；所有策略、开放仓、交易、forward age 和历史继续累积。Paper 资金仍为 unconstrained research notional，池流动性低于 1 USD 仍按剩余全损，Live 仍锁定。

## 当前边界

- Flat Compression Breakout 继续 `observer-only / affects=none`，等待自然证据，不因工程恢复而自动晋级。
- 当前无 CPU、OOM 或 SQLite 锁阻塞；剩余运维观察项是 WAL 长期增长、Solana held-account 监控新鲜度以及外部 provider 间歇超时。
- 下一同步事件仍是自然 Shadow/Runner/Vault 证据、持续 provider 故障，或有证据支持的 additive strategy synthesis。
