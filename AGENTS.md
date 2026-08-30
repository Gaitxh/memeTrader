# memeTrader project rules

## Goal

Run a simple personal-PC bot that discovers real-world/social events and related meme tokens within minutes, ranks the canonical token, and records Shadow/Paper decisions and exits. Keep one Python process, SQLite, JSON configuration, and an optional browser extension unless a proven requirement demands more.

## Non-negotiable safety and research rules

- `mode` is `shadow` or `paper`. `live.enabled` remains `false` until a separately reviewed live broker and small-capital chain test exist.
- Historical cases test identity matching, ambiguity, timing, and future-data rejection. Never use later ATH, final winner, exchange listing, current holder counts, or other outcomes as earlier decision features.
- A fact is decision-eligible only when its local `observed_at` and `ingested_at` are not later than the decision time.
- Do not commit `config.json`, `data/`, logs, SQLite databases, browser/session material, API keys, wallet material, or private bridge tokens.
- Free/public sources may fail or rate-limit. Preserve other collectors and record the failure; do not silently treat missing security data as safe.

## Agent-cost routing

- Use deterministic local code for polling, parsing, scoring, arithmetic, position sizing, risk limits, and exits.
- Use an Agent only for a small number of genuine semantic ambiguities: cultural jokes, aliases, identity conflicts, or near-tied canonical tokens.
- Use Low first; Medium only for high-attention near ties. High stays disabled by default.
- Agents never receive wallet, broker, private key, or permission to bypass local risk rules.

## Required checks for an in-scope change

Run the closest targeted test, then the full suite before a release or push:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m memetrader doctor --config config.json --online
```

For resident-operation changes, verify the single scheduled task, port `8765`, `/health`, `IgnoreNew` behavior, and one forced child-process restart.

## Current device deployment

- Working folder: `E:\memeTrader`
- Scheduled task: `memeTrader Paper Bot` (interactive user, at logon, `IgnoreNew`, battery-safe)
- Runtime database: always resolve `database` from ignored `config.json`; current device path is `data\memetrader_forward_20260830_r6.sqlite3`. Earlier `r5` contains rejected false-positive Paper evidence from promotional listicles and must not be merged into performance statistics.
- Browser bridge: loopback only on `127.0.0.1:8765`
- Manual step: load `browser-extension` as an unpacked Chrome/Edge extension and copy the local `bridge.token` from ignored `config.json` into its options.
