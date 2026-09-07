# Data latency and edge-decay diagnostic

Fixed boundary: `2026-09-07T13:38:59.399800Z`; current funding period only. The position denominator is `25063`. `25063` positions map through a bounded current-period BUY source; `0` do not and are reported as unmapped (historical inheritance or no eligible source mapping), not silently treated as coverage. The mapped rows collapse to `7435` unique `(token, cohort)` opportunities. Their latency is the within-opportunity median across arms, with per-opportunity min/max retained in the CSV; no shortest-arm selection occurs.

Full period: N=7435, delay p50=13.089s, p90=23.662s; terminal-median outcome N=7418, p50=-1.538U.

Signal time is a **decision-time proxy**, recovered in order: resource `resource_bound_opportunities.decision_at`, `feature.signal_at`, arm-specific `cohort_signals.decision_evidence.recorded_at`/`ingested_at`, then `feature.fill_signal_snapshot_id.recorded_at`. `cohort.decided_at` is never used. A receipt is verified by `source_entry_fill_id` joining `chain_meme_trader_v6_entry_fills.id` with matching version, entry_cohort_id and token. The actual BUY is separately matched by version/arm/cohort/token/side and frozen trade frontier. `source_buy_trade_id` is historically overloaded with a v6 fill ID, so it must not be joined to `trades.id`. Unverified fallback timestamps would remain projection proxies; in this frozen current-period sample all positions have a verified shared v6 fill. Entry snapshot timestamps are retained in the CSV. A source snapshot is only marked non-late when all observed/ingested/recorded timestamps are no later than the recovered decision proxy.

Original-pool identity: `{'original_pool_matched': 7435}` (EVM comparisons case-insensitive; Solana case-sensitive). Source-snapshot timing coverage: `{'False': 11, 'True': 7424}`. Receipt evidence by arm: `{'receipt_verified': 25063}`.

Entry snapshot clock gaps across arm-level BUY positions: observed→ingested N=25063, p50=0.226s, p90=2.259s; ingested→recorded N=25063, p50=0.047s, p90=0.107s. The 11 source snapshots later than their recovered decision feature are retained as a causal-timing coverage failure, not repaired.

Verified-identity plus three-clock (`observed <= ingested <= recorded <= v6 fill`) market-price subset: N=7424, signal→receipt **market-price** drift p50=0.000000, p90=0.055681. The configured execution-vs-market slippage is reported separately: N=25063, p50=0.040000, p90=0.040000. Neither is a causal latency estimate.

| Group | N opportunities | N recovered latency | p50 delay s | p90 delay s | N terminal median | p50 terminal PnL U |
| --- | --- | --- | --- | --- | --- | --- |
| bsc | 2519 | 2519 | 12.628166 | 24.948089400000008 | 2516 | -4.234013711263456 |
| robinhood | 1133 | 1133 | 13.667557 | 44.03373820000001 | 1128 | -1.2815690941245905 |
| solana | 3783 | 3783 | 13.196447 | 20.174505000000003 | 3774 | -1.41535674798811 |

## Era split

| Group | N opportunities | N recovered latency | p50 delay s | p90 delay s | N terminal median | p50 terminal PnL U |
| --- | --- | --- | --- | --- | --- | --- |
| after_091947Z | 429 | 429 | 15.021742 | 44.164079 | 412 | -1.083162639397484 |
| before_091947Z | 7006 | 7006 | 12.847876 | 23.2891495 | 7006 | -1.53846153846154 |

## Delay buckets and terminal outcome association

| Group | N opportunities | N recovered latency | p50 delay s | p90 delay s | N terminal median | p50 terminal PnL U |
| --- | --- | --- | --- | --- | --- | --- |
| 15-30s | 2121 | 2121 | 18.847789 | 24.627434 | 2117 | -1.4484601321895667 |
| 30-60s | 354 | 354 | 44.8606105 | 46.7744822 | 351 | -1.2013958125623132 |
| 5-15s | 3046 | 3046 | 12.4957785 | 14.4869615 | 3040 | -1.3750653500225372 |
| <=5s | 1837 | 1837 | 1.337146 | 3.380704600000001 | 1835 | -1.7824175824175827 |
| >60s | 77 | 77 | 79.558501 | 87.8900294 | 75 | -1.587864952109829 |

The terminal metric includes only closed/written-off arms with `closed_at <= cutoff`, then takes the median within a common Token/cohort. It prevents multiple arms from becoming multiple opportunities, but it is not a tradable single-arm payoff. Delay/outcome differences are descriptive only: entry rule, chain, pool age, liquidity, selection, capacity and exit contract are confounded. No causal edge-decay conclusion follows from this table.

Code-path evidence: `store.py:27056-27064` records resource-bound decision evidence and prevents repeat first-common opportunities; `store.py:28119-28124` separates isolated dispatch from main snapshot dispatch; position creation stores `entry_snapshot_id` and entry fill references at `store.py:29818-29854`; current position queries join that snapshot at `store.py:30923-30926`.
