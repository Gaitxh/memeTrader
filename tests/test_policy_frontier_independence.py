from __future__ import annotations

from datetime import timedelta

from memetrader.collectors import SOLANA_WRAPPED_SOL_MINT
from memetrader.models import TokenCandidate, TokenSnapshot, iso, parse_time, utcnow
from memetrader.store import Store


def test_appended_broad_arm_gets_first_post_frontier_episode_only(tmp_path, monkeypatch):
    monkeypatch.setattr(
        Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", Store.CHAIN_MEME_TRADER_V22_VERSION,
    )
    store = Store(tmp_path / "policy-frontier.sqlite3", initial_cash_usd=1000)
    activation = store.activate_chain_meme_trader_v22()
    version = Store.CHAIN_MEME_TRADER_V22_VERSION
    address = "F" * 32
    pair_address = "pool-policy-frontier"
    token = TokenCandidate(
        chain="solana", address=address, name="Frontier", symbol="FRT",
        source="dexscreener",
    )
    store.upsert_token(token, seen_at=parse_time(activation["activated_at"]))
    pair_created_at = utcnow() - timedelta(seconds=60)

    def add_snapshot() -> int:
        observed = utcnow()
        pair = {
            "chainId": "solana",
            "dexId": "pumpfun",
            "pairAddress": pair_address,
            "pairCreatedAt": round(pair_created_at.timestamp() * 1000),
            "priceUsd": "1.0",
            "baseToken": {"address": address, "name": token.name, "symbol": token.symbol},
            "quoteToken": {"address": SOLANA_WRAPPED_SOL_MINT},
            "txns": {
                "m5": {"buys": 30, "sells": 20},
                "h1": {"buys": 30, "sells": 20},
            },
            "volume": {"m5": 900.0, "h1": 900.0},
        }
        return store.add_snapshot(TokenSnapshot(
            "solana", address, 1.0, 10_000, 100_000, 900.0, 30, 20,
            observed_at=observed, ingested_at=observed,
            provider="dexscreener", raw={"pair": pair},
        ))

    old_snapshot_id = add_snapshot()
    assert store.enroll_chain_meme_trader_v6(definition_version=version)["admitted"] == 1
    old_cohort = store.db.execute(
        "SELECT id FROM chain_meme_trader_v6_cohorts WHERE definition_version=? "
        "AND source_snapshot_id=?",
        (version, old_snapshot_id),
    ).fetchone()
    assert old_cohort is not None
    old_position_count = store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=?",
        (version,),
    ).fetchone()[0]

    arm_id = "test_appended_broad_frontier_v1"
    addition = store.append_chain_meme_trader_policy({
        "arm_id": arm_id,
        "canonical_id": arm_id,
        "name": "Appended broad frontier fixture",
        "entry_family": "broad_launch",
        "entry_filter": {"max_age_seconds": 900},
        "forward_enabled": True,
    })
    assert int(addition["activation_snapshot_id"]) == old_snapshot_id
    assert store.db.execute(
        "SELECT 1 FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=?",
        (version, arm_id, int(old_cohort["id"])),
    ).fetchone() is None

    post_frontier_snapshot_id = add_snapshot()
    assert post_frontier_snapshot_id > old_snapshot_id
    store.enroll_chain_meme_trader_v6(definition_version=version)
    decision = store.db.execute(
        "SELECT d.status,d.shadow_cohort_id FROM chain_meme_trader_entry_decisions d "
        "JOIN chain_meme_trader_v6_cohorts c ON c.definition_version=d.definition_version "
        "AND c.id=d.shadow_cohort_id WHERE d.definition_version=? AND d.arm_id=? "
        "AND c.source_snapshot_id=?",
        (version, arm_id, post_frontier_snapshot_id),
    ).fetchone()
    assert decision is not None and decision["status"] == "admitted"
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=?",
        (version,),
    ).fetchone()[0] == old_position_count + 1

    third_snapshot_id = add_snapshot()
    store.enroll_chain_meme_trader_v6(definition_version=version)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id=?",
        (version, arm_id),
    ).fetchone()[0] == 1
    assert store.db.execute(
        "SELECT reason FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE definition_version=? AND source_snapshot_id=?",
        (version, third_snapshot_id),
    ).fetchone()["reason"] == "family_episode_already_enrolled_or_cooldown_active"
    store.close()


def test_main_entry_frontier_does_not_follow_async_observer_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", Store.CHAIN_MEME_TRADER_V22_VERSION,
    )
    store = Store(tmp_path / "entry-source-frontier.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_v22()
    version = Store.CHAIN_MEME_TRADER_V22_VERSION
    observed = utcnow()
    address = "M" * 32
    token = TokenCandidate("solana", address, "Main lane", "MAIN", source="dexscreener")
    store.upsert_token(token, seen_at=observed)
    pair = {
        "chainId": "solana",
        "dexId": "pumpfun",
        "pairAddress": "pool-main-lane",
        "pairCreatedAt": round((observed - timedelta(seconds=60)).timestamp() * 1000),
        "priceUsd": "1.0",
        "baseToken": {"address": address, "name": token.name, "symbol": token.symbol},
        "quoteToken": {"address": SOLANA_WRAPPED_SOL_MINT},
        "txns": {
            "m5": {"buys": 30, "sells": 20},
            "h1": {"buys": 30, "sells": 20},
        },
        "volume": {"m5": 900.0, "h1": 900.0},
    }
    stale_observed = observed - timedelta(seconds=120)
    stale_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", address, 1.0, 10_000, 100_000, 900.0, 30, 20,
        observed_at=stale_observed, ingested_at=stale_observed,
        provider="dexscreener", raw={"pair": pair},
    ))
    main_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", address, 1.0, 10_000, 100_000, 900.0, 30, 20,
        observed_at=observed, ingested_at=observed,
        provider="dexscreener", raw={"pair": pair},
    ))
    observer_snapshot_id = store.add_snapshot(TokenSnapshot(
        "solana", address, 1.0, 10_000, 100_000, 900.0, 30, 20,
        observed_at=utcnow(), ingested_at=utcnow(),
        provider="strategy-observer:dexscreener", raw={"pair": pair},
    ))
    assert observer_snapshot_id > main_snapshot_id
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_entry_evaluations("
            "definition_version,source_snapshot_id,token_id,evaluated_at,status,"
            "entry_family,reason,feature_json) VALUES(?,?,?,?,? ,NULL,?, '{}')",
            (
                version, observer_snapshot_id, token.token_id, iso(utcnow()),
                "rejected", "pattern_observation",
            ),
        )

    assert store.enroll_chain_meme_trader_v6(
        definition_version=version,
    )["evaluated"] == 2
    stale_evaluation = store.db.execute(
        "SELECT status,reason FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE definition_version=? AND source_snapshot_id=?",
        (version, stale_snapshot_id),
    ).fetchone()
    assert (stale_evaluation["status"], stale_evaluation["reason"]) == (
        "rejected", "entry_snapshot_too_old",
    )
    assert store.db.execute(
        "SELECT status FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE definition_version=? AND source_snapshot_id=?",
        (version, main_snapshot_id),
    ).fetchone()["status"] == "admitted"
    store.close()
