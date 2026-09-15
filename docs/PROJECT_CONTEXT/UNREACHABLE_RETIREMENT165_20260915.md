# Unreachable Contract Retirement 165

## Diagnosis

Four old alpha149 wide-observation arms remained entry-enabled for about 64 hours despite having
zero positions. Three produced no entry decision; `alpha149_broad_goldendog_band_v1` produced one
admitted decision but no position. Earlier forward diagnostics established two immutable contract
faults: they were registered against the main alpha149 trajectory namespace before the corrected
wide namespace existed, and the original distinct 30-second trajectory gate cannot be satisfied by
the wide observation cadence. The broad-band and broad-flow predicates also do not occur on the
young/coarse wide surface. These are structurally unreachable contracts, not merely rare signals.

The corrected append-only replacements `alpha149_wide_decorr_young_v1` and
`alpha149_wide_goldendog_band_v1` remain available. The two predicates with no valid wide-surface
form receive no invented replacement.

## Action

`unreachable_arms_r165.json` names only the four obsolete IDs. The existing account lifecycle
overlay loads them as `RETIRED_UNREACHABLE_CONTRACT` and sets `entry_paused` at read time. It does
not update immutable policy rows, erase decisions, change account balances, or interfere with SELL
processing. All four have zero open positions at activation.

The new authority source is separate from account depletion and paired-test domination so the UI
and future governance can preserve the causal reason. Removing an ID from the file and restarting
reverses only its entry pause.

## Validation

The targeted retirement suite covers state, replacement provenance, source isolation, missing-file
behavior, idempotency and continued use of the existing overlay. Twelve tests pass. Production
acceptance requires the runtime overlay to contain all four IDs and no post-activation decisions,
BUY intents or positions for them while the Paper funding period and Live lock remain unchanged.
