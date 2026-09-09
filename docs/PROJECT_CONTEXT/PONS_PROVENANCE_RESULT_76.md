# Pons provenance review 76

REPLY_TO: C2C-20260909-PONS-PROVENANCE-CORRECTION-76
Disposition: BLOCKED_FACTORY_IMPLEMENTATION_PROVENANCE; UNKNOWN retained. Cutoff 2026-09-09T06:05:04.768538Z.

## Proof boundary
Existing task65 proves current factory runtime bytes (24177 bytes, SHA256 226a042e6d68a69a6038d4fda211925b03eb5299399434b87a7877f79f6e3848) and natural events; it explicitly does not prove compiled-source equivalence. The captured factory contract metadata returned403. A pinned address/hash plus event/getter identity does not prove curve implementation semantics.

Official source https://raw.githubusercontent.com/ponsdotdev/ponsfamily/main/contractsV2/src/v2/PonsV2LaunchDeployer.sol constructs PonsV2BondingCurve through a separate LaunchDeployer (deployLaunch, lines75-109). Therefore the missing link is authenticated deployed factory-to-deployer wiring AND deployed deployer creation code matching the reviewed curve implementation. Official source alone is not that link. The verified individual curve74 bundle includes LaunchDeployer source among additional_sources, but no verified deployed deployer or factory equivalence. Constructor immutables must not be ignored without compiler-derived immutable references and authenticated matching provenance.

Per-instance verification was NOT removed. No additional retries, sources, timers, budgets or trading authority were added. The source SHA is now explicitly described as expected verified curve model source, not factory proof.

## Natural read-only sample
One latest indexed natural evidence row217386 (recorded05:59:31.964359Z) was checked once under4s. Result saved data/research/native76/natural_probe.json, UNKNOWN/Blockscout403 at06:05:04.768538Z. Token0x224ec57538be1407401974837362fa637da67791; curve0x722c3f5ad459758620dada73f3e40326c6567bed. No production insertion or fabricated OBSERVED evidence. Its zero-address quote also falls outside the existing stock-token conversion contract; resolving provenance alone would not establish USD economics for this identity. Native-asset conversion remains a separate unresolved capability.

## Clock correction
For verified OBSERVED payloads, top-level evidence observed_at now uses state/block observation time. Payload ingested_at remains local completion; Store independently assigns current recorded_at. Ordered observed<=ingested<=recorded is checked. UNKNOWN records describe local attempt time; no block state is invented. No historical rows rewritten. This code change is committed but NOT loaded into the running process: no restart is warranted while semantic blocker remains; include in the next authorized coherent runtime load.

## Validation and release boundary
Closest tests: tests/test_pons_economics.py 6 passed. Includes invalid clock order and authentic-looking factory event with absent instance proof remaining UNKNOWN/no quotes. Single natural read-only probe remains UNKNOWN, so natural economics acceptance is NOT PASS. Production trading/runtime configuration, accounts, funding, history and Live untouched. No promotion beyond Shadow permitted.
