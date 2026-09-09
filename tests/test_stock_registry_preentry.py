import sqlite3
from datetime import timedelta
import pytest
from memetrader.models import iso,utcnow
from memetrader.preentry_safety import stock_registry_evidence

@pytest.mark.parametrize('chain,address,offset,count,expected',[
 ('robinhood','0xAbC',-1,1,'EXCLUDED_STOCK_TOKEN'),
 ('robinhood','0xdef',-1,1,'NOT_LISTED'),
 ('robinhood','0xabc',1,1,'UNKNOWN'),
 ('robinhood','0xabc',-1,0,'UNKNOWN'),
 ('bsc','0xabc',-1,1,None),('solana','AbC',-1,1,None)])
def test_registry_asof_and_scope(chain,address,offset,count,expected):
 c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
 c.executescript('CREATE TABLE robinhood_stock_token_registry_runs(id,source_url,requested_at,completed_at,recorded_at,deployment_count);CREATE TABLE robinhood_stock_token_registry_entries(run_id,contract_address,chain_id,recorded_at);')
 now=utcnow();at=iso(now+timedelta(seconds=offset))
 c.execute('insert into robinhood_stock_token_registry_runs values(1,?,?,?,?,?)',('https://api.robinhood.com/rhj/assets',at,at,at,count))
 c.execute("insert into robinhood_stock_token_registry_entries values(1,'0xabc',4663,?)",(at,))
 result=stock_registry_evidence(c,chain+':'+address,now)
 assert (result['status'] if result else None)==expected
 c.execute('delete from robinhood_stock_token_registry_runs')
 if chain=='robinhood':assert stock_registry_evidence(c,chain+':'+address,now)['status']=='UNKNOWN'
 c.close()

def test_later_recording_not_backdated_and_latest_replaces_old():
 c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
 c.executescript('CREATE TABLE robinhood_stock_token_registry_runs(id,source_url,requested_at,completed_at,recorded_at,deployment_count);CREATE TABLE robinhood_stock_token_registry_entries(run_id,contract_address,chain_id,recorded_at);')
 now=utcnow();old=iso(now-timedelta(seconds=2));later=iso(now+timedelta(seconds=2))
 c.execute('insert into robinhood_stock_token_registry_runs values(1,?,?,?,?,1)',('https://api.robinhood.com/rhj/assets',old,old,later))
 c.execute("insert into robinhood_stock_token_registry_entries values(1,'0xabc',4663,?)",(old,))
 assert stock_registry_evidence(c,'robinhood:0xabc',now)['status']=='UNKNOWN'
 c.execute('update robinhood_stock_token_registry_runs set recorded_at=?',(old,))
 at=iso(now-timedelta(seconds=1))
 c.execute('insert into robinhood_stock_token_registry_runs values(2,?,?,?,?,1)',('https://api.robinhood.com/rhj/assets',at,at,at))
 c.execute("insert into robinhood_stock_token_registry_entries values(2,'0xdef',4663,?)",(at,))
 assert stock_registry_evidence(c,'robinhood:0xabc',now)['status']=='NOT_LISTED'

def test_common_guard_veto_precedes_other_safety(monkeypatch):
 from types import SimpleNamespace
 from memetrader.preentry_safety import PreentrySafety
 c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
 c.execute('create table token_snapshots(id,raw_json,observed_at)')
 now=iso();c.execute('insert into token_snapshots values(1,?,?)',('{"pair":{"pairAddress":"0xpool"}}',now))
 gate=PreentrySafety.__new__(PreentrySafety);gate.store=SimpleNamespace(db=c)
 recorded=[];gate.record=lambda item,status,assessment:recorded.append((status,assessment))
 monkeypatch.setattr('memetrader.preentry_safety.stock_registry_evidence',lambda *a:{'status':'EXCLUDED_STOCK_TOKEN','source_at':now,'reason':'official_robinhood_stock_token_not_meme'})
 assert not gate.guard(version='v',cohort_id=1,token_id='robinhood:0xabc',snapshot_id=1,filled_at=now,definition={'policy_notional_usd':5},reason='fixture')
 assert recorded[0][0]=='REJECT_SCOPE' and recorded[0][1]['not_a_scam_claim']
