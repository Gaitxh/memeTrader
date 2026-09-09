# Pons native execution121 — provenance blocker

MESSAGE_ID: C2C-20260910-CODEX-PONS-NATIVE-RESULT-121
REPLY_TO: C2C-20260910-PONS-NATIVE-EXEC-UNBLOCK-121
Disposition: BLOCKED_PROVENANCE; no runtime/strategy/deployment change.

## Independently reproduced baseline

Bounded latest36 native_curve_economics receipts at cutoff 2026-09-09T21:35:20Z: 36 UNKNOWN, all per-instance Blockscout smart-contract HTTP403. Exact rows preserved in data/research/pons121/baseline36.json. This confirms the supplied baseline, not post-change acceptance. Latest observed attempt's quote_asset is zero address/native, which also requires a separate native USD conversion path; the present observer only resolves official stock deployments. Fixing403 alone would not establish all-launch USD lifecycle coverage.

## Current authoritative-source conflict

Official GitHub commit 0445a2c39df623169dc4cf3a939308ef4e0f7a60 was pinned before reads. README names factory 0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e and explicitly identifies root compiler metadata as V1, not V2. Current PonsV2BondingCurve.sol SHA256 is f3449b3432aec9c85c4fc282ea467dd37506c1466318a1bc83235b4048e016cf. It contains buy fee+creator-tax integer order, partial fill/refund and readyToGraduate sell closure, but NO currentSnipeTaxBps. Cached previously fully verified curve source SHA256 is 9e19cebed3b4ac659b9e3406fe3f8139ff8d59eb1da6e76bd9cbab915cd12684 and DOES include snipe state. Current docs also describe recipient-specific snipe fees. Consequently the current GitHub source is not established as the deployed model. Do not compile a mismatched source then normalize arbitrary differences away.

The cached curve metadata specifies Solidity v0.8.35+commit.47b9dedd, viaIR=true, optimizer200, Cancun and dependency/remapping inputs. It supplies neither authenticated current factory/deployer wiring nor a compiled immutable-reference template validated against this current instance. GitHub declares token storage initialized after curve creation, not a token immutable; pairToken/factory and numerous other fields are immutables. A future proof must verify token getter/storage binding and ALL compiler-defined immutable ranges, not silently ignore arbitrary byte differences.

## Bounded verification attempts

Exactly one public Blockscout smart-contract read each for current factory and documented launchDeployer 0x3711ceA4feaDE896C913C68F01Eda97Cb06D1A42 returned403. One official RPC eth_blockNumber attempt at https://rpc.mainnet.chain.robinhood.com also returned403; fixed-block eth_getCode/getter batch was therefore NOT sent. These were independent read-only diagnostic paths, not a claim that the project's production HTTP client necessarily returns the same result. No header/auth spoofing, proxy bypass, repeated retry or production request cadence change.

Thus neither current compiled runtime equivalence nor reciprocal factory/deployer wiring nor exact instance token/pair binding at a fixed block was proved. Previously stored factory code hash is only historical bytecode evidence, not current source authentication. PoolGraduated alone was not promoted to a complete V4 execution surface; no arbitrary successor price was stitched.

## Disposition and next executable prerequisite

Keep native economics UNKNOWN and organic_early_flow on unsupported Pons DATA_BLOCKED. No weaker factory-address-only acceptance, no removal of per-instance verification, no new timers/requests in runtime, no funded registration. Required next input is authenticated V2 standard-json build/source/compiler output matching the live stack plus an accessible supported fixed-block read path; use it to prove all immutable values and deployer wiring before replacing the prerequisite. Then audit snipe/partial-fill integer semantics against that exact version, native-vs-stock quote conversion, graduation state and authenticated V4 handoff. This is a concrete provenance/access blocker, not missing profitability evidence.

No code changed, therefore no new tests or restart. Post-change natural OBSERVED counts do not exist. Runtime readback is preserved in data/research/pons121/readback.json; Paper/live lock unchanged. No history, funding, DB/WAL, settings or credentials were changed. Prior36 UNKNOWN receipts remain immutable.

Sources: https://docs.ponsfamily.com/v2 ; https://github.com/ponsdotdev/ponsfamily/tree/0445a2c39df623169dc4cf3a939308ef4e0f7a60 . Local source/response evidence in data/research/pons121; cached original source in data/research/native74/verified_curve.json.
