# runtime_timing_latest 结构（供运营与审计解析使用）

来源：`kv`/`runtime_timing_latest` 无法直接读，实际是表 `runtime_timing_latest` 的 `id=1` 行，`payload_json` 为 JSON。2026-09-12 实测结构：

```json
{
  "generated_at": "...",
  "components": {
    "<task name>": {
      "duration_seconds":          {"p50": 3.42, "p95": 3.42},   // 本任务每次执行的耗时
      "actual_interval_seconds":   {"p50": 15.03, "p95": 15.03},  // 实际启动间隔
      "configured_interval_seconds": 15.0,                        // 配置间隔
      "sample_count": 1, "interval_sample_count": 1,               // 注意：写快照时会重置
      "failures": 0,
      "items": 0
    }
  },
  "held_retrieval": {...}, "passive_queue": {...},
  "dex_http_capacity": {...}, "shared_batch_coverage": {...}, "alpha149_engine": {...}
}
```

## 解析要点（2026-09-12 审计踩过的坑）

- 延迟在 `duration_seconds.p50/p95`，**不是** `p50_seconds`；间隔在 `actual_interval_seconds`。
- 顶层还包含 `held_retrieval` / `passive_queue` / `dex_http_capacity` / `shared_batch_coverage` / `alpha149_engine` 五个专用块，各有自己的字段。
- **已知可见性缺陷**：实测 `sample_count` 与 `interval_sample_count` 常为 1，说明该快照只保留最近一个采样区间，因此 `p50/p95` 对多数任务没有统计意义，不能用来判断"后台速度是否退化"。需要真实分布时应改用 `held_retrieval` 的 10 秒桶或直接对 `chain_meme_trader_*` 表按时间分组测量。
