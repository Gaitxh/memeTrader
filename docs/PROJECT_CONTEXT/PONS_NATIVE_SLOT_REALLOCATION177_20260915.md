# Pons native discovery slot reallocation 177 (2026-09-15)

## Diagnosis

- The native launch loop had five fixed 30-second turns: Four.meme REST, Pons V2,
  Four.meme REST, Pons V1, and Raydium LaunchLab.
- At the frozen pre-change frontier, Pons V1 had completed 1,298 rounds and returned
  zero events and zero first-local discoveries. Pons V2 had completed 1,222 rounds,
  returned 3,610 events, and produced 3,596 first-local discoveries.
- The user-supplied gold-address audit found 76 of 92 unique addresses locally, but
  provider creation to first-local discovery was still p50 2,938.5 seconds for the 73
  cases with usable provider timestamps. This makes an already productive native
  frontier more valuable than continuing a multi-day zero-yield slot.
- This is a discovery coverage/latency defect, not evidence that filters should be
  loosened. Strict identity, point-in-time safety, pool, cash, and Paper execution
  rules remain unchanged.

## Change

- Replaced only the zero-yield Pons V1 turn with the same Pons V2 observer instance.
  The five-turn loop and its 30-second start cadence are unchanged. Pons V2 therefore
  has two nominal turns per cycle (60/90-second alternating gaps, 75-second average)
  instead of one turn every 150 seconds.
- Reusing one instance is material: both slots share the indexed/RPC frontier and the
  existing five-minute provider retry frontier, so they neither replay history nor
  form an independent retry stream.
- Pons economics remains eligible only on slot index 1, exactly once per five turns.
  The second Pons V2 slot is discovery-only and cannot double economics queue work.
- No new source, host, process, schedule, account, strategy, fee, risk threshold, or
  funding period was added. Live remains disabled.

## Verification

- Focused regression: `pytest tests/test_native_observer_runtime.py
  tests/test_pons_v2_53.py -q` passed 6 tests.
- `py_compile src/memetrader/runtime.py` passed.
- The schedule regression asserts that positions 1 and 3 are the identical Pons V2
  object and that only position 1 drains economics.
- First activation PID 41140 started at 2026-09-15T14:56:13.326929Z. One Pons V2
  upstream timeout at 14:58:08Z activated the existing shared five-minute backoff;
  both slots obeyed it and did not create a retry storm.
- After recovery, Pons V2 completed rounds at 15:04:48Z and 15:05:45Z. Each returned
  four events and four first-local discoveries: 8/8 incremental discoveries in a
  57-second completed-round gap. Pons V1 completed zero post-activation rounds.
- During that bounded window, the runtime remained alive. Short-window p95 durations
  were 7.378 seconds for held fetch, 0.175 seconds for held exit application, and
  10.193 seconds for observer fetch-with-wait. These are operational observations,
  not a causal before/after latency claim because no matched-load baseline was frozen.
- The final resource-boundary helper was loaded by a second manual restart. Final
  process PID 14180 started at 2026-09-15T15:06:50Z; the loaded `runtime.py` SHA-256
  matched disk. `/health`, `/api/live`, and `/api/performance` returned 200. Funding
  stayed `chain-meme-trader/funding-20260906-v002-final-1000`; Paper was true and
  Live remained locked.
- The final process then naturally completed Pons V2 rounds at 15:07:32Z and
  15:08:30Z. The second round returned six events and all six were first-local
  discoveries. Other native slots continued in the same five-turn rotation; no
  Pons V1 round appeared. Open Paper positions moved from 19 to 17 while the runtime
  continued normal exit processing.

## Manual forward supervision

On the next user-triggered review, compare only rounds after the final activation:

1. Pons V2 completed rounds and first-local discoveries per native loop call.
2. Pons V2 timeout/error rate and five-minute backoff occupancy.
3. Held fetch and exit-application latency under a comparable open-position load.
4. New Pons identities reaching snapshot, evaluation, cohort, and Paper decisions.

Keep the change when Pons V2 adds identities without a material held/exit regression.
If the second slot repeatedly hits provider backoff with negligible marginal discovery
or harms the priority path, restore the Pons V1 slot position to a no-op/disabled slot;
do not compensate by increasing global frequency or weakening trading safety gates.
