# Strategy / Policy / Chain / UI implementation research — 2026-09-03

Status: `LEAD_RESEARCH / READY_FOR_INCREMENTAL_CODEX_EXECUTION`
Owner for implementation: Codex thread `01a0514b-bbb5-7400-baf9-d9feb4dc603d`
North star: improve genuine forward, executable, cost-adjusted, risk-adjusted meme-token profitability. No future data, no winner backfill, Live locked.

## 1. Strategy model corrected by latest user instruction

The top-level strategy family is the opportunity-information model, not the exit method.

1. `S1 information_plus_token`: information/news/KOL/person/community/narrative and Token data jointly decide entry.
2. `S2 token_only`: Token/onchain/market/safety/execution information decides entry; no narrative is required.
3. `S3 token_then_information`: Token/onchain conditions trigger the initial position, then post-entry news/hot-topic/person/community/narrative/creator evidence controls subsequent position management.

Each family must support multiple independently versioned policy arms:
- signal policy;
- entry timing;
- sizing/notional;
- add-on/DCA policy;
- hard stop;
- trailing;
- staged take profit;
- sell fractions;
- runner fraction;
- max hold;
- liquidity/no-route emergency;
- chain execution profile / cost model.

A dynamic-exit policy is therefore not a fourth strategy. It is a policy arm inside a strategy family.

## 2. Recommended local architecture: Strategy Controller -> Policy Arm -> Execution Adapter

Do not import a new trading framework. Borrow the separation pattern from Hummingbot Strategy V2:
- Controller = persistent strategy logic reading normalized state and emitting actions.
- Executor = finite entry/position/exit workflow with its own lifecycle.

Local equivalent should remain simple Python + SQLite:

`StrategyFamilyController`
  -> `SignalPolicyVersion`
  -> `SizingPolicyVersion`
  -> `ExitPolicyVersion`
  -> `ChainExecutionAdapter`
  -> append-only `PolicyRun/Trade/Outcome`

The architecture is useful because S1/S2/S3 can share execution adapters while owning different signal and position-management policies.

Reference: Hummingbot V2 Controllers/Executors architecture, https://hummingbot.org/strategies/v2-strategies/ . Do not copy the framework wholesale.

## 3. S3 causal correction

Keep S3 as a research/strategy family, but current control implementation is confounded. Current runner definition uses dynamic exit challenger as its baseline while S2 top-level baseline uses fixed 15/60/240 exit. With narrative treatment disabled they can still diverge.

For the next clean forward version:

### S3-Control
- exact S2 Token;
- exact source BUY;
- exact entry time/notional/acquired raw amount/cost;
- exact S2 baseline exit semantics;
- collect post-entry narrative evidence but `affects=none`.

### S3-Treatment
Only after preregistration, permit post-entry divergence on event-driven evidence such as:
- new independent origin;
- correction/denial;
- important public-figure action;
- narrative-state transition;
- creator/LP anomaly;
- organic-vs-promotion state change.

Deterministic safety, route loss, hard risk and untradeable terminals always override narrative.

S3 may later learn a different size/sell policy, but first prove incremental information value using a clean exact-pair control.

## 4. Policy self-optimization design

Do not use unrestricted online self-modification or RL now. Use staged policy promotion:

`COLLECTING -> MATURE_DESCRIPTIVE -> POLICY_CANDIDATE -> CHALLENGER_PREREGISTERED -> FORWARD_CHALLENGER -> TEMPORAL_HOLDOUT_PASS -> PROMOTABLE | REJECTED`

Parameter candidates include:
- entry notional;
- DCA count/fractions;
- hard stop;
- trailing activation/drawdown;
- TP thresholds and fractions;
- runner fraction;
- max hold;
- liquidity survival threshold;
- no-route retry/write-off policy.

Objectives/constraints:
- executable net PNL;
- catastrophic-loss rate;
- max drawdown;
- no-route rate;
- capital lock;
- tail loss;
- cross-date stability.

Optuna is appropriate only for offline/rolling temporal candidate search. Prefer constrained TPE or limited discrete/grid search at current sample size; do not optimize dozens of dimensions. Multi-objective APIs support constraints; treat catastrophic loss/drawdown/no-route as constraints where possible rather than a giant weighted scalar. Reference: https://optuna.readthedocs.io/en/stable/reference/samplers/ and multi-objective tutorial.

River/ADWIN can later monitor a scalar policy performance metric for regime/concept drift. It should raise `REVIEW_REQUIRED` or reduce confidence, not rewrite live thresholds. Reference: https://riverml.xyz/latest/api/overview/ and ADWIN docs.

## 5. Current evidence maturity implication

Current r6 already has substantial descriptive evidence, but not mature policy adaptation:
- token-universe forward data is very large;
- liquidity-survival has thousands of outcomes;
- source utility has only a handful of independent closed Paper outcomes across a few dates;
- Token Context mature labels remain insufficient;
- attention learning still applies multiplier 1.0.

Therefore the immediate learning task is promotion governance, not creating more unrelated Shadow tables.

Liquidity survival is the first strong candidate research family for a future policy challenger because current local v3 data show materially different 60m collapse behavior across chains/surfaces. These are descriptive/confounded and cannot become thresholds directly.

## 6. Chain execution architecture

Keep S1/S2/S3 as top-level accounts. Do not create strategy x chain top-level account explosion. Every token/position/trade must carry `chain`, and each strategy API/UI returns per-chain breakdown.

Suggested `ExecutionCostBreakdown`:
- `chain`;
- `execution_quality`: executable_quote | modeled | indicative;
- `route_provider`;
- `venue_fee_usd` / embedded flag;
- `adverse_slippage_usd` / min-output semantics;
- `buy_tax_usd` / `sell_tax_usd`;
- `network_execution_fee_usd`;
- `l1_data_fee_usd` where applicable;
- `approval_fee_usd` where applicable;
- `total_cost_usd`;
- `fee_model_version`;
- point-in-time timestamps.

Observed dynamic costs take precedence. A frozen fallback is allowed only when unavailable and must remain explicitly `modeled`.

### Solana
- Jupiter amount-specific BUY minimum output;
- acquired raw quantity from the quote lower bound;
- remaining raw quantity -> amount-specific SELL;
- route/fee/price impact;
- signature/prioritization/rent where reliable;
- Pump/PumpSwap dynamic fee/surface semantics.

### BSC
Current Uniswap V3-only research is too narrow. Prefer aggregator firm/executable quote where configured (0x supports chain 56). Require:
- BNB gas;
- allowance/approval;
- buy/sell tax;
- honeypot/max-sell/blacklist/fee-on-transfer evidence;
- actual SELL ability;
- no-route terminals.

Use Foundry/Anvil fork simulation as a research validator for router transaction, transfer tax/reverts/max-sell. Anvil can fork any EVM-compatible chain at a fixed block and trace transactions. Reference: https://www.getfoundry.sh/anvil/index.html .

### Robinhood Chain
- chain id 4663, ETH gas;
- 0x officially supports Swap/Gasless and broad native routing;
- official Robinhood `/rhj/assets` returns Stock Token deployments. Build deterministic exact-address `stock_token/rwa_excluded` registry before Meme Candidate/Paper;
- EVM safety provider must explicitly support/test 4663 before removing current safety rejection;
- route/gas profile independent from BSC.

References:
- 0x supported chains: https://docs.0x.org/docs/introduction/supported-chains
- 0x 2026-07-31 Robinhood launch / route sources: https://docs.0x.org/changelog/2026/7/31
- Robinhood Stock Token API: https://docs.robinhood.com/chain/stock-token-apis/
- Robinhood connecting: https://docs.robinhood.com/chain/connecting/

### Base
Latest user emphasis is Solana/BSC/Robinhood, but Base history/code must remain. Keep it as retained research capability; if/when promoted, require Base L2 execution + L1 data fee semantics rather than generic EVM gas alone.

## 7. UI redesign contract

Do not rewrite the backend or introduce a frontend framework. Incrementally decompose current monolithic `portfolio()` and separate operating state from research detail.

### Information architecture

Top bar: Runtime | collectors | Agent | route/quote | data freshness | blocking issue | PAPER/LIVE LOCK.

Main portfolio: exactly 3 strategy tabs:
1. News + Token
2. Token-only
3. Token -> post-entry information

Each tab shows first:
- cash;
- realized PNL;
- executable unrealized PNL;
- unknown/unpriced exposure;
- max drawdown;
- win/loss counts;
- capital lock;
- current signal/size/exit/cost policy version;
- policy-arm comparison.

Chain filter/breakdown inside strategy:
`ALL | SOL | BSC | ROBINHOOD` (Base can remain research/retained until user re-promotes it).

Every position/trade displays:
- chain badge;
- `EXECUTABLE / MODELED / INDICATIVE`;
- route;
- slippage/min-output;
- token tax;
- network/L1 fee;
- total cost;
- no-route/write-off state.

Research Lab is default-collapsed and contains:
- liquidity survival;
- creator history;
- first buyers;
- holder concentration;
- source/KOL utility;
- Agent admission;
- missing/error denominators;
- promotion state.

For charts, existing SVG can remain initially. If the local hand-built chart becomes a maintenance/performance bottleneck, Apache ECharts is a reasonable optional future dependency because it supports streaming/large datasets. Do not add it merely for decoration. Reference: https://echarts.apache.org/en/feature.html .

## 8. Communication architecture

Current safe path is `E: durable artifact + CHATGPT_CODEX_SYNC_STATE.json + prompt/resume hook`.

Observed hook bug: it currently picks `open_groups[0]` when `attention_required=true`; an old ACKED group can mask a later unresolved release blocker. Fix selection to choose the newest/highest-priority unresolved group, preferring `blocks_release=true` / `ATTENTION_REQUIRED`, excluding ACKED/RESOLVED/SUPERSEDED.

Do not use `codex resume` as a message bus while another writer is active. Desktop app-server internally has `send_message_to_thread`, but that tool is not exposed in the ordinary tunnel CLI MCP list. Future optional COMMS-v2: authenticated loopback doorbell to the existing app-server after an isolated proof that it never creates a second writer. Durable E: handoff remains authority even if doorbell is added.

## 9. Immediate Codex tranches

### TRANCHE A — safe coordination + current startability
1. Fix hook unresolved-group selection; targeted unit/synthetic hook test.
2. Resolve current Runtime->Store constructor/signature mismatch; add targeted Runtime construction/startup test.
3. Do not stop the healthy loaded process until current checkout is startable.

### TRANCHE B — execution path recovery
1. Diagnose why current 20-USDC Solana onchain cohorts exist but Jupiter v2 attempts/results remain zero.
2. Fix dispatch/registration/version scheduling without backfill.
3. Observe first natural post-fix attempt before interpreting S2/S3 zero trades.

### TRANCHE C — clean S3 control
Register a corrected S3 control before the first new clean paired position under the new fair version. Treatment disabled => exact S2 baseline exit.

### TRANCHE D — chain execution
1. Robinhood official Stock Token/RWA exact registry + 4663 safety support.
2. BSC/Robinhood execution adapter interface and chain-aware cost breakdown.
3. Prefer 0x firm route when configured; otherwise result remains research/modeled.
4. Add Anvil fork-simulation experiment for EVM sellability; do not block production collection if RPC/provider prerequisite is absent.

### TRANCHE E — UI
Incrementally split strategy summary / policy arms / chain breakdown / research lab, preserving current API until chain-cost fields are available.

### TRANCHE F — learning/promotion
Add generic promotion-state summary first; do not implement automatic trading-rule changes yet.

## 10. Release guard

Any new strategy/policy version:
- activation point;
- append-only denominator;
- no historical winner backfill;
- point-in-time evidence;
- complete missing/error/no-route terminals;
- old versions preserved;
- Live locked;
- no Git push unless user reverses instruction.
