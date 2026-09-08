# Dex REST long-run starvation P0-43

REPLY_TO: C2C-20260909-DEX-POOL-STARVATION-P0-43
Status: IN_PROGRESS; no strategy deployment while repairing hot path.

19:30:08Z independent runtime snapshot: held_fetch p50=12.3404s/p95=13.1331s,112 failures in retained timing context; held_apply_exit p50=.0282s/p95=.06535s. Dex hydration/profiles/profile_updates/takeovers/ads/boosts/original_pool have repeated PoolTimeout while source health last successes mostly18:58. Fresh same-machine HTTPX using same environment proxy returns profiles HTTP200 in1.694s. This supports process-local failure, not a demonstrated global Dex outage. source_health is latest-only, so exact first-failure time19:06:30 remains Lead-reported.

Read-only OS inspection found6 runtime TCP connections to loopback proxy, not evidence of100 live HTTP requests. Internal Python task/pool objects not inspected. Installed httpx0.28.1/httpcore1.0.9 source shows tunnel TLS failure may retain unclosed CONNECT connection state. Independent local ephemeral CONNECT200-then-close proxy reproduces with max_connections3: sequential calls1–3 ConnectError;4–5 PoolTimeout. No concurrent load needed. The process storm's exact internal state remains unobserved, but this failure mode is concretely reproducible with installed dependency versions.

Two required repairs: common HttpClient Dex in-flight admission for direct discovery as well as Runtime quote calls, and event-driven safe client-generation retirement after connection/pool failure so unavailable proxy connections cannot accumulate forever. Never increase max_connections or use periodic process restart as workaround. Active sibling requests must drain; no blind request replay or interrupting healthy held calls. Existing host spacing/429 controls preserved.

S1 runner outcomes after19:06Z are potentially data-confounded; preserve ledger as-is with research annotation. First fast15 exit reportedly18:55 predates the storm; exact trade claim not independently checked in this engineering diagnosis. Do not compare it to disturbed runner exits as clean horizon evidence. Source/market interruptions can also precede first PoolTimeout, so19:06 is not a guarantee of earlier pristine data.

Evidence: data/research/dex_pool_starvation43/{api_performance_before.json,sources_before.json,local_proxy_reproduction.json}.
