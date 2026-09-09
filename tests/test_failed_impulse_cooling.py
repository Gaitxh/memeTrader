from datetime import timedelta
import pytest
from memetrader.failed_impulse_cooling import ARM, PARENT, CORE, latest_loss_receipt
from memetrader.models import TokenCandidate, iso
from test_resource_bound_store import setup_store, quote


@pytest.mark.parametrize('status,pnl,receipt_offset,pool,qualifies', [
    ('closed', -1, -1, 'Pool', True), ('written_off', -5, -1, 'Pool', True),
    ('closed', 1, -1, 'Pool', False), ('open', -1, -1, 'Pool', False),
    ('closed', -1, 1, 'Pool', False), ('closed', -1, 0, 'Pool', False),
    ('closed', -1, -1, 'Other', False)])
def test_receipt_and_prospective_entry(tmp_path, monkeypatch, status, pnl, receipt_offset, pool, qualifies):
    s, clock = setup_store(tmp_path, monkeypatch)
    s.register_chain_meme_resource_bound_research()
    token = TokenCandidate('solana', 'CoolingFixture', 'Cooling')
    created = int((clock[0]-timedelta(minutes=90)).timestamp()*1000)
    for _ in range(2):
        clock[0] += timedelta(seconds=16)
        s.observe_chain_meme_pattern(token, quote(token, 'Pool', created, clock[0], age_rate=True), recorded_at=clock[0])
    core = s.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?', (CORE,)).fetchone()
    assert core
    close_at = clock[0]
    signal_at = close_at+timedelta(seconds=16)
    with s.db:
        s.db.execute('UPDATE chain_meme_trader_positions SET status=?,closed_at=?,realized_pnl_usd=? WHERE arm_id=?',
                     (status, iso(close_at), pnl, CORE))
        s.db.execute("INSERT INTO chain_meme_trader_trades(definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,net_cash_flow_usd,realized_pnl_usd,reason,created_at,recorded_at) VALUES(?,?,?,?, 'SELL',1,1,?,'fixture',?,?)",
                     (core['definition_version'], CORE, core['shadow_cohort_id'], token.token_id, pnl,
                      iso(close_at), iso(signal_at+timedelta(seconds=receipt_offset))))
    assert bool(latest_loss_receipt(s.db, token.token_id, pool, signal_at)) == qualifies
    original = s._chain_meme_trader_registration(core['definition_version'])['definition_json']
    assert s.register_failed_impulse_cooling103() == 1
    assert s.register_failed_impulse_cooling103() == 0
    assert s._chain_meme_trader_registration(core['definition_version'])['definition_json'] == original
    clock[0] = signal_at
    s.observe_chain_meme_pattern(token, quote(token, pool, created, clock[0], cooling=True), recorded_at=clock[0])
    assert s.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?', (ARM,)).fetchone()[0] == 0
    # Future receipts may legitimately qualify on a later NEW signal; only test
    # next-frame admission here when receipt availability is unchanged.
    if receipt_offset < 0:
        for _ in range(3):
            clock[0] += timedelta(seconds=16)
            s.observe_chain_meme_pattern(token, quote(token, pool, created, clock[0], cooling=True), recorded_at=clock[0])
        assert s.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?', (ARM,)).fetchone()[0] == int(qualifies)
        if qualifies:
            assert s.db.execute('SELECT COUNT(*) FROM chain_meme_cohort_enrollment_claims WHERE arm_id=?', (ARM,)).fetchone()[0] == 1
            parent = s.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?', (PARENT,)).fetchone()
            child = s.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?', (ARM,)).fetchone()
            assert parent['source_entry_fill_id'] == child['source_entry_fill_id']
    s.close()
