from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from memetrader.event_candidates import (
    freeze_event_candidates,
    rank_frozen_event_candidates,
)


START = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def stamp(seconds):
    return (START + timedelta(seconds=seconds)).isoformat()


def event(**changes):
    value = {
        "source": "okx", "source_kind": "first_party",
        "event_type": "official_listing", "title": "ABC will be listed",
        "url": "https://www.okx.com/help/abc", "identity_status": "no_exact_ca",
        "published_at": stamp(0), "observed_at": stamp(1), "ingested_at": stamp(2),
    }
    value.update(changes)
    return value


def candidate(name, index=0, **changes):
    value = {
        "token_id": f"solana:{name}", "chain": "solana", "address": name,
        "pair_address": f"pool-{name}", "snapshot_id": 100 + index,
        "provider": "dexscreener", "name": name, "symbol": name.upper(),
        "observed_at": stamp(3), "recorded_at": stamp(4),
    }
    value.update(changes)
    return value


def frozen(names=("a", "b")):
    action, reason, evidence = freeze_event_candidates(
        event(), [candidate(name, index) for index, name in enumerate(names)],
        query="ABC", frozen_at=stamp(5),
    )
    assert (action, reason) == ("FROZEN", "candidate_set_frozen")
    return evidence


def flow(name, evidence_id, seconds, net_raw, **payload_changes):
    payload = {
        "complete": True, "scan_complete": True,
        "future_data_rejected": False, "usd_conversion_complete": True,
        "conversion_basis": "USDC_unit_accounting_reference_not_executable_fill",
        "decision_at": stamp(seconds + .3),
        "net_quote_flow_raw": net_raw,
        "resolver": {
            "status": "verified", "pool_address": f"pool-{name}",
            "base_mint": name, "quote_mint": "USDC", "quote_decimals": 6,
            "observed_at": stamp(seconds - 1), "recorded_at": stamp(seconds - .9),
        },
        "quote_conversion": {
            "quote_mint": "USDC", "usd_per_quote": 1,
            "observed_at": stamp(seconds - 1), "recorded_at": stamp(seconds - .9),
            "max_age_seconds": 15,
        },
        "buy_count": 999999, "sell_count": 0,
    }
    payload.update(payload_changes)
    return {
        "id": evidence_id, "kind": "amountful_flow",
        "token_id": f"solana:{name}", "pair_address": f"pool-{name}",
        "observed_at": stamp(seconds), "recorded_at": stamp(seconds + .2),
        "payload": payload,
    }


def rank(frozen_set, rows, **changes):
    arguments = {
        "round_id": "round-1", "round_started_at": stamp(10),
        "decision_at": stamp(20),
    }
    arguments.update(changes)
    return rank_frozen_event_candidates(frozen_set, rows, **arguments)


def test_freeze_is_exact_no_ca_identity_and_never_merges_later_result():
    first = frozen()
    payload = first["payload"]
    assert payload["candidate_count"] == 2
    assert payload["event"]["contract_address"] is None
    assert payload["authoritative_ca"] is False
    assert all(item["authoritative_ca"] is False for item in payload["candidates"])

    action, reason, second = freeze_event_candidates(
        event(), [candidate("winner", 9)], query="changed", frozen_at=stamp(9),
        existing=first,
    )
    assert (action, reason) == ("FROZEN", "candidate_set_already_frozen")
    assert second == first
    assert {item["token_id"] for item in second["payload"]["candidates"]} == {
        "solana:a", "solana:b",
    }


@pytest.mark.parametrize("change,reason", [
    ({"contract_address": "OfficialMint"}, "invalid_no_ca_event"),
    ({"identity_status": "exact_ca"}, "invalid_no_ca_event"),
])
def test_freeze_rejects_event_claiming_an_official_ca(change, reason):
    action, got_reason, evidence = freeze_event_candidates(
        event(**change), [candidate("a")], query="ABC", frozen_at=stamp(5),
    )
    assert (action, got_reason, evidence) == ("WAIT", reason, {})


def test_freeze_rejects_wrong_chain_token_or_pool_identity():
    wrong = candidate("a", chain="bsc")
    assert freeze_event_candidates(event(), [wrong], query="ABC", frozen_at=stamp(5)) == (
        "WAIT", "invalid_candidate_identity_or_time", {},
    )
    no_pool = candidate("a", pair_address="")
    assert freeze_event_candidates(event(), [no_pool], query="ABC", frozen_at=stamp(5)) == (
        "WAIT", "invalid_candidate_identity_or_time", {},
    )


def test_unique_positive_actual_flow_leader_requires_next_independent_frame():
    rows = [flow("a", 201, 15, 8_000_000), flow("b", 202, 15, 3_000_000)]
    action, reason, evidence = rank(frozen(), rows)

    assert (action, reason) == ("SELECT", "unique_positive_actual_flow_leader")
    assert evidence["token_id"] == "solana:a"
    assert evidence["pair_address"] == "pool-a"
    selected = evidence["payload"]["selected"]
    assert selected == {
        "token_id": "solana:a", "pair_address": "pool-a",
        "amountful_evidence_id": 201,
        "identity_kind": "frozen_search_candidate_not_official_ca",
        "authoritative_ca": False,
    }
    assert evidence["payload"]["next_frame_trade_required"] is True
    assert evidence["payload"]["next_frame_rule"]["market_observed_at_strictly_after"] == stamp(20).replace("+00:00", "Z")
    assert all(row["flow_semantics"] == "actual_notional"
               for row in evidence["payload"]["candidates"])


@pytest.mark.parametrize("rows,reason", [
    ([flow("a", 201, 15, 8_000_000)], "incomplete_amountful_coverage"),
    ([flow("a", 201, 15, 8_000_000), flow("b", 202, 15, 8_000_000)],
     "top_actual_flow_tie"),
    ([flow("a", 201, 15, -1_000_000), flow("b", 202, 15, -2_000_000)],
     "nonpositive_net_flow_leader"),
])
def test_missing_tied_or_nonpositive_flow_waits(rows, reason):
    action, got_reason, evidence = rank(frozen(), rows)
    assert (action, got_reason) == ("WAIT", reason)
    assert evidence["payload"]["authoritative_ca"] is False
    assert evidence["payload"]["next_frame_trade_required"] is False


def test_wrong_pool_future_stale_or_unverified_flow_does_not_cover_candidate():
    good = flow("a", 201, 15, 8_000_000)
    invalid_rows = []
    wrong_pool = flow("b", 202, 15, 7_000_000)
    wrong_pool["pair_address"] = "other-pool"
    invalid_rows.append(wrong_pool)
    invalid_rows.append(flow("b", 203, 21, 7_000_000))
    invalid_rows.append(flow("b", 204, -20, 7_000_000))
    unverified = flow("b", 205, 15, 7_000_000)
    unverified["payload"]["resolver"]["status"] = "unverified"
    invalid_rows.append(unverified)

    action, reason, evidence = rank(frozen(), [good, *invalid_rows])
    assert (action, reason) == ("WAIT", "incomplete_amountful_coverage")
    assert evidence["payload"]["missing_token_ids"] == ["solana:b"]
    assert evidence["payload"]["covered_candidate_count"] == 1
