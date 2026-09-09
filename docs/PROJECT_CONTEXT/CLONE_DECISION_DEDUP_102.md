# Clone opportunity ownership — P0 102

REPLY_TO: C2C-20260909-CLONE-DECISION-DEDUP-P0-102

## Confirmed defect

Frozen read-only audit at 2026-09-09T18:26:19Z examined 4,922 position/cohort records with non-empty event_keys[arm], across all definitions/arms. They represented 4,919 definition+arm+decision keys. Two duplicate groups (five positions, three excess enrollments) were found, both clone_liquidity_leader_v1 in funding-20260906-v002-final-1000. This was not an authorized add-on.

The supplied key passive-clone-1c88f954621b23e388827fe9|clone_liquidity_leader_v1 produced cohorts94637/94638/94639, fill IDs94295/94296/94297, three5U BUYs within129ms. The other key passive-clone-4711f10b9f8a5b1792e7b114|clone_liquidity_leader_v1 produced94641/94642. All five eventually floor-wrote-off, recorded PnL -25U. Three excess positions account for -15U; this is contamination attribution, not recovered money.

The important causal gap is between admission and position creation. Existing event dedup checked positions only. During WAIT_SECURITY there was no position, so multiple next frames created separate admitted cohorts. One later cached security result resumed all of them in a loop. The observer's cycle-start bought set did not close this gap. Updating only that memory set would not fix restart/pending races.

## Fix

5662d7a plus27dc2a0 add persistent primary-key ownership `(definition_version, arm_id, decision_key)` before the common Paper entry safety call. One cohort owns the frozen opportunity; subsequent observations cannot allocate another. Same-cohort WAIT_SECURITY resumes through the existing strictly later original-pool frame path. Explicit safety REJECT/expiry consumes the opportunity permanently. Queue-capacity refusal is an explicit terminal capacity skip, not a falsely resumable item without a worker slot. Distinct episodes and arms remain independent; existing paired-group fill checks remain in force.

Older admitted intents are found via immutable cohort/entry-decision evidence, including pending/rejected security attempts. Ownership is imported lazily when needed, without replaying trades. An initially unfavorable SQLite join plan was corrected: CROSS JOIN forces token-filtered cohort lookup before exact decision/cohort lookup. Production EXPLAIN confirms both searches are indexed; the supplied token lookup took1.82ms and resolved owner94637. No bulk history migration or new source requests.

NarrativeHold checks the same ownership before creating a case from a cohort BUY, so an old duplicate cannot generate another research case. Existing distinct opportunity/arm semantics remain; no broad token/time-window dedup merges different events.

## Historical annotation, no refund

Research-only KV annotations identify94638/94639/94642 with duplicate-opportunity-contamination and their retained owners. Existing accounting contamination/void mechanisms were deliberately NOT used because they change effective cash/equity and violate the no-refund requirement. Raw position/trade rows, PnL, account cash and funding are untouched. The annotation adapter reuses engineering_anomaly/research_metrics_eligible to quarantine contaminated arm metrics; historical research distributions exclude annotated duplicates while raw ledger totals remain visible. No historical entry/exit is merged, deleted or reinterpreted as a fill.

API readback: clone arm retains9 terminals, raw realized-20.2977886327U, cash979.7022113673U; engineering_anomaly_position_count3, research_metrics_eligible=false, PF/expectancy quarantined. Unique-opportunity diagnostic only: six retained terminals sum-5.2977886327U; not profit and not a refund. The five affected positions plus their trades retain SHA256 c91e1ab8eeb009110fcc1276b974840b464a44efbf25c447d51a489422f27276 before/after annotation.

## Validation and deployment

44 targeted cohort/security tests passed. After research eligibility/Narrative adapters, 18 targeted tests passed (cohort enrollment, narrative and Web curves). Three enrollment tests then passed after the capacity disposition and query-order refinement. Coverage includes repeated later batches while waiting, persisted pending/claim restart, strictly later security resume, terminal rejection, two independent SQLite connections racing on old duplicate intents, distinct episode/arm scope, capacity skip and unchanged cash/PnL under research annotation. git diff --check passed.

Code pushed and final Paper process loaded27dc2a0 around18:35:37Z; Web reloaded for eligibility display. Health running, Paper only/Live locked, passive drops0, unchanged seven-table funding/registration/activation digest5abffced88f8b8e3228071a123dd8bb79f9d0effca00b1e9a85a5d17194c71a3. Initial post-start held p954.943s/apply39ms; pre held3.331s/apply38ms. Small startup windows are not comparable latency acceptance. No new natural cohort claim yet at bounded readback: regression tests prove the path, natural same-decision acceptance remains pending. No new opportunity is fabricated for a test.

Artifacts: data/research/clone_dedup102/user102_clone_dedup_audit.json, annotation_dryrun/applied/readback.json, legacy_query_plan.json, live_readback.json, universe_readback.json; data/research/admission88/pre102.json/post102.json. Audit helper's suggestion to void was rejected for the financial boundary above; its raw duplicate evidence remains useful.
