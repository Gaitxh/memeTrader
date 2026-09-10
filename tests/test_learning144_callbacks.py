"""Actual passive callback delivery, without provider requests or forced fills."""
import asyncio
from collections import deque
from datetime import timedelta
import json

import pytest

from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.mode_learning144 import Coordinator, capture, train
from memetrader.runtime import Runtime
from memetrader.store import Store
from memetrader.trajectory144 import Engine
from test_l0_store import _snapshot


@pytest.mark.parametrize('floor_failure', [False, True])
def test_passive_only_frames_advance_old_episode_without_snapshot_writes(tmp_path, monkeypatch, floor_failure):
    start=utcnow(); clock=[start]
    for module in ('runtime','models','store'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'callbacks.sqlite3',initial_cash_usd=1000)
    learning=Coordinator(store);store._mode_learning144=learning
    token=TokenCandidate('bsc','0x'+'1'*40,'Callback','CB');pool='0x'+'2'*40
    capture(learning.state,episode_key='e',token_id=token.token_id,pair_address=pool,
        chain='bsc',age_bucket='0_300',mode='fast',features={},decision_at=iso(start),
        observed_at=iso(start),ingested_at=iso(start),recorded_at=iso(start))
    runtime=Runtime.__new__(Runtime);runtime.store=store
    store._trajectory144=Engine(start)
    runtime.config={'paper':{'max_quote_age_seconds':45}}
    runtime._cohort_started_at=start;runtime._cohort_state={};runtime._cohort_saved_at=start
    # Held work is busy: no cohort projection, but already acquired batches drain.
    idle=asyncio.Event();runtime._chain_meme_active_idle=lambda:idle
    monkeypatch.setattr('memetrader.cohort_experiments.consume_passive_cohort_batch',
        lambda frames,state,**kw:(state,{}))
    monkeypatch.setattr(store,'observe_chain_meme_pattern',lambda *a,**k:pytest.fail('Unexpected projection'))
    original_signals=learning.signals
    def capture_from_this_batch(features,signals,now):
        capture(learning.state,episode_key='same-batch',token_id=token.token_id,pair_address=pool,
            chain='bsc',age_bucket='0_300',mode='fast',features=features,decision_at=iso(now),
            observed_at=features['observed_at'],ingested_at=features['ingested_at'],
            recorded_at=features['recorded_at'])
        return original_signals(features,signals,now)
    monkeypatch.setattr(learning,'signals',capture_from_this_batch)

    async def deliver(second,price=2,liquidity=2000):
        received=start+timedelta(seconds=second);clock[0]=received+timedelta(seconds=2)
        snap=_snapshot(token,pool,received,price=price,liquidity=liquidity)
        snap.ingested_at=None
        runtime._cohort_batches=deque([(received,[(token,snap)])])
        await runtime.chain_meme_cohort_observer_once()
        assert not runtime._cohort_batches
        return snap

    async def run():
        await deliver(1,price=1)
        e=learning.state['episodes']['e']
        assert e['entry'] is not None
        assert e['entry']['price_usd']==1
        assert e['entry']['receipt_source']=='passive'
        assert learning.state['episodes']['same-batch']['entry'] is None
        for second in range(31,302,30):
            await deliver(second,price=None if floor_failure and second==31 else 2,
                          liquidity=10 if floor_failure and second==31 else 2000)
        label=e['results']['5']
        assert label['status']==('UNKNOWN' if floor_failure else 'OBSERVED')
        assert label['available_at']==iso(start+timedelta(seconds=303))
        assert store.db.execute('SELECT COUNT(*) FROM token_snapshots').fetchone()[0]==0
        if floor_failure:
            assert e['first_floor']['liquidity_usd']==10
        else:
            assert label['costed_return']==pytest.approx(2*.96/1.04-1)
        before=json.dumps(e,sort_keys=True)
        # The same receipt later reaching the Store callback cannot advance twice.
        snap=_snapshot(token,pool,start+timedelta(seconds=301),price=2)
        learning.observe(token.token_id,snap,snap.ingested_at,clock[0])
        assert json.dumps(e,sort_keys=True)==before
        assert train(learning.state,cutoff_at=iso(clock[0]))['consumed']==1
        assert train(learning.state,cutoff_at=iso(clock[0]))['consumed']==0
    try:asyncio.run(run())
    finally:store.close()


@pytest.mark.parametrize('mismatch',['token','raw_base','raw_chain'])
def test_learning_callback_rejects_identity_mismatch_without_advancing(tmp_path,mismatch):
    store=Store(tmp_path/'identity.sqlite3',initial_cash_usd=1000)
    learning=Coordinator(store);now=utcnow()
    token=TokenCandidate('bsc','0x'+'1'*40,'Identity','ID');pool='0x'+'2'*40
    capture(learning.state,episode_key='e',token_id=token.token_id,pair_address=pool,
        chain='bsc',age_bucket='0_300',mode='fast',features={},decision_at=iso(now),
        observed_at=iso(now),ingested_at=iso(now),recorded_at=iso(now))
    later=now+timedelta(seconds=1);snap=_snapshot(token,pool,later)
    if mismatch=='token':snap.address='0x'+'3'*40
    elif mismatch=='raw_base':snap.raw['pair']['baseToken']['address']='0x'+'3'*40
    else:snap.raw['pair']['chainId']='solana'
    try:
        learning.observe(token.token_id,snap,later,later,source='passive')
        assert learning.state['episodes']['e']['entry'] is None
        assert learning.state['counts']['callback_identity_rejected']==1
    finally:store.close()
