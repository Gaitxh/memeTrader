# GXH / memeTrader — Rug Safety, Realtime Exit, Entry Funnel, UI Research

Date: 2026-09-03
Owner: Lead ChatGPT research/review
Execution owner: existing Codex main thread only
Scope: design/review artifact; no code changes; Live remains locked

## 1. Executive conclusion

The highest-impact next work is not a generic threshold relaxation and not more Agent calls. It is a deterministic safety/execution layer around each actual entry and each open position:

1. **Before BUY:** identify the exact venue/pool, who can remove liquidity, how much liquidity is actually non-removable through the intended hold window, mint/Token-2022 privileges, creator/pool-deployer provenance, holder/dev concentration, and a fresh exact-size two-way sellability route.
2. **After BUY:** promote the exact held token/pool into an adaptive high-attention mechanical watch. Subscribe to exact on-chain accounts where possible, use API polling only as a fallback/valuation supplement, and trigger a fresh amount-specific exit quote immediately on adverse state changes. Agent is not in this emergency loop.
3. **Execution truth:** make Jupiter amount-specific minimum output (or an equivalent firm EVM route) the authority for executable BUY/SELL quantities and executable equity. DEX spot price is a trigger/indicative mark, not a fill claim.
4. **Scheduling:** emergency/new exit triggers outrank research/fixed-horizon observations. Dead-pool retries back off instead of consuming the same Jupiter lock indefinitely; a fresh pool-recovery event can re-arm immediate retry.
5. **UI:** reduce the product surface to an operations cockpit, three strategy workspaces, discovery/decision, research lab, and system. Open positions get a live cockpit showing both indicative mark and executable recovery value. Heavy pages remain slow-refresh; only a lightweight open-position endpoint refreshes quickly.
6. **Entry width:** first widen the funnel by removing engineering false negatives (e.g. valid exact-identity + firm route currently cannot enter main Paper), not by weakening safety thresholds. Threshold relaxation should be preregistered, one dimension at a time, in Shadow after rug/execution semantics are complete.

## 2. Current forward evidence that changes priority

Current production-forward v4 evidence already shows the exact failure mode the user described.

- Cohort 2179: same $20 entry. Fixed 15m Strategy-2/3 baseline closed at about **-$0.51209** after modeled costs, while the preregistered dynamic-exit challenger later completed four amount-specific Jupiter take-profit fills and closed at about **+$78.323105** realized PNL. This is one strong forward paired example, not sufficient evidence to retune/promote parameters.
- Cohort 2194: dynamic challenger sold 20% on its first TP quote and realized about **+$1.026781** on that slice; roughly five minutes later observed liquidity reached zero and the fixed 15m amount-specific baseline had `no_route`. This directly supports “capture value before liquidity death” as a real research target.
- Cohort 2185: liquidity reached zero and amount-specific sell quotes returned only roughly $0.0024 against the remaining position; repeated quotes were non-economic under the current $0.40 modeled network-cost fallback.
- v3+v4 LIQUIDITY_EXIT marks with economic semantics: 21 attempted marks, only one ever economic and that one was economic on the first attempt. Among 20 marks whose first attempt failed, there were no later economic recoveries despite roughly 967 subsequent retries. This makes fixed 15-second retry an execution-scheduling bottleneck, not useful learning.
- The dynamic and fixed Jupiter lanes share dispatch/quote locks and the same bounded request epoch. Dynamic exit holds the dispatch lock while awaiting provider response, so dead-pool retry storms consume shared execution capacity.

Do **not** change TP/stop parameters because of 2179. Preserve the current version and collect more natural paired samples.

## 3. What a Solana rug/scam safety layer must actually inspect

### 3.1 Venue-aware pool custody is mandatory

A single “LP locked?” boolean is wrong across venues.

- **Pump.fun bonding curve / graduated PumpSwap:** Pump’s current documentation says graduation atomically migrates the canonical liquidity to PumpSwap and the protocol owns that pool; Pump.fun does not seed/remove that migrated liquidity. Classic creator-controlled LP withdrawal is therefore not the same risk as an arbitrary creator-owned AMM pool. Creator dumping / clustered supply remains a risk.
- **Raydium CPMM / CLMM:** Raydium Burn & Earn permanently locks a position; its API exposes `burnPercent`. Raydium itself states unlocked LP means withdrawal risk and recommends checking liquidity lock, mint authority, and holder concentration. LaunchLab defaults are venue/platform specific and cannot be assumed for third-party launch platforms.
- **Raydium AMM v4:** Burn & Earn is not supported in the same way; LP ownership/removal must be interpreted from the actual pool/LP state.
- **Orca Whirlpool:** liquidity is represented by position NFTs and the position owner can withdraw liquidity. “LP token burned” is not a valid generic safety interpretation.
- **Meteora DAMM v2:** official pool API exposes `permanent_lock_liquidity`, `vested_liquidity`, vaults, TVL and creation metadata.
- Unknown/unrecognized pool programs should not silently pass; they should be `WAIT_POOL_CUSTODY_UNKNOWN` until a decoder/firm route is available.

### 3.2 Exact pre-BUY facts

Freeze a point-in-time `pretrade_rug_safety/v1` record containing at least:

**Token/mint control**
- mint authority / mintability;
- freeze authority / freezable;
- Token-2022 transfer hook address, whether hook program is trusted and non-upgradeable;
- transfer fee current + scheduled changes + fee authority/upgradability;
- default-frozen/default-account-state control;
- permanent delegate;
- pausable / non-transferable / close or balance-mutable authority where applicable;
- any known malicious authority address.

**Pool/custody**
- venue + program ID + pool address + quote/base vaults;
- pool type (bonding curve, CPMM, CLMM, AMM v4, DAMM, Whirlpool, etc.);
- pool creation signature, fee payer/signers, initial pool deployer, initial liquidity provider(s);
- current quote-side reserve/TVL and exact $20 sellability;
- LP/position concentration and effective removable-liquidity share;
- permanently locked share; locker program; unlock/end times; vested liquidity;
- whether the creator/deployer/funder cluster controls withdrawable liquidity;
- for protocol-owned canonical pools, record the protocol custody class rather than pretending the creator owns LP.

**Supply/behavior**
- top holder concentration after excluding known pool/burn/locker/protocol custody accounts;
- developer/creator-associated balance if reliably identifiable;
- creator local launch history and prior mature liquidity-collapse/rug outcomes;
- creator/pool-deployer malicious-address evidence;
- first minutes: liquidity path, tx rate, buys/sells, unique buyers when available, holder change, price path, token balance leaving the pool, and large creator/cluster flows.

### 3.3 Source strategy

Use a layered evidence model rather than trusting one provider:

- Existing GoPlus Solana response already exposes creator + malicious flag, transfer hook + malicious flag, holder locks, DEX pool ID/TVL/type, LP holders/percent/is_locked/locked_detail, mint/freezable/etc. Current code stores the report but does not yet promote the LP/creator/holder fields into a complete decision safety model.
- Jupiter Tokens V2 audit supplies suspicious flag, mint/freeze authority disabled state, top-holder percentage, developer balance/mints, pool/liquidity/activity context. Jupiter Shield can supplement warnings but the Ultra surface is deprecated, so do not make the deprecated endpoint a single critical dependency.
- Raydium/Meteora official APIs/program addresses provide venue-specific lock semantics.
- Solana RPC is the verification layer for pool creation transaction, mint state and exact account changes. Use `getSignaturesForAddress`/`getTransaction` for provenance and WebSocket subscriptions for open-position risk monitoring.
- Existing provider-observed PumpPortal `creator_address` remains a lower-bound identity observation until RPC verified; do not turn it into a hard fraud label by itself.

### 3.4 Hard blockers vs research features

Hard blockers should be structural and falsifiable; examples:

- exact-size current sell route absent / invalid;
- retained dangerous mint/freeze authority when incompatible with meme trading safety;
- non-transferable or unsafe/untrusted transfer hook / permanent delegate / pausable behavior capable of blocking or seizing holder transfers;
- pool custody unknown;
- for non-protocol-owned pools, the ability of a creator-related cluster to remove a material share of tradeable liquidity is unresolved or clearly dangerous;
- imminent unlock inside the intended hold window when that unlock controls material liquidity;
- current pool reserve / route capacity below required notional safety;
- malicious creator/hook/authority evidence from a reliable provider plus exact address match.

Holder concentration, serial-launch history, low organic activity, funding topology and early 5m behavior should initially be **bounded risk features / Shadow strata**, not one opaque “scam score” that silently blocks trades.

## 4. Why post-BUY monitoring must become adaptive and mechanical

Solana research in 2026 increasingly supports behavior-first defense. `SolRugDetector` identifies freeze-authority abuse, liquidity withdrawal and pump-and-dump as representative patterns; a separate 6.4M-token study reports that many rug characteristics occur within the first hour and that first-5-minute trading data can predict risk. This supports high early attention without Agent.

But there is an important physical limit: an atomic/same-slot liquidity withdrawal can make the position unsellable before any observer can react. **Pre-BUY custody/lock analysis is the main defense against atomic LP rugs.** Post-BUY monitoring is valuable for gradual drains, unlocks, authority changes, route deterioration, pump-and-dump and early liquidity collapse.

### Proposed monitoring states

- `ENTRY_HOT` — first 10 minutes: exact pool/mint account subscriptions active; DEX/market mark roughly every 3–5s if provider budget allows; amount-specific executable exit valuation no slower than ~15s and immediately on a hard trigger.
- `OPEN_WARM` — 10–60 minutes: subscriptions stay active; market mark roughly 5–10s; executable sell valuation ~30s, immediate on trigger.
- `OPEN_COOL` — after 60 minutes: subscriptions stay active; market mark ~15s; executable sell valuation ~60s, immediate on trigger.
- `ALERT` — any pool/mint/risk trigger: no Agent; immediately request exact remaining-size SELL quote and evaluate dynamic exit.
- `DEAD_OR_UNECONOMIC` — first failed/uneconomic emergency quote gets short retry; subsequent retries back off (e.g. 15s -> 30s -> 60s -> 120s -> 300s), while a fresh pool/vault/liquidity recovery event re-arms immediate quoting.

All values above are scheduling defaults for a new version, not retroactive mutations of existing v4 evidence.

### Mechanical hard triggers

At minimum:
- quote-side vault/reserve abrupt drop;
- LP/position liquidity decrease attributable to withdraw authority;
- lock expiry/unlock state transition;
- mint/freeze/Token-2022 authority state change;
- current amount-specific sell route disappears or minimum output collapses;
- DEX liquidity crosses emergency floor;
- hard stop / trailing stop / staged TP / max hold;
- material holder/creator dump if locally observable without expensive Agent.

Agent is reserved for post-entry narrative/context research and cannot delay a safety exit.

## 5. Dynamic exit — current state and correction

“Dynamic exit” means an exit decision is driven by evolving position/pool state rather than a fixed 15/60/240-minute clock.

Current token-only v4 challenger already uses deterministic priority roughly: terminal -> liquidity -> hard stop -> trailing -> inactivity -> take profit, with frozen hard stop, trailing activation/drawdown, staged TPs and 240m max hold. It then requests an amount-specific Jupiter SELL for the triggered remaining quantity; the DEX price is a trigger/mark, not a claimed fill.

However there are two major gaps:

1. **Dead-pool retry scheduling** wastes shared Jupiter capacity with no observed late recovery so far; fix in a new scheduling version, not by rewriting v4.
2. **Strategy 1 execution parity:** the main information+token Paper monitor currently triggers dynamic exits mechanically but final SELL accounting still uses DexScreener spot price with configured adverse slippage/fixed cost. It is not amount-specific Jupiter sell truth. Strategy 1 BUY similarly uses DEX spot + modeled slippage when normal liquidity exists. If a Jupiter route-capacity probe is used because DEX liquidity is unknown, the main Paper explicitly returns WAIT with `route_backed_paper_execution_not_implemented` and only records a research challenger.

Therefore Strategy 1 must be brought onto the same exact-size execution semantics before comparing its PNL to Strategy 2/3.

## 6. Buy funnel: what to widen now vs later

### Widen now by removing false engineering blocks

Do **not** weaken rug/sellability gates. Immediate safe funnel widening is:

- exact decision-as-of source-link identity can authorize the existing Jupiter route probe after all existing score/canonical/tx/Pump checks; identity still gives no score/evidence/tiebreak boost;
- if the final route is valid, implement the actual route-backed Paper BUY path instead of hard WAIT;
- use the amount-specific route as liquidity/executable-capacity authority when DEX aggregate liquidity is missing, while all other safety gates remain independent.

Current natural event 7357 demonstrates the issue: exact-source identity reached rank 1 / match 94 / score ~77 / wide canonical margin, yet route probing was blocked by a relation-condition mismatch and final safety also rejected weak buy flow. Fixing the route bridge would not have bypassed the weak-flow rejection.

### Thresholds later, one variable at a time

After pretrade rug safety and firm execution are active, create Shadow-only gate challengers. First candidate: lower **only** the buy-flow ratio by 0.05 from the active baseline for candidates that pass every other gate, with immutable cohort enrollment and 15/60/240 amount-specific outcomes. Do not simultaneously lower candidate score, canonical margin and liquidity requirements; that would make causal attribution impossible.

Promotion requires enough cross-date forward near-miss samples including losses and liquidity deaths, not a single winner.

## 7. UI redesign

Current UI has 11 primary pages and the portfolio is a very large combined rendering of three strategies, fixed/dynamic controls, research evidence and multiple charts. Full portfolio refresh is 15s. The charts are technically dynamic only at page-refresh cadence; they are not a focused live position cockpit.

### New information architecture

1. **实时 / Live Cockpit** (default)
   - mode/health/Live lock;
   - total Paper cash, executable equity and indicative equity;
   - open positions only;
   - urgent alerts;
   - last successful provider timestamps.
2. **三策略 / Strategies**
   - S1 / S2 / S3 tabs;
   - account, closed PNL, open positions, current policy arms;
   - fixed baseline vs dynamic challenger comparison clearly separated.
3. **发现与决策 / Discovery**
   - Event -> Token -> candidate -> safety -> route -> Paper funnel;
   - near-miss reasons and current bottleneck distribution.
4. **研究实验室 / Research Lab**
   - WATCH, creator history, holder shadow, route challengers, counterfactual gates, EVM research; collapsed by default.
5. **系统 / System**
   - sources, agents, audit, settings, wallet/dev validation.

### Open-position cockpit

Each held token should show:
- entry value and remaining raw quantity;
- indicative mark value/PnL;
- **fresh executable exit minimum value/PnL** with age badge and cost-truth level;
- pool liquidity / quote reserve;
- removable-liquidity / lock status / next unlock;
- pool creator/deployer provenance + creator risk state;
- mint/freeze/hook/holder concentration status;
- dynamic-exit state: next TP, hard stop, trailing armed/price, max-hold countdown;
- monitor state (`HOT/WARM/ALERT/COOL`) and last pool event / last Jupiter sellability check.

Charts:
- position chart: indicative mark line + executable recovery-value line + entry cost reference + exit events;
- strategy equity chart: cash + executable open-position recovery value. If a fresh executable quote is missing, do not silently substitute spot; show `incomplete/stale` and optionally a separate indicative line.

### Refresh architecture

Keep expensive full portfolio payload at 15s. Add a small open-position live endpoint and poll it ~2s only while the Live/position page is visible; current frontend already suppresses background refresh when the tab is not visible. Backend data must be produced by the position monitor, not by UI requests triggering provider calls. If a later SSE implementation is clearly simpler, it can replace the 2s poll, but do not redesign the server solely for transport aesthetics.

## 8. Ordered implementation plan

### P0-A — Pretrade rug-safety facts and hard gate
- Add venue-aware `pretrade_rug_safety/v1` append-only evidence + current assessment.
- Reuse GoPlus fields currently stored but not enforced: creator malicious flag, transfer hook, holders, DEX pool/TVL/type, LP holder lock/percent/unlock.
- Add RPC-verified mint/pool creation provenance; exact program/pool/vault identities.
- Add Raydium/Meteora official lock/custody facts where venue matches; Pump protocol-owned custody classification.
- Require complete safety assessment before new eligible Paper BUY. Unknown custody is WAIT, not “safe”.
- No historical backfill into decisions; research enrichment of old rows stays separate.

### P0-B — Adaptive mechanical open-position watch
- New state machine and exact-pool/mint subscriptions where possible.
- Immediate safety-exit quote on hard trigger.
- Prioritize new emergency/TP/stop exits ahead of dead-pool retries/fixed research quotes.
- New dead-pool retry schedule with backoff + event re-arm; old v4 immutable.
- No Agent in critical exit path.

### P0-C — Strategy-1 amount-specific execution parity
- Complete exact-identity -> route-probe bridge.
- Promote a separately registered forward route-backed S1 Paper execution version only after exact-size fresh BUY + immediate SELL preflight + honest cost semantics pass.
- S1 dynamic SELL must use the exact remaining token quantity and fresh Jupiter minimum output; DEX spot remains trigger/indicative mark only.
- Keep Live false.

### P0-D — UI cockpit redesign
- Implement the five-surface navigation incrementally, not a full framework rewrite.
- Add lightweight live-position endpoint; 2s visible-page poll, full portfolio 15s.
- Add executable-equity and pool-rug status to open positions.
- Move research-only panels out of the main strategy operating view.

### P1-A — Entry-gate learning
- Shadow-only one-dimensional buy-flow threshold challenger after P0-A/C.
- Preserve active thresholds in Paper until forward evidence matures.

### P1-B — Early rug behavior model
- Build a research-only first-5-minute feature ledger using liquidity/tx/buy-sell/holder/creator/LP-flow paths.
- Start with transparent rules/stratification, then optionally XGBoost after enough local forward samples. No model may consume future 60/240m outcomes at decision time.

### P1-C — BSC/Robinhood parity
- Apply analogous contract/owner/tax/honeypot/LP-lock/creator checks plus firm amount-specific aggregator route, taker simulation and full gas/L1/L2/allowance costs before Paper.

## 9. Acceptance / stop conditions

P0 is not complete because pages look better or tests pass. Require natural forward evidence that:
- eligible buys have frozen venue/pool custody and rug-safety facts;
- exact-size two-way route exists at entry and final execution uses the same amount semantics;
- open positions enter adaptive mechanical watch without Agent dependency;
- a hard pool/mint trigger produces an immediate priority sellability attempt;
- dead-pool retries no longer monopolize Jupiter capacity;
- Strategy-1 execution PNL is amount-specific, not DEX-spot assumed;
- UI distinguishes executable from indicative equity and updates open positions visibly faster than the heavy dashboard;
- Live remains locked.

## 10. External research basis

Primary/official sources consulted:
- Solana Token Extensions / Permanent Delegate / Transfer Hook / WebSocket RPC / getSignaturesForAddress: https://solana.com/docs/
- GoPlus Solana response fields: https://docs.gopluslabs.io/reference/response-detail-1
- Raydium Trust & Safety, Burn & Earn, token risks, program addresses: https://docs.raydium.io/
- Pump bonding curve / graduation custody: https://pump.fun/docs/bonding-curve
- Meteora DAMM v2 pool API: https://docs.meteora.ag/api-reference/damm-v2/pools/pool
- Orca liquidity position/withdraw documentation: https://docs.orca.so/
- Jupiter Tokens V2 and Shield / Swap V2: https://developers.jup.ag/docs/
- Solidus Labs Solana liquidity-sweep analysis: https://www.soliduslabs.com/reports/solana-rug-pulls-pump-dumps-crypto-compliance
- Chen et al., 2026, SolRugDetector / From Hype to Collapse: arXiv:2603.24625
- Li et al., 2026, Catching the Rug: arXiv:2608.20271

Research notes are recommendations, not retroactive labels and not guarantees against loss.
