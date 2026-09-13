# Right-tail discovery-to-Paper recovery 152 — 2026-09-13

## Scope and safety boundary

- Runtime mode: Paper. `config.json.live.enabled=false`; no Live trading was enabled.
- The 15 user-supplied addresses are an ex-post diagnostic cohort, never an allow-list.
- Later appreciation is not proof that a token was safe, liquid, sellable, or causally buyable at first discovery.

## Reproduced failure

At the audit cutoff, 14/15 addresses existed in the local database and none had a Paper position. The missing local address, `0x4b112e1ed0c0cb332d2b39e5dae3bba882f67777`, was still returned by the live DexScreener search endpoint as a BSC/PancakeSwap pair, proving a local coverage/identity gap rather than provider-wide absence.

The first causal breaks were not one universal threshold:

1. An initial curve/thin/missing frame permanently consumed mover follow-up eligibility. Later migrated/usable frames therefore did not receive the dense follow-up budget. The affected historical examples had maximum adjacent snapshot gaps of about 58–305 minutes.
2. Several tokens reached entry evaluation but had `no_active_matching_entry_policy`; the observed market shape had no enabled Paper entry contract.
3. Liquidity was unknown or below the configured entry floor for multiple examples. This is retained as a normal safety rejection for existing strategies.
4. `robinhood:0xe27501d787d647cc82a5b4a7eafd5750386f1b77` generated 68 admitted decisions but had no position. It waited for common safety facts, remained `CHECKED_UNKNOWN`, and expired before security/next-frame completion. This was a verified strategy-to-execution break, not a discovery miss.

See `data/research/righttail152/user_examples_diagnostic.{json,md}` for the per-address evidence.

## Implemented recovery

### Follow-up coverage

`mover_watchlist.py` now consumes the one-shot mover eligibility at the first **qualifying** surface, not the first-ever observation. A missing, curve-stage, or thin initial frame remains eligible for a later usable/migrated exact-pool frame. The waiting map is bounded and this change adds no HTTP request by itself.

### Additive strategy pair

Two new Paper-only matched arms were added without changing existing strategy behavior:

- `alpha152_quiet_acceleration_control_v1`: 30-minute control exit.
- `alpha152_quiet_acceleration_wide_v1`: 180-minute right-tail exit.

Both merge the already-causal trade-activity-growth and buy-pressure-without-breadth signals. Their entry is non-address-specific. The paired entries share the same source fill, so downstream comparison measures exit behavior rather than pretending that duplicated strategy accounts are independent market opportunities.

### Scoped missing-safety proxy

Existing strategies still require the existing common safety path. Only the two opt-in 152 Paper arms may use `causal-dex-continuity/152-v1` when common safety has no usable result. It requires exact token/pool identity, a current frame no older than 30 seconds, at least USD 3,000 liquidity, at least four trades, at least 55% buys, minimum activity relative to depth, and a previous exact-pool frame within 180 seconds with non-decreasing price and at least 90% liquidity retention.

Explicit scam/safety vetoes, stock/RWA exclusion, behavior hazards, token mismatch, stale data, price decline, or liquidity loss still reject. This proxy is expressly not evidence of sellability, tax, wallet distribution, custody safety, or contract safety.

### Strategy convergence

Five redundant negative EXIT150 entry carriers were changed to `PAUSED_NEW_ENTRY` while their positions, exits, trades, marks and immutable policy definitions remain intact:

- `exit150_bank15_v1` -> representative `exit_ladder150_t15_v1`
- `exit150_bank25_v1` -> representative `exit_ladder150_t25_v1`
- `exit150_full15_v1` -> representative `exit_ladder150_t15_v1`
- `exit150_full25_v1` -> representative `exit_ladder150_t25_v1`
- `exit150_widestop_v1` -> representative `exit_ladder150_t20_v1`

They had 49–95 terminal positions each and cost-adjusted realized Paper PNL between -$372.33 and -$747.32. The cleaner `exit_ladder150_t10/t15/t20/t25` set remains as the small comparison set. Existing `RETIRED_DUPLICATE` decisions remain retired. The reversible control receipt is `data/research/righttail152/convergence_applied.json`; rollback is `python scripts/apply_strategy_convergence152.py --rollback`.

## Verification and first forward evidence

- Targeted regression suite: 125 tests passed.
- Python compilation and `git diff --check`: passed (line-ending warnings only).
- Runtime restarted under the Paper supervisor; direct `127.0.0.1:8790/health` returned HTTP 200, `runtime_status=running`.
- Both 152 arms registered at `2026-09-13T05:25:19Z`, activation snapshot 152622.
- By `2026-09-13T05:29:03Z`, the pair had 12 admitted strategy decisions across six unique token opportunities. Four source Paper entry fills produced eight paired strategy positions; the other two admitted opportunities did not become fills in that readback. All fills recorded a 400 bps Paper slippage assumption. One control-arm position had already closed; the control arm's realized result was -$5.83. This early loss is evidence that the execution chain works, not evidence that the strategy is profitable.
- Runtime source health advanced to `2026-09-13T05:29:19Z` with no recorded source error.

## Evidence boundary and next evaluation

Engineering acceptance is complete for discovery -> evaluation -> strategy match -> DEX-mark synthetic Paper fill -> position entry. This path uses the exact-pool market snapshot and the configured 400 bps Paper cost assumption; it does **not** create an order intent, request a live route quote, or exercise an execution adapter. It must not be described as proof of real quote/execution availability. Profitability, right-tail capture, and superiority of the wide exit remain pending natural forward samples. Compare the matched pair only after sufficient independent token cohorts, using cost-adjusted outcome, maximum favorable/adverse excursion, stale/unpriceable exposure, and exit failure rate. Do not select the winner from early account PNL ranking.

The follow-up audit found that six of the first 18 admitted arm decisions had no
position, participant outcome, or safety evidence. Pipeline assurance 153 adds
explicit `SKIP_DEX_PROXY_*` evidence for every proxy-false path and monitors this
invariant. See `PIPELINE_ASSURANCE153_20260913.md`.

## Code and rollback

- Implementation commit: `5fb003b` (`fix right-tail discovery-to-paper gaps`), pushed to `work/2026-09-04-c2c-115000-additive-strategy`.
- Strategy behavior rollback: pause the two 152 arms through the account-convergence control; do not delete policy or historical rows.
- Follow-up semantic rollback: revert the mover-watchlist portion of `5fb003b` only if coverage/error metrics regress.
- Safety proxy rollback: remove `paper_safety_proxy` from the two 152 arms or revert the guarded branch; existing strategies are not coupled to it.
