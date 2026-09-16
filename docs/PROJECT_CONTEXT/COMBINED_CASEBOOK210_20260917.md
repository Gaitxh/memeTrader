# Combined user-sample casebook, 2026-09-17

## Scope and evidence

The original Appendix A remains unchanged (125 ordered lines, 94 distinct literal keys). The later list is separately preserved in `memory/USER_ADDITIONAL_SAMPLES_20260917.txt` (56 lines, 42 distinct keys). Seventeen distinct keys are new, yielding **111 unique research keys**; repetitions retain their original order in the two source files. They are retrospective user-selected hot-page leads, not proven winners, profitable fills or entry allow-list members.

The existing bounded read-only `scripts/audit_goal_cases156.py` now accepts both `--addresses-file` arguments, searches configured Solana/BSC/Base/Robinhood token IDs rather than omitting Base, and uses one SQLite read transaction. Run: `--addresses-file memory/USER_EXECUTION_REQUEST_20260916.md --addresses-file memory/USER_ADDITIONAL_SAMPLES_20260917.txt --output-dir data/research/goal_cases210 --seconds 90`. Result: `data/research/goal_cases210/cases_20260916T182138Z.json` and `.md`, **111/111 processed**, 80 with a local canonical token match, 31 without one, zero query errors or truncated per-token histories. This audit does not call external APIs, modify trades or use later prices in decisions.

For each local match the frozen report includes the provider/source exposure and round, locally recorded launch fact when available, provider-reported pair creation separately from local receipt, first valid pool quote, evaluation reasons, admitted opportunities and projected positions/exits where recorded. An absent local token is an evidence gap, not proof that the address never existed or was safe/unsafe. Current provider search results for 22 older absent keys were obtained later and cannot be placed on the historical decision clock.

## New-key triage (17 distinct)

| Group | Keys | Current evidence and next causal question |
| --- | ---: | --- |
| Local Paper positions recorded | 3 | `JBToL6…` has four strategy-position rows, `0x78e35…` one, `0x5078…` nine. These are strategy projections, not 14 independent token wins; inspect source BUY, costs, exit and first-quote timing before judging capture. |
| Admitted but no position | 1 | `0xe4bc08…` has two cohorts/eight arm admissions but no position. Its first evaluation rejected a below-floor pool; later admission's precise safety/next-quote/cash terminal still needs cohort inspection. |
| Evaluated, no recorded admission | 5 | `7GPG…`, `0xeaa766…`, `3DHT…`, `933HL…`, `8Min…`. The JSON records each evaluation reason; compare against ordinary failed tokens before changing any global filter. |
| Discovered, no market snapshot | 1 | `CvFCL…` has 32 stored native-launch identity exposures, first at 2026-09-16 16:11:17Z, but no snapshot or strategy evaluation. Check actual quote attempts/source coverage and whether a tradable pool existed; absence of quote is not a missed executable trade by itself. |
| Not in configured-chain local token IDs | 7 | `0xe6a247…`, `0xa163d…`, `0xbe0cad…`, `0x7f229…`, `0x2740fa…`, `0xec5b95…`, `0x3ba500…`. Chain/pair and historical visibility remain unverified; do not infer from address shape or add them to a watchlist. |

`0xe4bc08…` is an important example of distinct denominators: two admitted **cohorts**, eight **arm admissions**, zero **positions**. Its first local exposure was a Gecko new-pool round at 08:04:58.351Z; the first stored same-pool quote was recorded about the same time but had insufficient liquidity in the first evaluation. Neither the provider-reported pool birth at 08:03:32Z nor the user's later hot-page selection proves an executable early buy. `CvFCL…` is the opposite problem: discovery evidence without any stored market quote. These cases point to different next investigations, not a blanket lowering of the 1000U original-pool floor.

## Still open

The frozen casebook establishes local evidence and honest unknowns; it does not provide historical quotes the system never collected. The 80 matches require grouped early/old-reawakening path analysis, source BUY and exit attribution, and matched ordinary/failed controls. The 31 absent keys need chain/pool verification under a bounded present-identity process, then a separate determination of historical local visibility. Feature selection must use only records available by each decision; the case list and post hoc hot rank may be used only for evaluation.
