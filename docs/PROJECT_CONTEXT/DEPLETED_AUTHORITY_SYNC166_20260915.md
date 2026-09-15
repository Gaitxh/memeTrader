# Depleted-arm authority sync 166 (2026-09-15)

## Observed failure

The runtime still attempted entries for Paper arms whose independent 1000 USDC accounts had
less than the ordinary 20 USDC entry notional remaining. This created deterministic cash rejects
and made dead strategies appear active. The authority file had already retired 82 such arms, but
newly depleted arms required another manual database query and JSON edit.

At `2026-09-15T11:35Z`, two unretired arms met the irreversible-within-this-funding-period
condition and had no remaining position to manage:

| arm | cash | open | closed | realized PnL |
| --- | ---: | ---: | ---: | ---: |
| `alpha149_hold_any_band_control_v1` | 13.1711U | 0 | 293 | -986.8289U |
| `alpha152_quiet_acceleration_control_v1` | 18.0086U | 0 | 484 | -981.9914U |

`activity_floor150_v5k_v1` also had less than 20U cash but still had one open position during the
first scan, so it was not eligible. At `2026-09-15T11:44:37Z` that position had closed; the next
scan observed 12.3498U cash, zero open positions, 415 closed positions and -987.6502U realized PnL,
then admitted it as a third candidate. This sequence directly verifies that retirement does not
interrupt exit management and latches only after the final position is gone.

## Change

`scripts/sync_depleted_arm_authority.py` derives the latest account row per arm from the current
running funding period and reports candidates with cash below the authority file's floor and zero
open positions. It is dry-run by default. `--apply` atomically appends only new candidates to the
existing ignored `data/authority/failed_arms_r39.json` file; it does not mutate SQLite, policy
history, fills, positions, funding, or Live settings.

The tool refuses non-Paper/Live-enabled configuration, checks that the authority version matches
the runtime-loaded manifest, and excludes arms already controlled by either lifecycle overlay.
The first two candidates were applied and the Paper runtime alone was restarted through the
existing supervisor. The later zero-position transition was applied and restarted the same way.

## Validation

- Four retirement-focused test files: 14 passed.
- Post-restart manifest: funding version unchanged,
  `chain-meme-trader/funding-20260906-v002-final-1000`.
- Effective retirement overlay: 96 arms total: 85 depleted, 7 dominated, 4 unreachable.
- All three candidates now report `FAILED_ACCOUNT_DEPLETED` from the failed-arm authority source.
- `activity_floor150_v5k_v1` was excluded while open, then retired only after its final exit.
- `/health`, `/api/live?view=summary`, and `/api/performance` respond successfully when localhost
  bypasses the host's HTTP proxy; the apparent 502 during the first check came from `HTTP_PROXY`
  because `NO_PROXY` did not include `127.0.0.1`, not from ChainMemeTrader.

## Continuing monitor

The active two-hour MemeTrader heartbeat now runs the tool in dry-run mode first. It may apply and
restart Paper only when `added_count > 0` and the current-period, sub-20U, zero-open-position
evidence is rechecked. Unchanged rounds remain silent. This removes dead arms from future entry
work while preserving forward history and lets capital-depletion retirement keep pace with the
continuing multi-tempo strategy experiments.
