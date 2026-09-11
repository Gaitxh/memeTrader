# 持仓单币检索耗时曲线“断线”诊断（2026-09-12 03:1x 本地）

用户观察：总览面板「持仓单币检索耗时」在 02:24:30–03:12:20 之间，左段有采样、中段是一条几乎笔直的平线、右段又出现尖峰，看起来像系统中断。

结论：**不是进程中断、不是崩溃、也不是行情接口停摆**。该曲线只在主通道真正发起检索的 10 秒桶内产生数据点；中间三段（02:38–02:48、02:51–03:03、03:07–03:11）主通道没有任何检索目标，因此没有采样点，前端把相邻两点直接连线，跨 10–13 分钟的空档就被画成了一条直线。

## 1. 曲线数据来源

- `RuntimeTiming.observe_retrieval()`（`src/memetrader/runtime_timing.py`）：把每批检索耗时按币数加权写入 `int(observed_at.timestamp()) // 10 * 10` 桶，最多保留 120 桶。
- 只有 `Runtime._refresh_chain_meme_market_marks(..., high_priority=True)` 会调用它，即 `chain_meme_market_marks_once()`（间隔约 1.3 秒）。
- 该通道的目标集来自 `Store.chain_meme_trader_market_mark_targets()`：`OPEN_POSITION` ∪ `PENDING_INTENT`（ready/retry/submitted 且在期限内）∪ 最近 120 条 `admitted` 且未终结、未持仓、仍在 `max_signal_to_execution_start_seconds`（默认 120 秒）期限内的入场决策。
- 前端 `renderRetrievalCurve()` 直接把这些点按时间连线，没有任何空档处理。

**目标集为空 → 不发请求 → 不产生桶 → 曲线无点**。这是设计行为，不是故障。

## 2. 实测证据

### 2.1 当夜曲线（DB `runtime_timing_latest.payload_json.held_retrieval`，UTC→本地 +8）

| 本地时间 | 链 | 缺口 | 币次 | 耗时 |
|---|---|---|---|---|
| 02:25:50–02:38:10 | robinhood | 每 10 秒连续 | 3–9 | 0.25–2.25s |
| **02:38:10 → 02:48:50** | — | **640s 无点** | — | — |
| 02:48:50–02:50:20 | robinhood | 每 10 秒 | 3–8 | 0.45–1.28s |
| **02:50:20 → 03:03:00** | — | **760s 无点** | — | — |
| 03:03:00–03:06:20 | solana → bsc | 每 10 秒 | 1–9 | 0.29–4.15s（4.15s 为单币批次） |
| **03:06:20 → 03:11:20** | — | **300s 无点** | — | — |
| 03:11:20–03:13:40 | bsc | 每 10 秒 | 2–8 | 0.28–1.64s |

### 2.2 空档与"目标集为空"逐分钟吻合

按 `chain_meme_trader_market_mark_targets()` 的同一判定重建当夜目标数（本地时间）：

| 时间 | 目标 | 曲线 |
|---|---|---|
| 02:20–02:26 | 5（多个 OPEN） | 有采样 |
| 02:27–02:38 | 1（robinhood 持仓，02:38:14 平仓） | 有采样 |
| 02:39–02:48 | **0** | **空档 640s** |
| 02:49–02:50 | 1（02:48:53 admitted robinhood，120s 期限至 02:50:53） | 有采样（止于 02:50:20） |
| 02:51–03:03 | **0** | **空档 760s** |
| 03:04–03:06 | 1→3（03:03:07 solana、03:04:52 bsc 两条 admitted） | 有采样（止于 03:06:20） |
| 03:07–03:11 | **0** | **空档 300s** |
| 03:12–03:13 | 6（03:11:23 bsc 持仓 + 3 条 admitted，03:13:47 平仓） | 有采样（止于 03:13:40） |

采样段的起止时间与持仓/待成交决策的有效期逐分钟对齐，空档段目标数恒为 0。

### 2.3 进程与采集在空档内持续工作

- 进程自 2026-09-11 21:24:32 启动后一直运行；`data/logs/paper-supervisor.log` 最后一条重启记录即 21:24:27，此后无重启；`data/logs/runtime-crash.log` 仍停留在 2026-09-03。
- 第一个空档（18:38:20–18:48:40Z）内后台写入 `token_snapshots` 1,489 行、`chain_meme_trader_v6_entry_evaluations` 1,491 行，与相邻分钟速率一致（约 150–200 行/分钟）。
- 曲线上的 4.15s 峰值出现在 03:05:00 的 bsc 单币批次，是单点尾部延迟，不是系统性变慢；其余桶均在 0.25–1.3s。

## 3. 真实缺陷：曲线把"没活干"画成了"有测量值"

虽然系统本身正常，但面板确实会误导：

1. 折线跨空档直接连线，视觉上像数据中断或停顿；
2. 页脚"最低 0.22 秒 / 最高 4.15 秒 / 120 个后端快照点"是对**有采样的桶**统计，却与"10 秒聚合"一起读会以为覆盖整段时间；
3. 无法区分"无标的、未检索"与"进程停止采样"。

## 4. 已实施的修复（不改采集频率、不加请求）

- 后端 `runtime_timing.py`：`observe_market_targets(counts, observed_at=...)` 每个周期给当前 10 秒桶打点（即使目标数为 0），桶记录 `targets`；快照新增 `retained_points` / `sampled_points` / `idle_points` / `window_seconds`，每个点带 `targets`。
- `runtime.py`：`chain_meme_market_marks_once()` 调用处传入 `observed_at=utcnow()`。
- 前端 `app.js`：新增 `retrievalCurveChart()`，按空档断开折线；灰带＝该时段无标的未检索，黄带＝该时段完全没有计时点；未检索时头部显示"当前未检索 · 最近一次 X 秒，Y 秒前"；页脚显示"有效采样 n/N 桶 · 当前标的 k"。
- `index.html` 面板说明、`styles.css` 空档样式同步更新；保留窗口现在是连续 120 个 10 秒桶（约 20 分钟真实时间），与面板文字一致。

## 5. 验证

- `tests/test_runtime_timing.py` 新增空档用例（1 采样 + 3 空闲桶；同桶重复打点不新增；不传 `observed_at` 时保持旧行为）PASS。
- `tests/test_held_priority147.py` PASS；`node --check app.js` PASS。
- Node 隔离用例：3 段折线 + 1 灰带 + 1 黄带、全空档输入无 NaN → PASS。
- 03:40:36 经 supervisor 重启加载；`/api/discovery-activity` 返回 `bucket_seconds=10 retained=5 sampled=5 idle=0`，每桶 `targets` 与 `target_supply`（3 OPEN）一致。
- `tests/test_web_backend.py` 8 项失败与本改动无关：本机 Windows 代理绕过表含 `[::1]`，`import httpx; httpx.Client()` 在无任何项目代码时即抛 `InvalidURL: Invalid port: ':1]'`。

## 6. 仍未回答的问题

- 主通道长时间没有目标（当夜约 58% 的 10 秒桶）本身说明持仓/待成交机会稀少，这与"交易少"的经济结论一致，需要更长的自然样本才能评价，不在本轮结论内。
- 曲线只保留最近 120 桶且仅存于内存，无法回看更早的夜晚；如需长期审计，需要另行决定是否落盘（本轮未做）。
