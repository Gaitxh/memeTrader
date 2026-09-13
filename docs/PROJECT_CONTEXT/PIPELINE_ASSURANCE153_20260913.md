# Pipeline assurance 153 — 2026-09-13

## Boundary

- Paper remains the only enabled mode. No Live setting, real order, account reset,
  historical rewrite, or existing strategy threshold was changed.
- DexScreener remains the ordinary collection source. The patch changes allocation
  inside the existing bounded batch budget; it does not add paid APIs or unlimited
  concurrency.
- `admitted` means a strategy matched. It is not synonymous with risk authorization,
  route availability, or executable fill.

## Independent audit results

Two read-only agents inspected the same running SQLite database and code from
different sides of the chain.

### Discovery, hydration and feature continuity

At the 2026-09-13 05:41Z cutoff, 3,809 lifecycle follow-ups were already due while
the five-second details loop selected at most two follow-ups from a ten-token batch.
3,325/3,345 current token market marks and 2,415/2,435 current pool marks were older
than 30 seconds. First hydration itself was active (only one pending row), so the
bottleneck was repeat sampling, not discovery ingestion. Matched hydration attempts
had p50/p90/p99 latency 1.25/3.29/13.14 seconds, while adjacent visible market frames
had p50/p90/p99 gaps 11.0/67.9/518.6 seconds.

### Signal, safety, Paper execution and accounting

For the new 152 pair at the 05:39Z cutoff: nine independent opportunities produced
18 admitted arm decisions; six opportunities produced 12 participant outcomes and
12 positions from six shared entry fills. Three opportunities (six arms) had no
participant outcome, position, or safety evidence because `dex_proxy_guard()` could
return `False` silently.

All 8,210 positions carrying `source_entry_fill_id` had a valid matching source fill;
no negative or above-initial remaining amount was found. The 152 entry path is a
DEX-mark synthetic Paper path: it uses a negative synthetic execution identifier,
snapshot price and 400 bps configured cost. It does not exercise order-intent, live
quote, execution-attempt or execution-result adapters. That boundary is now emitted
by supervision rather than hidden.

### System-wide baseline

The 30-minute 05:47Z snapshot measured 1,299 evaluated tokens, 32 tokens with at
least one strategy match, and 17 traded tokens. The 506 strategy positions represent
fan-out across independent Paper accounts, not 506 independent opportunities. The
largest token carried 76 strategy arms. A read-only 10-arm shadow replay would have
blocked 84.09% of the last four hours' positions, but this is not deployed because
the replay is observational and order-dependent.

## Implemented engineering fixes

1. The five-second hydration cycle now reserves up to 8/10 existing batch slots for
   lifecycle follow-ups while retaining at least two first-hydration slots. The full
   discovery cycle reserves at most half of its existing budget. Total request and
   concurrency ceilings are unchanged.
2. Follow-up selection remains chain-fair, but within each chain it prioritizes an
   actively watched token and then the nearest lifecycle deadline before oldest due.
3. Every 152 proxy failure now records an auditable reason: missing/invalid snapshot,
   identity or causality failure, missing prior exact-pool frame, insufficient depth,
   trades, buy share, or volume, Paper-only boundary, or an explicit safety veto.
   These are evidence rows, not fabricated safety facts and not automatic buys.
4. `scripts/supervise_metrics.py` now reports due follow-up count/lateness, current
   mark age, admitted decisions without any auditable outcome, fill lineage errors,
   and the synthetic-Paper versus order-intent fill boundary. Its error queries now
   use `julianday()` and exclude cases already marked `fixed`.

## Verification and rollback

- Focused suite: 11 tests passed.
- Broader runtime suite: the new tests and affected paths passed; seven unrelated
  pre-existing failures remain in dirty-worktree active-version and partial-runtime
  fixtures. They are not caused by this patch and are not represented as passing.
- Rollback: revert the assurance commit. This restores the prior 2/10 follow-up
  allocation and removes the new evidence/monitoring only; database history remains
  append-only.

## Forward acceptance gates

After restart, the due-follow-up count and p90/p99 visible-frame gap must trend down
without increasing Dex error rate, primary hydration starvation, held-position quote
latency, or database lock failures. New 152 strategy matches must have either a
position/participant outcome or a named safety evidence row after the grace window.
No profitability claim is allowed until enough independent, cost-adjusted forward
cohorts mature.
