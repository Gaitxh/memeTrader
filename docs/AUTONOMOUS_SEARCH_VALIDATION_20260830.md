# Autonomous Search Agent validation — 2026-08-30

## Result

**PASS for autonomous discovery in Shadow/Paper mode.**

The resident bot can now find information without requiring the user to maintain a fixed source list. Three bounded search jobs share at most two concurrent Codex processes:

1. **Global trend scout** — searches current international events that may become Meme narratives.
2. **Token context investigator** — starts from a high-momentum Token and searches for the corresponding real-world/social event.
3. **Source discovery** — finds public RSS/Atom sources, verifies them locally, and adds only working feeds to the dynamic registry.

Agents never receive Broker, wallet, private key, position-changing, or Live-unlock access.

## Default cadence

| Work | Default cadence | Model route | Daily cap |
|---|---:|---|---:|
| Deterministic browser/Pump/new-pool/event loops | 10–60 seconds | Local code | none |
| Global trend scout | 12 minutes; 3 of 5 topic lanes per run | Spark/low → Luna/low | 64 calls / 500,000 tokens |
| Trend scout during a verified surge | 3 minutes for 30 minutes; all 5 lanes | Spark/low | same cap |
| Trend scout after three empty runs | 30 minutes | Spark/low → Luna/low | same cap |
| Trend scout while a fallback/high-token model is required | 30 minutes normally; 10 minutes in surge | Luna/low | same cap |
| Token context investigation | event driven; 240-minute per-Token cooldown | Luna/low → Terra/medium → Sol/medium | 8 calls / 250,000 tokens |
| New-source discovery | every 24 hours; hourly due check | Spark/low → Luna/low | 2 calls / 100,000 tokens |

All values are configurable under `config.json -> autonomous_search`. `max_concurrent_agents` defaults to `2`. Calls stop when either the call cap or the token budget is exhausted.

## Executed tests

- Full test suite: **59 passed**.
- Source and test compilation: PASS.
- Wheel build: PASS (`memetrader-0.6.0-py3-none-any.whl`).
- Installation into a clean virtual environment: PASS.
- Installed CLI import/help: PASS.
- `pip check`: PASS.
- Offline and online doctor: PASS.
- DexScreener, GeckoTerminal, Honeypot.is, RugCheck, configured RSS endpoints: reachable during validation.
- Chinese Unicode round-trip through Codex stdin/output: PASS (`牛来` preserved as UTF-8); mojibake seen in some console logs is display encoding, not prompt corruption.

## Real Agent runs

### Public-source discovery

A real Codex web-search run used Spark first. Spark quota was unavailable, so the router changed to Luna/low. The Agent proposed candidate feeds; the local program independently fetched and parsed them before activation.

Accepted and automatically polled:

- `https://www.aljazeera.com/xml/rss/all.xml`
- `https://www.france24.com/en/rss`
- `https://www.theguardian.com/world/rss`
- `https://www.lemonde.fr/en/international/rss_full.xml`

Rejected:

- one HTTP 404 endpoint;
- one feed without recent timestamped items.

The four accepted feeds subsequently appeared in `source_health` with successful `last_ok_at` and `last_item_at`, proving they were used by the resident collector rather than stored as recommendations only.

### Proactive trend scout

A real current-event run used Spark first, then Luna/low when Spark quota was unavailable. It returned no qualifying event because it could not find two recent independent sources for a sufficiently Meme-capable event. The system did not invent a result. The final controlled run used 31,583 tokens; because a fallback/high-token model was used, the next interval was automatically increased to 30 minutes and the usage was persisted to SQLite.

## Evidence rules

Agent search output is not trusted by itself. An event becomes an observation only after:

- URL scheme/host and public-network validation;
- successful local HTTP retrieval;
- a timezone-aware publication timestamp within the configured lookback;
- minimum relevance, confidence and Memeability scores;
- at least two independently hosted sources;
- exclusion of price pages, exchanges, launchpads and token-promotion sites.

The local receiver assigns `observed_at`; later ATH, winner identity, exchange listing, final holders, future returns and other outcome fields remain forbidden decision inputs.

## Runtime state

- Mode: `paper`.
- Live: locked.
- Resident browser bridge health endpoint: healthy after process restart.
- Dynamic source registry: active.
- Proactive scout scheduler: active.
- Browser extension: optional fast-path; autonomous web search and public feeds do not require manually entered account/source lists.
