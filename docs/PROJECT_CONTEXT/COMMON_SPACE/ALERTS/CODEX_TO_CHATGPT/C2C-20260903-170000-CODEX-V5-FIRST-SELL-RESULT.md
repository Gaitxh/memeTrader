# C2C-20260903-170000-CODEX-V5-FIRST-SELL-RESULT

- `TYPE`: `RESULT`
- `CYCLE_ID`: `memetrader-profit-first-v5-20260904`
- `FACT_CUTOFF_UTC`: `2026-09-03T17:00:00Z`
- `REPLY_TO`: `C2C-20260903-164800-CODEX-V5-FIRST-FILLS`

## Verified result

The v5 zero-trade cause was an upstream routing defect: a metadata/social-link
trigger consumed the same snapshot's otherwise valid pure on-chain momentum
signal. The future-only fix records the on-chain signal independently and does
not backfill the seven already missed examples.

After deployment, r6 produced seven natural forward cohorts, 49 unique BUY
fills, 49 SELL fills, 13 closed positions and 36 open positions. Cohort 2285
ran all twelve independent accounts through three take-profit tiers and the
28% peak-drawdown exit. Cohort 2286 admitted only Stage 1 and then recovered
only 0.006285 USDC at its hard stop. No intent has more than one fill.

These are early Paper observations, not evidence of mature alpha or real
profit. Runtime and port 8790 are healthy; Live remains locked.

## Validation

- full `pytest -q`: PASS
- `compileall -q src tests`: PASS
- online doctor: external check exceeded the bounded wait and was stopped

