# Round 120-16 record — first systematic parameter-variant comparison; one clean verdict, one fragile one about my own EXIT150

Date 2026-09-13. Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Tool used:
`scripts/paired_arm_ab.py` (pre-existing, purpose-built, read-only). **No production change.**

The user's strategy requirement §1 is explicit: **"对仅参数差异的策略，进行横向对比与择优，保留表现更优者，其余退出或合并"**
— compare parameter-only variants, keep the better one, retire or merge the rest. The project
already has the correct tool for this and it had not been run this session. It exists because, in
the tool's own words, *"the project has repeatedly drawn wrong conclusions from unpaired arm
comparisons"*: it matches on **within-cohort** differences (both arms riding the same frozen
opportunity) and resamples by **token**, because one token can carry dozens of arms.

---

## 1. Results

| A vs B | settled A/B | paired cohorts | mean diff (A−B) | token-clustered 90% CI | drop worst token | verdict |
|---|---|---|---|---|---|---|
| **`alpha149_merged_multi_setup_v1` vs `_fast_v1`** | 7 / 13 | 7 | **−3.7778** | **[−7.4973, −0.6131]** | sign survives (−4.41) | **CI excludes zero — `_fast` is better** |
| `alpha149_survive_noise_wide_v1` vs `_confirm_v1` | 6 / 9 | 6 | −3.4952 | [−7.4406, +0.0000] | sign survives (−4.19) | direction clear, CI touches zero |
| `alpha149_deadpool_flow_v1` vs `_control_v1` | 9 / 9 | 9 | −2.8569 | [−8.1632, +2.1877] | sign survives (−4.74) | treatment worse, CI includes zero |
| `exit150_bank15_v1` vs `exit150_bank25_v1` | 6 / 6 | 6 | **+2.2583** | [−0.0856, +5.8055] | sign survives (+0.35) | below threshold, CI includes zero |
| `exit150_bank15_v1` vs `exit150_widestop_v1` | 6 / 6 | 6 | +0.2301 | [+0.0000, +0.6903] | **sign FLIPS to +0.0000** | **fragile — not a finding** |
| `alpha149_hold_any_band_v1` vs `_control_v1` | 0 / 3 | 0 | — | — | — | `NOT READY` |
| `alpha149_mid_band_flow_v1` vs `_shallow_band_flow_v1` | 8 / 1 | 0 | — | — | — | `NOT READY` |

Per-arm headline numbers the tool printed:

* `merged_multi_setup_v1`: 7 settled, **−84.30%** of stake, **0.0% win**, −118.01
* `merged_multi_setup_fast_v1`: 13 settled, **−34.07%** of stake, **23.1% win**, −88.59
* `exit150_bank15_v1`: −58.90%, 16.7% win · `bank25_v1`: −70.19% · `widestop_v1`: −60.05%
* `survive_noise_wide_v1`: −90.71%, **0.0% win** · `_confirm_v1`: −47.74%, 22.2% win

## 2. The one clean verdict

**`alpha149_merged_multi_setup_fast_v1` beats its parent `alpha149_merged_multi_setup_v1`**, with a
token-clustered 90% interval that **excludes zero** and a sign that survives dropping the single
worst token. The parent has a **0% win rate over 7 settled positions at −84.30% of stake**; the fast
variant has 23.1% over 13 at −34.07%.

**Not acted on, and the reason matters.** The project's own bar (`MIN_SETTLED_PER_SIDE = 20`) is not
met — 7 paired cohorts against 20 — and the interval is 90%, not 95%. Arms are append-only, so
"retire" means writing a `PAUSED_NEW_ENTRY` control into the KV pause list, which is the mechanism
the user's own 442-row export used to pause 237 strategies. **Pausing an arm on a 7-cohort 90%
interval would be acting below the standard this project has repeatedly insisted on.** It is
recorded as a **named candidate for the pause list when it matures**, with the exact command to
re-check it.

## 3. The fragile verdict is about my own arm

`exit150_widestop_v1`'s apparent +0.23 USD advantage over `bank15_v1` **reverses to exactly +0.0000
when the single worst token is dropped**. Combined with round 120-14 — where 30.2% of hard stops
turned out to be tokens going to approximately zero, so a wider stop cannot help them — this is now
the second independent reason to treat `widestop` as the weakest of the three EXIT150 arms.

`bank15` vs `bank25` (the designed one-variable pair) points the right way (+2.26, bank15 better,
i.e. **banking earlier**) but is not judgeable at 6 settled per side.

**Both statements are recorded because the round-120-3 record is where `widestop` was argued for,
and that argument is now twice weakened. The arm stays registered (the ledger is append-only and it
is a legitimate experiment) but nobody should read the earlier record as support.**

## 4. Why this round matters beyond its own results

1. **The tool works and is cheap.** Every row above is one command. The correct comparison is now
   demonstrably repeatable rather than a thing the project knows it should do.
2. **It closes a user requirement that had been open.** §1's "compare parameter-only variants and
   keep the better" now has seven executed comparisons, honest readiness labels, and one verdict.
3. **It is the first statistical result this session that survives a clustering correction.** All
   previous arms-level numbers were per-position averages over a ~30× fan-out, which is the error
   the tool was built to prevent.

## 5. Priority list after this round

| # | action | evidence |
|---|---|---|
| **P0-1** | Re-run these seven pairs as settled counts grow; when `merged_multi_setup_v1` reaches ≥20 paired cohorts, add it to the pause list | §1, §2 |
| **P0-2** | Entry-quality activity floor (needs ≥30 dead-group **tokens**; currently 10) | round 120-15 |
| **P0-3** | Reduce the evaluation write RATE (74% of measured DB growth) — verify the `previous_features` continuity dependency first | round 120-11 |
| P1-1 | EXIT150 to ≥20 settled per side | 6/arm |
| P1-2 | Observation-slot admission probe | round 120-12 |

## 6. Method note

Seven rounds have repeatedly found that **per-position averages over a fanned book are the wrong
metric** — that is why `paired_arm_ab.py` exists. This round used it for the first time and the
result is instructive in both directions: it **confirmed** one difference that per-arm averages had
already hinted at, and it **destroyed** another (`widestop`) that per-arm averages had appeared to
support. **The lesson is not "run the tool"; it is that the same data yields a finding and a
non-finding depending on whether the comparison is paired and token-clustered.**
