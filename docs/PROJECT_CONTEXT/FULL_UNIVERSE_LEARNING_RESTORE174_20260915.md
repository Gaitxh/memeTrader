# Full-universe learning restore 174 - 2026-09-15

## Diagnosis

The active ChainMeme-only runtime had recorded 113,142 strictly-forward token
universe cohorts since the current registration frontier, but both
`token_universe_forward_baselines` and `token_universe_forward_outcomes`
contained zero rows. Consequently the downstream missed-opportunity audits and
no-decision attribution tables were also empty. This is not an inference from
missing API data: cohort capture was advancing while its finalizer was absent
from the ChainMeme-only task list.

The separate `chain_meme_universe_outcomes` loop only follows enrolled strategy
cohorts. It cannot measure the tokens stopped before a cohort or Paper position,
including `entry_family_has_no_policy` and entry-family filter refusals. This
breaks the requested rejected-candidate review loop and prevents evidence-based
decisions about whether a retired entry family should return in a revised form.

## Change

The existing 30-second `chain_universe_outcomes` loop now advances a bounded
slice of the complete token universe as well as admitted strategy outcomes. It
does not add another scheduler or external automation.

- `finalize_token_universe_forward_outcomes()` accepts an optional cohort limit;
  legacy callers retain the unbounded default behavior.
- ChainMeme-only processes at most 16 incomplete cohorts before and after its
  local finalizer slice. It makes no additional universe checkpoint request.
- The generic quote path remains available to legacy callers, but the
  ChainMeme-only call consumes neither Dex nor on-chain-only quote capacity.
- Existing incremental quality, fixed-cost execution, missed-opportunity and
  no-decision attribution finalizers run after the bounded outcome slice. They
  use stored data and add no market request.
- Existing cohort, observation and outcome clocks remain unchanged. Outcomes
  are research-only (`decision_eligible=false`, `affects=none`) and never
  retroactively create a trade or strategy decision.

The bounded selection query returned 64 rows from the live 113k backlog in
6.6ms using the cohort due index and the unique outcome `(cohort_id, horizon)`
index. The first 64 cohort tokens referenced 1,603 stored market frames, with a
maximum of 997 for one token; this is the initial deployment load boundary.

## Validation and forward guard

Seven focused tests passed. They cover the one-cohort finalizer limit, bounded
ChainMeme-only wiring, default followup compatibility, batching, provider errors
and both BSC/Robinhood safety enrichment on a universe quote.

Deployment acceptance requires all of the following:

- baseline and outcome rows start advancing from zero without rewriting any
  cohort, decision or trade;
- the active funding period and Paper/live lock remain unchanged;
- `chain_universe_outcomes` duration remains bounded and held fetch/apply-exit
  latency does not materially regress;
- the ChainMeme-only learning pass creates zero additional market requests;

The 113k backlog will drain gradually. An initial nonzero count proves the loop
is restored, not that outcome coverage or profitability is mature.

The first deployed 64/16 budget proved the complete chain (1,024 baselines,
3,072 outcomes and quality/audit rows, including 21 potential-miss no-decision
attributions), but it was too expensive: loop duration reached 16-21 seconds
and held-fetch p95 reached about 9 seconds with 7/21 failures. The retained
32/4 reduced loop duration to about 4.38 seconds, but held-fetch p95 remained
about 6.12 seconds versus the prior 4.7-4.9 second range. A 32/1 trial still had
held-fetch p95 around 6.75 seconds and a 6.94-second outcome pass. The retained
budget is therefore 16/0: local stored-observation finalization only. Those first
rows and their explicit quote attempts remain truthful append-only research
history.

## Final deployment receipt

The retained 16/0 code started at `2026-09-15T14:13:28.736314Z`, PID 77956,
under the unchanged Paper supervisor and funding version. Loaded `runtime.py`
and `store.py` hashes matched the working tree; `/health` returned HTTP 200 and
the live lock remained unchanged.

After four natural result-loop calls:

- 2,112 baseline rows and 6,336 outcome rows existed, all append-only;
- all 6,336 outcomes had quality and missed-opportunity audit rows;
- 58 potential-miss rows had a no-decision attribution;
- no `universe_*` quote attempt was made after the final deployment;
- `chain_universe_outcomes` had zero failures and about 2.03 seconds observed
  duration;
- held fetch p95 was about 3.94 seconds, while held apply-exit p95 was 0.125
  seconds with zero failures.

This final budget restores the learning data path without the held-path
regression seen in the two rejected deployment budgets. Long-run outcome
coverage and profitability remain forward evidence questions.
