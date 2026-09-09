"""One mature rediscovery probe per chain; no ranking or provider requests."""
import json
from datetime import timedelta

LEASE_SECONDS = 120


def protected(runtime, token_id):
    if token_id in getattr(runtime, '_pattern_held_tokens', set()):
        return True
    store = getattr(runtime, 'store', None)
    safety = getattr(store, '_preentry_safety', None)
    if any(x.get('token_id') == token_id for x in getattr(safety, 'pending', {}).values()):
        return True
    for item in getattr(runtime, '_cohort_pending', {}).values():
        if any(s.get('selected', {}).get('token_id') == token_id for s in item.get('signals', {}).values()):
            return True
    if store is None or not hasattr(store, 'db'):
        return True  # No current proof that the incumbent is idle.
    with store._lock:
        if store.db.execute("SELECT 1 FROM chain_meme_trader_positions WHERE token_id=? AND status='open' LIMIT 1", (token_id,)).fetchone():
            return True
        for reason in ('pattern_observation', 'cohort_observation'):
            row = store.db.execute('SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations '
                'WHERE definition_version=? AND token_id=? AND reason=? ORDER BY id DESC LIMIT 1',
                (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, token_id, reason)).fetchone()
            if row and json.loads(row[0]).get('ready_arm_ids'):
                return True
    return False


def victim(runtime, watch, chain, now):
    candidates = [(key, item) for key, item in watch.items()
                  if item['token'].chain == chain and item['bucket'] == 'mature'
                  and key not in getattr(runtime, '_pattern_held_tokens', set())]
    probes = [(key, item) for key, item in candidates if item.get('rediscovery_probe')]
    if probes:
        candidates = probes  # Never rotate a second continuity slot.
    for key, item in sorted(candidates, key=lambda x: (x[1].get('admitted_at', now), x[0])):
        if (item.get('sampled_at') is not None
                and now >= item.get('admitted_at', now) + timedelta(seconds=LEASE_SECONDS)
                and not protected(runtime, key)):
            return key
    return None
