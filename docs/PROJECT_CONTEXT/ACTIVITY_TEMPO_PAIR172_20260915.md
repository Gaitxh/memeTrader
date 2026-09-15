# Activity-conditioned tempo pair 172 - 2026-09-15

## Diagnosis

The deployed tempo matrix already covers fast/slow entry crossed with 5-minute
and 90-minute maximum holds. Its forward evidence shows that simply adding more
unconditioned horizon copies is not useful: the mature three-frame 5-minute arm
has 9 independent token outcomes and `+1.97U`, while its 90-minute counterpart
has 9 and `-10.39U`; the faster two-frame pairs are both materially negative.
The useful unanswered question is whether a sufficiently active mature signal
should be harvested quickly or given a longer right-tail window.

The existing activity study supplies one defensible entry condition:
`buys_5m + sells_5m >= 30` on the decision snapshot. In the measured epoch this
cut the write-off rate from 34.8% to 6.0%, though that result is in-sample and is
not treated as alpha. The new pair therefore combines a known causal signal
with this one common filter and varies only the exit horizon.

A separate reachability defect was found while tracing registration. A cloned
arm could retain its parent's `signal_origin_clock=activation_at`. The alpha
engine's activation time is process start, which can precede a newly appended
arm's frontier forever. Such a clone can emit signals but be permanently refused
by strict-forward validation. Fresh tempo clones now omit that parent clock;
their signal and record timestamps must still be at or after their own append-only
frontier.

## Change

Two new Paper arms reuse the exact `mature_two_step_slow` three-frame mechanism,
notional, risk, stop and trailing contract:

- `alpha149_mature_two_step_t30_fast5_pair_v1`: maximum hold 5 minutes.
- `alpha149_mature_two_step_t30_hold90_pair_v1`: maximum hold 90 minutes.

Both declare the same `min_trades=30` activity floor and the same strict
`paired_entry_group` of size two. A missing buy or sell count refuses entry.
The existing cohort admission logic removes both arms when either side fails
signal, safety, capital, post-frame or activity eligibility, so comparisons use
natural same-token, same-signal cohorts. Nothing historical is backfilled and
no existing policy is retuned or re-enabled.

The shared activity-floor implementation now reads an explicit policy-owned
`entry_filter.activity_floor`, while preserving the original two arm-id floors.
Policies without that declaration remain unchanged.

## Validation and monitoring

- 22 focused tests passed across tempo, activity-floor and the existing strict
  trend/Moonbag pair.
- Tests cover 29/30/missing activity, common pair identity, 5/90 horizon-only
  difference, removal of the stale parent origin clock, same activation time and
  snapshot/evaluation frontier, and idempotent registration.
- Deployment must keep the current funding period and must not reinitialize any
  account.

Monitor signal count, activity rejection count, paired rejection reason,
same-cohort fills, time-to-entry, realized return, MFE/MAE, write-off rate and
exit reason separately for the two arms. Do not select a winner until enough
strict same-cohort outcomes exist; report token-clustered results so one viral
token cannot masquerade as broad evidence. A 5-minute advantage would support
active mature scalp behavior; a 90-minute advantage would support slower
right-tail capture. If neither survives costs, retire the pair rather than
adding threshold variants.
