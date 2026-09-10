from memetrader.strategy_explainability import strategy_logic

def test_native_explanation_uses_protocol_contract_without_dex_floor_or_unknown_sequence():
 from memetrader.native_execution import policy
 p=policy();x=strategy_logic(p,{},current=True)
 assert any('下一独立曲线帧' in r for r in x['entry_sequence'])
 assert any('储备不足' in r for r in x['exit_rules'])
 assert any('不套用毕业前 DEX' in r for r in x['data_requirements'])
 assert not any('后帧要求：UNKNOWN' in r for r in x['entry_sequence'])

def test_positive_pause_not_failed_and_preserves_evidence():
 p={'arm_id':'age_rate_horizon_fast_v1','account_lifecycle':'PAUSED_NEW_ENTRY','assessment_status':'EXPERIMENT_COMPLETE_POSITIVE','assessment_note':'Positive benchmark, same fill parent stronger','assessment_evidence':'report89','max_hold_minutes':15,'require_post_decision_observation':True}
 x=strategy_logic(p,{}, {'reason':'whole paired experiment complete'},current=True)
 l=x['lifecycle_explanation'];assert l['assessment']=='EXPERIMENT_COMPLETE_POSITIVE'
 assert '不是失败' in l['note'] and l['evidence']=='report89' and l['pause_basis']=='whole paired experiment complete'
 assert 'benchmark' in l['benchmark']

def test_missing_historical_contract_stays_unknown():
 x=strategy_logic({}, {'account_lifecycle':'PAUSED_NEW_ENTRY'})
 assert x['lifecycle_explanation']['assessment']=='INSUFFICIENT'
 assert x['lineage']['policy_source']=='UNKNOWN'
 assert any('UNKNOWN' in s for s in x['entry_rules'])
 assert not any('最终 BUY 共用' in s for s in x['entry_sequence'])

def test_dynamic_and_narrative_exits_and_frozen_parameters_are_not_mutated():
 p={'entry_filter':{'min_rate_acceleration':3,'narrative_hold_v2':True,'unmapped_gate':{'a':2}},'dynamic_principal_recovery':'minimum_net_debit_keep_half_next_frame/v3','max_hold_minutes':30,'hard_stop_return':-.2,'take_profit':[],'source_arm_ids':['parent'],'paired_entry_group':'g','paired_entry_size':2}
 import copy
 before=copy.deepcopy(p);x=strategy_logic(p,{},current=True)
 assert p==before and x['lineage']['source_arm_ids']==['parent']
 assert any('一半' in r for r in x['exit_rules']) and any('不覆盖硬止损' in r for r in x['exit_rules'])
 assert any('unmapped_gate' in r for r in x['entry_rules'])
 assert x['lifecycle_explanation']['assessment']=='ACTIVE'


def test_v144_explanation_shows_frozen_entry_data_frame_and_trend_contracts():
 from memetrader.trajectory144 import ARMS, policies
 base={'entry_filter':{},'forward_enabled':True}
 p312,p315,p317=(policies(base)[index] for index in (0,3,5))
 x312=strategy_logic(p312,{},current=True)
 x315=strategy_logic(p315,{},current=True)
 x317=strategy_logic(p317,{},current=True)
 assert any('v144 冻结入场规则' in item and '池龄小于300秒' in item for item in x312['entry_rules'])
 assert any('独立轨迹后帧' in item for item in x312['entry_sequence'])
 assert any('v144 数据合同 provider' in item and 'Dexscreener exact original pool' in item for item in x312['data_requirements'])
 assert any('300 秒实际趋势' in item and '120 分钟' in item for item in x315['exit_rules'])
 assert any('模式选择合同' in item and '固定基线' in item for item in x317['data_requirements'])


def test_reactivated_assessment_does_not_pause_or_change_policy(tmp_path,monkeypatch):
 from test_resource_bound_store import setup_store
 store,_=setup_store(tmp_path,monkeypatch)
 version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
 raw=store._chain_meme_trader_registration(version)['definition_json']
 before=store.chain_meme_trader_effective_definition_from_connection(store.db,version,raw)
 arm=before['policies'][0]['arm_id']
 store.set_kv('chain-meme-account-convergence/v1:'+version,dict(activated_at='2026-09-10T00:00:00Z',arms={},active_assessments={arm:dict(assessment_status='ACTIVE',assessment_note='MIXED_HIGH_RECALL; retained positive experiment, no organic alpha proof',assessment_evidence='report126')}))
 after=store.chain_meme_trader_effective_definition_from_connection(store.db,version,raw)
 p=next(p for p in after['policies'] if p['arm_id']==arm)
 assert not p.get('entry_paused') and not p.get('account_lifecycle')
 assert strategy_logic(p,{},current=True)['lifecycle_explanation']['assessment']=='ACTIVE'
 assert 'MIXED_HIGH_RECALL' in strategy_logic(p,{},current=True)['lifecycle_explanation']['note']
 assert store._chain_meme_trader_registration(version)['definition_json']==raw
 store.close()
