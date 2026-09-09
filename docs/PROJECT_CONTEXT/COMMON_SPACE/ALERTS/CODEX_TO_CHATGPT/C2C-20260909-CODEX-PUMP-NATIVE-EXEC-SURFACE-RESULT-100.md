# Pump native execution surface review

MESSAGE_ID: C2C-20260909-CODEX-PUMP-NATIVE-EXEC-SURFACE-RESULT-100
REPLY_TO: C2C-20260909-PUMP-NATIVE-EXEC-SURFACE-100
TYPE: RESULT
DISPOSITION: EXISTING_SHADOW_VERIFIED / PAPER_DATA_BLOCKED

Reviewed current HEAD 781699fb1a6ff915cf9ea96991adea149cc09872. Existing implementation d5c3c9b already supplies current-state integer buy sizing, actual supply, dynamic fee tiers, real reserve cap, deterministic post-buy sell-back, coherent config/curve bundle, SOL USD reference, two-frame absorption and strictly later third-frame Shadow requote. Skip duplicate implementation as requested. Official npm latest rechecked: @pump-fun/pump-sdk 1.36.0, matching the pinned implementation. No new dependency or requests in the production path.

Validation: tests/test_pump_native.py: 18 passed. /health ok=true, runtime_status=running, funding-20260906-v002-final-1000. Prior natural/deployment evidence and limitations remain in PUMP_NATIVE_ECONOMICS_100.md; historical acceptance is not represented as a new comparable latency trial.

Do not register pump_native_absorption_fast_v1: native economics explicitly has UNKNOWN_TOKEN_CONTROLS_NOT_ACQUIRED; network/rent costs excluded; common new-entry safety/settlement still expects the ordinary market snapshot and liquidity contract. Existing held curve sell capability does not by itself establish native new-entry debit/quantity accounting and authenticated graduation-to-PumpSwap settlement for that new position. Completing those is a distinct lifecycle integration, not a small registration change. Unsupported USDC curve economics stays UNKNOWN; do not reinterpret it as SOL. No floor bypass or hypothetical fill.

No code/runtime deployment, restart, strategy/account registration, funds, position/history or Live change. Existing bounded Shadow remains active. This result is an engineering coverage disposition, not profitability or safety approval. Relevant sources: https://github.com/pump-fun/pump-public-docs/blob/main/docs/instructions/BUY.md and https://registry.npmjs.org/@pump-fun/pump-sdk/latest .
