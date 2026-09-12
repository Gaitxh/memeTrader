# ROUND 89 — Reserved mover admission implemented: reach went from 1 to 15 densely observed flagged tokens

Date: 2026-09-12 (local) / 2026-09-12T17:44Z reload
Source changes: `runtime.py` (`MOVER_RESERVED_SLOTS = 8`, `mover_reserved_admit`, one admission
branch), `tests/test_mover_reserved_slots.py` (6 tests).

## 1. What was implemented

Per the user's 25% decision and the round-88 spec:

- `MOVER_RESERVED_SLOTS = 8` - 8 of the pattern watch's 30 slots.
- `mover_reserved_admit(watch, token_id, registry)` - pure, testable: true only when the token is
  in the mover registry's active set **and** the watch already holds fewer than 8 of them.
- The `skip_bucket_full` branch in the pattern-watch admission loop now asks that function first: a
  flagged token may exceed its per-`(chain,bucket)` cap while the reservation is not full, and is
  admitted with reason `admit_mover_reserved`.
- Not done: the per-chain cap still applies (only the bucket cap is bypassed, so the reservation
  stays a global ceiling of 8), no held or `strong_protected` slot is ever displaced, and the
  existing replacement/borrow/reclaim rules are untouched.

Regression check: `tests/test_runtime.py` has 78 pre-existing failures in this environment and the
failure set is **byte-identical** with and without this change.

## 2. Measured effect

Nine minutes after the reload, against the round-87 window that motivated the change:

| quantity | round 87 (23 min) | round 89 (9 min) |
| --- | --- | --- |
| flagged tokens reaching >=10 observations | **1** | **15** |
| flagged tokens reaching >=25 observations | - | 8 |
| top observation counts | 60 (from the earlier era) | 262, 254, 214, 114, 42, 30, 29, 28, 23, 21, 21, 19 |
| added acquisition volume | +13.7% | **+16.0%** |

Reach is fixed: the mechanism now delivers dense observation to its own target tokens instead of
only to tokens that happened to already hold a slot.

## 3. Two honest qualifications

1. **The +16.0% figure is confounded and should not be read as the reservation's cost.** The top
   four counts (262, 254, 214, 114) are far above the 30-frame target and are almost certainly hot
   or held tokens that would have been dense anyway; the 30/29/28/23/21/21/19 cluster is what the
   reservation plausibly produced. The spend measure counts every observation of a flagged token
   beyond the population median, so naturally hot flagged tokens inflate it. Separating the
   reservation's own cost needs the observation counts of tokens admitted with reason
   `admit_mover_reserved`, which is the next instrumentation step.
2. **Conversion is not yet measured for this change.** The acceptance test remains the round-80
   definition split by dense/sparse against the fixed baseline of **102 sparse ready pools, 0
   conversions** (round 87). Nine minutes is far too short.

## 4. Next iteration

1. Instrument `admit_mover_reserved` admissions and the reservation's own added volume, so the
   +13% envelope can be verified on the reserved slots rather than on all flagged tokens.
2. Re-run the conversion table once the dense-ready sample is large enough, and report the
   equal-density comparison (flagged+dense vs unflagged+dense) that round 87 could not answer -
   flagged+dense had a single pool then.
3. If the reserved slots prove genuinely dense and converting, the share can be revisited; if they
   stay at 3 observations, the admission change did not take effect where it matters and the
   placement of the branch is the next thing to check.
