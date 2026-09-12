"""User-authorized change (2026-09-12): every per-arm concurrency cap below 8 becomes 8.

The registered policy contracts are frozen and append-only, and `chain_meme_trader_policy_additions`
forbids UPDATE/DELETE by trigger, so the raise is applied where the EFFECTIVE definition is
assembled. That reaches every consumer at once (entry gating, pending limits, UI) and covers existing
arms as well as future ones, while the registered rows keep their original values and each affected
policy carries its original value and the authorization basis.

An arm without the field is deliberately NOT given one: absence means "no cap", which is not a value
below the floor. Pinning those to 8 would be a tightening, not the requested raise.
"""
import json
from datetime import datetime, timezone

from memetrader.store import Store
from test_resource_bound_store import setup_store

FLOOR = 8
NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


def _register_arm(store, arm_id, entry_filter, *, canonical):
    """Append one synthetic arm exactly the way scripts/register_alpha149.py does."""
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    policy = {'arm_id': arm_id, 'canonical_id': canonical, 'entry_filter': dict(entry_filter),
              'notional_usd': 20.0, 'forward_enabled': True, 'no_historical_backfill': True}
    policy['behavior_contract_hash'] = Store.chain_meme_trader_behavior_hash(
        policy, definition_version=version)
    with store._lock, store.db:
        store.db.execute(
            'INSERT INTO chain_meme_trader_policy_additions('
            'definition_version,arm_id,canonical_id,registered_at,activated_at,'
            'activation_snapshot_id,activation_evaluation_id,behavior_contract_hash,'
            'policy_json) VALUES(?,?,?,?,?,?,?,?,?)',
            (version, arm_id, canonical, NOW, NOW, 0, 0,
             policy['behavior_contract_hash'], json.dumps(policy, ensure_ascii=False)))
    return policy


def _effective(store):
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    raw = store._chain_meme_trader_registration(version)['definition_json']
    return store.chain_meme_trader_effective_definition_from_connection(store.db, version, raw)


def _policy(definition, arm_id):
    return next(p for p in definition['policies'] if p.get('arm_id') == arm_id)


def test_a_registered_cap_below_the_floor_is_raised_at_runtime(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'concurrency-cap-floor-probe-v1'
    _register_arm(store, arm, {'direction': 'probe', 'max_concurrent_positions': 2,
                               'single_token_lifetime_entry': True}, canonical='probe-cap-2')
    policy = _policy(_effective(store), arm)
    assert policy['entry_filter']['max_concurrent_positions'] == FLOOR
    marker = policy['concurrency_cap_revision']
    assert marker['registered'] == 2 and marker['effective'] == FLOOR
    assert marker['field'] == 'entry_filter.max_concurrent_positions'
    assert 'user instruction' in marker['basis']
    # everything else about the arm is untouched
    assert policy['entry_filter']['single_token_lifetime_entry'] is True
    assert policy['entry_filter']['direction'] == 'probe'
    store.close()


def test_a_cap_at_or_above_the_floor_is_left_alone(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    for arm, cap, canonical in (('cap-floor-probe-exact-v1', FLOOR, 'probe-cap-8'),
                                ('cap-floor-probe-above-v1', 12, 'probe-cap-12')):
        _register_arm(store, arm, {'direction': 'probe', 'max_concurrent_positions': cap},
                      canonical=canonical)
    definition = _effective(store)
    for arm, cap in (('cap-floor-probe-exact-v1', FLOOR), ('cap-floor-probe-above-v1', 12)):
        policy = _policy(definition, arm)
        assert policy['entry_filter']['max_concurrent_positions'] == cap
        assert not policy.get('concurrency_cap_revision')
    store.close()


def test_a_policy_without_the_field_is_left_without_one(tmp_path, monkeypatch):
    """Absence is 'no cap', which is not below the floor; adding one would tighten the arm."""
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'cap-floor-probe-uncapped-v1'
    _register_arm(store, arm, {'direction': 'probe'}, canonical='probe-cap-none')
    policy = _policy(_effective(store), arm)
    assert 'max_concurrent_positions' not in policy['entry_filter']
    assert not policy.get('concurrency_cap_revision')
    store.close()


def test_the_registered_rows_and_frozen_definition_are_not_modified(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'cap-floor-probe-immutable-v1'
    registered = _register_arm(store, arm, {'direction': 'probe', 'max_concurrent_positions': 1},
                               canonical='probe-cap-1')
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    raw_before = store._chain_meme_trader_registration(version)['definition_json']
    _effective(store)
    _effective(store)  # rebuilding must not accumulate state
    assert store._chain_meme_trader_registration(version)['definition_json'] == raw_before
    row = store.db.execute(
        'SELECT policy_json FROM chain_meme_trader_policy_additions '
        'WHERE definition_version=? AND arm_id=?', (version, arm)).fetchone()
    assert json.loads(row['policy_json']) == registered
    store.close()


def test_the_recomputed_fingerprint_describes_the_effective_cap(tmp_path, monkeypatch):
    """The runtime hash must follow the cap, so it still describes what the policy does."""
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'cap-floor-probe-fingerprint-v1'
    registered = _register_arm(store, arm, {'direction': 'probe', 'max_concurrent_positions': 4},
                               canonical='probe-cap-4')
    policy = _policy(_effective(store), arm)
    marker = policy['concurrency_cap_revision']
    assert marker['registered_behavior_contract_hash'] == registered['behavior_contract_hash']
    expected = Store.chain_meme_trader_behavior_hash(
        policy, definition_version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    assert policy['behavior_contract_hash'] == expected
    assert policy['behavior_contract_hash'] != marker['registered_behavior_contract_hash']
    store.close()


def test_the_top_level_marker_reports_what_was_raised(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    for arm, cap, canonical in (('cap-floor-probe-a-v1', 1, 'probe-a'), ('cap-floor-probe-b-v1', 2, 'probe-b')):
        _register_arm(store, arm, {'direction': 'probe', 'max_concurrent_positions': cap},
                      canonical=canonical)
    definition = _effective(store)
    top = definition['concurrency_cap_floor']
    assert top['floor'] == FLOOR
    assert top['raised_policies'] == len(top['detail']) == 2
    assert {d['arm_id'] for d in top['detail']} == {'cap-floor-probe-a-v1', 'cap-floor-probe-b-v1'}
    assert {d['registered'] for d in top['detail']} == {1, 2}
    store.close()
