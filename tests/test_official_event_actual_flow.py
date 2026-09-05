import copy
import json
from datetime import timedelta

from memetrader.capital_entry import capital_observation_signal
from memetrader.capital_policies import capital_policies, event_actual_flow_policy
from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


def test_official_event_requires_post_event_money_not_counts(tmp_path, monkeypatch):
    clock = [utcnow() + timedelta(seconds=1)]
    monkeypatch.setattr('memetrader.store.utcnow', lambda: clock[0])
    monkeypatch.setattr('memetrader.models.utcnow', lambda: clock[0])
    store = Store(tmp_path / 'event-money.db')
    store.activate_chain_meme_trader_funded_period()
    old = capital_policies()
    policy = event_actual_flow_policy()
    store.append_chain_meme_trader_policy(policy)
    assert old == capital_policies()
    start = clock[0]
    token, pair = TokenCandidate('solana', 'event-mint', 'Event', 'EVT'), 'event-pool'
    event = dict(source_kind='first_party', trusted=True, event_type='official_listing',
                 contract_address=token.address, observed_at=iso(start+timedelta(seconds=1)),
                 recorded_at=iso(start+timedelta(seconds=1)))
    clock[0] += timedelta(seconds=1)
    event_id = store.record_chain_meme_pattern_evidence(token.token_id, '', 'authoritative_event',
        event, observed_at=clock[0], source_key='official-event-1')
    clock[0] = start + timedelta(seconds=20)
    w = dict(complete=True, observed_at=iso(clock[0]), recorded_at=iso(clock[0]),
             window_start=event['recorded_at'], window_end=iso(start+timedelta(seconds=19)),
             net_quote_flow_raw=2_000_000, gross_quote_flow_raw=4_000_000, effective_breadth=2)
    flow = dict(complete=True, scan_complete=True, windows=[w],
                observed_at=iso(clock[0]), recorded_at=iso(clock[0]),
                resolver=dict(status='verified', pool_address=pair, base_mint=token.address))
    store.record_chain_meme_pattern_evidence(token.token_id, pair, 'amountful_flow', flow,
        observed_at=clock[0], source_key='flow-1')
    frame = dict(token_id=token.token_id, pair_address=pair, price=1, liquidity=1000,
                 observed_at=iso(clock[0]), ingested_at=iso(clock[0]), recorded_at=iso(clock[0]))
    context = dict(token_id=token.token_id, pair_address=pair, event=event, amountful_flow=flow)
    assert capital_observation_signal([frame], policy, decision_at=iso(clock[0]),
        activated_at=iso(start), context=context)[0]
    for change in ('pre_event', 'future', 'no_money', 'wrong_pool'):
        bad = copy.deepcopy(context)
        if change == 'pre_event': bad['amountful_flow']['windows'][0]['window_start'] = iso(start)
        if change == 'future': bad['amountful_flow']['windows'][0]['recorded_at'] = iso(clock[0]+timedelta(seconds=1))
        if change == 'no_money': bad['amountful_flow']['windows'][0]['net_quote_flow_raw'] = 0
        if change == 'wrong_pool': bad['amountful_flow']['resolver']['pool_address'] = 'another'
        assert not capital_observation_signal([frame], policy, decision_at=iso(clock[0]),
            activated_at=iso(start), context=bad)[0]
    for seconds in (21, 36):
        clock[0] = start+timedelta(seconds=seconds)
        snapshot = TokenSnapshot('solana', token.address, 1, 1000, 100000, 500, 0, 99999,
            observed_at=clock[0], ingested_at=clock[0], provider='dexscreener',
            raw={'pair': {'chainId':'solana','pairAddress':pair,'baseToken':{'address':token.address},
                          'dexId':'pumpswap','pairCreatedAt':int(start.timestamp()*1000),
                          'priceUsd':'1','liquidity':{'usd':1000}}})
        store.observe_chain_meme_pattern(token, snapshot, recorded_at=clock[0])
        if seconds == 21:
            row = store.db.execute('SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1').fetchone()
            assert policy['arm_id'] in json.loads(row[0])['ready_arm_ids']
    rows = store.db.execute('SELECT * FROM chain_meme_trader_trades WHERE arm_id=?', (policy['arm_id'],)).fetchall()
    assert len(rows) == 1 and rows[0]['side'] == 'BUY' and rows[0]['net_cash_flow_usd'] == -5
    cohort = store.db.execute('SELECT feature_json FROM chain_meme_trader_v6_cohorts WHERE id=?',
                             (rows[0]['shadow_cohort_id'],)).fetchone()
    assert json.loads(cohort[0])['event_keys'][policy['arm_id']] == event_id
    store.close()
