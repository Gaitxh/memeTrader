"""Prospective actual-parent-fill comparator; no trade authority or requests."""
import json
from .models import canonical_token_address, parse_time, iso, utcnow

KEY='age-rate-fresh-impulse112'
PARENT='resource_age_rate_candidate_v1'
PRIOR=('prebreakout_net_accumulation_v1','resource_cooling_hold_candidate_v1')

def classify(db, version, token, pool, at):
    at=parse_time(at);pool=canonical_token_address(token.split(':')[0],pool)
    rows=db.execute('SELECT p.*,c.pair_address FROM chain_meme_trader_positions p '
        'JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id AND c.definition_version=p.definition_version '
        'WHERE p.definition_version IN (SELECT definition_version FROM chain_meme_trader_registrations) '
        'AND p.token_id=? AND p.arm_id IN (?,?) AND p.opened_at<=? '
        'ORDER BY p.opened_at DESC LIMIT 65',(token,*PRIOR,iso(at))).fetchall()
    if len(rows)>64:return dict(state='UNKNOWN',reason='PRIOR_HISTORY_BOUND')
    prior=[]
    for p in rows:
        if canonical_token_address(token.split(':')[0],p['pair_address'])!=pool:continue
        trades=db.execute('SELECT id,side,created_at,recorded_at FROM chain_meme_trader_trades '
            'WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=? ORDER BY id DESC LIMIT 65',
            (p['definition_version'],p['arm_id'],p['shadow_cohort_id'])).fetchall()
        if len(trades)>64:return dict(state='UNKNOWN',reason='RECEIPT_HISTORY_BOUND')
        visible=[t for t in trades if t['recorded_at'] and parse_time(t['created_at'])<=parse_time(t['recorded_at'])<=at]
        buys=[t for t in visible if t['side']=='BUY']
        if not buys:continue
        terminal=[t for t in visible if t['side'] in ('SELL','WRITEOFF') and p['closed_at']
            and parse_time(p['closed_at'])<=parse_time(t['created_at'])]
        closed=p['status'] in ('closed','written_off') and bool(terminal)
        prior.append(dict(version=p['definition_version'],arm=p['arm_id'],cohort=p['shadow_cohort_id'],
            buy_receipt_id=buys[-1]['id'],buy_recorded_at=buys[-1]['recorded_at'],
            state='CLOSED' if closed else 'OPEN',close_receipt_id=terminal[0]['id'] if closed else None))
    if not prior:return dict(state='CLEAN_FIRST_IMPULSE',prior=[])
    last=max(parse_time(p['buy_recorded_at']) for p in prior)
    # Rediscovery is a token-level episode, not proof of profitable reawakening.
    episodes=db.execute("SELECT id,observed_at,recorded_at,payload_json FROM chain_meme_pattern_evidence "
        "WHERE definition_version=? AND token_id=? AND pair_address='' AND kind='rediscovery_episode' ORDER BY id DESC LIMIT 32",
        (version,token)).fetchall()
    for e in episodes:
        if last<parse_time(e['observed_at'])<=parse_time(e['recorded_at'])<at and json.loads(e['payload_json']).get('episode')=='REAWAKENING':
            return dict(state='RESET_CONFIRMED',prior=prior,reset_evidence_id=e['id'],
                reset_recorded_at=e['recorded_at'],reset_basis='persisted_token_rediscovery_not_market_confirmation')
    return dict(state='CONFLICT_PRIOR_OPEN' if any(p['state']=='OPEN' for p in prior) else 'CONFLICT_PRIOR_CLOSED',prior=prior)

def capture(store, version, cohort, token, decision_at, fill_id):
    state=store.get_kv(KEY,None) or dict(version='age_rate_fresh_impulse_v2',decision_eligible=False,
        affects='none',started_at=iso(),counts={},outcomes={},pending=[],recent=[],dropped=0)
    key=f'{version}:{cohort}'
    if store.db.execute('SELECT 1 FROM chain_meme_pattern_evidence WHERE definition_version=? AND token_id=? '
            "AND kind='age_rate_fresh_impulse112_entry' AND source_key=?",(version,token,key)).fetchone():return
    c=store.db.execute('SELECT pair_address FROM chain_meme_trader_v6_cohorts WHERE id=? AND definition_version=?',(cohort,version)).fetchone()
    if not c:return
    result=classify(store.db,version,token,c[0],decision_at)
    row=dict(key=key,definition_version=version,cohort=cohort,token_id=token,pool=c[0],
        signal_at=decision_at,source_entry_fill_id=fill_id,recorded_at=iso(),**result)
    store.record_chain_meme_pattern_evidence(token,c[0],'age_rate_fresh_impulse112_entry',
        dict(decision_eligible=False,affects='none',**row),observed_at=parse_time(decision_at),source_key=key)
    state['counts'][result['state']]=state['counts'].get(result['state'],0)+1
    if len(state['pending'])<128:state['pending'].append(row)
    else:state['dropped']+=1  # Outcome capacity censoring is explicit, never a silent win/loss.
    store.set_kv(KEY,state)

def resolve(store):
    state=store.get_kv(KEY,None)
    if not state or not state['pending']:return
    remaining=state['pending'][8:]
    for row in state['pending'][:8]:
        p=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?',
            (row['definition_version'],PARENT,row['cohort'])).fetchone()
        if not p or p['status'] not in ('closed','written_off'):
            remaining.append(row);continue
        outcome=dict(**row,status=p['status'],closed_at=p['closed_at'],close_reason=p['close_reason'],
            realized_pnl_usd=p['realized_pnl_usd'],stake_usd=p['stake_usd'],outcome_recorded_at=iso())
        group=state['outcomes'].setdefault(row['state'],dict(n=0,pnl=0.,positive=0,tails_ge_5u=0))
        group['n']+=1;group['pnl']+=p['realized_pnl_usd'];group['positive']+=int(p['realized_pnl_usd']>0);group['tails_ge_5u']+=int(p['realized_pnl_usd']>=5)
        store.record_chain_meme_pattern_evidence(row['token_id'],row['pool'],'age_rate_fresh_impulse112_outcome',
            dict(decision_eligible=False,affects='none',**outcome),observed_at=utcnow(),source_key=row['key'])
        state['recent']=(state['recent']+[outcome])[-64:]
    state['pending']=remaining;store.set_kv(KEY,state)
