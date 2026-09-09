# Safety minimum evidence91

REPLY_TO: C2C-20260909-SAFETY-EVIDENCE-MINIMUM-91

Verified actual cohort94627 BSC e479...7777 authorization10:08:58.090617Z:
GoPlus presence alone, all13 risk/tax fields UNKNOWN, no Honeypot source. This was
a real authorization defect. d71ddf8 replaces provider-presence with >=1 usable
chain-appropriate fact, without requiring every field. False explicit EVM risk
flags or finite nonnegative tax<=existing12% count; empty/irrelevant/NaN/negative/
boolean tax does not. Solana uses resolved dangerous-control=false or rugged=false.
Hard reasons still override all positive facts. RH supported exact provider surface
remains explicitly UNKNOWN, not a contract audit. Per-assessment usable_facts is
now auditable. Empty reports WAIT/UNKNOWN and retry on existing45s local cache TTL
within original expiry; external source TTL and request budgets unchanged.

29 narrow tests PASS, including empty/irrelevant report cannot authorize, partial
usable fact can allow UNKNOWN, and retry does not occur before existing TTL.
Deployed10:28:57Z via existing launcher; immutable seven-table digest unchanged.
No dynamic recovery/flat/strategy/funding edits. Paper only, Live locked.

## Natural denominator at10:32:35Z

All since safety90:11 unique BUY cohorts/8tokens,11 audited/0unaudited.
Lifecycle status cohort counts PASS0,UNKNOWN11,REJECT0,WAIT11,HAZARD0.
WAIT and UNKNOWN overlap; these are not mutually exclusive final classes.
Post91 frontier:0 BUY cohorts,0audited/0unaudited; PASS/UNKNOWN/REJECT/WAIT all0.
No new natural safety sample yet. Historical rows lack usable_facts and are not
rewritten; missing that new field does not prove every historical report was empty.
Artifacts system91/frontier.json,safety_denominator.json; reproducible bounded
scripts/report_safety91.py. Later natural results remain necessary.

Runtime short readback: held fetch p95 3.000s vs pre2.004s; apply75.4ms vs97.5ms;
pattern7.268s vs6.700s. This is NOT a latency-improvement claim. No new safety fetch
sample occurred to attribute this unequal-window change to the gate. Flat selection
code is untouched. Existing admission audit still drops; not a complete denominator.

## Rediscovery: handoff vs strategy observation

Agent slice09:12–10:27 contained132episodes:90current hydrated/snapshots,21no_pair,
21pending. Its23 evaluation count meant PATTERN evaluation, not all decision receipts.
Corrected bounded root slice through10:32:136episodes,92first snapshots,44not yet
in that receipt slice. All92 have a generic decision evaluation: wakeup is functioning.
Of these,20first frames fail basic market floor/identity prerequisites;72pass basic
price/floor/pool/create fields.26of72 subsequently have pattern_observation,46do not.
Basic-valid is not full three-clock eligibility. Raw references in
system91/rediscovery_input.json; agent smaller slice in rediscovery.json/.md.

Code chain: hydration calls _dex_batch_quote -> _remember_pattern_quotes before
persisting snapshot and setting decision wakeup. Fixed3/4/3 watch admission is
separate; no_active_matching_entry_policy on generic snapshot is not a dropped
wake. Passive cohort processing selects only its special frozen opportunities;
it does not imply every hydration becomes event/quiet history. The first remaining
coverage gap is basic-valid receipt -> pattern observation, not security -> BUY.
Existing admission audit is discontinuous, so do not assert a specific incumbent
caused each missing historical case. No proven missing handoff warrants production
change in this slice; no capacity/gate relaxation.

Among the23 evaluated earlier samples, current revised event reasons were16activity,
4buy-ratio,1conditions,1missing L0 sequence,1gap. Quiet reasons were9wait-base,
7noncausal/gap,3conditions,3floor,1lifetime-consumed. The existing event revision
uses replacement L0 logic; do NOT substitute the older capital_entry event contract
as the current explanation. No new event/quiet BUY. Remaining full input/admission
coverage is unresolved, not evidence of successful reawakening or a proven new bug.
