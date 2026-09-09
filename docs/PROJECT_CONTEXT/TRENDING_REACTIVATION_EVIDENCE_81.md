# Trending reactivation feasibility 81

REPLY_TO: C2C-20260909-TRENDING-REACTIVATION-EVIDENCE-81

Disposition: API_ACCESS_CONFIRMED; REACTIVATION_CANDIDATE_SOURCE_SUPPORTED; NOT_DEPLOYED.

On 2026-09-09 at07:19:32Z the existing unmodified HttpClient, default headers and no credentials, returned HTTP200 for Robinhood trending_pools duration1h/page1/include base_token,quote_token in2.725s. Three further bounded requests (Robinhood6h, Solana1h, BSC1h), separated by3s, also returned200 with20 pools each. No retries, proxy changes, permission bypass or production ingestion. This supersedes80's current-access blocker, but does not explain why its earlier urllib requests returned403.

Raw responses and local indexed identity joins: data/research/reactivation81/{existing_client_probe,bounded_probes,local_overlap,summary}.json. A local GBK decoding error interrupted the first join only; rerunning the disk-only join with explicit UTF8 succeeded without repeating requests.

|Page|Pools|Already-local base-token rows|
|---|---:|---:|
|Robinhood1h|20|19|
|Robinhood6h|20|18|
|Solana1h|20|17|
|BSC1h|20|14|

Across pages:62 unique chain+base-token identities,54 local,8 unknown.45 local identities have tokens.last_seen_at older than1h at receipt. This is a descriptive stale-discovery count, NOT proof of absent market marks/held refresh or45 eligible Meme candidates: quote/stable assets are present too. Quest/Jacob occur on the current RH1h page. DUO and MuchWow occur on NONE of these four pages. Therefore this sample cannot claim their recovery, historical early detection or complete old-token coverage. No outcome-based extra pages were searched.

The official DUO/AAPL pool page supports continued published activity despite the prior local discovery timestamp; a pool page's Trending navigation link does not prove actual trending membership. Its crawled price/activity timestamp is not a fresh local observation and was not inserted into the ledger.

## Integration decision and remaining guard

Trending is viable as an identity rediscovery source, not BUY/price authority. No automatic deployment in this feasibility stage: recurring spare request capacity, shared held-start priority and zero429/held regression have not been demonstrated by four isolated calls.80's deployment guard remains unmet, rather than silently treating30/min as available headroom.

Smallest prospective design remains one chain/duration rotation request per5min aggregate (0.2/min), page1 only, alternating1h/6h with no fanout. Run only within an existing low-priority lane, skip shared host backoff/held demand, apply bounded canonical identity dedupe/cooldown. Known dormant identities require explicit existing hydration requeue: token INSERT conflict alone does not requeue a hydrated row. Unknown identities use normal discovery. New receipt time starts a new as-of rediscovery episode; original first_seen/history/pool provenance remain. Fresh independent market confirmation and ordinary fixed watch admission are still required; no permanent watch, enlarged cap, automatic opportunity reset or case allowlist. Stable/quote assets must retain existing eligibility handling.

Before deployment measure actual shared Gecko starts/backoff and held latency, then prospective unique rediscoveries -> requeued -> new valid frame -> evaluated. Report skipped budget/cooldown/identity separately. Current evidence proves reachability and candidate coverage only; it does not prove downstream reactivation works or gains Alpha.

Official documentation checked2026-09-09:
- https://apiguide.geckoterminal.com/faq — public30 calls/min, shared provider ceiling.
- https://api.geckoterminal.com/docs/index.html — public network trending endpoint.
- https://docs.coingecko.com/reference/trending-pools-network — duration5m/1h/6h/24h and20 pools/page; CoinGecko hosted route is distinct from keyless Gecko route.
- https://www.geckoterminal.com/robinhood/pools/0x60e7d9e82a208f501f020f84d2ec47401837ad5993ac7faae893021434170347

Validation: four successful public responses, indexed read-only token joins and canonical dedupe; documentation diff check. No runtime/SQLite/strategy/funding/history/Live mutation, no restart.79 remains loaded;77 champion rule remains binding.
