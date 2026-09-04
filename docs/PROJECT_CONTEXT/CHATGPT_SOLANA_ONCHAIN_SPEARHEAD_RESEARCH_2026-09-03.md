# Solana On-Chain Spearhead Research — 2026-09-03

FACT_CUTOFF_UTC: 2026-09-03T12:01:30Z
OWNER: Lead ChatGPT research / Codex execution
STATUS: SUPPLEMENTAL_DELTA_TO_CHATGPT_ONCHAIN_FIRST_STRATEGIC_CONVERGENCE_2026-09-03
AUTHORITY: `docs/PROJECT_CONTEXT/CHATGPT_ONCHAIN_FIRST_STRATEGIC_CONVERGENCE_2026-09-03.md` remains the single implementation authority; this file contributes later fact checks and design deltas only.
LIVE: locked / false

## 1. Executive decision

Temporarily concentrate active strategy engineering, Paper-promotion work and execution-learning resources on **one strategy family: Solana token-only / pure on-chain**. This is a bounded Focus Epoch, not a permanent rejection of information/news/social alpha.

Recommended active scope:

`SOLANA_ONCHAIN_SPEARHEAD/v1 = Solana + RPC-verified canonical PumpSwap custody + fixed $20 exact-size Jupiter entry + pretrade rug/sellability PASS + frozen dynamic-exit treatment + fixed-horizon causal control`.

Everything else becomes observe-only/research-only during the focus epoch:

- Strategy 1 information+Token: preserve deterministic source/event/token collection and denominators; freeze new feature/engineering/promotion work.
- Strategy 3 Token→post-entry information: preserve exact S2 paired accounting, but pause expensive post-entry semantic expansion while the on-chain spearhead is being validated.
- WATCH remains observer-only.
- BSC/Base/Robinhood and non-PumpSwap Solana venues remain Shadow/research-only; do not spend P0 engineering budget on them now.
- Live remains locked.

The rationale is not that pure on-chain is already proven profitable. The rationale is that it currently has the best **feedback-to-effort ratio**: exact executable quotes are arriving in seconds, Paper entries/exits exist, causal fixed-vs-dynamic comparisons exist, and the main blockers are deterministic engineering/market-microstructure problems rather than semantic data access.

## 2. Current local evidence

### 2.1 Information strategy has poor current conversion per unit effort

From 2026-09-03T03:33:04Z through the fact cutoff:

- Strategy-1 decision stream: 131 WAIT, 7 REJECT, **0 CANDIDATE**.
- Token Context assessments: 187 `no_context`, 13 `insufficient_reachable_sources`, 1 `insufficient_context_only`.
- Admission ledger contains 423 `global_cooldown_active`, 270 `no_eligible_trigger`, 143 admitted and other reuse/skip rows.

This does not prove information alpha is absent. It proves the current system spends meaningful scheduling/Agent effort without closing the information→canonical Token→executable Paper loop. Continuing to add more semantic machinery now has high displacement cost.

### 2.2 Pure on-chain already has an executable feedback loop

Current version `onchain-only-shadow/v2-20usdc`:

- registered 2026-09-03T03:33:04Z;
- momentum threshold 80;
- 72 current cohorts total: 32 Solana, 18 BSC, 13 Robinhood, 9 Base;
- Solana cohort momentum range 80.0995–92.0053, mean ~85.6654.

Current Solana market-surface distribution:

- 31/32 = PumpSwap CPMM;
- 1/32 = Meteora.

Current fair-v4 S2 Paper entries:

- 8 entries, **8/8 PumpSwap CPMM**;
- fixed baseline: 3 closed, realized PNL sum **+$13.478075**, 5 still open;
- dynamic-exit challenger: 2 closed, realized PNL sum **+$90.631865**, 6 open, with one open position carrying +$1.026781 already-realized partial PNL.

Important paired examples:

- cohort 2179: fixed 15m `-$0.51209`; same-entry dynamic `+$78.323105` after four amount-specific TP fills;
- cohort 2200: fixed 15m `+$15.777079`; dynamic trailing `+$12.308760` — evidence that dynamic is not universally superior;
- cohort 2194: dynamic captured `+$1.026781` on a 20% TP before later observed liquidity collapse/no-route behavior.

The paired sample is far too small for promotion or parameter retuning. It is, however, enough to justify concentrating measurement on this family.

### 2.3 Current entry execution scheduling is no longer the primary bottleneck

The database has 23 old Solana baseline rows labeled queue-delay-expired, but those were historical gap finalizations around 07:48Z for cohorts that existed before the Jupiter-v2 execution overlay was active. They are not current dispatch misses.

For the nine natural Solana baseline BUYs after the executable overlay began, queue delay has been approximately **0.13–4.05 seconds**. Therefore, do not spend P0 work on the obsolete “72% baseline queue miss” interpretation.

### 2.4 Rug safety is now producing real forward abstentions

`pretrade_rug_safety/v3-pumpswap-raydium-cpmm-rpc-custody` is forward active.

Natural cohort 2221 at 11:58:16Z had:

- momentum = 88.9714;
- valid fresh $20 Jupiter BUY quote;
- immediate acquired-size SELL preflight with minimum output ~$18.343493 and modeled net recovery ~$17.943493;
- token controls reported non-dangerous;
- exact PumpSwap pool RPC ownership/vault identity verified;
- but canonical migration structure was false, LP burned ~0%, removable LP ~100%.

The new rug layer correctly returned `WAIT: pool_custody_or_lp_burn_insufficient`, and no new S2 Paper cash mutation occurred. This is exactly the type of forward abstention denominator needed to learn whether safety is worth the opportunity cost.

## 3. Why PumpSwap-only is the correct first scope

Current opportunity data already overwhelmingly lands on PumpSwap, and current executable Paper entries are entirely PumpSwap. Meanwhile the strongest custody proof is also PumpSwap canonical RPC verification.

Therefore, during the focus epoch:

- **active Paper eligibility: RPC-verified canonical PumpSwap only**;
- Raydium CPMM v3 RPC decoder remains research-ready but does not justify parallel product expansion yet;
- Raydium AMM-v4/CLMM, Meteora and Orca stay fail-closed/Shadow;
- BSC/Base/Robinhood stay research-only.

This sacrifices little current observed opportunity flow while sharply reducing safety-decoder, transaction-simulation and fee-model engineering scope.

## 4. Pool withdrawal / rug terminal semantics

User supersession: when on-chain evidence proves the pool/liquidity has actually been withdrawn/drained, **do not consider recovery**.

Implement two distinct classes so data-source failure is not mislabeled as fraud:

### A. CONFIRMED_POOL_WITHDRAWAL / RUG_TERMINAL

Evidence must be deterministic on-chain evidence appropriate to the venue, e.g. a verified custody transition, LP withdrawal/removable supply event, vault drain inconsistent with normal swap economics, or an equivalent program-decoded terminal custody failure.

Behavior:

1. emit immutable `CONFIRMED_POOL_WITHDRAWAL` risk event;
2. if a position remains, perform exactly one immediate amount-specific emergency SELL attempt;
3. if economic SELL succeeds, close with `rug_emergency_exit`;
4. if it fails/no-route, mark remaining position `RUG_TERMINAL_WRITEOFF` using unallocated cost;
5. never re-arm, never retry Jupiter, never treat later provider liquidity as recovery for that position/version;
6. cheap audit observation may continue but cannot reopen the position or alter PNL.

This rule supersedes the generic scheduler re-arm semantics for a confirmed withdrawal terminal.

### B. UNKNOWN / NO_ROUTE / PROVIDER_LIQUIDITY_ZERO

These are not proof of LP withdrawal. Behavior:

- no fake SELL;
- use the current bounded adaptive backoff/cap to protect Jupiter capacity;
- cheap local/Dex/RPC monitoring may continue;
- a new independently valid liquidity/custody state may re-arm only when no irreversible rug terminal has been recorded.

## 5. Entry strategy specification

### 5.1 Keep active momentum M80 frozen for now

Current `momentum_score/v1` uses:

- log liquidity;
- log 5m volume;
- transaction count;
- buy/sell count imbalance.

Do **not** lower 80 now. The score is not too sophisticated; it is too *narrow*. Volume/transaction/buy imbalance can be manipulated by wash/bundle activity. Lowering the threshold before adding trajectory/manipulation-sensitive evidence increases false positives without learning why.

### 5.2 Required active BUY gates

For `SOLANA_ONCHAIN_SPEARHEAD/v1`, a Paper BUY requires:

1. Solana;
2. current M80 trigger under the frozen formula;
3. exact current market surface identified as PumpSwap;
4. `pretrade_rug_safety` current version PASS;
5. canonical PumpSwap migration/custody RPC proof with exact program/layout/PDA/mints/vaults/authorities and frozen removable-LP semantics;
6. Token controls safe: mint/freeze/close/balance-mutable/transfer-fee/transfer-hook/default-state/non-transferable/Token-2022 dangerous authority checks, including explicit Permanent Delegate coverage where applicable;
7. creator malicious-address hard evidence, if present, rejects; missing creator-history lineage does not automatically reject because coverage is currently poor (5/33 Solana cohorts have local create lineage; 0/8 current Paper entries do);
8. fresh exact $20 Jupiter ExactIn BUY quote;
9. fresh immediate SELL preflight using the exact acquired minimum token quantity;
10. normalized price impact within the frozen limit;
11. account/cash constraints;
12. atomic lineage from trigger→rug assessment→BUY quote→SELL preflight→Paper BUY.

### 5.3 Strengthen the immediate round-trip gate

Current rug assessment only hard-rejects exact-size SELL when modeled net recovery `<= 0`. This is too weak economically: a $20 buy that can immediately recover only $1 should not pass merely because $1 > 0.

Do not invent an arbitrary 70%/80% floor. Freeze a versioned **cost-derived immediate recovery floor**:

- authority = BUY minimum token output followed by SELL minimum stable output;
- route/slippage already embedded in Jupiter minimum outputs are not double-counted;
- observed fee fields are used when complete;
- modeled network fee remains explicitly labeled fallback;
- compare immediate minimum recovered value to the frozen entry economic cost;
- PASS only if the round trip is within the current allowed execution-cost envelope rather than a catastrophic hidden-loss route.

Implement as a new rug/execution-policy version; do not mutate old assessments.

## 6. Add behavior trajectory without delaying hot entry

Current hot candidates usually have only 1–3 snapshots in the preceding five minutes, often only seconds of history. Therefore active M80 cannot yet use robust five-minute trajectories.

Use a bounded **prewatch**, not full-universe high-frequency polling:

- enrollment: Solana PumpSwap candidates crossing a lower observer threshold (suggest M70 only as a data-collection threshold, not a BUY threshold) or otherwise entering a small priority candidate set;
- hard bound: at most ~10–20 concurrent prewatch candidates;
- no Agent;
- preserve current M80 active rule;
- maintain cheap candidate state until M80 crossing or expiry;
- prefer pool/vault RPC account subscriptions after exact pool identity is known; avoid repeated broad DexScreener requests;
- only persist material/interval snapshots needed for features, not every slot notification.

Freeze pre-M80 features available strictly before the entry trigger:

- liquidity/reserve change over 30s/60s/120s;
- volume acceleration and transaction acceleration;
- buy/sell imbalance change;
- short-return, realized volatility and peak drawdown;
- pool/token age;
- BUY price impact;
- exact immediate round-trip recovery ratio;
- reserve asymmetry / sudden reserve shock;
- GoPlus top-holder concentration when already available;
- creator initial-buy/history only when forward lineage exists;
- later: candidate-specific unique participant / bundle features from decoded transactions.

Do not synchronously run the current public-RPC holder scan on every hot candidate. Existing holder-shadow observed calls average ~5.77s and have a long error tail, which is too expensive for a synchronous entry path. Use existing GoPlus concentration facts in hot safety and keep direct RPC holder/bundle analysis targeted/asynchronous until a better path is proven.

## 7. Mechanical held-position monitoring — Agent-free

All emergency/risk logic stays deterministic. Agent must never sit in the critical exit path.

Recommended lifecycle:

- `ENTRY_HOT` 0–10m: pool/vault/mint subscriptions active; lightweight market state ~3–5s equivalent; executable remaining-size SELL refresh no slower than ~15s unless a state change triggers it immediately.
- `OPEN_WARM` 10–60m: lightweight state ~5–10s; executable equity ~30s; event-triggered quote immediate.
- `OPEN_COOL` >60m: lightweight state ~15s; executable equity ~60s; risk subscription remains.
- `ALERT`: bypass periodic clock and evaluate/quote immediately.
- `RUG_TERMINAL`: one emergency SELL attempt at most, then terminal close/writeoff; never re-arm.

Use Solana `accountSubscribe` for exact pool/vault/mint accounts; `logsSubscribe` may be used for a small number of candidate/position pubkeys because `mentions` supports only one pubkey per subscription. Do not subscribe the whole chain.

Runtime owns provider/RPC work. Web/terminal views must be read-only consumers and must never cause a Jupiter/RPC request.

## 8. Exit policy

Keep current dynamic-exit v4 TP/stop/trailing thresholds frozen while the focus cohort grows. The current n is too small to retune.

Keep the fixed 15/60/240 arm only as a causal comparator. Do not delete it.

Next exit research should focus on **state triggers**, not parameter chasing:

- confirmed rug terminal;
- relative reserve/liquidity shock (shadow first);
- route deterioration / executable recovery collapse;
- current hard stop;
- current trailing and staged TP;
- inactivity/max-hold terminal.

The dynamic vs fixed question must be answered on exact same-entry paired cohorts, including losers and written-off positions.

## 9. Entry-threshold learning after the protected baseline exists

Do not immediately run M80/M75/M70 as three active Paper arms.

Order:

1. collect protected M80 forward outcomes under canonical PumpSwap + rug v3+ + exact execution;
2. collect M70 prewatch data only, with no Paper effect;
3. if protected M80 opportunity flow is too sparse or evidence indicates the threshold leaves economic opportunities on the table, preregister **one** M75 Shadow/quote-only challenger;
4. compare with same safety and exit semantics;
5. only after that consider M70.

No gate is changed from retrospective winner inspection.

## 10. Learning and stop/promotion gates

Every current focus position must end in a terminal class:

- economic close;
- max-hold writeoff;
- confirmed-rug emergency close;
- confirmed-rug writeoff;
- other preregistered terminal.

Never let dead/no-route losers remain indefinitely open while winners close, because that creates survivor bias.

Track at minimum:

- net PNL/trade after actual min-output semantics and costs;
- median net PNL;
- win rate (secondary, not sufficient);
- max drawdown;
- lower-tail/CVaR-like loss metric;
- rug/writeoff rate;
- no-route / uneconomic-exit rate;
- time from trigger to executable BUY;
- time from exit trigger to first economic SELL;
- immediate round-trip recovery distribution;
- dynamic-vs-fixed exact-paired PNL delta;
- abstained opportunity outcomes by exact safety reason.

Use >=30 primary terminal tokens, >=15 independent trigger dates, and >=5 positive + >=5 nonpositive outcomes only as a **minimum research-comparison checkpoint**. It does not supersede the stricter capital/expansion/Live-review gate in the authoritative convergence plan: >=100 closed primary positions, >=15 dates, >=20 losses, >=10 dead/no-route terminal cases plus winner-removal/date-block robustness.

Allow earlier **stop/research** decisions when catastrophic tail behavior clearly invalidates the hypothesis, but never early capital promotion from a few winners.

Later model work may use XGBoost/HistGradientBoosting or similar transparent tabular models with strict chronological train/validation and forward holdout. Keep rug-risk model separate from alpha/ranking model. Do not copy non-commercial research code into a profit-oriented system; MemeTrans/MELT is useful research inspiration but its published repository states CC BY-NC licensing.

## 11. Resource allocation during Focus Epoch

### Engineering / review budget

- ~80%: Solana token-only safety, entry microstructure, execution, dynamic exit, forward analysis.
- ~10%: operating reliability and war-room observability.
- ~10%: preserve raw information/other-chain data and blockers; no broad feature expansion.

### Runtime/Agent budget

Main S2 path is Agent-free.

During Focus Epoch:

- preserve deterministic raw news/social/event collectors so future information research is not left-censored;
- freeze new S1/S3 semantic features and Paper promotions;
- suppress/pause low-value Token Context Agent work whose only purpose is onchain metadata/onchain-momentum narrative research or S3 post-entry narrative treatment;
- if keeping any information Agent lane, reserve it for rare exact high-impact original posts only, under a small bounded budget;
- do not increase Agent concurrency.

The exact runtime routing change must be versioned/reversible and must not delete historical admissions or assessments.

## 12. Terminal war-room before broad Web redesign

Implement a read-only terminal command, preferably with no new dependency:

`python -m memetrader warroom --config config.json`

Refresh ~1s from SQLite/local runtime state only. It must not issue provider calls.

Header:

- spearhead version;
- Paper cash;
- executable-equity lower bound;
- realized PNL;
- open positions;
- today entries/exits/writeoffs;
- Jupiter queue/request latency;
- runtime/SQLite/RPC subscription health;
- Live LOCKED.

Per open position:

- token + short CA;
- position age;
- entry cost;
- realized PNL;
- indicative DEX value;
- **latest amount-specific executable recovery** and quote age;
- recovery/cost ratio;
- latest price/liquidity/reserve state;
- custody class and burned/removable LP facts;
- current dynamic state/action/next trigger;
- latest route status;
- risk state: NORMAL / ALERT / RUG_TERMINAL;
- last material risk event.

Use ANSI/plain stdlib first. A durable `position_live_state` operational cache may be mutable and updated at most ~1Hz; material risk/action events stay append-only. Do not append a SQLite row for every slot just to animate a UI.

After the war-room proves the data contract, Web can consume a lightweight `/api/warroom` endpoint at ~2s only while the page is visible; heavy pages stay ~10–15s. Browser polling never drives chain/quote work.

## 13. Expansion order after the Focus Epoch

Do not expand because a decoder is available; expand because the core strategy reaches a decision boundary.

Suggested order:

1. canonical PumpSwap spearhead mature/invalidated;
2. Pump.fun pre-graduation/bonding-curve challenger, only if firm exact-size BUY/SELL and safety semantics can be frozen — it may capture earlier lifecycle upside but is a distinct market regime;
3. Raydium CPMM (RPC custody work already exists) if current data shows meaningful opportunity not covered by PumpSwap;
4. Meteora/Orca after venue custody/lock semantics are complete;
5. BSC/Robinhood after firm route + taker/sellability + complete chain costs;
6. reactivate major Strategy-1/Strategy-3 semantic engineering only when the on-chain focus reaches maturity/ceiling or new information-path evidence materially changes its expected value.

## 14. External research basis

Key sources considered:

- Pump.fun official bonding-curve/PumpSwap documentation: canonical migrated liquidity is protocol-owned; graduation is automatic/irreversible.
- Pump.fun official dynamic fee schedule: current PumpSwap trading fee is market-cap dependent, so a universal fixed 125bps must be labeled fallback rather than execution truth.
- Solana official WebSocket RPC: `accountSubscribe` and `logsSubscribe` provide bounded account/log monitoring; logs `mentions` supports one pubkey per subscription.
- Raydium/Orca/Meteora official documentation: custody and lock semantics differ substantially by venue and pool type; venue-aware decoding is mandatory.
- 2026 `Catching the Rug`: large Solana dataset; early five-minute transaction/microstructure features can predict rug characteristics with chronological evaluation.
- MemeTrans/MELT: context/trading/holding/time-series and bundle-level features improve scam detection/risk modeling; published code/data is non-commercially licensed and is research inspiration only.
- USENIX Security 2026 work on DEX manipulation: wash trading/liquidity inflation can precede extraction, supporting anti-manipulation features rather than raw-volume rules.
- practitioner simple-rule studies: caution that many static Solana momentum/filter combinations do not remain profitable under realistic execution; use only as a warning, not as authoritative proof.

## 15. Codex implementation order

P0.0 — focus freeze and authority cleanup
- S2 Solana token-only becomes sole active optimization/promotion lane.
- S1/S3 semantic expansion + non-Solana/non-PumpSwap expansion go observe-only.
- keep raw data capture and denominators.

P0.1 — spearhead safety/economic entry v1
- canonical PumpSwap only;
- rug v3+ PASS;
- complete Token-2022 dangerous authority coverage including Permanent Delegate semantics;
- cost-derived immediate round-trip recovery floor;
- new forward registration; no backfill.

P0.2 — irreversible rug terminal
- confirmed on-chain pool withdrawal/drain => one emergency SELL attempt then terminal writeoff/no re-arm.
- distinguish no-route/provider-zero from confirmed rug.

P0.3 — mechanical live-state monitor
- bounded pool/vault/mint subscriptions;
- ENTRY_HOT/WARM/COOL cadence;
- runtime material risk state + executable-equity refresh;
- no Agent.

P0.4 — terminal war-room
- read-only 1s terminal view using runtime/SQLite state;
- no provider calls from UI.

P1.0 — bounded prewatch + trajectory features
- M70 observer only; max ~10–20 active candidates;
- compute strict pre-trigger trajectory;
- M80 active entry unchanged.

P1.1 — paired exit evidence
- keep v4 dynamic parameters frozen;
- add rug/reserve-shock state arms separately;
- fixed horizons remain causal control.

P1.2 — threshold challenger only after protected sample exists
- M75 Shadow/quote-only first if justified;
- M70 later;
- no concurrent multi-threshold Paper tuning.

P2 — model/venue/chain expansion only after maturity or falsification.

## 16. Acceptance for this focus decision

The focus transition is correctly implemented only when:

1. current product Strategy 3 authority stays restored; no fourth confirm-before-entry account can execute;
2. S2 is the only active strategy development/promotion lane;
3. new active Paper entries are Solana canonical PumpSwap with current rug + exact-size economic PASS;
4. confirmed pool withdrawal is irreversible for that position/version;
5. main S2 safety/exit path has no Agent dependency;
6. current M80 and dynamic TP/stop thresholds are not relaxed/retuned from the existing small sample;
7. raw information collection remains available for future research without consuming the main engineering budget;
8. war-room is truthful/read-only and Live remains locked;
9. all future policy changes are versioned, activation-fenced and no-backfill.
