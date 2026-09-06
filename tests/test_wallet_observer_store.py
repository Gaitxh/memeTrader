from __future__ import annotations

import json
from datetime import timedelta

import pytest
from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.store import Store


S05_CANDIDATE = "watched_wallet_distribution_candidate_v1"
S05_CONTROL = "watched_wallet_distribution_control_v1"
S06_CANDIDATE = "watched_wallet_confirmed_entry_candidate_v1"
S06_CONTROL = "watched_wallet_confirmed_entry_control_v1"


def _token(name):
    return TokenCandidate("solana", str(Pubkey.new_unique()), name, name[:4], source="fixture")


def _snapshot(token, pair, created_at, at, *, price=1.0, liquidity=2_000.0):
    return TokenSnapshot(
        token.chain, token.address, price, liquidity, 100_000.0, 300.0, 3, 1,
        observed_at=at, ingested_at=at, provider="dexscreener",
        raw={"pair": {"chainId": token.chain, "dexId": "pumpswap",
            "pairAddress": pair, "pairCreatedAt": round(created_at.timestamp() * 1000),
            "baseToken": {"address": token.address}, "priceUsd": str(price),
            "liquidity": {"usd": liquidity}}},
    )


def _trade(token, pair, signer, side, block_at, received_at, suffix):
    return {"pool_address": pair, "base_mint": token.address, "quote_mint": "USDC",
        "signature": f"{side}-{suffix}", "instruction_path": "0.1", "side": side,
        "signer_address": signer, "block_time": iso(block_at),
        "observed_at": iso(received_at), "recorded_at": iso(received_at),
        "amount_complete": True}


def _record_scan(store, clock, token, pair, at, trades, key):
    clock[0] = at
    return store.record_chain_meme_pattern_evidence(
        token.token_id, pair, "participation_scan",
        {"complete": True, "observed_at": iso(at), "recorded_at": iso(at),
            "trades": list(trades)},
        observed_at=at, source_key=key,
    )


def _store(tmp_path, monkeypatch, name, *, seed=True):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / name, initial_cash_usd=1_000)
    store.activate_chain_meme_trader_funded_period()
    if seed:
        source, source_pair = _token("Seed"), str(Pubkey.new_unique())
        seed_at = clock[0]
        _record_scan(store, clock, source, source_pair, seed_at, [
            _trade(source, source_pair, "watched", "BUY",
                seed_at - timedelta(seconds=1), seed_at, "seed")], "seed")
        clock[0] += timedelta(seconds=1)
    assert store.register_chain_meme_wallet_observers() == 4
    assert store.register_chain_meme_wallet_observers() == 0
    return store, clock


def test_watchlist_can_seal_after_registration_when_first_seed_arrives(tmp_path, monkeypatch):
    store, clock = _store(tmp_path, monkeypatch, "late-seed.sqlite3", seed=False)
    assert store.chain_meme_wallet_watchlist(now=clock[0])["status"] == "UNSEALED"
    token, pair = _token("Late"), str(Pubkey.new_unique())
    at = clock[0] + timedelta(seconds=5)
    _record_scan(store, clock, token, pair, at, [
        _trade(token, pair, "late-wallet", "BUY", at - timedelta(seconds=1), at, "late")
    ], "late-seed")
    sealed = store.chain_meme_wallet_watchlist(now=at)
    assert sealed["status"] == "SEALED"
    assert sealed["addresses"] == ["late-wallet"]
    hits = store.chain_meme_wallet_participation_hits(token.token_id, pair,
        not_before=at - timedelta(seconds=5), now=at)
    assert not hits["hits"]
    store.close()


def test_s06_changed_pool_freezes_new_identity_and_unsupported_chain_never_buys(tmp_path, monkeypatch):
    store, clock = _store(tmp_path, monkeypatch, "wallet-pair.sqlite3")
    origin = clock[0]
    token = _token("Pair")
    pair_a, pair_b = str(Pubkey.new_unique()), str(Pubkey.new_unique())
    for seconds, pair in [(1, pair_a), (17, pair_b)]:
        clock[0] = origin + timedelta(seconds=seconds)
        assert store.observe_chain_meme_pattern(token,
            _snapshot(token, pair, origin - timedelta(seconds=60), clock[0]), recorded_at=clock[0]) == 0
    row = store.db.execute("SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE token_id=? ORDER BY id DESC LIMIT 1", (token.token_id,)).fetchone()
    states = json.loads(row[0])["wallet_entry_states"]
    assert all(state["opportunity"]["pair_address"] == pair_b for state in states.values())
    bsc = TokenCandidate("bsc", "0x" + "11" * 20, "BSC", "BSC", source="fixture")
    for seconds in (33, 49):
        clock[0] = origin + timedelta(seconds=seconds)
        store.observe_chain_meme_pattern(bsc,
            _snapshot(bsc, "0x" + "22" * 20, origin, clock[0]), recorded_at=clock[0])
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE token_id=?",
        (bsc.token_id,)).fetchone()[0] == 0
    store.close()


def test_s06_same_opportunity_control_then_watched_candidate_each_buy_five(tmp_path, monkeypatch):
    store, clock = _store(tmp_path, monkeypatch, "wallet-entry.sqlite3")
    origin = clock[0]
    token, pair = _token("Entry"), str(Pubkey.new_unique())
    created_at = origin - timedelta(seconds=60)

    def observe(seconds, price):
        clock[0] = origin + timedelta(seconds=seconds)
        return store.observe_chain_meme_pattern(token,
            _snapshot(token, pair, created_at, clock[0], price=price), recorded_at=clock[0])

    assert observe(1, 1.0) == 0
    hit_at = origin + timedelta(seconds=10)
    _record_scan(store, clock, token, pair, hit_at, [
        _trade(token, pair, "watched", "BUY", hit_at - timedelta(seconds=1), hit_at, "entry")
    ], "entry-hit")
    assert observe(17, 1.01) == 1
    assert observe(33, 1.02) == 1
    assert observe(49, 1.03) == 0

    rows = store.db.execute(
        "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
        "AND arm_id IN (?,?) ORDER BY opened_at",
        (Store.CHAIN_MEME_TRADER_ACTIVE_VERSION, S06_CANDIDATE, S06_CONTROL),
    ).fetchall()
    assert len(rows) == 2
    assert {row["stake_usd"] for row in rows} == {5.0}
    assert rows[0]["arm_id"] == S06_CONTROL
    assert rows[1]["arm_id"] == S06_CANDIDATE
    keys = []
    for row in rows:
        features = json.loads(store.db.execute(
            "SELECT feature_json FROM chain_meme_trader_v6_cohorts WHERE id=?",
            (row["shadow_cohort_id"],),
        ).fetchone()[0])
        keys.append(features["event_keys"][row["arm_id"]])
    assert len(set(keys)) == 1
    store.close()


def test_s05_raw_participation_drives_candidate_exit_without_amountful_flow(tmp_path, monkeypatch):
    store, clock = _store(tmp_path, monkeypatch, "wallet-exit.sqlite3")
    origin = clock[0]
    token, pair = _token("Exit"), str(Pubkey.new_unique())
    created_at = origin - timedelta(seconds=60)
    episode = f"passive-broad:{token.token_id}:{pair}"

    def observe(seconds):
        at = origin + timedelta(seconds=seconds)
        clock[0] = at
        signals = {arm: {"episode_id": episode, "decision_key": f"{episode}|{arm}",
            "selected": {"token_id": token.token_id, "pair_address": pair},
            "decision_evidence": {"original_pool": True},
            "scope": "same_passive_broad_initial_opportunity",
            "observed_at": iso(at), "recorded_at": iso(at)}
            for arm in (S05_CANDIDATE, S05_CONTROL)}
        return store.observe_chain_meme_pattern(token,
            _snapshot(token, pair, created_at, at), recorded_at=at,
            cohort_signals=signals)

    assert observe(1) == 0
    assert observe(17) == 2
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id IN (?,?)",
        (S05_CANDIDATE, S05_CONTROL),
    ).fetchone()[0] == 2

    def mark(seconds, price, liquidity):
        at = origin + timedelta(seconds=seconds)
        clock[0] = at
        store.upsert_chain_meme_trader_market_mark(token,
            _snapshot(token, pair, created_at, at, price=price, liquidity=liquidity),
            recorded_at=at)
        store.evaluate_chain_meme_trader_market_marks(
            definition_version=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            now=at, token_ids=[token.token_id])

    buy_at = origin + timedelta(seconds=24)
    _record_scan(store, clock, token, pair, buy_at, [
        _trade(token, pair, "watched", "BUY", buy_at - timedelta(seconds=1), buy_at, "exit-buy")
    ], "exit-buy")
    mark(30, 1.0, 2_000)
    sell_at = origin + timedelta(seconds=38)
    _record_scan(store, clock, token, pair, sell_at, [
        _trade(token, pair, "watched", "SELL", sell_at - timedelta(seconds=1), sell_at, "exit-sell")
    ], "exit-sell")
    mark(44, .95, 1_900)
    mark(50, .90, 1_800)
    pending = store.db.execute(
        "SELECT * FROM chain_meme_trader_marks WHERE arm_id=? AND status='pending'",
        (S05_CANDIDATE,),
    ).fetchone()
    assert pending["reason"] == "watched_wallet_distribution_l0_weak"
    assert store.db.execute(
        "SELECT COUNT(*) FROM chain_meme_pattern_evidence WHERE token_id=? AND kind='amountful_flow'",
        (token.token_id,),
    ).fetchone()[0] == 0
    mark(56, .89, 1_700)
    statuses = {row["arm_id"]: row["status"] for row in store.db.execute(
        "SELECT arm_id,status FROM chain_meme_trader_positions WHERE arm_id IN (?,?)",
        (S05_CANDIDATE, S05_CONTROL),
    )}
    assert statuses == {S05_CANDIDATE: "closed", S05_CONTROL: "open"}
    store.close()
