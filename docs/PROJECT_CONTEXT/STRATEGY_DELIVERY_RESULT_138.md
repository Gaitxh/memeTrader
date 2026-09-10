# 138 — ongoing delivery, first coherent repair

Owner: existing Codex writer. This is a stage result, not completion of 138.

## Microstructure duplicate-frame repair

The bounded Lead read in LEAD_RUNNABILITY_FINDINGS_138.md found 13 invalid-clock
classification receipts with equal window start/end. The worker accepted two
copies of one underlying observation as a price trajectory and replaced its
valid ten-minute signed-flow window with a zero-duration interval.

The worker now deduplicates exact-pool price endpoints by observation time.
If fewer than two distinct endpoints remain, price displacement is unavailable
and the original requested flow window is retained. Trade coverage, safety,
next-observation execution, request budget, watch capacity and thresholds are
unchanged. This does not convert missing trade coverage into zero activity.

Validation: tests/test_market_microstructure119.py — 20 passed. The regression
runs the actual worker and classifier on duplicate provider/observer frames and
complete organic trade coverage, plus a genuine two-endpoint trajectory.
Source tested; not loaded. No natural post-change counts or speedup claim.

## Trade-delay evidence

Organic cohort94707 first later raw original-pool frame arrived at
00:45:10.751745Z after its 00:44:26.627150Z anchor. Decision was
00:45:12.639864Z and BUY 00:45:15.546154Z. Thus about44.1 seconds was
waiting for the required independent frame, 1.888119 seconds local handoff,
and 2.906290 seconds decision-to-BUY. Reusing the anchor is not a valid fix.
Its subsequent -2U writeoff remains historical evidence.

At the Lead's fixed cutoff, 34 policies were truly eligible after both entry
controls, not268. UTC01 hour had9 BUYs/3 unique tokens versus UTC00 hour7/2;
these are sparse observations, not proof of zero trading or an equal-window
causal startup comparison. Repeated per-frame rejection counts are not
independent lost opportunities. See the bounded Lead report for denominators.

## Remaining work and deployment boundary

137 native exact SOL math, metadata controls, current rent/message fees,
sealed cash assembler and rare dispatch are implemented/tested. They must not
be described as missing inputs again. Native current-period position/cash/fill
ledger, remaining-raw exits, canonical migration and valuation remain actual
implementation work, with no native funded registration yet. Strategies297–299
and earlier completed corrections are not to be reimplemented.

The prior process-control tool request was denied before execution. This stage
does not retry or bypass that denial. New source load and natural acceptance
remain unverified; source work is not blocked by that separate boundary.
No production ledger, funding, history, Live setting, or watch request changed.
