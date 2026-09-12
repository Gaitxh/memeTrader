# Round 120-10 record — payload work quantified (−46% per row) and a loss-rate analysis that clears the 120-4 revert

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Scripts
`data/research/diag_round120/r10_*`. **No production change this round.**

Two measurements: one confirms the payload work of rounds 120-8/9 actually landed, the other
asks whether the accelerating realized loss is volume or a worse rate — and whether my own
round-120-4 cap revert caused it.

---

## 1. Payload reduction confirmed, and a caveat about the intermediate window

| window | all-reason bytes/row | `cohort_observation` bytes/row | payload/min |
|---|---|---|---|
| 18:30–20:42 (pre-120-8) | 28,916 B | **86,788 B** | 4,731 KB/min |
| 20:42–20:50 (120-8 only) | 32,545 B | **93,920 B** | 6,672 KB/min |
| **20:50–now (120-8 + 120-9)** | **16,136 B** | **46,484 B** | **3,059 KB/min** |

* `cohort_observation` per row: **86,788 → 46,484 B, −46.4%**
* all reasons per row: **28,916 → 16,136 B, −44.2%**
* payload written per minute: **−35%**

**The intermediate window got WORSE, not better** (93,920 B/row), and that is worth stating:
`feature_vector` compaction alone removed ~7.6 KB from every arm, but the rows written in those
eight minutes carried more arms than the historical average, so the per-row figure rose. The
saving only becomes visible once the arm-count-independent metric is used AND both reductions are
in. This is the third time in this session that a per-row average over a shifting arm-count
population has misled — it is now recorded as a standing trap for this table.

**The file still grows ~7.3 MB/min (~440 MB/hour) at 1,092 MB.** Evaluations now account for only
~3.1 MB/min of that, i.e. **~42%, down from the ~63% share measured in round 120-7.** The next
contributor has not been identified and is the obvious follow-up: the payload work fixed the
largest single object, not the growth.

## 2. Is the accelerating loss volume or rate — and did the cap revert cause it?

Realized total moved −4,704 → −5,670 → −6,632 over ~17 minutes, which needed explaining. Per
settled position, split at the three control epochs:

| epoch | settled | write-off % | **PnL per settled position** |
|---|---|---|---|
| before 20:11:15 (no cap) | 367 | 46.0% | −10.417 |
| **cap ENFORCED 20:11:15–20:29:46** | 78 | 23.1% | **−7.753** |
| cap OFF 20:29:46–now | 198 | **18.2%** | −11.331 |

**It is volume, not a worse rate.** Positions opened per 5-minute bucket went from 35–47 to
**237** in the 20:30–20:34 bucket, immediately after the revert. The cap-enforced window does show
the best per-settled figure (−7.753) — but it is **18 minutes and 78 settled positions**, and its
write-off count is confounded by when the rug pulls happened to land, so it is not evidence that
the cap helps.

**My round-120-4 revert to the user's chosen state is therefore NOT contradicted by the data**:
the epoch after it has the *lowest* write-off rate (18.2%) of the three. Recorded because the
opposite conclusion was available from the same table by reading only the per-settled column.

## 3. What the loss analysis did surface

* **Write-offs remain 100% BSC**: 8 tokens, and the two newest (`bsc:0xc80e36a2…` 25 positions at
  20:43, `bsc:0xd69c4032…` 16 at 20:40) are both post-revert. The chain split from round 120-5
  holds and extends.
* **Non-write-off positions are still deeply negative**: in the cap-OFF epoch, 198 settled with
  36 write-offs → 162 ordinary closes carrying −1,523.5U, i.e. **−9.40U on a 20U stake (−47%)**.
  That is far beyond the 8.33% round-trip friction, so it is adverse entry selection, not cost.
  This is the same conclusion the cross-session synthesis reached from the old device's much
  larger sample (friction 58% of the loss, only 37.2% of positions clear `entry × 1.0833`) — here
  the ordinary-position loss is larger than friction alone can explain.
* **Open exposure is concentrated again**: **215 positions, 4,300U stake, on only 5 tokens (98
  arms)** — ~43 positions per token. With the cap off this is the expected structural state, and
  it is the condition under which one more BSC death costs ~860U rather than ~160U. Noted, not
  acted on.

## 4. Priority list after this round

| # | action | state |
|---|---|---|
| **P0-1** | Identify the next-largest contributor to the remaining ~4.2 MB/min of non-evaluation growth | measurement |
| **P0-2** | Supply-weighted observation caps — designed, needs a discovery-share signal through four live enforcement sites | ready |
| **P0-3** | EXIT150 forward samples via `paired_arm_ab.py` at ≥20 settled per side (33 positions so far) | live |
| P1-1 | Drop the derivable duplicate between `decision_key` and `episode_id` (~10% of the residual per arm) | priced |
| P1-2 | Standing loop: `supervise_metrics.py` + `trade_context_ledger.py`, by independent cohort | in use |

## 5. Method note

Round 120-9 recorded a **false negative** (an unrepresentative 40-row sample said a working fix
did nothing). This round found the same class again in the intermediate window — per-row
averages over shifting arm counts. Two of the last three measurement errors were the metric, not
the system. **For any payload or rate claim in this project, use a per-unit metric (bytes per
arm, PnL per settled position, positions per bucket) and state the sample sizes next to it.**
