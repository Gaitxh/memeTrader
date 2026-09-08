import pytest
import json
from datetime import timedelta
from memetrader.flap_successor import KEY, PORTAL, resolve
from memetrader.models import TokenCandidate, utcnow, iso
from memetrader.store import Store
from test_chain_meme_pool_identity import _seed_position, _snapshot

OLD="0x"+"1"*40
NEW="0x"+"2"*40

@pytest.mark.parametrize("pending", [False, True])
def test_authenticated_successor_next_frame_exit_preserves_entry(tmp_path, monkeypatch, pending):
    store=Store(tmp_path/"flap.sqlite3", initial_cash_usd=1000)
    token=TokenCandidate("bsc","0x"+"3"*40,"Flap","F",source="dexscreener")
    import test_chain_meme_pool_identity as fixture
    monkeypatch.setattr(fixture,"TokenCandidate",lambda *a,**k: token)
    version,policy,old_token,cohort=_seed_position(store,entry_pair=OLD)
    at=utcnow()
    if pending:
        t=at-timedelta(seconds=4)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,pair=OLD,price=2,liquidity=10000,at=t),recorded_at=t)
        assert store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=t)==1
    link=dict(portal=PORTAL,chain_id=56,status=4,token_id=token.token_id,original_pool=OLD,successor_pool=NEW,observed_at=iso(at-timedelta(seconds=3)),ingested_at=iso(at-timedelta(seconds=2)),recorded_at=iso(at))
    with store.db:
        store.db.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)",(KEY+token.token_id+":"+OLD,json.dumps(link),iso(at)))
    assert resolve(store.db,token.token_id,OLD,iso(at)) is None
    targets=store.chain_meme_trader_market_mark_targets(definition_version=version)
    assert next(x for x in targets if x["token_id"]==token.token_id)["entry_pair_addresses"]==NEW
    for offset,expected in ((-1,0),(1,1),(2,0)):
        t=at+timedelta(seconds=offset)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,pair=NEW,price=2,liquidity=10000,at=t),recorded_at=t)
        n=store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=t)
        if offset in (-1,1): assert n==(0 if pending else expected)
    pos=store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE token_id=?",(token.token_id,)).fetchone()
    assert pos["status"]=="closed"
    assert store.db.execute("SELECT pair_address FROM chain_meme_trader_v6_cohorts WHERE id=?",(cohort,)).fetchone()[0]==OLD
    mark=store.db.execute("SELECT * FROM chain_meme_trader_marks WHERE shadow_cohort_id=? AND definition_version=?",(cohort,version)).fetchone()
    assert mark["market_pair_address"]==NEW and mark["market_post_pair_address"]==NEW
    assert json.loads(mark["trigger_evidence_json"])["official_migration_successor"]==link
    assert resolve(store.db,token.token_id,"0x"+"9"*40,iso(at+timedelta(seconds=3))) is None


def test_invalid_receipt_cannot_authenticate(tmp_path):
    import sqlite3
    db=sqlite3.connect(":memory:")
    db.execute("CREATE TABLE kv(key TEXT,value_json TEXT)")
    token="bsc:0x"+"3"*40
    at=iso(utcnow())
    base=dict(portal=PORTAL,chain_id=56,status=4,token_id=token,original_pool=OLD,successor_pool=NEW,observed_at=at,ingested_at=at,recorded_at=at)
    for field,value in (("portal",OLD),("status",1),("successor_pool","0x"+"0"*40),("chain_id",1),("token_id","bsc:wrong"),("recorded_at","2099-01-01T00:00:00Z")):
        db.execute("DELETE FROM kv")
        db.execute("INSERT INTO kv VALUES(?,?)",(KEY+token+":"+OLD,json.dumps(dict(base,**{field:value}))))
        assert resolve(db,token,OLD,iso(utcnow()+timedelta(seconds=5))) is None
