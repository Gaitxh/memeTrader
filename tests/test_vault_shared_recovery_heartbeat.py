import asyncio
from types import SimpleNamespace

from memetrader.runtime import Runtime


def test_shared_pattern_vault_update_recovers_same_source_health():
    async def run():
        runtime = Runtime.__new__(Runtime)
        runtime._stop = asyncio.Event()
        async def stream(targets):
            yield dict(observer_version='chain-pattern-exact/v1',token_id='solana:x',
                       pool_address='p',pool_target_id='target')
            raise asyncio.CancelledError()
        calls=[]
        runtime.held_accounts=SimpleNamespace(stream=stream)
        runtime._pattern_vault_tracker=SimpleNamespace(push=lambda update: dict(
            observed_at='2026-09-05T21:00:00Z',observer_state='HEALTHY'))
        runtime._chain_meme_v21_vault_last_heartbeat=-100
        runtime.store=SimpleNamespace(record_chain_meme_pattern_evidence=lambda *a,**k:1,
            heartbeat=lambda *a,**k:calls.append((a,k)))
        try:
            await runtime.chain_meme_v21_vault_shadow_loop(v22=True)
        except asyncio.CancelledError:
            pass
        assert calls==[(('chain-meme-v22-vault-shadow',),dict(item=True,error=''))]
    asyncio.run(run())
