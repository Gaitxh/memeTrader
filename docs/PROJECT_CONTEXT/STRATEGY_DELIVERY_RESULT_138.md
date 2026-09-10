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

## SOL arithmetic identity versus current safety

Root bounded readback confirms prior exact-pool proof282572: RESOLVED,
base/quote decimals6/9, slot445768159 at02:18:57.948241Z. Later282835
at02:22:45.207298Z is RPC timeout with null decimals. This verifies that a
transport failure, rather than contradictory identity, erased arithmetic inputs.

The surface collector now hashes its acquired pool/base-mint/quote-mint
bundle. Runtime retains only identity/decimals, original receipt clocks/hash and
evidence ID for at most600 seconds and only while the pool remains selected.
Only UNKNOWN_RPC can reuse that proof; identity failure, changed target, expiry
or missing prior proof fails closed. Current reserves/custody/safety are never
copied from the old proof. Amountful evidence records current UNKNOWN_RPC
separately from its original identity proof. No added RPC/scan/rate or target.
Zero-duration/no-new-signature scans remain incomplete; no timestamps refreshed.

Validation: pool-surface and pattern-input files:81 passed,2 failed. Both failures
were reproduced with unchanged HEAD runtime in memory: the authoritative-event
fixture expects an old producer result; the empty-capital-quote mock lacks
due_direct_lp_entry_preflight_quote. Neither is on the changed flow path; no
unrelated fix included. New timeout/identity/expiry/contradiction and actual
adjacent-flow tests passed. Source only; runtime/natural acceptance pending.
