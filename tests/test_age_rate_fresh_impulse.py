import sqlite3,json
from memetrader.age_rate_fresh_impulse import classify,PRIOR

def fixture():
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript('''CREATE TABLE chain_meme_trader_registrations(definition_version TEXT);
    INSERT INTO chain_meme_trader_registrations VALUES('v');
    CREATE TABLE chain_meme_trader_positions(definition_version,arm_id,shadow_cohort_id,token_id,opened_at,closed_at,status);
    CREATE TABLE chain_meme_trader_v6_cohorts(id,definition_version,pair_address);
    CREATE TABLE chain_meme_trader_trades(id,definition_version,arm_id,shadow_cohort_id,side,created_at,recorded_at);
    CREATE TABLE chain_meme_pattern_evidence(id,definition_version,token_id,pair_address,kind,observed_at,recorded_at,payload_json);''')
    db.execute("INSERT INTO chain_meme_trader_v6_cohorts VALUES(1,'v','0xAbC')")
    db.execute("INSERT INTO chain_meme_trader_positions VALUES('v',?,1,'bsc:T','2026-09-09T01:00:00+00:00',NULL,'open')",(PRIOR[0],))
    db.execute("INSERT INTO chain_meme_trader_trades VALUES(1,'v',?,1,'BUY','2026-09-09T01:00:00+00:00','2026-09-09T01:00:01+00:00')",(PRIOR[0],))
    return db

def read(db,at='2026-09-09T02:00:00+00:00',pool='0xabc'):
    return classify(db,'v','bsc:T',pool,at)

def test_prior_receipts_pool_and_future_close():
    db=fixture()
    assert read(db)['state']=='CONFLICT_PRIOR_OPEN'
    assert read(db,pool='other')['state']=='CLEAN_FIRST_IMPULSE'
    assert read(db,at='2026-09-09T01:00:00+00:00')['state']=='CLEAN_FIRST_IMPULSE'
    db.execute("UPDATE chain_meme_trader_positions SET status='closed',closed_at='2026-09-09T01:30:00+00:00'")
    db.execute("INSERT INTO chain_meme_trader_trades VALUES(2,'v',?,1,'SELL','2026-09-09T01:30:00+00:00','2026-09-09T03:00:00+00:00')",(PRIOR[0],))
    assert read(db)['state']=='CONFLICT_PRIOR_OPEN'
    db.execute("UPDATE chain_meme_trader_trades SET recorded_at='2026-09-09T01:30:01+00:00' WHERE id=2")
    assert read(db)['state']=='CONFLICT_PRIOR_CLOSED'
    db.close()

def test_reset_requires_later_persisted_episode_before_signal():
    db=fixture()
    db.execute("INSERT INTO chain_meme_pattern_evidence VALUES(1,'v','bsc:T','','rediscovery_episode','2026-09-09T01:40:00+00:00','2026-09-09T02:00:01+00:00',?)",(json.dumps({'episode':'REAWAKENING'}),))
    assert read(db)['state']=='CONFLICT_PRIOR_OPEN'
    db.execute("UPDATE chain_meme_pattern_evidence SET recorded_at='2026-09-09T01:40:01+00:00'")
    assert read(db)['state']=='RESET_CONFIRMED'
    db.execute("UPDATE chain_meme_pattern_evidence SET observed_at='2026-09-09T00:40:00+00:00'")
    assert read(db)['state']=='CONFLICT_PRIOR_OPEN'
    db.close()

def test_future_actual_fill_once_and_parent_terminal_comparator(tmp_path,monkeypatch):
    from datetime import timedelta
    from test_resource_bound_store import setup_store,quote
    from memetrader.resource_bound_research import resource_policies
    from memetrader.models import TokenCandidate,iso
    from memetrader.age_rate_fresh_impulse import KEY,PARENT,capture,resolve
    store,clock=setup_store(tmp_path,monkeypatch)
    parent=next(p for p in resource_policies() if p['arm_id']==PARENT)
    store.append_chain_meme_trader_policy(parent,activated_at=clock[0])
    assert store.get_kv(KEY,None) is None  # no historical seeding at registration
    token=TokenCandidate('solana','Fresh112Fixture','Fixture')
    created=int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
    for _ in range(2):
        clock[0]+=timedelta(seconds=16)
        store.observe_chain_meme_pattern(token,quote(token,'pool',created,clock[0],age_rate=True),recorded_at=clock[0])
    p=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(PARENT,)).fetchone()
    state=store.get_kv(KEY);assert len(state['pending'])==1
    row=state['pending'][0];assert row['source_entry_fill_id']==p['source_entry_fill_id']
    capture(store,p['definition_version'],p['shadow_cohort_id'],p['token_id'],row['signal_at'],p['source_entry_fill_id'])
    assert store.get_kv(KEY)['counts']=={'CLEAN_FIRST_IMPULSE':1}
    resolve(store);assert len(store.get_kv(KEY)['pending'])==1
    # Terminal fixture only: observer reads actual ledger PnL, never computes a replay.
    store.db.execute("UPDATE chain_meme_trader_positions SET status='closed',closed_at=?,close_reason='fixture',realized_pnl_usd=6 WHERE arm_id=?",(iso(clock[0]),PARENT))
    resolve(store);resolve(store)
    state=store.get_kv(KEY)
    assert state['pending']==[] and state['outcomes']['CLEAN_FIRST_IMPULSE']==dict(n=1,pnl=6.,positive=1,tails_ge_5u=1)
    assert state['recent'][0]['source_entry_fill_id']==p['source_entry_fill_id']
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_pattern_evidence WHERE kind='age_rate_fresh_impulse112_outcome'").fetchone()[0]==1
    store.close()
