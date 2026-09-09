"""Bounded Pons curve diagnostics. Never a trade or market-price authority."""
from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from typing import Any

from .pons_observer import PonsV2Observer

SOURCE_SHA256 = '9e19cebed3b4ac659b9e3406fe3f8139ff8d59eb1da6e76bd9cbab915cd12684'
# Explicit hypothetical recipient, not a wallet/account and never used to send.
RECIPIENT = '0x0000000000000000000000000000000000000001'
SELECTORS = {'token': 'fc0c546a', 'pair': '3de35b79', 'factory': 'c45a0155',
             'sellable': '808bcddc', 'fee': '24a9d853', 'creator': 'c1bb8901',
             'snipe': 'd7e1ef39' + RECIPIENT[2:].zfill(64),
             'ready': 'c68360a5', 'graduated': 'e7c2b772',
             'real': '4f1f58fd', 'reserves': '0902f1ac'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def usd_conversion(asset, quote, address, now):
    def identity(row):
        return any(d.get('chainId') == 4663 and str(d.get('contractAddress', '')).lower() == address
                   for d in row.get('deployments', []))
    if not identity(asset) or not identity(quote) or asset.get('tokenSymbol') != quote.get('tokenSymbol'):
        raise ValueError('stock_identity_mismatch')
    generated = datetime.fromisoformat(quote['generatedAt'].replace('Z', '+00:00'))
    if not 0 <= (now - generated).total_seconds() <= 30:
        raise ValueError('stock_quote_stale_or_future')
    if quote.get('currency') != 'USD' or quote.get('isTradingHalt') is not False:
        raise ValueError('stock_usd_or_halt_unknown')
    if asset.get('status') != 'ASSET_STATUS_ACTIVE' or asset.get('pendingMultiplier'):
        raise ValueError('stock_multiplier_transition_or_inactive')
    m, bid, ask = (Decimal(str(x)) for x in (asset['currentMultiplier'], quote['bid'], quote['ask']))
    if not all(x.is_finite() and x > 0 for x in (m, bid, ask)) or bid > ask:
        raise ValueError('stock_price_invalid')
    return bid*m, ask*m


def roundtrip(state, budget, bid, ask, decimals):
    """Verified source integer rounding, hypothetical immediate post-buy sell."""
    if state['ready'] or state['graduated'] or state['sellable'] == 0:
        return {'budget_usd': budget, 'status': 'SELL_UNAVAILABLE'}
    q, t = state['reserves']
    f, tax = state['fee'], state['creator']
    if q <= 0 or t <= 0 or not 0 <= f+tax <= 9900 or not 0 <= decimals <= 36:
        raise ValueError('curve_state_invalid')
    sn = min(state['snipe'], 10000-f-tax-100)
    with localcontext() as ctx:
        ctx.prec = 80
        funds = int(Decimal(budget) / ask * 10**decimals)
        spent = funds
        net = spent-spent*f//10000-spent*tax//10000-spent*sn//10000
        amount = net*t//(q+net)
        if amount <= 0:
            return {'budget_usd': budget, 'status': 'UNKNOWN_DUST'}
        if amount > state['sellable']:
            amount = state['sellable']
            needed = amount*q//(t-amount)+1
            spent = min(funds, (needed*10000 + (10000-f-tax-sn)-1)//(10000-f-tax-sn))
            net = spent-spent*f//10000-spent*tax//10000-spent*sn//10000
        result = {'budget_usd': budget, 'quote_in_raw': str(spent), 'refund_raw': str(funds-spent),
                  'token_out_raw': str(amount), 'buy_usd': str(Decimal(spent)/10**decimals*ask)}
        if amount >= state['sellable']:
            return {**result, 'status': 'SELL_UNAVAILABLE', 'reason': 'hypothetical_buy_reaches_graduation'}
        gross = amount*(q+net)//t  # post-buy token reserve plus returned amount == original t
        if gross > state['real']+net:
            return {**result, 'status': 'UNKNOWN_REAL_RESERVE_SHORTFALL'}
        recovered = gross-gross*f//10000-gross*tax//10000
        usd = Decimal(recovered)/10**decimals*bid
        return {**result, 'status': 'MODEL_QUOTE', 'quote_recovered_raw': str(recovered),
                'sell_usd': str(usd), 'roundtrip_delta_usd': str(usd-Decimal(result['buy_usd']))}


class PonsEconomicsObserver:
    """At most one fresh launch per existing Pons rotation; caller bounds time."""
    def __init__(self, rpc, http):
        self.rpc, self.http = rpc, http
        self.verified_cache = {}

    async def observe(self, event: dict[str, Any], busy=lambda: False):
        result = {'status': 'UNKNOWN', 'decision_eligible': False, 'affects': 'none',
                  'recipient': RECIPIENT, 'recipient_semantics': 'hypothetical_only',
                  'requested_at': stamp(), 'token': event['token'], 'curve': event['curve'],
                  'quote_asset': event['pair_token'], 'source_sha256': SOURCE_SHA256}
        try:
            if event.get('factory') != PonsV2Observer.FACTORY or event.get('event') != 'TokenLaunched':
                raise ValueError('launch_identity_invalid')
            if busy():
                raise ValueError('held_priority_deferred')
            curve, pair = event['curve'].lower(), event['pair_token'].lower()
            verified = self.verified_cache.get(curve)
            if verified is None:
                response = await self.http.get(f'https://robinhoodchain.blockscout.com/api/v2/smart-contracts/{curve}', ttl=0)
                verified = response.json()
            assets = (await self.http.get('https://api.robinhood.com/rhj/assets', ttl=0)).json()
            if not verified.get('is_fully_verified') or hashlib.sha256(verified.get('source_code', '').encode()).hexdigest() != SOURCE_SHA256:
                raise ValueError('unverified_curve_source_version')
            if len(self.verified_cache) >= 32:
                self.verified_cache.pop(next(iter(self.verified_cache)))
            self.verified_cache[curve] = verified
            candidates = [a for a in assets.get('assets', []) if any(
                d.get('chainId') == 4663 and str(d.get('contractAddress', '')).lower() == pair
                for d in a.get('deployments', []))]
            if len(candidates) != 1:
                raise ValueError('stock_deployment_missing_or_ambiguous')
            asset = candidates[0]
            symbol = asset['tokenSymbol']
            if not symbol.isalnum():
                raise ValueError('stock_symbol_invalid')
            if busy():
                raise ValueError('held_priority_deferred')
            price = (await self.http.get(f'https://api.robinhood.com/rhj/prices/{symbol}', ttl=0)).json()
            quotes = [x for x in price.get('quotes', []) if x.get('tokenSymbol') == symbol]
            if len(quotes) != 1:
                raise ValueError('stock_quote_missing_or_ambiguous')
            quote = quotes[0]
            result['stock_receipt_at'] = stamp()
            bid, ask = usd_conversion(asset, quote, pair, datetime.now(timezone.utc))
            block = await self.rpc._rpc(PonsV2Observer.NETWORK, 'eth_blockNumber', [])
            if busy():
                raise ValueError('held_priority_deferred')
            calls = [(k, 'eth_call', [{'to': curve, 'data': '0x'+v}, block]) for k,v in SELECTORS.items()]
            calls += [('decimals', 'eth_call', [{'to': pair, 'data': '0x313ce567'}, block]),
                      ('code', 'eth_getCode', [curve, block]), ('block', 'eth_getBlockByNumber', [block, False]),
                      ('chain', 'eth_chainId', [])]
            async with self.rpc._lock:
                if busy():
                    raise ValueError('held_priority_deferred')
                await asyncio.sleep(max(0, self.rpc.http.min_host_interval -
                                        (time.monotonic()-self.rpc._last_request_started)))
                if busy():
                    raise ValueError('held_priority_deferred')
                self.rpc._last_request_started = time.monotonic()
                response = await self.rpc.http.client.post(PonsV2Observer.NETWORK['rpc_url'], json=[
                    {'jsonrpc':'2.0','id':i,'method':m,'params':p} for i,(_,m,p) in enumerate(calls)])
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, list) or len(payload) != len(calls):
                raise ValueError('rpc_batch_shape')
            indexed = {x['id']: x for x in payload}
            if set(indexed) != set(range(len(calls))) or any('error' in x for x in payload):
                raise ValueError('rpc_batch_error')
            raw = {k:indexed[i]['result'] for i,(k,_,_) in enumerate(calls)}
            if int(raw['chain'],16) != 4663 or raw['code'].lower() != verified['deployed_bytecode'].lower():
                raise ValueError('chain_or_bytecode_mismatch')
            for k, expected in [('token',event['token']),('pair',pair),('factory',PonsV2Observer.FACTORY)]:
                if raw[k].lower() != '0x'+expected[2:].lower().zfill(64):
                    raise ValueError('curve_identity_mismatch')
            state = {}
            for k in SELECTORS:
                if k in ('token','pair','factory'): continue
                value = raw[k]
                if len(value) != (130 if k == 'reserves' else 66):
                    raise ValueError('curve_abi_shape')
                state[k] = [int(value[2:66],16),int(value[66:],16)] if k == 'reserves' else int(value,16)
            observed = datetime.fromtimestamp(int(raw['block']['timestamp'],16),timezone.utc)
            now = datetime.now(timezone.utc)
            if state['ready'] not in (0,1) or state['graduated'] not in (0,1):
                raise ValueError('curve_status_invalid')
            if not 0 <= (now-observed).total_seconds() <= 30:
                raise ValueError('block_stale_or_future')
            # Conversion must remain fresh through completion, not just HTTP receipt.
            bid, ask = usd_conversion(asset, quote, pair, now)
            result.update(status='OBSERVED', block=block, block_hash=raw['block']['hash'],
                          observed_at=observed.isoformat(), state=state, quote=quote,
                          ingested_at=now.isoformat(),
                          multiplier=asset['currentMultiplier'],
                          quotes=[roundtrip(state,n,bid,ask,int(raw['decimals'],16)) for n in (5,20)])
        except Exception as exc:
            result['reason'] = str(exc)
        result['recorded_at'] = stamp()
        return result
