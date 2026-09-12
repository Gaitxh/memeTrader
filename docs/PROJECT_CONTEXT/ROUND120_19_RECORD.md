# ROUND 120-19 RECORD — ACTIVITY-FLOOR150 landed and verified live

Date: 2026-09-13
Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Mode: paper (`live.enabled=false`).
Change: `024b0d6` (pushed). Two new ENTRY arms. **No existing strategy modified.**

## 1. What was landed

Round 120-18 found that 404 low-activity BSC positions carry a 78.6% write-off rate at
−15.39 U/pos — about **69.2% of the whole epoch loss** — and that the write-off rate falls
**34.8% → 6.0%** at `trades ≥ 30` on the entry snapshot's own 5-minute activity
(token-clustered bootstrap **+9.73 U/pos, 95% CI [+3.93, +14.17]**). This round builds that
floor as two new arms.

`src/memetrader/activity_floor150.py` (new):

| arm | floor | kind | hold |
|---|---|---|---|
| `activity_floor150_t30_v1` | `buys_5m + sells_5m ≥ 30` | `merged_multi_setup` | 15 min |
| `activity_floor150_v5k_v1` | `volume_5m_usd ≥ 5,000` | `merged_multi_setup` | 15 min |

They are **entry** arms, so unlike EXIT150 they go into `alpha149.SPECS` and emit their own
signal — they must, so the shared acceptance loop can screen them. (Confirmed by round 18:
`alpha149.py:2283` iterates `SPECS` generically.)

## 2. It is a genuine one-factor experiment

The arms reuse the control's `kind` (`merged_multi_setup`), so they fire on exactly the same
mechanism flags and receive the same frozen signal. Their exit contract is the control's,
cloned verbatim: `hard_stop_return −0.2`, `trailing_activate_return 0.3`,
`trailing_drawdown 0.15`, `max_hold_minutes 15`, `take_profit []`, `notional_usd 2.0`,
`entry_match_mode isolated_cohort_observer`, `entry_gate cohort_strict_forward_asof`.

The control is **`alpha149_merged_multi_setup_fast_v1`**, chosen because `merged_multi_setup`
is the highest-volume generic mechanism on this epoch (6 arms × 123 emits per 374 cohorts) so
the matched control has both sample size and an already-characterised verdict (round 16 found
`fast_v1` better than `_v1` with a clean CI).

Verified on the **built** policy, not the override dict: every exit-contract field is equal,
and on all shared keys the only differences are identity/label fields
(`arm_id`, `canonical_id`, `name`, `description`, `entry_family`, `entry_filter`,
`excess_return_vs_arm`). The test asserts exactly that, so a future edit that quietly changes
a stop or a hold on these arms fails.

## 3. Enforcement is opt-in and additive

`store.py`, in the shared cohort-acceptance loop, **after** signal validation:

```python
floor_rejection = activity_floor150.reject_reason(arm, snapshot)
if floor_rejection is not None:
    activity_floor_rejections[arm] = floor_rejection
    continue
```

Deliberate placement: checking *after* validation means a recorded rejection means exactly
"a valid signal existed but the pool was too quiet", not merely "this arm had no signal".
`reject_reason` returns `None` for every arm that is not ours — asserted against the **whole
158-arm registry**, which is what makes this additive rather than a change to an existing
strategy.

Two additions for auditability:

- the floor is declared on each arm's own `entry_filter.activity_floor`, so a reviewer sees it
  in the **registered policy body** rather than only by reading the acceptance loop;
- the rejection reason is distinct — `activity_floor_trades_not_met` /
  `activity_floor_volume_not_met`.

Missing activity evidence **never admits** (a snapshot with no activity fields fails the
floor). Measured coverage is complete — 0 nulls in 35,349 snapshots — so this is a safety net,
not a common path.

## 4. Verification (observed, not assumed)

Registration: **321 → 323** additions; both arms at their **own frontier 36360**; the control's
frontier is unchanged (append-only respected).

Registered bodies carry the intended contract (`entry_filter.activity_floor` present,
stop −0.2, trail .30/.15, hold 15, `take_profit []`, 2U, `isolated_cohort_observer`,
`feature_hypothesis merged_multi_setup`).

**The arms trade.** Within ~3 minutes of the restart: `t30` 5 positions, `v5k` 2 positions.

**The floor actually bites.** Per-arm reasons persist in
`chain_meme_trader_v6_cohorts.feature_json → outcomes`:

| arm | rejection reason | ready |
|---|---|---|
| `activity_floor150_t30_v1` | **1×** `activity_floor_trades_not_met` | 7× `cohort_frozen_opportunity_ready` |
| `activity_floor150_v5k_v1` | **5×** `activity_floor_volume_not_met` | 4× `cohort_frozen_opportunity_ready` |
| `alpha149_merged_multi_setup_fast_v1` (control) | **0** floor reasons | 27× ready |

Both arms reject *and* accept; the control is untouched. `v5k` rejects more than `t30`,
consistent with the measured pass rates (47.2% vs 59.3%).

A correction to my own expectation: I first expected the reason in
`chain_meme_trader_v6_entry_evaluations.reason`, but `store.py:28327` persists
`observation_reason` (`cohort_observation` / `pattern_observation`) there, **not** the per-arm
reason. The per-arm reason lives in the cohort `outcomes` map. Verified empirically rather than
assumed.

## 5. What this round did NOT do

- Did not modify, retune, pause or replace any existing arm.
- Did not touch the concentration cap (still OFF by default; the user declined it twice).
- Did not change any stop, hold or exit contract.
- Did not judge the arms — 7 positions is far too early. The in-sample caveat from round 18
  stands: the effect is concentrated (3 of 24 tokens carried 83% of the round-17 take-profit
  gain) and the best combined configuration still lost −506U at P(profitable) = 12.9%.

## 6. Next actions

1. **P0 — let ACTIVITY-FLOOR150 accumulate, then read it.** The verdict is
   `activity_floor150_*_v1` vs `alpha149_merged_multi_setup_fast_v1` on the same signals.
   Watch the write-off rate specifically: the whole hypothesis is 34.8% → 6.0%. Use
   `scripts/paired_arm_ab.py` once each side has ≥20 settled.
2. **P0 — settle `exit150_full15_v1` / `exit150_full25_v1`** to ≥20 per side; they are
   currently positive (+11.22U / +11.24U) against the older arms' −60 to −76U.
3. **P0-1** — re-run `paired_arm_ab.py` as counts grow; add `alpha149_merged_multi_setup_v1`
   to the pause list once it reaches ≥20 paired cohorts.
4. **P1** — if the floor works, look for the next filterable population; if it does not,
   the chain-stratified BSC-death story needs revising.
5. **Do NOT build** a "+15%-touch predictor" (falsified, round 18 §2).
6. P0-3 (evaluation write rate) stays background: ~46 days headroom, state-chain risk.

## 7. Probe artifacts

Under `data/research/diag_round120/` (gitignored), read-only:
`r19_emitters.py`, `r19_preflight.py`, `r19_parent_policy.py`, `r19_built.py`,
`r19_verify.py`, `r19_reason_probe.py`.
