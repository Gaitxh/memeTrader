from copy import deepcopy
from scripts.review_policy_lifecycle233 import entry_availability,stats


def member(arm,paused=False,group='pair',mode='isolated_cohort_observer',size=2):
    return dict(arm_id=arm,entry_paused=paused,paired_entry_group=group,
                entry_match_mode=mode,paired_entry_size=size)


def test_paused_twin_does_not_leave_control_reported_as_structurally_ready():
    policies=[member('control'),member('twin',True)]; before=deepcopy(policies)
    states=entry_availability(policies)
    assert states['control']['state']=='PAIRED_DEPENDENCY_INCOMPLETE'
    assert states['twin']['state']=='PAUSED' and policies==before


def test_complete_pair_and_unpaired_remain_conditional_not_promised_trades():
    states=entry_availability([member('a'),member('b'),dict(arm_id='plain')])
    assert all(v['state']=='ELIGIBLE_SUBJECT_TO_RUNTIME_CHECKS' for v in states.values())


def test_declared_disabled_or_different_lane_does_not_complete_pair():
    policies=[member('a'),{**member('b'),'forward_enabled':False},
              member('c',mode='isolated_pattern_observer')]
    states=entry_availability(policies)
    assert states['a']['state']==states['c']['state']=='PAIRED_DEPENDENCY_INCOMPLETE'
    assert states['b']['state']=='FORWARD_DISABLED'


def test_inconsistent_pair_sizes_are_not_treated_as_a_complete_group():
    states=entry_availability([member('a'),member('b',size=3)])
    assert all(v['state']=='PAIRED_DEPENDENCY_INCOMPLETE' for v in states.values())
    states=entry_availability([member('a',size=None)])
    assert states['a']['state']=='PAIR_CONTRACT_UNKNOWN'


def test_unknown_writeoff_proceeds_are_not_silently_full_loss():
    rows=[dict(token_id='a',stake_usd=20.,realized_pnl_usd=-20.,status='written_off'),
          dict(token_id='b',stake_usd=20.,realized_pnl_usd=-20.,status='written_off',realized_proceeds_usd=None),
          dict(token_id='c',stake_usd=20.,realized_pnl_usd=-20.,status='written_off',realized_proceeds_usd=0.)]
    result=stats(rows)
    assert result['written_off_positions']==3 and result['full_loss_writeoffs']==1
