import sqlite3

from scripts.review_metrics151 import composite_exit151_diagnostics


ARM = 'alpha149_confirmed_recovery_decay_v1'


def fixture_db():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE chain_meme_trader_positions(
            definition_version TEXT, arm_id TEXT, shadow_cohort_id INTEGER, token_id TEXT,
            opened_at TEXT, closed_at TEXT, close_reason TEXT, capital_exit_state_json TEXT);
        CREATE TABLE chain_meme_trader_order_intents(
            definition_version TEXT, arm_id TEXT, shadow_cohort_id INTEGER, token_id TEXT,
            side TEXT, reason TEXT);
    ''')
    return db


def test_composite_diagnostics_distinguishes_no_trigger_from_unknown():
    db = fixture_db()
    db.execute('INSERT INTO chain_meme_trader_positions VALUES(?,?,?,?,?,?,?,?)',
        ('v1', ARM, 1, 'solana:one', '2026-09-13T00:00:00Z', '2026-09-13T00:10:00Z',
         'alpha149_vol_scaled_stop:dex_mark_paper_fill', '{"composite151":{"confirmation":{"first":1}}}'))
    result = composite_exit151_diagnostics(db)
    assert result['natural_paper_positions'] == 1
    assert result['independent_tokens'] == 1
    assert result['terminal_reasons'] == {'alpha149_vol_scaled_stop:dex_mark_paper_fill': 1}
    assert result['persisted_two_confirmation_trigger'] == {
        'status': 'not_observed', 'count': 0, 'evidence': 'persisted_sell_intent_exact_reason'}
    assert result['state_checkpoint']['pending_confirmation_positions'] == 1
    assert result['definition_version_counts'] == [
        {'definition_version': 'v1', 'positions': 1, 'independent_tokens': 1, 'open_positions': 0}]
    assert result['parent_comparison']['status'] == 'pending'


def test_composite_diagnostics_uses_exact_persisted_trigger_reason_and_cap():
    db = fixture_db()
    for cohort in range(3):
        db.execute('INSERT INTO chain_meme_trader_positions VALUES(?,?,?,?,?,?,?,?)',
            ('v1', ARM, cohort, f'solana:{cohort}', '2026-09-13T00:00:00Z',
             f'2026-09-13T00:0{cohort}:00Z', 'market_mark_max_hold:dex_mark_paper_fill',
             '{"composite151":{"first":1,"second":2}}'))
    db.execute('INSERT INTO chain_meme_trader_order_intents VALUES(?,?,?,?,?,?)',
        ('v1', ARM, 2, 'solana:2', 'SELL', 'confirmed_market_decay_net_recovery151'))
    db.execute('INSERT INTO chain_meme_trader_order_intents VALUES(?,?,?,?,?,?)',
        ('v1', ARM, 1, 'solana:1', 'SELL', 'some_other_reason'))
    result = composite_exit151_diagnostics(db, limit=2)
    assert result['truncated'] is True
    assert result['natural_paper_positions'] == 2
    assert result['persisted_two_confirmation_trigger'] == {
        'status': 'observed', 'count': 1, 'evidence': 'persisted_sell_intent_exact_reason'}
    assert result['state_checkpoint']['pending_confirmation_positions'] == 0


def test_composite_diagnostics_empty_sample_is_not_a_zero_trigger_claim():
    db = fixture_db()
    result = composite_exit151_diagnostics(db)
    assert result['status'] == 'no_natural_samples'
    assert result['persisted_two_confirmation_trigger']['status'] == 'no_natural_samples'
