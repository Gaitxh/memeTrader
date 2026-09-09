from memetrader.admission_shadow import AdmissionShadow


def event(token_id, now, *, bucket="early", held=(), eligible=True, buys=5, sells=5,
          provider="dex", quote_asset="USDC", actual_pre=None, actual=None, **extra):
    candidate = {
        "token_id": token_id, "chain": "bsc", "pool": f"pool-{token_id}", "bucket": bucket,
        "created_at": now - 20, "observed_at": now, "recorded_at": now,
        "ingested_at": now, "price": 1.0, "liquidity": 5000.0, "buys": buys,
        "sells": sells, "provider": provider, "quote_asset": quote_asset, "eligible": eligible,
    }
    candidate.update(extra)
    return {"received_at": now, "held": list(held), "candidate": candidate,
            "actual_pre": [] if actual_pre is None else actual_pre,
            "actual": {"admitted": False, "reason": "legacy", "victim": None}
            if actual is None else actual}


def test_rejects_noncausal_receipts_without_copying_control_or_pnl():
    shadow = AdmissionShadow()
    row = shadow.process(event("late", 1000, observed_at=1001,
                               actual_pre=[{"token_id": "legacy", "expires_at": 2000}],
                               actual={"admitted": False, "reason": "full", "victim": "old"}))
    assert row["reason"] == "INELIGIBLE_OR_NONCAUSAL"
    assert set(row) == {"challenger", "admitted", "reason", "victim", "occupancy", "pre_state", "ranking_version"}
    assert row["ranking_version"] == "admission-shadow-v1"


def test_fixed_base_borrow_and_base_reclaim_never_exceed_ten():
    shadow = AdmissionShadow()
    now = 1000.0
    for index in range(10):
        row = shadow.process(event(f"e{index}", now + index))
        assert row["admitted"]
    assert row["occupancy"]["by_bucket"] == {"early": 10, "growth": 0, "mature": 0}
    # Leases have elapsed, so growth can reclaim one surplus early candidate.
    row = shadow.process(event("growth", now + 200, bucket="growth", created_at=now - 2000))
    assert row["admitted"]
    assert row["reason"] == "BASE_RESERVATION_RECLAIM"
    assert row["victim"] is not None
    assert row["occupancy"]["nonheld_total"] == 10
    assert row["occupancy"]["by_bucket"] == {"early": 9, "growth": 1, "mature": 0}


def test_protected_lease_then_missing_checkpoint_and_deterministic_tie_choose_challenger():
    shadow = AdmissionShadow()
    for token_id in ("z", "y", "x", "e0", "e1", "e2", "e3", "e4", "e5", "e6"):
        assert shadow.process(event(token_id, 1000, buys=5, sells=5))["admitted"]
    blocked = shadow.process(event("a", 1010, buys=5, sells=5))
    assert blocked["reason"] == "PROTECTED_LEASE"
    # A causal receipt fills only the 60s checkpoint for z.  The comparator
    # retains the identities still missing both checkpoints, so z is evicted.
    assert shadow.process(event("z", 1061, buys=5, sells=5))["reason"] == "ALREADY_WATCHED"
    row = shadow.process(event("a", 1160, buys=5, sells=5, provider="other"))
    assert row["admitted"]
    assert row["victim"] == "z"
    assert row["reason"] == "RANKED_REPLACEMENT"


def test_other_pool_and_cached_receipts_cannot_change_checkpoint_history():
    shadow = AdmissionShadow()
    assert shadow.process(event("same", 1000))["admitted"]
    assert shadow.process(event("same", 1060, pool="other"))["reason"] == "OTHER_POOL_SKIP"
    assert shadow.process(event("same", 1061, observed_at=1000))["reason"] == "DUPLICATE_OR_STALE_RECEIPT"
    row = shadow.process(event("same", 1062))
    assert row["reason"] == "ALREADY_WATCHED"
    assert row["pre_state"][0]["checkpoints"] == {}
    row = shadow.process(event("same", 1120))
    assert row["reason"] == "ALREADY_WATCHED"
    assert row["pre_state"][0]["checkpoints"] == {"60": 1062}


def test_quiet_reservation_requires_measured_counts_and_held_does_not_consume_capacity():
    shadow = AdmissionShadow()
    for token_id in ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"):
        assert shadow.process(event(token_id, 1000, buys=8, sells=8))["admitted"]
    quiet = shadow.process(event("quiet", 1200, buys=1, sells=2))
    assert quiet["admitted"] and quiet["victim"] is not None
    assert shadow.process(event("unknown", 1201, buys=None, sells=None))["reason"] == "CHALLENGER_NOT_BETTER"
    held = shadow.process(event("held", 1202, held={"held"}))
    assert held["admitted"] and held["reason"] == "HELD_EXEMPT"
    assert held["occupancy"]["nonheld_total"] == 10


def test_aged_early_overflow_rebuckets_without_exceeding_chain_capacity():
    shadow = AdmissionShadow()
    for index in range(10):
        assert shadow.process(event(f"age{index}", 1000))["admitted"]
    row = shadow.process(event("new", 1899))
    assert len(row["pre_state"]) == 4
    assert row["occupancy"]["nonheld_total"] == 5
    assert row["occupancy"]["by_bucket"] == {"early": 1, "growth": 4, "mature": 0}


def test_delayed_frame_not_checkpoint_and_held_survives_expiry():
    shadow = AdmissionShadow()
    shadow.process(event("a", 1000))
    shadow.process(event("a", 1060, observed_at=1035))
    row = shadow.process(event("a", 1070, observed_at=1065))
    assert row["pre_state"][0]["checkpoints"] == {}
    shadow.process(event("a", 2000, held={"a"}))
    assert shadow._watch["a"]["admitted_at"] == 1000
    assert shadow._watch["a"]["expires_at"] == 1900
    shadow.process(event("other", 2001))
    assert "a" not in shadow._watch
