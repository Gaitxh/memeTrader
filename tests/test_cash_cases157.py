from pathlib import Path
import sys
import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_cash_cases157 import cash_at, check_writeoff_evidence


def test_cash_uses_receipt_time_not_backdated_sell_and_does_not_count_unrealized_value():
    trades = [dict(id=1, side='BUY', net_cash_flow_usd=-990,
        created_at='2026-01-01T00:00:00Z', recorded_at='2026-01-01T00:00:01Z'),
        dict(id=2, side='SELL', net_cash_flow_usd=50,
        created_at='2026-01-01T00:00:02Z', recorded_at='2026-01-01T00:00:08Z')]
    early = cash_at(trades, '2026-01-01T00:00:05Z', 1000)
    assert early['cash'] == 10
    assert early['last_available_trade_id'] == 1
    late = cash_at(trades, '2026-01-01T00:00:08Z', 1000)
    assert late['cash'] == 60
    assert late['buy_debits'] == 990 and late['exit_receipts'] == 50


def test_missing_ledger_provenance_does_not_become_zero_cash():
    with pytest.raises(ValueError, match='provenance'):
        cash_at([dict(id=1, side='BUY', net_cash_flow_usd=-20,
            created_at='2026-01-01T00:00:00Z', recorded_at=None)], '2026-01-01T00:00:01Z', 1000)


def test_writeoff_missing_liquidity_and_wrong_pool_do_not_become_confirmed_dust():
    evidence = dict(pair_address='0xAB', observed_at='2026-01-01T00:00:00Z',
        recorded_at='2026-01-01T00:00:01Z', liquidity_usd=None)
    mark = dict(market_pair_address='0xab', trigger_evidence_json=json.dumps(dict(terminal_dust_pool=evidence)))
    result = check_writeoff_evidence('0xab', mark, '2026-01-01T00:00:02Z')
    assert result['same_original_pool'] and result['causal'] and not result['known_below_1000']
    assert not check_writeoff_evidence('0xcd', mark, '2026-01-01T00:00:02Z')['same_original_pool']
