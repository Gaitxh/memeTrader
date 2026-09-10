from datetime import timedelta
from types import SimpleNamespace
import json
import pytest
from memetrader.models import utcnow, iso, TokenCandidate
from memetrader.trajectory144 import Engine, ARMS
from memetrader.store import Store
from memetrader.preentry_safety import PreentrySafety
from test_l0_store import _snapshot
from test_trajectory144 import row


@pytest.mark.parametrize('arm', ARMS)
@pytest.mark.parametrize('exit_kind', ['hard','timeout'])
def test_real_producer_safety_later_buy_and_exit(tmp_path,monkeypatch,arm,exit_kind):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'pipeline.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period();store.register_chain_meme_cohort_experiments()
    clock[0]+=timedelta(seconds=1);start=clock[0];engine=Engine(start);store._trajectory144=engine
    gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    from memetrader.mode_learning144 import Coordinator
    learning=Coordinator(store);store._mode_learning144=learning
    token=TokenCandidate('bsc','0x'+'1'*40,'144 fixture','T144');pool='0x'+'2'*40;store.upsert_token(token)
    if arm==ARMS[2]:prices=[1,1.1,1.3,1.1,1.15,1.25,1.31]
    elif arm==ARMS[4]:prices=[1,1.05,1.1,1.2,.9,.91,.9,.91,.9,.91,.9,.91,.9,.91,1,1.1,1.2]
    else:prices=[1,1.01,1.05,1.14,1.25]
    def advance(price,seconds=10):
        clock[0]+=timedelta(seconds=seconds);i=int((clock[0]-start).total_seconds()/10)
        r=row(clock[0],i,price=price,buys=i*i,volume=100+i*i*20)
        engine.accept(r,clock[0]);snap=_snapshot(token,pool,clock[0],price=price)
        snap.volume_5m_usd=r['volume_5m_usd'];snap.buys_5m=r['buys_5m'];snap.sells_5m=r['sells_5m']
        return snap
    for price in prices:snap=advance(price)
    all_signals=learning.signals(engine.pools[(token.token_id,pool)]['features'],engine.signals_for(token.token_id,pool,clock[0]),clock[0]);assert arm in all_signals
    signals={arm:all_signals[arm]}
    store.observe_chain_meme_pattern(token,snap,recorded_at=clock[0],cohort_signals=signals)
    snap=advance(prices[-1]*1.001)
    store.observe_chain_meme_pattern(token,snap,recorded_at=clock[0],cohort_signals=signals)
    assert gate.pending
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==0
    gate.cache[(token.token_id,pool)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
    snap=advance(prices[-1]*1.002)
    with store._lock,store.db:gate.resume(token,snap,clock[0])
    positions=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchall()
    assert len(positions)==1 and positions[0]['stake_usd']==2
    opened=positions[0]['opened_at']
    assert opened>signals[arm]['recorded_at']
    snap=advance(prices[-1]*1.003)
    store.observe_chain_meme_pattern(token,snap,recorded_at=clock[0],cohort_signals=signals)
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==1
    if exit_kind=='timeout':clock[0]+=timedelta(minutes=31)
    for _ in range(2):
        clock[0]+=timedelta(seconds=2)
        price=.2 if exit_kind=='hard' else prices[-1]
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,pool,clock[0],price=price),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])
    p=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()
    assert p['status']=='closed' and int(p['amount_raw'])==0
    assert ('hard_stop' in p['close_reason']) if exit_kind=='hard' else ('max_hold' in p['close_reason'])
    assert learning.state['counts']['actual_BUY']==1
    learning.flush(clock[0]);assert learning.state['counts']['actual_terminal']==1
    assert store.get_kv(learning.key)['actual_groups'][arm][0]['realized_pnl_usd']==p['realized_pnl_usd']
    assert store.register_chain_meme_cohort_experiments()==0
    store.close()


def test_pending_security_reservations_obey_two_position_limit(tmp_path,monkeypatch):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    s=Store(tmp_path/'limits.sqlite3',initial_cash_usd=1000)
    s.activate_chain_meme_trader_funded_period();s.register_chain_meme_cohort_experiments()
    clock[0]+=timedelta(seconds=1);start=clock[0];e=Engine(start);s._trajectory144=e
    gate=PreentrySafety(s,SimpleNamespace(config={}));s._preentry_safety=gate
    for j in range(1,4):
        token=TokenCandidate('bsc','0x'+str(j)*40,'Slot','SLOT');pool='0x'+str(j+5)*40;s.upsert_token(token)
        for i in range(5):
            clock[0]+=timedelta(seconds=10)
            e.accept(row(clock[0],i,token=token.token_id,pool=pool,price=1+i*i*.02,buys=i*i,volume=100+i*i*20),clock[0])
        sig=e.signals_for(token.token_id,pool,clock[0])[ARMS[0]]
        s.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0],price=1.32),recorded_at=clock[0],cohort_signals={ARMS[0]:sig})
        clock[0]+=timedelta(seconds=5)
        e.accept(row(clock[0],5,token=token.token_id,pool=pool,price=1.33,buys=25,volume=650),clock[0])
        s.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0],price=1.33),recorded_at=clock[0],cohort_signals={ARMS[0]:sig})
    # Expiries are advanced explicitly only by the safety worker; reservations
    # remain authoritative while provider work is pending.
    assert len(gate.pending)==2
    assert s.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(ARMS[0],)).fetchone()[0]==0
    s.close()
