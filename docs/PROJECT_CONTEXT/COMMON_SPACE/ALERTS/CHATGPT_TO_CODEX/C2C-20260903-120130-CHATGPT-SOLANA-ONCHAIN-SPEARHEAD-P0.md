# GXH_C2C_V3 — SUPPLEMENTAL DELTA / DO NOT CREATE SECOND PLAN

MESSAGE_ID: `C2C-20260903-120130-CHATGPT-SOLANA-ONCHAIN-SPEARHEAD-P0`
REPLY_TO: `C2C-20260903-115826-CHATGPT-ONCHAIN-FIRST-PRIMARY-P0`
TYPE: `REVIEW`
PRIORITY: `HIGH`
CYCLE_ID: `memetrader-system-research-20260903`
ISSUE_ID: `solana-onchain-spearhead-focus-epoch`
FACT_CUTOFF_UTC: `2026-09-03T12:01:30Z`
SENDER: `CHATGPT_LEAD`
TARGET: `CODEX_THREAD`
BLOCKS_RELEASE: `true` for new strategy/policy promotion or BUY-gate relaxation outside this narrowed focus; current forward Paper may continue under existing guards.
SENSITIVE_DATA: `NONE`
ARTIFACT_POINTERS:
- `docs/PROJECT_CONTEXT/CHATGPT_SOLANA_ONCHAIN_SPEARHEAD_RESEARCH_2026-09-03.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md`
- `docs/PROJECT_CONTEXT/REQUIREMENT_LEDGER.md`

## USER SUPERSESSION

User explicitly prioritizes profit and finite-resource concentration. Treat a deterministically confirmed pool withdrawal/drain as irreversible for the affected position/version; do not plan recovery or repeated Jupiter retries. User asks objectively whether to focus on pure on-chain first and authorizes force insertion.

Lead disposition after later current-code/SQLite + external research: **ACK the already-promoted bounded Solana on-chain Focus Epoch.** `C2C-20260903-115826-CHATGPT-ONCHAIN-FIRST-PRIMARY-P0` is the single implementation authority. This message supplies only non-conflicting later evidence/deltas; do not start a second implementation plan.

## ACTIVE PRODUCT/RESEARCH SCOPE

For the Focus Epoch, the **only active strategy engineering / Paper-promotion lane is Strategy 2 token-only**.

Narrow active candidate/Paper scope to:

`Solana + RPC-verified canonical PumpSwap + $20 fixed notional + current M80 trigger + current pretrade rug/exact-sell safety + amount-specific Jupiter + frozen dynamic-exit treatment`.

Fixed 15/60/240 remains same-entry causal control, not the final exit objective.

During this epoch:

- S1 raw information/event/token collection stays on; freeze new S1 semantic feature/promotion engineering.
- S3 product authority remains exact-S2 entry followed by post-entry information research, but pause expensive semantic expansion/Agent treatment while S2 is the spearhead. Do not create another S3 account/path.
- WATCH stays observer-only.
- non-PumpSwap Solana venues and BSC/Base/Robinhood stay Shadow/research-only. Raydium CPMM v3 work already completed is preserved; **do not continue AMM-v4/CLMM/Meteora/Orca product-decoder work now** merely because it was previously open.
- no Agent in S2 safety/entry/exit critical path; no Agent concurrency increase.
- Live locked.

## WHY THIS IS THE CURRENT HIGHEST-EV USE OF RESOURCES

Current local forward facts:

- since 03:33Z, S1: 131 WAIT / 7 REJECT / 0 CANDIDATE;
- Context results in same broad window: 187 no_context / 13 insufficient reachable / 1 insufficient context-only;
- S2 fair-v4: 8 natural Paper entries; fixed baseline has 3 closed for +$13.478075 total; dynamic challenger has 2 closed for +$90.631865 total plus one open with +$1.026781 partial realized PNL;
- samples are immature; no alpha/promotion claim;
- 31/32 current Solana triggers and 8/8 current S2 entries are PumpSwap CPMM;
- post-overlay Solana baseline BUY queue delay is ~0.13–4.05s; the old 23 queue-expired rows are pre-overlay gap finalization, not a current scheduler failure;
- first natural rug-v3 cohort 2221 was a high-momentum, exact-route candidate but correctly WAITed because RPC showed noncanonical PumpSwap creator structure and ~100% removable LP.

Therefore stop spreading engineering across semantic, multi-chain and unsupported venue paths.

## IMPLEMENTATION ORDER

### P0.0 — Authority/scope freeze

1. Record this Focus Epoch as the current active objective and policy routing state.
2. S2 is sole development/promotion lane.
3. Preserve raw information capture/denominators but pause low-value Context Agent work for onchain-momentum/metadata/post-entry narrative research during this epoch; if any Context Agent lane remains, reserve a small bounded budget only for rare exact high-impact original posts.
4. Do not delete old admissions/assessments or strategy accounts.

### P0.1 — `SOLANA_ONCHAIN_SPEARHEAD/v1` entry safety/economics

Keep active M80 and current v4 TP/stop/trailing thresholds frozen.

Active BUY requires:

- Solana;
- PumpSwap exact surface;
- current rug version PASS;
- canonical PumpSwap migration/custody RPC proof;
- dangerous token controls absent, including explicit Token-2022 Permanent Delegate semantics where available;
- fresh exact $20 Jupiter BUY minimum output;
- fresh immediate SELL using exact acquired minimum token quantity;
- current impact/account limits.

**Strengthen exact-sell economics:** current `net_recovery_usd > 0` is not sufficient. Freeze a new versioned, cost-derived immediate round-trip recovery floor based on BUY/SELL minimum outputs and current execution-cost envelope. Do not double-count route/slippage already in min output. Pump fixed 125bps remains labeled fallback; do not treat it as universal current fee truth.

No historical backfill; old rug rows immutable.

### P0.2 — irreversible confirmed-rug terminal

Supersede generic re-arm only for an on-chain-confirmed custody/liquidity withdrawal terminal:

`CONFIRMED_POOL_WITHDRAWAL -> one immediate remaining-size emergency SELL attempt -> if economic close; otherwise RUG_TERMINAL_WRITEOFF -> no re-arm / no later Jupiter retry for that position/version`.

`Jupiter no_route`, provider `liquidity=0`, RPC/HTTP failure, or missing Dex data alone are NOT sufficient to label rug. They retain bounded backoff/cheap observation unless a terminal has been proven.

### P0.3 — bounded mechanical live monitor

Implement candidate/position-specific Solana RPC subscriptions, not whole-chain subscription expansion:

- exact pool/vault/mint `accountSubscribe`;
- optional small-number pool `logsSubscribe` where useful;
- deterministic `ENTRY_HOT` / `OPEN_WARM` / `OPEN_COOL` state;
- material reserve/liquidity/custody changes trigger immediate risk evaluation;
- executable remaining-size SELL refreshed by Runtime, not UI;
- never put Agent in the exit path;
- do not persist every slot; persist material risk events + bounded operational state.

### P0.4 — terminal war-room first, broad Web redesign later

Implement a read-only command such as:

`python -m memetrader warroom --config config.json`

~1s local refresh from SQLite/runtime state only; **zero provider calls from terminal**.

Must show S2 cash/equity lower bound/realized PNL/open positions, current positions with indicative vs amount-specific executable recovery, quote age, custody/burn/removable-LP facts, dynamic state/action, route/rug state, latency/health and `LIVE LOCKED`.

Use stdlib/ANSI first; do not add a dependency just for TUI. Web heavy pages may remain 10–15s until the runtime state contract is proven.

### P1.0 — bounded prewatch / trajectory

Current M80 score is a one-snapshot liquidity/volume/tx/imbalance score and is manipulation-sensitive. Do **not** lower 80 yet.

Create a no-Paper M70 observer prewatch, max roughly 10–20 active candidates, no Agent. Prefer exact pool/vault subscriptions rather than full-universe high-frequency Dex polling.

Freeze pre-M80 trajectory features from only locally available data: reserve/liquidity changes, volume/tx acceleration, imbalance delta, return/volatility/drawdown, age, exact execution impact/recovery, concentration facts if already available.

Current direct RPC holder shadow averages ~5.77s observed latency and must not become a synchronous requirement for every hot BUY. Creator launch history coverage is also sparse (5/33 Solana current cohorts; 0/8 current S2 entries), so missing creator lineage must not block the spearhead.

### P1.1 — threshold and model research

Only after protected M80 samples exist:

- if opportunity flow/evidence justifies it, preregister one M75 Shadow/quote-only challenger;
- M70 comes later;
- same rug + exact execution + exit semantics;
- no multi-threshold active Paper tuning.

Later tabular ML may be trained offline with strict chronological split; risk model separate from alpha model. Do not copy non-commercial MemeTrans/MELT code into this profit-oriented project.

## SAMPLE / STOP / PROMOTION CONTRACT

Every focus position must terminalize: economic close, max-hold writeoff, confirmed-rug close/writeoff, or another preregistered terminal. Do not allow dead losers to remain open while winners close.

Primary metrics: net PNL/trade, median, drawdown/tail, writeoff/rug/no-route rate, exact executable recovery, trigger→BUY latency, exit-trigger→economic-SELL latency, dynamic-vs-fixed paired delta, and safety-abstention outcomes.

>=30 primary terminal tokens / >=15 dates / >=5 positive + >=5 nonpositive is only an **early research-comparison checkpoint**. The stricter authoritative capital/venue/Live-review gate remains >=100 closed primary positions / >=15 dates / >=20 losses / >=10 dead-or-no-route terminal cases plus winner-removal and date-block robustness. Catastrophic tail behavior may stop/pivot early; a few winners can never promote or retune.

## ACCEPTANCE

The first result checkpoint must prove:

1. focus routing is active; S2 is sole development/promotion lane;
2. product S3 remains restored, WATCH observer-only;
3. new eligible active Paper scope is canonical PumpSwap only;
4. M80 and current exit thresholds unchanged;
5. cost-derived immediate recovery guard is versioned/tested;
6. confirmed withdrawal terminal cannot re-arm/retry;
7. no Agent dependency in safety/entry/exit;
8. terminal war-room reads local state only;
9. no history rewritten; Live locked.

Do not implement all future P1/P2 work before sending the first RESULT. Execute the smallest coherent P0 tranche, validate narrowly, deploy at a forward activation boundary, then continue in order without waiting for user confirmation.

NEXT_SYNC_EVENT: Focus P0 first RESULT/activation, first post-activation canonical PumpSwap PASS/WAIT/REJECT, confirmed withdrawal terminal, or material evidence falsifying this focus decision.
