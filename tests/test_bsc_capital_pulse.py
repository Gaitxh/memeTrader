from datetime import timedelta
from dataclasses import replace
import pytest
from memetrader.bsc_capital_pulse import ARM,PARENT,policy,qualifies
from memetrader.resource_bound_research import resource_policies
from memetrader.models import TokenCandidate
from memetrader.narrative_hold import max_hold
from test_resource_bound_store import setup_store,quote

@pytest.mark.parametrize('chain,b,s,v,expected',[
 ('bsc',6,4,10000,True),('bsc',9,6,15000,True),('bsc',6,4,9999,False),
 ('bsc',5,5,10000,False),('bsc',10,6,16000,False),('solana',7,3,10000,False),
 ('robinhood',7,3,10000,False),('bsc',0,0,10000,False),('bsc',None,3,10000,False),
 ('bsc',7,3,float('nan'),False)])
def test_proxy(chain,b,s,v,expected):assert qualifies(chain,b,s,v)==expected

def pulse_quote(token,at,created,price=1):
    q=quote(token,'pool',created,at,age_rate=True,price=price)
    q.raw['pair']['volume']={'m5':10000,'h1':11000}
    return replace(q,volume_5m_usd=10000)

def test_additive_next_frame_one_opportunity_and_29m_exit(tmp_path,monkeypatch):
    store,clock=setup_store(tmp_path,monkeypatch)
    parent=next(p for p in resource_policies() if p['arm_id']==PARENT)
    store.append_chain_meme_trader_policy(parent,activated_at=clock[0])
    before=store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)['definition_json']
    assert store.register_bsc_capital_pulse114()==0
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE arm_id=?',(ARM,)).fetchone()[0]==0
    # Historical contract fixture only; withdrawn production registrar above is inert.
    store.append_chain_meme_trader_policy(policy(parent),activated_at=clock[0])
    child=policy(parent)
    assert max_hold(None,{},child,clock[0])==29 and parent['max_hold_minutes']==30
    assert child['notional_usd']==5 and child['entry_filter']['max_concurrent_positions']==4
    assert (child['hard_stop_return'],child['trailing_activate_return'],child['trailing_drawdown'])==(-.2,.3,.15)
    token=TokenCandidate('bsc','0x'+'12'*20,'4Stock');created=int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
    def observe():store.observe_chain_meme_pattern(token,pulse_quote(token,clock[0],created),recorded_at=clock[0])
    clock[0]+=timedelta(seconds=16);observe()
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()[0]==0
    clock[0]+=timedelta(seconds=16);observe()
    p=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()
    pp=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(PARENT,)).fetchone()
    assert p and p['source_entry_fill_id']==pp['source_entry_fill_id'] and p['stake_usd']==5
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_cohort_enrollment_claims WHERE arm_id=?',(ARM,)).fetchone()[0]==1
    for _ in range(3):clock[0]+=timedelta(seconds=1);observe()
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()[0]==1
    assert store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)['definition_json']==before
    clock[0]+=timedelta(minutes=29)
    store.upsert_chain_meme_trader_market_mark(token,pulse_quote(token,clock[0],created),recorded_at=clock[0])
    store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])
    p=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()
    mark=store.db.execute('SELECT * FROM chain_meme_trader_marks WHERE id=?',(p['pending_mark_id'],)).fetchone()
    assert mark and mark['action']=='TIME_EXIT'
    pp=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(PARENT,)).fetchone()
    assert pp['pending_mark_id'] is None
    store.close()

def test_pulse_security_pending_is_one_reserved_opportunity(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from memetrader.preentry_safety import PreentrySafety
    store,clock=setup_store(tmp_path,monkeypatch)
    parent=next(p for p in resource_policies() if p['arm_id']==PARENT)
    store.append_chain_meme_trader_policy(parent,activated_at=clock[0])
    store.append_chain_meme_trader_policy(policy(parent),activated_at=clock[0])
    token=TokenCandidate('bsc','0x'+'34'*20,'4Stock');created=int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
    store.upsert_token(token)
    gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    for _ in range(5):
        clock[0]+=timedelta(seconds=1)
        store.observe_chain_meme_pattern(token,pulse_quote(token,clock[0],created),recorded_at=clock[0])
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()[0]==0
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_cohort_enrollment_claims WHERE arm_id=?',(ARM,)).fetchone()[0]==1
    assert len(gate.pending)==1
    store.close()
