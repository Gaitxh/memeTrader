# Recent universe 71 / failure-learning 73

Disposition: complete frozen normalized denominator; economic discrimination remains INSUFFICIENT_EVIDENCE. No new strategy, trading change, restart or source-data write.

## Frozen extraction

Cutoff 2026-09-09T04:55:14.116134Z, snapshot frontier 2194123. Read-only production extraction in 10,000-ID chunks with 10-second per-query progress budget produced 929,595 valid rows; 24,650 selected rows failed identity/clock/pool validation. Elapsed 117.893s; research SQLite 333,565,952 bytes. This supersedes the earlier 250k-row incomplete extraction, not historical source evidence.

Artifacts: `data/research/universe71/normalized_identity.sqlite3`, `normalized.json`, `universe.json`, `summary.json`, `matched_capture.json`. Scripts: `research_universe71_disk.py`, `analyze_universe71_disk.py`, `match_capture_universe71.py`.

Validate base-token/chain identity, Solana case sensitivity, exact pool, positive price, liquidity >=1000 and observed <= ingested <= recorded <= cutoff. Unit is token+pool; original means first locally valid pool in the frozen database, not proven first-ever onchain pool. Other pools remain separate research cohorts, not authenticated migrations.

Entry is first same-pool observation strictly after anchor recording. Entry delay is retained, not assumed short. Future marks must be observed after entry recording; costs are 4% buy / 4% sell proxy. Fixed endpoint tolerance is horizon through horizon+120s. MFE is a sampled lower bound, not executable realized profit. Loss<=-50% and right tail overlap. Sep9 outcomes are deliberately unlabelled; zero counts there mean not evaluated.

## Denominator and observed paths

| UTC date | Original anchors | Strict later entries | 60m sampled paths | 60m endpoints | 60m >=100/400/900% | 6h endpoints | 6h >=100/400/900% |
|---|---:|---:|---:|---:|---|---:|---|
| Sep7 exploration |21773|7513|2816|97|125/35/17|13|133/39/21|
| Sep8 holdout |24748|9380|3542|153|182/62/29|69|232/87/41|
| Sep9 prospective descriptors |5511|2477|not evaluated|not evaluated|not evaluated|not evaluated|not evaluated|

Sep8 15m endpoints=537; 6h sampled paths=3809, observed losses<=-50%=422. First measurable loss stage is anchor→strict-next availability (15368/24748 missing), then next→future path/endpoint. This establishes sampling loss, not its scheduling/provider cause. No terminal absence is converted to writeoff or zero return.

## Frozen feature check and its limits

Sep7 median activity-rate split plus nonnegative anchor→entry price/liquidity change was applied unchanged to Sep8. Support group 2984 entries: 887 observed 60m paths, 69 tails>=100%,145 losses<=-50%. Other measured group6396:2655 paths,113 tails,106 losses. Support enriches observed tails (7.78% vs4.26% among observed paths), but enriches losses much more (16.35% vs3.99%). Coverage differs substantially. Six-hour support:92 tails/248 losses vs140/174 outside support. This does not identify a safe opportunity gate.

These activity fields are stored snapshot aggregates; raw provider missing-vs-zero presence has not yet been fully audited. Thus this split is a diagnostic, not accepted missing-aware discrimination. Native state, multi-frame path efficiency and dollar buy/sell imbalance are UNKNOWN rather than fabricated. Entry-delay variation prevents calling this a uniformly short trajectory. Train medians and date/chain/provider strata are persisted; no threshold grid was run.

## System capture and controls

365 original pools have sampled 6h >=100% across Sep7/8;236 have actual same-pool BUY within entry+6h,223 have an arm BUY before the sampled peak. Historical arms are listed per token; this is not a claim that currently active strategies captured all these opportunities, nor that buys were profitable. The balance129 has no matching BUY in that window;142 has none before observed peak.

Outcome-blind control ranking fixes same date/chain/provider/known launch provenance/quote/age band and liquidity0.5x–2x, then age/liquidity/time distance.342 cases have at least one control, but only37 have fully known launchpad+quote+age identity.988 reused control rows include97 observed tails,152 losses,463 missing paths and only8 known6h endpoints. Reuse is explicit and not independent sample size. UNKNOWN-matched strata cannot support launchpad-specific inference. Multiple provenance labels are AMBIGUOUS, never arbitrarily assigned.

Top1/top3 tail-count removal is descriptive only, not an economic robustness test. Endpoint coverage and incomplete native/quote attribution prevent a trustworthy costed strategy comparison. No stable, adequately covered mechanism passes registration gates. The three73 candidates remain hypotheses; no accounts registered.

## Next evidence boundary

Complete raw activity-presence and multi-frame feature coverage before any discrimination claim; obtain validated native quote-asset/state semantics described in NATIVE_CURVE_FEASIBILITY_73.md. Prospective regime state72 must accumulate outcome-independent history before it can gate trades. Do not solve missing endpoints by relaxing floors, switching pools, or survivor-only selection.
