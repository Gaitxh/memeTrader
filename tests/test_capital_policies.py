from memetrader.capital_policies import (
    authoritative_event_shock_signal,
    capital_policies,
    direct_lp_float_constrained_signal,
)

D = "2026-09-05T12:00:00Z"
A = "2026-09-05T10:00:00Z"


def ev(**values):
    return {"observed_at": "2026-09-05T11:59:50Z",
            "recorded_at": "2026-09-05T11:59:51Z", **values}


def policy(direction, **values):
    return {"entry_filter": {"direction": direction, **values}}


def test_direct_lp_requires_exact_surface_and_explicit_nonmigration():
    context = {
        "token_id": "solana:CA",
        "snapshot": ev(pool_surface={"status":"RESOLVED", "complete":True, "surface":"NORMAL_DIRECT"},
                         pool_supply_share=.1, lp_custody_risk="high"),
        "mint_permission": ev(known=True, status="renounced"),
    }
    ok, reason = direct_lp_float_constrained_signal(
        [], policy("direct_lp_float_constrained", min_pool_supply_share=.05), D, A, context)
    assert ok and reason == "direct_lp_float_soft_low_size"
    context["snapshot"] = dict(context["snapshot"], pool_surface={"status":"RESOLVED", "complete":True, "surface":"UNKNOWN"})
    assert not direct_lp_float_constrained_signal(
        [], policy("direct_lp_float_constrained", min_pool_supply_share=.05), D, A, context)[0]


def test_authoritative_event_requires_first_party_exact_ca_and_asof_receipt():
    p = policy("authoritative_event_shock", event_types=["official_launch"])
    c = {"token_id": "solana:CA", "event": ev(
        source_kind="first_party", trusted=True, event_type="official_launch",
        contract_address="CA")}
    assert authoritative_event_shock_signal([], p, D, A, c)[0]
    c["event"] = dict(c["event"], source_kind="promotion")
    assert not authoritative_event_shock_signal([], p, D, A, c)[0]


def test_catalog_has_18_independent_hypotheses_and_required_boundaries():
    policies = capital_policies()
    assert len(policies) == 18
    assert len({p["arm_id"] for p in policies}) == 18
    lp = next(p for p in policies if p["entry_family"] == "direct_lp_float_constrained")
    assert "mint_permission" in lp["required_inputs"]
    event = next(p for p in policies if p["entry_family"] == "authoritative_event_shock")
    assert "next_frame_trade" in event["required_inputs"]
    velocity = next(p for p in policies if p["entry_family"] == "capital_velocity")
    assert "postgraduation_status" in velocity["required_inputs"]
