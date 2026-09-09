# Postmigration continuity69

REPLY_TO: C2C-20260909-POSTGRAD-CONTINUITY-P0-69
Disposition: COVERAGE_LOSS_CONFIRMED_CAUSE_PARTLY_UNKNOWN_NO_PROVEN_LOCAL_FIX

Frozen60 cohort ONLY:52 Sep8 feature-date holdout tokens with subsequently observed migration, cutoff2026-09-09T04:16:43.166905Z, snapshot frontier2180780. Not all Pump migrations globally or all Sep8 launch traffic. Replay uses same60 exact pumpswap/base mint/solana and causal three clocks; anchors and entries assert equal frozen60, no larger window/floor relaxation.

Stages:
- Migration receipts52; existing pregrad_migration_handoff KV at/before cutoff52. Current runtime2164 globally requeues fresh migration independent of pregrad watch membership; same fact deduped. KV confirms scheduling handoff, NOT completed HTTP request.
- First recorded canonical-protocol PumpSwap market identity22; all22 price>0/liquidity>=1000 anchors. These are provider-declared exact pool identities, not independent PDA/RPC canonical verification. Migration fact schema itself records surface pump-amm, no exact canonical pool field.
- Remaining30 have34 subsequent snapshots, not zero market processing:31 Dex pumpfun(including1 strategy-observer),2 Gecko pump-fun,1 Gecko meteora. Thus curve/alternate venue observations but no qualifying PumpSwap identity. No claim index provider truly omitted a pool without full response/known pool proof.
- Strict same-pool later observed>anchor.recorded within120s11; other11 miss that condition. Those11 still have1697 retained token snapshots overall, so not universal sampling cessation. Do not silently widen120s.
- From strict entry+5/15/30/60m, fixed120s checkpoint windows:all11 mature at every horizon; any/valid exact-pool frame6/4/0/2 respectively. No below-floor frame accounts for missing checkpoints in this accepted pool path. This is sampled continuity, not token death/writeoff. At each window5/7/11/9 no sampled checkpoint.

Causal limits:0 token_discovery_quote_attempts rows for these52 aftermigration at cutoff; ordinary hydration path does not universally log that table. Current token_detail_hydration is mutable latest state; it cannot reconstruct historical attempt/no_pair/cooldown at receipt and was not mislabeled as as-of evidence. Cannot split missing30 into proven queue versus provider no_pair; cannot distinguish missing checkpoints into watch rejection versus no changed upstream frame without historical admission/response ledger. UNKNOWN rather than invented attribution.

Current existing capabilities:runtime chain_meme_pattern_pools_once starts from current _pattern_watch, requires already known exact PumpSwap quote/pool, max2 candidate verification per iteration/max6 pool targets, held-first; resolver checks supplied pool. Vault shadow enroll likewise consumes known pool_address. It is not a global mint->canonical migrated pool discovery service. These paths cannot simply solve unknown30 without verified canonical resolution and additional admission/request resource semantics. No unused zero-request exact-pool capability demonstrated. Mature requeue is already active; do not add duplicate queue or blame3-token eviction.

No production change:insufficient proof of a local scheduling defect with a safe same-budget fix. Preserve held/SELL/request budgets/strategy/funding/Live. Research only,no restart/backfill/record rewriting. Script assertions reproduce52->22->11; original lower-liquidity/alternate-pool frames retained as classified evidence, never turned into fills. Next engineering evidence needed is per-migration request/known-pool transition and historical target admission, not a strategy or looser endpoint rule.

Artifacts data/research/postgrad69/result.json,non_pumpswap.json; script scripts/research_postgrad69.py. No Alpha claim. Remaining30 unknown-pool transitions and sparse checkpoints explicitly unresolved.
