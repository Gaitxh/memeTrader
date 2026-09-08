# Corrected ACTIVE16 matching47

REPLY_TO: C2C-20260909-RIGHTTAIL-MATCH-CORRECTION-47
Status: corrected selection/path/ledger extraction complete; ECONOMIC_DISCRIMINATION_BLOCKED_BY_ENDPOINT_COVERAGE. No strategy registration, threshold search, backfill, restart or Live change.

Frozen snapshots: ID2019801 /2026-09-08T20:34:35.511126Z. All prior IDs scanned in5000-row chunks using read-only SQLite. Case originals independently agree with all14 supplied valid anchor IDs/pools;2 lack valid anchors. First VALID causal exact-pool frame, not first issuance/invalid observation. Controls same UTC date, chain and provider family (strategy-observer prefix removed), same fixed age band [0,180),[180,300),[300,900),[900,3600),[3600,21600),[21600,86400),older;0.5–2x liquidity. Controls must already be recorded by case anchor. Rank without outcomes by normalized age distance + absolute log2 liquidity ratio + time distance/86400; retain up to5 unique tokens per case. Reuse across cases is flagged, not independent replication.

13 matched cases,57 control assignments,51 distinct control tokens. CME unmatched under fixed conditions; qINU/HONTER no valid anchor. Build/500 only1 control each.46 remains pilot and is not overwritten. All57 liquidity bounds/date/chain/provider assertions passed. Actual stored pair activity fields are separately MISSING/ZERO/PRESENT; among171 selected control activity fields0 missing/23 measured zeros/148 positive. Nulls are never converted to0; zero-total buy share is undefined, not0. This audit does not prove upstream figures are accurate or wash-free.

## Strict future labels

First later valid exact-pool observation must observed>anchor.recorded; subsequent retained frames observed>previous retained recorded. Positive price,liq>=1000,valid three clocks,recorded<=anchor.recorded+6h. Entry is first strict-next frame; future must be strictly later again. Net proxy=.96*future/(1.04*entry)-1. Righttail>=100%, observed loss<=-50%, and6h end<=-50% are separate. No end frame within final5min => end UNKNOWN; unobserved events UNKNOWN. Observed righttail/crash positives do not prove executable fills, all fees, or unbiased event probability. Source change permitted only on same pool.

6 cases observed righttail positives;3 observed loss positives (7Stock,LAPTOP,GAGE), with7Stock also righttail-positive. Controls3 positive righttail assignments/10 loss assignments. **All cases and controls lack qualified6h endpoint coverage**. Thus no negative-label precision, end-profit comparison, or Alpha claim is justified. Thin/missing/other-pool rows are excluded, never turned into loss. Endpoint tolerance is frozen engineering coverage, not tuned to returns.

## Actual system attribution

Current active funding-version position ledger extracted separately from frozen snapshots. Counts are strategy positions, NOT independent tokens. Full per-arm entry/close/reason/PnL/source-fill pointers and entry-pool identities are in matched_corrected47.json. First-buy delay is relative to first valid original-pool anchor. Entry on another pool is a separate surface, not implied migration. Closed-before-observed-peak is descriptive and does not prove exit error or that holding was safe.

|Case|Controls|Positions|First BUY delay min|Entry snapshot same original pool|Closed before original observed peak|
|---|---:|---:|---:|---:|---:|
|MEME|5|0|NA|0|0|
|4Stock|5|68|21.41|33|58|
|qINU|0|0|NA|0|0|
|RSTR|5|0|NA|0|0|
|build|1|38|73.63|38|34|
|ROUTE|5|6|94.71|0|0|
|O1BOT|5|14|39.21|14|11|
|7Stock|5|32|294.57|32|0|
|PUGCOIN|5|0|NA|0|0|
|500|1|0|NA|0|0|
|CME|0|26|1.17|26|16|
|LAPTOP|5|10|7.52|10|8|
|GAGE|5|17|0.17|17|0|
|HONTER|0|0|NA|0|0|
|zDOG|5|8|64.35|8|6|
|KERF|5|0|NA|0|0|

Build38 positions all hard-stop exits; first buy73.63min late relative to anchor.7Stock32 positions first294.57min,30hardstop/2maxhold. CME26 positions first1.17min,19hardstop and other exits;16 closed before observed peak. ROUTE6 positions all different entry surface. No-buy MEME/RSTR/PUGCOIN/500/KERF does not establish a missed tradable righttail on original pool; original-path labels remain UNKNOWN. Actual reasons say what execution did, not why signal was absent: decision-gate causal attribution remains unresolved without episode-level decision readback.

## As-of discrimination change

Corrected4Stock anchor trades7 vs matched median65 (46 had7 vs1); O1BOT191 vs253. Build70 vs0 but only1 control;7Stock measured0 vs0 at anchor then822 at strict-next. This falsifies interpreting pilot activity separation as universal. Anchor and strict-next feature records are preserved per matched episode; strict-next availability differs, so comparing only survivors would bias discrimination. A later activity rise is a research direction, not permission to register rejected P2 or fit new thresholds.

Validation: synthetic clock rejection/missing-vs-zero/Solana case-preservation assertions PASS; all14 case anchors agree with prior row pointers; all57 fixed matching bounds PASS; independent review confirmed strict path and outcome-blind score. Script available at scripts/research_righttail_match47.py (--cutoff-id2019801). Initial null-clock parsing failure was fixed by excluding invalid clocks. No runtime code edited. S1 19:06–19:51:47 remains confounded; historical matches do not constitute post-fix validation. Next material requirement is endpoint/decision coverage, not relaxing match bands.
