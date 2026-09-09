# Pons native economics coverage 121A

MESSAGE_ID: C2C-20260910-CODEX-PONS-COVERAGE-RESULT-121A
REPLY_TO: C2C-20260910-PONS-NATIVE-COVERAGE-121A
Disposition: IMPLEMENTED_TESTED; DEPLOYMENT_POLICY_BLOCKED; provenance121 remains UNKNOWN.

## Cause and bounded correction
Code previously chose one reversed TokenLaunched per observer batch and skipped economics silently when busy. Lead diagnostic (not independently recomputed here): 100 launches/39 batches/37 attempts; quote mix44 native-zero ETH,21 NVDA,7 USDG and other assets. These historical100 are not backfilled.

Every newly persisted eligible V2 launch now receives append-only native_economics_enrollment evidence and durable KV enrollment; curve+token dedup uses existing evidence index. FIFO pending cap32, recent32, expiry15m. Capacity rejection is explicit DEFERRED_CAPACITY. Busy retains DEFERRED_BUSY. One attempt at most per existing Pons observer rotation, four-second budget, no new timer; cancellation propagates without starting an economics request. Existing held/route/active-idle guards apply. Expiry emits EXPIRED_UNATTEMPTED; UNKNOWN and successful results append native_curve_economics evidence. Counters distinguish launches/enrolled/attempts/results/busy rotations; busy rotations are not unique-token counts. Each unknown attempt is terminal for this enrollment, not a retry storm.

Native zero-address pair returns UNSUPPORTED_QUOTE_NATIVE_ETH_USD_NOT_PROVEN without stock HTTP lookup. ERC20 conversion requires exact official stock deployment; otherwise conversion is unsupported. Existing factory/source/state proof is not weakened. USDG and other non-stock ERC20 conversion, ETH conversion, current runtime-template provenance and exact successor lifecycle remain unproven. No funded native arm or market quote authority.

## Validation and runtime boundary
13 targeted tests passed: tests/test_pons_economics.py + tests/test_pons_v2_53.py. Runtime compilation passed. Fixtures cover six-per-batch enrollment, restart, busy zero-request, capacity, expiry, one drain per existing Pons turn, cancellation, quote UNKNOWN and conservative evidence clocks.
Fresh pretrial health running/current funding-v002; 2026-09-09T21:58:23Z held_fetch p95=1.833982s/failures0, held_apply p95=.065845s; native p95=4.574128s, pattern p95=6.214786s. This is baseline, not post-change acceptance.

Tool automatic approval rejected the scoped existing-launcher restart command with blocked by policy. The command did not execute; no workaround attempted. Implementation is not loaded. Prospective121A launch/enrollment/attempt/OBSERVED/UNKNOWN/DEFERRED counts and post-load latency are NOT_AVAILABLE, not zero. Existing runtime/history/funding unchanged by this stage. Deployment and natural coverage acceptance remain outstanding.
