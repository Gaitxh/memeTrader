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

## Shared cohort router and short observed organic experiment

Implemented `cohort_opportunity_router_v1` (5U/max4): current eligible source
signals resolve in frozen reawakening > clone consensus > organic early order.
One token has at most one pending/open router opportunity across pools; closed
positions do not block a genuinely new episode. Mode and source key remain on
the cohort. Early exits at5m, clone at15m; reawakening uses30m and actual
half-principal recovery with the existing verified narrative extension. Hard
exits dominate. Original accounts/policies remain unchanged.

Implemented `organic_short_observed_flow_v1` (2U/max2/5m), using the same
acquired Gecko page. The frozen observed15–60s interval requires end freshness
within30s and original exact-pool signed-flow validity. The ten-minute baseline
can remain UNKNOWN while this independent short window is complete. No extra
request, silent baseline change, or historical enrollment.

Validation:34 targeted tests passed, including actual Store claim -> common
safety wait -> strictly later BUY -> mechanical SELL, new episode after close,
real half recovery -> verified narrative extension -> overriding hard exit,
and malformed/truncated/future short-window evidence. `git diff --check` passed.
This is source/test completion, not production registration/load or natural
profit evidence. The existing process-control denial remains unchanged; no
bypass/restart attempted. Native ledger/held/handoff work remains outstanding.

## Reawakening producer correction

ACK C2C-20260910-138-REAWAKENING-PRODUCER-BUG. Actual Store cohorts use
`broad_launch`; revised `event_reawakening_v1` uses `evidence_extension_l0`, so
the old family plus generic reactivation flag could never authorize this route.
The worker now resolves the cohort's exact prior signal evaluation through the
existing (definition_version,source_snapshot_id) index. It requires the admitted
source arm, same token/original pool, ready membership, the explicit
replacement_reawakening_confirmed outcome and causal snapshot/evaluation/cohort
clocks. It freezes that source identity into enrollment and downstream signal
evidence; no blanket broad_launch allowance or historical mutation.

Two targeted tests passed: the real Store revision/quiet-to-reawakening/next-frame
BUY/exit fixture now exercises this route and malformed source rejection; the
rare queue test preserves deduplication and zero enqueue network requests.
Diff check passed. Source only: not loaded or naturally accepted. Earlier
router source/test completion did not establish natural reawakening supply.

## Native boundary and saved matching reconciliation

The native cash dispatcher now waits for REQUOTED_SHADOW, requiring the exact
independent slot/receipt after the frozen absorption signal. Its sealed plan
retains that execution frame and a deterministic hash. A frozen signal alone
cannot dispatch a plan; the prior plan must not be applied to a different later
frame. Three existing runtime tests passed, including the new actual dispatch
boundary. No funded native account/position is created by this change.

The remaining native requirement is a protocol-model Paper fill on later
observed public state, not signing/broadcast or a real-wallet fill. It must
join current public strategy cash/positions/PNL, with actual remaining raw,
rent asset and fee reserve separated, and canonical migration pending/UNKNOWN
when proof is missing. An isolated book or magic safety booleans is insufficient.
The rejected draft remains absent. Input proofs remain accepted; ledger, held
exit and public valuation integration remain unfinished source work.

Saved matching47 is not an unstarted task. Lead independently verified65 saved
anchor rows,57 matched uses/50 case-normalized unique controls;54/57 control
outcomes remain UNKNOWN, not losses. No full scan repeated by root. Preserve
this completed matching stage and pursue only missing causal first-hit/endpoint
coverage, not a claimed win rate. Evidence: LEAD_RUNNABILITY_FINDINGS_138.md and
data/research/lead138/validate_saved_matching.py. ModeChat scope remains root-owned;
7a0c649 was implemented/pushed by root, with no release to Chat.

Validation: pool-surface and pattern-input files:81 passed,2 failed. Both failures
were reproduced with unchanged HEAD runtime in memory: the authoritative-event
fixture expects an old producer result; the empty-capital-quote mock lacks
due_direct_lp_entry_preflight_quote. Neither is on the changed flow path; no
unrelated fix included. New timeout/identity/expiry/contradiction and actual
adjacent-flow tests passed. Source only; runtime/natural acceptance pending.

## RESULT — C2C-20260910-138-NATIVE-IMPLEMENT-NOW

Supersedes the preceding native "ledger unfinished" source boundary. The current
period native integration is now implemented, with nine targeted tests passing.
No independent book or extra timer was introduced. Startup appends exactly one
`pump_native_absorption_fast_v1` policy through the existing append API: 5U total
entry cash budget, max1, supported SOL/nonmayhem/noncashback/standard-supply,
metadata-only Token2022 subset. This is later-observed protocol-model Paper,
not signing, broadcasting, actual wallet fills or evidence of profitability.

- Existing two-frame absorption freezes token/curve/probe and signal clocks;
  a strictly later independent requote frame and its exact sealed cash plan
  reach one atomic common cohort/position/BUY trade and immutable native receipt.
  Persistent opportunity dedup, current effective pause controls, max1 and common
  account cash are checked within the Store transaction. Native controls and
  post-buy sellback are recomputed; known common safety hazards block entry, and
  successful native authorization joins the common safety audit.
- Common cash pays actual model curve debit, current BUY message fee and locked
  setup rent. Reserved SELL fee remains restricted cash, not an expense charged
  twice. Rent is separately disclosed at cost, with no assumed refund. Public
  account valuation and account snapshots include this asset and native current
  remaining-raw marks; they do not call locked rent executable equity. Ordinary
  DEX price/floor/cost contracts do not process native positions.
- The existing local-surface task services at most one native held position;
  its native subsection has a three-second bound and failure does not abort the
  existing surface lane. Full remaining-raw current curve quotes and current
  unsigned SELL-message fees supply marks. Hard loss, trailing or 300s max-hold
  creates intent; only a strictly later slot/observation can settle SELL. Missing
  evidence/capacity is UNKNOWN, not a fabricated fill or liquidity writeoff.
- Curve completion persists MIGRATION_PENDING. Existing canonical PumpSwap
  resolver supplies exact PDA/index0/creator/program/token/vault facts. Identity
  is persisted first; a later coherent canonical pool quote plus current fee
  and setup receipt can settle. Wrong identity is rejected. The unsigned
  PumpSwap SELL shape is pinned to official pump-public-docs commit
  `2c22246b670812e2392e5f94b9543f500d6c9e15`, IDL SHA256
  `6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56`.
  New WSOL setup rent, if needed, is charged and retained as an asset, never
  silently refunded. Missing fee-account/setup proof remains pending.

Validation: `test_native_execution138.py` + `test_pregrad_runtime.py`, 9 passed;
changed Python syntax and diff checks passed. Tests cover actual assembled-message
plan to common BUY, held runtime intent/later SELL, public account/snapshot cash
and rent equality, common safety hazard, max1, repeated/restarted receipts,
migration UNKNOWN/wrong identity/canonical/later SELL, current unsigned curve and
PumpSwap remaining-raw fee producers, and native failure isolation. Previously
accepted onchain/VM probes were not repeated.

Deployment facts are separate: read-only `/health` and `/api/live` at approximately
2026-09-10T03:39–03:40Z show runtime running, current funding version
`chain-meme-trader/funding-20260906-v002-final-1000`, Paper-only=true,
Live-locked=true, one existing open/held token and zero pending exit quotes.
Native registered strategy count is **0**: this source is **NOT LOADED/REGISTERED**,
so native natural fills and post-load latency acceptance are **NOT AVAILABLE**.
DEX pool timeouts0, retired-client count0 and waiting-high/low0 at this read are
baseline facts, not an improvement attributed to un-loaded code. The previously
denied process-control reload was not retried or bypassed. No production funding,
ledger, history or account-control mutation was performed in this stage.

Source: [official pinned PumpSwap IDL](https://github.com/pump-fun/pump-public-docs/blob/2c22246b670812e2392e5f94b9543f500d6c9e15/idl/pump_amm.json).
