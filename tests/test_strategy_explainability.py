from memetrader.strategy_explainability import strategy_logic

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
