from copy import deepcopy
from datetime import timedelta

from memetrader.models import TokenSnapshot, utcnow
from memetrader.store import Store
from memetrader.trajectory144 import policies as trajectory_policies
from memetrader.trajectory_exit190 import ARM, CONTROL, PARENT, alias_signals, policy
from test_core import _seed_chain_market_position


def test_first_mark_challenger_changes_only_trailing_activation():
    parent=next(item for item in trajectory_policies({}) if item['arm_id']==PARENT)
    candidate=policy(parent)
    assert candidate['trailing_activate_return']==-1.0
    assert Store._chain_meme_trailing_activation(candidate)==-1.0
    assert candidate['excess_return_vs_arm']==CONTROL
    assert candidate['no_historical_backfill'] and candidate['affects']=='paper_only'
    omitted={'arm_id','canonical_id','entry_family','name','description','entry_filter',
             'entry_alias_of','source_arm_ids','paired_opportunity_group',
             'excess_return_vs_arm','trailing_activate_return','assessment_status',
             'decision_eligible','observer_only','affects','live','no_historical_backfill',
             'signal_origin_clock'}
    assert {key:deepcopy(value) for key,value in candidate.items() if key not in omitted}=={
        key:deepcopy(value) for key,value in parent.items() if key not in omitted}
    source={'decision_key':'original','selected':{'token_id':'solana:token','pair_address':'pool'},
            'decision_evidence':{'mode':PARENT,'feature_vector':{'chain':'solana'}}}
    aliased=alias_signals({PARENT:source})
    assert aliased[ARM]['selected']==source['selected']
    assert aliased[ARM]['decision_evidence']['trajectory_exit190_source_decision_key']=='original'
    assert source['decision_evidence']['mode']==PARENT


def test_forward_registration_and_first_mark_trailing_differs_from_break_even(tmp_path):
    store=Store(tmp_path/'exit190.sqlite3',initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        assert store.register_chain_meme_trajectory_regime187()==3
        frontier=store.db.execute('SELECT COALESCE(MAX(id),0) FROM token_snapshots').fetchone()[0]
        assert store.register_chain_meme_trajectory_exit190()==1
        assert store.register_chain_meme_trajectory_exit190()==0
        version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        addition=store.db.execute('SELECT activation_snapshot_id FROM chain_meme_trader_policy_additions '
            'WHERE definition_version=? AND arm_id=?',(version,ARM)).fetchone()
        assert addition['activation_snapshot_id']==frontier
        registration=store._chain_meme_trader_registration(version)
        definition=store._chain_meme_trader_effective_definition(version,registration['definition_json'])
        policies={item['arm_id']:item for item in definition['policies']}
        assert policies[ARM]['hard_stop_return']==policies[CONTROL]['hard_stop_return']==-.20
        assert policies[ARM]['trailing_drawdown']==policies[CONTROL]['trailing_drawdown']==.15
        assert policies[CONTROL]['trailing_activate_return']==0.0

        opened=utcnow()-timedelta(minutes=2)
        token,cohort=_seed_chain_market_position(store,version=version,
            policy=policies[ARM],opened_at=opened)
        with store.db:
            trade=dict(store.db.execute('SELECT * FROM chain_meme_trader_trades WHERE '
                'definition_version=? AND arm_id=? AND shadow_cohort_id=?',
                (version,ARM,cohort)).fetchone())
            trade.pop('id')
            trade['arm_id']=CONTROL
            columns=list(trade)
            control_buy=store.db.execute('INSERT INTO chain_meme_trader_trades('
                +','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',
                tuple(trade.values())).lastrowid
            position=dict(store.db.execute('SELECT * FROM chain_meme_trader_positions '
                'WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?',
                (version,ARM,cohort)).fetchone())
            position['arm_id']=CONTROL
            position['source_buy_trade_id']=control_buy
            columns=list(position)
            store.db.execute('INSERT INTO chain_meme_trader_positions('
                +','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',
                tuple(position.values()))
        for seconds,price in ((60,1.05),(61,.88)):
            at=opened+timedelta(seconds=seconds)
            store.upsert_chain_meme_trader_market_mark(token,TokenSnapshot(
                'solana',token.address,price,50_000,100_000,1000,6,2,
                observed_at=at,ingested_at=at,provider='dexscreener',
                raw={'pair':{'pairAddress':'pair-A'}}),recorded_at=at)
            store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=at)
            if seconds==60:
                assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_marks '
                    'WHERE definition_version=? AND action=?',(version,'TRAILING_EXIT')).fetchone()[0]==0
        trailing=store.db.execute('SELECT arm_id FROM chain_meme_trader_marks WHERE '
            'definition_version=? AND action=?',(version,'TRAILING_EXIT')).fetchall()
        assert [row['arm_id'] for row in trailing]==[ARM]
        assert store.db.execute('SELECT status FROM chain_meme_trader_positions WHERE '
            'definition_version=? AND arm_id=?',(version,CONTROL)).fetchone()[0]=='open'
    finally:
        store.close()
