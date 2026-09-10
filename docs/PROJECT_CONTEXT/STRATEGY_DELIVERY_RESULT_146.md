# Delivery146 — implemented, loaded, first natural cycle

ACK/RESULT `C2C-20260911-146-EXACT-DELIVERY-FIXES`. Sole production writer remains root Codex. The complete A–G corrections in `DELIVERY146_CONCRETE_CORRECTIONS.md` were folded into the existing learner/runtime/UI. Agent work stays deferred. No case rescan, new market request, forced trade, history replay, reset or Live enablement.

Core **c079df4** loaded **2026-09-10T19:04:54.659988Z**, Paper PID **34616**, all **13/13** source hashes match. Static UI **40ad14e** is served exactly from current source without another Paper restart. Existing launcher `scripts/start_system.ps1` invoked `run_paper.ps1` and reused its cold account-read retry. The deployment stopped only the freshly verified Paper supervisor/children and 8790 Web tree. A null descendant entry interrupted the shell before launch; the existing launcher was then invoked immediately and verified READY. No crash cause is inferred from this intentional deployment.

| Requirement | Implemented and tested | Loaded / natural boundary |
|---|---|---|
| A | Publishable modes limited to actual four source modes and current available contracts. NO_SIGNAL/unknown modes remain CONTROL_ONLY statistics; cannot occupy release slots. Real train→choose regression. | v5 loaded. No natural model release; no fixture labels inserted. |
| B | New economic contract `fixed_full_position_costed_endpoint_or_known_floor_minus1/v1`: valid sampled endpoint uses costed return; known causal original-pool floor contributes -1 to this full-position model proxy; missing coverage remains censored. Endpoint conditional mean remains separate. 20×+.05 plus5 floors has model mean-.16 and cannot publish. | New independent `mode-learning146/v5` KV/evidence generation. v4 last update19:04:34 remains preserved, not relabeled or reused as a v5 seal. Actual partial/terminal accounting unchanged. |
| C | Rejected model versions excluded from restore; rollback records group/label/actual frontiers. Full eligibility is reevaluated using only target-group post-rollback decision+anchor+availability, including20 endpoints/10 tokens/2 dates. Other-group UNKNOWN or one fresh target cannot unlock old evidence. | Loaded; no natural model release/rollback yet. Existing positions keep their frozen mode/exit. |
| D | Real Dex `QUOTE_USD_UNKNOWN` plus unavailable price may reach existing outcome callback; other identity/future/stale rejection and full entry rejection stay. Existing episode observes before new signal capture. Collector→Runtime tests cover missing price+known floor, all-missing expiry UNKNOWN, wrong token/pool/future and duplicate callbacks. | Natural callback→strict research anchors advances. No claim that the rare missing-USD/floor case itself naturally occurred in this short cutoff. No extra snapshot writes/requests. |
| E | Actual recipe status now INSUFFICIENT/PAPER_SUPPORTED/REJECT, with real paired count/tokens/dates/costed PnL/delta and known notional-risk evidence.20/10/2days, positive net, nonnegative delta required for PAPER_SUPPORTED; unknown stake cannot qualify. Status count is computed, not constant0. | Two seed slots preserved. Both currently INSUFFICIENT; economic promotions0 is observed state, not missing implementation. C3 extra-batch capacity remains WAIT_PREREQUISITE. |
| F | Precise trajectory145/recipe145 provenance precedes shared v144 engine;146 has its own filter. Numeric strategy144/145 alone never establishes provenance. | Served JS plus real API: #318/#319 each match once and both classify145; Chinese search finds expected strategies. Full current browser typed-search verification not claimed; old open page had a cached script, and app-panel navigation returned queued. |
| G | New independent `trajectory146_learned_mode_selector_v1`,2U/max2 including pending, same-token single position, common safety, strict later original-pool execution, frozen source/mode/model/contract/fixed-priority baseline;5/15/30 mode exits. Existing317v3 and145seeds unchanged; new arm is outside recipe2 slots. | **Registered id320 / displayed family289**, activated19:04:47.900657Z, snapshot2823167, behavior hash41abe3dc316eb2d1. Forward enabled. Actual first BUY and hard-stop SELL observed below; model still BASELINE. |

## Actual first-cycle evidence

Cutoff **19:08:46Z** (API fields have their own generated times): new learner8 independent episodes,7 strict research entries,3 selected decisions; model `fixed_priority/v1`, releases0. No horizon had matured in this initial cutoff. Later natural horizon results must be read separately, not inferred from terminal fills.

New320 source `trajectory144_sparse_peer_hot_fast_v1`: source observed19:05:47.174950Z, selection recorded19:05:47.367786Z, actual common BUY19:05:52.078527Z; cohort95063, source_entry_fill94507, exact pool0x0a231413ac9e820c61bbf959a13ee75986cb4985. BSC token0xf64bc7aacbf1f5c33f0e9be0c0915a54fa2ed595 is evidence only, never an allowlist.320, source313, original317 and seed318 share this fill; this is **one** market opportunity, not four independent samples.

New320 hard-stop SELL19:06:51.545300Z,2U debit, realized **-0.42999353587588907U**. Source/fixed baseline had identical entry terms and terminal PnL; `MATCHED_FIXED_PRIORITY`, N1, delta0. This validates actual producer→safety→later BUY→mechanical exit and matching, **not profitable learning**. Later model/selection changes cannot mutate this position's frozen profile. Natural safety funnel includes WAIT_SECURITY and a separate REJECT; no authorization was injected.

318 now has its first same-fill terminal above, N1/token1/date1, delta0, no extended-hold treatment.319 keeps its earlier N1 terminal **-0.2220843672456576U**, delta0, `trajectory144_price_activity_liquidity_decay`, no extension. Both lack20/10/2-day and positive-net evidence. No natural30→120m extension, automatic recipe append/replacement or positive economic promotion is claimed.

## Resource and integrity readback

| Metric | Before19:02:54Z | After19:08:46Z |
|---|---:|---:|
| Open / held tokens |1 /1 |4 /3 |
| held_fetch p50/p95 (n120) |.997 /3.289s |.989 /2.641s |
| held_apply_exit p95 (n120) |44.45ms |65.10ms |
| passive compute p95 |1.321s (n120) |1.966s (n99) |
| passive queue wait p95 |2.566s |2.885s |
| passive dropped batches/quotes |0 /0 |0 /0 |
| flat task p95 |7.901s (n120) |7.947s (n39) |
| learner flush p95 |50.97ms (n18) |14.97ms (n7) |
| learner observe p95 |.161ms |.097ms |
| Dex PoolTimeout / connect errors |0 /1 cumulative |0 /0 since restart |

The cold-start held p95 briefly reached5.444s (n29), then3.943s (n107). The final short window meets held fetch/no-drop/no-pool-error guard; this is **not a controlled causal speedup or long-run acceptance**. Passive compute/load variance remains visible. No C3 expansion is enabled. Four timings remain exposed: trajectory features, learner observe, entry decision and learner flush. All examined component failure counters0. No traceback in current startup stderr tail. Current held/SELL continues, pending exit quotes0.

DB36,237,578,240→36,255,965,184 bytes (+18,386,944); WAL771,482,392 unchanged. This is total system growth, not attributed to learner alone. No delete/VACUUM/checkpoint/history downsample.

`/health`, `/api/live`, `/api/performance`, `/api/strategy-universe` read successfully; final seconds .132/4.024/.020/.080. API timing is distinct from market latency. Paper=true, Live locked, original funding `chain-meme-trader/funding-20260906-v002-final-1000`. Old319 policy rows,25 registrations,1 funding activation and0 restorations retain exact before/after SHA256. Old317 hash522e63a8eb83ecbd,318f929c430b1ab6f52,319bbaa8c424b8a7fc2 unchanged. Only authorized320 was appended.

Tests: **37** targeted source/learner/collector/Store pipeline cases + **10** recipe manager cases PASS; Node actual UI-function suite PASS, including separate146 denominator/status, precise145/146 filtering and economic missing criteria. New strategy regression includes safety WAIT→later BUY→frozen5m exit; natural first terminal instead hit the unchanged hard stop. Source diff check passed. No fixture is production evidence.

## 145 A–G reconciliation and remaining conditions

- A recovery/launcher: already complete;146 was an intentional, verified reload, not another unexplained-outage diagnosis.
- B truthful UI: loaded exact search/provenance/explanations, legacyv3 and newv5 episode/horizon/funnel separated, BASELINE and candidate INSUFFICIENT visible through real HTTP rendering. Browser visual/typed interaction for latest script not asserted.
- C1/C2 callback and bounded leases: existing implementations retained;146 fixes the genuine missing-USD handoff. C3 conditional extra batch remains disabled until natural budget/coverage evidence supports it.
- D two source-faithful trend seeds: implemented/registered/loaded; now each has N1 same-fill terminal. Trend continuation still WAIT_NATURAL_TREATMENT; no artificial hold or fill.
- E causal learner:317 frozenv3 remains; new146v5 is independently funded and actually trades baseline. Natural learned release/rollback and economic quality remain WAIT_MATURE_FORWARD_EVIDENCE. v4 data preserved historically.
- F restricted recipe generation/append and positive/negative economic status: implemented/loaded; both slots occupied by seeds. AUTO_GENERATED0/PAPER_SUPPORTED0 at cutoff; future candidate supply/capacity/independent terminal evidence required, not code missing.
- G timings, bounded indexed callbacks, execution/safety: source/tests/load pass. Short runtime guard above; broader performance and coverage improvement unproven.

Evidence: `data/research/strategy_delivery146/{before,after_start,accepted,final,summary,natural_first_cycle,ui_readback}.json`. Large readbacks are local research artifacts, not committed database copies. No denied review file was recreated. Current business checkpoint points here; archived145 figures remain historical, not new execution instructions. Agent, unrelated ModeChat work and repeated case audits remain deferred.

Versioned checkpoint **revision24**, digest `fcf1b5ea56a794d1f8bc01540df0a397c6285b85c1139bdee600661b9ce413af`; resume CONSISTENT, sole codex lease epoch0, no execution fences. This is local durable readback, not fresh Chat/Project-memory verification. A first oversized packet was rejected before mutation; completed native milestones were consolidated under143 with report pointers, then one valid semantic revision was written. Attention points to exact146; no ACK-induced revision loop.
