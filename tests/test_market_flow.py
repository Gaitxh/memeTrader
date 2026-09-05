from copy import deepcopy

import pytest

from memetrader.market_flow import aggregate_market_frames, build_market_frame


def resolver(**changes):
    return dict(status="verified", pool_address="pool", base_mint="base", quote_mint="quote",
                base_decimals=6, quote_decimals=9, observed_at=1, recorded_at=2, **changes)


def trade(side="BUY", who="a", quote=100, *, sig="s", block=5, **changes):
    return dict(side=side, signer_address=who, quote_amount_raw=quote,
                base_amount_raw=2_000_000, signature=sig, instruction_path="outer:0",
                block_time=block, observed_at=21, recorded_at=22,
                pool_address="pool", base_mint="base", quote_mint="quote",
                amount_complete=True, amount_source="parsed_spl_transfer", **changes)


def window(start=0, end=10, trades=()):
    return dict(window_start=start, window_end=end, trades=list(trades), scan=dict(
        complete=True, coverage_complete=True, coverage_start=start, coverage_end=end,
        observed_at=23, recorded_at=24))


def build(rows=(), **changes):
    args = window(trades=rows)
    args.update(resolver=resolver(), decision_at=25)
    args.update(changes)
    return build_market_frame(**args)


def test_amountful_two_windows_breadth_new_repeat_creator_dust():
    out = aggregate_market_frames([
        window(trades=[trade(quote=100, sig="1"), trade(who="b", quote=50, sig="2")]),
        window(10, 20, [trade(quote=50, sig="3", block=11),
                       trade(who="c", quote=25, sig="4", block=12),
                       trade("SELL", "creator", 20, sig="5", block=13)]),
    ], creator_address="creator", dust_quote_raw=25, resolver=resolver(), decision_at=25)
    assert out["complete"] and out["adjacent"]
    first, second = out["windows"]
    assert first["effective_breadth"] == 150**2 / (100**2 + 50**2)
    assert first["top1_notional_share"] == 100 / 150
    assert second["new_buyer_notional_raw"] == 25
    assert second["repeat_buyer_notional_raw"] == 50
    assert second["creator_sell_quote_notional_raw"] == 20
    assert second["creator_sell_notional_share"] == 1
    assert second["dust_buy_quote_notional_raw"] == 25


def test_decimals_and_explicit_fresh_conversion_never_raw_times_usd():
    row = trade(quote=3_000_000_000)
    plain = build([row])
    assert plain["complete"]
    assert plain["buy_base_amount"] == 2
    assert plain["buy_quote_notional"] == 3
    assert plain["buy_quote_notional_usd"] is None
    assert plain["dust_buy_quote_notional_raw"] is None
    assert plain["creator_sell_quote_notional_raw"] is None
    conversion = dict(quote_mint="quote", usd_per_quote=150, observed_at=23,
                      recorded_at=24, max_age_seconds=5)
    converted = build([row], quote_conversion=conversion)
    assert converted["buy_quote_notional_usd"] == 450
    assert converted["capital_velocity_usd_per_second"] == 45
    six = resolver()
    six["quote_decimals"] = 6
    assert build([trade(quote=3_000_000)], resolver=six)["buy_quote_notional"] == 3
    for change in ({"observed_at": 0}, {"recorded_at": 26}, {"quote_mint": "other"},
                   {"usd_per_quote": float("nan")}):
        assert build([row], quote_conversion={**conversion, **change})["buy_quote_notional_usd"] is None


def test_real_empty_complete_windows_are_valid():
    out = aggregate_market_frames([window(), window(10, 20)], resolver=resolver(), decision_at=25)
    assert out["complete"]
    assert out["windows"][1]["buy_quote_notional_raw"] == 0
    assert out["windows"][1]["effective_breadth"] is None


@pytest.mark.parametrize("change", [dict(complete=False), dict(coverage_complete=False),
    dict(truncated=True), dict(status="TRUNCATED_INCOMPLETE"), dict(observed_at=None),
    dict(recorded_at=None), dict(recorded_at=26), dict(coverage_start=1), dict(coverage_end=9)])
def test_missing_truncated_or_future_scan_is_never_complete(change):
    assert not build(scan={**window()["scan"], **change})["complete"]


@pytest.mark.parametrize("change", [dict(pool_address="other"), dict(base_mint="other"),
    dict(quote_mint="other"), dict(amount_complete=False), dict(amount_source="instruction_limit"),
    dict(block_time=None), dict(block_time=0), dict(block_time=11), dict(observed_at=None),
    dict(recorded_at=26), dict(signer_address=""), dict(side="UNKNOWN"), dict(quote_amount_raw=1.5)])
def test_invalid_trade_amount_identity_time_or_side_fails_closed(change):
    out = build([{**trade(), **change}])
    assert not out["complete"] and out["invalid_count"] == 1
    assert out["buy_quote_notional_raw"] == 0


def test_resolver_provenance_and_decimals_are_required():
    for change in ({"quote_decimals": None}, {"base_decimals": None}, {"status": "unknown"},
                   {"recorded_at": 26}, {"observed_at": None}, {"pool_address": ""}):
        assert not build([trade()], resolver={**resolver(), **change})["complete"]


def test_block_time_uses_event_window_and_receipt_must_precede_decision():
    assert build([trade(block=10)])["complete"]  # received at 21, after window end
    assert not build([trade()], decision_at=20)["complete"]
    row = trade()
    row.update(block_time="2026-09-05T08:00:05+08:00", observed_at="2026-09-05T00:00:21Z",
               recorded_at="2026-09-05T00:00:22Z")
    scan = dict(complete=True, coverage_complete=True, coverage_start="2026-09-05T00:00:00Z",
                coverage_end="2026-09-05T00:00:10Z", observed_at=row["observed_at"], recorded_at=row["recorded_at"])
    assert build([row], window_start=scan["coverage_start"], window_end=scan["coverage_end"],
                 scan=scan, decision_at="2026-09-05T00:00:25Z")["complete"]


def test_duplicate_not_coordination_but_distinct_instruction_paths_are():
    original = trade()
    same = build([original, deepcopy(original)])
    assert same["complete"] and same["trade_count"] == 1 and same["duplicate_count"] == 1
    assert same["atomic_coordination_groups"] == []
    second = {**trade(who="b"), "instruction_path": "inner:0:1"}
    atomic = build([original, second])
    assert atomic["effective_breadth"] == 2
    assert atomic["atomic_adjusted_effective_breadth"] == 1
    assert atomic["atomic_coordination_signatures"] == ["s"]
    assert atomic["bundle_status"] == "unknown"
    conflict = build([original, {**original, "quote_amount_raw": 500}])
    assert not conflict["complete"] and conflict["trade_count"] == 0


@pytest.mark.parametrize("windows", [[window()], [window(), window(9, 20)],
    [window(), window(11, 20)], [window(), window(10, 20), window(20, 25)]])
def test_pair_requires_exactly_two_adjacent_nonoverlapping_windows(windows):
    assert not aggregate_market_frames(windows, resolver=resolver(), decision_at=25)["complete"]


def test_raw_transfers_not_instruction_limits_and_bounded_input():
    row = {**trade(quote=123), "max_quote_in_raw": 99999, "min_quote_out_raw": 999}
    assert build([row])["buy_quote_notional_raw"] == 123
    out = build(trade(sig=str(i)) for i in range(1000))
    assert not out["complete"] and len(out["trades"]) == 128
    assert "trade_limit_exceeded" in out["reasons"]


def test_same_instruction_cannot_be_reused_with_a_changed_block_time():
    out = aggregate_market_frames([window(trades=[trade(block=5)]),
                                   window(10, 20, [trade(block=15)])],
                                  resolver=resolver(), decision_at=25)
    assert not out["complete"] and out["cross_window_duplicates"]
