# RESULT143 — cohort94747 actually exited

The repeated “1仓等待恢复” was not resolved by142's display change. A deeper Paper accounting defect is now fixed and the remaining position is CLOSED, quantity0. Source f916668 was pushed and loaded through the existing Paper launcher; runtime PID31596. No forced trade/manual close/reset/Live action was used.

## Root cause and model correction

The native BUY already debited cash and verified a post-BUY curve that adds net quote reserves and removes bought tokens. Subsequent held quotes applied only prior SELL deltas to fresh public state. Omitting the recorded BUY delta made entry sellability and later exit accounting inconsistent. The deliberately conservative140 convention was asymmetric; resetting its sold counters or changing UI wording would not fix it.

One bounded current RPC bundle proved original curve6yLdu5…DKJw still incomplete, real quote7,643,704raw; canonical successor absent. The old partial had consumed exactly7,643,704raw in Paper. The immutable BUY's net curve deposit was45,405,135raw; fees were excluded. V2 reconstructs `current public curve + recorded BUY - recorded SELL` for both virtual pricing and real capacity. It uses full curve token delta for reserve math, adverse-slippage Paper quantity for holdings. Public evidence remains unchanged and distinctly identified from derived Paper state.

New buys retain the deltas. Existing open positions get one append-only `CURVE_ACCOUNTING_V2` transition tied to their immutable BUY receipt; quotes must be observed strictly afterwards. Prior debits remain, so repeated slots cannot reuse capacity. Invalid reconstructed token/virtual reserves block; public completion still requires verified canonical migration and a later successor frame. This is protocol-model Paper, not a claim of an onchain transaction.

## Actual result

- Transition receipt3: 2026-09-10T13:26:05.238281Z.
- Fresh original-curve quote slot445895040, observed13:26:15.903660Z; current exact quantity fee and conversion were acquired by the normal held task.
- SELL receipt4/common trade512482:13:26:18.141312Z. Sold all remaining1,284,729,855,258raw; recovered3.388363686943932U net. Position CLOSED/max_hold, remaining quantity0.
- Total proceeds including old partial:4.121161651698222U; total realized PnL−0.5185345393554777U. Entry rent0.35979919255599896U remains a separate locked-cost asset, not an invented refund.
- Independent reconciliation: sum of common cash flows + retained rent equals realized PnL; full entry cost allocated. All old native receipts/trades byte-equivalent; all captured registration/policy/funding table counts/hashes unchanged (311 additions, same funding period).
- API after:12 ordinary open positions,12 valued,0 native open,0 UNKNOWN values. Actual existing browser refreshed21:27:58 local: no “等待恢复” or “储备不足” message. Paper=true/Live locked, system running.

## Validation and resource boundary

Closest native/Pump test modules PASS. Includes post-BUY quote equality, net-fee reserve credit, counterfactual divergence/public graduation, partial->restart->no reused capacity, legacy partial->versioned transition->strict later full close, immutable earlier receipts, fee/clock binding and common cash reconciliation. An independent bounded code review found no accounting blocker. No new scheduled source/API work was added.

First post-load rolling window: held_fetch p952.389s, held_apply28.6ms, passive wait2.171s/drops0; PoolTimeout0/ConnectError0. Pre-load p951.888s/68.3ms/passive2.518s. Startup/workload differ; these are operational readbacks, not a controlled performance improvement claim.

Evidence: data/research/native_exit143/current_pool.json, before_load.json, after.json. One normal forward exit is engineering acceptance, not strategy Alpha. Prior142 statement that only external reserve restoration could resolve this position is superseded by this proven asymmetric accounting defect.
