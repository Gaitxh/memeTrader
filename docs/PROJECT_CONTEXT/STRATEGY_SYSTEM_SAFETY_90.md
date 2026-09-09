> SUPERSEDED P1-A: 90-ADDENDUM-A withdrew checkpoint sales and new enrollment.
> See CHECKPOINT_WITHDRAWAL_90A.md. Earlier deployment details below are historical.

# Message90 staged implementation — IN PROGRESS

Reply-to: C2C-20260909-STRATEGY-SYSTEM-SAFETY-90.

## P0-A common Paper entry safety

Code audit of the current14 active policies finds isolated pattern/cohort enrollment
projects BUY through `_project_chain_meme_trader_market_entry`. This did not invoke
the older event `SafetyChecker.check`; the Jupiter-only baseline pretrade gate did
not cover this market-price contract. A signal-only asynchronous safety worker now
guards that common projection. Commit c2e93f5 loaded08:53:24Z via existing Paper launcher.

Explicit GoPlus dangerous controls/honeypot flags and existing12% tax limit reject.
Honeypot simulation failure alone stays UNKNOWN rather than proving a honeypot.
Solana reuses dangerous-control assessment and explicit verified pool rejection;
missing LP-lock/custody knowledge is not a hard rejection of legitimate protocol
pools. No new global Jupiter exact-quote requirement. Robinhood supported provider
surface identity is checked, but external contract security is UNKNOWN: this is
not onchain bytecode verification or an assertion of safety.

Missing all reports waits; partial evidence without explicit danger may authorize
ordinary Paper with UNKNOWN visibly retained. PASS never means guaranteed safe.
Security acquisition uses existing source TTLs, one worker,128 pending cohorts,
256 cache entries. Successful acquisition is local availability time, not claimed
chain freshness. Failed refresh cannot renew an old report. Existing explicit
negative evidence rejects before any supplemental request.

Pending entries persist in KV and require a strictly later valid original-pool
frame after security acquisition. Original legacy intents stay ready while waiting,
and freeze their receipt only when authorized. No historical snapshot/fill rewrite.
Audit is append-only evidence keyed by cohort/status, independent of account fanout.

Validation:14 focused safety cases plus6 existing Paper execution cases PASS.
Natural cutoff08:57:55Z: one unique token/cohort/BUY, audited UNKNOWN Robinhood
boundary, security acquisition08:55:24.058582Z after signal08:55:23.458267Z;
strict later original-pool fill08:55:27.332744Z. No unaudited BUY. No natural BSC
or Solana gate sample yet; no empirical false-positive or rejection-rate claim.
Held fetch p95 3.262s pre /1.777s post; apply55.97/61.71ms, pattern9.97/6.63s.
Seven-table immutable hash unchanged b376b3e07f9f4aae836dec63a5d54a95641eca89cd221cdfd142a355ef12a2fd.
These short unequal workloads do not establish causal performance improvement.
Old admission84 audit drops remain separate and unresolved. Artifacts:
data/research/system90/safety_natural.json; admission88/safety90_{before,start,natural}.json.

## Flat selector and old-token discovery stage (deployed db442c3)

Flat projection bootstraps once from a consistent read-only snapshot, then consumes
evaluation/observer PK frontiers plus dirty market identities and current open
positions. Age/due heaps preserve6h crossings, near5s and ordinary60s; there is no
60s refill gap. Full ordered equality on production cutoff09:04:37Z:116733 candidates,
baseline2.737s, bootstrap20.829s, repeated0.422–0.564s. Startup cost is explicit.
Mixed fixture tests cover new mature eval, pair changes, invalid dates, open/close,
failure attempts, near status, and bounded stale heap entries. No production schema
or network cadence change. scripts/verify_flat_frontier90.py is a read-only check.

Existing Dex profiles/boost/community feeds only requeued `no_pair`, leaving old
previously completed hydration dormant. A bounded rediscovery episode now requeues
at most2 dormant nonheld identities/minute, after >=1h absence of token/snapshot/
hydration activity, through the existing batch queue. Existing pending work is not
reset. Episode evidence is not official event/BUY authority. No trending endpoint,
new requests/task/capacity, liquidity or strategy threshold change. Existing
reactivation strategies still require their own causal market/event confirmation.

## New age-rate exit revisions (registered prospectively)

Two5U/max4 hypotheses copy the deployed age-rate entry and parent exit contract,
using the same cohort/fill when jointly eligible; no new funded control. Checkpoint
at15m exits if current total net economic value is below initial debit OR both
price and liquidity deteriorate across causal adjacent <=60s frames. Missing
structure remains UNKNOWN and waits rather than falsely passing the checkpoint.
Otherwise parent exits continue unchanged. Dynamic recovery has no fixed+40/+80
trigger or fixed fraction: earliest strictly partial coverable sale, resized at
the next valid actual frame through current sell_terms. If no longer coverable,
cancel only recovery attempt and retain parent safety. Actual fill alone marks
principal_recovered and rebases high-water. It may leave a very small remainder;
this is a testable economic tradeoff, not claimed alpha.8 pure/integration tests
PASS, including common entry, next-frame execution and recovery resizing.

Primary field semantics: https://docs.gopluslabs.io/reference/response-details and
https://docs.honeypot.is/ishoneypot . Missing values are not measured false;
generic simulation errors are not affirmative cannot-sell evidence.

## Runtime acceptance at 2026-09-09T09:16:59Z

Safety commit c2e93f5 and integration db442c3 pushed. Integration loaded09:12:06Z.
Health/live/performance readable; Paper only/live locked. Forty-seven flat samples:
duration p50 2.398s/p95 5.225s; actual interval p50 5.032s/p95 5.622s.
Selection48 samples p50 .479s/p95 .739s. Initial bootstrap was expensive and remains
part of the reported distribution; this is a short natural acceptance, not long-run proof.
Held fetch p95 2.485s versus immediate pre-trial2.495s; apply79.7ms;
pattern5.534s; passive wait2.054s, dropped batches/quotes0. Dex pool timeouts0,
connect errors0. No extra source/cadence was introduced. Existing source errors and
429 history are not erased; this small window cannot establish provider-rate effects.
Observer fetch-with-wait p95 3.464s and passive compute .891s are mixed/network
measurements, not claimed local speedups. Eight copies of the221033-byte cohort
state took .0248s: no speculative in-place state mutation was justified.

Both new arms activate09:12:03.681726Z, snapshot2285820/evaluation1481249.
Checkpoint hash c8a6eb2cf8f15292; dynamic hash2faf7128cacc61af.
Each has1 admitted opportunity/1 open position/0 terminals at cutoff. Dynamic has
actual partial realized PnL .041264U and cash restored to1000U with a small remainder;
this is execution evidence only, not strategy profitability. Parent contract stays
unchanged; no extra funded control. Seven immutable tables' prior rows all preserved;
only policy additions grow286->288. Four natural rediscovery episodes by09:14:09Z.

Artifacts: data/research/system90/{flat_equivalence,registration_acceptance,
copy_profile,safety_natural}.json; data/research/admission88/system90_final.json.
Targeted suites:32 integrated tests PASS; flat/dormant/pure revision fixtures also
PASS. No redundant full-suite rerun. git diff --check completed for staged changes.

## Explicit unresolved boundaries

Pump native absorption remains DATA_BLOCKED/Shadow only: held sell math does not
prove a full causal new-buy/instant-sell USD cost contract. No Paper arm fabricated.
Safety has only sparse natural samples; UNKNOWN stays visible and supported RH
surface checks do not prove onchain code safety. No absolute scam-free claim.
Old admission84 audit still drops (1855 at cutoff), distinct from the zero-drop
trading passive queue. Its discontinuous generation is not a complete denominator.
Fresh/feature/gate/safety/next-frame/BUY evidence is cohort-keyed; full natural
missed-opportunity and terminal funnel remains immature. No Alpha claim.
