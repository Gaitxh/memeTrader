# 119 shared microstructure — prepared Shadow stage, NOT deployed

REPLY_TO: C2C-20260910-DUAL-MICROSTRUCTURE-ROUTER-119
Status: CORE_TESTED / RUNTIME_INTEGRATION_PENDING. This is not completion of both requested Paper branches.

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
