import json
from datetime import timedelta
import pytest
from memetrader.age_rate_revisions import age_rate_revision_policies
from memetrader.models import TokenCandidate
from memetrader.resource_bound_research import resource_policies
from test_resource_bound_store import setup_store, quote


def fixture(tmp_path,monkeypatch):
    store,clock=setup_store(tmp_path,monkeypatch)
    parent=next(p for p in resource_policies() if p['arm_id']=='resource_age_rate_candidate_v1')
    policies=[parent,*age_rate_revision_policies(parent)]
    original=store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)['definition_json']
    store.append_chain_meme_trader_policy(parent,activated_at=clock[0])
    assert store.register_age_rate_revisions90()==1
    # Reconstruct the already-registered withdrawn experiment, not a new runtime arm.
    store.append_chain_meme_trader_policy(policies[1],activated_at=clock[0])
    assert store.register_age_rate_revisions90()==0
    assert store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)['definition_json']==original
    token=TokenCandidate('solana','RevisionFixture','Fixture')
    created=int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
    for _ in range(2):
        clock[0]+=timedelta(seconds=16)
        store.observe_chain_meme_pattern(token,quote(token,'pool',created,clock[0],age_rate=True),recorded_at=clock[0])
    rows=store.db.execute('SELECT * FROM chain_meme_trader_positions').fetchall()
    assert len(rows)==3 and len({r['source_entry_fill_id'] for r in rows})==1
    def position(arm):return store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()
    def mark(price,seconds):
        clock[0]+=timedelta(seconds=seconds)
        store.upsert_chain_meme_trader_market_mark(token,quote(token,'pool',created,clock[0],price=price),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])
    return store,position,mark,policies


def test_withdrawn_checkpoint_preserves_parent_exits(tmp_path,monkeypatch):
    store,pos,mark,policies=fixture(tmp_path,monkeypatch)
    mark(1,899)
    assert pos(policies[1]['arm_id'])['pending_mark_id'] is None
    mark(1,1)
    child=pos(policies[1]['arm_id'])
    assert child['pending_mark_id'] is None and child['status']=='open'
    assert pos(policies[0]['arm_id'])['pending_mark_id'] is None
    mark(1,1)
    assert pos(policies[1]['arm_id'])['status']=='open'
    assert pos(policies[0]['arm_id'])['status']=='open'
    store.close()


def test_dynamic_recovery_reprices_next_frame_and_rebases_only_on_fill(tmp_path,monkeypatch):
    store,pos,mark,policies=fixture(tmp_path,monkeypatch)
    arm=policies[2]['arm_id']
    mark(1.5,10)
    before=pos(arm)
    assert before['pending_mark_id'] is not None and before['principal_recovered']==0
    pending=store.db.execute('SELECT * FROM chain_meme_trader_marks WHERE id=?',(before['pending_mark_id'],)).fetchone()
    assert pending['action']=='PRINCIPAL_RECOVERY'
    mark(2,1)
    after=pos(arm)
    assert after['principal_recovered']==1 and after['status']=='open'
    assert after['realized_proceeds_usd'] >= after['stake_usd']
    assert 0 < int(after['amount_raw']) < int(before['amount_raw'])
    filled=store.db.execute('SELECT * FROM chain_meme_trader_marks WHERE id=?',(pending['id'],)).fetchone()
    assert int(filled['sell_amount_raw']) < int(pending['sell_amount_raw'])
    assert after['highest_signal_price_usd']==2
    quantity_sold=before['remaining_quantity_tokens']*int(filled['sell_amount_raw'])/int(before['amount_raw'])
    assert after['realized_proceeds_usd']==pytest.approx(quantity_sold*2*.96)
    store.close()
