from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from memetrader.flat_selector import FlatSelector
from memetrader.models import TokenCandidate, TokenSnapshot, UTC, iso
from memetrader.store import Store


BASE = datetime(2026, 9, 9, tzinfo=UTC)


def _add_evaluation(store: Store, token: TokenCandidate, source_id: int, pair: str, created: object, version=None):
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_v6_entry_evaluations("
            "definition_version,source_snapshot_id,token_id,evaluated_at,status,entry_family,reason,feature_json) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (version or store.CHAIN_MEME_TRADER_ACTIVE_VERSION, source_id, token.token_id,
             iso(BASE), "rejected", None, "fixture",
             json.dumps({"pair_address": pair, "pair_created_at": created})),
        )


def _add_observation(store: Store, token: TokenCandidate, pair: str, status: str, at: datetime, version=None):
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_flat_breakout_shadow("
            "observer_version,token_id,pair_address,observed_at,ingested_at,status,feature_json,recorded_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (version or store.FLAT_BREAKOUT_SHADOW_VERSION, token.token_id, pair, iso(at), iso(at),
             status, "{}", iso(at)),
        )


def _set_mark(store: Store, token: TokenCandidate, at: datetime):
    snapshot = TokenSnapshot(
        token.chain, token.address, 1.0, 50_000.0, 100_000.0, 0.0, 0, 0,
        observed_at=at, ingested_at=at, provider="fixture", raw={},
    )
    store.upsert_chain_meme_trader_market_mark(token, snapshot, recorded_at=at)
    store._flat_dirty_marks.add(token.token_id)


def _open_position(store: Store, token: TokenCandidate):
    with store.db:
        store.db.execute(
            "INSERT INTO chain_meme_trader_positions("
            "definition_version,arm_id,shadow_cohort_id,token_id,source_buy_trade_id,"
            "baseline_quote_result_id,entry_snapshot_id,entry_signal_price_usd,"
            "entry_execution_price_usd,paper_quantity_tokens,remaining_quantity_tokens,"
            "amount_raw,initial_amount_raw,stake_usd,highest_signal_price_usd,status,"
            "realized_pnl_usd,opened_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (store.CHAIN_MEME_TRADER_ACTIVE_VERSION, "fixture", 1, token.token_id,
             -1, -1, -1, 1.0, 1.0, 20.0, 20.0, "20", "20", 20.0, 1.0,
             "open", 0.0, iso(BASE)),
        )


def _assert_matches(store: Store, selector: FlatSelector, now: datetime):
    assert selector.due_targets(now=now) == store.due_flat_compression_breakout_shadow_targets(now=now)


def test_flat_selector_matches_store_for_incremental_mixed_state_changes(tmp_path: Path):
    store = Store(tmp_path / "flat-selector.sqlite3", initial_cash_usd=1000)
    store._flat_dirty_marks = set()
    ordinary = TokenCandidate("solana", "A" * 32, "ordinary", "fixture")
    near = TokenCandidate("solana", "B" * 32, "near", "fixture")
    young = TokenCandidate("solana", "C" * 32, "young", "fixture")
    switch = TokenCandidate("solana", "D" * 32, "switch", "fixture")
    invalid = TokenCandidate("solana", "E" * 32, "invalid", "fixture")
    for token in (ordinary, near, young, switch, invalid):
        store.upsert_token(token, seen_at=BASE)
    store.register_flat_compression_breakout_shadow()
    _add_evaluation(store, ordinary, 1, "ordinary-pair", iso(BASE - timedelta(hours=7)))
    _add_evaluation(store, near, 2, "near-pair", iso(BASE - timedelta(hours=7)))
    _add_evaluation(store, young, 3, "young-pair", iso(BASE - timedelta(hours=6) + timedelta(seconds=1)))
    _add_evaluation(store, switch, 4, "old-pair", iso(BASE - timedelta(hours=7)))
    _add_evaluation(store, invalid, 5, "valid-old", iso(BASE - timedelta(hours=7)))
    _add_evaluation(store, invalid, 6, "invalid-new", "not-a-timestamp")
    _add_observation(store, near, "near-pair", "near_trigger", BASE)
    _add_observation(store, switch, "old-pair", "flat_watch", BASE)
    _set_mark(store, near, BASE - timedelta(seconds=4))

    selector = FlatSelector(store)
    _assert_matches(store, selector, BASE)
    _assert_matches(store, selector, BASE + timedelta(seconds=1))

    fresh = TokenCandidate("solana", "F" * 32, "fresh", "fixture")
    store.upsert_token(fresh, seen_at=BASE)
    _add_evaluation(store, fresh, 7, "fresh-pair", iso(BASE - timedelta(hours=7)))
    _assert_matches(store, selector, BASE + timedelta(seconds=2))

    _set_mark(store, ordinary, BASE + timedelta(seconds=2))
    store.record_chain_meme_trader_market_mark_failure(
        token_id=ordinary.token_id, failure_kind="fixture", recorded_at=BASE + timedelta(seconds=2),
    )
    store._flat_dirty_marks.add(ordinary.token_id)
    _assert_matches(store, selector, BASE + timedelta(seconds=3))
    _assert_matches(store, selector, BASE + timedelta(seconds=63))

    _add_observation(store, switch, "new-pair", "near_trigger", BASE + timedelta(seconds=63))
    _add_evaluation(store, switch, 8, "new-pair", iso(BASE - timedelta(hours=7)))
    _assert_matches(store, selector, BASE + timedelta(seconds=63))

    _open_position(store, fresh)
    _assert_matches(store, selector, BASE + timedelta(seconds=63))
    with store.db:
        store.db.execute(
            "UPDATE chain_meme_trader_positions SET status='closed' WHERE token_id=?",
            (fresh.token_id,),
        )
    _assert_matches(store, selector, BASE + timedelta(seconds=63))
    store.close()


def test_global_highwater_skips_interleaved_versions_without_losing_later_rows(tmp_path):
    store = Store(tmp_path / 'interleaved.sqlite3', initial_cash_usd=1000)
    store._flat_dirty_marks = set()
    token = TokenCandidate('solana', 'Z' * 32, 'fixture', 'fixture')
    store.upsert_token(token, seen_at=BASE)
    store.register_flat_compression_breakout_shadow()
    selector = FlatSelector(store)
    for i in range(8):
        at = BASE + timedelta(seconds=i * 15)
        # The highest id can belong to an unrelated version, including batches
        # with no matching rows. Later matching rows must remain discoverable.
        if i % 3 != 0:
            _add_evaluation(store, token, i*2+1, 'current', iso(BASE-timedelta(hours=7)))
            _add_observation(store, token, 'current', 'near_trigger' if i%2 else 'flat_watch', at)
        _add_evaluation(store, token, i*2+2, 'wrong', iso(BASE-timedelta(hours=8)), 'other')
        _add_observation(store, token, 'wrong', 'near_trigger', at, 'other')
        _assert_matches(store, selector, at)
        db, evaluations, observations, _, _ = selector._snapshot()
        try:
            assert evaluations == db.execute('SELECT MAX(id) FROM chain_meme_trader_v6_entry_evaluations').fetchone()[0]
            assert observations == db.execute('SELECT MAX(id) FROM chain_meme_trader_flat_breakout_shadow').fetchone()[0]
        finally:
            db.close()
    store.close()
