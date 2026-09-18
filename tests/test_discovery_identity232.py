import asyncio
from datetime import timedelta
from copy import deepcopy
import pytest
from memetrader.collectors import DexScreenerClient
from memetrader.models import TokenCandidate,utcnow,iso
from memetrader.runtime import Runtime
from memetrader.store import Store

ADDRESS='0x'+'Ab'*20


def links(chain='bsc',address=ADDRESS):
    raw={'item':{'chainId':chain,'tokenAddress':address}}
    return DexScreenerClient._source_link_rows(chain=chain,address=address,
        surface='token_profiles',role='identity',raw=raw,
        primary_url='https://example.org/token',links=[])


def test_normalize_metadata_identity_preserving_raw_evidence():
    raw=links()[0]
    assert raw['token_id']=='bsc:'+ADDRESS.lower()
    assert raw['address']==ADDRESS.lower()
    assert raw['raw']['item']['tokenAddress']==ADDRESS
    assert raw['verification_status']=='provider_metadata'
    assert raw['role']=='identity'


def test_solana_case_is_never_lowered():
    value='AbCdEfGhJkLmNpQrStUvWxYz123456789abcd'
    raw=links('solana',value)[0]
    assert raw['token_id']=='solana:'+value and raw['address']==value


def test_known_canonical_token_is_not_rediscovered_as_a_new_token(tmp_path):
    store=Store(tmp_path/'discovery.sqlite3')
    token=TokenCandidate('bsc',ADDRESS,'Known')
    store.upsert_token(token)
    runtime=Runtime.__new__(Runtime);runtime.store=store
    async def run():
        idle=asyncio.Event();idle.set();runtime._chain_meme_active_idle=lambda:idle
        rid=store.start_token_discovery_round(provider='dexscreener',surface='token_profiles',mode='poll',chain_scope='bsc')
        count,first=await runtime._persist_dex_discovery_links(rid,links(),{'bsc'})
        assert count==1 and first==0
        row=store.db.execute('SELECT token_id,first_local_discovery FROM token_discovery_exposures WHERE round_id=?',(rid,)).fetchone()
        assert row['token_id']==token.token_id and row['first_local_discovery']==0
        assert store.db.execute('SELECT COUNT(*) FROM token_detail_hydration WHERE token_id=?',(token.token_id,)).fetchone()[0]==1
    try:asyncio.run(run())
    finally:store.close()


def test_case_variants_share_one_runtime_discovery_item(tmp_path):
    store=Store(tmp_path/'dedup.sqlite3');runtime=Runtime.__new__(Runtime);runtime.store=store
    async def run():
        idle=asyncio.Event();idle.set();runtime._chain_meme_active_idle=lambda:idle
        rid=store.start_token_discovery_round(provider='dexscreener',surface='token_profiles',mode='poll',chain_scope='bsc')
        count,first=await runtime._persist_dex_discovery_links(rid,links()+links(address=ADDRESS.lower()),{'bsc'})
        assert count==1 and first==1
        assert store.db.execute('SELECT COUNT(*) FROM token_discovery_exposures WHERE round_id=?',(rid,)).fetchone()[0]==1
    try:asyncio.run(run())
    finally:store.close()
