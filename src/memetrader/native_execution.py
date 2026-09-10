"""Current-period protocol-model Paper adapter; the common ledger owns cash/PNL.

Native receipts hold units/provenance, never transaction signatures. No send API.
"""
import hashlib
import json
from copy import deepcopy
from .models import iso, parse_time, utcnow
from .pump_native import native_cash_budget, native_mint_controls, pump_sol_exact_input_quote_v2, SOL
from .pump_native_cash import addresses
from .collectors import pump_bonding_curve_sell_quote_v1

ARM = 'pump_native_absorption_fast_v1'
MODEL = 'later_observed_protocol_model_paper'

SCHEMA = """
CREATE TABLE IF NOT EXISTS chain_meme_native_receipts (
 id INTEGER PRIMARY KEY, definition_version TEXT NOT NULL, opportunity_key TEXT NOT NULL,
 kind TEXT NOT NULL, recorded_at TEXT NOT NULL, payload_json TEXT NOT NULL,
 UNIQUE(definition_version,opportunity_key,kind));
CREATE TRIGGER IF NOT EXISTS native_receipt_immutable_update BEFORE UPDATE ON chain_meme_native_receipts
 BEGIN SELECT RAISE(ABORT,'native receipts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS native_receipt_immutable_delete BEFORE DELETE ON chain_meme_native_receipts
 BEGIN SELECT RAISE(ABORT,'native receipts are immutable'); END;
CREATE TABLE IF NOT EXISTS chain_meme_native_positions (
 definition_version TEXT NOT NULL, cohort_id INTEGER NOT NULL, token_id TEXT NOT NULL,
 curve TEXT NOT NULL, opportunity_key TEXT NOT NULL, state_json TEXT NOT NULL,
 PRIMARY KEY(definition_version,cohort_id), UNIQUE(definition_version,opportunity_key));
"""


def policy():
    return dict(arm_id=ARM, canonical_id=ARM, name='Pump 原生吸收快退（协议模型 Paper）',
        description='两帧净真实储备增长超过当前摩擦；后帧原生报价成交；租金单列，毕业等待规范池。',
        entry_family=ARM, entry_match_mode='native_protocol_model', native_execution=True,
        order_size_usd=5.0, notional_usd=5.0, entry_filter={'max_concurrent_positions':1},
        max_open_positions=1, stop_loss_pct=20, hard_stop_return=-0.20, max_hold_minutes=5,
        trailing_activation_pct=30, trailing_drawdown_pct=15, max_hold_seconds=300,
        take_profit_levels=[], narrative_extension=False, execution_model=MODEL,
        assessment_status='INSUFFICIENT', forward_enabled=True, paper_only=True)


def register(store):
    with store._lock, store.db:
        row = store.db.execute('SELECT 1 FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?',
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, ARM)).fetchone()
        if row is None:
            store.append_chain_meme_trader_policy(policy())


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def usd_per_raw(reference, now, observed):
    at = parse_time(reference['completed_at'])
    if not at <= observed <= now or not 0 <= (now-at).total_seconds() <= 30:
        raise ValueError('native_reference_clock')
    inp, out = int(reference['input_amount_raw']), int(reference['output_amount_raw'])
    if inp <= 0 or out <= 0:
        raise ValueError('native_reference_unknown')
    return out / inp / 1_000_000


def _receipt(db, version, key, kind, payload, now):
    return db.execute('INSERT INTO chain_meme_native_receipts(definition_version,opportunity_key,kind,recorded_at,payload_json) VALUES(?,?,?,?,?)',
        (version, key, kind, iso(now), dumps(payload))).lastrowid


def targets(store):
    with store._lock:
        rows = store.db.execute("SELECT n.*,p.amount_raw FROM chain_meme_native_positions n JOIN chain_meme_trader_positions p "
            "ON p.definition_version=n.definition_version AND p.shadow_cohort_id=n.cohort_id AND p.arm_id=? "
            "WHERE p.status='open' ORDER BY n.cohort_id LIMIT 1", (ARM,)).fetchall()
        return [dict(row, state=json.loads(row['state_json'])) for row in rows]


def ensure_time_exit(store, target, *, now=None):
    """Time expiry creates an intent even during missing quotes; never a fill."""
    now = parse_time(now or utcnow())
    with store._lock, store.db:
        row = store.db.execute('SELECT p.opened_at,p.status,n.state_json FROM chain_meme_native_positions n '
            'JOIN chain_meme_trader_positions p ON p.definition_version=n.definition_version '
            'AND p.shadow_cohort_id=n.cohort_id AND p.arm_id=? '
            'WHERE n.definition_version=? AND n.cohort_id=?',
            (ARM,target['definition_version'],target['cohort_id'])).fetchone()
        if row is None or row['status']!='open' or (now-parse_time(row['opened_at'])).total_seconds()<300:
            return
        state=json.loads(row['state_json'])
        if state.get('exit_intent'):
            return
        state['exit_intent']=dict(slot=state['last_slot'],recorded_at=iso(now),reason='max_hold')
        store.db.execute('UPDATE chain_meme_native_positions SET state_json=? WHERE definition_version=? AND cohort_id=?',
            (dumps(state),target['definition_version'],target['cohort_id']))


def buy(store, plan, *, now=None):
    """Commit one later-frame fill and its public cash flow in the same transaction."""
    now = parse_time(now or utcnow()); version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    f, trigger = plan['execution_frame'], plan['trigger']
    key = f"{f['token_id']}:{f['curve_address']}:{trigger['slot']}"
    with store._lock, store.db:
        addition = store.db.execute('SELECT * FROM chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?', (version, ARM)).fetchone()
        if addition is None:
            return 'NOT_REGISTERED'
        reg = store._chain_meme_trader_registration(version)
        definition = store._chain_meme_trader_effective_definition(version, reg['definition_json'])
        effective = next(p for p in definition['policies'] if p['arm_id'] == ARM)
        if effective.get('entry_paused') or not effective.get('forward_enabled'):
            return 'PAUSED'
        if store.db.execute('SELECT 1 FROM chain_meme_native_receipts WHERE definition_version=? AND opportunity_key=? AND kind=?', (version,key,'BUY')).fetchone():
            return 'ALREADY_CONSUMED'
        if store.db.execute("SELECT 1 FROM chain_meme_trader_positions WHERE definition_version=? AND arm_id=? AND status='open' LIMIT 1", (version,ARM)).fetchone():
            return 'MAX1'
        observed, recorded = parse_time(f['observed_at']), parse_time(f['recorded_at'])
        if not (parse_time(addition['activated_at']) <= parse_time(trigger['recorded_at']) < observed <= recorded <= parse_time(plan['recorded_at']) <= now
            and 0 <= (now-observed).total_seconds() <= 30 and trigger['slot'] < f['slot'] == trigger['requote_slot']
            and f['recorded_at'] == trigger['requote_recorded_at'] and trigger['status'] == 'REQUOTED_SHADOW'):
            raise ValueError('native_entry_clock')
        if hashlib.sha256(dumps(f).encode()).hexdigest() != plan['execution_frame_sha256']:
            raise ValueError('native_frame_hash')
        if (f['token_id'] != 'solana:'+f['base_mint'] or native_mint_controls(f)['status'] != 'CONTROLS_VERIFIED'
            or trigger.get('token_id')!=f['token_id'] or trigger.get('curve_address')!=f['curve_address']
            or (trigger.get('probe') or {}).get('status')!='FRICTION_EXCEEDED'
            or addresses(f, plan['account_id']) != plan['addresses'] or plan['addresses']['bonding_curve'] != f['curve_address']):
            raise ValueError('native_entry_identity_controls')
        # Known common safety hazards cannot be overridden by a native quote.
        gate = getattr(store, '_preentry_safety', None)
        cached = getattr(gate, 'cache', {}).get((f['token_id'], f['curve_address']), {})
        if cached.get('hard_veto') or cached.get('soft_hazard') or cached.get('status') in {'REJECT','WAIT_HAZARD'}:
            return 'WAIT_SAFETY'
        rate = usd_per_raw(plan['reference'], now, observed)
        budget = native_cash_budget(total_quote_raw=plan['cash_budget']['total_cash_budget_raw'], receipt=plan,
            now=now, token_id=f['token_id'], curve=f['curve_address'], account_id=plan['account_id'])
        if budget['total_cash_budget_raw'] * rate > 5.000001:
            raise ValueError('native_cash_over_5usd')
        q = pump_sol_exact_input_quote_v2(quote_budget_raw=budget['spendable_quote_raw'], slippage_bps=400,
            bonding_curve=f['curve_state'],global_config=f['global_config'],fee_config=f['fee_config'])
        if q != plan['buy_quote'] or any(plan['message_hashes'][s] != plan['fees'][s]['message_sha256'] for s in ('BUY','SELL')):
            raise ValueError('native_quote_message_binding')
        post = deepcopy(f['curve_state'])
        for field, delta in [('virtual_token_reserves_raw',-q['token_amount_raw']),('real_token_reserves_raw',-q['token_amount_raw']),
            ('virtual_quote_reserves_raw',q['curve_quote_in_raw']),('real_quote_reserves_raw',q['curve_quote_in_raw'])]:
            post[field] += delta
        sell = pump_bonding_curve_sell_quote_v1(token_amount_raw=q['paper_token_amount_raw'],slippage_bps=400,
            bonding_curve=post,global_config=f['global_config'],fee_config=f['fee_config'])
        if int(sell['min_quote_raw']) <= budget['sell_network_fee_reserved_raw']:
            return 'WAIT_SELLABILITY'
        stake = (q['actual_quote_cost_raw']+budget['buy_network_fee_raw'])*rate
        rent = budget['rent_locked_raw']*rate
        cash = float(definition['starting_cash_usd_each_arm']) + store.db.execute(
            'SELECT COALESCE(SUM(net_cash_flow_usd),0) FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=?',(version,ARM)).fetchone()[0]
        if cash < stake+rent+budget['sell_network_fee_reserved_raw']*rate:
            return 'CASH_INSUFFICIENT'
        receipt_id = _receipt(store.db,version,key,'BUY',dict(plan,execution_model=MODEL,
            safety_status='NATIVE_CONTROLS_AND_SELLBACK_VERIFIED',receipt_kind='PAPER_BUY',
            decision_eligible=True,affects='native_protocol_model_paper',native_ledger_required=False),now)
        episode = store.db.execute('SELECT COALESCE(MAX(episode_no),0)+1 FROM chain_meme_trader_v6_cohorts WHERE definition_version=? AND token_id=?',(version,f['token_id'])).fetchone()[0]
        # Negative source id is explicitly a native receipt, never a fabricated DEX snapshot.
        cohort = store.db.execute('INSERT INTO chain_meme_trader_v6_cohorts(definition_version,token_id,entry_family,source_snapshot_id,pair_address,decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,?,?)',
            (version,f['token_id'],'flow_burst',-receipt_id,f['curve_address'],iso(now),episode,dumps(dict(execution_model=MODEL,native_receipt_id=receipt_id,event_keys={ARM:key})))).lastrowid
        trade = store.db.execute('INSERT INTO chain_meme_trader_trades(definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,net_cash_flow_usd,realized_pnl_usd,reason,created_at,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (version,ARM,cohort,f['token_id'],'BUY',stake,-stake-rent,0,MODEL,iso(now),iso(now))).lastrowid
        quantity = q['paper_token_amount_raw']/1_000_000
        price = stake/quantity
        store.db.execute('INSERT INTO chain_meme_trader_positions(definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,highest_economic_value_usd,status,opened_at,entry_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (version,ARM,cohort,f['token_id'],trade,-receipt_id,0,price,price,quantity,quantity,str(q['paper_token_amount_raw']),str(q['paper_token_amount_raw']),stake,price,stake,'open',iso(now),MODEL))
        state = dict(plan=plan,execution_model=MODEL,surface='CURVE',rent_locked_raw=budget['rent_locked_raw'],rent_locked_usd_at_cost=rent,
            sell_fee_reserve_raw=budget['sell_network_fee_reserved_raw'],entry_rate=rate,entry_slot=f['slot'],last_slot=f['slot'],last_recorded_at=iso(now),
            high_value_usd=stake,mark=None,exit_intent=None,safety_status='NATIVE_CONTROLS_AND_SELLBACK_VERIFIED')
        store.db.execute('INSERT INTO chain_meme_native_positions VALUES(?,?,?,?,?,?)',(version,cohort,f['token_id'],f['curve_address'],key,dumps(state)))
        if gate is not None:
            gate.record(dict(version=version,token_id=f['token_id'],pool=f['curve_address'],cohort_id=cohort,
                snapshot_id=0,notional=5,requested_at=trigger['recorded_at']), 'BUY_AUTHORIZED_NATIVE_PROTOCOL',
                dict(status='PASS_NATIVE_PROTOCOL',allow=True,source_at=f['recorded_at'],reasons=[],
                    native_receipt_id=receipt_id,execution_model=MODEL,not_a_safety_guarantee=True))
        return 'BOUGHT'


def apply_curve_quote(store, target, quote, fee, reference, *, now=None):
    """Intent first; only a later coherent state can settle the remaining raw."""
    now = parse_time(now or utcnow()); version=target['definition_version']; cohort=target['cohort_id']
    with store._lock, store.db:
        row = store.db.execute('SELECT n.state_json,p.* FROM chain_meme_native_positions n JOIN chain_meme_trader_positions p ON p.definition_version=n.definition_version AND p.shadow_cohort_id=n.cohort_id AND p.arm_id=? WHERE n.definition_version=? AND n.cohort_id=?',(ARM,version,cohort)).fetchone()
        if row is None or row['status'] != 'open':return 'TERMINAL'
        s=json.loads(row['state_json']);slot=int(quote.get('context_slot') or 0)
        expected_pool=s.get('successor',{}).get('pool_address') if s['surface']=='PUMPSWAP' else target['curve']
        if (quote.get('token_id') != row['token_id'] or quote.get('pool_address') != expected_pool
            or str(quote.get('remaining_amount_raw')) != str(row['amount_raw'])):
            raise ValueError('native_exit_identity_amount')
        if s['surface']=='MIGRATION_PENDING':return 'MIGRATION_PENDING'
        if slot <= s['last_slot']:return 'NO_NEW_STATE'
        observed=parse_time(quote['requested_at']);recorded=parse_time(quote['completed_at'])
        if not parse_time(s['last_recorded_at']) < observed <= recorded <= now or (now-observed).total_seconds()>30:
            return 'UNKNOWN_CLOCK'
        status=quote.get('status');reason=quote.get('reason','')
        s.update(last_slot=slot,last_recorded_at=iso(now),mark=None)
        if reason=='bonding_curve_complete_migrated':
            s.update(surface='MIGRATION_PENDING',exit_intent=s['exit_intent'] or dict(slot=slot,recorded_at=iso(now),reason='graduation'))
            result='MIGRATION_PENDING'
        elif status != 'LOCAL_SURFACE_CURRENT' or fee is None:
            if reason=='insufficient_real_quote_reserves':
                s['exit_intent']=s['exit_intent'] or dict(slot=slot,recorded_at=iso(now),reason='sell_capacity_lost')
            result='UNKNOWN_EXIT'
        else:
            if (int(fee['context_slot'])<slot or not recorded<=parse_time(fee['recorded_at'])<=now
                or fee.get('token_amount_raw')!=int(row['amount_raw']) or fee.get('curve')!=expected_pool
                or fee.get('account_id')!=s['plan']['account_id'] or len(fee.get('message_sha256',''))!=64):
                raise ValueError('native_exit_fee_binding')
            rate=usd_per_raw(reference,now,observed)
            net=(int(quote['min_quote_raw'])-int(fee['fee_lamports']))*rate
            if net<=0:return 'UNKNOWN_NET_RECOVERY'
            s['sell_fee_reserve_raw']=max(s['sell_fee_reserve_raw'],int(fee['fee_lamports']))
            s['mark']=dict(value_usd=net,observed_at=iso(observed),recorded_at=iso(now),slot=slot,execution_model=MODEL)
            s['high_value_usd']=max(s['high_value_usd'],net)
            intent=s['exit_intent']
            if intent and slot>intent['slot'] and observed>parse_time(intent['recorded_at']):
                pnl=net-float(row['stake_usd'])
                new_rent=int(fee.get('setup_rent_raw',0))*rate
                if new_rent<0:raise ValueError('invalid_exit_setup_rent')
                reg=store._chain_meme_trader_registration(version)
                definition=store._chain_meme_trader_effective_definition(version,reg['definition_json'])
                cash=float(definition['starting_cash_usd_each_arm'])+store.db.execute(
                    'SELECT COALESCE(SUM(net_cash_flow_usd),0) FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=?',(version,ARM)).fetchone()[0]
                if cash+net<new_rent:return 'WAIT_EXIT_SETUP_CASH'
                _receipt(store.db,version,target['opportunity_key'],'SELL',dict(quote=quote,fee=fee,reference=reference,exit_intent=intent,execution_model=MODEL),now)
                store.db.execute('INSERT INTO chain_meme_trader_trades(definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,net_cash_flow_usd,realized_pnl_usd,reason,created_at,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (version,ARM,cohort,row['token_id'],'SELL',net,net-new_rent,pnl,intent['reason']+':'+MODEL,iso(now),iso(now)))
                store.db.execute("UPDATE chain_meme_trader_positions SET status='closed',amount_raw='0',remaining_quantity_tokens=0,realized_proceeds_usd=?,allocated_cost_usd=stake_usd,realized_pnl_usd=?,closed_at=?,close_reason=? WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=?",
                    (net,pnl,iso(now),intent['reason'],version,ARM,cohort))
                s.update(surface='CLOSED',sell_fee_reserve_raw=0,
                    rent_locked_usd_at_cost=s['rent_locked_usd_at_cost']+new_rent,
                    rent_locked_raw=s['rent_locked_raw']+int(fee.get('setup_rent_raw',0)));result='SOLD'
            else:
                reason=('hard_stop' if net<=float(row['stake_usd'])*.8 else
                    'trailing' if s['high_value_usd']>=float(row['stake_usd'])*1.3 and net<=s['high_value_usd']*.85 else
                    'max_hold' if (now-parse_time(row['opened_at'])).total_seconds()>=300 else '')
                if reason:s['exit_intent']=dict(slot=slot,recorded_at=iso(now),reason=reason)
                result='EXIT_INTENT' if reason else 'MARKED'
        store.db.execute('UPDATE chain_meme_native_positions SET state_json=? WHERE definition_version=? AND cohort_id=?',(dumps(s),version,cohort))
        return result


def canonical_pool(mint):
    from solders.pubkey import Pubkey
    from .pump_native_cash import PUMP
    from .collectors import PUMP_AMM_PROGRAM_ID
    base=Pubkey.from_string(mint)
    creator=Pubkey.find_program_address([b'pool-authority',bytes(base)],Pubkey.from_string(PUMP))[0]
    pool=Pubkey.find_program_address([b'pool',bytes(2),bytes(creator),bytes(base),bytes(Pubkey.from_string(SOL))],Pubkey.from_string(PUMP_AMM_PROGRAM_ID))[0]
    return str(pool),str(creator)


def confirm_successor(store,target,evidence,*,now=None):
    """Persist a post-completion, exact canonical identity before later valuation."""
    from .collectors import PUMP_AMM_PROGRAM_ID
    now=parse_time(now or utcnow())
    with store._lock,store.db:
        row=store.db.execute('SELECT state_json FROM chain_meme_native_positions WHERE definition_version=? AND cohort_id=?',
            (target['definition_version'],target['cohort_id'])).fetchone()
        s=json.loads(row[0])
        if s['surface']!='MIGRATION_PENDING':return s['surface']
        if evidence.get('status')!='RESOLVED':return 'MIGRATION_PENDING'
        mint=s['plan']['execution_frame']['base_mint'];pool,creator=canonical_pool(mint)
        facts=evidence.get('identity_facts',{});p=facts.get('pool',{})
        if (evidence.get('token_id')!=target['token_id'] or evidence.get('pool_address')!=pool
            or evidence.get('base_mint')!=mint or evidence.get('quote_mint')!=SOL
            or p.get('status')!='verified' or p.get('owner')!=PUMP_AMM_PROGRAM_ID or p.get('index')!=0
            or p.get('creator')!=creator or p.get('base_mint')!=mint or p.get('quote_mint')!=SOL):
            raise ValueError('native_canonical_identity')
        for name,m in [('base_vault',mint),('quote_vault',SOL)]:
            v=facts.get(name,{})
            if v.get('status')!='verified' or v.get('mint')!=m or v.get('authority')!=pool or p.get(name)!=evidence.get(name):
                raise ValueError('native_canonical_vault')
        if not s['last_slot']<evidence['resolved_slot'] or not parse_time(s['last_recorded_at'])<parse_time(evidence['resolved_at'])<=now:
            return 'UNKNOWN_MIGRATION_CLOCK'
        _receipt(store.db,target['definition_version'],target['opportunity_key'],'CANONICAL_SUCCESSOR',evidence,now)
        s.update(surface='PUMPSWAP',successor=evidence,last_slot=evidence['resolved_slot'],last_recorded_at=iso(now),mark=None)
        store.db.execute('UPDATE chain_meme_native_positions SET state_json=? WHERE definition_version=? AND cohort_id=?',
            (dumps(s),target['definition_version'],target['cohort_id']))
        return 'PUMPSWAP'


def account_assets(connection, version, now):
    """Bounded native-only assets, shared by public accounts and account snapshots."""
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chain_meme_native_positions'").fetchone() is None:
        return dict(rent=0.,reserve=0.,values={})
    result=dict(rent=0.,reserve=0.,values={})
    for row in connection.execute('SELECT cohort_id,state_json FROM chain_meme_native_positions WHERE definition_version=?',(version,)):
        s=json.loads(row['state_json']);result['rent']+=s['rent_locked_usd_at_cost']
        result['reserve']+=s['sell_fee_reserve_raw']*s['entry_rate']
        m=s.get('mark');result['values'][row['cohort_id']]=None
        if m and s['surface']!='MIGRATION_PENDING' and 0<=(parse_time(now)-parse_time(m['observed_at'])).total_seconds()<=15:
            result['values'][row['cohort_id']]=m['value_usd']
    return result
