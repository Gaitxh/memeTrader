import asyncio
import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.runtime import Runtime
from memetrader.store import Store


def _seed_position(store: Store, *, entry_pair: str | None):
    registration = store.register_chain_meme_trader_v20()
    store.activate_chain_meme_trader_v20()
    version = Store.CHAIN_MEME_TRADER_V20_VERSION
    policy = next(
        item for item in json.loads(registration["definition_json"])["policies"]
        if item.get("zero_activity_grace_minutes") is not None
    )
    token = TokenCandidate(
        "solana", str(Pubkey.new_unique()), "Pool identity", "POOL",
        source="dexscreener",
    )
    opened_at = utcnow() - timedelta(
        minutes=float(policy["zero_activity_grace_minutes"]) + 1.0
    )
    store.upsert_token(token, seen_at=opened_at)
    quantity = 20.0 / 1.04
    amount_raw = str(round(quantity * 1_000_000_000))
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_cohorts("
            "definition_version,token_id,entry_family,source_snapshot_id,pair_address,"
            "decided_at,episode_no,feature_json) VALUES(?,?,?,?,?,?,1,'{}')",
            (version, token.token_id, "broad_launch", 1, entry_pair or "", iso(opened_at)),
        )
        cohort_id = int(store.db.execute("SELECT last_insert_rowid()").fetchone()[0])
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,opened_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,20,1,'open',?)",
            (
                version, policy["arm_id"], cohort_id, token.token_id, cohort_id,
                1, 1, 1.0, 1.04, quantity, quantity, amount_raw, amount_raw,
                iso(opened_at),
            ),
        )
        store.db.execute(
            "INSERT INTO chain_meme_trader_trades("
            "definition_version,arm_id,shadow_cohort_id,token_id,side,gross_usd,"
            "net_cash_flow_usd,reason,created_at) "
            "VALUES(?,?,?,?, 'BUY',20,-20,'fixture',?)",
            (version, policy["arm_id"], cohort_id, token.token_id, iso(opened_at)),
        )
    return version, policy, token, cohort_id


def _snapshot(token: TokenCandidate, *, pair: str, price: float, liquidity: float, at):
    return TokenSnapshot(
        token.chain, token.address, price, liquidity, 100_000.0, 0.0, 0, 0,
        observed_at=at, ingested_at=at, provider="dexscreener",
        raw={"pair": {"pairAddress": pair}},
    )


def test_sibling_pool_cannot_exit_write_off_or_create_indicative_profit(tmp_path):
    store = Store(tmp_path / "pool-identity.sqlite3", initial_cash_usd=1000)
    version, policy, token, cohort_id = _seed_position(store, entry_pair="pair-A")
    first = utcnow() - timedelta(seconds=2)

    for at, liquidity in ((first, 10_000.0), (first + timedelta(seconds=1), 0.5)):
        store.upsert_chain_meme_trader_market_mark(
            token, _snapshot(token, pair="pair-B", price=20.0, liquidity=liquidity, at=at),
            recorded_at=at,
        )
        assert store.evaluate_chain_meme_trader_market_marks(
            definition_version=version, now=at,
        ) == 0

    position = store.db.execute(
        "SELECT status,pending_mark_id FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, policy["arm_id"], cohort_id),
    ).fetchone()
    assert (position["status"], position["pending_mark_id"]) == ("open", None)
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_trades WHERE definition_version=? "
        "AND arm_id=? AND shadow_cohort_id=? AND side IN ('SELL','WRITEOFF')",
        (version, policy["arm_id"], cohort_id),
    ).fetchone()[0] == 0

    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=first + timedelta(seconds=1),
    )
    account = store.db.execute(
        "SELECT * FROM chain_meme_trader_account_snapshots WHERE definition_version=? "
        "AND arm_id=? ORDER BY id DESC LIMIT 1", (version, policy["arm_id"]),
    ).fetchone()
    assert account["valuation_status"] == "partial_market_mark_unknown"
    assert account["indicative_equity_usd"] is None
    assert account["indicative_unrealized_pnl_usd"] is None

    for at in (first + timedelta(seconds=2), first + timedelta(seconds=3)):
        store.upsert_chain_meme_trader_market_mark(
            token, _snapshot(token, pair="pair-A", price=2.0, liquidity=10.0, at=at),
            recorded_at=at,
        )
        store.evaluate_chain_meme_trader_market_marks(
            definition_version=version, now=at,
        )
    closed = store.db.execute(
        "SELECT status,realized_pnl_usd FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, policy["arm_id"], cohort_id),
    ).fetchone()
    assert closed["status"] == "closed"
    assert closed["realized_pnl_usd"] == pytest.approx(20.0 * 2.0 / 1.04 * 0.96 - 20.0)
    store.close()


def test_unknown_entry_pair_never_borrows_current_token_pool_identity(tmp_path):
    store = Store(tmp_path / "unknown-entry-pool.sqlite3", initial_cash_usd=1000)
    version, policy, token, cohort_id = _seed_position(store, entry_pair=None)
    first = utcnow() - timedelta(seconds=1)
    for at in (first, first + timedelta(seconds=1)):
        store.upsert_chain_meme_trader_market_mark(
            token, _snapshot(token, pair="pair-B", price=50.0, liquidity=50_000.0, at=at),
            recorded_at=at,
        )
        assert store.evaluate_chain_meme_trader_market_marks(
            definition_version=version, now=at,
        ) == 0
    row = store.db.execute(
        "SELECT status,pending_mark_id FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, policy["arm_id"], cohort_id),
    ).fetchone()
    assert (row["status"], row["pending_mark_id"]) == ("open", None)
    store.record_chain_meme_trader_account_snapshots(
        definition_version=version, now=first + timedelta(seconds=1),
    )
    account = store.db.execute(
        "SELECT valuation_status,indicative_equity_usd FROM "
        "chain_meme_trader_account_snapshots WHERE definition_version=? AND arm_id=? "
        "ORDER BY id DESC LIMIT 1", (version, policy["arm_id"]),
    ).fetchone()
    assert account["valuation_status"] == "partial_market_mark_unknown"
    assert account["indicative_equity_usd"] is None
    store.close()


def test_entry_pool_structural_missing_over_sixty_seconds_writes_off(tmp_path):
    store = Store(tmp_path / "entry-pool-missing.sqlite3", initial_cash_usd=1000)
    version, policy, token, cohort_id = _seed_position(store, entry_pair="pair-A")
    first = utcnow() - timedelta(seconds=62)
    store.record_chain_meme_trader_pool_mark_miss(
        token_id=token.token_id, pair_address="pair-A", chain=token.chain,
        address=token.address, recorded_at=first,
    )
    second = first + timedelta(seconds=61)
    store.record_chain_meme_trader_pool_mark_miss(
        token_id=token.token_id, pair_address="pair-A", chain=token.chain,
        address=token.address, recorded_at=second,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=second,
    ) == 1
    row = store.db.execute(
        "SELECT status,close_reason FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, policy["arm_id"], cohort_id),
    ).fetchone()
    assert row["status"] == "written_off"
    assert row["close_reason"] == "dex_pair_missing_over_60_seconds_writeoff"
    store.close()


def test_network_failure_after_structural_misses_does_not_write_off(tmp_path):
    store = Store(tmp_path / "entry-pool-network-failure.sqlite3", initial_cash_usd=1000)
    version, policy, token, cohort_id = _seed_position(store, entry_pair="pair-A")
    first = utcnow() - timedelta(seconds=62)
    for at in (first, first + timedelta(seconds=61)):
        store.record_chain_meme_trader_pool_mark_miss(
            token_id=token.token_id, pair_address="pair-A", chain=token.chain,
            address=token.address, recorded_at=at,
        )
    checked_at = first + timedelta(seconds=62)
    store.record_chain_meme_trader_pool_mark_failure(
        token_id=token.token_id, pair_address="pair-A", chain=token.chain,
        failure_kind="HTTP_TIMEOUT", recorded_at=checked_at,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=checked_at,
    ) == 0
    row = store.db.execute(
        "SELECT status,pending_mark_id FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, policy["arm_id"], cohort_id),
    ).fetchone()
    assert (row["status"], row["pending_mark_id"]) == ("open", None)
    store.close()


def test_fresh_dust_on_entry_pool_still_writes_off(tmp_path):
    store = Store(tmp_path / "entry-pool-dust.sqlite3", initial_cash_usd=1000)
    version, policy, token, cohort_id = _seed_position(store, entry_pair="pair-A")
    at = utcnow()
    store.upsert_chain_meme_trader_market_mark(
        token, _snapshot(token, pair="pair-A", price=1.0, liquidity=0.5, at=at),
        recorded_at=at,
    )
    assert store.evaluate_chain_meme_trader_market_marks(
        definition_version=version, now=at,
    ) == 1
    row = store.db.execute(
        "SELECT status,close_reason FROM chain_meme_trader_positions WHERE "
        "definition_version=? AND arm_id=? AND shadow_cohort_id=?",
        (version, policy["arm_id"], cohort_id),
    ).fetchone()
    assert row["status"] == "written_off"
    assert row["close_reason"] == "dex_pool_liquidity_below_1_usd_writeoff"
    store.close()


def test_batch_response_keeps_entry_pool_when_sibling_pool_has_more_liquidity(tmp_path):
    async def scenario():
        store = Store(tmp_path / "all-pools.sqlite3", initial_cash_usd=1000)
        version, policy, token, cohort_id = _seed_position(store, entry_pair="pair-A")
        runtime = Runtime.__new__(Runtime)
        runtime.store = store
        runtime._paper_quote_rejections = lambda *args: []

        def raw_pair(pair_address, price, liquidity):
            return {
                "chainId": "solana", "pairAddress": pair_address,
                "baseToken": {
                    "address": token.address, "name": token.name, "symbol": token.symbol,
                },
                "priceUsd": str(price), "liquidity": {"usd": liquidity},
                "marketCap": 100_000.0, "volume": {"m5": 0.0},
                "txns": {"m5": {"buys": 0, "sells": 0}},
            }

        async def batch_quote(chain, addresses, *, fresh=False, high_priority=False):
            at = utcnow()
            pool_a = raw_pair("pair-A", 2.0, 10.0)
            pool_b = raw_pair("pair-B", 20.0, 50_000.0)
            selected = _snapshot(
                token, pair="pair-B", price=20.0, liquidity=50_000.0, at=at,
            )
            selected.raw["pairs"] = [pool_a, pool_b]
            return {token.token_id: (token, selected)}

        runtime._dex_batch_quote = batch_quote
        targets = store.chain_meme_trader_market_mark_targets(
            definition_versions=[version],
        )
        assert targets[0]["entry_pair_addresses"] == "pair-A"
        for _ in range(2):
            await runtime._refresh_chain_meme_market_marks(
                targets, heartbeat_name="pool-identity", high_priority=True,
                evaluate_version=version,
            )

        generic = store.db.execute(
            "SELECT pair_address FROM chain_meme_trader_market_marks WHERE token_id=?",
            (token.token_id,),
        ).fetchone()
        entry_pool = store.db.execute(
            "SELECT pair_address,sample_sequence FROM chain_meme_trader_pool_marks "
            "WHERE token_id=? AND pair_address='pair-A'", (token.token_id,),
        ).fetchone()
        assert generic["pair_address"] == "pair-B"
        assert (entry_pool["pair_address"], entry_pool["sample_sequence"]) == ("pair-A", 2)
        status = store.db.execute(
            "SELECT status FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND arm_id=? AND shadow_cohort_id=?",
            (version, policy["arm_id"], cohort_id),
        ).fetchone()[0]
        assert status == "closed"
        store.close()

    asyncio.run(scenario())
