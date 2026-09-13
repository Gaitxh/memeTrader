import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace

from memetrader.held_flap_recovery import KEY, candidates, recover_one


def test_candidates_skip_healthy_pool_and_keep_unresolved_stale(tmp_path):
    db=tmp_path/'x.sqlite'; c=sqlite3.connect(db)
    c.executescript('CREATE TABLE chain_meme_trader_positions(token_id,status,entry_snapshot_id);CREATE TABLE token_snapshots(id,raw_json);CREATE TABLE kv(key,value_json);CREATE TABLE chain_meme_trader_pool_marks(token_id,pair_address,liquidity_usd,observed_at);')
    token='bsc:0x'+'1'*40; pool='0x'+'2'*40
    raw=json.dumps({'pair':{'pairAddress':pool,'chainId':'bsc','dexId':'flapsh','baseToken':{'address':token[4:]}}})
    c.execute('INSERT INTO token_snapshots VALUES(1,?)',(raw,));c.execute("INSERT INTO chain_meme_trader_positions VALUES(?,'open',1)",(token,));c.execute("INSERT INTO chain_meme_trader_pool_marks VALUES(?,?,?,?)",(token,pool,1000,datetime.now(timezone.utc).isoformat()));c.commit()
    assert candidates(db)==[]
    c.execute("UPDATE chain_meme_trader_pool_marks SET observed_at='2026-01-01T00:00:00Z'");c.commit()
    assert candidates(db)==[(token,pool)]
    c.execute('UPDATE chain_meme_trader_pool_marks SET liquidity_usd=NULL');c.commit()
    assert candidates(db)==[(token,pool)]


def test_recovery_retry_bound_and_no_history_mutation(monkeypatch, tmp_path):
    calls=[]
    class Store:
        path=tmp_path/'none.sqlite'; db=sqlite3.connect(':memory:')
        def __init__(self): self.values={}
        def get_kv(self,k,d): return self.values.get(k,d)
        def set_kv(self,k,v): self.values[k]=v
    store=Store(); runtime=SimpleNamespace(config={'mode':'paper','live':{'enabled':False}},store=store,http=SimpleNamespace(proxy_url=None))
    monkeypatch.setattr('memetrader.held_flap_recovery.candidates',lambda *_:[('bsc:0x'+'1'*40,'0x'+'2'*40)])
    monkeypatch.setattr('memetrader.held_flap_recovery.prove',lambda *_:calls.append(1) or (_ for _ in ()).throw(ValueError('wrong identity')))
    assert asyncio.run(recover_one(runtime))['status']=='failed'
    assert asyncio.run(recover_one(runtime))['status']=='none' and len(calls)==1
    assert store.db.execute("select count(*) from sqlite_master where type='table'").fetchone()[0]==0


def test_proof_calldata_strips_bsc_token_0x_and_checks_pool_identity(monkeypatch):
    import memetrader.held_flap_recovery as mod
    token='bsc:0x'+'1'*40; old='0x'+'2'*40; new='0x'+'3'*40; seen=[]
    abi='0x'+'0'*64*15
    words=['0'*64 for _ in range(15)];words[0]=f'{4:064x}';words[13]=new[2:].rjust(64,'0');abi='0x'+''.join(words)
    word=lambda a:'0x'+'0'*24+a[2:]
    replies=[['0x38','0x100'],[{'number':'0xec','hash':'h','timestamp':hex(int(datetime.now(timezone.utc).timestamp()))},abi,word(token[4:]),word('0x'+'4'*40)],[word(token[4:]),word('0x'+'4'*40),{'number':'0xec','hash':'h'}]]
    def batch(_client,calls): seen.append(calls);return replies.pop(0)
    monkeypatch.setattr(mod,'_batch',batch)
    result=mod.prove(token,old,None)
    assert result['successor_pool']==new
    assert seen[1][1][1][0]['data']==mod.GET_TOKEN_V6+token[4:].removeprefix('0x').rjust(64,'0')


def test_oldest_unattempted_pool_gets_probe_before_repeated_first_pool(monkeypatch, tmp_path):
    import memetrader.held_flap_recovery as mod
    first=('bsc:0x'+'1'*40,'0x'+'2'*40); second=('bsc:0x'+'3'*40,'0x'+'4'*40)
    calls=[]; state={'pools':{first[0]+':'+first[1]:{'at':1,'status':'failed'}}}
    store=SimpleNamespace(path=tmp_path/'unused',get_kv=lambda *_:state,set_kv=lambda *_:None)
    runtime=SimpleNamespace(config={'mode':'paper'},store=store,http=SimpleNamespace(proxy_url=None))
    monkeypatch.setattr(mod,'candidates',lambda *_:[first,second])
    def failed(token,pool,proxy):
        calls.append((token,pool));raise ValueError('not migrated')
    monkeypatch.setattr(mod,'prove',failed)
    assert asyncio.run(recover_one(runtime))['status']=='failed'
    assert calls==[second]


def test_success_writes_link_only_for_still_held_exact_binding(monkeypatch, tmp_path):
    import memetrader.held_flap_recovery as mod
    token='bsc:0x'+'1'*40; pool='0x'+'2'*40; successor='0x'+'3'*40
    db=sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE chain_meme_trader_positions(token_id,status,entry_snapshot_id);'
        'CREATE TABLE token_snapshots(id,raw_json);CREATE TABLE kv(key PRIMARY KEY,value_json);')
    raw=json.dumps({'pair':{'pairAddress':pool,'chainId':'bsc','dexId':'flapsh','baseToken':{'address':token[4:]}}})
    db.execute('INSERT INTO token_snapshots VALUES(1,?)',(raw,))
    db.execute("INSERT INTO chain_meme_trader_positions VALUES(?,'open',1)",(token,))
    class LocalStore:
        path=tmp_path/'unused.sqlite'
        def get_kv(self,key,default):
            row=db.execute('SELECT value_json FROM kv WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row else default
        def set_kv(self,key,value):
            db.execute('INSERT OR REPLACE INTO kv VALUES(?,?)',(key,json.dumps(value)))
    store=LocalStore();store.db=db
    runtime=SimpleNamespace(config={'mode':'paper','live':{'enabled':False}},store=store,http=SimpleNamespace(proxy_url=None))
    monkeypatch.setattr(mod,'candidates',lambda *_:[(token,pool)])
    monkeypatch.setattr(mod,'prove',lambda *_:{'successor_pool':successor})
    before=list(db.execute('SELECT * FROM chain_meme_trader_positions'))
    assert asyncio.run(recover_one(runtime))['status']=='linked'
    assert store.get_kv(KEY+token+':'+pool,{})['successor_pool']==successor
    assert list(db.execute('SELECT * FROM chain_meme_trader_positions'))==before
    db.execute('DELETE FROM kv')
    db.execute("UPDATE chain_meme_trader_positions SET status='closed'")
    assert asyncio.run(recover_one(runtime))['status']=='binding_changed'
    assert store.get_kv(KEY+token+':'+pool,None) is None
