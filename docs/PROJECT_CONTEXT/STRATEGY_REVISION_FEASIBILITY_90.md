# Strategy revision feasibility 90: P1-A/B/D mechanism audit

Scope: read-only design review for `age_rate_checkpoint_runner_v2`,
`dynamic_principal_recovery_runner_v2`, and a possible Pump-native arm. This
document makes no runtime, store, database, deployment, or registration change.

## Decision

| Proposal | Disposition | Why |
|---|---|---|
| P1-A `age_rate_checkpoint_runner_v2` | **IMPLEMENTABLE AS A NEW FORWARD SHADOW/PAIRED ARM** | It can make one state-dependent 15-minute decision, then delegate every non-triggered position to the unchanged parent exit path. |
| P1-B `dynamic_principal_recovery_runner_v2` | **IMPLEMENTABLE AS A NEW FORWARD SHADOW/PAIRED ARM** | It is an age-rate child that sizes the earliest coverable recovery sale to the outstanding initial cash debit at the next valid frame. Existing settlement remains the authority for actual recovery and filled-only rebasing. |
| P1-D Pump.fun/Solana native strategy | **SHADOW DATA_BLOCKED** | Pump pregraduation reserves, fee-aware exact current *sell* math, and a held-position quote path exist. The live pregraduation watch does not carry the complete same-frame buy-debit, sell-quote, conversion, and fee inputs needed for a new native-entry economic contract. |

Neither P1-A nor P1-B has forward alpha evidence. They are implementation candidates only after an explicit new-forward authorization; they must be appended as new contracts and never mutate or revive a paused arm.

## Evidence and non-duplication

`resource_age_rate_candidate_v1` remains active in the result-89 ledger (+558.5533U across 154 terminals). The old exact-entry pair is already closed: `age_rate_horizon_fast_v1` has +101.7183U across 33 terminals and `age_rate_horizon_runner_v1` has -12.5757U. Result 89 classifies the fast arm as `EXPERIMENT_COMPLETE_POSITIVE` and the runner as failed; it explicitly says the pair remains paused. This rejects a renamed 15-minute horizon copy.

P1-A uses the user-specified frozen decision rule at its first causally valid
15-minute checkpoint:

```
if economic_value_usd < original_debit_usd OR fresh_deterioration:
    request full exit on the next valid market frame
else:
    use the copied parent runner/exit path unchanged
```

`economic_value_usd` is the actual `realized_proceeds_usd` plus the current
remaining-quantity `sell_terms` net value, compared with the original
`stake_usd`. It is not a realized-only recovery check, a gross mark, or a
quoted future recovery. `fresh_deterioration` is true only for an explicit
causal prior-to-current pair where both price and liquidity declined. Missing,
stale, wrong-pool, or no-predecessor evidence is `UNKNOWN` deterioration and
cannot create an exit. If neither disjunct is true, the position falls through
to the unchanged age-rate parent path.

This differs from the retired fixed 15-minute arm because an economically
covered position with no two-field deterioration remains a runner even if it
has no realized partial sale. That distinction uses the value of the actual
remaining quantity under the current Paper sell-cost contract.

P1-B is an age-rate child, not a broad-principal-runner revision. It shares the
current `resource_age_rate_candidate_v1` entry and ordinary exit contract.
At the earliest valid next-frame recovery opportunity it recomputes the
smallest integer raw partial amount whose current Paper `sell_terms` net covers
the outstanding original debit gap. It has no inherited +80% trigger and no
locked fraction. A partial-fill receipt is authoritative; a trigger or a
pre-fill quote is not.

The existing settlement path already supplies the important receipt semantics:
`Store._settle_chain_meme_trader_market_mark` accumulates
`realized_proceeds_usd`, sets `principal_recovered` only at
`new_proceeds >= stake_usd`, and rebases the high-water to `post_price` only
after that actual recovery fill. V2 should reuse those columns and preserve
that condition rather than add a second recovery flag.

## Minimal implementation shape, when authorized

### P1-A: `age_rate_checkpoint_runner_v2`

Add one policy factory beside `age_rate_horizon_policies()` in
`src/memetrader/resource_bound_research.py`. Deep-copy only
`resource_age_rate_candidate_v1`; retain its entry filter, stop, trailing,
execution profile, notional, and parent exit fields. Give the child a new
`arm_id`, `canonical_id`, behavior hash, and forward activation. Do not change
the parent policy or any historical registration.

Add the smallest dedicated hook used by
`Store.evaluate_chain_meme_trader_market_marks`, before ordinary parent
take-profit/runner handling. Its policy fields should be explicit and frozen:

| Field | Value/semantics |
|---|---|
| `exit_mode` | `age_rate_checkpoint_then_parent_runner` |
| `checkpoint_minutes` | `15.0` |
| `checkpoint_economic_basis` | `realized_proceeds_plus_current_remaining_sell_net_lt_stake_usd` |
| `checkpoint_trigger` | `economic_value_uncovered_or_prior_to_current_price_and_liquidity_decline` |
| `checkpoint_deterioration_kind` | `explicit_prior_to_current_both_price_and_liquidity_decline` |
| `checkpoint_state_key` | `age_rate_checkpoint_runner_v2` |
| `parent_exit_arm_id` | `resource_age_rate_candidate_v1` |
| `parent_exit_contract_hash` | copied/frozen parent exit behaviour, recorded in the child policy |

The helper's idempotent state is only `prior_market_point` plus
`checkpoint_status` (`EXIT_TRIGGERED` or `PASSED_TO_PARENT`). It derives the
economic value from `stake_usd`, `realized_proceeds_usd`, and the current
`net_market_position_value_usd`; it never treats a realized-only value as the
coverage test. Parent integration must write one pending mark after `SELL` and
obtain the sale on the next valid frame. No new table is needed.

Pairing must reuse the established source-fill mechanism, not synthesize a
second buy: `source_entry_fill_id`, `source_buy_trade_id`,
`entry_snapshot_id`, execution price, quantity, stake, and `opened_at` must
match the designated source-entry cohort. The existing
`age_rate_horizon_policies()` / `test_age_rate_horizon_pair_shares_entry_fill_and_preserves_parent`
pattern is the narrow precedent. Registration must leave the parent contract
and existing positions unchanged; a paused entry gate must also prevent the
child from queuing a late buy.

### P1-B: `dynamic_principal_recovery_runner_v2`

Append a new child from the current `resource_age_rate_candidate_v1` contract.
Preserve its entry, ordinary exits, source fill, and next-frame Paper fill
model. Add the following recovery step without a separate profit threshold:

1. On the earliest valid visible same-pool recovery frame, calculate
   `debit_gap_usd = max(0, stake_usd - realized_proceeds_usd)`. Use the
   existing `sell_terms` fee/slippage calculation and integer `amount_raw` to
   choose the least sell amount whose modeled Paper net is at least that gap.
   If that amount is strictly below the remainder, submit that partial amount;
   otherwise record `RECOVERY_NOT_PARTIALLY_COVERABLE` and continue the
   unchanged parent exit path. Do not promote an all-remainder estimate into a
   partial-recovery success.
2. At settlement, use the existing actual receipt update. Set
   `principal_recovered=1` only when cumulative `realized_proceeds_usd >=
   stake_usd`; only then reset `highest_signal_price_usd` and
   `highest_economic_value_usd` from the filled post-confirmation frame. A
   failed/partial receipt remains unrecovered and cannot consume the recovery
   tier or rebase a high.

The minimal V2 policy fields are `exit_mode=
dynamic_principal_recovery_runner_v2`, `parent_exit_arm_id=
resource_age_rate_candidate_v1`, `principal_recovery_basis=
initial_actual_cash_debit`, `principal_recovery_execution=
next_valid_market_frame`, `principal_recovery_sizing=
minimum_integer_net_recovery`, `principal_recovery_trigger=
earliest_valid_coverable_frame`, `principal_recovery_rebase=
filled_receipt_only`, and a unique `capital_exit_state_json` key. The existing
symbols to extend are `Store.evaluate_chain_meme_trader_market_marks`,
`Store._settle_chain_meme_trader_market_mark`, `sell_terms`, and
`chain_meme_trader_decision_behavior` (so the fields participate in the
contract hash). Do not create a separate accounting ledger or change the
existing `principal_recovered` definition.

## Pump.fun/Solana pregraduation disposition

The Pons/Robinhood 403 is unrelated to Pump.fun and is not evidence for this
decision. Pump has more local mechanism support than that earlier report:

| Component | Present now | Boundary |
|---|---|---|
| Curve identity and reserve feed | `bonding_curve_identity()` derives the mint-bound Pump PDA; confirmed RPC decoding returns virtual token/quote reserves, real token/quote reserves, total supply, completion, creator, and quote mint. | The active `PregradWatch` persists only real-reserve frames for at most three launch seeds, for five minutes, at a 30-second periodic cadence. It labels them `decision_eligible=false`, `affects=watch_priority_only`. |
| Exact sell arithmetic | `pump_bonding_curve_sell_quote_v1()` ports the SDK integer sell calculation: virtual-reserve output, ceiling-rounded protocol/creator fees, real-quote-reserve capacity, and slippage minimum. | It is a sell calculation for a supplied current `remaining_amount_raw`; it is not a buy/debit quote or a fill receipt. |
| Fees and quote snapshot | `bonding_curve_quotes()` fetches curve, Pump Global, and fee-config accounts in one confirmed RPC bundle; it validates identities, hashes source bytes, selects a fee tier when available, and returns `LOCAL_SURFACE_CURRENT` or explicit unknown/no-capacity states. | USD recovery is direct only for USDC curves. WSOL recovery needs an externally supplied Jupiter WSOL-to-USDC minimum-output conversion. The active pregrad watcher calls `bonding_curve_observations()`, explicitly not this quote method. |

This is enough to retain a bounded Pump pregraduation economics **Shadow**,
but not enough to register a new Pump-native Paper entry strategy. The missing
contract inputs are: an exact same-frame buy quote and initial actual debit for
the proposed raw token amount; a paired, fresh sell quote for that amount; the
WSOL-to-USDC conversion minimum when the curve quote is SOL; and a defined
complete cost contract covering the native buy/sell and any required network
costs. A pregrad reserve observation alone is not a quote, and its reserve
growth is expressly not gross trade flow.

Therefore no Pump-native policy, entry gate, or Paper execution should be
registered. Keep the status `SHADOW_DATA_BLOCKED` until one natural Pump
pregraduation cohort has the required mint/PDA identity, same-bank reserve and
fee data, time-valid buy and sell quote pair, conversion where needed, and
three clocks showing availability before its decision/fill point. The result
does not backfill launch facts or use post-graduation PumpSwap observations as
pregraduation economics.

## Focused helper validation

`tests/test_age_rate_revisions.py` now covers the pure helpers only: economic
coverage with zero realized proceeds, either checkpoint disjunct, future/stale
frame rejection, fee-aware minimum raw rounding, next-frame recomputation, and
the strictly-partial insufficiency result. The helpers do not set
`principal_recovered`; settlement remains responsible for that receipt fact.

When the parent integrates them, add only source-fill preservation and
settlement-rebase coverage around the existing Store tests. Do not run a
threshold sweep, backtest, or parameter grid as part of this revision.

## Source pointers

- `src/memetrader/resource_bound_research.py`: resource age-rate parent and the existing 15/60-minute source-fill pairing factory.
- `src/memetrader/store.py`: `chain_meme_trader_v21_policies`, `chain_meme_trader_decision_behavior`, `evaluate_chain_meme_trader_market_marks`, and `_settle_chain_meme_trader_market_mark`.
- `src/memetrader/age_rate_revisions.py`: pure checkpoint and minimum-recovery helpers introduced for this revision.
- `src/memetrader/pregrad_watch.py` and `src/memetrader/collectors.py`: Pump pregraduation reserve observation, exact sell math, and the separate held-position quote path.
- `tests/test_age_rate_revisions.py`, `tests/test_resource_bound_store.py`, and `tests/test_principal_review_recovery.py`: focused helper coverage and integration precedents.
- `docs/PROJECT_CONTEXT/PAUSED_POSITIVE_AUDIT_RESULT_89.md`, `AGE_RATE_HAZARD_RESULT_85.md`, and `NATIVE_ECONOMICS_RESULT_74.md`: current evidence/status boundaries.
