# Dex REST long-run starvation P0-43

REPLY_TO: C2C-20260909-DEX-POOL-STARVATION-P0-43
Status: DEPLOYED_SHORT_WINDOW_PASS; LONG_RUN_ACCEPTANCE_PENDING.

19:30:08Z independent runtime snapshot: held_fetch p50=12.3404s/p95=13.1331s,112 failures in retained timing context; held_apply_exit p50=.0282s/p95=.06535s. Dex hydration/profiles/profile_updates/takeovers/ads/boosts/original_pool have repeated PoolTimeout while source health last successes mostly18:58. Fresh same-machine HTTPX using same environment proxy returns profiles HTTP200 in1.694s. This supports process-local failure, not a demonstrated global Dex outage. source_health is latest-only, so exact first-failure time19:06:30 remains Lead-reported.

Read-only OS inspection found6 runtime TCP connections to loopback proxy, not evidence of100 live HTTP requests. Internal Python task/pool objects not inspected. Installed httpx0.28.1/httpcore1.0.9 source shows tunnel TLS failure may retain unclosed CONNECT connection state. Independent local ephemeral CONNECT200-then-close proxy reproduces with max_connections3: sequential calls1–3 ConnectError;4–5 PoolTimeout. No concurrent load needed. The process storm's exact internal state remains unobserved, but this failure mode is concretely reproducible with installed dependency versions.

Two required repairs: common HttpClient Dex in-flight admission for direct discovery as well as Runtime quote calls, and event-driven safe client-generation retirement after connection/pool failure so unavailable proxy connections cannot accumulate forever. Never increase max_connections or use periodic process restart as workaround. Active sibling requests must drain; no blind request replay or interrupting healthy held calls. Existing host spacing/429 controls preserved.

S1 runner outcomes after19:06Z are potentially data-confounded; preserve ledger as-is with research annotation. First fast15 exit reportedly18:55 predates the storm; exact trade claim not independently checked in this engineering diagnosis. Do not compare it to disturbed runner exits as clean horizon evidence. Source/market interruptions can also precede first PoolTimeout, so19:06 is not a guarantee of earlier pristine data.

Evidence: data/research/dex_pool_starvation43/{api_performance_before.json,sources_before.json,local_proxy_reproduction.json}.

## Implementation and acceptance
Code142615d pushed. Shared Dex8 total/5 low admission, bounded0.25s low wait with distinct defer error; actual host pacing inside admission. Failed/cancelled client generations drain healthy siblings before close; no automatic replay or increased connection limits. Existing10s telemetry exposes capacity and recovery.

17 tests/test_dex_stream tests PASS plus3 existing runtime reservation/fresh-quote cases PASS; runtime compilation and diff check PASS. Single Paper code-load restart19:39:54Z, supervisor4196/runtime36148. Health/live endpoints respond; Live=false. Four immutable registration/activation/policy hashes match. No strategy/account reset.

At19:41:58Z (~2min): held p50=.749s/p95=1.903s,0 failures; apply p95=.0358s; pattern p95=4.90s/15s cadence; passive drops0; PoolTimeout0; generation retirements2 and pending retired0; low deferrals2. No connect error count, so natural retirements exercised cancellation path, not TLS failure. Discovery profiles/ads/boosts/hydration advance. Original_pool last_ok advances but last_item remains old: HTTP success does not guarantee valid fresh original-pool price. Two discovery calls deferred under load. No new latest Dex429 observed in bounded source snapshot; not a full request-rate audit.

Evidence: performance_after.json, sources_after.json, immutable_before/after.json under data/research/dex_pool_starvation43. Earlier false hash comparison used ensure_ascii=False against original default JSON; corrected identical serialization yields all4 matches.

Prior29min horizon NOT crossed. Restart alone also refreshes pools; short recovery cannot isolate long-run causal effect. Deterministic regression proves mechanism; natural long-run acceptance remains pending. Next read-only acceptance after20:10Z without restart: PoolTimeout, generation drainage, held/SELL latency, source progress,429, low deferrals and drops. Do not permanently close P0 or use disturbed S1 outcomes as clean evidence.
