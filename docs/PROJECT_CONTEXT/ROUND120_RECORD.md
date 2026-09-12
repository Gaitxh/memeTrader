# Round 120 record — what was measured, changed, deployed and verified

Epoch: `chain-meme-trader/funding-20260906-v002-final-1000`
Window analysed: 2026-09-12T18:26Z → 20:05Z. Full evidence: `data/research/diag_round120/`
(scripts + raw dumps, `data/` is gitignored) and the committed summary
`docs/PROJECT_CONTEXT/DIAGNOSIS_ROUND120.md`.

Stage purpose restated by the user during this round: **this is the forward simulation phase
whose goal is to design and implement a usable strategy set.** Paper results are design
evidence; the priority is that the pipeline keeps producing interpretable forward evidence.

---

## 1. Live incident found and resolved

**The DexScreener REST market-data lane had been wedged since 19:24:40Z (40 minutes).**

* Last raw `dexscreener` frame 19:24:40.385Z, last `strategy-observer:dexscreener`
  19:24:54.238Z, `token_market_surfaces` stopped at 19:24:40.385Z. Only GeckoTerminal
  continued at a pinned 60 rows/min.
* Every DexScreener REST poll/hydration round afterwards was `interrupted` (23–31 times),
  three hydration rows stuck `running`. The entry lane had nothing eligible to consume.
* Consequence: no admitted evaluation, decision or BUY fill after **19:23:50.957Z**; the 33
  open positions had `last_evaluated_at IS NULL` and no `pending` marks — **the exit engine
  was not managing live risk.**
* **The provider was reachable the whole time.** An independent live query of
  `api.dexscreener.com` from this host succeeded during the stall (see
  `verify_pools_live.py`). The failure is a local wedge with **no self-recovery**.
* **Resolution:** the supervised trader process was restarted at 20:04:01Z. Verified within
  60 s: DexScreener frames resumed (20:04:47Z), `market_marks`/`market_mark_history`/
  `pool_marks` resumed (20:04:55–57Z), the full reason mix returned
  (`invalid_exact_asof_market_snapshot`, `entry_pool_liquidity_below_configured_floor`), and
  open positions went 33 → 45 with a new entry at 20:04:47Z.

**Open follow-up:** a stalled-lane watchdog (fresh `last_ok_at` with frozen `last_item_at`)
would have caught this. `chain-meme-market-marks` reported `ok_age 0 s` while
`item_age 2086 s`. This is the highest-value stability item for the next round.

## 2. Money diagnosis (the numbers that matter)

| | positions | stake USD | realized USD |
|---|---|---|---|
| written_off | 169 | 3,380.00 | -3,380.00 |
| closed | 148 | 2,883.54 | -379.66 |
| open | 33 | 660.00 | 0.00 |
| **total** | **350** | **6,923.54** | **-3,759.66** |

* **89.9% of the loss is 169 rows that are really 4 data reads on 4 BSC tokens.** Excluding
  them: -220.11 over 92 positions / 1,840 USD = **-12.0%**, against a frozen ~9.2% round-trip
  cost → entry edge ≈ -3% before costs on this window.
* **350 positions were ~11 independent bets.** Per-token: `{1: 5, 30: 1, 55: 1, 57: 2, 65: 1,
  81: 1}`; worst single-token burst **40 positions in one second**. BSC = 74% of positions and
  94% of the loss.
* **The write-off was correct.** Live re-query confirms all four pools are genuinely dead
  (`liquidity.usd = 0`, quote reserve 0.0032 USDT, `priceChange -100%`, `txns 0/0`). A
  parallel workstream's "provider artifact, 1,320 USD recoverable via `COLLATE NOCASE`"
  conclusion is **refuted**.
* **The take-profit ladder is unreachable.** Measured per-position peak economic return:
  p50 +22.7%, p90 +34.8%, **p100 +55.0%**; +20% reached by 51.0%, +30% by 32.0%, **+60% by
  0.0%**. The configured first tier is +80% (and +100% on the one arm that has tiers).
  Result: `next_tp_index = 0` and `principal_recovered = 0` on **all 350** positions — not one
  profit was ever banked. Total give-back **4,508.94 USD**.
* **The stop sits inside the noise.** `hard_stop_return = -0.20` economic on 84/92 arms = a
  **-13.3% price move**; median actual trigger -16.3%; 44/92 fired within one minute; the
  pool's own 30-second move is p90 9.49% / p95 18.65%. `hard_stop_liquidity_veto_usd` was set
  on **0/92** arms, and all 92 fired in pools holding ≥69,937 USD.
* **Exit counterfactual (design evidence, this window):** reachable tiers
  (+20%/50% · +30%/25% · +60%/15%) with a -35% economic stop = **-1,181.61 USD**, versus
  -3,759.66 actual. **Banking at +20% is worth ≈ +2,578 USD here.**

## 3. Coverage root cause (why most tokens never reach a decision)

* The v6 **enrollment lane has zero admission-capable unpaused policies**: all 131
  admission-capable arms carry `entry_paused=True`; all 206 unpaused arms are observer-mode.
  `snapshot_policies` is therefore empty on 100% of enrollment snapshots and
  `no_active_matching_entry_policy` is structural (3,718/3,718 rows).
* The pause comes from `kv: chain-meme-account-convergence/v1:<version>`, contract
  `attachment-strategy-exit-controls/v1`, `operation=pause_new_entry_preserve_natural_exit`,
  237 arms. **Engineering defect:** `definition["policies"]` is merged *before* the pause loop,
  so the control also paused 110 runtime-addition arms, 5 of which were registered only 16 s
  earlier. Re-enabling the 126 paused base arms is a **user-authorization boundary**, not a
  mechanical fix.
* **51.5% of evaluations (5,995 rows) are observation-only and can never admit.** Their
  `feature_json` lacks `age_seconds`/`m5_trades`/`m5_volume_usd`/`signal_age_seconds` on
  5,995/5,995 rows although the source snapshots carry all of them; the two lanes use
  **disjoint snapshot ids**.
* **489,718 arm-instances blocked at `await_distinct_dex_trajectory_frame`.** The engine's own
  counters: 954 frames accepted, only **321 (33.6%)** produced a usable 30 s window, 371 gap
  resets — because `window(rows, 30)` needs ≥3 frames with every gap ≤30 s while the real
  cadence is 60–120 s. `pending_signal_expired` 6,052.
* Two dead features: `cooldown_seconds` is null on 3,718/3,718 rows (the family-episode
  cooldown has never run), and `tx_rate_acceleration`/`volume_rate_acceleration` are saturated
  at exactly `1e6`, so their `>= 3.0` tests are always true and carry no information.
* WS-D refuted the earlier "cash exhaustion" explanation: **443/443 arms can open a 20 USDC
  position** (min arm cash 880). `shared_available_cash_usd = 0.0` is `min()` of an **empty
  dict** — a fabricated value, not a measurement.

## 4. Changes implemented in this round

**New: `src/memetrader/pool_concentration.py`** — a pure, testable cross-arm per-pool exposure
cap. Why: one accepted frame fanned out to 30–81 arms on one pool, turning a single rug into
169 written-off positions. Design:

* `max_arms_per_pool = 8` (worst measured: 81), `max_new_arms_per_pool = 3` per settlement
  pass (worst measured burst: 40).
* Unknown pool identity → **fail open**; missing/invalid inputs → never block.
* `max_arms_per_pool: null` (or `cross_arm_pool_concentration: false`) on a definition →
  byte-identical previous uncapped behaviour, so historical epochs are unaffected.
* Refused intents are marked `failed` with reason `pool_cross_arm_concentration_cap`.

**Wired into `Store.settle_chain_meme_trader_execution_result`** via
`_chain_meme_entry_pool_identity`, `_chain_meme_open_arms_on_pool` and
`_chain_meme_pool_concentration_allows`, plus a per-pass counter
(`pool_arms_added_this_pass`). No existing arm contract, threshold or policy field was
touched.

**Correctness fix in `_dust_read_contradicted`:** the mark-history reference query now joins
`pair_address` with `COLLATE NOCASE`. The dust payload is lower-case while the pool's own
history is checksum-case, so the guard could not see 67 and 95 rows of healthy marks. Honest
impact: this restores the guard's visibility but **changes none of the four measured
write-offs** (the guard's own `price_now >= median_price * 0.5` test declines for a collapsed
price regardless).

**New test: `tests/test_pool_concentration.py`** — 12 tests pinning the measured worst case,
the reachable healthy cluster, the explicit opt-out, fail-open on bad input, and the store
gate's counting/refusal telemetry. `pytest tests/test_pool_concentration.py
tests/test_dust_read_guard.py` → **19 passed**.

**Deployed and verified:** process restarted 20:04:01Z, new manifest pid 31264 loaded, marks
and entries confirmed live.

## 5. Next-round priority (unchanged ordering, evidence-backed)

| # | action | expected value |
|---|---|---|
| P0-1 | **Stalled-lane watchdog** (fresh `last_ok_at` + frozen `last_item_at` ⇒ restart/alert) | removes a 40-minute blind spot that left 33 positions unmanaged |
| P0-2 | **New exit-carrier arms** with reachable tiers (+15~20% first tier, bank ≥50%) and a -35% economic stop, plus a liquidity veto on stops | ≈ +2,578 USD on this window; existing arms untouched |
| P0-3 | **Cadence-aware trajectory engine** + new arms reading it (≥2 observed frames spanning ≥30 s) | unblocks 489,718 blocked arm-instances |
| P0-4 | **Owner decision:** the 126 paused base arms / funding activation registration | currently gates 2,124 tokens |
| P1-1 | Index `(definition_version, evaluated_at, id)`; stop writing 67 KB of JSON for observation-only rows | 30–358 ms → ms; ~235 MB and ~50% of write pressure removed |
| P1-2 | Self-review loop: per-arm / per-token / per-exit-reason win-rate and payoff plus the counterfactual replay | makes the next parameter choice evidence-based |

## 6. Limits of this round's evidence

* All counterfactuals replay only marks observed **strictly after** each position opened, on
  one 87-minute window with 11 tokens. They are design evidence, **not** forward-proven
  performance, and they inherit the mark history's own ceiling (three pools printed an exact
  `49,999.99` liquidity ceiling; p90 and p95 peak returns are both +34.8%, i.e. saturated).
* `pretrade_rug_safety_assessments = 0` and `pretrade_rug_safety_registrations` covering
  **Solana only** are reported as measured; whether that is intended is left open.
* `token_discovery_quote_attempts` and `source_poll_attempts` are both **0 rows**, so the
  DexScreener failure *mode* (timeout vs 429 vs wedged client) is inference, not proof.
* `src/memetrader/store.py` currently carries both this round's guard and pre-existing
  uncommitted changes from earlier rounds; only the new files and this record were staged.
