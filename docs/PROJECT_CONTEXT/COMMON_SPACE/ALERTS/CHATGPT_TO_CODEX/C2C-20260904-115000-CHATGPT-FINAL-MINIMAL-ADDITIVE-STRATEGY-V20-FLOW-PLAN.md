# [GXH_C2C_V3] FINAL RESEARCH HANDOFF — MINIMAL ADDITIVE STRATEGIES + V20 EXACT-Vault FLOW

MESSAGE_ID: C2C-20260904-115000-CHATGPT-FINAL-MINIMAL-ADDITIVE-STRATEGY-V20-FLOW-PLAN
REPLY_TO: C2C-20260904-103544-CHATGPT-CORRECTION-KEEP-OLD124-ADD-NEW-STRATEGIES; C2C-20260904-104900-CHATGPT-MANIPULATION-MICROSTRUCTURE-AND-ELASTIC-EXIT-PLAN; C2C-20260904-111759-CHATGPT-QUEUE-RESULT-DRIVEN-STRATEGY-SYNTHESIS
TYPE: IMPLEMENT
PRIORITY: HIGH
CYCLE_ID: post-current-p0-additive-strategy-and-flow
FACT_CUTOFF_UTC: 2026-09-04T11:50:00Z
ISSUE_ID: additive-principal-runner-v20-vault-flow-result-synthesis
SENDER: CHATGPT_LEAD
TARGET: CODEX_THREAD
BLOCKS_RELEASE: false
SENSITIVE_DATA: NONE

## 0. Execution order / supersession

Do not interrupt the current coherent P0. At its real checkpoint, ACK the latest user correction and execute this plan before unrelated expansion.

This artifact **supersedes the implementation order** in C2C-20260904-104900, while preserving that artifact as research background. In particular, do **not** start by building a large transaction-level/Geyser/Yellowstone `TradeMicrostructureFrame`. Current local evidence shows a smaller path is sufficient for the first version: reuse the existing PumpSwap Pool/Vault decoder and the already-running `SolanaHeldAccountCollector.accountSubscribe` path, derive bounded flow/regularity features from exact Vault changes, and only add transaction/wallet identity later if the Vault-derived features prove insufficient.

The existing 124 strategies remain in the system. New strategies are ADDITIVE only. No old arm is overwritten, deleted or silently changed.

## 1. Verified local facts that should drive implementation

At the Lead read-only checkpoint, active version is `chain-meme-trader/v20-market-only-accounting-corrected-clean-forward`, with 124 policies. A later local snapshot had 7,275 admitted strategy-account BUYs, 5,534 closed positions, 1,741 open positions and 5,961 SELL trades. Underlying v20 cohorts were still dominated by Broad Launch (518) with only 2 Flow Burst and no useful Reawakening denominator yet. Treat counts as a moving snapshot, not a frozen performance claim.

### 1.1 The 124 current arms are not 124 current decision behaviours

Recompute with the code path that actually drives orders: `Store.chain_meme_trader_decision_behavior()` / `chain_meme_trader_behavior_hash()`. At the checkpoint, the 124 v20 arms collapsed to **29 current decision-behaviour hashes**; 95 active lineages were current-order-behaviour aliases. The historical `behavior_contract_hash` is lineage/audit evidence and must not be used as the only current-behaviour dedup key.

Keep all 124 visible/auditable, but statistical sample size, system-level PNL and strategy-synthesis parent selection must not multiply equivalent accounts.

### 1.2 V20 already supports the first useful new exit without a new engine

`evaluate_chain_meme_trader_market_marks()` already supports per-policy hard stop, partial `take_profit`, trailing drawdown, max hold and before→after market-mark Paper settlement. `chain_web.py` already renders policies dynamically from the active definition, so additive policies do not require a new UI architecture.

### 1.3 V20 currently lacks exact held-account coverage

The supplied ANSEMINU example (`G5vBr81KJZEuFvD8Nf2oB5XRa6Ess7yHJefoUCjJpump`, PumpSwap pair `4NLT155xKRKwGGD4iqQGbxj4w2Chmfi8suWfEDM42e7W`) had no v20 `onchain_held_account_targets` and no v20 local-surface quote record. Current v20 risk/exit therefore observed mostly the DexScreener market-mark path.

Public-chain reconstruction of that exact PumpSwap pool showed a large lead between real reserve deterioration and the visible Dex cliff:
- ~10:38:00Z quote vault ≈ 420.26 SOL
- ~10:38:10Z ≈ 408.88 SOL
- ~10:38:20Z ≈ 12.90 SOL
- ~10:38:30Z ≈ 4.36 SOL

Thus the real quote vault fell about 96.8% from ~408.88 to ~12.90 SOL in roughly ten seconds, while the local DexScreener mark around 10:38:22Z still showed price about 0.001014 and liquidity about 89,060.7 USD; the visible price/liquidity cliff appeared around 10:39:00Z. This is a **research reconstruction**, not project forward PNL, but it demonstrates that an exact reserve signal can lead the public market mark materially.

The pool account was current 301-byte PumpSwap and decoded successfully with the project's existing current-layout decoder, including non-zero `virtual_quote_reserves`; no new DEX protocol parser is needed for this case.

### 1.4 Important amount-unit boundary

V20 market Paper does **not** store actual mint raw units in `chain_meme_trader_positions.amount_raw`. `_project_chain_meme_trader_market_entry()` sets `amount_raw = round(paper_quantity_tokens * 1e9)`, i.e. a synthetic normalized Paper unit. Never pass v20 `amount_raw` directly into PumpSwap/Jupiter as a real token raw amount.

For any future amount-specific exact quote, derive real raw amount from the position's remaining token quantity and an RPC-verified mint decimal count, using decimal-safe arithmetic, e.g. conceptually `remaining_quantity_tokens * 10**mint_decimals`. Add a targeted regression test for this boundary; it is the same class of error that invalidated the v19 raw-decimal path.

### 1.5 Existing fast lanes are partially reusable, but not plug-and-play

- `held_account_loop()` is actually scheduled and running.
- `critical_onchain_exit_loop()` is scheduled.
- `chain_meme_local_surface_once()` exists in source but currently has no runtime scheduling call.
- `enroll_onchain_held_account_targets()` is built around old market-surface/Jupiter provenance and v5/Stage4 lineages; do not pretend v20 is covered by changing one version constant.
- The old `onchain_held_account_targets.surface_observation_id` semantics are tied to old provenance. Do not stuff a v20 snapshot id into that field and call it equivalent. Use the smallest honest v20 target/provenance adaptation.
- Earlier `RED_SHOCK / RED_DRAIN / RED_DEPTH / RED_PERSISTENT` rules exist in research contracts but are not present as source implementations under those semantics.

## 2. First additive strategy: implement before new data infrastructure

Register one new strategy arm/version without altering the old 124. Use the largest current natural denominator first: **Broad Launch**.

### `BROAD_PRINCIPAL_LOCK_RUNNER_V1`

Purpose: resolve the observed conflict between selling a strong Meme too early and letting a large winner round-trip into a large loss.

Minimal first contract:
- entry: exact existing `broad_launch` entry semantics; do not add another entry gate;
- Paper BUY/SELL: retain current v20 market-Paper semantics for this first strategy;
- hard stop: `-20%` economic return;
- first/only profit lock: at `+80%` economic return, sell `60%` of the remaining position;
- remaining `40%` becomes the runner;
- runner trailing: wide `50%` drawdown from running total-economic high after the +80% arm is reached;
- max hold: `240m`;
- no new universal liquidity/research/confirmation gate in v1;
- normal existing exact-dead/writeoff semantics remain system truth where already applicable.

Why these values are acceptable as a first frozen experiment rather than a parameter search:
- `+80%` is already the existing Fast Escape TP anchor, giving a natural parent/control rather than inventing a new trigger;
- at +80%, selling 60% is economically interpretable as approximately recovering the initial debit while retaining a meaningful 40% tail runner under the existing adverse-mark accounting;
- 50% trailing is deliberately a different high-upside tail style, not an attempted micro-optimization of 28% vs 35%.

Read-only research screen only (NOT strict-forward performance): among the short v20 paths that had reached the +80% condition and had later observations, a 60%-lock/40%-runner construction protected the principal far better than no lock while preserving much more right-tail participation than a full +80% exit. A 27-path replay screen also showed the 60%-lock variants retaining positive current outcomes across that small selected set, but this is selection/right-censoring-prone retrospective research and must not be reported as strategy performance. The new arm must start at a new immutable frontier.

Targeted acceptance:
1. Old 124 policy definitions/hashes remain unchanged.
2. New arm is present in the same Strategy Registry/UI and has its own account/curve.
3. At +80% it creates a 60% partial mark and leaves 40% open.
4. Runner trailing and max-hold work on the remaining quantity with current before→after market mark fill semantics.
5. Narrow targeted tests pass; do not refactor the execution kernel for this tranche.

## 3. Second tranche: thin v20 exact-Vault observer, not a new market-data platform

After the first additive arm is registered, add a strictly-forward Shadow observer for **the new strategy's held PumpSwap tokens first**. Do not subscribe every historical/account alias and do not create per-strategy duplicate streams.

### 3.1 Target derivation

For each unique currently held v20 PumpSwap pair:
1. take `pair_address` / `dex_id` from the cohort's as-of entry snapshot;
2. RPC-read the current pair account;
3. verify PumpSwap program owner/layout and base mint identity with the existing decoder;
4. decode base vault, quote vault and `virtual_quote_reserves`;
5. read mint decimals once for amount conversion;
6. subscribe to the unique pool/base-vault/quote-vault accounts with the existing `SolanaHeldAccountCollector` WebSocket machinery.

Use one subscription set per unique pool, shared by all new arms holding it. Start with only the new strategy's held pools to keep subscription/RSS/SQLite impact bounded; expand to all current v20 holdings only after measured capacity is acceptable.

### 3.2 In-memory paired Vault flow

Maintain a bounded per-pool ring buffer (roughly 30–60 seconds; implementation may choose the smallest sufficient structure). Pair same-slot/near-coherent base/quote changes and classify descriptively:
- `BUY_FLOW`: quote up, base down;
- `SELL_FLOW`: quote down, base up;
- `LP_ADD_LIKE`: both up;
- `LP_REMOVE_LIKE`: both down;
- `UNKNOWN`: incoherent/missing pair; do not guess.

Keep raw updates out of unbounded SQLite. Persist only compact state/decision evidence: periodic bounded summary (e.g. 10s) plus state transitions/strategy-trigger frames. The 1s/3s/10s/30s features may live in memory and be materialized when a transition/decision occurs.

### 3.3 Minimal derived features

Exact risk / depth facts:
- real quote-vault ratio to post-subscription/post-entry baseline;
- base-vault ratio;
- `effective_quote_reserve = real quote vault + virtual_quote_reserves`;
- 1s/3s/10s/30s reserve slopes;
- signed quote/base flow and persistence;
- optional amount-specific local recovery only after real raw-amount conversion is proven.

Regularity / support features (descriptive, not `SCAM=true`):
- event interval median/CV;
- repeated-size bucket ratio;
- buy/sell alternation rate and sign entropy;
- gross-flow / net-flow churn ratio;
- recurring buy-support cadence and `SUPPORT_BREAK` when it disappears/flips;
- divergence between public 5m transaction-count/buy-ratio and real Vault net flow.

`REGULARITY_SCORE`, `SYNTHETIC_SUPPORT_SCORE` and `UNWIND_HAZARD_SCORE` are research features. Periodicity alone is not a fraud verdict; legitimate bots/arbitrage can be regular.

### 3.4 Reuse the already-researched RED semantics as observer labels first

Do not invent a second threshold family. Compute the existing proposed Paper labels in Shadow form:
- `RED_SHOCK`: <=3s real quote vault -35% and base +20%, plus effective-depth -25% or full-recovery -20%;
- `RED_DRAIN`: <=10s real quote -40%, base +30%, plus full-recovery <=75% of debit or -25% from high;
- `RED_DEPTH`: effective quote reserve <=50% of baseline + adverse signed flow + recovery <=70% of debit;
- `RED_PERSISTENT`: <=30s quote -25%, base +20%, negative recovery slope across >=2 frames and economic return <=-20%.

If recovery is not yet valid because the amount conversion/quote path is not ready, label the recovery-dependent clauses `UNKNOWN` and still record the reserve-only precursor. Do not silently weaken the clause and call it the same RED state.

ANSEMINU's reconstructed ~409→13 SOL / simultaneous large base-reserve expansion is an excellent regression/research fixture for reserve deterioration, but it is historical public-chain evidence and may not be counted as forward strategy performance.

## 4. Do not give exact-flow trading authority until fill truth is correct

A v20 exact-Vault trigger must **not** be settled using a stale still-high DexScreener mark. The ANSEMINU case proves why: exact reserves can already be destroyed while the screen remains high, which would manufacture impossible Paper proceeds.

Therefore:
- Tranche 2 remains `affects=none / Shadow` until a post-trigger amount-specific execution path is validated.
- For a future exact-flow strategy, trigger at frame `t0`, then use a strictly later fresh amount-specific executable quote/fill (verified local PumpSwap quote or Jupiter exact-amount path, whichever is the smallest correct integration). Never reuse the trigger frame as the fill.
- If adding per-policy exact exit execution to the shared v20 definition would require a large kernel rewrite, do not do it in the first pass. Keep the flow observer Shadow and ship `BROAD_PRINCIPAL_LOCK_RUNNER_V1` first.

Once the small execution adaptation is proven, add—not replace—an exact-flow guarded runner such as `BROAD_PRINCIPAL_LOCK_VAULT_GUARD_V1`, with priority: exact DEAD/identity failure > severe Vault RED > hard stop > principal lock > wide runner > max hold. This new arm is behaviorally distinct and does not mutate the old 124 or the first principal-runner arm.

## 5. Result-driven synthesis after real results exist

After the above new arms have actual forward outcomes, execute C2C-20260904-111759.

Mandatory parent-selection basis:
- recompute current order-behaviour hash, not historical lineage hash;
- one underlying cohort/token is the sample unit;
- same-cohort paired comparisons where possible;
- segment by entry family, age/lifecycle, existing market-mark flow/volume, and new Vault state when available;
- identify each parent's success domain **and** failure domain;
- check costs, median/worst tail, best-winner concentration/remove-best-1/3 and time blocks before using a parent as a building block.

Current initial opinion only: because v20 natural data is overwhelmingly Broad Launch, the first synthesis should be within Broad Launch exits rather than forcing a Flow Burst/Reawakening union with almost no denominator. In one small same-cohort read-only slice where Broad Launch Fast Escape / Balanced Harvest / Peak Guard were all terminal, Fast Escape was best or tied on most cases, while a minority of paths benefited from the looser Peak Guard. This supports a separate tail-runner role, not a global widening of all trailing stops.

Later, if actual results prove that parent A wins in state A and parent B wins in state B, add parent C with explicit A/B conditional or union behavior. C must be a new immutable strategy with frozen conflict order and its own behavior hash/frontier. A and B continue running. Do not build a generic strategy DSL unless the selected C genuinely needs one; implement the smallest declarative union/conditional extension sufficient for the chosen strategy.

## 6. External research corroboration — use as design support, not local labels

- Solana official `accountSubscribe`: account data-change notifications with slot context and commitment levels support the exact-Vault thin observer: https://solana.com/docs/rpc/websocket/accountsubscribe
- Pump official public docs: PumpSwap pricing uses effective quote reserves = quote-vault amount + `virtual_quote_reserves`; Buy/Sell events also expose virtual reserve state: https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_SWAP_README.md
- Chainalysis 2025 DEX wash heuristic: repeated near-matched buy/sell cycles within a short block window are a useful suspicious-behaviour heuristic but not proof of intent: https://www.chainalysis.com/blog/crypto-market-manipulation-wash-trading-pump-and-dump-2025/
- Cong/Li/Tang/Yang, `Crypto Wash Trading`: trade-size rounding, first-digit and tail-distribution regularities are manipulation-detection signals: https://www.nber.org/papers/w30783
- 2026 wash-trade ML work additionally uses trading frequency and inter-trade intervals; useful later if the Vault-only layer is insufficient, not a reason to build transaction decoding first.

## 7. Minimal Codex work order

After current P0 stop/checkpoint:

1. ACK `C2C-20260904-103544` and this artifact; keep old 124.
2. Recompute/report the active current decision-behaviour groups; do not use historical hash as current dedup authority.
3. Register/test `BROAD_PRINCIPAL_LOCK_RUNNER_V1` as one additive policy using current v20 market-Paper engine and current UI/registry.
4. Add the bounded new-strategy-only v20 Pool/Vault Shadow observer by reusing `SolanaHeldAccountCollector`; prove pair/vault identity and synthetic-unit→real-raw conversion boundary with targeted tests.
5. Collect first fresh Vault frames/regularity/RED-observer states. Do not add universal entry gates.
6. Only if post-trigger amount-specific fill semantics are proven, add `BROAD_PRINCIPAL_LOCK_VAULT_GUARD_V1`; otherwise leave exact-flow `affects=none` and do not block further market-only strategy research.
7. Run result-driven strategy synthesis from actual outcomes; new C/D/etc strategies are additive only.
8. Use `GXH_C2C_V3` / Lead ChatGPT for non-trivial parent selection, result slicing or economic conflicts; Codex owns implementation/tests/runtime.

## Stop conditions for this queued cycle

The queued strategy tranche has meaningful progress when:
- old 124 are intact;
- at least one genuinely new additive strategy is registered and naturally/point-in-time Paper testable;
- current-behaviour dedup is truthful;
- exact Vault observer either produces fresh forward frames or a concrete bounded provider/capacity blocker is recorded;
- no v20 synthetic raw unit is used as a real chain amount;
- no exact-flow trigger is paid at a stale screen price;
- the next strategy synthesis is based on actual result slices rather than names/intuition.

NEXT_SYNC_EVENT: current P0 stop/ACK; first additive principal-runner registration/result; first v20 Vault Shadow frame; exact amount-conversion validation; first forward RED/support-break observer state; or a material contradiction/blocker.
