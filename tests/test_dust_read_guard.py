"""Corroboration guard in front of the dust-pool terminal fact.

Measured on 2026-09-12 over the 24h write-off population: 19 of the 20 classifiable
written-off tokens were real rugs whose price collapsed by 3-6 orders of magnitude, and one
Solana pool reported `liquidity.usd` of exactly 0.0 while its price held at -3.9% and it kept
printing 19k-63k USD of 5-minute volume. That one contradicted read wrote off 48 positions
across 48 arms (-120U, 14% of the daily write-off loss).

These tests pin the separation: a real rug must still be written off, and a sub-floor print that
contradicts itself must not be.
"""
from memetrader import paper_execution as pe
from memetrader import store as store_module


def test_a_real_rug_is_not_contradicted():
    """BSC pool 0x7c6f...: 0.0003469 -> 3.346e-10 with liquidity 0.0 is a genuine death."""
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=3.346e-10, entry_price_usd=0.0003469,
        volume_5m_usd=50000.0, buys_5m=40, sells_5m=20) is False


def test_a_sub_floor_read_with_live_trading_at_a_held_price_is_contradicted():
    """solana:5SwF9vAr...: liquidity 0.0 while the price held and volume kept printing."""
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=3.002e-05, entry_price_usd=2.7e-05,
        volume_5m_usd=47429.3, buys_5m=40, sells_5m=20) is True
    # a negative liquidity is not "below floor" by the existing rule (invalid is not dust), so
    # the guard stays out of the way there too
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=-1.0, price_usd=1.0, entry_price_usd=1.0,
        volume_5m_usd=1000.0) is False


def test_the_guard_never_fires_above_the_floor():
    for liquidity in (1000.0, 5000.0, 250000.0):
        assert pe.dust_read_contradicted_by_live_trading(
            liquidity_usd=liquidity, price_usd=1.0, entry_price_usd=1.0,
            volume_5m_usd=1e9, buys_5m=999, sells_5m=999) is False


def test_a_merely_drained_pool_keeps_the_existing_writeoff():
    """Below the floor but physically possible: the existing terminal rule still applies.

    This is the behaviour the existing execution tests pin (liquidity 0.05 and 999.99 must
    still write off immediately).
    """
    for liquidity in (999.99, 999.0, 1.5, 0.05, 0.9):
        assert pe.dust_read_contradicted_by_live_trading(
            liquidity_usd=liquidity, price_usd=1.9, entry_price_usd=1.9,
            volume_5m_usd=1e6, buys_5m=99, sells_5m=99) is False
    # exactly zero is the impossible read the guard exists for
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=pe.DUST_IMPOSSIBLE_LIQUIDITY_USD, price_usd=1.9, entry_price_usd=1.9,
        volume_5m_usd=1e6, buys_5m=99, sells_5m=99) is True
    # ...but only with material volume: a zero-liquidity print with no volume is a dead pool
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.9, entry_price_usd=1.9,
        volume_5m_usd=0.0, buys_5m=1, sells_5m=1) is False


def test_the_guard_respects_a_custom_floor_from_the_definition():
    definition = {"min_pool_liquidity_usd": 25000.0}
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.0, entry_price_usd=1.0,
        volume_5m_usd=5000.0, definition=definition) is True
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=30000.0, price_usd=1.0, entry_price_usd=1.0,
        volume_5m_usd=5000.0, definition=definition) is False


def test_missing_fields_leave_the_previous_behaviour():
    """No positive evidence of a live pool means no interference with the dust rule."""
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.0, entry_price_usd=1.0,
        volume_5m_usd=None) is False
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.0, entry_price_usd=None,
        volume_5m_usd=1e6, buys_5m=10) is False
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=None, price_usd=1.0, entry_price_usd=1.0,
        volume_5m_usd=1e6, buys_5m=10) is False
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=0.0, entry_price_usd=1.0,
        volume_5m_usd=1e6, buys_5m=10) is False
    # zero volume is a dead pool, not a contradiction, whatever the trade count says
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.0, entry_price_usd=1.0,
        volume_5m_usd=0.0, buys_5m=0, sells_5m=0) is False
    # a small volume below the live-trading threshold is not enough on its own
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=1.0, entry_price_usd=1.0,
        volume_5m_usd=pe.DUST_LIVE_VOLUME_USD / 2.0) is False


def test_the_two_measured_populations_separate_exactly():
    """The 20 classifiable 24h write-off tokens, as (entry price, dust price, volume)."""
    real_rugs = [
        (0.0003469, 3.346e-10, 50000.0), (6.801e-05, 8.868e-10, 12000.0),
        (0.000152, 1.614e-09, 23525.0), (0.001071, 1.369e-06, 18160.0),
        (0.0005055, 8.699e-10, 107190.0), (0.0002927, 1.5e-09, 65750.0),
        (0.0002174, 7.655e-10, 70566.0), (1.0624e-07, 5.254e-12, 10365.0),
    ]
    for entry, dust, volume in real_rugs:
        assert pe.dust_read_contradicted_by_live_trading(
            liquidity_usd=0.0, price_usd=dust, entry_price_usd=entry,
            volume_5m_usd=volume, buys_5m=30, sells_5m=30) is False
    # the single contradicted case
    assert pe.dust_read_contradicted_by_live_trading(
        liquidity_usd=0.0, price_usd=3.002e-05, entry_price_usd=2.7e-05,
        volume_5m_usd=47429.3, buys_5m=60, sells_5m=25) is True


def test_the_store_helper_reads_the_mark_row_and_counts_vetos():
    class _Cursor:
        def fetchall(self):
            return []  # too little mark history: the previous behaviour must stand

    class _Db:
        def execute(self, *args, **kwargs):
            return _Cursor()

    class Fake:
        _dust_read_contradicted = store_module.Store._dust_read_contradicted
        _count_dust_veto = store_module.Store._count_dust_veto
        db = _Db()

        def __init__(self):
            self.kv = {}

        def set_kv(self, key, value):
            self.kv[key] = value

    fake = Fake()
    definition = {"min_pool_liquidity_usd": 1000.0}
    glitch = {"mark_liquidity_usd": 0.0, "mark_price_usd": 3.002e-05,
              "entry_signal_price_usd": 2.7e-05, "mark_volume_5m_usd": 47429.3,
              "mark_buys_5m": 60, "mark_sells_5m": 25,
              "token_id": "solana:T", "mark_pair_address": "P", "mark_observed_at": "2026-09-12T03:41:00Z"}
    rug = {"mark_liquidity_usd": 0.0, "mark_price_usd": 3.346e-10,
           "entry_signal_price_usd": 0.0003469, "mark_volume_5m_usd": 50000.0,
           "mark_buys_5m": 40, "mark_sells_5m": 20,
           "token_id": "bsc:T", "mark_pair_address": "P", "mark_observed_at": "2026-09-12T03:41:00Z"}
    assert fake._dust_read_contradicted(glitch, definition) is True
    assert fake._dust_read_contradicted(rug, definition) is False
    assert getattr(fake, "_dust_read_vetos", 0) == 1
    assert fake.kv.get("dust-read-vetos") == "1"
