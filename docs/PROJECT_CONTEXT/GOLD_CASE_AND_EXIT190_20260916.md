# Round 190: exact case scope, buy-only risk, and first-mark exit trial

## Exact user cases

`GOLD_CASE_ADDRESSES_20260916.txt` freezes the latest supplied sequence: 125 lines, 94 distinct addresses. It excludes the 27 older prefix entries that were not in this latest list and includes the 40 later lines absent from the previous 112-line file. Repeated addresses are preserved in the source; all funnel counts deduplicate by address. It is a retrospective audit set, never an entry allow-list.

The bounded current-period audit at `data/research/goal_cases190/cases_20260916T090250Z.{json,md}` completed 94/94 addresses: 70 matched a current canonical token, 24 did not; of the matched, 44 reached evaluation without recorded admission, 4 were admitted without position, and 22 formed Paper positions. Unmatched is not proof a token never existed on chain or in an older archived ledger. The per-token file contains first-seen and evaluation timestamps, rejection reasons, cohort decisions, security outcomes, and positions. It does not treat later popularity, later ATH, or later price as an earlier signal.

In a bounded first-1000-snapshot read for each matched token, only 9 of 70 formed a fresh, distinct, same-pool three-frame rising window within 30–90 seconds; two histories hit the sample cap. Only 3 of those 9 had 6 same-chain/same-pool-age noncase rising-window controls in the preceding 600 seconds/3000 snapshot IDs. This is too small and too selected to justify a new entry alpha. The 9 case windows also had zero complete matches to the existing friction, liquidity, volume/activity-growth and acceleration impulse contract. Relaxing that contract solely because these tokens later became popular would be leakage, not evidence of profit.

## Risk and economics

All ordinary Paper arms share the safety gate. This round adds a fresh exact-pool DexScreener buy-only wait: at least 4 buys and zero sells in the current five-minute window, with token/pool identity and `observed <= ingested <= recorded <= decision` and age <=15 seconds. It is a reversible wait, not a honeypot verdict or a basis for account reimbursement. A later fresh frame containing a sell can proceed through the existing security gate. Missing sell counts and stale frames cannot be read as zero sells; the opt-in DEX proxy is covered too. No new API call, background job, or schema was added.

Historical scale check at the current-period entry-snapshot frontier: 2,431 projected positions across 99 tokens/450 cohorts had a DexScreener entry frame with >=4 buys and zero sells. Among these replicated Paper accounts, 1,025 closed positions sum to +10,901.51U and 1,406 written-off positions to -27,831.33U. This is **not** the causal value of the new wait: arms share opportunities, account cash is independent, and a later sell might have allowed entry. It shows the rule has material opportunity cost as well as material observed risk; monitor both.

No current-period position joins the three explicitly confirmed honeypot tokens found in the safety receipts. Therefore no compensation/void was applied. If an affected source BUY is later directly proven, use the existing append-only whole-lifecycle void: remove both profit and loss from effective cash/PNL while preserving raw fills and an evidence receipt. Ordinary pool disappearance, missing security reports, and buy-only flow alone do not qualify.

## Strategy decision

The complete strategy audit from round 188 remains the baseline. The current-period `trajectory144_trend_runner_v1` has 180 distinct positioned tokens, +576.51U across independent Paper account projections; Solana 100 tokens +881.61U, BSC 73 -298.38U, Robinhood 7 -6.72U. This is chain-heterogeneous and not a guaranteed alpha. Existing second-wave, absorption-reclaim and sparse-peer hot-fast cohorts remain materially negative and are not repackaged as new entries.

One new independent Paper arm, `trajectory190_first_mark_trail_v1`, clones the existing trajectory144 runner signal and exit contract, changing only `trailing_activate_return` from the break-even-armed control's 0.0 to -1.0. Thus the existing 15% trailing rule starts on the first valid economic mark; the 20% hard stop, holding logic, position size, shared market frames and security checks remain unchanged. The observed 28/180 runner tokens whose *realized running peak* stayed between 94.12% and 100% of stake lost 191.72U across replicated arms. This outcome defines a differentiating experiment, **not** a hindsight entry rule or a claim that those losses were avoidable. Earlier trailing may wash out a future runner; retain the parent and break-even control and compare only forward same-source BUYs with costs and pool write-offs.

## Foundation and validation

The current ten-minute acquisition window recorded 114 launch facts, 87 market surfaces, 187 hydration tasks, and zero passive-queue drops. Dex discovery's observed interval was about 30 seconds despite a 15-second setting, but the measured round contributed zero new tokens, while held fetch still has the larger tail. No API/interface/concurrency increase or SQLite maintenance is justified by this sample; held and pending exits retain priority. The current database size is a capacity concern, not an observed hot-query bottleneck.

Seventy-three targeted tests passed across shared risk, DEX proxy, trajectory144, trajectory187 and the new exit arm. The new Store mark-path test seeds two accounts on one token/cohort: both remain open after the first valid negative-net mark; after a later 15% drawdown above the hard-stop level, only the first-mark arm creates a trailing exit. The new policy registers once at a new snapshot frontier and never backfills prior positions.

At 2026-09-16 09:10:31Z the restarted Paper runtime activated the new arm at snapshot 911276. Its first observed position used entry snapshot 911424, strictly after that frontier; the latest account readback showed 980U cash after its ordinary 20U buy and zero realized PNL. `/health` returned `running` with the unchanged `funding-20260906-v002-final-1000` period. Live trading remained disabled; no new funding period or historical position reset was made. This is a deployment/readback result, not a profitability result.

The first position subsequently closed at 09:12:45Z: BSC token `0xb03467d7854e6742c8c33277f6f4c1e9fd69518d`, source BUY 8863, a market-mark hard stop with realized -6.1031U. The parent runner and armed-trail control on that same source BUY also closed via the same hard stop for -6.1031U each. New-arm cash became 993.8969U. This is one paired no-difference loss, not evidence that the new trailing rule helps or harms.

The round-189 exact original-pool quote correction was also naturally exercised: after the upstream 429 cleared, the same WIF pool produced a fresh `VISIBLE` Gecko mark at about 09:00:25Z (price 0.1770463154 USD, liquidity 5127.07 USD). This proves one successful current-pool refresh, not continuous quote availability; when its 15-second evidence expires the Paper path still waits rather than borrowing a different pool.

## Manual forward review

No scheduled review or automatic deployment was added. At a user-triggered review, compare the new arm to `trajectory187_armed_runner_v1` and its shared runner parent by distinct token/source BUY, chain, full observation window, costs, risk write-offs, washout after early exit, and the result after removing the largest winner. Keep open/missing outcomes visible. Do not promote a claimed winner without a mature independent sample.
