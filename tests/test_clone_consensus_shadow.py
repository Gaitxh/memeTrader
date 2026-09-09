from datetime import timedelta
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.store import Store
from test_paper_execution import _snapshot


def test_shadow_registration_has_no_funded_arm_and_preserves_frontier(tmp_path):
    store=Store(tmp_path/'clone.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_cohort_experiments()
    key='clone-consensus-shadow/v2:'+store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    reg=store.get_kv(key)
    assert reg['policy']['observer_only'] and reg['policy']['notional_usd']==5
    assert store.db.execute("select count(*) from chain_meme_trader_policy_additions where arm_id='clone_consensus_leader_v2'").fetchone()[0]==0
    assert store.register_chain_meme_cohort_experiments()==0 and store.get_kv(key)==reg
    now=utcnow();token=TokenCandidate('robinhood','0x'+'12'*20,'Clone','CLONE');pool='0x'+'34'*20
    store.upsert_token(token,seen_at=now)
    snap=_snapshot(token,pool,now)
    signal={'decision_key':'episode|clone_consensus_leader_v2','decision_evidence':{'frozen_at':iso(now-timedelta(days=1))}}
    assert store.record_clone_consensus_shadow(signal,snap,now) is None
    signal['decision_evidence']['frozen_at']=reg['activated_at']
    assert store.record_clone_consensus_shadow(signal,snap,now) is not None
    assert store.db.execute("select count(*) from chain_meme_pattern_evidence where kind='clone_consensus_leader_v2_shadow'").fetchone()[0]==1
    store.record_clone_consensus_shadow(signal,snap,now)
    assert store.db.execute("select count(*) from chain_meme_pattern_evidence where kind='clone_consensus_leader_v2_shadow'").fetchone()[0]==1
    assert store.db.execute("select count(*) from chain_meme_trader_positions where arm_id='clone_consensus_leader_v2'").fetchone()[0]==0
    store.close()
