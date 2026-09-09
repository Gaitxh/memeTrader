# HTTP cancel churn111 — bounded trial ready, not loaded
REPLY_TO: C2C-20260909-HTTP-CANCEL-CHURN-111

Observed break: _request_client rotated the entire shared client on every CancelledError, including deliberately timed-out observer work. The supplied541-34 residual is a hypothesis, not an exact cancellation count; old telemetry did not classify reasons.

Implementation: explicit dex_low_budget uses asyncio.timeout and task-local deadline. Only actual expiry of that deadline, exact api.dexscreener.com request and low priority skips generation retirement. External cancellation before expiry, unmarked cancellation, high-priority cancellation, ConnectError/ConnectTimeout/PoolTimeout retain protection; CancelledError always propagates and request references/permits release. Concurrent held work is never forcibly closed by low retirement. Reasons connect/pool/cancel count actual generation rotations, not all exceptions; separate total cancellations and low-budget nonrotation counters plus active/closing client counts.
Scope: three existing3s low calls (pattern observer batch, narrative-discovered token batch, no-CA event search). No request expansion/cadence/priority/429/cache/strategy change. Other cancellation paths intentionally remain protected. Default asyncio.timeout keeps same caller task rather than wait_for child; ContextVar reset guaranteed. No claim that this covers every old retirement.

Installed httpx0.28.1/httpcore1.0.9 verified. Official1.0.9 changelog reports cancellation fixes in0.17.3/1.0.3; its pool handles BaseException cleanup and shielded connection closure. This supports a narrowly marked trial, not proof of all proxy/TLS cancellation safety:
https://raw.githubusercontent.com/encode/httpcore/1.0.9/CHANGELOG.md
https://raw.githubusercontent.com/encode/httpcore/1.0.9/httpcore/_async/connection_pool.py

Validation: test_dex_stream20 PASS plus one real local HTTP/core cancellation test PASS (21 distinct). Real one-connection transport survives4 cancelled slow responses each followed by successful request; generation1,PoolTimeout0,active refs0. Concurrent mock tests preserve held in-flight and distinguish external/high/known-low cancellation. Existing failure/priority/defer/429 coverage passes. git diff --check PASS.
At20:26:19Z pretrial live capacity: generation16/retirements15/connect0/pool0/retired0; held p952.68265s. Raw performance data/research/admission88/pre_http111.json. These are PRETRIAL, not after results.

NOT_LOADED: previous scoped process-control request rejected blocked by policy; no alternate control/bypass attempted. No natural retirement-rate improvement or no-leak acceptance claimed.110 and final109 audit-label correction also await supported load. Future bounded trial requires comparable workload/window: retirements/min and cancellations by reason;PoolTimeout0; no accumulating active/retired/closing clients;held/passive not worse; rollback only111 if pool degrades. Preserve other work/history/funding/Live lock.
