import copy
import json
from datetime import timedelta

from memetrader.capital_common_funding import common_funding_policy, common_funding_adjusted_breadth_signal
from memetrader.models import TokenCandidate, TokenSnapshot, utcnow, iso
from memetrader.store import Store


def test_actual_common_funding_signal_and_next_frame_store_buy(tmp_path, monkeypatch):
    clock = [utcnow()+timedelta(seconds=1)]
    monkeypatch.setattr('memetrader.store.utcnow', lambda: clock[0])
    monkeypatch.setattr('memetrader.models.utcnow', lambda: clock[0])
    store = Store(tmp_path/'funding-relation.db')
    store.activate_chain_meme_trader_funded_period()
    policy = common_funding_policy()
    store.append_chain_meme_trader_policy(policy)
    start = clock[0]
    stamp = lambda seconds: iso(start+timedelta(seconds=seconds))
    windows = [dict(complete=True, window_start=stamp(i), window_end=stamp(i+10),
        observed_at=stamp(i+11), recorded_at=stamp(i+11), trades=[dict(
            signer_address=buyer, side='BUY', quote_amount_raw=1_000_000,
            signature=str(i)+buyer, instruction_path='0', amount_complete=True,
            amount_source='parsed_spl_transfer', block_time=stamp(i+5),
            observed_at=stamp(i+11), recorded_at=stamp(i+11)) for buyer in 'ABCD']) for i in (1,11)]
    edges = [dict(relation_type='observed_funding_transfer', signature='fund'+buyer,
        instruction_path='0', source='F', destination=buyer, amount_raw=2_000_000,
        observed_at=stamp(12), recorded_at=stamp(12), sealed_at=stamp(12)) for buyer in 'AB']
    assert common_funding_adjusted_breadth_signal(dict(prior=windows[0],current=windows[1]),
        edges, stamp(23), stamp(0), policy['entry_filter'])[0]
    bad = copy.deepcopy(edges)
    bad[0]['sealed_at'] = stamp(24)
    assert not common_funding_adjusted_breadth_signal(dict(prior=windows[0],current=windows[1]),
        bad, stamp(23), stamp(0), policy['entry_filter'])[0]
    token,pair = TokenCandidate('solana','funding-mint','Funding','FUN'), 'funding-pool'
    clock[0] = start+timedelta(seconds=22)
    flow = dict(complete=True, adjacent=True, nonoverlap=True, windows=windows,
        observed_funding_transfers=edges, resolver=dict(status='verified',pool_address=pair,base_mint=token.address))
    store.record_chain_meme_pattern_evidence(token.token_id,pair,'amountful_flow',flow,
        observed_at=clock[0],source_key='funding-flow')
    for sec in (23,38):
        clock[0] = start+timedelta(seconds=sec)
        snap = TokenSnapshot('solana', token.address,1,1000,100000,100,4,1,
            observed_at=clock[0],ingested_at=clock[0],provider='dexscreener',
            raw={'pair':{'chainId':'solana','pairAddress':pair,'baseToken':{'address':token.address},
                'dexId':'pumpswap','pairCreatedAt':int(start.timestamp()*1000),'priceUsd':'1','liquidity':{'usd':1000}}})
        store.observe_chain_meme_pattern(token,snap,recorded_at=clock[0])
        if sec == 23:
            row = store.db.execute('SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1').fetchone()
            assert policy['arm_id'] in json.loads(row[0])['ready_arm_ids']
    trades=store.db.execute('SELECT side,net_cash_flow_usd FROM chain_meme_trader_trades WHERE arm_id=?',(policy['arm_id'],)).fetchall()
    assert len(trades)==1 and tuple(trades[0])==('BUY',-5)
    store.close()
