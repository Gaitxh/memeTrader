from datetime import timedelta
from types import SimpleNamespace

from memetrader import alpha149
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.preentry_safety import PreentrySafety
from memetrader.righttail_recovery152 import (
    ARMS, CONTRACT, CONTROL_ARM, SAFETY_PROXY, SIGNAL_KIND, WIDE_ARM, policy, signal,
)
from memetrader.store import Store
from test_paper_execution import _snapshot
from test_resource_bound_store import setup_store


def test_righttail_signal_merges_existing_available_data_proxies():
    assert signal({"trade_activity_growth151": True})
    assert signal({"buy_pressure_no_breadth151": True})
    assert not signal({})
    assert all(arm in alpha149.SPECS for arm in ARMS)
    assert alpha149.mechanisms({})[SIGNAL_KIND] is False


def test_righttail_pair_keeps_one_entry_and_two_exit_contracts():
    base = next(p for p in alpha149.policies({})
                if p["arm_id"] == "alpha149_trade_activity_growth_proxy_v1")
    short = policy(base, CONTROL_ARM)
    wide = policy(base, WIDE_ARM)
    for field in ("feature_hypothesis", "paper_safety_proxy", "source_arm_ids"):
        assert short[field] == wide[field]
    assert short["feature_contract"] == wide["feature_contract"] == CONTRACT
    assert short["paper_safety_proxy"] == SAFETY_PROXY
    assert short["max_hold_minutes"] == 30
    assert wide["max_hold_minutes"] == 180
    assert short["entry_filter"]["direction"] == CONTROL_ARM
    assert wide["entry_filter"]["direction"] == WIDE_ARM


def test_registration_is_additive_and_idempotent(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    sources = {p["arm_id"]: p for p in alpha149.policies({})}
    parent = "alpha149_trade_activity_growth_proxy_v1"
    store.append_chain_meme_trader_policy(sources[parent], activated_at=clock[0])
    before = store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE definition_version=?",
        (version,),
    ).fetchone()[0]
    assert store.register_chain_meme_righttail_recovery152_experiments() == 2
    assert store.register_chain_meme_righttail_recovery152_experiments() == 0
    rows = store.db.execute(
        "SELECT arm_id,policy_json FROM chain_meme_trader_policy_additions "
        "WHERE definition_version=? AND arm_id IN (?,?) ORDER BY arm_id",
        (version, *ARMS),
    ).fetchall()
    assert len(rows) == 2
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE definition_version=?",
        (version,),
    ).fetchone()[0] == before + 2
    store.close()


def test_dex_proxy_requires_two_causal_frames_and_preserves_hard_veto(tmp_path, monkeypatch):
    clock = [utcnow()]
    for module in ("store", "models", "preentry_safety"):
        monkeypatch.setattr("memetrader." + module + ".utcnow", lambda: clock[0])
    store = Store(tmp_path / "righttail152.sqlite3", initial_cash_usd=1000)
    token = TokenCandidate("bsc", "0x" + "12" * 20, "Proxy", "PROXY", source="fixture")
    pool = "0x" + "34" * 20
    store.upsert_token(token, seen_at=clock[0])
    first = _snapshot(token, pool, clock[0], price=1.0, liquidity=5000)
    store.add_snapshot(first)
    gate = PreentrySafety(store, SimpleNamespace(config={}))
    definition = {
        "policy_notional_usd": 2.0, "max_signal_to_execution_start_seconds": 120,
        "min_pool_liquidity_usd": 1000, "live_execution": False,
    }
    assert not gate.dex_proxy_guard(
        version="v", cohort_id=1, token_id=token.token_id, snapshot_id=1,
        filled_at=iso(clock[0]), definition=definition, reason="test",
        funding_mode="paper", signal_price_usd=1.0,
    )
    clock[0] += timedelta(seconds=30)
    second = _snapshot(token, pool, clock[0], price=1.1, liquidity=5200)
    sid = store.add_snapshot(second)
    assert gate.dex_proxy_guard(
        version="v", cohort_id=1, token_id=token.token_id, snapshot_id=sid,
        filled_at=iso(clock[0]), definition=definition, reason="test",
        funding_mode="paper", signal_price_usd=1.0,
    )
    evidence = store.db.execute(
        "SELECT payload_json FROM chain_meme_pattern_evidence "
        "WHERE kind='preentry_obvious_scam_v1' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    assert "BUY_AUTHORIZED_DEX_PROXY_PAPER" in evidence

    clock[0] += timedelta(seconds=30)
    dangerous = _snapshot(token, pool, clock[0], price=1.2, liquidity=5400)
    dangerous.raw["goplus_evm"] = {"is_honeypot": "1"}
    danger_id = store.add_snapshot(dangerous)
    assert not gate.dex_proxy_guard(
        version="v", cohort_id=2, token_id=token.token_id, snapshot_id=danger_id,
        filled_at=iso(clock[0]), definition=definition, reason="test",
        funding_mode="paper", signal_price_usd=1.1,
    )
    store.close()


def test_market_projection_fallback_isolated_to_opt_in_152_arm(tmp_path, monkeypatch):
    clock = [utcnow()]
    for module in ("store", "models", "preentry_safety"):
        monkeypatch.setattr("memetrader." + module + ".utcnow", lambda: clock[0])
    store = Store(tmp_path / "projection152.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    parent = next(p for p in alpha149.policies({})
                  if p["arm_id"] == "alpha149_trade_activity_growth_proxy_v1")
    candidate = policy(parent, CONTROL_ARM)
    candidate.pop("requires_distinct_trajectory_frame", None)
    candidate.pop("conditional_trajectory_frame", None)
    candidate.pop("trajectory_engine", None)
    store.append_chain_meme_trader_policy(candidate, activated_at=clock[0])
    registration = store._chain_meme_trader_registration(version)
    definition = store._chain_meme_trader_effective_definition(
        version, registration["definition_json"],
    )
    regular_arm = next(
        p["arm_id"] for p in definition["policies"]
        if not p.get("entry_paused") and not p.get("paper_safety_proxy")
    )
    token = TokenCandidate("bsc", "0x" + "56" * 20, "Projection", "PRJ", source="fixture")
    pool = "0x" + "78" * 20
    store.upsert_token(token, seen_at=clock[0])
    store.add_snapshot(_snapshot(token, pool, clock[0], price=1.0, liquidity=5000))
    clock[0] += timedelta(seconds=30)
    sid = store.add_snapshot(_snapshot(token, pool, clock[0], price=1.1, liquidity=5200))
    with store.db:
        cursor = store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
            (version, token.token_id, "broad_launch", sid, pool, iso(clock[0])),
        )
        cohort = int(cursor.lastrowid)
        for arm in (CONTROL_ARM, regular_arm):
            store.db.execute(
                "INSERT INTO chain_meme_trader_entry_decisions("
                "definition_version,arm_id,shadow_cohort_id,token_id,baseline_quote_result_id,"
                "decided_at,status,reason) VALUES(?,?,?,?,?,?,'admitted','test')",
                (version, arm, cohort, token.token_id, sid, iso(clock[0])),
            )
    gate = PreentrySafety(store, SimpleNamespace(config={}))
    store._preentry_safety = gate
    projected = store._project_chain_meme_trader_market_entry(
        version=version, cohort_id=cohort, token_id=token.token_id,
        snapshot_id=sid, market_price=1.1, filled_at=iso(clock[0]),
        reason="test", definition=definition, funding_mode="paper",
        signal_price_usd=1.0,
    )
    assert projected == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?",
        (CONTROL_ARM,),
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?",
        (regular_arm,),
    ).fetchone()[0] == 0
    store.close()
