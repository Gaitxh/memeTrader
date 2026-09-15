# Lifecycle follow-up backpressure repair 179 (2026-09-15)

## Observed failure

- The current Paper period remained healthy, but `supervise_metrics` reported 797 due
  lifecycle follow-ups, with the oldest frame about 82 minutes late. A later bounded
  read showed 862 due rows and valid-pool frames 86-88 minutes late.
- During one production hour, market follow-up exposures included 5,890 Robinhood
  `no_pair` receipts for only 580 distinct tokens. Those retries were 84.5% of all
  6,969 follow-up receipts in the same window.
- The old earliest-final-deadline ordering selected twelve just-due `no_pair` rows in
  a 15-row shadow batch while hundreds of valid-pool rows remained more than an hour
  late. Their final lifecycle deadlines were not imminent.

This was a scheduling/backpressure defect, not evidence that the liquidity, identity,
or strict point-in-time gates should be loosened. Missing quotes remain non-evidence.

## Repair

1. Preserve global capacity lending across chains.
2. Protect lifecycle rows whose final deadline is within 15 minutes, ordered by that
   deadline.
3. Order every other due row by its scheduled `next_attempt_at`, preventing a stream
   of newer short-horizon rows from starving older frames.
4. Keep the first lifecycle `no_pair` confirmation at five minutes, then back off
   consecutive `no_pair` results to 15 minutes. A recovered fresh snapshot resets the
   state to `hydrated`; no stale or missing observation is promoted to a signal.

No provider ceiling, pool floor, safety filter, strategy rule, execution behavior,
account, position, funding period, or historical row is changed.

## Verification and forward acceptance

- `pytest tests/test_followup_backpressure179.py tests/test_pipeline_assurance153.py -q`:
  7 passed.
- `pytest tests/test_runtime.py -q -k "growth_followup or growth_followups"`:
  2 passed.
- Production-database shadow selection kept the one row 10.6 minutes from expiry,
  then selected fourteen valid-pool rows 86-88 minutes late. The old order selected
  mostly just-due `no_pair` rows with roughly 2.5 hours still remaining.

After deployment, compare equivalent windows for due follow-up count, oldest/mean
lateness, follow-up `no_pair` requests per distinct token, fresh snapshot persistence,
strict-as-of refusals, discovery-to-evaluation latency, and source timeout rate. This
stage is accepted only if useful fresh-frame service improves without deadline expiry
or degradation of the first-hydration lane.
