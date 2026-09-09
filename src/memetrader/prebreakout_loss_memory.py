"""One scoped prior-loss hypothesis; no market requests or history writes."""
from copy import deepcopy
from .models import canonical_token_address,iso,parse_time

ARM='prebreakout_loss_memory_v1'
PARENT='prebreakout_net_accumulation_v1'
CORE='resource_age_rate_candidate_v1'

def policy(parent):
    p=deepcopy(parent)
    for key in ('stage','runtime_addition_id','entry_paused','entry_pause_reason','behavior_hash','forward_started_at','forward_activation_snapshot_id','forward_activation_evaluation_id'):
        p.pop(key,None)
    p.update(arm_id=ARM,canonical_id=ARM,name='启动前积累·同池亏损记忆',notional_usd=5.0,source_arm_ids=[PARENT],description='原信号加同币同池先前核心亏损记忆；独立前向假设，未证明盈利。')
    p.pop('paired_entry_group',None);p.pop('paired_entry_size',None)
    p['entry_filter']=dict(p.get('entry_filter') or {},max_concurrent_positions=4,prior_core_loss_same_pool=True)
    return p

def prior_loss(connection,token_id,pair_address,signal_at):
    pool=canonical_token_address(token_id.split(':')[0],pair_address)
    return connection.execute("""SELECT p.definition_version,p.shadow_cohort_id,p.closed_at,p.realized_pnl_usd
      FROM chain_meme_trader_positions p
      JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id AND c.definition_version=p.definition_version
      WHERE p.definition_version IN (SELECT definition_version FROM chain_meme_trader_registrations)
      AND p.token_id=? AND p.arm_id=? AND p.status IN ('closed','written_off')
      AND p.closed_at<? AND p.realized_pnl_usd<0 AND c.pair_address=? LIMIT 1""",
      (token_id,CORE,iso(parse_time(signal_at)),pool)).fetchone()
