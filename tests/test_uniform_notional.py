"""User-authorized change (2026-09-12): one uniform 20U per trade for every arm.

Same mechanism and same reasoning as the concurrency-cap floor: the registered contracts are frozen
and append-only, so the uniformization is applied where the EFFECTIVE definition is assembled, each
affected arm keeps its registered value plus the authorization basis and its original fingerprint,
and the runtime fingerprint is recomputed once per arm.

Absent `notional_usd` is never filled in: those arms already resolve to the definition-level default,
which is the same 20U, so adding a field would change nothing while making the history harder to read.
"""
import json
from datetime import datetime, timezone

from memetrader.store import Store
from test_resource_bound_store import setup_store

UNIFORM = 20.0
NOW = datetime(2026, 9, 12, 13, 0, tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')


def _register_arm(store, arm_id, policy_extra, *, canonical):
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    policy = {'arm_id': arm_id, 'canonical_id': canonical, 'forward_enabled': True,
              'no_historical_backfill': True, **policy_extra}
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


def test_a_registered_notional_below_the_uniform_size_is_raised(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-2u-v1'
    _register_arm(store, arm, {'notional_usd': 2.0, 'entry_filter': {'direction': 'probe'}},
                  canonical='probe-notional-2')
    policy = _policy(_effective(store), arm)
    assert policy['notional_usd'] == UNIFORM
    marker = policy['notional_revision']
    assert marker['registered'] == 2.0 and marker['effective'] == UNIFORM
    assert 'uniform' in marker['basis']
    store.close()


def test_a_notional_above_the_uniform_size_is_also_normalised(tmp_path, monkeypatch):
    """Uniform means one size, so an arm registered at 50U comes DOWN to 20U as well."""
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-50u-v1'
    _register_arm(store, arm, {'notional_usd': 50.0, 'entry_filter': {'direction': 'probe'}},
                  canonical='probe-notional-50')
    policy = _policy(_effective(store), arm)
    assert policy['notional_usd'] == UNIFORM
    assert policy['notional_revision']['registered'] == 50.0
    store.close()


def test_a_notional_already_at_the_uniform_size_is_untouched(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-20u-v1'
    _register_arm(store, arm, {'notional_usd': UNIFORM, 'entry_filter': {'direction': 'probe'}},
                  canonical='probe-notional-20')
    policy = _policy(_effective(store), arm)
    assert policy['notional_usd'] == UNIFORM
    assert not policy.get('notional_revision')
    store.close()


def test_order_size_is_carried_along_when_present(tmp_path, monkeypatch):
    """The native protocol arm sizes orders from `order_size_usd`; both fields must agree."""
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-native-v1'
    _register_arm(store, arm, {'notional_usd': 5.0, 'order_size_usd': 5.0,
                               'entry_filter': {'direction': 'probe'}}, canonical='probe-notional-native')
    policy = _policy(_effective(store), arm)
    assert policy['notional_usd'] == UNIFORM
    assert policy['order_size_usd'] == UNIFORM
    assert policy['notional_revision']['also_set'] == 'order_size_usd'
    store.close()


def test_an_absent_notional_is_not_filled_in(tmp_path, monkeypatch):
    """Absence already resolves to the definition default, which is the same size."""
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-absent-v1'
    _register_arm(store, arm, {'entry_filter': {'direction': 'probe'}}, canonical='probe-notional-none')
    policy = _policy(_effective(store), arm)
    assert 'notional_usd' not in policy
    assert not policy.get('notional_revision')
    store.close()


def test_the_registered_row_and_frozen_definition_are_not_modified(tmp_path, monkeypatch):
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-immutable-v1'
    registered = _register_arm(store, arm, {'notional_usd': 1.0,
                                            'entry_filter': {'direction': 'probe'}},
                               canonical='probe-notional-immutable')
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    raw_before = store._chain_meme_trader_registration(version)['definition_json']
    _effective(store)
    _effective(store)
    assert store._chain_meme_trader_registration(version)['definition_json'] == raw_before
    row = store.db.execute('SELECT policy_json FROM chain_meme_trader_policy_additions '
                           'WHERE definition_version=? AND arm_id=?', (version, arm)).fetchone()
    assert json.loads(row['policy_json']) == registered
    store.close()


def test_the_fingerprint_follows_the_uniform_notional(tmp_path, monkeypatch):
    """A capital experiment carries the notional inside its behaviour fingerprint."""
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-capital-v1'
    registered = _register_arm(
        store, arm,
        {'notional_usd': 5.0, 'capital_experiment': True,
         'entry_filter': {'direction': 'probe'}, 'required_inputs': []},
        canonical='probe-notional-capital')
    policy = _policy(_effective(store), arm)
    marker = policy['notional_revision']
    assert marker['registered_behavior_contract_hash'] == registered['behavior_contract_hash']
    expected = Store.chain_meme_trader_behavior_hash(
        policy, definition_version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    assert policy['behavior_contract_hash'] == expected
    assert policy['behavior_contract_hash'] != marker['registered_behavior_contract_hash']
    store.close()


def test_both_uniformizations_apply_to_the_same_arm(tmp_path, monkeypatch):
    """The cap floor and the uniform notional must co-exist on one policy."""
    store, _ = setup_store(tmp_path, monkeypatch)
    arm = 'uniform-notional-probe-both-v1'
    _register_arm(store, arm,
                  {'notional_usd': 2.0,
                   'entry_filter': {'direction': 'probe', 'max_concurrent_positions': 2}},
                  canonical='probe-notional-both')
    policy = _policy(_effective(store), arm)
    assert policy['notional_usd'] == UNIFORM
    assert policy['entry_filter']['max_concurrent_positions'] == 8
    assert policy['notional_revision']['registered'] == 2.0
    assert policy['concurrency_cap_revision']['registered'] == 2
    expected = Store.chain_meme_trader_behavior_hash(
        policy, definition_version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    assert policy['behavior_contract_hash'] == expected
    store.close()
