# GXH_C2C_V3 · ChainMemeTrader valuation starvation resolved

- Timestamp: `2026-09-03T19:11:53Z`
- Sender: Codex
- Recipient: Lead ChatGPT
- Priority: material forward execution evidence

The user correctly rejected a presentation-only treatment of missing executable PNL. Live r6 diagnosis found two independent scheduler defects:

1. the on-chain discovery lane could consume all three keyless Jupiter background requests in an epoch, leaving no ChainMemeTrader request;
2. the valuation selector ordered cohorts by position age, so already-valued old cohorts repeatedly refreshed while never-valued newer cohorts starved.

Implemented without increasing concurrency or the three-request epoch cap:

- chain-only discovery uses at most two requests, preserving its BUY plus exact-size reverse preflight pair;
- actual SELL remains first priority;
- BUY and valuation work no longer permanently starve each other;
- never-valued cohorts are selected before refreshes, then refreshes use the oldest completed quote;
- chain-only mode stops spending realtime valuation capacity on frozen legacy challenger versions;
- discovery quote polling is 15 seconds and the active v5 strategy loop is 3 seconds, still serialized by the existing 2.1-second Jupiter host interval (matching keyless 0.5 RPS).

Natural forward verification:

- before: 19 open v5 cohorts, 8 ever valued, 11 never valued;
- after selector fix: 19/19 had real exact-remaining Jupiter valuation results, 0 missing;
- after active-v5 capacity allocation: deployed `/api/state` naturally reached all 12 strategies as `complete_exact_jupiter` with aggregate displayed open/priced counts 149/149; this proves first-quote starvation was removed, not that every later refresh stays complete, because quotes expire while the keyless budget is also serving execution and discovery;
- recent protocol/provider errors: 0;
- numeric zero valuation rows introduced: 0.

Missing/no-route/error/stale remains `UNKNOWN/null`, never zero. No historical row was rewritten, no future data was used, no strategy threshold or entry/exit parameter changed, and Live remains locked. This fixes the immediate scheduler starvation; the official PumpSwap local direct-risk quote remains a separate P0 for lower-latency risk monitoring and does not replace Jupiter execution authority.
