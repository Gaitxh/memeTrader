# Codex implementation handoff — memeTrader system research → ordered execution

MESSAGE_ID: `C2C-20260903-MEMETRADER-SYSTEM-RESEARCH-IMPL-001`
TYPE: `IMPLEMENTATION_DIRECTIVE / USER_EXPLICIT`
OWNER: `Codex`
LEAD_RESEARCH: `ChatGPT conversation 6a98135b-e2d4-83e9-bd0c-269e36451542`
FACT_CUTOFF_UTC: `2026-09-02T18:12:27Z`
BLOCKS_LIVE: `true`
NORMAL_PAPER_OPERATION: `continue unless the specific change requires one controlled restart`
FULL_RESEARCH: `docs/PROJECT_CONTEXT/CHATGPT_MEMETRADER_SYSTEM_RESEARCH_2026-09-03.md`

## 0. User intent

The user explicitly asked Lead ChatGPT to perform a comprehensive, deep system-level study covering architecture, simulation logic, News+Token, narrative/heat, creator/dev, buyers/snipers/rat trading, liquidity-pool disappearance, post-buy news monitoring, multi-chain costs, KOL experience posts and OSS references; **after completing the research, synchronize all content to Codex and have Codex execute and advance the project**.

This handoff therefore has implementation authority, subject to current code/SQLite validation and all frozen safety/causal rules.

Do not reply with a second generic architecture review. Read the detailed research, verify the small set of current facts that matter, update the authoritative plan, then execute in the ordered stages below. Keep the one-writer rule. Do not launch parallel generic reviewer agents.

---

# 1. Mandatory boundaries

1. Live remains locked.
2. No future data / winner backfill / later ATH.
3. New research features start `decision_eligible=0 / affects=none` unless this handoff explicitly says otherwise.
4. Do not lower current Strategy/Decision gates to obtain trades.
5. Do not raise production Agent concurrency above 2.
6. Do not make KOL/social/project metadata trade evidence just because it is popular.
7. Do not label a liquidity drop “developer removed LP” without actual pool/LP/onchain evidence.
8. Do not mechanically reject `LP unlocked` until market surface + canonical pool semantics are known.
9. Keep Base/Robinhood research-only for Strategy/Paper until their execution/safety/cost challenger matures.
10. Use official docs/mature OSS before custom protocol decoding. Reuse Pump official IDLs/SDK definitions, Solana JSON-RPC, 0x, GoPlus, Honeypot, Raydium/Pancake docs as appropriate.
11. No Git commit/push.
12. Minimal targeted tests per local change; full suite only at coherent deployment boundary.

---

# 2. Current facts Codex must verify before editing

At Lead cutoff:

- r6: tokens 160,695; events 5,968; decisions 2,975; WAIT 2,607 / REJECT 364 / CANDIDATE 4; trades 8.
- main Paper realized PNL ≈ -$4.3188; no open position.
- information-first active sampler: targets 24, attempts/results 12/12, terminals 14; 4 terminals `scheduler_missed_deadline`, 2 `late_response`, 8 `observed_mark`.
- `onchain_only_jupiter_quote_*` already has thousands of amount-specific Solana quote records.
- `solana_holder_shadow_*` exists but raw holder role classification is not economically meaningful yet.
- PumpPortal raw create event includes `traderPublicKey`, `initialBuy`, `solAmount`, `bondingCurveKey`, signature, reserves etc.
- `Store.upsert_token()` currently replaces `tokens.raw_json` on later upsert, so launch facts are not durable immutable launch evidence.
- current `SafetyChecker` EVM chain map excludes Robinhood and explicitly rejects Robinhood; official GoPlus now supports chain 4663; official 0x now supports BSC/Base/Robinhood.
- normal main Paper execution still uses DexScreener mark ± configured slippage rather than amount-specific router minimum output.

If any fact changed, preserve later code/SQLite truth and record the delta; do not invalidate the research conclusions merely because counts advanced.

---

# 3. Execution order

## P0-A — Finish active-outcome sampler deadline correctness first

### Observed failure

Natural active sampler has already produced `scheduler_missed_deadline` and late-response terminals. Earlier first natural target created an attempt before deadline, provider request blocked, and the hard-deadline finalizer could not run because request/finalizer were in the same awaited periodic action. Later natural samples include 4 `scheduler_missed_deadline`.

### Required behavior

- Deadline finalization must not be hostage to a provider await.
- At each target, schedule +0/+30/+120/+300 seconds exactly as registered.
- A request must have a bounded timeout that cannot exceed the frozen deadline.
- Provider work may complete late, but late responses must append a late result and must not rewrite the terminal.
- `scheduler_missed_deadline` should mean scheduler itself failed to start any request, not “provider call was slow”.
- The periodic sampler must not starve other runtime tasks.

### Minimal implementation options

Prefer the smallest one:

1. wrap the provider quote in deadline-bounded `asyncio.timeout()`/equivalent and finalize after each bounded call; or
2. separate deadline finalizer into a lightweight periodic task if this is materially safer.

Do not add a queue framework.

### Acceptance

- unit test: provider hangs beyond target deadline → terminal is written on/bounded near deadline, no unbounded task blockage;
- unit test: late provider response cannot overwrite terminal;
- unit test: scheduler-missed vs timeout/late-response semantics remain distinct;
- controlled Paper restart only if needed;
- natural next targets should show attempts/results/terminals with no new scheduler-miss caused by provider blockage.

### Stop gate

If >5% future matured targets are scheduler-originated misses after the fix, pause interpretation and fix scheduling before using active outcome coverage.

---

# 4. P0-B — Immutable token launch facts

### Why now

Creator/developer analysis is impossible to do causally if Pump create facts disappear when `tokens.raw_json` is later overwritten by hydration. Current raw Pump data already has high-value launch fields. Preserve them before building wallet intelligence.

### Minimal schema

Create an append-only launch fact table, e.g. `token_launch_facts`:

- id
- token_id
- chain
- launch_provider
- launch_surface / launchpad
- launch_event_type (`create`, `migration`, etc.)
- mint/address
- creator_address / trader_public_key
- create_signature
- bonding_curve_key / initial_pool_key
- initial_buy_token_amount
- initial_quote_amount (SOL/USDC/BNB as applicable)
- initial_market_cap_native
- initial_virtual_quote_reserve
- initial_virtual_token_reserve
- token_pairing (`SOL`, `USDC`, unknown)
- source_observed_at / ingested_at / recorded_at
- raw_payload_hash
- definition_version
- `decision_eligible=0`
- `affects='none'`

Unique key should reflect exact immutable launch event, not token only, because migration is a separate event.

### Ingestion

- Freeze PumpPortal create fields at the existing `TokenCandidate` ingestion point before later upsert can replace `raw_json`.
- Do not backfill old r6 into the new experiment denominator. Historical rows can be a separate design-only extraction if needed, clearly versioned and excluded.
- Keep token table behavior unchanged unless a minimal merge is necessary for unrelated correctness.

### Derived research features — append-only/as-of only

- creator prior launch count;
- creator prior launch cadence;
- creator prior survival/graduation/liquidity-collapse/route statistics using only outcomes mature before this launch;
- initial self-buy amount / fraction;
- factory-like launch frequency.

Never use later creator history for earlier launch.

### Tests

- launch fact survives later Dex hydration/upsert;
- exact timestamps preserved;
- no Strategy/Paper/Decision side effects;
- duplicate create replay is idempotent; migration remains a separate fact.

---

# 5. P0-C — Market-surface classifier

### Purpose

Security, fees, LP semantics and liquidity failure cannot be interpreted without knowing exact market surface.

### Add a normalized research descriptor

For each relevant pair/route snapshot freeze:

- chain
- dex_id
- pair_address
- base/quote mint
- launchpad/source
- surface_type: bonding_curve / CPMM / CLMM / v2 / v3 / v4 / unknown
- canonical_status: `pump_canonical / pump_noncanonical / not_applicable / unknown`
- pool_creator / LP position owner evidence if available
- liquidity_control: `protocol_owned_burned_lp / user_withdrawable_lp / nft_position / unknown`
- migration lineage
- pair_created_at
- source/provider
- as-of timestamps

### Pump rules

Use official Pump program / PumpSwap IDL semantics:

- Pump bonding curve completion/migrate → canonical PumpSwap; Pump Program says LP tokens received are burnt.
- canonical pool can be identified from Pump pool authority semantics / migrate lineage.
- ordinary PumpSwap pools have LP tokens and `withdraw`.

### Other surfaces

- Raydium CPMM/CLMM;
- Pancake V2/V3;
- Uniswap/Aerodrome and Robinhood DEX surfaces as encountered.

Do not build a universal DEX decoder. Implement only surfaces observed in current candidate/research flow and preserve `unknown`.

### Acceptance

- a known Pump canonical pair is classified canonical/protocol-owned semantics;
- a known normal PumpSwap pool remains user-withdrawable/unknown as appropriate;
- Pancake V2 and Raydium surface labels are preserved;
- no vendor `LP unlocked` flag is reinterpreted as a hard reject solely from this change.

---

# 6. P0-D — Liquidity survival and failure-mode Shadow

### Motivation

Lead retrospective same-pair analysis (design-only): fixed `chain+dexId+pairAddress`, first local liquidity >=$12k, require >=30m later observation; 2,864 mature pairs, ~37.4% lost >=90% same-pair liquidity within 60m. BSC Pancake ~84.5%, PumpSwap ~43%; highly confounded but large enough to make liquidity survival a P0 research target.

### Register new strict-forward version

Example: `liquidity-survival-shadow/v1`.

Freeze future cohorts only. No historical winner-based admission.

### Cohort eligibility

Prefer one coherent estimand, for example:

- first post-registration snapshot for a newly discovered token/pair when same-pair liquidity first crosses a fixed pre-registered baseline (e.g. current $12k gate), OR link to existing token-universe baseline if that already supplies a cleaner denominator.
- include all eligible pairs, not just later collapses.

### Fixed targets

Suggested: baseline / 1m / 5m / 15m / 60m; add 240m only if provider budget is safe.

### Data

- exact market surface/canonical status;
- same pair liquidity/reserves;
- token/quote reserve where available;
- volume/tx/buy/sell;
- amount-specific route/min output if available;
- LP owner/lock/position evidence;
- creator/related-entity evidence if available;
- migration/pair-switch evidence;
- provider errors/missing.

### Terminal classification

Strict hierarchy with evidence:

- `lp_withdrawal_confirmed`
- `sell_drain_observed`
- `migration_or_pair_switch`
- `route_disappeared`
- `provider_unobservable`
- `liquidity_collapse_unclassified`
- `survived`
- `missing/error`

A DexScreener drop alone must never be `lp_withdrawal_confirmed`.

### Onchain proof priority

- Pancake V2: LP Burn/remove liquidity related logs/transactions + LP ownership where feasible.
- Pump canonical: treat LP withdrawal by coin creator as structurally unavailable unless contrary onchain evidence; investigate sell drain instead.
- Pump noncanonical: PumpSwap withdraw semantics apply.
- Raydium CPMM/CLMM: Withdraw/DecreaseLiquidity semantics.

### Outputs

No production score. Report by surface:

- survival rate;
- no-route rate;
- collapse rate;
- confirmed withdrawal rate;
- sell-drain rate;
- time-to-failure;
- relation to future executable outcomes.

---

# 7. P0-E — Execution-realism research parity

## Solana

Existing Jupiter Shadow already proves amount-specific quote infrastructure. Do not duplicate it.

Codex should design the smallest path to make **future main Paper** use a frozen, amount-specific two-way execution model, but only after a separately registered challenger validates it against current mark±slippage Paper.

Challenger fields:

- intended USDC notional;
- BUY quote min output;
- acquired minimum token amount;
- SELL quote for actual remaining amount;
- slippage bps;
- platform/pool fees;
- signature/prioritization/rent fees;
- quote request/response clocks;
- no-route / stale / protocol-invalid terminals.

Pump fee model must follow current dynamic fee schedule rather than a permanent 125bps assumption.

## EVM BSC/Base/Robinhood research

0x now supports chain 56/8453/4663. GoPlus now supports 4663.

Do NOT directly enable Paper.

Create read-only execution overlay/challenger with:

- amount-specific sellAmount/buyAmount/minBuyAmount;
- token buy/sell tax;
- `totalNetworkFee`;
- gas/gasPrice;
- route liquidity sources;
- no-route/errors;
- chain id;
- request/response clock.

For Base, account for L2 execution + L1 security fee; 0x `totalNetworkFee` can be compared to Base GasPriceOracle / documented semantics.

If 0x requires a key, do not write/print it. Use existing secret/config mechanism only if configured; otherwise leave capability disabled with a clear external prerequisite rather than blocking other work.

### Promotion gate

Main Paper replacement only after future paired samples show the challenger produces reliable fills/no-fills and costs. Do not silently mix execution semantics in a single performance series.

---

# 8. P1-A — Rich behavioral safety Shadow from existing provider fields

### EVM immediate data

GoPlus already exposes:

- creator address/balance/percent;
- holder count/top10 holders/tags/lock/contracts;
- LP holder count/top LP holders/lock;
- pool fee;
- malicious address indicators.

Honeypot.is simulation exposes:

- buy/sell tax;
- maxBuy/maxSell when detected;
- buy/sell gas;
- honeypot status.

Current SafetyChecker uses only part.

### Implement research normalization

Do not hard gate at first. Store:

- creator_direct_percent;
- owner/top10 circulating share after role exclusion where possible;
- LP top holder/lock;
- max sell/buy; gas;
- provider disagreement;
- malicious creator/address flags;
- pool fee.

Version, as-of, append-only.

### Surface-aware rules

Before computing top10/user concentration, classify addresses as:

- burn/null;
- pool/bonding curve;
- LP locker;
- protocol/program;
- creator/deployer;
- unknown/user.

Do not treat a pool/PDA as insider.

---

# 9. P1-B — Targeted Solana creator / first-N buyer Shadow

### Why targeted

Do not stream every transaction for 160k Tokens on the personal PC. Start after deterministic shortlist or a small registered sample.

### Data source order

1. existing Pump create facts;
2. official Solana public RPC `getSignaturesForAddress` + `getTransaction` for token/bonding curve/pair;
3. Pump official IDLs/SDK/program event definitions;
4. only if public RPC coverage/latency demonstrably fails, evaluate Yellowstone/Geyser or a provider.

### Cohort

Strict future registration; sample deterministically from new Pump launches OR reuse a pre-registered onchain Shadow subset. Freeze sample before outcomes.

### Features

- creator direct wallet;
- creator initial buy;
- creator first-N buyer rank;
- first 10/20/50 unique buyer addresses;
- buyer interarrival time;
- same slot/bundle evidence;
- shared funding source where observable;
- repeated cross-launch co-occurrence;
- early buyer sell-through;
- creator actual sell vs transfer;
- related-wallet balance if cluster evidence supports it;
- unique buyer count, amount concentration, Gini/HHI;
- wash/circular flow indicators.

### Economic entity

Version cluster heuristics. A relation is evidence strength, not a certainty:

- shared funder;
- repeated co-firing across launches;
- same bundle/slot with deterministic relationship;
- direct transfer link;
- common creator/deployer.

Keep raw address lineage auditably available under E: but do not send it to Agents unless required. Agents are not needed for graph arithmetic.

### Critical causal warning

RED-COHORT-2026 finds repeated early cohorts but an activity-matched placebo produces even larger buyer-flow lift. Therefore repeated cohorts must not become a production “smart money” positive signal without launch-quality controls. Treat it primarily as coordination/manipulation context.

---

# 10. P1-C — Creator/developer position state

Implement only after launch facts + targeted tx lineage exist.

State per token/as-of:

- creator direct holding;
- creator direct sold amount;
- creator direct transferred amount;
- related-entity holding if supported;
- entity net sold amount;
- creator fee collection separately;
- `direct_wallet_empty` must not equal `creator_entity_exited` unless lineage supports it.

Do not hard reject `dev sold` or `dev did not sell` initially. Learn relationship to liquidity survival / executable loss / rug outcomes.

---

# 11. P1-D — NarrativeEpisode + neutral lead-lag ledger

### Goal

Stop forcing the architecture to assume News-first or Token-first.

### Minimal tables

`narrative_episodes`
- version/id/key/category/first_available/state/recorded_at/affects-none.

`narrative_episode_observations`
- episode + observation + source/action/duplicate fingerprint/available_at.

`token_narrative_bindings`
- token + episode + binding basis/confidence/fanout/as-of.

`token_narrative_lead_lag`
- token/episode;
- narrative primary first available;
- narrative independent first available;
- token create;
- first local discovery;
- market ignition;
- social acceleration;
- executable entry quote;
- missing states.

### Important

Use existing Event/Observation tables; do not duplicate source text. NarrativeEpisode is semantic grouping, not a new evidence authority.

### Narrative states

`dormant / ignition / emerging / expansion / crowded / exhaustion / decay / corrected/invalidated`.

Initial states research-only.

---

# 12. P1-E — Social Heat / Acceleration v1 with honest coverage

Use current locally captured public X/browser/Trend/RSS first. Do not pretend full-X coverage.

Feature buckets:

- unique observed creator count;
- unique exact-post/text fingerprint count;
- duplicate ratio;
- original/repost/quote mix;
- mentions/minute inside covered universe;
- creator growth;
- engagement growth where supplied;
- cross-platform breadth;
- watchlist reputation/priority as descriptive only;
- paid promotion/Dex boost fraction;
- social→price and price→social lag.

Every heat record must include `coverage_scope` / collector coverage state. If X extension stale, heat cannot be silently interpreted as low.

No production score in v1.

---

# 13. P1-F — Position-aware information monitoring

### Current gap

After a Paper BUY, Token Context runs once. No persistent position-specific Agent watch exists.

### Implement event-driven, not interval-agent polling

When a new Paper/Shadow position opens, register an append-only `position_information_watch` referencing:

- position/trade/decision/cohort;
- token_id;
- narrative episode;
- creator entity;
- exact source links;
- entry narrative/social states.

While position open:

- priority collect exact token/creator/narrative sources;
- deterministic new source/revision detection;
- use existing source-fact single-flight;
- trigger Agent only on a new material source/revision/contradiction/correction/public-figure action/state-transition candidate.

Do not run Agent every minute.

### Research exit events

Record challenger reasons:

- narrative decay;
- correction/denial;
- social acceleration reversal;
- creator/entity net selling;
- manipulation risk spike;
- liquidity survival deterioration.

Do not replace deterministic route-backed exits until forward paired samples mature.

---

# 14. P2 — KOL Hypothesis Library

Use curated/watch-account X posts, not random web hype.

For each methodology/experience post extract:

- author/entity;
- exact post id/URL;
- published_at;
- ex-ante vs retrospective;
- chain/launchpad/regime;
- proposed metric/threshold/direction;
- rationale;
- evidence type;
- promotion/conflict markers.

Retrospective winner posts **cannot** count as prediction success.

Future evaluation labels:

- executable 15/60/240 return;
- dynamic-exit PNL;
- catastrophic-loss rate;
- no-route;
- liquidity survival;
- manipulation/rug outcomes;
- identity errors.

Keep KOL utility sample-size-shrunk; no raw-follower ranking.

---

# 15. P2 — Statistical challenger only after data maturity

Do not ask an LLM to produce a direct buy score from all these features.

Candidate models after enough forward labels:

- regularized logistic / ordinal;
- survival/hazard for liquidity/route survival;
- gradient boosting with calibration.

Time-split train/validation/test. Strictly closed future holdout. Preserve chain/launchpad regime and date clustering.

Evaluation is not average return/ATH. Use:

- median net return;
- expected utility;
- catastrophic loss;
- drawdown;
- route failure;
- calibration;
- precision/recall for executable positive returns;
- capital lock;
- tail risk.

---

# 16. Existing candidate/safety logic: what NOT to do during this implementation

Do NOT immediately:

- reverse liquidity weights because current exploratory correlations show lower absolute liquidity/mcap had higher 15m returns;
- increase/decrease `min_buy_ratio` from the retrospective analysis;
- hard reject creator repeat launch count;
- hard reject developer sold/cleared;
- hard reject top10 percentage before entity-role correction;
- hard reject Pump canonical `LP unlocked` vendor flag;
- add social heat to Candidate score;
- enable Base/Robinhood production Candidate;
- increase Agents;
- train on current 4 main Paper trades.

All of those require future challenger evidence.

---

# 17. Required durable updates during execution

At the end of each substantive stage, update:

- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md`
- `docs/PROJECT_CONTEXT/SNAPSHOT_2026-09-03.md` (create if needed; do not rewrite old snapshot)
- `docs/PROJECT_CONTEXT/REQUIREMENT_LEDGER.md` for continuous items
- `docs/PROJECT_CONTEXT/CHATGPT_CODEX_SYNC_STATE.json` / mailbox as appropriate

Do not duplicate the 33k research report into other docs; point to it.

---

# 18. Suggested stage acceptance sequence

1. **A** sampler deadline fix → targeted tests + natural proof.
2. **B+C** immutable launch facts + market-surface classifier → local tests; no runtime trade effect.
3. **D** liquidity-survival Shadow → register future boundary → controlled deploy → prove first natural cohort/terminal.
4. **E** execution overlay/challenger → Solana reuse existing Jupiter; EVM bounded 0x research if credential capability exists.
5. **P1-A/B/C** behavioral safety + targeted wallets → Shadow only.
6. **P1-D/E** NarrativeEpisode/lead-lag/social features → Shadow only.
7. **P1-F** position information watch → incremental, affects none initially.
8. **P2** KOL and modeling after denominators mature.

If a stage reveals a higher-severity causal/production bug, fix that bug and resume; do not use it as justification for a new audit project.

---

# 19. Expected near-term outcome

The near-term goal is **not** “more Paper trades”. It is to transform the system from:

`Event/Token text match + basic market score + contract security + mark-based Paper`

into a forward learning system that can answer, for every attractive new Meme candidate:

1. Is this the exact right CA, or a clone?
2. What market surface are we on and who controls/owns withdrawable liquidity?
3. Can a fixed dollar amount actually buy and later sell now?
4. Is the creator/deployer/early-buyer structure natural or coordinated?
5. Is liquidity likely to survive the next minutes, and if it disappears was it LP withdrawal, sell drain, migration or data loss?
6. Is there a real narrative? Is it growing organically, already crowded, or promotional/manipulated?
7. Did information lead the market, or did price lead social FOMO?
8. While holding, did the narrative/creator/liquidity state materially change?
9. What did the strict forward outcome show after costs and tail failures?

Only after those answers are measured across natural forward cohorts should Strategy gates be changed.
