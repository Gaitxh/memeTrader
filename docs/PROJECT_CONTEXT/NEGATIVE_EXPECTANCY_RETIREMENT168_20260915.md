# Negative-expectancy retirement 168 (2026-09-15)

## Root cause

The existing lifecycle stopped an arm only after its independent 1000U Paper account could no
longer fund the ordinary 20U entry. That is too late for profitability: an arm could repeatedly
demonstrate negative after-cost expectancy across many independent tokens and still consume nearly
all of its account before becoming `FAILED_ACCOUNT_DEPLETED`.

The current funding period had 103 still-entry-enabled arms with at least 30 settled tokens. Only
two had positive cumulative realized PnL. A conservative per-token screen identified 66 arms whose
loss was not explained by one token or position concentration. Together they had realized
-41,797.65U before this action. Several were winners only relative to even worse controls while
remaining absolutely loss-making; relative rank is therefore no longer treated as proof of a
tradable positive edge.

## Selection contract

The frozen `negative_expectancy_arms_r168.json` authority requires all of the following within the
current funding period:

- at least 30 independent settled tokens, aggregating all positions for the same token;
- at least 200U cumulative realized loss;
- negative median PnL per token;
- a deterministic 5,000-resample, token-clustered two-sided 99% bootstrap interval wholly below
  zero;
- negative mean PnL after deleting any one token.

This is an absolute after-cost break-even comparison. It does not use later ATH, current metadata,
future marks or position-level pseudo-replication. The authority is latched and reviewable rather
than silently following every new database row.

## Action

`scripts/sync_negative_expectancy_authority.py` is read-only by default. Explicit `--apply`
atomically records newly qualified arms in a separate authority source. On runtime load those arms
receive `FAILED_FORWARD_EXPECTANCY`, which pauses only new entry. Existing positions, SELL intents,
write-offs, marks and account history remain governed by their original contracts.

The source is independently reversible and does not alter the depleted, paired-dominated,
unreachable-contract or user convergence sources. The existing depleted-arm sync was also brought
back to its established minimal authority schema (`arm_id`, `cash_usd`, `observed_at`); detailed
snapshot/PnL evidence remains in reports instead of expanding that permission file.

## Deployment evidence

- Applied candidates: 66; captured realized PnL: -41,797.65U.
- Runtime start: `2026-09-15T12:00:54.998124Z`.
- Funding unchanged: `chain-meme-trader/funding-20260906-v002-final-1000`.
- Policy count unchanged by this retirement stage: 486.
- Effective paused/retired overlay: 162 arms total: 85 depleted, 7 paired-dominated, 4
  structurally unreachable and 66 negative-expectancy.
- After load, the 66 arms produced zero entry decisions and zero new positions.
- Their 91 existing open positions remained present for normal exit management.
- Idempotent rescan: zero new candidates and zero restart required.
- `/health`, `/api/live?view=summary` and `/api/performance` healthy with localhost bypassing the
  host HTTP proxy. Paper remains active and Live remains disabled.
- Retirement and statistical boundary tests: 17 passed.

## Continuing rule

The active two-hour heartbeat dry-runs both the deterministic depletion sync and this statistical
screen. New statistically failed arms may be latched only under the same fixed criteria. A release
requires an explicit evidence review; ordinary sampling noise cannot automatically reactivate an
arm. New low-sample tempo and Goldendog experiments are unaffected and retain their declared
strict-forward comparison thresholds.
