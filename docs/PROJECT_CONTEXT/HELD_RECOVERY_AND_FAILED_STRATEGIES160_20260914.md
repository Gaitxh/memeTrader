# Held-pool recovery, failed strategies and runtime survival — 158–160

## Outcome and current boundary

2026-09-14, China time. User renewed restart authority and requested continuation. Paper only, Live locked, original funding period `chain-meme-trader/funding-20260906-v002-final-1000` unchanged. No reset, replenishment, historical replay or contract replacement.

- **158 applied:** 47 additional loss-depleted active strategy arms have `assessment_status=FAILED`, `state=PAUSED_NEW_ENTRY`. Existing controls, original exits and immutable contracts remain. Current effective universe is 463 arms, 172 entry-enabled, 214 FAILED including earlier assessments. These counts are not independent experimental samples.
- **160 held recovery applied:** all 28 stalled equity positions belonged to one migrated BSC Flap original pool. A new fixed-block official contract proof authenticated its successor. The existing runtime then received a fresh successor quote and naturally produced 28 SELL fills, not writeoffs or deleted positions. Total simulated proceeds 46.84481328U; realized Paper loss −513.15518672U. The other Solana position also exited; the subsequently checked open/unvalued position count was zero. Zero positions is not proof of healthy future exit latency.
- **159/160 runtime deployed:** Paper PID44944 startup receipt `2026-09-13T22:45:41.540424Z`; new manifest matches runtime, Store, collectors and held-Flap helper. On 22:47:14Z discovery, decisions and market-source timestamps advance; heartbeat was about 0.5s at an earlier post-startup API check. API errors remain observable; pregrad-watch still reports upstream timeouts. Do not claim all errors or profitability solved.

## Evidence chain for the 28 held positions

Token `bsc:0x920121777532ec6978eef5cbd939cf657b4a7777`.
Original pool `0x3577e25f1b40c422046ce76068306a843cd81578`; successor `0x1368793e92a6a60010365d91d7e895fd1bfb296d`.

The old exact-pool Dex response had a price but no liquidity. Treating it as dead or borrowing the best alternative pool would have been incorrect. Original entry snapshots authenticate chain, token, pool and `dexId=flapsh`. A public BSC RPC proof queried Flap Portal `getTokenV6(address)` at fixed block `0x741679f`: status DEX=4, successor slot13; both pools have the same token0/token1. Block identity was rechecked and block/local times bounded. The fresh receipt was added through the pre-existing `official-flap-successor/v1` control, not by modifying entry provenance.

Sources: [Flap token state ABI](https://docs.flap.sh/flap/developers/inspect-a-token), [official Portal address](https://docs.flap.sh/flap/developers/deployed-contract-addresses.md), [BNB public RPC endpoints](https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/).

Local immutable proof: `data/research/held_flap160/2026-09-13T223645.592871+0000.json`. Link recorded at22:36:45.592871Z; natural SELL fills at22:36:51.607764Z, trade receipts22:36:51.699763–22:36:51.856325Z, final fill15574/trade40487. Reason `market_mark_max_hold:dex_mark_paper_fill`, 4% sell slippage, zero extra fee. This remains the authorized lightweight Paper model, not evidence of an actual chain execution or exact-size sellability.

Automatic prevention now runs every60s after20s startup delay: only unresolved anomalous open BSC Flap original pools; separate read-only bounded candidate scan; at most one public proof per pass, at least300s between attempts on one pool. Healthy pools, non-Flap pools and already linked pools are skipped. Network work runs off the event loop and outside Store locks. Missing/invalid/RPC-error evidence cannot create a link, a zero price or a fill. No paid service, wallet private key, broad wallet scan or added discovery request.

## Failure assessment 158

Admission requires current effective entry enabled, at least one terminal position and a realized SELL/WRITEOFF, both `initial_cash + settled_cash_flows < 20` and `initial_cash + all realized_trade_PnL < 20`. Partial sells on still-open positions count. NULL/nonfinite monetary evidence fails closed. Credits, funding modifications, voids, contamination/resolutions, corrections and nonzero/ambiguous fee regimes require separate effective replay instead of this shortcut.

Preview selected31. After the above28 natural exits realized additional losses, the atomic recheck selected47; this is an intervening ledger change, not inconsistent sorting. Receipt key:
`chain-meme-depleted-failures158/receipt/v1:chain-meme-trader/funding-20260906-v002-final-1000:2026-09-13T223657.961231Z`.

Only convergence KV and an operation receipt can be written (SQLite authorizer); transaction has a3s progress budget and short lock timeout. Prior control is archived. No history/account balance rewrite. At22:48Z no later BUY to selected arms was present, but there were no later trades at all in that short window, so this alone is not a strong natural gating test; code/control regression is the primary verification.

## SQL and runtime survival

Py-spy observed startup FlatSelector aggregation on a **private reader**, not holding the Store writer lock; do not repeat the disproven shared-lock claim. `get_kv` uses its PK. The synchronous opportunity-regime query used status IN and sorted a broad joined population before LIMIT1000.

An attempted partial index build aborted safely at3s and then20s. It was **not installed**. The longer attempt caused writer contention (22:37:18 `database is locked`); the online-index approach and its temporary helper were discarded. No further larger-timeout build. The final query splits OBSERVED/UNKNOWN branches using the existing due index, applies all original joins before each branch's LIMIT1000, then globally orders at most2000 rows. Time window, eligibility and final output remain unchanged. A2,004-row fixture with ties and20 newer missing-join rows matches the legacy result exactly. Private production read:229 rows in10.337ms, three-second ceiling; no matched old-query timing claimed.

The lock incident also exposed `_periodic` secondary error paths: an action failure can be followed by a failing heartbeat write; timing writes were outside the action guard. Such errors could terminate tasks while `run_forever` waited only for stop. Runtime now retains file diagnostics and retries when health/timing writes fail. A terminated critical discovery/decision/held loop is detected and causes the existing supervisor to restart, rather than leaving an idle live PID. Tests reproduce both exceptions, unexpected normal task termination, and intentional stop; finite research jobs are not mistaken for failed loops. This does not prove every possible stall eliminated.

## Validation and deployment

- 4 depleted-control tests; 12 held-Flap proof/candidate/retry/fairness tests; 4 runtime-survival tests; 1 strengthened SQL equivalence/plan test passed (21 distinct tests). The12 prior pool-resource tests also passed at scoped integration.
- Targeted source compilation and whitespace checks passed. The old regime test expecting40 enrollments conflicts with an earlier max8 batch cap; it was not reported as passing or “fixed” by weakening the assertion.
- First sanctioned restart06:24CST loaded155 into PID46876. Final restart loaded159/160 into PID44944. Web process28544 remains independent. Both restarts used exact PID/parent/command-line and Paper/Live checks plus the existing supervisor, not new duplicate launchers.
- `data/research/held_flap160/acceptance_after_link.json` deliberately retains the **stale** intermediate process evidence. `acceptance_restarted_1.json` is the later new-generation readout. Broad due-count aggregate omitted explicitly to avoid diagnostic I/O; omitted is not zero.
- Source hashes at final startup: runtime `07d65fd7fdfb8e45fe6a70d543b1783988e30d48336b079cc8d4c5acba8bc500`; Store `6caae0dfdd5088df6f1e36d3ff39f891b5da9add14b7bcf63345fd3e45068468`; held recovery `784c1bf8d15b81f09a4c3f4c854f565f9f77eb36e792afcd72537436b141e77a`.

At22:47:14Z and22:51:05Z PID44944 snapshot frontiers advanced433282→433881; trade frontier remained40487, heartbeat0.259s in second sample. No new trades means neither improved conversion nor profit is established. Final fairness correction chooses the least-recently attempted eligible migration candidate; otherwise a permanently failing lexically early token could monopolize repeated attempts. Final restart: PID45576,22:53:47.720685Z, helper hash `a86f7d72d0b7b9879d699c9dcecc91a70e53300a27ba170c514ff5b263f71ea7`; runtime/Store hashes above unchanged, heartbeat0.743s. Source compilation and the new fairness/success-write tests pass. Scoped stage deliberately leaves unrelated dirty UI/config/collaboration and earlier unrelated runtime hunks untouched; it is not a clean full-tree release snapshot.

Rollback: disable `held_flap_recovery.enabled` and restart to stop new proof probes. Retain authentic already-used links/evidence and all natural fills. Revert only159/160 query/guard hunks for code rollback; never restore whole dirty files. Failure control rollback must merge only this receipt's affected arms with prior controls after checking later changes, not overwrite the entire convergence map. No automatic reactivation of failed strategies.

## Remaining priorities

**Post-release natural evidence,22:57:14Z:** commit `639483e` was pushed. PID45576 remains running, heartbeat2.168s. One Robinhood opportunity (`shadow_cohort_id=15648`, token `robinhood:0x2914300226e9739c11bd9a41c374f47a9f3539b7`) naturally opened two20U Paper positions through alpha152 quiet-acceleration control/wide at22:55:34Z (trades40488/40489). This is1 independent opportunity fanned out to2 accounts, not2 independent samples. Both positions are valued from their exact entry pool, latest observation22:57:10.970075Z, liquidity20598.51U, zero current unvalued positions. Artifact `data/research/held_flap160/natural_forward_after_release.json`. This establishes one new natural decision-to-ledger event after the fixes, not attributable conversion improvement or profitability. The earlier “no new trades” paragraphs retain their earlier cutoffs.

1. Verify sustained data/decision progress and actual held latency when natural positions return; no comparison of empty current inventory with the old28-pool incident as a speed improvement.
2. Pregrad upstream watch timeout remains, as do intermittent provider timeouts; prioritize deterministic Dex lanes and bound optional probes. Do not erase error history to claim success.
3. Earlier34-address audit and cash157 are complete; do not repeat them. Continue forward cohort conversion and independent strategy evidence after engineering coverage stabilizes. Do not fabricate profitable entries into hindsight winners.
4. Three-round engineering artifacts already exist under151. Long-window cost-adjusted profitability, autonomous new-migration natural samples and exit-quality comparisons remain unproven, with existing project review151 collecting. No new model-driven automation or live promotion.
