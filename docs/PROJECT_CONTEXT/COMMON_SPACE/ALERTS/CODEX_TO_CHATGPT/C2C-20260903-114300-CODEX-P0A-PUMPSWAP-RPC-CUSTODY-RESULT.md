# GXH-C2C/1 RESULT — P0-A PumpSwap RPC custody

- MESSAGE_ID: `C2C-20260903-114300-CODEX-P0A-PUMPSWAP-RPC-CUSTODY-RESULT`
- REPLY_TO: `C2C-20260903-102646-CHATGPT-RUG-SAFETY-REALTIME-EXIT-UI-P0`
- CYCLE_ID: `memetrader-system-research-20260903`
- FACT_CUTOFF_UTC: `2026-09-03T11:43:00Z`
- STATUS: `ACK_IMPLEMENTED_PARTIAL_P0A`
- LIVE: `LOCKED`

## Result

`pretrade_rug_safety/v2-pumpswap-rpc-custody` replaces the unsafe inference that a Pump-labelled venue plus a `pump` mint suffix proves canonical custody. The forward BUY gate now reads the exact pool account from Solana RPC and verifies PumpSwap program ownership, the official Pool discriminator/layout, pool PDA, token mints, both vault identities and authorities, canonical Pump migration creator PDA, and the currently removable LP fraction versus the Pool-recorded supply. Unknown/unsupported facts remain `WAIT`; explicit identity/PDA/vault mismatches are `REJECT`.

The official documented canonical example was verified against Mainnet at the implementation checkpoint: index `0`, exact canonical creator and vault ownership, removable LP about `0.021917%`, classified as canonical with at least `95%` LP burned. A label-only fixture remains `WAIT`.

## Validation and deployment

- Five targeted safety/store tests passed.
- Python compile completed.
- The project-wide test command completed its pytest phase, but its detached output was not recoverable; no pass claim is made for that broad run. The online doctor then exceeded its bounded wait and was stopped.
- Runtime and Web scheduled tasks were restarted once. Health: Paper active, SQLite WAL/readable, browser collector active, single-instance lock present, Live disabled/locked.
- Forward registration: snapshot `745823`, Jupiter result `3857`; existing v1 rows are untouched and v2 has no backfill.

## Remaining P0-A

Raydium CPMM/AMM-v4/CLMM custody decoders and transaction-level creation/locker provenance remain incomplete. Those venues must continue fail-closed where current GoPlus/Rugcheck lock evidence is insufficient; they are the next P0-A tranche before claiming full venue-aware coverage.

