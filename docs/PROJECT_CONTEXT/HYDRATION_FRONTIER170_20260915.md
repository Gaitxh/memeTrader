# Hydration frontier 170 - 2026-09-15

## Problem and evidence

Since `2026-09-15T12:00:54Z`, snapshot-to-entry evaluation remained healthy
(`p50 2.32s`, `p95 14.42s`), while discovery-to-first-snapshot had a
`p95` near 347 seconds. The delay was concentrated in first-local discoveries:

- Solana PumpPortal create: 405 mature tokens with a snapshot, `p50 316.7s`,
  `p95 360.7s`.
- BSC FourMeme native launch: 204 mature tokens with a snapshot, `p50 13.8s`,
  `p95 26.0s`.
- The hydration component ran at an observed `p95` interval of about 10.96s.

The fast hydration cycle has 30 address slots. It reserved 80%, or 24 slots,
for lifecycle follow-ups before selecting new discoveries. That left only six
first-frame slots shared by Solana, BSC and Robinhood, an effective upper bound
near 0.55 new tokens/second at the observed interval. This was the immediately
controllable capacity bottleneck; it amplified, but did not fully cause, the
PumpPortal latency.

The first post-deployment mature slice sharpened the diagnosis: all 37 recent
PumpPortal creates returned no DEX snapshot within two minutes, while 26/26
FourMeme launches did (`p50 19.1s`, `p95 32.7s`). The generic no-pair path waits
five minutes after the first miss, which explains roughly 300 seconds of the
historical PumpPortal latency. A source-specific short retry is therefore the
next causal experiment; applying it to every no-pair identity would waste the
bounded shared address capacity.

## Change

The fast hydration cycle now reserves 50%, or 15 slots, for lifecycle
follow-ups and leaves 15 for first frames. This does not increase HTTP request
count, batch size, configured source capacity, or weaken identity, freshness,
liquidity, risk, cash or execution rules. Held-token and pending-exit work keep
their existing higher-priority paths.

## Validation and guard

- Focused regression: 7 passed, 117 deselected.
- Restarted under the existing supervisor without reinitialization.
- Funding period remained `chain-meme-trader/funding-20260906-v002-final-1000`.
- Loaded `runtime.py` SHA-256 matched disk:
  `aef86c1e374ba34935a7c549295de7960a75238a95f9d76bbc5e0fd488913d2e`.
- Runtime reported `Paper-only=true`, `Live locked=true` and a fresh heartbeat.

Keep the change only if a mature forward window shows higher first-attempt
throughput without new lifecycle follow-up expiry/failure. PumpPortal
first-snapshot latency is not expected to fall below 180 seconds until its
generic five-minute no-pair retry is separately addressed. BSC native latency
and lifecycle follow-up outcomes remain the safety guards. Economic results
remain unproven; this change only restores capacity for timely, identity-bound
evidence in the strategy funnel.

## Strategy-tempo disposition

The existing `tempo_matrix162` already covers fast/slow entry crossed with
5-minute/90-minute exits. The next non-duplicate experiment candidate is a
strictly paired mature three-frame signal with known entry-time market activity
(`buys_5m + sells_5m >= 30`), comparing 5-minute and 90-minute exits. It is not
registered in this stage: first-frame capacity is being changed first so the
entry sample is not confounded by two simultaneous interventions.
