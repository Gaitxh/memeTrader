# Cohort terminals and all-strategy readback, 2026-09-17

This is a manually triggered read-only follow-up to the bounded `[2026-09-16T18:12,18:42)Z` funnel in `MIGRATION_CONFIRM214_20260917.md`. Units remain separate: 4,967 evaluated snapshots/956 tokens, 39 cohorts/15 tokens, 16 source-filled cohorts/11 tokens and 29 projected position rows/11 tokens. The 1,813 `entry_family_has_no_policy` evaluations represent mainly existing loss-retired family arms, not 1,813 tradable winners. No liquidity/safety rule was changed to inflate trades.

## The six admitted but unfilled cohorts

All six had later **same exact-pool** frames inside the 90-second window. Cohort-keyed pre-entry evidence, which the existing bounded `scripts/diagnose_cohort_terminals203.py` classifier can read, supplies the missing attribution:

| Cohorts | Chain | Existing safety disposition | Actual terminal |
| --- | --- | --- | --- |
| 36130, 36131 | BSC, same token/pool | `CHECKED_WEAK`, sellability/control facts unresolved | `EXPIRED_SECURITY_OR_NEXT_FRAME` |
| 36140, 36143, 36146 | Robinhood, same token/pool | `CHECKED_UNKNOWN`, `allow=false` | `EXPIRED_SECURITY_OR_NEXT_FRAME` |
| 36145 | BSC | `REJECT transfer_pausable` | Explicit safety refusal |

The generic expiry string for five cohorts hides their preceding safety state if read alone. They had zero source fills, order intents and participant outcomes because `Store` checks safety **before** Paper projection, not because the collector lacked a later quote. The evidence is in the existing cohort-keyed pre-entry records; this report corrects the earlier apparent terminal gap. No retry loop, unsafe override, simulated fill or new hot-path write is warranted. This also preserves the user's cross-strategy requirement to avoid known unsellable tokens.

## Current policy inventory and first forward pairs

Manual read-only `scripts/audit_strategy_inventory204.py` at `2026-09-16T18:58:15.602032Z` produced `data/research/strategy_inventory214_full.json`: **13 historical V6 registrations, 507 current-period policy IDs, 400 distinct effective behavior hashes, 22 duplicate-hash groups**. Lifecycle at that cutoff: 86 active, 183 paused new entry, 85 failed account depleted, 81 failed forward expectancy, 61 retired duplicates, seven dominated in paired tests, four retired unreachable. Among active arms, 20 had no position and 51 had negative realized PnL. IDs and hashes are not independent profit experiments; historical registration clocks may reflect import time. The per-arm generated file retains the complete version/account/position index without putting a heavy scan on the live path.

At a later natural readback (source snapshot frontier982570), 214 had **one open** position on cohort36174, `solana:8EoRx3DZxK8vbq8wMkY32QpBfcwnb9dUutq2ZoaTpump`, opened 18:58:29Z; 209 entered the same token earlier on cohort36173 at 18:58:23Z and was also open. These have different entry snapshots and fills, so they are a selection/entry-timing comparison, not a same-fill pair. Neither has a terminal return yet. Stage212's second position and its contemporary hold control did share cohort36170, entry snapshot981619 and source fill9016 on `solana:F5j22ghoqaCjzEAyi8EDpoTZ3mmhNFDsS47B95YE6eYa`. The 212 anchor exit closed 18:54:15Z for **-4.16306U net**, while the hold control was still open at the cutoff. Combined 212 realized was +8.4582U over two distinct positions, of which the first +12.62126U was unpaired. Open controls cannot be counted as zero-return or claimed beaten.

Remaining work: compare these positions only once their true terminal/cost and unvalued states are available; categorize the 111 user sample keys against same-period losing/non-rising controls; identify genuine feature lift and resource impact before keeping, retiring or modifying an arm. No profitability conclusion follows from this cutoff.
