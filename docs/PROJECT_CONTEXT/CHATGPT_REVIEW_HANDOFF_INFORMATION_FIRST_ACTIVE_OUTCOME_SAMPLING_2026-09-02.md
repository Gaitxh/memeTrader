# ChatGPT independent review handoff — information-first active outcome sampling

## Review purpose

Review a strictly forward sampling policy for 15/60/240-minute information-first Shadow outcomes. The current outcome finalizer only consumes Token snapshots that other collectors happen to record. It does not actively request a quote at the registered target horizon.

## Objective

Measure whether information-first `WAIT`/rejected opportunities later rose or failed, without future leakage, winner backfill, survivorship bias or changes to production Strategy/Paper. Solana is primary; Live remains locked.

## Current empirical evidence

- There are 100 trackable `information-first-shadow/v1` cohorts.
- Current outcome counts:
  - 15 minutes: 60 observed, 38 missing, 1 due without a target-window snapshot, 1 not due.
  - 60 minutes: 45 observed, 46 missing, 4 due without a target-window snapshot, 4 not due, 1 awaiting finalization.
  - 240 minutes: 27 observed, 53 missing, 1 due without a target-window snapshot, 19 not due.
- Of the missing outcomes, 17/38 at 15 minutes, 18/46 at 60 minutes and 5/53 at 240 minutes later received another valid Token snapshot after the 30-minute lateness deadline. They were not necessarily permanently unobservable.
- New cohort `100` targeted its first 15-minute outcome at approximately `2026-09-02T13:28:27Z`. No target-window snapshot had been recorded by `13:29:38Z`, so no outcome existed yet.
- A direct read-only DexScreener request immediately returned the Token's Pump.fun pair and current price, proving it was queryable even though the passive collector had not written a target-window snapshot.
- Manually inserting a snapshot for this selected cohort would bias the sample and is explicitly rejected.

## Current implementation to inspect

- `src/memetrader/store.py`
  - `INFORMATION_FIRST_SHADOW_VERSION`
  - `create_information_first_shadow_cohort`
  - `finalize_information_first_shadow_outcomes`
  - `token_snapshots`
- `src/memetrader/runtime.py`
  - where the finalizer runs
  - existing bounded quote schedulers and shared request locks
- `src/memetrader/dex.py` or the current DexScreener client quote path
- tests around `test_information_first_shadow_*` and runtime poll ordering.

## Non-negotiable boundaries

- Do not change, reinterpret or actively fill old `information-first-shadow/v1` cohorts.
- Register a new activation point before any active request. No historical winner selection.
- Request timing, completion timing, provider, success/error/no-route and the actual observed/ingested/recorded timestamps must be durable and append-only.
- A target quote may occur only at or after the target horizon. It cannot be treated as if observed exactly at the target.
- Use the first valid response inside a pre-registered lateness window; preserve missing/error as outcomes.
- Apply the same policy to every eligible cohort, not only interesting Tokens.
- Sampling is research-only: `decision_eligible=0`, `affects=none`; no Strategy, safety, sizing, Paper or Live effect.
- Bound request volume and share existing Dex request limits. Do not use an Agent for numerical market data.

## Questions for three independent reviewers

1. Is active target-horizon sampling required to reduce informative missingness, or would it create a different selection bias?
2. Should this be a new Shadow version, a separate outcome-collection registration linked to existing future cohorts, or a new cohort table?
3. What exact target/lateness/retry schedule is causally valid and operationally economical?
4. Should DexScreener price be descriptive only while Jupiter amount-specific quotes measure executable returns?
5. How should dead pair, empty pair list, HTTP error, rate limit, stale response and no executable route differ?
6. What is the minimum schema and bounded scheduler that preserves single-instance operation and SQLite WAL safety?
7. Which forward metrics and stop gates prove improved coverage without fabricating performance?
8. Recommend `GO`, `REVISE`, or `NO-GO`, with minimal code paths and tests.

## Required output

- Verdict: `GO | REVISE | NO-GO`.
- Sampling estimand and activation/version boundary.
- Exact timing, retry and terminal-state rules.
- Minimal append-only schema and scheduler.
- Dex mark versus executable Jupiter quote roles.
- Tests, forward metrics and stop gates.
- Explicit confirmation that no old cohort is backfilled and no production trade rule changes.
