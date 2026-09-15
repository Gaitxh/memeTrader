# Shared market retry lanes 182

## Observed problem

After shared-core 181 was deployed, new pending discoveries drained promptly and
DexScreener requests reached the supported 30-address size per chain. Natural
runtime evidence then showed that many later batches requested 30 addresses but
returned zero or one pair. The hydration queue still had thousands of old
`no_pair` rows: the selector ordered `pending` first but selected
`pending`, `no_pair`, and `error` from the same base query, so old failures filled
all capacity whenever fewer than 30 new tokens were waiting.

This was wasted shared market-data capacity, not insufficient free API capacity.

## Root cause and change

The shared selector now has explicit capacity lanes in this order:

1. `pending` first quotes consume capacity first.
2. Valid lifecycle follow-ups within their bounded observation window use spare
   addresses.
3. Historical `no_pair` and `error` recovery uses only the remaining addresses and
   is capped at three tokens per chain.

The runtime opens the generic recovery lane only once every 30 seconds. A new
discovery or migration receipt still promotes a matching old `no_pair` or `error`
row back to `pending`, so fresh evidence is served immediately rather than waiting
for generic recovery.

The change affects only shared acquisition scheduling. It does not change strategy
cash, positions, historical trades, pool floors, write-off rules, funding periods,
or Live status.

## Verification

- Seven shared-core/retry/follow-up tests passed.
- Five existing hydration selection and retry tests passed, including durable
  missing-pair retry and fresh/FIFO fairness behavior.
- A focused test proves that 12 due historical no-pair rows cannot expand a
  two-token fast lane when generic recovery is closed, and can contribute only
  three rows when it is open.
- A focused test proves ordering of fresh first quote, lifecycle follow-up, then
  generic recovery.

## Forward acceptance

After deployment, compare a natural window against the pre-change evidence:
addresses requested per batch, returned-pair ratio, all-zero 30-address batches,
pending queue age, discovery-to-first-frame latency, source errors, and held-market
mark age. This scheduling repair is expected to recover acquisition capacity; it
does not by itself establish profitable strategy performance.
