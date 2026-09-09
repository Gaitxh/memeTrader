import json,sqlite3
from datetime import timedelta
from types import SimpleNamespace
import pytest
from memetrader.models import iso,utcnow
from memetrader.preentry_safety import rwa_metadata_scope,PreentrySafety

def row(name,chain='bsc'):
    at=iso(utcnow()-timedelta(seconds=1))
    return dict(token_id=chain+':0xabc',provider='dexscreener',observed_at=at,ingested_at=at,recorded_at=at,
        raw_json=json.dumps({'pair':{'chainId':chain,'pairAddress':'pool','baseToken':{'address':'0xabc','name':name,'symbol':'NET'}}}))

@pytest.mark.parametrize('chain',['bsc','robinhood','solana','base','ethereum'])
@pytest.mark.parametrize('name',['Cloudflare, Inc. Class A Common Stock (Derivatives)','AST SpaceMobile Tokenized Stock (Reality)','Example Corp. Class B Common Stock (Derivatives)'])
def test_standardized_security_names(chain,name):
    r=row(name,chain);a=rwa_metadata_scope(r,r['token_id'],utcnow())
    assert a['status']=='EXCLUDED_NON_MEME_RWA' and a['not_a_scam_claim']

@pytest.mark.parametrize('name',['4Stock','STOCKMEME','MemeETF','Game Stock','ETF','Cloudflare Meme','Tokenized Stock','AST SpaceMobile Tokenized Stock (Reality) Meme',None,''])
def test_meme_and_ambiguous_names_nonblocking(name):
    r=row(name);assert rwa_metadata_scope(r,r['token_id'],utcnow())['status']=='UNKNOWN'

def test_future_and_wrong_identity_metadata_nonblocking():
    r=row('AST SpaceMobile Tokenized Stock (Reality)')
    assert rwa_metadata_scope(r,'bsc:other',utcnow())['status']=='UNKNOWN'
    r['recorded_at']=iso(utcnow()+timedelta(seconds=10))
    assert rwa_metadata_scope(r,r['token_id'],utcnow())['status']=='UNKNOWN'

def test_common_scope_before_provider_authorization():
    r=row('AST SpaceMobile Tokenized Stock (Reality)');db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE token_snapshots(id,token_id,provider,observed_at,ingested_at,recorded_at,raw_json)')
    db.execute('INSERT INTO token_snapshots VALUES(1,?,?,?,?,?,?)',tuple(r[k] for k in ['token_id','provider','observed_at','ingested_at','recorded_at','raw_json']))
    gate=PreentrySafety.__new__(PreentrySafety);gate.store=SimpleNamespace(db=db)
    events=[];gate.record=lambda item,status,assessment:events.append((status,assessment))
    assert gate.guard(version='v',cohort_id=1,token_id=r['token_id'],snapshot_id=1,filled_at=iso(),definition={'policy_notional_usd':5},reason='fixture') is False
    assert events[0][0]=='REJECT_SCOPE' and events[0][1]['classification_only']
    db.close()
