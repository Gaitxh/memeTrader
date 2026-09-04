# ERR-20260905-007：基础指标与 Web 负载修复

## 范围

本报告只记录本轮已证实并已实现的基础指标、仓位展示和 Web 负载事实。未改变 Paper 合同、行情采集合同或交易资格判定。

## 已证实问题与根因

1. `correction ∩ contamination` 的仓位在终局计数路径中可能被重复纳入。该交集属于已污染账务：不能进入经济统计，但必须保留原始记录和审计标记，不能通过删除记录掩盖。
2. 最大回撤曾从受 UI 展示点数限制的 `curve` 计算。展示曲线被截断后，峰值和回撤美元值会随展示窗口变化；同时对无固定本金的 unconstrained/funding-model 显示资本百分比会制造伪分母。
3. compact Web 返回的“剩余数量”使用了 synthetic/raw 数量字段，用户看到的不是 Token 数量。
4. `/api/live` 冷汇总会处理约 53k positions，实测约 2.8–4 秒；compact cache 的 TTL 从 1 秒到 6 秒时，前端 5 秒轮询约隔次命中缓存。该延迟发生在 Web 汇总层，后台行情周期不受影响。
5. 未采用 amount-specific capacity gate。当前 Paper 合同要求 DexScreener 池/价格可见且 `liquidity >= 1`；流动性低于 1 美元的仓位按全损处理，因此额外的 amount-specific gate 不属于当前合同的必要条件。

## 修复

- 污染交集终局不计入正式指标，同时保留仓位、交易和 contamination 审计信息。
- 最大回撤改为完整有效 `terminal_pnls` 按终局时间累计的 realized-PNL 序列；美元回撤不再依赖截断 UI curve。增加 `max_drawdown_basis=realized_terminal_pnl`。只有 `legacy_cash_limited` 使用固定本金计算回撤比例；unconstrained/funding-model 的 `max_drawdown_fraction` 为 `None`。
- compact `open_positions` 返回 `paper_quantity_tokens` 与 `remaining_quantity_tokens`；UI 的“剩余数量”展示 Token quantity，不再展示 `amount_raw`。
- 保持 `/api/live` 与后台行情采集解耦；本轮未引入 amount-specific capacity gate。

## 验证

- 定向 Web backend 回归：回撤、compact open positions 通过。
- `python -m py_compile src/memetrader/chain_web.py` 通过。
- `node --check src/memetrader/chain_web_static/app.js` 通过。
- 完整 suite：100% 通过。
- `python -m compileall -q src tests` 与 `node --check` 通过。

## 回归指引

- 用包含完整终局序列且 UI curve 超过展示上限的 fixture，验证最大回撤美元值不随 curve 截断变化。
- 分别覆盖 `legacy_cash_limited` 与 unconstrained/funding-model，确认只有前者有固定本金回撤分母。
- 验证 compact payload 的 `remaining_quantity_tokens` 与 UI 展示一致，并保留 `amount_raw` 仅作底层审计字段。
- 构造 correction 与 contamination 同时命中的仓位，确认正式计数排除、审计详情仍可见且不重复计数。
- 冷缓存和热缓存分别测量 `/api/live`；确认前端刷新节奏变化不改变后台行情采集周期。
