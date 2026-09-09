# Passive local regime Shadow v2 — 62

REPLY_TO: C2C-20260909-REGIME-SHADOW-V2-62
Disposition: IMPLEMENTED_ON_DEMAND_REPORT_ONLY
Cutoff: 2026-09-09T04:29:17.163199+00:00

`scripts/report_regime_shadow_v2.py` reads bounded primary-key tails (10000 discovery exposures,12000 snapshots,10000 evidence rows), read-only connection and a 3-second SQLite progress budget. It writes a compact report, not production KV, and has no scheduler, network calls or strategy consumer. decision_eligible=false, affects=none. Existing v1 remains historical component-only.

Current and immediately preceding 15-minute windows use local recorded clocks; snapshots require observed<=ingested<=recorded<=cutoff, lag<=15s, exact pool, positive finite price and liquidity>=1000. Unique first-local identities are grouped by chain and native source surface where identifiable. Report includes 300s matured conversion and receipt latency, early liquid/active counts, missing activity, median liquidity/turnover, provider coverage, unique Pump watch migration/completion events. Native provider creation time is not launch receipt. Venue attribution is receipt-source only; no claim of verified Stonk subplatform identity. No outcome/PnL/ATH tables are read.

Intensity ratio requires both local windows fully retained and >=20 receipts each. This first report has complete current15m but incomplete prior window, so ALL intensity states UNKNOWN; never COLD. Coverage means retained local records, not full-chain coverage or healthy upstream. Pregrad events remain watch-selected. Signal incidence is explicitly UNKNOWN_NOT_READ rather than a costly evaluation join. Conversion is first retained valid market pool, not proof of executable launch curve or cross-pool continuity. Historical snapshot columns may already encode unavailable activity as zero; report preserves SQL NULL but cannot repair upstream missingness. No Alpha claim.

Validation: 2 targeted tests PASS (future-frame exclusion, missing activity, truncation UNKNOWN, event dedupe). Actual run 1.474s; 32000 rows bounded; zero recurring runtime scheduling cost. One-shot DB I/O is nonzero and must not be called on a hot loop. No restart, trading changes, funding/reset/backfill/Live. Frozen state: data/research/regime62/state.json. Subsequent outcome study must use this cutoff before entries and separate source changes/censoring; no future outcomes yet examined.

Run: `.venv/Scripts/python.exe scripts/report_regime_shadow_v2.py --database data/memetrader_forward_20260830_r6.sqlite3 --output data/research/regime62/<new-cutoff>.json`. Use distinct output names to preserve prospective freezes. No autonomous periodic research installed.
