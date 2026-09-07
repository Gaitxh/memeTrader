import json
from datetime import timedelta

import pytest

from memetrader.inventory_research import (inventory_fields, inventory_policies, research_signal,
    post_signal_compatible, evaluate_inventory_exit)
from memetrader.models import TokenCandidate, utcnow
from test_resource_bound_store import quote, setup_store


TOKEN = TokenCandidate("bsc", "0x" + "ab" * 20, "Fixture")
PAIR = "0x" + "cd" * 20


def inventory_quote(created, at, *, price=1., base=100., reserve_quote=100., provider="dexscreener"):
    q = quote(TOKEN, PAIR, created, at, price=price)
    q.provider = provider
    q.raw["pair"].update(dexId="pancakeswap", labels=["v2"], priceNative=str(price),
        quoteToken={"address": "0x" + "ef" * 20}, liquidity={"usd": 10000, "base": base, "quote": reserve_quote})
    return q


def frames(prices=(1., 1., 1.08)):
    start = utcnow()
    result = []
    for i, price in enumerate(prices):
        at = start + timedelta(seconds=16 * (i + 1))
        q = inventory_quote(0, at, price=price, base=100 if i == 0 else 110,
                            reserve_quote=100 if i == 0 else 110 * price)
        result.append({"id": i + 1, "token_id": TOKEN.token_id, "pair_address": PAIR,
            "price": price, "liquidity": 10000, "buys": 10, "sells": 4, "volume": 100,
            "pool_age_seconds": 1800, "upstream_provider": "dexscreener",
            "inventory": inventory_fields(q.raw["pair"]),
            **{k: at.isoformat() for k in ("observed_at", "ingested_at", "recorded_at")}})
    return start.isoformat(), result


def signal(history, start, policy_index=0):
    return research_signal(history, inventory_policies()[policy_index],
                           decision_at=history[-1]["recorded_at"], activated_at=start)


@pytest.mark.parametrize("mutation", ["future", "source", "quote", "missing", "usd_only", "old_epoch"])
def test_inventory_rejects_false_paths(mutation):
    start, history = frames()
    assert signal(history, start)[0]
    if mutation == "future":
        history[1]["ingested_at"] = history[-1]["recorded_at"]
    elif mutation == "source":
        history[1]["upstream_provider"] = "geckoterminal"
    elif mutation == "quote":
        history[1]["inventory"]["quote_address"] = "other"
    elif mutation == "missing":
        history[1]["inventory"] = {}
    elif mutation == "usd_only":
        history[1]["inventory"]["base"] = 100
    else:
        start = history[1]["observed_at"]
    assert not signal(history, start)[0]


@pytest.mark.parametrize("labels", [["v3"], ["v4"], [], ["v2", "v3"]])
def test_unknown_and_concentrated_liquidity_never_inferred_as_v2(labels):
    pair = inventory_quote(0, utcnow()).raw["pair"]
    pair["labels"] = labels
    assert inventory_fields(pair) == {}


def test_cost_space_uses_past_anchor_costs_and_rejects_fee_erasure():
    start, history = frames((1., .75, .80, .83))
    passed, _, evidence = signal(history, start, 2)
    assert passed and evidence["anchor_frame_id"] == 1
    assert evidence["net_anchor_space"] == pytest.approx(1 / .83 / 1.04 * .96 - 1)
    assert evidence["anchor_is_prediction"] is False
    policy = inventory_policies()[2]
    policy["_execution"] = {"additional_fee_usd_each_fill": .2}
    assert not research_signal(history, policy, decision_at=history[-1]["recorded_at"], activated_at=start)[0]
    history[-1]["price"] = .90
    assert signal(history, start, 2)[1] == "cost_space_insufficient"


@pytest.mark.parametrize("interruption", [None, "missing", "failure"])
def test_inventory_additive_next_observation_matched_entry_and_exit(tmp_path, monkeypatch, interruption):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    assert store.register_chain_meme_inventory_research() == 3
    assert store.register_chain_meme_inventory_research() == 0
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions").fetchone()[0] == 0
    created = int((clock[0] - timedelta(minutes=20)).timestamp() * 1000)
    def positions():
        return store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'inventory_%' ORDER BY arm_id").fetchall()
    for i, (price, base, rq) in enumerate(((1, 100, 100), (1, 110, 110), (1.08, 110, 118.8), (1.10, 110, 121))):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(TOKEN, inventory_quote(created, clock[0], price=price, base=base, reserve_quote=rq), recorded_at=clock[0])
        assert len(positions()) == (2 if i == 3 else 0)
    entered = positions()
    assert len({p["source_entry_fill_id"] for p in entered}) == 1
    assert all(p["paper_quantity_tokens"] == pytest.approx(5 / 1.10 / 1.04) for p in entered)
    # Establish inventory on a new held-pool frame, then confirm a two-sided
    # contraction twice; only the subsequent independent observation may fill.
    reserves = (110., 80., 80., 110., 80., 80., 80.) if interruption else (110., 80., 80., 80.)
    for i, reserve in enumerate(reserves):
        if i == 2 and interruption:
            clock[0] += timedelta(seconds=1)
            if interruption == "missing":
                store.record_chain_meme_trader_pool_mark_miss(token_id=TOKEN.token_id, pair_address=PAIR,
                    chain=TOKEN.chain, address=TOKEN.address, recorded_at=clock[0])
            else:
                store.record_chain_meme_trader_pool_mark_failure(token_id=TOKEN.token_id, pair_address=PAIR,
                    chain=TOKEN.chain, failure_kind="HTTP_ERROR", recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[TOKEN.token_id])
        clock[0] += timedelta(seconds=10)
        q = inventory_quote(created, clock[0], price=1.10, base=reserve, reserve_quote=reserve * 1.10)
        store.upsert_chain_meme_trader_market_mark(TOKEN, q, recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[TOKEN.token_id])
        baseline, candidate = positions()
        assert baseline["status"] == "open"
        assert candidate["status"] == ("closed" if i == len(reserves)-1 else "open")
        if i == len(reserves)-2:
            assert candidate["pending_mark_id"] is not None
        elif i < len(reserves)-2:
            assert candidate["pending_mark_id"] is None
    # Independent flat-price ledger check: two adverse 4% fills still lose money.
    assert candidate["realized_pnl_usd"] == pytest.approx(5 / 1.04 * .96 - 5)
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    store.close()


def test_pool_inventory_cannot_refresh_from_cached_or_foreign_source(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    q = inventory_quote(0, clock[0])
    store.upsert_chain_meme_trader_pool_mark(TOKEN, q, recorded_at=clock[0])
    mark = lambda: store.db.execute("SELECT * FROM chain_meme_trader_pool_marks WHERE token_id=?", (TOKEN.token_id,)).fetchone()
    original = dict(mark())
    assert json.loads(original["inventory_json"])["base"] == 100
    q.raw["pair"]["liquidity"]["base"] = 1
    store.upsert_chain_meme_trader_pool_mark(TOKEN, q, recorded_at=clock[0] + timedelta(seconds=1))
    assert dict(mark()) == original
    clock[0] += timedelta(seconds=10)
    q = inventory_quote(0, clock[0], provider="geckoterminal")
    q.raw["pair"].pop("liquidity")
    store.upsert_chain_meme_trader_pool_mark(TOKEN, q, recorded_at=clock[0])
    assert json.loads(mark()["inventory_json"]).get("base") is None
    assert mark()["sample_sequence"] == 2
    store.close()


def test_inventory_quote_identity_is_bound_at_fill_and_first_exit_frame():
    start, history = frames()
    p = inventory_policies()[1]
    evidence = signal(history, start)[2]
    latest = history[-1]
    assert post_signal_compatible(latest, evidence, p)
    latest["inventory"] = {**latest["inventory"], "quote_address": "other"}
    assert not post_signal_compatible(latest, evidence, p)
    frame = {"frame_id": "held1", "token_id": TOKEN.token_id, "pair_address": PAIR,
        "original_pool": True, "observed_at": latest["observed_at"], "recorded_at": latest["recorded_at"],
        "provider": "dexscreener", "price_usd": latest["price"],
        "inventory": latest["inventory"], "entry_inventory": history[0]["inventory"]}
    result = evaluate_inventory_exit({"opened_at": start, "token_id": TOKEN.token_id, "pair_address": PAIR},
        frame, {}, now=latest["recorded_at"], policy=p["capital_exit_policy"])
    assert result[0] == "WAIT" and "accepted" not in result[2]
