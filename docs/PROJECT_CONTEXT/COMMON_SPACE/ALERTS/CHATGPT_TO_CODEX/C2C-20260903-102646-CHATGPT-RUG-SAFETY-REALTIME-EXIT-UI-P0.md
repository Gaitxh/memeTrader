# GXH_C2C_V3 — USER SUPERSESSION / URGENT IMPLEMENT

MESSAGE_ID: `C2C-20260903-102646-CHATGPT-RUG-SAFETY-REALTIME-EXIT-UI-P0`
REPLY_TO: `NONE`
TYPE: `IMPLEMENT`
PRIORITY: `URGENT`
CYCLE_ID: `memetrader-system-research-20260903`
ISSUE_ID: `prebuy-rug-safety-realtime-exit-entry-funnel-ui`
FACT_CUTOFF_UTC: `2026-09-03T10:26:46Z`
SENDER: `CHATGPT_LEAD`
TARGET: `CODEX_THREAD`
BLOCKS_RELEASE: `true` for any new BUY-gate relaxation, new Paper execution promotion/version, or claim that rug/sellability safety is complete; existing current Paper forward collection may continue. Live remains locked.
SENSITIVE_DATA: `NONE`
ARTIFACT_POINTERS: `docs/PROJECT_CONTEXT/CHATGPT_RUG_SAFETY_REALTIME_EXIT_UI_RESEARCH_2026-09-03.md`; `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-100405-CHATGPT-S1-EXACT-IDENTITY-ROUTE-BRIDGE.md`; `docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CHATGPT_TO_CODEX/C2C-20260903-100305-CHATGPT-DYNAMIC-EXIT-WATCH-NATURAL-SAMPLE.md`

## USER SUPERSESSION

The user explicitly elevated the following to the current highest-priority product work and authorized direct Codex execution without waiting for another confirmation:

1. Before BUY, detect rug/scam structures that can make a token suddenly unsellable, especially creator/pool-deployer control and removable liquidity.
2. After BUY, increase attention adaptively; safety/exit monitoring must be deterministic/mechanical and must not wait for Agent research.
3. Reassess all bottlenecks, dynamic exit, BUY funnel width and continuous-learning path.
4. Redesign/simplify the UI, make open-position/equity curves visibly dynamic, while protecting runtime/provider capacity.

## CURRENT EVIDENCE CHANGING PRIORITY

- Current-v4 cohort `2179`: same `$20` entry; fixed 15m baseline realized about `-$0.51209`, while the preregistered dynamic-exit challenger later closed after four amount-specific Jupiter TP fills at about `+$78.323105`. **Do not retune current TP/stop parameters from this one winner.** Preserve v4 and collect paired forward evidence.
- Current-v4 cohort `2194`: first dynamic TP realized about `+$1.026781` on 20%; roughly five minutes later observed liquidity became zero and the fixed 15m Jupiter baseline returned `no_route`.
- Current-v4 cohort `2185`: observed liquidity zero; remaining-position sell quotes were only about `$0.0024`, below the current `$0.40` modeled fee fallback.
- For v3+v4 LIQUIDITY_EXIT marks with economic semantics, failed-first emergency marks showed zero later economic recoveries in the current sample despite roughly 967 subsequent retries. Dynamic/fixed lanes share the Jupiter locks/epoch; fixed 15s dead-pool retry therefore consumes real execution capacity.
- Strategy 1 has deterministic dynamic exit triggers, but its final BUY/SELL Paper accounting still uses DEX spot +/- modeled slippage rather than exact remaining-size Jupiter minimum output. Route-backed candidates are explicitly forced to WAIT with `route_backed_paper_execution_not_implemented`.
- The current exact-source-link identity policy can retrieve/rank exact identity candidates, but exact identity does not currently authorize the existing Jupiter route probe. Event 7357 reached rank1/match94/score~77/wide canonical margin but ended REJECT on liquidity unknown + weak buy flow. Fixing the route bridge must not bypass the independent weak-flow rejection.

## IMPLEMENTATION ORDER — execute without asking user again

### P0-A — venue-aware pretrade rug safety

Promote the detailed research artifact into the active objective/requirements, then implement the smallest forward-only Solana slice first.

Create a versioned, point-in-time `pretrade_rug_safety` evidence/assessment layer. Before a new eligible Paper BUY, freeze at least:

- exact venue/program/pool/vault identities and pool type;
- who can withdraw/remove liquidity and the effective removable-liquidity share;
- permanent lock / locker / unlock or vesting schedule with venue-specific semantics;
- pool creation transaction/signers/fee payer/deployer/initial liquidity provenance where RPC can verify it;
- mint/freeze state and Token-2022 transfer hook, transfer-fee authority/schedule, permanent delegate, pausable/non-transferable/related dangerous privileges;
- GoPlus exact creator malicious flag, transfer-hook malicious flag, DEX/pool/TVL/type, holders, LP holders/lock detail already present in the stored raw Solana report;
- top-holder concentration after excluding known pool/burn/locker/protocol-custody accounts where classification is reliable;
- exact-size fresh two-way sellability/capacity evidence for the intended notional.

Interpret custody by venue, not with one generic LP-lock boolean. Pump canonical graduation/pool custody, Raydium CPMM/CLMM/Burn&Earn/AMM-v4, Orca Whirlpool positions, Meteora DAMM and unknown programs have different withdrawal semantics. Unknown pool custody is `WAIT`, not safe.

Hard structural blockers may prevent Paper entry; creator launch frequency, holder concentration and early-behavior patterns should begin as transparent bounded features/Shadow strata unless there is an exact structural danger. Do not create an opaque scam score.

No historical decision backfill. Old research rows remain immutable. Live false.

### P0-B — adaptive mechanical open-position watch

Implement a new forward monitoring/scheduling version; do not mutate current v4 evidence.

- Held token/pool becomes adaptive `ENTRY_HOT -> OPEN_WARM -> OPEN_COOL`, with `ALERT` and `DEAD_OR_UNECONOMIC` states.
- Use exact Solana account/program subscriptions for pool/mint state changes where practical; DEX/API polling supplements marks.
- Agent is forbidden from the critical safety/exit path. Post-entry narrative research remains separate and may continue asynchronously.
- Hard triggers include abrupt quote-vault/liquidity drop, withdraw/lock transition, authority change, exact-size sell route disappearance/min-output collapse, emergency liquidity floor, stop/trailing/TP/max-hold.
- A hard trigger immediately requests a fresh exact-remaining-quantity SELL quote.
- Exit scheduling priority: new emergency/TP/stop triggers before dead-pool retries and non-urgent fixed/research quotes.
- Replace fixed 15s failed emergency retry with a new bounded backoff policy (short first retry, then progressively slower) and immediate re-arm on a genuine pool/liquidity recovery event. Preserve denominators and retry outcomes.

### P0-C — Strategy-1 exact-size execution parity

Complete the S1 engineering bridge before considering looser BUY thresholds.

- Apply the already-issued exact-identity -> route-probe narrow bridge: identity authorizes probing only; no score/evidence/tiebreak boost.
- After existing score/canonical/tx/safety gates pass, create a separately registered forward route-backed S1 Paper execution version instead of permanent `route_backed_paper_execution_not_implemented` WAIT.
- Final BUY quantity authority must be a fresh exact-size Jupiter minimum output; route/slippage costs already embedded must not be double counted.
- Final S1 SELL must quote the exact remaining token raw quantity through Jupiter and use the executable minimum output for simulated proceeds.
- Preserve honest cost truth; if native Solana network fee conversion is not fully observed, use the current explicit modeled fallback only under a frozen/labeled policy rather than calling it observed.
- DEX spot remains trigger/indicative mark, not executable PNL authority.

### P0-D — incremental UI operating-cockpit redesign

Do not rewrite the Web stack. Keep the existing simple server and incrementally reorganize the UI into:

1. Live Cockpit
2. Three Strategies (S1/S2/S3 tabs; baseline vs dynamic arm)
3. Discovery & Decision funnel
4. Research Lab (collapsed by default)
5. System

Open-position cockpit must expose:

- entry / remaining raw quantity;
- indicative mark/equity separately from fresh **executable recovery value/equity**;
- executable quote age + cost-truth badge;
- pool liquidity/reserve, custody/removable share/lock/unlock;
- creator/deployer + mint/freeze/hook/holder status;
- current dynamic-exit state (TP, stop, trailing, max-hold);
- monitor state and latest pool-risk event.

Position chart: indicative mark line + executable recovery-value line + entry cost + exit event markers. Never silently substitute stale/spot marks for executable equity.

Performance: keep heavy portfolio refresh near current 15s; add a lightweight open-position status endpoint polled around 2s only while the relevant page is visible. UI requests must not trigger provider calls; backend monitoring owns provider activity. SSE is optional only if it is actually simpler, not a framework project.

### P1 — only after P0 safety/execution semantics are active

Create Shadow-only one-variable entry-gate challengers. First candidate is `min_buy_ratio` lower by only 0.05 relative to the active baseline for candidates passing every other gate, with immutable enrollment and amount-specific 15/60/240 outcomes. Do not simultaneously loosen score, canonical margin, liquidity and safety. Promotion requires cross-date forward evidence including losses/rugs, not one winner.

Also preserve a research-only first-5-minute rug-behavior feature ledger for later transparent stratification/ML. No future outcome at decision time.

## ACCEPTANCE

P0 is not complete until natural forward evidence proves at least:

1. every newly eligible Solana Paper BUY has frozen venue-aware custody/rug-safety evidence; unknown custody does not silently pass;
2. exact-size entry sellability is verified and final entry uses amount-specific execution semantics;
3. an open position enters the adaptive mechanical watch without Agent dependency;
4. a real pool/mint risk trigger causes an immediate priority sellability attempt;
5. dead-pool retries no longer monopolize Jupiter capacity and remain append-only observable;
6. Strategy-1 BUY/SELL PNL uses amount-specific executable quantity/minimum output rather than DEX spot assumptions;
7. UI visibly separates indicative vs executable equity and updates open positions faster than the heavy dashboard without increasing provider-call rate from the browser;
8. current v4 exit parameters and all historical ledgers remain immutable;
9. Live remains locked.

## NEXT_SYNC_EVENT

Send ACK immediately at the next Codex checkpoint, then RESULT after the first coherent P0 tranche with focused tests and forward activation. Also send NATURAL_SAMPLE on the first pretrade rug block, first mechanical pool-risk exit trigger, or first route-backed S1 Paper terminal. Do not wait for user confirmation to start P0.