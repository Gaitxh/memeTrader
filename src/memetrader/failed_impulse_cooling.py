"""Cooling after a receipted core loss: independent, one-shot Paper hypothesis."""
from copy import deepcopy
from .models import canonical_token_address, iso, parse_time
from .resource_bound_research import resource_entry_signal

ARM = 'failed_impulse_cooling_v1'
PARENT = 'resource_cooling_hold_candidate_v1'
CORE = 'resource_age_rate_candidate_v1'


def policy(parent):
    p = deepcopy(parent)
    for k in ('stage', 'runtime_addition_id', 'entry_paused', 'entry_pause_reason',
              'behavior_hash', 'forward_started_at', 'forward_activation_snapshot_id',
              'forward_activation_evaluation_id', 'paired_entry_group', 'paired_entry_size'):
        p.pop(k, None)
    p.update(arm_id=ARM, canonical_id=ARM, name='核心失败后·降温守位',
             description='原降温信号加同池核心亏损退出凭据；每个核心退出事件一次，未验证盈利。',
             source_arm_ids=[PARENT, CORE], notional_usd=5.0)
    p['entry_filter'].update(failed_impulse_cooling=True, max_concurrent_positions=4)
    return p


def latest_loss_receipt(db, token_id, pool, at):
    pool = canonical_token_address(token_id.split(':')[0], pool)
    # Select latest position first: a newer open/winning core cannot expose an older loss.
    p = db.execute('SELECT p.* FROM chain_meme_trader_positions p '
        'JOIN chain_meme_trader_v6_cohorts c ON c.definition_version=p.definition_version AND c.id=p.shadow_cohort_id '
        'WHERE p.definition_version IN (SELECT definition_version FROM chain_meme_trader_registrations) '
        'AND p.token_id=? AND p.arm_id=? AND c.pair_address=? AND p.opened_at<? '
        'ORDER BY p.opened_at DESC,p.shadow_cohort_id DESC LIMIT 1', (token_id, CORE, pool, iso(parse_time(at)))).fetchone()
    if not p or p['status'] not in ('closed', 'written_off') or p['realized_pnl_usd'] is None or p['realized_pnl_usd'] >= 0:
        return None
    if not p['closed_at'] or parse_time(p['closed_at']) >= parse_time(at):
        return None
    t = db.execute("SELECT id,created_at,recorded_at FROM chain_meme_trader_trades "
        "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=? AND side IN ('SELL','WRITEOFF') "
        "ORDER BY id DESC LIMIT 1", (p['definition_version'], CORE, p['shadow_cohort_id'])).fetchone()
    if not t or not t['recorded_at'] or not (parse_time(p['closed_at']) <= parse_time(t['created_at']) <= parse_time(t['recorded_at']) < parse_time(at)):
        return None
    return dict(parent_version=p['definition_version'], parent_cohort=p['shadow_cohort_id'],
                close_receipt_id=t['id'], close_recorded_at=t['recorded_at'])


def signal(db, history, p, token_id, pool, at, pending=None):
    if pending:
        return True, 'failed_impulse_cooling_next_frame', pending
    passed, reason, _ = resource_entry_signal(history, p, decision_at=iso(at), activated_at=p['forward_started_at'])
    if not passed:
        return False, reason, None
    receipt = latest_loss_receipt(db, token_id, pool, at)
    if not receipt:
        return False, 'cooling_requires_prior_recorded_core_loss', None
    key = f"{ARM}:{token_id}:{pool}:{receipt['parent_version']}:{receipt['parent_cohort']}:{receipt['close_receipt_id']}"
    return True, 'failed_impulse_cooling_ready', dict(decision_key=key, episode_id=key,
        selected=dict(token_id=token_id, pair_address=pool), observed_at=history[-1]['observed_at'],
        recorded_at=iso(at), core_loss_receipt=receipt)
