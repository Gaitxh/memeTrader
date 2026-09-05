from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.capital_cross_section import (
    MAX_HISTORY_PER_TOKEN,
    MAX_TOKENS,
    build_capital_cross_section,
)
from memetrader.capital_entry import capital_entry_signal
from memetrader.capital_policies import capital_policies


START = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def stamp(seconds):
    return (START + timedelta(seconds=seconds)).isoformat()


def market(token, pair, seconds, price, liquidity, sample):
    return {
        "id": sample, "sample_sequence": sample, "token_id": token,
        "pair_address": pair, "price": price, "liquidity": liquidity,
        "observed_at": stamp(seconds), "ingested_at": stamp(seconds + .1),
        "recorded_at": stamp(seconds + .2),
    }


def flow(token, pair, evidence_id, seconds, net_raw, **payload_changes):
    mint = token.split(":", 1)[1]
    payload = {
        "complete": True, "scan_complete": True,
        "future_data_rejected": False, "usd_conversion_complete": True,
        "conversion_basis": "USDC_unit_accounting_reference_not_executable_fill",
        "decision_at": stamp(seconds), "pool_address": pair,
        "net_quote_flow_raw": net_raw,
        "resolver": {
            "status": "verified", "pool_address": pair,
            "base_mint": mint, "quote_mint": "USDC", "quote_decimals": 6,
            "observed_at": stamp(seconds - 2), "recorded_at": stamp(seconds - 1.9),
        },
        "quote_conversion": {
            "quote_mint": "USDC", "usd_per_quote": 1,
            "observed_at": stamp(seconds - 2), "recorded_at": stamp(seconds - 1.9),
            "max_age_seconds": 15,
        },
        # Diagnostic counts deliberately have no monetary meaning.
        "buy_count": 1, "sell_count": 999,
        **payload_changes,
    }
    return {
        "id": evidence_id, "token_id": token, "pair_address": pair,
        "observed_at": stamp(seconds), "recorded_at": stamp(seconds + .3),
        "payload": payload,
    }


def item(name, first_price, last_price, first_liquidity, last_liquidity, net_raw):
    token, pair = f"solana:{name}", f"pool-{name}"
    return {
        "token_id": token, "pair_address": pair,
        "history": [
            market(token, pair, 60, first_price, first_liquidity, 1),
            market(token, pair, 95, last_price, last_liquidity, 2),
        ],
        "amountful_flow": flow(token, pair, name, 96, net_raw),
    }


def build(items, **changes):
    arguments = {
        "round_id": "round-1", "decision_at": stamp(100),
        "activated_at": stamp(0), "remaining_slots": 2,
    }
    arguments.update(changes)
    return build_capital_cross_section(items, **arguments)


def policy(direction):
    return next(value for value in capital_policies()
                if value["entry_filter"]["direction"] == direction)


def test_builds_ranked_contract_and_allowed_regime_from_actual_cross_section():
    rows = [
        item("a", 10, 12, 1000, 1100, 11_000_000),
        item("b", 10, 11, 1000, 1000, 5_000_000),
        item("c", 10, 9, 1000, 900, -4_500_000),
    ]
    contexts = build(rows)

    ranked = contexts["solana:a"]["ranker"]["candidates"]
    assert [candidate["token_id"] for candidate in ranked] == [
        "solana:a", "solana:b", "solana:c",
    ]
    assert [candidate["score"] for candidate in ranked] == pytest.approx([1, .5, 0])
    assert all(candidate["flow_semantics"] == "actual_notional" for candidate in ranked)
    assert contexts["solana:a"]["regime"]["cross_section_breadth"] == pytest.approx(2 / 3)
    assert contexts["solana:a"]["regime"]["depth_health"] == pytest.approx(2 / 3)
    assert contexts["solana:a"]["regime"]["throttle"] == "allow"

    base_context = {"token_id": "solana:a", "pair_address": "pool-a", **contexts["solana:a"]}
    assert capital_entry_signal(
        rows[0]["history"], policy("finite_capital_ranker"),
        stamp(100), stamp(0), base_context,
    ) == (True, "finite_capital_ranker_selected")
    assert capital_entry_signal(
        rows[0]["history"], policy("market_regime_throttle"),
        stamp(100), stamp(0), base_context,
    ) == (True, "market_regime_allowed")


def test_transaction_counts_never_change_score_or_regime():
    rows = [item("a", 10, 11, 1000, 1000, 4_000_000),
            item("b", 10, 9, 1000, 900, -2_000_000)]
    before = build(rows)
    changed = deepcopy(rows)
    changed[0]["amountful_flow"]["payload"].update(buy_count=0, sell_count=10**12)
    changed[1]["amountful_flow"]["payload"].update(buy_count=10**12, sell_count=0)
    after = build(changed)

    assert before == after


def test_wrong_identity_future_or_unverified_amounts_are_not_candidates():
    good_a = item("a", 10, 11, 1000, 1000, 4_000_000)
    good_b = item("b", 10, 11, 1000, 1000, 3_000_000)
    wrong = item("wrong", 10, 20, 1000, 2000, 99_000_000)
    wrong["amountful_flow"]["payload"]["resolver"]["pool_address"] = "other-pool"
    contexts = build([good_a, good_b, wrong])
    assert set(contexts) == {"solana:a", "solana:b"}
    assert {row["token_id"] for row in contexts["solana:a"]["ranker"]["candidates"]} == set(contexts)

    future = deepcopy(good_b)
    future["history"][-1]["recorded_at"] = stamp(101)
    assert build([good_a, future]) == {}
    unverified = deepcopy(good_b)
    unverified["amountful_flow"]["payload"]["usd_conversion_complete"] = False
    assert build([good_a, unverified]) == {}


def test_identity_canonicalizes_evm_but_preserves_solana_case():
    evm_a = item("0xABC", 10, 11, 1000, 1000, 4_000_000)
    evm_b = item("0xDEF", 10, 9, 1000, 900, -2_000_000)
    for row in (evm_a, evm_b):
        old = row["token_id"]
        row["token_id"] = old.replace("solana:", "bsc:")
        for history in row["history"]:
            history["token_id"] = row["token_id"]
        row["amountful_flow"]["token_id"] = row["token_id"]
    contexts = build([evm_a, evm_b])
    assert set(contexts) == {"bsc:0xabc", "bsc:0xdef"}

    sol_a = item("MintA", 10, 11, 1000, 1000, 4_000_000)
    sol_b = item("MintB", 10, 9, 1000, 900, -2_000_000)
    sol_a["history"][-1]["token_id"] = "solana:minta"
    assert build([sol_a, sol_b]) == {}


def test_input_caps_fail_closed_without_unbounded_iteration():
    same = item("a", 10, 11, 1000, 1000, 4_000_000)
    too_many_history = deepcopy(same)
    too_many_history["history"] = [
        market("solana:a", "pool-a", 60 + index, 10 + index / 100, 1000, index)
        for index in range(MAX_HISTORY_PER_TOKEN + 1)
    ]
    assert build([too_many_history, item("b", 10, 11, 1000, 1000, 3_000_000)]) == {}

    def token_stream():
        for index in range(MAX_TOKENS + 10):
            yield item(str(index), 10, 11, 1000, 1000, 1_000_000)

    assert build(token_stream()) == {}
