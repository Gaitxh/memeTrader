# User Requirement Traceability — Profit-First V5

Date: 2026-09-04
Status: `AUTHORITATIVE TRACEABILITY / RESEARCH COMPLETE, IMPLEMENTATION PARTIAL OR PENDING`

## 1. Purpose

Map the user’s latest explicit requirements to current production evidence, v5 design decisions, implementation tranche and honest status. A design document is not marked implemented. Historical v4/S1/S2/S3 evidence is preserved and not relabeled as v5.

| User requirement | Current evidence/capability | V5 decision | Main artifact | Implementation status | Acceptance evidence required |
|---|---|---|---|---|---|
| Final goal is profit, not more pages/reports | Current r6 has real discovery, quotes, Paper positions and exact exit evidence, but no proven stable strategy | Optimize executable net PNL, tail, capital time and capacity; all UI/research serves this | `CHATGPT_PROFIT_FIRST_AUTONOMOUS_MEME_TRADING_RESEARCH_2026-09-04.md` | Research complete; strategy unproven | Forward terminal outcomes, costs, drawdown/tail, remove-best/date/cluster robustness |
| Each Stage must be a real strategy | V4 `chain_meme_trader_policies()` is cumulative historical stages with different entry gates | V5 registers 12 independent complete policies: 3 entry families × 4 exits/treatments | `CHATGPT_V5_STRATEGY_REGISTRY_AND_ACTIVATION_SPEC_2026-09-04.md` | Pending Codex Gates A-B | Immutable 12 definitions/readiness; v4 moved to History; exact paired entries within family |
| Do not mutate/delete existing evidence | V4 registrations/rows and open positions exist | Append-only v4 entry-stop frontier; old positions keep old exits; no backfill | same; `CHATGPT_V5_AUTHORITY_AND_SUPERSESSION_MAP_2026-09-04.md` | Pending | Atomic v5 registration + v4 frontier; row/history unchanged; old exits continue |
| Why were there zero/too few trades? | Earlier pipeline faults were repaired; v4 now has natural entries, but cumulative strict gates still suppress/divide coverage | Diagnose discovery→frame→preflight→selection→fill; broaden through Launch Recall/risk buckets, not one global threshold | `V4_CURRENT_ECONOMIC_AND_FUNNEL_AUDIT_2026-09-04.md`; `CHATGPT_V5_DISCOVERY_FAST_LANE_AND_LATENCY_SPEC_2026-09-04.md` | Diagnostic artifacts created; implementation pending | Per-stage attrition/latency; broader bucket candidate/fill counts; capacity/no-selection reasons |
| Buy logic should be wider | Current v4 common momentum/liquidity base gate and later safety gates are nested | Launch Recall includes bounded low/adjacent/high-risk executable Paper buckets; exact mint/BUY/SELL/transfer/dead truth remain hard | `CHATGPT_V5_INITIAL_POLICY_PRIORS_2026-09-04.md`; `CHATGPT_V5_EXPLORATION_PROPENSITY_AND_MODEL_LEARNING_SPEC_2026-09-04.md` | Pending Gate D | Pre-registered buckets/propensities; all-cases PNL/tail/cost; no capacity starvation |
| Risky/rug-prone tokens may profit if exited early | Existing held-account terminal handles confirmed pool failure; current exit rules are coarse | Separate atomic rug, gradual liquidity decay, demand exhaustion, impossible transfer and provider failure; test Fast Escape | `CHATGPT_EXECUTION_ECONOMICS_AND_RUG_ESCAPE_SPEC_2026-09-04.md` | Core terminal exists in v4; Fast Escape pending | All risky cohorts including atomic/no-warning/writeoff; Fast vs Balanced exact paired outcomes |
| Price stops moving after pool removal | Dex/provider flat price can also mean stale source or quiet market | `DATA_STALE`, `MARKET_STALLED`, `PRICE_FLAT_WARNING` can arm exit; only exact account + economic failure confirms dead/writeoff | `CHATGPT_PUMPSWAP_FLOW_AND_EXIT_FEATURE_SPEC_2026-09-04.md`; adversarial review | Pending v5 risk mapping; exact terminal exists v4 | Natural stale/quiet/dead cases correctly separated; flat warning alone cannot write off |
| Determine whether it can really be sold | Existing amount-specific Jupiter BUY and acquired-quantity SELL preflight plus remaining-position quote | Preserve as common execution truth; no route becomes research/no-fill unless existing position terminal policy applies | `CHATGPT_PAPER_LIVE_EXECUTION_KERNEL_SPEC_2026-09-04.md` | Reusable v4 capability; generic kernel pending | Exact amount/time plan/attempt/result; no DEX mark fill; partial exact amount; failures retained |
| Pool/vault/LP facts are preferable | Existing PumpSwap holding-surface, mint and held-account monitoring | Reuse exact facts; distinguish route truth; opaque surface allowed only bounded Paper, safety unknown/Live false | surface correction C2Cs; adversarial review | Existing canonical monitoring; broader tier pending | Exact/opaque/invalid states; no borrowed watcher; route/surface lineage and UI truth |
| Buy wide, sell very cautiously/quickly | Current 15s provider marks and fixed rules are too coarse for some dynamics | Event-driven position state and exit-first scheduler; full-position recovery, flow reversal, account alerts | `CHATGPT_PUMPSWAP_FLOW_AND_EXIT_FEATURE_SPEC_2026-09-04.md`; `CHATGPT_V5_PORTFOLIO_SELECTION_SIZING_AND_CAPACITY_SPEC_2026-09-04.md` | Exact critical lane exists; unified v5 pending | Feature→intent→quote→terminal latency; exits preempt entries; fair no-route retries |
| Some traders exit near local tops | Current rules use fixed DEX-price thresholds/trailing | PeakGuard uses current-only executable-recovery/flow/breadth/intensity/route divergence; exact ATH never an input | `CHATGPT_V5_QUANTITATIVE_ENTRY_EXIT_MODEL_ROADMAP_2026-09-04.md` | Advisory feature design only | Strict-as-of MarketFrames, quote-cadence controls, paired Peak vs Balanced terminal PNL/tail |
| Partial exits/principal recovery | Current v4 has fixed fractions based on raw return | Exact partial amount quote solves principal recovery; no proportional fictitious fill | initial priors/economics/kernel specs | Pending Gate D/E | Exact raw tranche plan/result, remaining cost/amount, no double counting |
| Post-buy Agent investigation | Old Strategy 3/post-entry research infrastructure exists but active high-cost general Agents paused | One shared case per token/cohort; deterministic Tier 0 + max two semantic roles; advisory then affecting treatment | `CHATGPT_POSTBUY_MULTI_AGENT_RESEARCH_SPEC_2026-09-04.md` | Pending Gate I | Shared case/no 12× calls; latency/coverage; hard exit override; exact Balanced pair; ITT missing/errors |
| Multiple Agents from different angles | Existing concurrency limit 2 | Two non-overlapping roles: identity/narrative/diffusion and adversarial/manipulation; chain facts remain deterministic | same | Pending | Structured result/evidence roles; no secret/order access; no duplicated source research |
| Agents should be fast | Existing general Agent path has high latency/cost and low yield | Position-linked priority, local evidence package first, hard deadline, cancel optional work after close | same | Pending | Fill-to-case/result latency, fraction before close, token/call cost, source-fact reuse |
| Agent positive finding should increase confidence/holding | Current product S3 keeps treatment off | Positive evidence may only extend bounded soft runner after available; negative may accelerate soft exit; hard rules override | same | Advisory first | New treatment version/frontier; exact paired economic improvement and tail safety |
| Continuous learning/optimization | Many append-only research ledgers already exist; risk of fragmented experiments | Baseline→Shadow challenger→Paper challenger→maturity review→new version; no per-trade self-editing | `CHATGPT_V5_CAUSAL_LEARNING_AND_PROMOTION_SPEC_2026-09-04.md` | Design complete | Propensity/ITT/right-censor/cluster/date metrics; promotion creates new immutable version |
| Discover new features during forward operation | Current snapshots/held events exist but high-frequency transaction flow incomplete | Versioned MarketFrame with 1/3/5/15/60s flow/breadth/intensity/recovery/account/source-quality components | `CHATGPT_PUMPSWAP_FLOW_AND_EXIT_FEATURE_SPEC_2026-09-04.md` | Pending Gate F | Official decoder fixtures + natural events; late/gap semantics; no duplicate work |
| Improve system speed continuously | Fresh-token hydration queue was previously a proven bottleneck; current exit/quote clients exist | On-chain discovery fast lane; background enrichment separated; persistent clients/batching/shared scheduler | `CHATGPT_V5_DISCOVERY_FAST_LANE_AND_LATENCY_SPEC_2026-09-04.md` | Partially available; v5 integration pending | Stage latency p50/p95, oldest queue, discovery burst with exit SLO preserved |
| Reduce duplicate operations | Existing source-fact reuse and quote grouping are partial | One MarketFrame/subscription/execution observation/post-buy case per exact contract; N local decisions | Master DAG; adversarial review | Pending generic v5 implementation | Provider calls independent of strategy count; exact sharing/different-contract rejection tests |
| Optimize storage | Current single SQLite/WAL, large growing tables, materialized account snapshots | Hot ring buffers; decision/state/checkpoint persistence; optional cold archive only if measured | `CHATGPT_V5_STORAGE_LATENCY_AND_RUNTIME_ARCHITECTURE_SPEC_2026-09-04.md` | Design complete | DB write/query/WAL metrics; no network wait in transaction; reconstructable projections |
| Paper and Live should be one flow | Current Live locked and Paper paths are fragmented/direct trade writes | Shared Decision→Allocation→Observation/Plan→Attempt→Fill→PositionEvent; Paper adapter now, future Live signer/send/reconcile | `CHATGPT_PAPER_LIVE_EXECUTION_KERNEL_SPEC_2026-09-04.md` | Gates A-C pending | Attempt-before-side-effect, idempotency/rebuild, conservative/central separation, Live false/no signer |
| Real trading interface must exist eventually | Devnet/old wallet pieces exist; no reviewed Mainnet broker | Define isolated signer, build/simulate/send/confirm/reconcile as later release; no current implementation | same | Deliberately not implemented | Separate security review, small capital, reconciled balance delta, explicit authorization |
| Strictly no future data/function | Current project has immutable registrations and strict-forward rules; historical defects were corrected | Every feature/event/result has available-at; late data creates future frame only; no old winner backfill | all v5 specs; historical reconciliation | Contract active | Tests for late/out-of-order, activation frontiers, chronological splits, sealed test |
| Reawakening old Meme tokens | Current idea preserved but not implemented as a genuine strategy | Independent entry family with pre-trigger observed dormant baseline, data-gap qualification and episode/reset rules | `CHATGPT_REAWAKENING_STRATEGY_SPEC_2026-09-04.md` | Baseline-building design; pending Gate H | Natural valid baselines, gap≠dormant, first crossing, no duplicate episode/dead reentry |
| BSC simulated trading | Existing EVM route/math/0x research only, not complete Paper | Reuse generic kernel; BSC firm quote/build/simulation, tax/blacklist/allowance/gas/MEV semantics | `CHATGPT_BSC_ROBINHOOD_EXECUTION_ADAPTER_SPEC_2026-09-04.md` | P3 after Solana kernel | Exact BUY/acquired SELL, simulation/cost terminals, forward Paper registration |
| Robinhood Chain simulated trading | Existing discovery/registry/0x research; RWA contamination known | Exact official Stock Token/RWA address exclusion; Arbitrum L2/ETH costs; separate adapter/version | same | P3 after BSC/kernel | Registry freshness/address classification, firm route/simulation/L1+L2 costs, forward samples |
| Web must look/operate like a real autonomous trading system | Existing old web and ChainMemeTrader pages contain useful components but v4 presentation misstates strategy independence | Cockpit + strategies/positions/execution/tokens/risk/learning/chains/system/history; real persisted pulses | `CHATGPT_V5_WEB_TRADING_COCKPIT_DATA_CONTRACT_2026-09-04.md` | Truth-label correction in Gates A-B; full cockpit later | No browser provider calls, critical first, unknown≠0, mature Top3/unranked, bounded performance |
| Home shows best few strategies | Current v4 can rank sparse/incomparable arms | Only mature, completely valued v5 policies; max Top 3; otherwise `LEARNING / UNRANKED` | same | Pending | Maturity and exact comparison set; remove-best/tail visible |
| Dynamic symbols show system is operating | Existing pulses partly CSS/data-driven | Sequence/time-driven subsystem pulses; quiet/stale/disabled separated | same | Pending | Pulse only on persisted sequence change; collector/process/market state distinguishable |
| Secondary/deep pages and hyperlinks | Existing Token drawers/source links and legacy web useful | Separate operational and research pages with exact lineage/explorer/evidence links | same | Pending incremental | Safe allowlisted links, bounded detail, no secrets/raw payloads |
| Parallel/multi-agent execution where useful | Runtime single writer and Agent concurrency 2 | Parallel deterministic collection/frame/read-only research; serialize writes/quote capacity/version activation; one Codex writer | storage/Agent/Master DAG | Governance active | No overlapping writers; exit priority; no 12× work; bounded Agent calls |
| Do not let extra ideas interrupt execution plan | Project governance says supplementary requests preserve active plan | Master DAG orders Gates A–L; current Codex scope only A–C | `CHATGPT_V5_MASTER_IMPLEMENTATION_DAG_2026-09-04.md` | Active authority | One coherent Gates A-C RESULT before Gate D; no multichain/UI/Agent scope creep |

## 2. Immediate status

### Already present and reusable

- real Solana discovery/hydration/quote infrastructure;
- v4 natural Paper positions;
- holding-surface versus route distinction;
- SPL/Token-2022 checks;
- exact held-account events and confirmed-rug terminal/no-reentry;
- amount-specific current sellability/valuation;
- strict-forward append-only evidence;
- passive information/source-fact infrastructure;
- read-only Web discipline.

### Research/specification completed this cycle

- v5 independent strategy architecture;
- execution/economics/rug classification;
- MarketFrame/PeakGuard/quant model roadmap;
- Reawakening;
- post-buy Agent treatment;
- portfolio/propensity/capacity;
- Paper/Live kernel;
- Web cockpit;
- storage/runtime;
- BSC/Robinhood adapters;
- historical handoff reconciliation;
- adversarial corrections.

### Not yet implemented/claimed

- v4 entry-stop frontier;
- v5 registry/readiness;
- generic execution-observation/virtual-Paper lifecycle;
- any active/executable v5 policy or v5 trade;
- PumpSwap high-frequency MarketFrame;
- PeakGuard affecting exit;
- Agent affecting treatment;
- Reawakening executable Paper;
- v5 cockpit;
- BSC/Robinhood complete Paper;
- Mainnet Live broker/signer/send/reconciliation;
- stable v5 profitability.

## 3. Current implementation request

Codex is asked to implement Gates A-C only through the current C2C group:

- premise verification;
- atomic v4 entry-stop + v5 registry/readiness;
- minimal shared execution observation/virtual Paper lifecycle;
- targeted tests and truthful Web labels;
- no natural executable v5 fill required before Gate D activation;
- v4 exits continue; Live locked.

## 4. Completion rule

This long-term objective is not complete when documents, tests or one profitable trade exist. It remains `ACTIVE / CONTINUOUS` until:

- core paths work naturally across dates and failures;
- enough terminal Paper outcomes exist;
- broad entry and exit variants have honest all-cases economics;
- learning/promotion is operational;
- Web accurately exposes operation/equity/risk;
- multi-chain execution semantics mature where enabled;
- any future Live step receives a separate explicit review/authorization.
