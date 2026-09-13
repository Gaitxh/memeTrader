"""Available-data Paper replacements, not distinct-wallet or safety evidence."""
from copy import deepcopy
from math import isfinite

SPECS = {
    'alpha149_trade_activity_growth_proxy_v1': (
        'trade_activity_growth151', '成交活跃度增长代理151', 'alpha149_participant_growth_v1'),
    'alpha149_buy_pressure_no_breadth_v1': (
        'buy_pressure_no_breadth151', '买盘占比151·无钱包广度条件', 'alpha149_participant_breadth_v1'),
}
DESCRIPTIONS = {
    'trade_activity_growth151': '独立Paper：用相邻原池快照滚动5分钟成交笔数增长>10%替代不可得的独立买家增长，'
        '成交额不下降、买笔占比≥55%、流动性≥3000U且保留≥前帧98%。不是新钱包数或净资金流；旧臂不改。',
    'buy_pressure_no_breadth151': '独立Paper：仅取消无法获得的独立买家数/买笔数条件；'
        '保留买笔占比≥60%、流动性≥3000U且不下降。不能识别捆绑、集中度或独立钱包；旧臂不改。',
}

def num(x):
    try:
        value = float(x)
        return value if isfinite(value) and not isinstance(x, bool) else None
    except (TypeError, ValueError):
        return None

def flags(f):
    out = {kind: False for kind, _, _ in SPECS.values()}
    if not isinstance(f, dict):
        return out
    cur, prev = f.get('current') or {}, f.get('prev') or {}
    liq, old = num(cur.get('liquidity_usd')), num(prev.get('liquidity_usd'))
    share = num(f.get('buy_count_share'))
    if liq is None or old is None or liq < 3000 or old <= 0 or share is None:
        return out
    out['buy_pressure_no_breadth151'] = share >= .6 and liq >= old
    counts = [num(row.get(key)) for row in (cur, prev) for key in ('buys_5m', 'sells_5m')]
    vol, prior_vol = num(cur.get('volume_5m_usd')), num(prev.get('volume_5m_usd'))
    if all(n is not None and n >= 0 for n in counts) and sum(counts[2:]) > 0:
        out['trade_activity_growth151'] = bool(
            sum(counts[:2]) > sum(counts[2:]) * 1.1 and share >= .55 and liq >= old * .98
            and vol is not None and prior_vol is not None and vol >= prior_vol > 0)
    return out

def policy(base, arm):
    kind, name, parent = SPECS[arm]
    result = deepcopy(base)
    result.update(arm_id=arm, canonical_id=arm, entry_family=arm, name=name,
        entry_filter={**base.get('entry_filter', {}), 'direction': arm},
        source_arm_ids=[parent], excess_return_vs_arm=parent,
        feature_hypothesis=kind, feature_contract='market-proxy/151-v1',
        description=DESCRIPTIONS[kind])
    for key in ('behavior_contract_hash', 'forward_activation_snapshot_id', 'forward_started_at'):
        result.pop(key, None)
    return result
