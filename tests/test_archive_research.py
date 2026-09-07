import json
from datetime import timedelta

import pytest

from memetrader.archive_research import archive_policies, archive_signal, evaluate_plateau_exit
from memetrader.models import TokenCandidate, utcnow
from test_resource_bound_store import quote, setup_store

TOKEN = TokenCandidate("solana", "ArchiveFixture", "Fixture")
PAIR = "ArchivePool"
DRIFT = (1., 1.02, 1.015, 1.04, 1.06, 1.08)
RELEASE = (1., 1.01, 1., 1.02, 1.06, 1.10)


def sample(created, at, price, *, release=False, late=False):
    q = quote(TOKEN, PAIR, created, at, price=price)
    buys, sells, hour = ((70 if late else 50), (30 if late else 50), 250) if release else (6, 4, 120)
    q.buys_5m, q.sells_5m = buys, sells
    q.raw["pair"]["txns"] = {"m5": {"buys": buys, "sells": sells},
        "h1": {"buys": hour, "sells": hour}}
    return q


def history(release=False):
    start = utcnow()
    frames = []
    for i, price in enumerate(RELEASE if release else DRIFT):
        at = start + timedelta(seconds=16 * (i + 1))
        q = sample(0, at, price, release=release, late=i >= 3)
        frames.append({"id": i + 1, "token_id": TOKEN.token_id, "pair_address": PAIR,
            "price": price, "liquidity": 10000, "volume": 100,
            "buys": q.buys_5m, "sells": q.sells_5m,
            "buys_h1": q.raw["pair"]["txns"]["h1"]["buys"],
            "sells_h1": q.raw["pair"]["txns"]["h1"]["sells"],
            "pool_age_seconds": 7200, "upstream_provider": "dexscreener",
            **{k: at.isoformat() for k in ("observed_at", "ingested_at", "recorded_at")}})
    return start.isoformat(), frames


@pytest.mark.parametrize("mutation", ["future", "provider", "pool", "gap", "duplicate", "activation", "h1_invalid", "young"])
def test_archive_entry_rejects_noncausal_or_incompatible_paths(mutation):
    start, frames = history()
    policy = archive_policies()[0]
    check = lambda: archive_signal(frames, policy, activated_at=start, decision_at=frames[-1]["recorded_at"])[0]
    assert check()
    if mutation == "future":
        frames[2]["ingested_at"] = frames[-1]["recorded_at"]
    elif mutation == "provider":
        frames[2]["upstream_provider"] = "geckoterminal"
    elif mutation == "pool":
        frames[2]["pair_address"] = "Other"
    elif mutation == "gap":
        frames[2]["observed_at"] = frames[0]["observed_at"]
    elif mutation == "duplicate":
        frames.insert(3, dict(frames[2]))
    elif mutation == "activation":
        start = frames[1]["observed_at"]
    elif mutation == "h1_invalid":
        frames[2]["buys_h1"] = 1
    else:
        frames[2]["pool_age_seconds"] = 300
    assert not check()


def test_release_requires_ordered_transition_and_is_not_drift():
    start, frames = history(True)
    check = lambda h, p: archive_signal(h, p, activated_at=start, decision_at=h[-1]["recorded_at"])[0]
    assert not check(frames[:3], archive_policies()[2])
    assert check(frames, archive_policies()[2])
    assert not check(frames, archive_policies()[0])
    for f in frames[3:]:
        f["price"] = 1.
    assert not check(frames, archive_policies()[2])


@pytest.mark.parametrize("receipt", ["normal", "provider", "late", "release"])
def test_archive_registration_and_next_quote_matched_entry(tmp_path, monkeypatch, receipt):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    assert store.register_chain_meme_archive_research() == 3
    assert store.register_chain_meme_archive_research() == 0
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    created = int((clock[0] - timedelta(hours=2)).timestamp() * 1000)
    release = receipt == "release"
    for i, price in enumerate(RELEASE if release else DRIFT):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(TOKEN, sample(created, clock[0], price, release=release, late=i >= 3), recorded_at=clock[0])
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id LIKE 'archive_%'").fetchone()[0] == 0
    clock[0] += timedelta(seconds=31 if receipt == "late" else 16)
    q = sample(created, clock[0], 1.12, release=release, late=True)
    if receipt == "provider":
        q.provider = "geckoterminal"
    store.observe_chain_meme_pattern(TOKEN, q, recorded_at=clock[0])
    positions = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'archive_%'").fetchall()
    assert len(positions) == (2 if receipt == "normal" else 1 if release else 0)
    if positions:
        assert len({p["source_entry_fill_id"] for p in positions}) == 1
        assert all(p["paper_quantity_tokens"] == pytest.approx(5 / 1.12 / 1.04) for p in positions)
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    store.close()


@pytest.mark.parametrize("interruption", [None, "missing", "failure"])
def test_plateau_exit_later_fill_cost_ledger_and_gap_reset(tmp_path, monkeypatch, interruption):
    store, clock = setup_store(tmp_path, monkeypatch)
    store.activate_chain_paper_execution({"buy_slippage_pct": 4, "sell_slippage_pct": 4,
        "additional_fee_usd_each_fill": .1, "min_pool_liquidity_usd": 1000}, activated_at=clock[0])
    store.register_chain_meme_archive_research()
    created = int((clock[0] - timedelta(hours=2)).timestamp() * 1000)
    for price in DRIFT + (1.10,):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(TOKEN, sample(created, clock[0], price), recorded_at=clock[0])
    def positions():
        return store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id IN ('archive_drift_v1','archive_plateau_v1') ORDER BY arm_id").fetchall()
    assert len(positions()) == 2
    for i in range(10 if interruption else 7):
        if interruption and i == 3:
            clock[0] += timedelta(seconds=1)
            if interruption == "missing":
                store.record_chain_meme_trader_pool_mark_miss(token_id=TOKEN.token_id, pair_address=PAIR,
                    chain=TOKEN.chain, address=TOKEN.address, recorded_at=clock[0])
            else:
                store.record_chain_meme_trader_pool_mark_failure(token_id=TOKEN.token_id, pair_address=PAIR,
                    chain=TOKEN.chain, failure_kind="HTTP_ERROR", recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[TOKEN.token_id])
        clock[0] += timedelta(seconds=6)
        final = i == (9 if interruption else 6)
        q = sample(created, clock[0], 1.37 if final else 1.40)
        q.buys_5m = q.sells_5m = 20 + i * 3
        q.raw["pair"]["txns"]["m5"] = {"buys": q.buys_5m, "sells": q.sells_5m}
        store.upsert_chain_meme_trader_market_mark(TOKEN, q, recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[TOKEN.token_id])
        baseline, candidate = positions()
        assert baseline["status"] == "open"
        assert candidate["status"] == ("closed" if final else "open")
        if i == (8 if interruption else 5):
            assert candidate["pending_mark_id"] is not None
        elif not final:
            assert candidate["pending_mark_id"] is None
    # Independent receipt-price ledger: two fees, both adverse slips; not trigger price.
    assert candidate["stake_usd"] == pytest.approx(5.1)
    assert candidate["realized_pnl_usd"] == pytest.approx((5 / 1.10 / 1.04) * 1.37 * .96 - .1 - 5.1)
    store.close()


def test_plateau_keeps_high_seen_between_independent_frames():
    start, frames = history()
    p = archive_policies()[1]["capital_exit_policy"]
    state = {}
    position = {"opened_at": start, "token_id": TOKEN.token_id, "pair_address": PAIR, "stake_usd": 5}
    at = utcnow() + timedelta(seconds=30)
    for i, price in enumerate((1.4, 1.6, 1.4)):
        t = at + timedelta(seconds=i)
        frame = {"frame_id": str(i), "token_id": TOKEN.token_id, "pair_address": PAIR,
            "observed_at": t.isoformat(), "recorded_at": t.isoformat(), "price_usd": price,
            "original_pool": True, "provider": "dexscreener", "buys": 10, "sells": 10,
            "economic_value_usd": 6}
        _, _, state, _ = evaluate_plateau_exit(position, frame, state, now=t, policy=p)
    assert state["peak_price"] == 1.6
    assert len(state["window"]) == 1
