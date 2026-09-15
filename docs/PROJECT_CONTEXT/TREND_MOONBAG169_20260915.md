# Trend Moonbag 169 - 2026-09-15

## Diagnosis

- `trajectory144_trend_runner_v1` closed 96 independent tokens for +333.188337U, but the
  result is not robust profitability evidence. Removing its largest winner changes the total to
  -73.252142U; the token-bootstrap 95% mean interval is [-3.137930, 13.729977]U and the later
  48-token half is -111.682675U.
- It shares all 96 source entry fills with `trajectory144_early_activity_fast_v1`. The runner is
  +333.188337U and the fast arm is -61.732115U, but 81 pairs tie and only seven favour the runner.
  Therefore the observed advantage is right-tail exit capture, not evidence for a better entry.
- Chain results are mixed: Solana 43 tokens/+505.391200U, BSC 52/-170.286226U and Robinhood
  1/-1.916636U. Do not scale the parent or infer a universal alpha.
- The existing full-exit ladder is depleted and negative at every tested level. On the 144 common
  terminal cohorts, t10/t15/t20/t25 returned -476.044734/-489.623057/-533.547398/-656.081934U.
  Lower full liquidation is less bad, not profitable, and destroys the right tail by construction.

## Forward Experiment

Added one paired Paper experiment without changing any existing strategy:

- `trajectory169_trend_runner_control_v1` is a fresh-capital copy of the trend runner.
- `trajectory169_trend_runner_moonbag_v1` has the same entry, signal, stop, trailing and 30-to-120
  minute trend extension. Its only behavioural difference is
  `minimum_net_debit_keep_half_next_frame/v3`: a fresh executable mark may sell the minimum amount
  needed to recover actual net debit only when at least half the position can remain.
- Both arms use `trajectory169_trend_runner_moonbag_pair_v1`, size two, and receive separate aliases
  of the exact same frozen parent signal. They add no source request and remain Paper-only.
- The inherited old engine activation clock is deliberately removed. Store still requires the
  signal observation and receipt clocks to be at or after each new policy frontier, preventing
  replay of pre-activation signals.

Registration was append-only at one frontier:

- activated: `2026-09-15T12:18:39.211966Z`
- snapshot frontier: `736443`
- evaluation frontier: `729358`
- pre-frontier decisions/positions: zero for both arms
- starting cash: 1000U each; no reset, credit, backfill or Live change

## Verification

- 27 focused trajectory/recovery tests passed initially; the final focused selection passed 13.
- Python compilation and `git diff --check` passed.
- A neighbouring broad test retains a stale pre-existing assertion that cohort policy count is 12;
  the pre-change implementation already exposed 30 and this stage raises it to 32. It was not
  altered to disguise unrelated test drift.
- Runtime restarted under the existing supervisor. `/health`, `/api/live?view=summary` and
  `/api/performance` returned 200. Paper-only and Live locked remained true.
- Loaded manifest at `2026-09-15T12:19:44.120282Z` contains 488 policy IDs. The loaded
  `trend_moonbag169.py` SHA-256 equals the disk hash:
  `e1975d5a84ab09d167cecda1aa83dc5647579309894574f1fb3a8bfdfbc0f72f`.

## Frozen Review Gate

Do not tune or promote from the historical parent result. Review only new paired terminal tokens
after the later common frontier. Keep BSC and Solana results separate and require at least 40 paired
independent terminal tokens, at least five actual principal-recovery triggers, two UTC dates, and
no single token contributing more than half of challenger net PNL. Pause challenger new entries if
its costed mean is non-positive, its paired delta is non-positive, or the token-clustered 95%
bootstrap lower bound of the paired delta is not above zero. Existing positions must continue their
frozen exits after any pause.
