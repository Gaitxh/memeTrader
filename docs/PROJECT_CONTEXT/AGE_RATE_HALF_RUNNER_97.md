# Half-runner principal recovery97

REPLY_TO: C2C-20260909-AGE-RATE-HALF-RUNNER-97
Code8b93a28 deployed. New independent Paper age_rate_half_runner_recovery_v3,5U/max4, exact parent age-rate entry and next-frame execution/common safety. Parent and defensive v2 remain unchanged as controls; no duplicate funded control.

Reuses minimum actual-net debit-gap sale calculation. Only this new policy requires sell_raw*2<=remaining_raw, both at trigger and recomputed actual next frame. Integer arithmetic includes exact50% and rejects rounding above half. When not eligible, no special action and parent hard/trailing/maxhold remains. Settlement alone confirms principal_recovered; existing actual-fill high-water rebasing remains. No fixed price/TP tier/chain/date filter.

14 targeted tests PASS:49/50/51 percent, odd raw rounding, unchanged parent behavior, same nonempty source_entry_fill_id across fixture arms, next-frame repricing/boundary recheck, actual proceeds and high-water. Test found a real pre-existing cancellation defect: pending recovery used invalid marks status failed. Corrected to allowed exhausted; no settlement/recovery invented. Diff check PASS.

Activation2026-09-09T11:12:26.127872Z, snapshot2331465/evaluation1526890,behavior e27dea0da845086c. All old rows in seven contract/funding tables unchanged, additions289->290 only. Paper/live locked, healthy restart, no reset/backfill. No withdrawn checkpoint registration.

Natural read11:13:13Z:0 positions,0 paired outcomes. INSUFFICIENT_NATURAL_EVIDENCE. Historical limited-mark hypotheses are not validated Alpha; withdrawn post-parent-close diagnostic was not used. Compare future common fills with parent/v2.

Evidence data/research/system97/acceptance.json,before_contracts.json; runtime data/research/admission88/pre97.json,post97.json. Short post held p95~2.207s/apply~.0716s, not a sustained speed claim.
