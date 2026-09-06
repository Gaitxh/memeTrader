from datetime import datetime, timedelta, timezone

from memetrader.opportunity_regime import classify_opportunity_regimes


BASE = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def row(i, *, price=2.0, liq=200.0, chain="bsc", lifecycle="launch"):
    t = BASE - timedelta(minutes=110 - i)
    stamp = t.isoformat().replace("+00:00", "Z")
    return {"token_id": f"t{i}", "chain": chain, "lifecycle": lifecycle,
            "source_cohort_id": f"c{i}", "pair_address": f"p{i}",
            "observed_at": stamp, "recorded_at": stamp,
            "target_at": stamp, "h0price": 1.0, "h15price": price,
            "h0liq": 200.0, "h15liq": liq, "status": "observed"}


def test_hot_classification_uses_cost_return_and_survival():
    out = classify_opportunity_regimes([row(i) for i in range(20)], now=BASE)
    group = out["groups"]["bsc|launch"]
    assert group["regime"] == "HOT"
    assert group["positive_ratio"] == 1.0
    assert group["survival_ratio"] == 1.0


def test_unknown_is_denominator_but_not_zero_return():
    rows = [row(i) for i in range(20)]
    for item in rows[:4]:
        item["h15price"] = None
        item["observed_at"] = None
        item["status"] = "UNKNOWN"
    out = classify_opportunity_regimes(rows, now=BASE)
    group = out["groups"]["bsc|launch"]
    assert group["total_episodes"] == 20
    assert group["known_episodes"] == 16
    assert group["coverage"] == 0.8
    assert group["positive_ratio"] == 1.0


def test_dedup_and_two_new_frontier_confirmation():
    rows = [row(i) for i in range(20)]
    rows.append(dict(rows[0], source_cohort_id="duplicate", h15price=0.1))
    first = classify_opportunity_regimes(rows, now=BASE)
    assert first["groups"]["bsc|launch"]["total_episodes"] == 20
    prior = first["state"]
    changed = [row(i, price=0.1) for i in range(20)]
    changed[0]["source_cohort_id"] = "new0"
    pending = classify_opportunity_regimes(changed, prior, now=BASE)
    assert pending["groups"]["bsc|launch"]["regime"] == "HOT"
    assert pending["groups"]["bsc|launch"]["candidate"] == "COLD"
    newer = [row(i, price=0.1) for i in range(20)]
    newer[0]["source_cohort_id"], newer[1]["source_cohort_id"] = "new0", "new1"
    newer[0]["recorded_at"] = (BASE - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    newer[1]["recorded_at"] = (BASE - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    # Two rows in one call do not count as two independent evaluation rounds.
    same_round = classify_opportunity_regimes(newer, prior, now=BASE)
    assert same_round["groups"]["bsc|launch"]["regime"] == "HOT"
    confirmed = classify_opportunity_regimes(newer, pending["state"], now=BASE + timedelta(seconds=61))
    assert confirmed["groups"]["bsc|launch"]["regime"] == "COLD"
    assert len(confirmed["state"]["groups"]["bsc|launch"]["seen"]) <= 1000


def test_unmatured_rows_are_ignored():
    future = row(1)
    future["target_at"] = (BASE + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    out = classify_opportunity_regimes([future], now=BASE)
    assert out["groups"] == {}
