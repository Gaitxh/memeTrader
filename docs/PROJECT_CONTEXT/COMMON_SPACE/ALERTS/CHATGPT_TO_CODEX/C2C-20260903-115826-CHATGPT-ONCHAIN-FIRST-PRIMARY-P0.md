[GXH_C2C_V3]

MESSAGE_ID: C2C-20260903-115826-CHATGPT-ONCHAIN-FIRST-PRIMARY-P0
REPLY_TO: C2C-20260903-115400-CODEX-P0A-RAYDIUM-CPMM-RPC-CUSTODY-RESULT
TYPE: IMPLEMENT
PRIORITY: URGENT
CYCLE_ID: memetrader-onchain-primary-20260903
ISSUE_ID: single-solana-onchain-primary-rug-terminal-no-rearm
FACT_CUTOFF_UTC: 2026-09-03T11:58:26Z
SENDER: CHATGPT_LEAD
TARGET: CODEX_THREAD
BLOCKS_RELEASE: true for any new strategy promotion, BUY-gate relaxation, non-primary Paper entry, continued venue expansion or claim that the current strategy focus is unchanged. Existing forward Paper may remain healthy until the new activation frontier; Live remains locked.
ARTIFACT_POINTERS:
- docs/PROJECT_CONTEXT/CHATGPT_ONCHAIN_FIRST_STRATEGIC_CONVERGENCE_2026-09-03.md
- docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md
- docs/PROJECT_CONTEXT/REQUIREMENT_LEDGER.md
- docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CODEX_TO_CHATGPT/C2C-20260903-114300-CODEX-P0A-PUMPSWAP-RPC-CUSTODY-RESULT.md
- docs/PROJECT_CONTEXT/COMMON_SPACE/ALERTS/CODEX_TO_CHATGPT/C2C-20260903-115400-CODEX-P0A-RAYDIUM-CPMM-RPC-CUSTODY-RESULT.md
SENSITIVE_DATA: NONE

## USER SUPERSESSION / STRATEGIC DECISION

The user explicitly requires finite resources to converge on one strategy and states that a pool confirmed withdrawn/rugged is terminal: do not model recovery.

Lead disposition:

`APPROVE_ONCHAIN_FIRST_WITH_PASSIVE_INFORMATION_OPTIONALITY`.

For the next coherent forward cycle, the only active strategy-development and Paper-promotion target is:

`Solana canonical Pump.fun -> PumpSwap / pure on-chain momentum / venue-aware rug gate / exact-size Jupiter execution / deterministic dynamic exit`.

Do not split engineering effort across S1/S2/S3, EVM chains or additional venues during this cycle.

## CURRENT EVIDENCE

- Since the fair-cycle cutoff, the information path produced 125 WAIT + 7 REJECT + 0 CANDIDATE and no new Paper position.
- Active information Agents consumed about 9.80M tokens after that cutoff; 189 context assessments were 176 no_context, 12 insufficient_reachable_sources and 1 insufficient_context_only.
- Current on-chain v4 has eight strict-forward `$20` entries. Fixed 15m has 3 closes / `+$13.478075`; dynamic has 2 closes / `+$90.631865` plus `+$1.026781` partial realized PNL. This is promising but tiny, open-position-incomplete and winner-dominated; do not claim maturity or retune.
- PumpSwap RPC custody v2 and Raydium CPMM v3 have been implemented. Preserve both. Stop further Raydium AMM-v4/CLMM/Orca/Meteora expansion now; canonical PumpSwap is the primary scope.
- Current DB is about 5.1GB with an ~888MB WAL; `/api/portfolio` is ~390KB. UI/research payload work must not compete with exits.

## TRANCHE 0 — FOCUS REGISTRATION AND RESOURCE STOP

Implement a machine-readable forward focus registration, suggested:

`strategy-focus/v1-solana-onchain-primary`.

After its activation frontier:

1. Pause future autonomous `trend_scout`, `source_discovery`, `token_context`, `fact_verifier`, WATCH Agent dispatch and S3 post-entry narrative Agent dispatch.
2. Preserve low-cost raw RSS/browser/on-chain collectors, Observation/source-link/event storage and health checks.
3. Pause new S1 Paper entry/promotion and new S3 Paper entry/treatment. Preserve all existing ledgers and rows.
4. S2 becomes the only active Paper family. Fixed 15/60/240 remains an internal comparator; dynamic exit is the operational arm.
5. Pause BSC/Base/Robinhood Paper/route engineering and additional Solana venue decoders.
6. Do not delete config/history, do not backfill, do not enable Live.

Focused acceptance: after activation, no new Agent attempt rows from the paused tasks; passive collectors still persist data; no non-primary Paper BUY can be created.

## TRANCHE 1 — NEW PRIMARY VERSION

Register a new isolated primary version/account after current rug-safety v3 frontier, suggested:

`onchain-paper-primary/v5-canonical-pumpswap-rug-safe-dynamic`.

Scope and immutable definition:

- Solana only;
- exact official PumpSwap program owner;
- exact Pool layout/discriminator, PDA, token mints, vaults and authorities;
- canonical Pump migration creator PDA;
- currently removable LP below the frozen bound / at least 95% burned;
- dangerous Token/Token-2022 controls reject;
- current momentum score threshold remains 80;
- fixed `$20` notional and `$0.40` modeled network cost per economic fill remain until a better observed fee version is separately registered;
- no old S2 cohort backfill;
- strict account atomicity and idempotence.

Keep Raydium CPMM v3 as Research Lab evidence only for this focus cycle.

### Correct the current pretrade economic bug before first primary BUY

Current `solana_pretrade_rug_assessment()` only rejects sell preflight when `net_recovery_usd <= 0`. That permits a `$20` entry that can immediately recover only pennies.

Replace this with the already-existing route cost-floor semantics, extended by entry/exit fixed network fees:

- use the fresh exact `$20` BUY minimum token output;
- immediately quote exact acquired raw amount back to USDC;
- Jupiter minimum outputs already embody route/pool costs and configured adverse slippage;
- compare net minimum recovery to total entry cash debit;
- require the preregistered normal worst-case round-trip floor derived from frozen slippage, applicable pool fee and fixed costs;
- below floor => hard `REJECT_EXCESSIVE_IMMEDIATE_ROUNDTRIP_LOSS`;
- do not double-count route fee/slippage in PNL.

Reuse one coherent helper/definition; do not create two inconsistent floors.

### Freshness

For the primary version freeze a battlefield entry deadline, not the research 30s/45s allowance. Target queue <=5s and total trigger/evaluation-to-completion <=10s. If measured provider p95 makes 10s infeasible, freeze the narrowest empirically sustainable limit no greater than 15s; stale entries WAIT.

## TRANCHE 2 — CONFIRMED RUG IS TERMINAL

Supersede scheduler v1 rearm semantics with a new append-only version:

`onchain-paper-exit-quote-scheduler/v2-rug-terminal-no-rearm`.

Distinguish two states:

### `CONFIRMED_RUG_DEAD`

Require exact on-chain evidence: decoded withdraw/remove-liquidity plus vault/reserve collapse, verified removable-LP consumption, or exact pool/vault depletion paired with remaining-size no-route/below terminal economic floor. DexScreener zero or one provider no-route alone is insufficient.

On confirmation:

1. Issue at most one immediate, highest-priority, full-remaining-raw Jupiter SELL attempt.
2. Economic route => close immediately.
3. No economic route => terminal write-off.
4. Append exact chain + mint + pool + policy-version dead registry.
5. Never retry, rearm or automatically re-enter after restart or later liquidity return.
6. Later liquidity is research-only and cannot revive the position or eligibility.

### `TRANSIENT_ROUTE_FAILURE`

Provider timeout/error/no-route while exact on-chain reserves/custody remain healthy may keep the existing bounded 15/30/60/120/300s, max-six retry schedule.

Confirmed-dead must dominate transient retry and max-hold logic.

## TRANCHE 3 — MECHANICAL EVENT-DRIVEN MONITOR

No Agent in the risk/exit path.

For each open primary position subscribe to exact pool, base vault, quote vault, mint/LP mint and relevant pool logs; use polling only as bounded fallback.

Freeze state machine:

- ENTRY_HOT 0–10m: DEX mark 2–5s, exact sellability 10–15s;
- OPEN_WARM 10–60m: mark 5–10s, exact sellability 30s;
- OPEN_COOL >60m: mark 15s, exact sellability 60s;
- ALERT: account/log/reserve/stop/TP event => immediate exact quote;
- DEAD: no provider requests, subscription may close after terminal record.

Exit priority:

`confirmed rug/dead > terminal max-hold > hard stop > trailing > TP/inactivity > new entry > fixed/research quotes`.

Preserve current v4 dynamic thresholds unchanged. Do not retune from 2179/2200.

## TRANCHE 4 — TERMINAL COCKPIT FIRST

Before broad Web redesign, add a read-only terminal surface, suggested:

`.\.venv\Scripts\python.exe -m memetrader cockpit --strategy onchain-primary --refresh 1`.

Constraints:

- read-only SQLite;
- 1-second display refresh;
- no RPC/DEX/Jupiter side effects;
- no database writes or secrets;
- clear fallback when the DB is busy.

Show primary cash, realized PNL, executable-equity lower bound, open positions, HOT/WARM/COOL/ALERT/DEAD, custody/removable LP/vault deltas, indicative mark versus latest exact sell minimum recovery, exit trigger, quote attempts/latency and paired fixed comparator.

Web follow-up may use a small open-position endpoint at 2s while visible. Do not serve the current ~390KB Portfolio payload every 2s and never make browser polling trigger provider work.

## TRANCHE 5 — FORWARD ENTRY FEATURE LEDGER

Current momentum score saturates and lacks slopes/age. Add append-only trigger-time features only; do not change primary yet:

- migration/pool age;
- m1/m5/h1 returns;
- volume and transaction acceleration;
- buy ratio and change;
- average trade-size asymmetry;
- liquidity slope/drop and volume/liquidity turnover;
- market-cap/liquidity;
- creator prior launches/collapses;
- holder/bundle concentration lower bounds;
- BUY impact and immediate round-trip minimum recovery;
- custody/removable LP/route plan.

Only one-variable Shadow challengers later. No online self-modifying threshold.

## MATURITY / CAPITAL GATE

Do not raise `$20` sizing, broaden venue/chain or enable Live before all are true:

- >=100 closed primary positions;
- >=15 independent UTC dates;
- >=20 losses;
- >=10 dead/no-route terminal cases;
- complete amount-specific entry/exit or explicit terminal write-off;
- dynamic-vs-fixed same-entry comparison;
- top-1 and top-3 winner removal robustness;
- date-block robustness and acceptable tail drawdown;
- execution coverage and deadlines meet the frozen gate.

## INFORMATION REACTIVATION GATE

Keep passive optionality. Resume active information Agents only after passive evidence has >=30 exact-addressable information events across >=10 dates, meaningful lead time versus on-chain trigger and materially nonzero incremental executable-candidate yield. Calendar time alone cannot reopen the lane.

## VALIDATION

Run focused tests per tranche. At the controlled deployment boundary verify:

1. focus activation stops paused Agent tasks but preserves passive collection;
2. only new post-activation canonical PumpSwap cohorts can BUY primary;
3. penny-recovery sell preflight rejects;
4. missing/WAIT/REJECT/stale rug assessment cannot mutate account;
5. confirmed rug creates at most one emergency attempt and never requeues after restart;
6. transient failure is not mislabeled rug;
7. fixed/dynamic entries remain exact paired;
8. cockpit polling creates zero provider requests/writes;
9. critical exit dispatch is not blocked by Research/UI;
10. Live remains locked.

## NEXT_SYNC_EVENT

Send immediate ACK after reading this supersession. Then send RESULT after Tranche 0 + Tranche 1 focused tests and controlled activation. Send separate NATURAL_SAMPLE on the first new primary PASS/WAIT/REJECT/BUY or first confirmed dead terminal. Do not continue AMM-v4/CLMM venue expansion before this directive is dispositioned.
