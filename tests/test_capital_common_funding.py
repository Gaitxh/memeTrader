from memetrader.capital_common_funding import (
    adjusted_flow_breadth, common_funding_adjusted_breadth_signal,
)


def _flow():
    return {
        "prior": {"complete": True, "observed_at": "2026-09-05T12:00:00Z", "recorded_at": "2026-09-05T12:00:01Z"},
        "current": {"complete": True, "observed_at": "2026-09-05T12:05:00Z", "recorded_at": "2026-09-05T12:05:01Z",
                     "trades": [
                         {"side": "BUY", "signer_address": "w1", "quote_amount_raw": 100,
                          "amount_complete": True, "amount_source": "parsed_spl_transfer"},
                         {"side": "BUY", "signer_address": "w2", "quote_amount_raw": 100,
                          "amount_complete": True, "amount_source": "parsed_spl_transfer"},
                         {"side": "BUY", "signer_address": "w3", "quote_amount_raw": 20,
                          "amount_complete": True, "amount_source": "parsed_spl_transfer"},
                     ]},
    }


def _edge(source, destination, signature):
    return {"relation_type": "observed_funding_transfer", "source": source, "destination": destination,
            "amount_raw": 1, "signature": signature, "observed_at": "2026-09-05T12:04:00Z",
            "recorded_at": "2026-09-05T12:04:01Z", "sealed_at": "2026-09-05T12:04:02Z"}


def test_explicit_funding_edges_collapse_amountful_buyers_only():
    result = adjusted_flow_breadth(_flow(), [_edge("funder", "w1", "s1"), _edge("funder", "w2", "s2")],
                                   decision_at="2026-09-05T12:05:30Z", activated_at="2026-09-05T11:00:00Z")
    assert result["status"] == "ok"
    assert result["adjusted_group_count"] == 2
    assert result["identity_semantics"].endswith("not_common_controller")


def test_future_or_ambiguous_edge_waits_and_no_edges_do_not_fake_adjustment():
    assert common_funding_adjusted_breadth_signal(_flow(), [], "2026-09-05T12:05:30Z", "2026-09-05T11:00:00Z")[0] is False
    ambiguous = [_edge("f1", "w1", "s1"), _edge("f2", "w1", "s2")]
    assert adjusted_flow_breadth(_flow(), ambiguous, decision_at="2026-09-05T12:05:30Z",
                                activated_at="2026-09-05T11:00:00Z")["adjusted_group_count"] == 3
    future = _edge("f", "w1", "s3"); future["recorded_at"] = "2026-09-05T12:06:00Z"
    assert adjusted_flow_breadth(_flow(), [future], decision_at="2026-09-05T12:05:30Z",
                                 activated_at="2026-09-05T11:00:00Z")["status"] == "wait_unsealed_funding_evidence"
