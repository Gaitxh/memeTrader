# Official Robinhood stock scope veto96

REPLY_TO: C2C-20260909-RH-STOCK-MEME-VETO-96
Code67c5a27 deployed via existing Paper launcher.

Common preentry guard now queries the latest successfully recorded official /rhj/assets registry whose completed_at AND recorded_at are available by decision time. Contract address canonicalized for Robinhood. Exact membership produces REJECT_SCOPE / official_robinhood_stock_token_not_meme, classification_only=true/not_a_scam_claim=true, before cached safety authorization. Open positions and exits are untouched.

Missing/empty registry evidence is UNKNOWN and attached to the existing audit item; it alone does not reject nonlisted Robinhood. BSC/Solana bypass this lookup. Existing registry only accepts validated nonempty official snapshots and defines no TTL; therefore no new expiry policy was invented. Failed refreshes do not erase completed official membership. NOT_LISTED is not a safety guarantee; existing provider usable-fact checks remain unchanged. No API/cadence additions.

33 targeted tests passed (32 registry/existing safety, plus common-guard precedence). Covers hit/miss/canonical case, future completed/recorded time exclusion, no/empty registry, latest snapshot semantics and unaffected other chains. EXPLAIN uses existing unique(run_id,contract_address) index; no schema/index change.

Historical read-only diagnostic reproduced: current period10 positions/3 tokens/-14.272903136962233U linked to run26, completed2026-09-03T14:12:48.767628Z, recorded14:12:48.772436Z,194 deployments. This is a missed classification, not recovered/counterfactual profit. No historical row or PnL changed.

Acceptance 2026-09-09T11:09:50.694987+00:00: health={'ok': True, 'runtime_status': 'running', 'version': 'chain-meme-trader/funding-20260906-v002-final-1000'}; Paper=True, live_locked=True. Seven-table contract/funding digest unchanged 5883a315353ee88e25bf6090c69bf7b216c0804145a7a6822922b776c3723980. Short startup read only, not a sustained performance claim. Evidence data/research/admission88/pre96.json and post96.json. No reset/backfill/Live.
