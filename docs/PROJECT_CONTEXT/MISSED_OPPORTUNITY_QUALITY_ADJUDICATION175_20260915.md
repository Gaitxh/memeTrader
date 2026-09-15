# Missed-opportunity quality adjudication 175 - 2026-09-15

## Diagnosis

The restored full-universe learner produced 63 raw `potential_miss` rows. The
raw audit intentionally used the maximum locally sampled token path and did not
join the already available outcome-quality overlay. That complete denominator
is useful, but it is unsafe as an optimization input:

- only 9/63 retained at least +25% after canonical same-route liquidity and
  configured Paper cost estimation;
- 0/63 had confirmed executable net return;
- the largest raw result, +11,383,142%, was a provider/pair switch classified
  `cross_pair_incomparable`, with no executable return;
- another raw +12,571% path began in a zero-liquidity pool; its estimated net
  result was negative.

Therefore a raw miss count could overstate both the number and magnitude of
opportunities and cause a self-learning process to loosen entry rules for data
artifacts rather than tradable outcomes.

## Change

An append-only `missed-opportunity-quality-adjudication/v1` overlay now starts
at its own audit frontier. It does not update or delete the raw v1 audit.

- `confirmed_executable_miss` is learnable only when outcome quality is
  `same_route_liquidity_supported`, tradability is `confirmed_executable`, and
  net return after configured costs is at least +25%.
- `estimated_only_unconfirmed` preserves same-route, cost-positive observations
  whose safety or execution evidence is still unknown, but cannot drive tuning.
- `excluded_quality` isolates cross-pair comparisons, insufficient liquidity,
  known non-executability and sub-threshold net results with explicit reasons.
- Missing quality never becomes safe, rejected, or learnable. The finalizer
  waits for an immutable quality row.
- The existing raw audit remains the complete outcome denominator. Its console
  labels now say `Raw potential miss`; the existing quality/execution view and
  the new API payload keep raw, estimated and confirmed evidence distinct.

This layer is research-only (`decision_eligible=false`, `affects=none`). It
does not change entries, exits, sizing, accounts, or Live state.

## Validation and deployment

Focused tests passed for a confirmed same-route +60% case and a dust-to-liquid
cross-pair case whose raw path exceeded 10,000x. The former is the only
learnable row; the latter remains in the raw denominator and is adjudicated
`cross_pair_incomparable`. Update attempts on adjudications are rejected.
Runtime ordering tests also confirm `quality -> raw audit -> adjudication ->
target-time attribution`. JavaScript syntax validation passed.

The final Paper code restarted naturally under the existing supervisor at
`2026-09-15T14:36:00.856763Z` (PID 31588). `/health` returned HTTP 200 with the
unchanged funding version `chain-meme-trader/funding-20260906-v002-final-1000`;
`live.enabled` remained false. Loaded `runtime.py` and `store.py` hashes matched
the working tree.

The insert-validation trigger is installed and rejects rows whose immutable
audit/outcome/quality lineage or learnable status does not match. The new
registration froze `activation_audit_id=9504`, so the 63 diagnostic
rows that motivated the fix were not rewritten or relabeled. The first natural
post-frontier adjudication was written as `excluded_quality /
cross_pair_incomparable`; a second natural row received the same exclusion,
with zero learnable rows. Three natural outcome-loop
calls completed with zero failures. Held apply-exit remained failure-free with
p95 about 0.14 seconds; held fetch p95 was about 5.35 seconds with intermittent
upstream failures, not adjudication work.

## Forward rule

Raw, estimated-only and confirmed-executable miss rates must be reviewed
separately. Automatic or semi-automatic filter/strategy tuning may use only the
confirmed-executable group after sufficient independent-token maturity. The
estimated-only group is a queue for better evidence, not authorization to
loosen safety or execution requirements.
