# Gate marginal value: frozen evidence

Fixed boundary: `2026-09-07T13:38:59.399800Z`. The general decision ledger has 149,380 rows, dominated by cash and slot constraints; those are admission/capacity outcomes, not a recoverable marginal hypothesis-gate reject population. No-decision and missing features are not counted as rejects.

## Round2 chase: persisted common-opportunity denominator

The dispatcher writes `round2_chase_receipt` before it removes a vetoed candidate and records `round2_chase_consumed` to prevent replay. This is the recoverable gate denominator. Deduplicating repeated cohort projections by `(token_id, signal_snapshot_id, receipt_snapshot_id)` gives 231 common receipt opportunities: candidate allowed 189, candidate vetoed 42. Of the vetoes, 42 have a control terminal by the cutoff and 0 remain unknown/open.

For terminal veto controls, avoided-loss cases=31 / 80.4380U, missed-profit cases=11 / 40.9758U, net control outcome=-39.4622U. This is a finite, capacity- and selection-confounded counterfactual ledger, not an alpha estimate or deployable portfolio return.

The required historical records are retained: cohort 56861 (SOL) is a 19.3438% veto with control terminal +24.0510U; cohort 57425 (BSC) is a 6.8094% veto with control terminal -5.0000U. Both are one receipt opportunity each despite duplicate cohort projections.

## Other declared gate directions

Age/flow/pullback/liquidity/wallet/narrative/safety/acceleration/breakout/confirmation mechanisms cannot be given marginal avoided/missed estimates here because they lack a persisted candidate-veto plus same-opportunity control-receipt chain. Their absent `entry_decision` rows can mean no dispatcher invocation, incomplete feature coverage, another admission constraint, or no trigger; they are not rejects. Resource age-rate and cooling controls have common decisions but no candidate rejection at the frozen boundary. Existing exit pairs are not gate evidence: different receipt/exit behavior cannot establish admission marginal value.

Source evidence: `store.py:27153-27169` builds and persists the chase receipt/outcomes before candidate removal; `store.py:27167-27172` persists consumption. The detailed deduplicated rows are in `round2_chase_common_denominator.json`.
# Repair-boundary split from persisted chase receipts

This is an offline aggregation of the already-generated `round2_chase_common_denominator.json`; it does not read the database. The boundary is `received_at >= 2026-09-07T09:19:47Z`. A common receipt group is counted once; allowed rows have a zero counterfactual effect, and a terminal veto has effect `0 - control_terminal_pnl_usd`. Unknown terminal outcomes would remain unknown rather than be assigned zero; there were none here.

| receipt era | common groups | allowed | veto | independent Tokens | terminal veto controls | avoided loss (U) | missed profit (U) | control PnL (U) | net veto effect (U) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| before boundary | 196 | 167 | 29 | 196 | 29 | 61.0514 | 10.7216 | -50.3298 | +50.3298 |
| at/after boundary | 35 | 22 | 13 | 35 | 13 | 19.3865 | 30.2542 | +10.8677 | -10.8677 |

The token-level nonparametric bootstrap (10,000 deterministic resamples, independent Tokens as units) gives mean veto effect `+0.2568U`, 95% interval `[+0.0997, +0.4226]`, before the boundary; and `-0.3105U`, `[-2.0060, +0.8196]`, at/after it. The latter interval spans zero and the point estimate is adverse. The 231-group full-period result must therefore not be used as evidence for the current repair-era behavior.

Receipt-hour distribution is: before boundary, 2026-09-06 19–23Z = `7/10/24/24/19`, and 2026-09-07 00–08Z = `17/21/13/15/16/12/8/6/4`; at/after boundary, 2026-09-07 09–13Z = `5/11/9/7/3`. These are descriptive, receipt-timed strata only: capacity, candidate mix, and control-arm selection can confound the comparison, so they do not establish a causal gate effect.
