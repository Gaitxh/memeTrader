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
- Autonomous Agents are allowed for three bounded jobs: global trend scouting, free-source discovery, and high-momentum Token context investigation.
- Keep at most two Agent subprocesses concurrent. Trend/source search uses Spark/low first and Luna/low only as fallback; Token context uses Luna/low, then Terra/medium, with Sol/medium only as the final fallback.
- Enforce daily call budgets, daily token budgets, per-call token reserves, adaptive quiet/surge intervals, a global Token-context cooldown, and a shorter error retry delay. A manual `--force` may bypass time due checks but never daily budgets.
- The separate semantic tie-breaker remains disabled by default; uncertain canonical rankings return `WAIT` instead of forcing a winner.
- Agents never receive wallet, broker, private key, project-write access, or permission to bypass local risk rules.

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
