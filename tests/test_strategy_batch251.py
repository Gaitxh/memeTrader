from copy import deepcopy
from datetime import timedelta

from memetrader import bsc_survival253, diversified_router252, liquidity_breadth254, trend_regime251
from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.models import iso, utcnow
from memetrader.revision_evidence_extensions import revise_evidence_extension
from memetrader.store import Store
from memetrader.trajectory144 import ARMS, policies as trajectory_policies
from memetrader.unpaired_trend249 import policy as unpaired_policy


def trajectory_by_arm():
    return {p["arm_id"]: p for p in trajectory_policies(cohort_experiment_policies()[2])}


def test_regime251_uses_same_chain_unique_strictly_prior_results():
    now = utcnow()
    rows = [{"token_id": f"bsc:{i}", "closed_at": iso(now - timedelta(minutes=i + 1)),
             "realized_pnl_usd": 2.0, "status": "closed"} for i in range(10)]
    rows.insert(0, {"token_id": "solana:other", "closed_at": iso(now - timedelta(seconds=1)),
                    "realized_pnl_usd": -999.0, "status": "written_off"})
    ok, reason, evidence = trend_regime251.assess(rows, decision_at=now, chain="bsc")
    assert ok and reason == "regime251_favorable"
    assert evidence["terminal_tokens"] == 10 and evidence["net_pnl_usd"] == 20
    bad = deepcopy(rows)
    bad[1]["status"] = "written_off"; bad[1]["realized_pnl_usd"] = -20
    bad[2]["status"] = "written_off"; bad[2]["realized_pnl_usd"] = -20
    assert not trend_regime251.assess(bad, decision_at=now, chain="bsc")[0]


def test_regime251_policy_preserves_revision249_contract():
    parent = unpaired_policy(trajectory_by_arm()["trajectory169_trend_runner_control_v1"])
    candidate = trend_regime251.policy(parent)
    for key in ("hard_stop_return", "take_profit", "max_hold_minutes",
                "trailing_activate_return", "trailing_drawdown", "notional_usd"):
        assert candidate[key] == parent[key]
    source = {"decision_key": "x", "selected": {"token_id": "bsc:a"},
              "decision_evidence": {}}
    assert trend_regime251.alias(source)[trend_regime251.ARM]["decision_key"].endswith(
        "|" + trend_regime251.ARM)


def test_diversified_router_requires_two_distinct_families():
    signal = {"decision_key": "s", "observed_at": "2026-09-19T00:00:00Z",
              "recorded_at": "2026-09-19T00:00:01Z", "decision_evidence": {},
              "selected": {"token_id": "solana:a", "pair_address": "pool"}}
    assert diversified_router252.alias({"trajectory144_trend_runner_v1": signal}) == {}
    result = diversified_router252.alias({
        "trajectory144_trend_runner_v1": signal,
        "trajectory144_absorption_reclaim_v1": {**signal, "decision_key": "a"},
    })[diversified_router252.ARM]
    assert result["selected"] == signal["selected"]
    assert result["decision_evidence"]["contributing_families"] == ["trend", "absorption"]


def test_bsc_survival_needs_later_retained_price_liquidity_and_activity():
    start = utcnow()
    seed_feature = {"chain": "bsc", "current": {"price_usd": 1.0,
                    "liquidity_usd": 2000, "buys_5m": 6, "sells_5m": 4}}
    parent = {"decision_key": "p", "observed_at": iso(start), "recorded_at": iso(start),
              "decision_evidence": {"feature_vector": seed_feature},
              "selected": {"token_id": "bsc:0x" + "1" * 40,
                           "pair_address": "0x" + "2" * 40}}
    current = {"chain": "bsc", "observed_at": iso(start + timedelta(seconds=40)),
               "recorded_at": iso(start + timedelta(seconds=41)), "buy_count_share": .6,
               "current": {"price_usd": 1.01, "liquidity_usd": 2100,
                           "buys_5m": 7, "sells_5m": 4}}
    state = {"signals": {}}
    result = bsc_survival253.update(parent, current, state,
                                    now=start + timedelta(seconds=41))[bsc_survival253.ARM]
    assert result["observed_at"] == current["observed_at"]
    assert result["decision_evidence"]["confirmation_delay_seconds"] == 40
    weaker = deepcopy(current); weaker["current"]["liquidity_usd"] = 1999
    assert bsc_survival253.update(parent, weaker, {"signals": {}},
                                  now=start + timedelta(seconds=41)) == {}


def test_liquidity_breadth_requires_parent_signal_and_fresh_distributed_flow():
    now = utcnow(); activated = now - timedelta(minutes=2)
    parent = revise_evidence_extension({
        "arm_id": liquidity_breadth254.PARENT, "entry_family": "liquidity_leads_price",
        "strategy_revision": 1, "entry_filter": {}, "_execution": {"min_pool_liquidity_usd": 1000},
    })
    candidate = liquidity_breadth254.policy(parent)
    history = []
    for seconds, liquidity, price in ((-60, 2000, 1.0), (-30, 2400, 1.03), (0, 2700, 1.06)):
        at = now + timedelta(seconds=seconds)
        history.append({"token_id": "solana:a", "pair_address": "pool", "price": price,
                        "liquidity": liquidity, "volume": 1000, "buys": 6, "sells": 3,
                        "pool_age_seconds": 600, "observed_at": iso(at),
                        "ingested_at": iso(at), "recorded_at": iso(at)})
    flow = {"observed_at": iso(now), "recorded_at": iso(now), "effective_breadth": 3,
            "top1_notional_share": .4, "net_quote_flow_usd": 100}
    assert liquidity_breadth254.signal(history, candidate, decision_at=iso(now),
        activated_at=iso(activated), context={"amountful_flow": flow}) == (True, "breadth254_confirmed")
    flow["top1_notional_share"] = .8
    assert not liquidity_breadth254.signal(history, candidate, decision_at=iso(now),
        activated_at=iso(activated), context={"amountful_flow": flow})[0]


def test_batch_registration_is_append_only_and_idempotent(tmp_path):
    store = Store(tmp_path / "batch251.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_capital_experiments()
        store.register_chain_meme_opportunity_experiments()
        store.register_chain_meme_cohort_experiments()
        store.register_chain_meme_unpaired_trend249()
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        base = store._chain_meme_trader_registration(version)["definition_json"]
        assert store.register_chain_meme_strategy_batch251() == 4
        assert store.register_chain_meme_strategy_batch251() == 0
        assert store._chain_meme_trader_registration(version)["definition_json"] == base
        rows = store.db.execute(
            "SELECT arm_id,activated_at FROM chain_meme_trader_policy_additions WHERE arm_id IN (?,?,?,?)",
            (trend_regime251.ARM, diversified_router252.ARM,
             bsc_survival253.ARM, liquidity_breadth254.ARM)).fetchall()
        assert len(rows) == 4 and len({row["activated_at"] for row in rows}) == 1
    finally:
        store.close()
