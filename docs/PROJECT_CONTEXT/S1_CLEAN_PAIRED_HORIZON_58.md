# S1 clean paired horizon58

REPLY_TO: C2C-20260909-S1-CLEAN-PAIRED-HORIZON-58
Cutoff: 2026-09-09T04:09:42.752644+00:00. Read-only consistent SQLite transaction; active funding version only.

## Disposition

**KEEP_LEARNING; insufficient robust evidence to pause runner solely on horizon economics.** No production controls, thresholds, entry definitions, accounts or runtime changed. A unilateral pause could break the paired-entry enrollment contract; any later retirement must preserve group semantics.

29 exact pairs found,27 both terminal and2 open/censored. No mismatched or missing counterpart groups. Pair key is exact token+shadow_cohort+nonempty source_entry_fill_id. Both arms additionally match source_buy_trade_id,entry_snapshot_id,initial_amount_raw,stake,execution price,paper quantity and opened_at exactly; each has one BUY with equal gross cash/net cash/time. Every position realized PnL reconciles to its trade ledger within1e-8. Entry_fill_id is null in these legacy-backed positions, so it was not invented as identity.

Delta below = fast minus runner, in USDC after the existing Paper cost convention. This is actual ledger accounting, not a future-path replay. Known storm interval conservatively starts19:06:00Z and ends19:51:47Z on Sep8. Any pair whose combined holding span overlaps is confounded, even if fast itself exited before the storm. No wholly pre-storm complete pair. Post-native boundary21:17:50Z is a descriptive operational period, not randomization or an alpha filter.

| Partition | Complete pairs | Fast PnL | Runner PnL | Delta |
|---|---:|---:|---:|---:|
| pre_storm | 0 | 0.000000 | 0.000000 | 0.000000 |
| storm_confounded | 2 | -2.547335 | -2.580111 | 0.032776 |
| post_fix_pre_native53 | 7 | 22.102205 | -7.502142 | 29.604347 |
| post_native53 | 18 | 31.339222 | 1.340688 | 29.998533 |
| clean | 25 | 53.441427 | -6.161453 | 59.602880 |

## Clean pair-delta distribution

25 complete pairs =25 independent tokens; mean +2.384115U, median +0.021840U, symmetric10%-trimmed mean +0.846761U (drop floor(0.1*N)=2 at each tail).13 positive/8 negative/4 ties. Range -12.077963 to +29.043815U. Remove largest positive pair: +30.559065U total; remove largest3: -5.318379U. Removal is on pair delta, not each arm’s unrelated best trades.

Pre-native post-fix7 pairs: delta+29.604347, median0; remove top1 +0.965104, top3 -0.117443. Post-native18 pairs: delta+29.998533, median+0.145047; remove top1 +0.954718, top3 -13.170087. Positive totals repeat, but robust tail removal does not.

## Actual treatment exposure

Four clean pairs exit before900s in both arms:3 shared hard stops,1 shared trailing exit. All4 deltas exactly0; no horizon treatment exposure. Remaining21 fast positions close by max_hold around the15m boundary; their deltas account for all+59.602880U. Runner later reasons:11 max_hold,5 hard_stop,3 trailing_exit,2 below-liquidity-floor writeoff. This directly supports horizon-induced divergence rather than unequal entry or shared early exits. Full times/reasons preserved per pair.

The two largest deltas are BSC5138... (+29.043815U) and BSC9a50... (+28.639243U): fast exited at903.33/902.34s, runner was later written off below the configured pool floor at1997.29/1941.57s. Together +57.683058U, about96.8% of clean net difference. These are observed Paper writeoff outcomes, not proof of executable live losses or universally better15m exits. Storm-excluded does not guarantee perfect source coverage.

## Chain/date composition

- chain=bsc: N4, delta+57.683058, median+14.319621, top1 removed+28.639243.
- chain=robinhood: N11, delta+2.315298, median+0.021840, top1 removed+1.449569.
- chain=solana: N10, delta-0.395476, median+0.085134, top1 removed-7.633677.
- utc_date=2026-09-08: N17, delta+37.059261, median+0.000000, top1 removed+8.420018.
- utc_date=2026-09-09: N8, delta+22.543619, median+0.145047, top1 removed-6.500196.

No chain-specific threshold/selection proposed. BSC4 pairs dominate; Solana10 are slightly negative in total, RH11 modestly positive. Only two UTC entry dates. Two incomplete pairs excluded from all terminal economic statistics; retained in result.json for censoring.

## Evidence / validation

scripts/research_s1_pairs58.py; data/research/s1_pairs58/result.json (full position/trade-reconciled pair facts and distributions), strata.json. Script completed with identity and ledger assertions; no writes to production SQLite. No production-code change, deployment, restart or runtime tests required. Existing costs/Live lock unchanged.
