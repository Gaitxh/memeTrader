from datetime import timedelta
from test_chain_meme_performance import _open_v22, _insert_position
from memetrader.models import utcnow,TokenSnapshot


def test_empty_accounts_quiesce_and_new_receipt_invalidates_totals(tmp_path):
    store,d,p=_open_v22(tmp_path,'quiet.sqlite3');v=d['version'];t=utcnow();arm=p['arm_id']
    store.record_chain_meme_trader_account_snapshots(definition_version=v,now=t)
    traced=[];store.db.set_trace_callback(traced.append)
    assert store.record_chain_meme_trader_account_snapshots(definition_version=v,now=t+timedelta(seconds=61))==0
    store.db.set_trace_callback(None)
    assert not any('SUM(net_cash_flow_usd)' in q and 'GROUP BY arm_id' in q for q in traced)
    _insert_position(store,version=v,arm_id=arm,opened_at=t+timedelta(seconds=62),status='closed',sell_gross_usd=15)
    assert store.record_chain_meme_trader_account_snapshots(definition_version=v,now=t+timedelta(seconds=80))==1
    row=store.db.execute('SELECT * FROM chain_meme_trader_account_snapshots WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1',(v,arm)).fetchone()
    assert row['cash_usd']==995 and row['realized_pnl_usd']==-5 and row['closed_position_count']==1
    assert store.record_chain_meme_trader_account_snapshots(definition_version=v,now=t+timedelta(seconds=141))==0
    store.close()


def test_cached_ledger_preserves_open_mark_values_and_state_change_curve(tmp_path):
    store,d,p=_open_v22(tmp_path,'marks.sqlite3');v=d['version'];t=utcnow();arm=p['arm_id']
    token,_,_,_=_insert_position(store,version=v,arm_id=arm,opened_at=t-timedelta(seconds=1))
    values=[]
    for i,price in enumerate([1.,2.,.5]):
        now=t+timedelta(seconds=11*i)
        store.upsert_chain_meme_trader_market_mark(token,TokenSnapshot('solana',token.address,price,100000,100000,100,5,2,
            observed_at=now,ingested_at=now,provider='dexscreener',raw={'pair':{'pairAddress':'pair-A'}}),recorded_at=now)
        store.record_chain_meme_trader_account_snapshots(definition_version=v,now=now)
        row=store.db.execute('SELECT * FROM chain_meme_trader_account_snapshots WHERE definition_version=? AND arm_id=? ORDER BY id DESC LIMIT 1',(v,arm)).fetchone()
        values.append(row['indicative_equity_usd'])
        assert row['open_position_count']==1 and row['indicative_position_count']==1
    assert values==[999.2,1018.4,989.6]
    # Removing identical points cannot change the state-change drawdown sequence.
    assert max(values)-values[-1]==max([values[0]]*6+[values[1]]*6+[values[2]])-values[-1]
    store.close()
