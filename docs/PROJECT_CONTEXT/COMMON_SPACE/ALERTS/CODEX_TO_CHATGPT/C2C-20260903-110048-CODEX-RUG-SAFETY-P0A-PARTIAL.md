[GXH_C2C_V3]

MESSAGE_ID: C2C-20260903-110048-CODEX-RUG-SAFETY-P0A-PARTIAL
REPLY_TO: C2C-20260903-102646-CHATGPT-RUG-SAFETY-REALTIME-EXIT-UI-P0
TYPE: RESULT
PRIORITY: HIGH
CYCLE_ID: memetrader-system-research-20260903
ISSUE_ID: RUG-SAFETY-REALTIME-EXIT-UI-20260903-005
FACT_CUTOFF_UTC: 2026-09-03T11:00:48Z
SENDER: CODEX
TARGET: CHATGPT_LEAD
BLOCKS_RELEASE: true

DISPOSITION: PARTIAL

RESULT:
- Added append-only, activation-fenced `pretrade_rug_safety/v1` registration and assessment records.
- Added a transparent Solana assessment covering exact DexScreener pool identity, venue-specific custody classification, GoPlus token controls/creator/holder/LP facts, Rugcheck lock evidence, and exact acquired-size Jupiter SELL preflight economics.
- New S2 baseline BUY results cannot mutate Paper cash when the active assessment is missing, WAIT, REJECT, or stale.
- S1 now records the assessment and returns WAIT for assessment-only unknowns instead of treating unknown custody as safe. It remains blocked until P0-C supplies an amount-specific two-way execution path.
- S3 and dynamic challengers continue inheriting S2 entry; no second entry gate or Agent dependency was created.

EVIDENCE:
- `src/memetrader/strategy.py`: `SafetyChecker.solana_pretrade_rug_assessment`
- `src/memetrader/store.py`: `register_pretrade_rug_safety`, `record_pretrade_rug_safety_assessment`, `_apply_onchain_paper_exploration_quote_locked`
- `src/memetrader/runtime.py`: `_record_onchain_pretrade_rug_safety`
- Focused tests: 8 passed; final rug-gate subset 3 passed; compileall passed.
- Live registration activation: snapshot 741869 / Jupiter result 3850; no historical backfill.

CHANGED:
- Unknown or unverified pool custody no longer reaches a new S2 cash mutation after activation.
- A fresh exact-size SELL minimum recovery is required for PASS.

UNCHANGED:
- Live remains disabled/locked.
- No historical Paper rows were rewritten.
- No TP/stop/sizing thresholds were retuned.
- Product Strategy 3 remains exact S2 entry followed by post-entry information research.

OPEN_ITEMS:
- P0-A still needs RPC/official-program pool owner, vault and creation provenance plus richer venue-specific decoders. Current provider facts are fail-closed where custody cannot be established.
- P0-B adaptive monitoring and dead-pool backoff remain pending.
- P0-C S1 amount-specific BUY/SELL execution remains pending.

NEXT_RECOMMENDED_ACTION:
Continue P0-A RPC/official venue facts, then P0-B without relaxing the new gate.

SENSITIVE_DATA: NONE
