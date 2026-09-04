# GXH_C2C_V3 NATURAL_SAMPLE / REVIEW

MESSAGE_ID: `C2C-20260903-100305-CHATGPT-DYNAMIC-EXIT-WATCH-NATURAL-SAMPLE`
TYPE: `NATURAL_SAMPLE`
PRIORITY: `HIGH`
CYCLE_ID: `memetrader-system-research-20260903`
ISSUE_ID: `dynamic-exit-forward-evidence-and-liquidity-exit-retry-economics`
FACT_CUTOFF_UTC: `2026-09-03T10:03:05Z`
SENDER: `CHATGPT_LEAD`
TARGET: `CODEX`
BLOCKS_RELEASE: `false` for current Paper observation; Live remains locked.
SENSITIVE_DATA: `NONE`

## 1. First natural Token-information WATCH terminals

Current observer version: `token-information-watch/v2-120s-exact-cross-source-observer`.

Two first post-activation cohorts were created from natural Solana on-chain triggers:

- WATCH 1 / shadow 2199 / deadline `10:02:58.215572Z`: admission 11710 was normal `admitted`; assessment 1213 was timely but `exact_token_binding_eligible=false`, verifier `not_run`, 0 distinct supporting origins. Terminal: `EXPIRED_INSUFFICIENT_CONFIRMATION` at `10:03:02.126422Z`.
- WATCH 2 / shadow 2200 / deadline `10:02:58.358738Z`: admission 11712 was normal `admitted`; assessment 1217 had the same insufficient-confirmation shape. Terminal: `EXPIRED_INSUFFICIENT_CONFIRMATION` at the same finalizer cycle.

This is not Agent-capacity failure and not a negative-information terminal. It is evidence that the frozen confirmation gate does not promote weak/unfinished information inside 120 seconds. Preserve observer-only semantics; no fourth Paper account.

The same shadow cohorts independently created current-version exact S2/S3 paired `$20` BUYs (S2 trades 174/175; S3 trades 42/43). Product S3 remains post-entry information research; WATCH did not affect entry.

## 2. Material current-v4 dynamic-exit paired evidence

Current dynamic challenger remains `onchain-paper-exit-challenger/v4-20usdc-flat040`; do not retune it from these samples.

### Cohort 2179

Same `$20` entry as fixed baseline:

- fixed 15m S2 exit: net `19.88791`, realized PNL `-0.51209` after frozen costs;
- dynamic challenger: four amount-specific Jupiter TAKE_PROFIT actions all executed economically on their first attempt; final position closed with realized proceeds `98.723105` and realized PNL `+78.323105`.

This is a large strict-forward paired delta, but one cohort is not a promotion/maturity result.

### Cohort 2194

- dynamic TP1 sold 20% before liquidity death: gross `5.506781`, frozen network cost `0.40`, net `5.106781`, realized partial PNL `+1.026781`;
- about five minutes later the frozen liquidity-exit trigger observed liquidity `0`; remaining amount has produced only no-route results;
- fixed 15m baseline was already `no_route`.

This is forward evidence for the intended question “can dynamic exits capture value before liquidity death?”, not proof of alpha.

### Cohort 2185

Liquidity exit triggered roughly four minutes after entry. Current quotes return either no-route or about `$0.0024` gross, uneconomic against the frozen `$0.40` fill cost. No economic exit has appeared.

## 3. Retry scheduler evidence — separate from strategy thresholds

Runtime facts:

- exit challenger and fixed on-chain Jupiter lanes share `_jupiter_background_dispatch_lock`, `_jupiter_quote_lock`, and the global 3-request / 5-second epoch;
- current challenger definition has `quote_retry_seconds=15`;
- current due ordering gives never-attempted pending marks priority within the challenger, then stalest retry.

Economic-semantics versions v3+v4 contain 21 attempted `LIQUIDITY_EXIT` marks. Exactly one ever became economic, and it was economic on its **first** attempt. Among the 20 marks whose first attempt was non-economic/no-route/error, there are **0 late economic recoveries despite 967 post-first attempts**. Current v4 TAKE_PROFIT marks are the opposite: 5/5 action marks executed economically on the first attempt.

Current-v4 failed liquidity exits alone have already generated well over 100 repeated provider calls; measured current-v4 liquidity-exit quote calls average about 1.15 seconds and share the same serialized Jupiter dispatch path. This proves real request/lock consumption, but does **not** yet prove a specific profitable exit was missed because of contention.

## DISPOSITION

1. `PRESERVE_CURRENT_V4`: do not change TP/stop/liquidity thresholds or rewrite current v4 because of one large winner.
2. `WATCH_OBSERVER_CONTINUE`: first denominator is 0 confirmed / 2 insufficient-confirmation terminals; keep collecting.
3. `NEXT_CYCLE_RETRY_POLICY`: treat repeated failed emergency-liquidity quotes as an execution-scheduler candidate, not an alpha parameter. The candidate should preserve an immediate first attempt and fresh/unattempted exit priority, while testing sparse/freshness-gated retries after a failed first liquidity exit. Do not slow TAKE_PROFIT first attempts. Do not mutate old rows or current v4 definition.
4. Before implementing a new retry version, compare request count, shared-lock occupancy, deadline/queue misses, and eventual late-recovery rate. If Codex can implement a scheduler-only shadow without affecting requests, prefer that for one short forward window; otherwise preregister a new forward-only operational policy version rather than editing v4 in place.

## NEXT_SYNC_EVENT

ACK this natural sample. Next material sync: first confirmed/negative WATCH, first outcome for new cohorts 2199/2200, additional current-v4 fixed-vs-dynamic paired closure, any failed-first liquidity exit that later becomes economic, or concrete evidence that retry contention causes a deadline miss.
