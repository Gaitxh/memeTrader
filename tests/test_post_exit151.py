import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from math import ceil
import sqlite3
import threading
from types import SimpleNamespace as Obj

import pytest
from memetrader.post_exit151 import PostExitObservations, due_windows
from memetrader.models import iso

NOW = datetime(2026,9,13,5,tzinfo=timezone.utc)


def store_at(path):
    c=sqlite3.connect(path); c.row_factory=sqlite3.Row
    c.executescript('CREATE TABLE chain_meme_trader_positions(token_id,closed_at,entry_snapshot_id,shadow_cohort_id);'
        'CREATE INDEX closed_idx ON chain_meme_trader_positions(closed_at);'
        'CREATE TABLE token_snapshots(id,raw_json);'
        'CREATE TABLE chain_meme_trader_v6_cohorts(id,token_id,pair_address);'
        'CREATE TABLE chain_meme_trader_market_mark_history(token_id,chain,address,pair_address,provider,price_usd,'
        'liquidity_usd,volume_5m_usd,buys_5m,sells_5m,observed_at,recorded_at,status,failure_kind);')
    return Obj(db=c,_lock=threading.RLock())


def quote(pool='Pool', observed=NOW):
    token=Obj(token_id='solana:Token',chain='solana',address='Token')
    snap=Obj(observed_at=observed,price_usd=1.,liquidity_usd=1000.,volume_5m_usd=1.,buys_5m=1,sells_5m=1,
        raw={'pair':dict(pairAddress=pool,chainId='solana',baseToken={'address':'Token'})})
    return token,snap


@pytest.mark.parametrize('n',[0,1,28,29,30,31,60])
def test_spare_batch_shape_and_bounded_selection(n):
    m=PostExitObservations()
    m.reload([(f'solana:T{i}','Pool',NOW) for i in range(200)],NOW)
    before=[str(i) for i in range(n)]
    after,selected,extras=m.extend('solana',before,NOW)
    assert ceil(len(after)/30)==ceil(n/30)
    assert len(extras)<=1 and len(m.windows)<=96
    assert after[:n]==before
    if selected:
        assert not m.extend('solana',before,NOW)[1] == selected


@pytest.mark.parametrize('pool,offset',[('wrong',0),('Pool',-16),('Pool',1)])
def test_no_wrong_pool_stale_or_future_evidence(tmp_path,pool,offset):
    s=store_at(tmp_path/'db'); m=PostExitObservations()
    token,snap=quote(pool,NOW+timedelta(seconds=offset))
    m.response(s,{token.token_id:(token,snap)},[(token.token_id,'Pool',NOW-timedelta(seconds=20))],NOW,lambda _:snap)
    assert s.db.execute('SELECT COUNT(*) FROM chain_meme_trader_market_mark_history').fetchone()[0]==0
    s.db.close()


def test_restart_reconstructs_queue_and_fanout_quote_is_one_row(tmp_path):
    path=tmp_path/'db'; s=store_at(path)
    for i in range(3):
        s.db.execute('INSERT INTO chain_meme_trader_positions VALUES(?,?,NULL,1)',('solana:Token',iso(NOW-timedelta(minutes=15))))
    s.db.execute('INSERT INTO chain_meme_trader_v6_cohorts VALUES(1,?,?)',('solana:Token','Pool')); s.db.commit()
    windows=due_windows(path,NOW)
    assert len(windows)==1
    m=PostExitObservations(); m.reload(windows,NOW)
    token,snap=quote()
    m.response(s,{token.token_id:(token,snap)},windows,NOW,lambda _:snap)
    assert m.counts['history_rows']==1 and not m.windows
    assert due_windows(path,NOW)==[]
    s.db.close()


@pytest.mark.parametrize('high,fresh,allowed,expected',[(False,True,True,1),(True,True,True,0),(False,False,True,0),(False,True,False,0)])
def test_runtime_real_caller_isolation_and_no_extra_http(tmp_path,monkeypatch,high,fresh,allowed,expected):
    from memetrader.runtime import Runtime, DexScreenerClient
    async def run():
        runtime=Runtime.__new__(Runtime); runtime.chain_meme_trader_only=True
        runtime.store=store_at(tmp_path/'db'); runtime._post_exit151=PostExitObservations()
        runtime._post_exit151.reload([('solana:Token','Pool',NOW)],NOW)
        runtime._dex_quote_backoff_until=0; runtime._dex_quote_failure_streak=0
        @asynccontextmanager
        async def slot(**kwargs): yield True
        runtime._dex_quote_slot=slot; calls=[]; remembered=[]
        token,snap=quote()
        async def fetch(chain,addresses):
            calls.append(list(addresses))
            return {token.token_id:(token,snap)} if 'Token' in addresses else {}
        runtime.dex=Obj(batch_quote_fresh=fetch,batch_quote=fetch)
        runtime._remember_pattern_quotes=lambda q,**kwargs: remembered.append(q)
        monkeypatch.setattr('memetrader.runtime.utcnow',lambda:NOW)
        monkeypatch.setattr(DexScreenerClient,'_snapshot',lambda _:snap)
        result=await runtime._dex_batch_quote('solana',['legacy'],fresh=fresh,high_priority=high,allow_shared_spares149=allowed)
        assert len(calls)==1 and len(calls[0])==1+expected
        assert result=={} and all(not x for x in remembered)
        assert runtime._post_exit151.counts['history_rows']==expected
        runtime.store.db.close()
    asyncio.run(run())
