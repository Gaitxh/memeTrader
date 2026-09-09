# 119 shared microstructure — prepared Shadow stage, NOT deployed

REPLY_TO: C2C-20260910-DUAL-MICROSTRUCTURE-ROUTER-119
Status: SHADOW_TRIAL_REJECTED_RUNTIME_GUARD / ROLLED_BACK. This is not completion of both requested Paper branches.

## FINAL runtime disposition — overrides implementation checkpoints below

Shadow integration93aa15e loaded via existing launcher at2026-09-09T21:08:45Z (supervisor31028), no reset. At21:10:41Z startup window: pattern p95=45.981s (3 samples) versus pre12.116s (120); passive wait p95=47.727s (9) versus pre2.664s (120); held_fetch p95=69.889s (6,2failures) versus pre1.763s (120); drops0/PoolTimeout0/connect_errors4. This fails the conservative runtime guard. Startup and previously pending code loading are confounders: this is NOT a controlled proof119 caused the slowdown, especially because classifier candidate/request counters stayed0.

At21:11:37Z withdrew ONLY119 runtime/preentry/store hooks and Gecko arbitration/backoff changes, restored those files to pre93aa15e, and loaded via existing launcher (supervisor9636). Standalone classifier, cached adapter, bounded worker/outcome research code and fixtures remain; no runtime initialization or callback uses them. The retained worker refuses transport without the now-absent shared Gecko priority capability. The trial remains inspectable in93aa15e Git history. The modified pacing test and integration-only priority test were withdrawn with runtime implementation; remaining12microstructure tests PASS.

Rollback21:12:41Z: /health+/api/live running, same funding period, Paper/Live locked; passive92/92/depth0/drops0, wait p95=2.760s; pattern p95=5.326s (3); held_apply p95=.0559s; held_fetch p95=3.405s (72). PoolTimeout/connect_errors0, retired clients0. Held is still above the old mature baseline; no claim of comparable-load full latency acceptance. Do not periodically restart to conceal it.119 remains disabled.

Last119 KV21:11:30.204887Z has candidate0/request0/classifications0, no funded registrations/BUY/outcomes. Preserved KV is an inactive trial snapshot, not a live denominator. No forced candidate/query was manufactured. Immutable registration/activation/policy/funding/capital digest before trial and after rollback identical: b45a4ae22870b3051eaf0d7650dc779236b37b0aa1a64711c8c5357e52be54db. All historic positions/profits/exits remain. Data artifacts: data/research/microstructure119/*before.json, *after.json, performance_later.json, *rollback.json, immutable_before.json, rollback_state.json.

The supported launcher worked for this new explicitly authorized trial, superseding the prior process-control blocker. Previously pending final109/110-113 code was also loaded at this boundary; their natural acceptance is NOT implied by119 smoke. No funded114 registration (inert registrar). Four115 pauses remain in existing KV.

Remaining requested Paper work is deliberately NOT registered: organic5U/max2 needs a resource-accepted classifier feed; synthetic1U/max1 also needs an exact-pool positive sell simulation and no hard safety rejection; Solana still needs a complete existing amountful wallet adapter. This is the task's permitted Shadow fallback after a failed resource trial, not two completed strategies or evidence of Alpha. Restore shared priority safely and demonstrate comparable-load acceptance before another forward deployment; do not loosen clocks/coverage/safety to obtain samples.

## Subsequent integration checkpoint (supersedes pending wiring below)

Added shared Gecko high/low request-start arbitration; existing held original-pool calls explicitly high, low starts yield to pending high, cancellation removes waiting tickets. Existing2.1s spacing remains. Gecko429 now updates the same HttpClient backoff, including retries. No change to Dex arbitration.

Added MicrostructureWorker on existing idle trader tick; no new periodic task. It accepts only admitted rare existing event_reawakening/quiet/clone/prebreakout source decisions, maximum8 pending, original signal expiry, bounded persisted seen/queue state, <=1 supplemental request/min and skips when the last minute already has8 Gecko starts. It does not revive paused age-rate or use old snapshots as new signals. Common safety REJECT is retained; explicit cannot-sell reasons produce HARD_UNSELLABLE without a trade request. Safety and trading decisions are otherwise unchanged. Solana consults indexed local amountful evidence only, returning explicit missing-adapter UNKNOWN until full per-wallet adapter exists.

Classifier receipts append to existing pattern evidence; later exact-pool snapshot callback anchors the outcome strictly after classification receipt, or records missing anchor UNKNOWN. Existing idle15s flush expires/caps outcome state. Raw code capture is prospective only; no historical replay.13 dedicated tests plus shared preentry/stock tests total63PASS. Gecko/original-pool selected checks9passed initially; the remaining old sleep-mock test was updated to verify actual condition-based pacing, then passed. No repeated whole-suite testing.

Still pending: natural request/held acceptance; exact original-pool positive sellability receipt adapter; Solana complete trade-level adapter; funded policy registration/fill tests. The two funded branches remain unregistered. Source scopes/budgets above are Shadow supply, not proof that either new strategy can enroll.

119 supersedes the old prohibition on deliberately studying manipulated-but-sellable opportunities: the authorized synthetic experiment is separate1U/max1/15m, not normal-meme Alpha. It does not revive funded Capital Pulse114 or authorize hard-unsellable buys.115 parent/derivative pauses remain unchanged.

## Implemented, without production writes

`market_microstructure.py` implements normalized exact-pool/token trade classification, signed buy/sell USD, net/gross, wallet count/effective breadth, top1/top3 gross concentration, both-side overlap, dominant-wallet gross/sell share, size/interval CV. Sender addresses are not asserted to identify humans. States are ORGANIC_BREADTH_NET_BUY, SYNTHETIC_SINGLE_WALLET_CYCLE, UNKNOWN, HARD_UNSELLABLE.

Initial mechanistic research buckets, not learned cutoffs: synthetic >=4 trades, one observed sender, both buy/sell and net sell; organic >=5 senders, effective breadth>=4, top1<=50%, net buy. These are unvalidated conservative descriptors. Regularity is reported separately, not a standalone scam verdict. No CRUMBS/BNC4 addresses or theme allowlist in code.

The prepared shared-HttpClient adapter uses one unfiltered exact-pool page, <=1 supplemental request/min globally,60s original-receipt cache,128 pool bound, duplicate request serialization and shared429 backoff; no retry/pagination invented. It refuses to start without an explicit shared held-start admission context. It creates no HTTP client or scheduler. Cache hits retain original availability.

Coverage requires both returned trade-time boundaries span the chosen window and verified descending order; empty/fewer-than-cap does not alone authorize completeness. Trade side is derived from exact from/to token identities, not default provider `kind` orientation. Post-window rows may prove recency but never contribute metrics; all rows must have causal availability. A latest300 truncated window is UNKNOWN, never zero flow.

Pure branch eligibility requires later original-pool frame, floor>=1000, safety allowed and no hard veto. Organic requires a reawakening episode. Synthetic requires BSC plus a positive same-token/same-pool recent simulation receipt; token-only simulation or another-pool result stays WAIT. This is Shadow eligibility, NOT fill authority or account registration. It does not bypass common soft hazards.

Bounded MicrostructureShadow retains128 recent receipts and reuses existing passive15/60/240 outcome machinery, including UNKNOWN/HARD triggers, strict later callbacks, observed floor/positive order and UNKNOWN expiry. No historical query or market request. Outcomes remain5U reference-cost proxies from the reused observer, not execution of the proposed1U strategy. No natural denominator is claimed.

## Concrete remaining integration gates

Independent read-only review found:
- Common final entry gate: Store projection near28351 -> PreentrySafety.guard; next-frame resume near28470. Existing event_reawakening family consumes unique persisted event evidence. Paused parent cannot be silently used as an active trigger.
- Existing Gecko starts use a generic host lock; DEX_REQUEST_HIGH_PRIORITY prioritizes Dex only. Checking idle before a Gecko call does not protect held demand arriving while that call waits at the host limiter. The prepared adapter deliberately refuses a missing guard. A shared Gecko start-priority integration and regression test remain required before runtime wiring.
- SafetyChecker._enrich_honeypot queries token address/chain, retains raw simulationSuccess/result, but no current standardized exact-original-pool positive simulation receipt. Positive simulation needs exact pool binding and clocks before the synthetic arm can buy; absence is not hard-unsellable proof.
- Solana capital_context already validates complete amountful raw flow/conversion/provenance. Its aggregate output does not supply all per-wallet both-side/concentration/regularity rows needed here. Reuse a verified complete upstream amountful adapter; do not fabricate trade rows or launch extra Solana queries. That adapter remains pending.
- Rare-signal admission, idle worker, persistent newly inserted receipt ID and snapshot/flush callback wiring remain pending. MicrostructureShadow is a prepared component, not an installed observer. No runtime latency trial has occurred.

Next stage must install shared start arbitration, attach bounded rare candidate receipts/worker and existing passive callbacks, then test natural request/held guards. Append organic5U/max2 and synthetic1U/max1 policies only at real deployment frontier when their respective causal gates are usable. Organic mechanical exits can precede optional principal/narrative overlays; synthetic15m/no averaging/no reentry/no Agent remains isolated. Do not call unregistered policy specifications funded implementation. No Pump100/dedup102 work repeated.

## Validation and evidence

11 targeted pytest cases passed: organic/synthetic direction; truncated300; future receipts; pool mismatch; duplicate events; post-cutoff exclusion; strict-next/positive exact-pool simulation; concurrent cache; global budget; shared429; missing held guard causes zero calls; UNKNOWN/HARD passive expiry and dedup. All provider calls mocked. No production requests, deployment, account registration, history/funding/Live changes. Natural receipts/BUY/outcomes=0 from this code because runtime wiring is not installed.

Official API sources read for design, not live market evidence:
- https://apiguide.geckoterminal.com/changelogs — latest300 trades/past24h endpoint contract.
- https://docs.coingecko.com/reference/pool-trades-contract-address — exact from/to token, sender, USD and timestamp response fields. This CoinGecko page is field documentation, not authorization for a paid API dependency.
- https://docs.coingecko.com/docs/keyless-public-api — keyless pool-trades surface.

No funded profit or resource improvement claim. Prepared code is not deployed acceptance; higher-priority trading runtime work still precedes deferred ModeChat118.
