# Round 120-2 record — root cause of the outage, the cap moved to the real fan-out site, and a look-ahead audit

Epoch `chain-meme-trader/funding-20260906-v002-final-1000`. Deploy boundary **20:11:15Z**.
Round-1 record: `ROUND120_RECORD.md`. Evidence scripts: `data/research/diag_round120/`.

The user restated the governing constraints for this phase: **forward simulation only — no
future functions, no future-data leakage** — and that the phase's purpose is to design and
implement a usable strategy set.

---

## 1. Root cause of the 39-minute market-data outage (fixed)

Round 1 established that the DexScreener REST lane wedged at `19:24:40Z`, stayed dead for 39
minutes, and was cleared only by a process restart. Workstream A then found the traceback in
`data/logs/periodic-tracebacks/chain_meme_pattern_observer.txt` @ `19:25:18Z`:

```
collectors.py:1513  await asyncio.wait_for(condition.wait(), timeout=wait)
collectors.py:1518  condition.notify_all()
RuntimeError: cannot notify on un-acquired lock
collectors.py:1496  async with condition
RuntimeError: Lock is not acquired.
```

`asyncio.wait_for` **cancels** the inner `condition.wait()` when it times out, which can leave
the `asyncio.Condition`'s lock released. The `finally` then cannot `notify_all()`, the
enclosing `async with` cannot exit, and the Condition is **permanently unusable** — so every
later reservation in that process fails and the lane never recovers on its own.

### Fix
Both per-host start gates now **pace outside the condition** and never cancel `wait()`:

* `collectors.py` `_reserve_dex_request_start`
* `collectors.py` `_reserve_gecko_request_start` — the same latent defect, and GeckoTerminal
  is the *only* remaining provider when DexScreener is down, so fixing only one would have
  left the fallback able to wedge the last source of market frames.

The original intent is preserved: the ticket is removed and `notify_all()` is called while the
lock is still held, the priority/cooldown re-check happens on re-entry, and a newly arrived
high-priority start can still take the turn during the bounded `asyncio.sleep`.

### Additional bounded waits (same incident chain)
* `runtime.py` `_dex_quote_slot`: `await self._dex_quote_lock.acquire()` had **no timeout**. An
  unbounded `acquire()` is what turns one stuck holder into an invisible permanent outage — the
  waiter never returns, so no deadline, retry or health check ever runs. Now an 8-second
  deadline, after which the caller **defers** (the existing `False` contract) instead of
  hanging.
* `runtime.py` `_dex_batch_quote`: the **low-priority** branch had no wall-clock bound (only the
  high-priority held path had 3.5 s). Now 20 s (`dex_low_priority_request_deadline`), converted
  into the existing `None` = "deferred, no HTTP result claimed" contract. A low-priority batch
  is always safe to defer.

### Verification
`tests/test_dex_start_gate.py` — 7 tests: the hazard is reproduced, both gates survive repeated
forced pacing, 5 concurrent waiters × 4 paced reservations complete and leave the Condition
usable, and a **static guard** asserts no module ever wraps `condition.wait()` in `wait_for`
again. Plus `tests/test_pool_concentration.py` (12) and `tests/test_dust_read_guard.py` (7) →
**26 passed**; together with `tests/test_alpha149.py` → **74 passed**.

Post-deploy (20:11:15Z → 20:13:57Z): 227 raw `dexscreener` frames and 234 observer frames,
**152 discovery rounds completed**, 1 interrupted (the deploy itself), 5 running. No stall.

## 2. The concentration cap was on the wrong path (found and fixed)

Round 1 wired the cap into `settle_chain_meme_trader_execution_result`. Post-restart
verification showed it had **not** fired: 35 new positions appeared with
`source_entry_fill_id = 54` but `entry_fill_id = NULL`, so they came from a different site.

The real fan-out is the **projection loop** (`store.py` ~28944): one cohort plus one entry fill
become **one position per admitted arm** in a single transaction. That is how a single decision
became 35–42 simultaneous positions. The cap is now enforced there.

Two hazards were found and avoided while wiring it:

* **CHECK constraint.** `chain_meme_trader_entry_participant_outcomes.outcome` is constrained to
  `('projected','skipped_cash_unavailable_at_fill')`. Writing the refusal reason there would
  have raised `IntegrityError` **inside the entry transaction** and broken the entry loop. The
  refusal therefore writes no row.
* **Nested transaction.** `set_kv` wraps `with self.db:`, which would have **committed the
  projection transaction early** from inside the loop and could have persisted a half-projected
  cohort. The refusal counter is now in-memory only; the gate's effect is measured directly
  instead (arms per pool must respect the cap).

### Verified effect (deploy boundary 20:11:15Z)
| | before | after |
|---|---|---|
| arms fanned out per cohort | 35–42 | **0–4** |
| worst single-token burst | 40 positions in one second | 4 |

Five positions opened post-deploy across two tokens, max 4 arms on one. The pre-existing 40-arm
position on `solana:JQWYyzQ9…` is **historical exposure and was deliberately left alone** — the
cap governs new admissions only and never retroactively closes a position.

## 3. Look-ahead / future-data audit

`r2_lookahead_audit2.py`. A regex sweep over every SQL read proved too noisy to be evidence
(3,000+ matches including UI and research reads), so the audit is built from checks that can
actually **falsify** a no-leakage claim.

| check | result |
|---|---|
| A. evaluations consuming a snapshot observed/ingested/recorded **after** the decision | **0 / 14,040** |
| B. rows whose `signal_at` or `snapshot_observed_at` is after their own `decision_at` | **0 / 4,468** |
| C. cohort before its positions · fill before its position · close before open · mark before position | **0 / 0 / 0 / 0** |
| D. running high above entry with no observed in-window mark to justify it | **0** |
| D. running high > 100× entry | **0** |
| E. spot-check: `highest_signal_price_usd` vs the peak of the position's own mark window | equal in 8/8 |

**One audit predicate was initially wrong and is worth recording.** It first flagged 12 closed
positions whose running high no observed mark reaches. Investigation showed every one has
`high == entry_signal_price` while all in-window marks are *lower*: the running high is
**seeded with the entry price at open**, which is correct point-in-time behaviour. The predicate
now only demands justification for a high **strictly above** entry. **This was a false positive,
not leakage.**

### ⚠️ Explicit in-sample warning (future-data discipline)
The exit counterfactual (`exit_sweep.py`, `profit_counterfactual.py`) **is causal**: marks are
read in ascending `observed_at` order, filtered to strictly after each position's own open, and
the replay returns at the **first** triggering mark, so no later mark can decide an earlier
exit. **But the parameter choice is in-sample.** The sweep picked its best tier/stop
combination by scoring every candidate on the same 87-minute window it was measured on.

Therefore the "+2,578 USD from banking at +20%" figure is a **hypothesis for a forward-tested
new arm, not a validated setting**, and must not be promoted to live parameters on this
evidence. Any new exit arm has to be enrolled at its own deployment frontier and judged on
forward data only.

## 4. Next round (unchanged priorities, still evidence-backed)

| # | action | why |
|---|---|---|
| P0-2 | **New exit-carrier arms** with reachable tiers (+15~20% first tier) and a wide stop, enrolled as NEW arms | the ladder is unreachable by construction; zero profits were ever banked |
| P0-4 | **Owner decision:** the 126 paused base arms / the funding-activation registration | the v6 enrollment lane admits nothing structural |
| P1-1 | Index `(definition_version, evaluated_at, id)`; stop writing 67 KB of JSON for observation-only rows | 30–358 ms → ms; ~235 MB and ~50% of write pressure |
| P1-2 | Self-review loop with the causal replay, scored **out of sample** | turns the next parameter choice into evidence |

## 5. Limits

* The DexScreener failure *mode* was inferred from a traceback, not from live stacks;
  `token_discovery_quote_attempts` and `source_poll_attempts` are both 0 rows.
* `tests/test_cohort_store.py` fails, but it **already fails at pristine HEAD** — verified in a
  separate `git worktree` of commit `74ea78e`, so it is pre-existing and not caused by this
  round. (`runtime.py:7763` assumes `get_kv` never returns `None`; a kv value of JSON `null`
  breaks it.)
* `src/memetrader/store.py`, `runtime.py` and `collectors.py` each also carry pre-existing
  uncommitted changes from earlier rounds. Only this round's record is staged.
