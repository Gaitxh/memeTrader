# Native launch mature coverage — 55

Frozen cutoff: 2026-09-09T03:48:20.294597Z; snapshot frontier 2171308. Post-53 exposure start 2026-09-08T21:17:40Z. Read-only production queries; no backfill, strategy, runtime, funding, or Live mutation.

## Result

COVERAGE_INSUFFICIENT_FOR_NEW_GOLD_DOG_ENTRY. First demonstrated bottleneck is receipt-to-usable-market information, not proof of a stopped strategy loop. No local scheduling mutation is justified by this cohort alone.

The original 116-identity acceptance sample contains 113 first-local identities (108 Four, 5 PonsV2) and 3 already-known Four identities. At this cutoff 6/108 Four first-local and 0/5 Pons first-local have a qualifying frame; the other 3 existing identities still have none. Thus original116 coverage is 6/116, separated from the expanded natural cohort below.

| Horizon | Four valid / matured identities | PonsV2 valid / matured identities |
|---|---:|---:|
| ≤30s | 25/5105 (0.49%) | 1/343 (0.29%) |
| ≤60s | 105/5105 (2.06%) | 28/343 (8.16%) |
| ≤120s | 236/5080 (4.65%) | 70/343 (20.41%) |
| ≤180s | 314/5055 (6.21%) | 102/343 (29.74%) |
| ≤300s | 365/5036 (7.25%) | 115/343 (33.53%) |
| ≤900s | 375/4877 (7.69%) | 122/339 (35.99%) |

Expanded cohort: Four5105, PonsV2343 unique first-local identities. Ever qualifying by cutoff:385/5105 and123/343. Horizon denominators exclude identities not yet old enough; absent futures remain censored/unknown, not dead coins.

## Identity, clocks and meaning

Each qualifying snapshot is a post-receipt stored frame with receipt <= observed <= ingested <= recorded <= cutoff, positive price, liquidity>=1000, nonempty exact provider pair identity. Separate raw audit confirms chain/base-token identity for all inspected frames and every first qualifying frame (zero failures). Pool addresses are not substituted across sources. Provider pair IDs can identify bonding-curve surfaces (Four token address or :4meme suffix); they are NOT proof of a standard on-chain AMM or executable sell. This is usable-information coverage, not actual fillability/Alpha.

Delay is local native receipt to snapshot recorded_at. Four createDate and Pons block timestamp remain source metadata, never the clock starting availability or an authenticated universal launch time. No history was inserted.

## Hydration and censoring

Four: hydrated5061/no_pair44; Pons: hydrated85/no_pair258. Aggregate hydration attempt counters are6794/1187; zero identities have never been attempted. These counters are current mutable row state read during the bounded audit, not a transactionally frozen per-attempt history.

Four first causal snapshot:5061 identities, median11.851s;4887 within30s,4998 within120s. Yet4647 first frames have missing/nonpositive price. Remaining Four without a qualifying frame:4641 have only nonpositive-price failures,35 liquidity-missing failures,44 no snapshot. All385 first qualifying Four frames are GeckoTerminal. All5061 snapshot-bearing Four identities have Dex records;385 show multiple provider pool identities. This demonstrates a major Dex native-surface information gap after prompt hydration. A hydrated flag means a pair was returned, not that price/liquidity passes trading requirements.

Pons:125 identities have causal snapshots, median first receipt delay117.313s,2 within30s/72 within120s. Of123 first valid frames,120 are Gecko and3 Dex.218 lack any snapshot and2 have only below-floor frames. Five identities have multiple pool identities. no_pair does not imply no observations from a different source; all125 snapshot-bearing identities also have evaluation records.

Historical hydration-attempt ledger has no hydration call site: token_discovery_quote_attempts is used by reverse-context/universe paths, not the ordinary hydrate method. Consequently empty attempt lists are NOT zero requests. Exact per-attempt status/latency and historical queue residence cannot be reconstructed from current aggregate hydration rows. This is a measurement limitation.

Entry-evaluation ledger reaches5061 Four and125 Pons identities; this shows processing, not eligible signals or BUY. It cannot establish a causal latency for each valid frame because the first evaluation may concern an earlier unusable frame.

## Scheduling hypotheses checked

Code review: enqueue on conflict retains no_pair next_attempt_at; later PoolGraduated may therefore not wake an existing backed-off row. Also newest-first main hydration ordering can potentially delay older work. But all natural cohort identities were attempted; the seven observed Pons graduation events do not demonstrate the proposed stuck-after-graduation state in the frozen cohort: four first-local graduation identities are hydrated, three are not first-local cohort members. Historical attempt transitions are unavailable. These remain hypotheses, not a proven cause permitting production changes in55.

No retirement or retry-threshold changes made. Held/SELL priority and request budget preserved.

## Descriptive comparison only

A cheap outcome-blind sample selected first20 lexical identities per BSC/RH UTC-hour from non-native first-local exposure records:265 Gecko,15 Dex. Their ever-valid counts160/265 and2/15;900s matured150/254 and2/14. This is NOT age/liquidity-matched and receipt-after-discovery may exclude the discovery frame itself. Therefore it cannot estimate native causal disadvantage; retained for audit only.

## Evidence and next boundary

Artifacts: data/research/native_coverage55/{result,summary,identity_audit,diagnostic,native_event_audit,frozen53_existing_identities}.json; scripts/research_native_coverage55.py and audit_native_coverage55.py. Read-only reproduction and independent raw identity audit completed. No runtime tests/deployment needed because production code unchanged.

Keep new gold-dog entry blocked. Next useful evidence is source-validity/curve-surface availability and timestamped hydration outcome transitions; a graduation wake-up fix requires demonstrating the stuck transition first. Discovery count alone is insufficient.
