from copy import deepcopy
from datetime import datetime, timedelta, timezone

from memetrader.capital_entry import capital_observation_signal
from memetrader.capital_policies import opportunity_policies

A = datetime(2026, 9, 6, tzinfo=timezone.utc)


def stamp(seconds):
    return (A + timedelta(seconds=seconds)).isoformat()


def frames():
    return [{"token_id": "solana:T", "pair_address": "P", "price": price,
             "liquidity": depth, "observed_at": stamp(s), "ingested_at": stamp(s), "recorded_at": stamp(s)}
            for s, price, depth in ((1, 1., 1000), (31, 1.01, 1050), (61, 1., 1100),
                                    (91, 1.015, 1200), (121, 1.02, 1300))]


def call(direction, history, context):
    p = next(p for p in opportunity_policies() if p["entry_family"] == direction)
    return capital_observation_signal(history, p, decision_at=stamp(121), activated_at=stamp(0),
        context={"token_id": "solana:T", "pair_address": "P", **context})


def test_prebreakout_requires_two_real_nonoverlap_broad_windows():
    windows = [{"complete": True, "window_start": stamp(s), "window_end": stamp(e),
                "observed_at": stamp(e), "recorded_at": stamp(e), "net_quote_flow_raw": 30,
                "gross_quote_flow_raw": 100, "effective_breadth": 3, "top1_notional_share": .4}
               for s, e in ((1, 61), (61, 121))]
    flow = {"complete": True, "adjacent": True, "nonoverlap": True, "windows": windows,
            "observed_at": stamp(121), "recorded_at": stamp(121)}
    assert call("prebreakout_net_accumulation", frames(), {"amountful_flow": flow})[0]
    bad = deepcopy(flow)
    bad["windows"][1]["top1_notional_share"] = .99
    assert not call("prebreakout_net_accumulation", frames(), {"amountful_flow": bad})[0]
    bad = deepcopy(flow)
    bad["windows"][1]["window_start"] = stamp(31)
    assert not call("prebreakout_net_accumulation", frames(), {"amountful_flow": bad})[0]
    bad = deepcopy(flow)
    bad["windows"][1]["recorded_at"] = stamp(122)
    assert not call("prebreakout_net_accumulation", frames(), {"amountful_flow": bad})[0]


def test_liquidity_first_is_distinct_from_price_breakout_and_cannot_fill_missing_depth():
    assert call("liquidity_leads_price", frames(), {})[0]
    h = frames()
    h[-1]["price"] = 1.2
    assert call("liquidity_leads_price", h, {})[1] == "price_already_expanded"
    h = frames()
    h[2]["liquidity"] = None
    assert not call("liquidity_leads_price", h, {})[0]


def test_no_ca_selected_candidate_still_requires_later_identity_bound_observation():
    ranked = {"action": "SELECT", "authoritative_ca": False,
              "selected": {"token_id": "solana:T", "pair_address": "P"},
              "observed_at": stamp(120), "recorded_at": stamp(120), "decision_at": stamp(120)}
    assert call("no_ca_event_flow_leader", frames(), {"no_ca_event": ranked})[0]
    ranked["decision_at"] = stamp(121)
    assert not call("no_ca_event_flow_leader", frames(), {"no_ca_event": ranked})[0]
    ranked["decision_at"] = stamp(120)
    ranked["selected"]["pair_address"] = "OTHER"
    assert not call("no_ca_event_flow_leader", frames(), {"no_ca_event": ranked})[0]
