from __future__ import annotations

from datetime import datetime, timedelta, timezone

from memetrader.capital_policies import capital_policies
from memetrader.l0_experiments import l0_experiment_policies
from memetrader.wallet_observer_experiments import (
    EXPIRED,
    HOLD,
    READY,
    SELL,
    WAIT,
    evaluate_wallet_confirmed_entry,
    evaluate_wallet_distribution_exit,
    participation_hits,
    seal_watchlist,
    wallet_observer_policies,
)


UTC = timezone.utc
TOKEN_ID = "solana:MINT"
PAIR = "POOL"


def _watchlist(start):
    return seal_watchlist(
        [{
            "address": "watched",
            "observed_at": (start - timedelta(seconds=2)).isoformat(),
            "recorded_at": (start - timedelta(seconds=1)).isoformat(),
        }],
        activated_at=start,
        now=start,
    )


def _trade(side, signer, block_at, received_at, *, pair=PAIR, signature=None):
    return {
        "pool_address": pair,
        "base_mint": "MINT",
        "quote_mint": "USDC",
        "signature": signature or f"{side}-{block_at.timestamp()}",
        "instruction_path": "0.1",
        "side": side,
        "signer_address": signer,
        "block_time": block_at.isoformat(),
        "observed_at": received_at.isoformat(),
        "recorded_at": received_at.isoformat(),
    }


def _frame(opened, seconds, frame_id, watchlist, trades=(), *, price=1.0, liquidity=1_000):
    observed = opened + timedelta(seconds=seconds)
    recorded = observed + timedelta(seconds=1)
    return {
        "frame_id": frame_id,
        "token_id": TOKEN_ID,
        "pair_address": PAIR,
        "original_pool": True,
        "observed_at": observed.isoformat(),
        "recorded_at": recorded.isoformat(),
        "price_usd": price,
        "liquidity_usd": liquidity,
        "watchlist": watchlist,
        "participation_scan": {
            "complete": False,
            "trades": list(trades),
        },
    }


def _exit(position, frame, state=None):
    return evaluate_wallet_distribution_exit(
        position,
        frame,
        state,
        now=datetime.fromisoformat(frame["recorded_at"]),
    )


def test_watchlist_seals_latest_twenty_received_addresses_without_scores():
    activated = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    candidates = [
        {
            "address": f"wallet-{index}",
            "observed_at": (activated - timedelta(seconds=30 - index)).isoformat(),
            "recorded_at": (activated - timedelta(seconds=29 - index)).isoformat(),
            "return_score": 999,
        }
        for index in range(25)
    ]
    candidates.append({
        "address": "future",
        "observed_at": (activated + timedelta(seconds=1)).isoformat(),
        "recorded_at": (activated + timedelta(seconds=1)).isoformat(),
    })
    sealed = seal_watchlist(candidates, activated_at=activated, now=activated)
    assert sealed["addresses"] == [f"wallet-{index}" for index in range(24, 4, -1)]
    assert sealed["candidate_count"] == 25
    assert sealed["omitted_count"] == 5
    assert "score" not in sealed
    assert sealed["history_coverage"] == "forward_observations_only_after_activation"


def test_wallet_policies_are_unique_five_u_s05_and_s06_pairs():
    policies = wallet_observer_policies()
    assert {policy["arm_id"] for policy in policies} == {
        "watched_wallet_distribution_candidate_v1",
        "watched_wallet_distribution_control_v1",
        "watched_wallet_confirmed_entry_candidate_v1",
        "watched_wallet_confirmed_entry_control_v1",
    }
    assert all(policy["notional_usd"] == 5.0 for policy in policies)
    s05 = [policy for policy in policies if "distribution" in policy["arm_id"]]
    s06 = [policy for policy in policies if "confirmed_entry" in policy["arm_id"]]
    assert all(policy["entry_match_mode"] == "isolated_cohort_observer" for policy in s05)
    assert all(policy["entry_family"] == "broad_launch" for policy in s05)
    assert all(
        policy["entry_match_mode"] == "isolated_pattern_observer" for policy in s06
    )
    assert all(
        policy["entry_filter"]["required_market_surface"] == "solana_pumpswap"
        for policy in s06
    )
    assert all("paired_entry_group" not in policy for policy in policies)
    assert all(policy["paired_opportunity_group"].startswith("watched_wallet_") for policy in policies)
    assert sum(policy["wallet_exit_kind"] is not None for policy in s05) == 1
    existing_ids = {
        policy["arm_id"]
        for policy in capital_policies() + l0_experiment_policies()
    }
    assert existing_ids.isdisjoint(policy["arm_id"] for policy in policies)


def test_late_seal_seed_trade_cannot_self_confirm_but_later_trade_can():
    activated = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    sealed_at = activated + timedelta(seconds=10)
    watchlist = seal_watchlist(
        [{
            "address": "watched",
            "observed_at": sealed_at.isoformat(),
            "recorded_at": sealed_at.isoformat(),
        }],
        activated_at=activated,
        now=sealed_at,
    )
    seed = _trade(
        "BUY", "watched", sealed_at - timedelta(seconds=1), sealed_at,
        signature="seed-trade",
    )
    hits, evidence = participation_hits(
        watchlist, {"complete": True, "trades": [seed]},
        token_id=TOKEN_ID, pair_address=PAIR,
        not_before=activated, now=sealed_at,
    )
    assert hits == []
    assert evidence["positive_hit_count"] == 0

    received = sealed_at + timedelta(seconds=2)
    later = _trade(
        "BUY", "watched", sealed_at + timedelta(seconds=1), received,
        signature="post-seal-trade",
    )
    hits, evidence = participation_hits(
        watchlist, {"complete": True, "trades": [seed, later]},
        token_id=TOKEN_ID, pair_address=PAIR,
        not_before=activated, now=received,
    )
    assert [hit["signature"] for hit in hits] == ["post-seal-trade"]
    assert evidence["positive_hit_count"] == 1


def test_s05_requires_watched_buy_then_later_sell_and_two_weak_l0_frames():
    activated = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    watchlist = _watchlist(activated)
    opened = activated + timedelta(seconds=10)
    position = {
        "opened_at": opened.isoformat(),
        "token_id": TOKEN_ID,
        "pair_address": PAIR,
    }

    no_hit = _frame(opened, 5, "no-hit", watchlist)
    action, reason, state, evidence = _exit(position, no_hit)
    assert (action, reason) == (HOLD, "watched_wallet_buy_not_observed")
    assert evidence["scan_complete"] is False
    assert evidence["absence_inference"] is False

    buy_frame = _frame(opened, 10, "buy", watchlist, price=1.0, liquidity=1_000)
    received = datetime.fromisoformat(buy_frame["recorded_at"])
    buy_frame["participation_scan"]["trades"] = [
        _trade("BUY", "watched", opened + timedelta(seconds=9), received)
    ]
    action, reason, state, _ = _exit(position, buy_frame, state)
    assert (action, reason) == (HOLD, "watched_wallet_sell_not_observed")

    sell_frame = _frame(opened, 20, "sell", watchlist, price=0.95, liquidity=950)
    received = datetime.fromisoformat(sell_frame["recorded_at"])
    sell_frame["participation_scan"]["trades"] = [
        _trade("SELL", "watched", opened + timedelta(seconds=19), received)
    ]
    action, reason, state, evidence = _exit(position, sell_frame, state)
    assert (action, reason) == (HOLD, "wallet_distribution_l0_monitoring")
    assert evidence["weak_streak"] == 1

    weak_frame = _frame(opened, 26, "weak-2", watchlist, price=0.90, liquidity=900)
    action, reason, state, evidence = _exit(position, weak_frame, state)
    assert (action, reason) == (SELL, "watched_wallet_distribution_l0_weak")
    assert evidence["weak_streak"] == 2
    assert evidence["required_fill"] == "next_fresh_original_pool_frame"
    assert evidence["sell_fraction"] == 1.0

    action, reason, repeated, duplicate = _exit(position, weak_frame, state)
    assert (action, reason) == (WAIT, "duplicate_frame")
    assert duplicate["duplicate"] is True
    assert repeated == state


def test_s05_ignores_pre_activation_and_wrong_pool_positive_rows():
    activated = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    watchlist = _watchlist(activated)
    opened = activated + timedelta(seconds=10)
    position = {
        "opened_at": opened.isoformat(),
        "token_id": TOKEN_ID,
        "pair_address": PAIR,
    }
    frame = _frame(opened, 10, "invalid-hits", watchlist)
    received = datetime.fromisoformat(frame["recorded_at"])
    frame["participation_scan"]["trades"] = [
        _trade("BUY", "watched", activated - timedelta(seconds=1), received),
        _trade("BUY", "watched", opened + timedelta(seconds=9), received, pair="OTHER"),
    ]
    action, reason, state, evidence = _exit(position, frame)
    assert (action, reason) == (HOLD, "watched_wallet_buy_not_observed")
    assert state["watched_buys"] == {}
    assert evidence["positive_hit_count"] == 0
    assert evidence["absence_inference"] is False


def test_s06_control_is_immediate_candidate_waits_for_later_buy_and_ttl_is_bounded():
    activated = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    watchlist = _watchlist(activated)
    opportunity_at = activated + timedelta(seconds=10)
    opportunity = {
        "opportunity_id": "broad-1",
        "token_id": TOKEN_ID,
        "pair_address": PAIR,
        "broad_like": True,
        "original_pool": True,
        "observed_at": opportunity_at.isoformat(),
        "recorded_at": opportunity_at.isoformat(),
    }
    initial_now = opportunity_at + timedelta(seconds=1)
    empty = {"watchlist": watchlist, "participation_scan": {"complete": False, "trades": []}}

    action, reason, control, control_evidence = evaluate_wallet_confirmed_entry(
        opportunity, empty, now=initial_now, role="control"
    )
    assert (action, reason) == (READY, "same_opportunity_control_ready")
    assert control_evidence["required_fill"] == "next_fresh_original_pool_frame"

    action, reason, candidate, evidence = evaluate_wallet_confirmed_entry(
        opportunity, empty, now=initial_now, role="candidate"
    )
    assert (action, reason) == (WAIT, "wallet_buy_not_observed_coverage_unknown")
    assert evidence["absence_inference"] is False

    received = opportunity_at + timedelta(seconds=20)
    scan = {
        "watchlist": watchlist,
        "participation_scan": {
            "complete": False,
            "trades": [
                _trade("BUY", "watched", opportunity_at + timedelta(seconds=10), received)
            ],
        },
    }
    action, reason, candidate, evidence = evaluate_wallet_confirmed_entry(
        opportunity, scan, candidate, now=received, role="candidate"
    )
    assert (action, reason) == (READY, "watched_wallet_buy_confirmed")
    assert evidence["same_initial_opportunity"] is True
    assert evidence["same_buy_price_claimed"] is False
    assert candidate["ready_at"] != control["ready_at"]

    expired_at = opportunity_at + timedelta(seconds=601)
    action, reason, expired, _ = evaluate_wallet_confirmed_entry(
        opportunity, empty, now=expired_at, role="candidate"
    )
    assert (action, reason) == (EXPIRED, "wallet_confirmation_ttl_expired")
    assert expired["status"] == "EXPIRED"
