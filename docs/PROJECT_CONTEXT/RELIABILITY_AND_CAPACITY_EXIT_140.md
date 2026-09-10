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

## First actual loaded result

48d338a loaded through the existing retained Paper supervisor at2026-09-10T10:05:15.221949Z (PID41164). First natural partial receipt2 at10:05:19.008743Z used curve slot445856925 and current exact-message fee slot445856929/5000lamports. It sold273,320,210,121 raw, received0.73279796475429U net, allocated0.8139165525004656U cost, and realized−0.08111858774617553U. Remaining1,284,729,855,258 raw stays OPEN/UNKNOWN. All7,643,704 observed real quote lamports were consumed in the conservative Paper capacity budget; later identical states produced no additional SELL. This is a real Paper ledger result, not positive Alpha or full liquidity recovery.

The test reviewer caught an important pre-load flaw in the first draft: real-reserve debits alone would retain pre-sale virtual pricing. The deployed version also carries prior raw-token/gross-quote deltas into virtual-reserve pricing. Tests prove later model recovery is below the no-impact quote. The separate public input bundle remains intact.

10:07 readback: registration,152 policy additions and both funding tables have exactly equal counts/hashes before/after. Held-fetch p95=2.588s versus2.479s before (+.109s/+4.4%, inside the guard); held apply=.0389s versus.0501s; passive wait2.139s/drops0; HTTP pool/connect failures0. Native held22 samples p95=2.980s. Flat selector12 samples showed p95=25.42s/p50=.365s after restart; source review identifies its one-time full projection rebuild. Do not compare that cold-start window as steady performance or claim all latency is repaired. No speculative selector rewrite from aggregate timing alone.

Final small completion: classify exhausted capacity as `LOCAL_NO_DIRECT_CAPACITY` rather than a math fault, and add **future** native admissions/BUY/partial/terminal receipts to the existing bounded cohort funnel. Old cohort94747 is deliberately not retro-enrolled after restart. Closest tests cover fee-missing, no duplicate capacity, actual partial amounts and native unique-cohort accounting; no new audit ledger or provider requests.

## Final actual boundary

Core48d338a is running and naturally accepted. Follow-up763ccce is implemented/tested/pushed but **NOT LOADED**: automatic process review rejected the combined exact-PID Paper reload/Web reload command before it executed, with only `blocked by policy` as its reason. No workaround attempted. PID41164 remained running; web remains its previous version. The partial-exit rule text is source-complete but Web was not refreshed to it. Existing page/API still work.

Fresh10:12:35Z read (`final_running.json`), seven minutes after core load: held fetch p95=2.106s/failures0; held apply=.0268s; passive wait2.165s/drops0; HTTP generation1/connect errors0/pool timeouts0. Flat selection71 samples p95=.803s/p50=.387s, supporting a cold-bootstrap explanation for the earlier25s tail; no selector implementation change or speculative cache introduced. Workload differs, so no causal global speedup percentage is claimed. Native remaining raw unchanged after the single partial; current zero remaining capacity correctly prevents repeat settlement, although the loaded diagnostic still says `LOCAL_UNKNOWN_MATH` until763ccce can be loaded.

Actual native API accounting at10:13:07Z: cash995.7333025811446U, rent locked0.35979919255599896U, realized−0.08111858774617553U,1 open/0 terminals, executable and indicative equity **null**, valuation `native_protocol_model_unknown`. Missing future exit liquidity is not made into a mark or profit. New139 Dex arms at10:07:22 had10 terminals, combined−5.907982450224995U; small sample/overlapping tokens, not profitability acceptance or a reason to mechanically retune/pause.

Remaining boundaries are explicit: residual native liquidity/migration naturally unknown; source-only763ccce load blocked by process review; Pons execution provenance DATA_BLOCKED; missing saved6h outcomes and fresh external Chat/model/memory readback are not solved by local code or repeating old probes. Prior139 runnable strategies remain active. No controls or funding were changed in140.
