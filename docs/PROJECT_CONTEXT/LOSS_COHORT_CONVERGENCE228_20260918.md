# Stage 228: contain materially losing Paper arms

## Observed failure

The user's report that newer strategy changes continued to lose is supported by current-period account ledgers. The effective registry still had 81 arms able to open new positions after stages 225-227. A manual full-registry query found 20 such arms with at least 50 distinct terminal tokens **within each account** and realized net <=-200U. They are not 20 independent market experiments: many project the same source BUY into correlated strategy accounts. Their aggregate 3,951 account-position terminal rows, -8,666.67U and 352 writeoffs must **not** be described as that many independent token opportunities or a portfolio loss. The most material examples are below; the complete frozen arm list and read-time evidence are in `scripts/converge_loss_cohort228.py` and two durable control receipts.

| Arm | Distinct terminal tokens in arm | Net U at readback | Full writeoffs |
| --- | ---: | ---: | ---: |
| alpha149_nonbsc_flow_v1 | 542 | -999.59 | 23 |
| alpha149_shallow_band_flow_v1 | 337 | -983.82 | 62 |
| alpha149_moonbag_steady_v1 | 329 | -853.45 | 26 |
| alpha149_washout_reclaim_v1 | 470 | -707.44 | 32 |
| alpha149_score_gate_band_v1 | 323 | -613.56 | 14 |
| alpha149_friction_multiple_escape_v1 | 201 | -548.74 | 12 |
| alpha149_mid_deep_band_nonbsc_v1 | 203 | -490.93 | 4 |
| alpha149_smooth_organic_trend_v1 | 123 | -376.57 | 15 |
| alpha149_depth_first_mature_v1 | 214 | -366.23 | 4 |
| dex_hot_impulse_v1 | 66 | -288.54 | 9 |
| dex_liquidity_divergence_exit_v1 | 66 | -288.54 | 9 |
| recipe145_6c89c7f9e7f33d0a_v1 | 362 | -287.94 | 37 |
| trajectory190_first_mark_trail_v1 | 200 | -246.48 | 20 |
| dex_profit_velocity_exit_v1 | 66 | -240.10 | 6 |
| trajectory187_nonsol_fast_v1 | 86 | -237.18 | 12 |
| alpha212_washout_reclaim_hold_control_v1 | 65 | -236.01 | 13 |
| alpha149_sf_extreme_buy_pressure_hold_v1 | 99 | -232.81 | 34 |
| alpha212_washout_reclaim_anchor_v1 | 66 | -228.42 | 6 |
| organic_short_observed_flow_v1 | 66 | -212.74 | 6 |
| dex_blowoff_exit_v1 | 66 | -207.59 | 7 |

These measurements are current-period terminal realized net values, not a causal estimate of an alternative strategy or a forecast. In particular, several DEX exit variants share exactly the same 66 source tokens and identical account outcomes. The older `trajectory144_trend_runner_v1` has separate evidence of positive net in a 378-token same-source comparison with its failed fast exit, so it was deliberately not included.

## Action and validation

`scripts/converge_loss_cohort228.py` freezes the 20 identifiers and recomputes a minimum current evidence condition before any mutation: >=50 distinct terminal tokens in the account and <=-200U realized net. It refuses non-Paper/Live configuration, previews by default, and requires explicit `--apply`. It only updates the existing `chain-meme-account-convergence/v1` entry-pause overlay, leaving old policies, account money, transactions, positions, exits and funding untouched. A receipt saves the previous overlay for exact manual rollback. The first 18-arm receipt is `loss228:convergence:2026-09-18T02:18:44.266535Z`; the second adds two arms omitted by an overly restrictive writeoff-count criterion, `loss228:convergence:2026-09-18T02:19:17.307331Z`. The second receipt's previous-control snapshot includes the first 18, so any rollback must respect order and not overwrite later controls.

`tests/test_converge_loss_cohort228.py`: two focused tests passed for threshold refusal, Paper-only authorization, idempotence, unchanged positions/PnL and a single test receipt. Effective registry readback: 511 total, 61 able to open new entries, all 20 frozen paused, 144 runner not paused. Two preexisting positions in this frozen set remained eligible for their original exits. At first post-second-receipt readback there were zero new positions with `opened_at` later than the receipt. This is immediate control verification, **not** proof of improved future profitability. `/health` remained running on the same `chain-meme-trader/funding-20260906-v002-final-1000` period; no worker restart, funding reset, Live trading, added API or scheduled review.

## Next manual review

Compare post-pause **source** BUY and distinct-token counts, current remaining arms' costed net and writeoffs, and any unvalued/open positions against similar pre-pause windows. Do not infer that stopping 20 correlated accounts removes 20 independent opportunities. Review the remaining moderately negative or low-sample arms individually, including why the original runner performed better on Solana but not uniformly across chains. Test 227 as a separate forward entry hypothesis, without unpausing known losses to raise trade count. If rollback is warranted, restore the saved overlay from the proper receipt in a reviewed transaction while preserving newer changes; never delete historical trades or clear the funding period.

### Immediate post-control readback

After the second receipt, one independent token received a natural source BUY at `02:19:52.866779Z` and produced three projected strategy positions; the 20 frozen arms produced zero new positions in the same readback. Thus the control did not globally stop Paper entry. A later 120-sample runtime window showed `chain_meme_cohort_observer` p95 interval 11.51s and duration 2.06s (failures zero), worse than an earlier post-227 120-sample interval 2.79s/duration 0.97s. The windows are not load-matched, and the new arm had no signal or trade. In the slower window, Dex follow-up request start p95 was 12.75s with 14 failures in its most recent 64 samples, while held-priority Dex requests had zero failures in their 64-sample view and the sole held Solana quote was about 0.4s old. Passive queue dropped zero batches/quotes. This points to shared follow-up latency as a live issue but does **not** establish its root cause or exclude compute contention. Further matched-window diagnosis is required before changing scheduler capacity or blaming 227.
