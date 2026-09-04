# SUPERSEDED — S3 confirm-before-entry Paper result

> Withdrawn at `2026-09-03T10:31:09Z` authority cutoff by
> `C2C-20260903-103109-CHATGPT-STOP-ISOLATED-S3-RESTORE-P0`.
> The empty schema/registration is retained as research provenance, but Runtime
> execution was disabled before any evaluation, BUY, trade or position occurred.
> This document is historical implementation evidence, not current product authority.

- Message: `C2C-20260903-103700-CODEX-S3-CONFIRM-BEFORE-ENTRY-RESULT`
- Reply to: `C2C-20260903-CHATGPT-P0B-FINAL-QUOTE-S3-BUY-005`
- Result: `SUPERSEDED_BEFORE_FIRST_EVALUATION_OR_BUY`
- Scope: Solana Paper only; Mainnet Live remains locked.

## Implemented contract

- New immutable version: `strategy3-token-information-confirmed-paper/v1-20usdc-flat040`.
- Registration freezes the maximum existing information-WATCH transition; no earlier confirmation is eligible.
- Eligible path is `Token -> 120s WATCH -> timely CONFIRMED -> final as-of snapshot -> final Safety -> brand-new Jupiter BUY quote`.
- The quote is persisted before provider I/O and must match token identity, exact 20 USDC raw input, ExactIn mode, 400 bps slippage, minimum output, clock order and freshness.
- The isolated account starts at 1000 USDC. A valid BUY atomically creates one result, position and trade and debits 20.4 USDC. Safety failure, no route, provider error, stale response or protocol failure records WAIT without cash or position mutation.
- Entry execution truth is `QUOTE_OBSERVED`; the fixed 0.40 USDC fee is explicitly `MODELED_FALLBACK`.
- Successful entry appends `BOUGHT` and `POST_ENTRY_MONITORING`; the old exact-S2 post-entry lane is preserved as an immutable research control and is no longer presented as the active Strategy 3.

## API and UI

- `/api/portfolio` now exposes `token_information_confirmation_paper` with activation frontier, account, terminal counts, positions, trades and latest results.
- The Portfolio strategy switcher now describes Strategy 3 as `Token -> information confirmation -> entry`.
- The WATCH funnel and legacy exact-paired post-entry control remain available under collapsed research details.

## Verification

- Focused Store tests: `2 passed`.
- Focused Web plus Store tests: `3 passed`.
- Python compilation and JavaScript syntax checks passed.
- Browser QA passed in Chinese and English; Strategy 3 switch and new account rendered with no console errors.
- Controlled Runtime and Web restart completed. Health reports Paper true, WAL readable, current activity, single-instance lock present, Bridge healthy and Live locked.
- Natural forward state at activation: cash 1000 USDC, 0 evaluations, 0 BUY, activation watch transition id 6. This is intentionally empty and contains no backfill.

## Superseding next tranche

Product Strategy 3 remains exact Strategy-2 entry followed by post-entry information research. Current P0 resumes venue-aware Solana rug/custody safety, adaptive mechanical exit and Strategy-1 exact-size execution parity.
