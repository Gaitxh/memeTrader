"""BSC-only reported rolling average-notional proxy, not transaction sizes."""
from copy import deepcopy
from math import isfinite

ARM='bsc_capital_pulse_29m_v1'
PARENT='resource_age_rate_candidate_v1'

def qualifies(chain,buys,sells,volume):
    if chain!='bsc':return False
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not isfinite(x) for x in (buys,sells,volume)):return False
    n=buys+sells
    return buys>=0 and sells>=0 and buys==int(buys) and sells==int(sells) and 0<n<=15 and volume/n>=1000 and buys/n>=.60

def policy(parent):
    p=deepcopy(parent)
    for k in ('stage','runtime_addition_id','entry_paused','entry_pause_reason','behavior_hash','forward_started_at',
              'forward_activation_snapshot_id','forward_activation_evaluation_id','paired_entry_group','paired_entry_size',
              'dynamic_principal_recovery','revision_exit_kind','revision_exit_policy','capital_exit_kind','capital_exit_policy'):
        p.pop(k,None)
    p.update(arm_id=ARM,canonical_id=ARM,name='BSC资金脉冲·29分钟实验',source_arm_ids=[PARENT],notional_usd=5.,
        max_hold_minutes=29.,hard_stop_return=-.20,trailing_activate_return=.30,trailing_drawdown=.15,
        description='BSC池龄机会；5分钟报告成交额/笔数代理≥1000U，1–15笔、买方占比≥60%；非真实逐笔金额。29分钟上限不接受叙事延期；小额前向实验，未验证盈利。')
    p['entry_filter']={**p['entry_filter'],'bsc_capital_pulse114':True,'max_concurrent_positions':4}
    p['entry_filter'].pop('narrative_hold_v2',None)
    return p
