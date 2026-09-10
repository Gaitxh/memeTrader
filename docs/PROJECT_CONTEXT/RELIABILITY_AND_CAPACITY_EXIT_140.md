# Reliability and native exit completion140

## Scope and current facts

Continues the user's full-delivery139 request. No new strategy, threshold change, funding, replay, or Live authority. Prior completed139 delivery remains in `FULL_DELIVERY_139.md`.

Fresh root API read at2026-09-10T09:53Z: runtime running; Paper=true, Live locked;14 open positions/4 unique held tokens. Held-fetch p95=2.321s, held apply=.0593s, flat selector=.719s, flat task=5.385s, cohort compute=.750s, passive wait=2.142s/drops0. HTTP3 generations/2 connect retirements/153 routine cancellations without rotation/0 pool timeouts. These are bounded current windows, not a speedup claim. The earlier08:51 performance snapshot is historical and must not be presented as current.

Dex engine naturally continued:41,642 distinct frames/381 retained pools by09:53. Startup30m and steady admission cohorts both produced BUYs (10 and7 respectively). This does not support blanket scheduler dormancy. Gecko Robinhood429 is a separate upstream condition; do not increase its budget.

## Concrete exit defect and implementation

Native cohort94747 had a persisted max-hold intent but no settlement because the current public curve could not quote the entire remaining1,558,050,065,379 raw tokens. The scheduler and new curve slots continued advancing. The adapter could only sell all or retain all, even when a smaller executable quantity might exist.

The native-only exit path now computes the largest integer quantity within current observed real quote reserves. It uses the existing coherent Curve+Global+FeeConfig bundle and existing integer sell math. Only an already-persisted exit intent can request this path; completion still requires a strictly later independent state, exact-amount current unsigned message fee, positive net recovery, and current causal USD reference. No extra market request, timer, watch slot, or provider cadence is introduced.

Paper does not change public pool state. Each position therefore persists cumulative gross quote debit and raw tokens sold. Subsequent pricing applies those SELL deltas to both virtual and real reserves on top of the next public state, with **no credit for the hypothetical BUY's liquidity**. Raw public provenance and the derived `paper_pricing_curve` remain separate. This conservative protocol-model convention prevents repeated capacity and repeated pre-sale pricing. It is not a chain transaction or a claim that public reserves already include Paper sales.

Each partial settlement atomically appends immutable native/common SELL receipts, charges the exact quantity's fee, allocates the unallocated cost proportionally, updates remaining raw/proceeds/cumulative realized PnL, and leaves residual position OPEN/valuation UNKNOWN. Entry rent remains a separate locked asset. Only actual zero remainder closes the position. Curve completion still requires authenticated canonical PumpSwap handoff and a later successor quote. Unknown/zero capacity or uneconomic fee remains unsold; no forced writeoff.

## Validation and deployment boundary

Closest native/Pump/explainability tests pass (63 cases). Coverage includes integer capacity boundary and cap+1 failure; coherent single-bundle fee tiers; no change to legacy full-amount collector; exact partial fee message amount; missing fee=no fill; strict-later partial; proportional cash/PNL; restart and unchanged-reserve no-repeat; prior-sale virtual price impact; later reserve recovery/full close; canonical migration; accounting/UI rent semantics. An initial new fixture exposed NOT NULL `close_reason` on partial positions; fixed before load.

Source implemented/tested; deployment and natural acceptance are recorded below after the supported launcher loads the coherent commit. No independent Pons provenance proof was produced: its existing bounded all-launch observer/enrollment is loaded, but external execution authentication/conversion gaps remain DATA_BLOCKED. Old docs saying121A is source-only are historical. No repeated failed external probe or fabricated OBSERVED state.

Evidence: `data/research/reliability140/before_performance.json`, `before_live.json`, `before_load.json`. Registration/policy/funding hashes are frozen in the latter for after-load comparison. Records include historical suspicious Paper returns; no profit erasure or Alpha claim.
