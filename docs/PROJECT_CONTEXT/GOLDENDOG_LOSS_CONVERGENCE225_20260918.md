# Goldendog loss convergence and current chain readback, 2026-09-18

## Why this action was taken

The user reported that older strategies had earned while later changes kept losing. That complaint is consistent with large current-period losses, but a before/after causal claim needs same-source, same-period comparisons. In the active Paper funding period (`chain-meme-trader/funding-20260906-v002-final-1000`), the trade ledger's daily realized sums were -26,205.31U on September 12, -61,556.94U on September 13, -40,406.25U on September 14, -19,969.52U on September 15, -2,608.23U on September 16, -6,264.69U on September 17, and +787.29U in the incomplete September 18 UTC window at the read. These sums count independent strategy accounts and highly correlated same-token exposures, not distinct market opportunities. Open/unvalued position equity is not included; the September 18 partial day is not a recovery claim.

One old main arm, `trajectory144_trend_runner_v1`, had +275.30U realized over 379 current-period BUY tokens at this later frontier. Its 137 fully terminal exact-source-BUY pairs with `trajectory220_breakout_anchor_v1` were both negative (-345.60U for 144, -276.39U for 220): the newer exit reduced losses by 69.21U on that selected shared cohort, not a proof that it earns money. A stronger negative causal comparison exists for the already-paused `trajectory169_trend_runner_moonbag_v1`: 148 same-source, terminal token pairs yielded +100.63U for its control and -96.12U for the moonbag exit, a -196.75U deterioration. The four arms below have severe independent-account natural losses; their exact same-source pairs do not by themselves identify whether entry or exit is at fault. They are paused for further *new* exposure, not historically reclassified as counterfactual no-trades.

| Arm | Terminal independent tokens | Net realized U | Full pool writeoffs |
| --- | ---: | ---: | ---: |
| `alpha149_goldendog_early_impulse_v1` | 232 | -971.8699 | 40 |
| `alpha149_goldendog_revival_control_v1` | 236 | -784.6464 | 39 |
| `alpha149_goldendog_low_recovery20_control_v1` | 35 | -594.6315 | 31 |
| `alpha149_goldendog_low_recovery20_v1` | 35 | -332.7221 | 33 |

The recovery20 pair shares its entry but does not prove a profitable principal-recovery exit: both accounts remain deeply negative and most positions were written off. The early-impulse and revival controls also have substantial independent-token counts and tail losses. These are conditional Paper outcomes after configured costs and the system's original-pool writeoff model; they are not live execution guarantees.

## Current shared-chain diagnosis

An indexed cohort read for ID>=37501 (2026-09-17 23:54:25Z to September 18 01:53:25Z) found 114 cohorts/47 tokens, all with strategy decisions; 81 cohorts had at least one admitted arm, 52 cohorts obtained source BUY fills, and those source fills produced 188 arm-level projected positions. The latter are correlated strategy-account rows, not 188 independent market trades. First locally known discovery to cohort source quote was p50 181s/p95 2110s; decision to source BUY among 52 fills was p50 7.69s/p95 42.38s. The quote's observed/ingested/recorded clocks preceded its decision, and available quote to decision was in the same pass. The two adjacent one-hour windows had 25 then 27 source BUY fills, so there was no observed zero-trading incident in this interval.

Of 29 admitted cohorts without a source fill, existing receipts identified 13 safety REJECT, 3 WEAK, 5 UNKNOWN/disallow, 7 fresh buy-only/no-sell, and one generic `EXPIRED_SECURITY_OR_NEXT_FRAME`. The final one also has a terminal enrollment claim and no intent/attempt, so it is not a lost order; only the expiry's internal security-versus-next-frame attribution is coarse. Another 33 cohorts had only cash-rejected arm decisions, chiefly accounts with 0.41U, 8.13U and 16.18U remaining against a 20U entry. This is a real account constraint, not a reason to fabricate more capital or weaken execution checks. The long discovery-to-quote tail remains a shared data-quality and timeliness investigation; this read does not isolate its queue, source, identity or scheduler component or prove a before/after regression.

## Implementation, acceptance and rollback

`scripts/converge_goldendog225.py` is a manual, Paper-only, idempotent control. It requires each named arm to have at least 30 independent terminal tokens, <=-150U terminal realized PNL and at least 10 full writeoffs. It previews without writing; `--apply` writes only the existing `chain-meme-account-convergence/v1` new-entry control and a receipt containing its exact previous JSON. It does not change strategy rules, pending/history/account cash, executed trades or open-position exits. Applied at `2026-09-18T01:57:41.152773Z`; receipt `goldendog225:convergence:2026-09-18T01:57:41.152773Z`. Intentional rollback would restore the prior control JSON from that receipt after a new review, not delete data or reset funding.

Two focused tests cover insufficient evidence, preview, apply/idempotence, all four account controls, intact synthetic ledger, and Live refusal. Natural post-control new-BUY exclusion and matching-load performance must still be checked; no improvement in PNL or data freshness is claimed from the pause. No schedule, auto-parameter adjustment or Live permission was added. Further strategy work should compare real same-entry variants and ordinary-token controls, preserve the profitable 144 main-arm opportunity stream, and stop creating correlated clones merely to increase strategy count.
