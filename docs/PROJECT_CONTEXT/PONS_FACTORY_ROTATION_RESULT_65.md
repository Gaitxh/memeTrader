# Pons factory rotation65

REPLY_TO: C2C-20260909-PONS-V2-FACTORY-ROTATION-P0-65
Disposition: REJECT_FACTORY_EXPANSION_NO_RECENT_LAUNCHES

Direct current official raw README https://raw.githubusercontent.com/ponsdotdev/ponsfamily/main/README.md returned200 and declares existing0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e. Search-cached GitHub README instead lists0x7E1EAbd52Ae29598e6483F72dCf1a70b14284dB8; not current deployment authority. Official docs https://docs.ponsfamily.com/v2 likewise identify existing7ed. No extra V2 address verified by current authoritative evidence.

Both addresses have nonempty runtime code via official public Robinhood RPC. Old7E1E22757bytes SHA2566796fb0e5c1687698e7f2dcea07d855606396345b14c8dd212eb3ce3544cad63; current7ed24177bytes SHA256226a042e6d68a69a6038d4fda211925b03eb5299399434b87a7877f79f6e3848. They differ; this is NOT independently compiled-source equivalence. Blockscout contract metadata and address logs both403 for both addresses; no bypass attempted, source/bytecode compiler verification unavailable.

Fallback read-only public RPC same fixed block window58230814–58266814 (2026-09-09T03:37:06+00:00 to2026-09-09T04:37:38Z): old7E1E0 matching TokenLaunched/PoolGraduated; current7ed728 logs. Exact topic counts: {"0x7e1eabd52ae29598e6483f72dcf1a70b14284db8": {}, "0x7ed598bcef8bd9edd8c97a195c6d13f40801ec7e": {"0x8d4aad4953d0ca700d468f3753aa14432d1b35b43ec6409f051fb6aa43a89607": 716, "0x0a44ef75df69c534f43cd6c1aa3ef8983065fe5fe79ef9e79f6494e6f258c259": 12}}. Matching token overlap0 because old has0. Shorter58265014–58266814 (04:34:36–04:37:38Z) agrees:old0,current36launch+1graduation. Successful result arrays, not errors interpreted as zero. Queries bounded to two windows, no production evidence insertion/backfill.

User falsifier met: proposed address emits no matching recent launches. Preserve existing observer; no code/test/deploy/restart/strategy/funding/Live changes. This does not prove old factory can never reactivate, nor full current-factory ingestion. Current factory volume and blocked index surface may explain coverage independently, but this task supplies no verified missing active factory. Do not claim mature53 low count solved. Future rotation requires authoritative source AND chain activity/ABI verification, separate frontiers/no-backfill.

Artifacts data/research/pons65/readme.txt, address code responses, Blockscout403 responses, window.json,summary.json,hour.json. No secrets. No runtime tests needed because no runtime change. RPC evidence is report-only, not BUY authority.
