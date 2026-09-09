from __future__ import annotations

from datetime import datetime, timedelta

from memetrader.flat_frontier import (
    FlatFrontierEvaluation,
    FlatFrontierMark,
    FlatFrontierObservation,
    FlatTargetFrontier,
)
from memetrader.models import UTC


BASE = datetime(2026, 9, 9, tzinfo=UTC)


def _evaluation(token_id: str, evaluation_id: int, pair: str, *, age_hours: float):
    return FlatFrontierEvaluation(
        token_id=token_id,
        chain="solana",
        address=f"address-{token_id}",
        evaluation_id=evaluation_id,
        pair_address=pair,
        pair_created_at=BASE - timedelta(hours=age_hours),
    )


def _ids(frontier: FlatTargetFrontier, now: datetime) -> list[str]:
    return [target.token_id for target in frontier.select(now=now)]


def test_frontier_admits_new_evaluations_and_age_crossings_without_refill_delay():
    frontier = FlatTargetFrontier()
    frontier.rebuild(
        evaluations=[
            _evaluation("age", 10, "pair-age", age_hours=6 - 1 / 3600),
            _evaluation("ordinary", 20, "pair-ordinary", age_hours=7),
        ],
        observations=[
            FlatFrontierObservation("age", "pair-age", 1, "near_trigger"),
            FlatFrontierObservation("ordinary", "pair-ordinary", 1, "flat_watch"),
        ],
        marks=[],
        open_position_counts=[],
        registered=True,
        now=BASE,
    )

    assert _ids(frontier, BASE) == ["ordinary"]
    assert _ids(frontier, BASE + timedelta(seconds=1)) == ["age", "ordinary"]

    frontier.on_evaluation(_evaluation("new", 30, "pair-new", age_hours=7), now=BASE + timedelta(seconds=2))
    assert _ids(frontier, BASE + timedelta(seconds=2)) == ["age", "new", "ordinary"]


def test_frontier_tracks_pair_near_state_attempt_and_open_close_changes_in_sql_order():
    frontier = FlatTargetFrontier()
    frontier.rebuild(
        evaluations=[
            _evaluation("switch", 10, "old-pair", age_hours=7),
            _evaluation("ordinary", 20, "ordinary-pair", age_hours=7),
        ],
        observations=[
            FlatFrontierObservation("switch", "old-pair", 1, "near_trigger"),
            FlatFrontierObservation("switch", "new-pair", 5, "near_trigger"),
            FlatFrontierObservation("ordinary", "ordinary-pair", 1, "flat_watch"),
        ],
        marks=[FlatFrontierMark("ordinary", BASE - timedelta(seconds=61))],
        open_position_counts=[],
        registered=True,
        now=BASE,
    )

    assert _ids(frontier, BASE) == ["switch", "ordinary"]
    frontier.on_mark(FlatFrontierMark("switch", BASE), now=BASE)
    assert _ids(frontier, BASE + timedelta(seconds=4)) == ["ordinary"]
    assert _ids(frontier, BASE + timedelta(seconds=5)) == ["switch", "ordinary"]

    frontier.on_evaluation(_evaluation("switch", 30, "new-pair", age_hours=7), now=BASE + timedelta(seconds=5))
    changed = frontier.select(now=BASE + timedelta(seconds=5))
    assert [target.token_id for target in changed] == ["switch", "ordinary"]
    assert changed[0].pair_address == "new-pair"

    frontier.on_mark(FlatFrontierMark("switch", BASE + timedelta(seconds=10)), now=BASE + timedelta(seconds=10))
    frontier.on_observation(
        FlatFrontierObservation("switch", "new-pair", 6, "flat_watch"),
        now=BASE + timedelta(seconds=10),
    )
    assert _ids(frontier, BASE + timedelta(seconds=69)) == ["ordinary"]
    assert _ids(frontier, BASE + timedelta(seconds=70)) == ["ordinary", "switch"]

    frontier.on_open_position_count("switch", 1, now=BASE + timedelta(seconds=70))
    assert _ids(frontier, BASE + timedelta(seconds=70)) == ["ordinary"]
    frontier.on_open_position_count("switch", 0, now=BASE + timedelta(seconds=70))
    assert _ids(frontier, BASE + timedelta(seconds=70)) == ["ordinary", "switch"]


def test_frontier_keeps_sql_latest_eval_and_observation_rules():
    frontier = FlatTargetFrontier()
    frontier.rebuild(
        evaluations=[_evaluation("token", 10, "pair-a", age_hours=7)],
        observations=[FlatFrontierObservation("token", "pair-a", 3, "flat_watch")],
        marks=[],
        open_position_counts=[],
        registered=True,
        now=BASE,
    )

    # Empty pairs are filtered before SQL takes MAX(id), so they do not evict id=10.
    frontier.on_evaluation(
        FlatFrontierEvaluation("token", "solana", "address-token", 99, "", BASE),
        now=BASE,
    )
    frontier.on_observation(
        FlatFrontierObservation("token", "pair-a", 2, "near_trigger"), now=BASE,
    )
    target = frontier.select(now=BASE)[0]
    assert target.pair_address == "pair-a"
    assert target.observer_state == "flat_watch"


def test_frontier_mirrors_registration_gate_and_token_output_updates():
    frontier = FlatTargetFrontier()
    frontier.rebuild(
        evaluations=[_evaluation("token", 10, "pair", age_hours=7)],
        observations=[],
        marks=[],
        open_position_counts=[],
        registered=False,
        now=BASE,
    )

    assert _ids(frontier, BASE) == []
    frontier.set_registered(True, now=BASE)
    frontier.on_token("token", chain="bsc", address="new-address", now=BASE)
    target = frontier.select(now=BASE)[0]
    assert (target.chain, target.address) == ("bsc", "new-address")


def test_frontier_compacts_stale_heap_entries_without_a_database_rescan():
    frontier = FlatTargetFrontier()
    frontier.rebuild(
        evaluations=[_evaluation("token", 1, "pair-0", age_hours=5)],
        observations=[],
        marks=[],
        open_position_counts=[],
        registered=True,
        now=BASE,
    )

    for evaluation_id in range(2, 200):
        frontier.on_evaluation(
            _evaluation("token", evaluation_id, f"pair-{evaluation_id}", age_hours=5),
            now=BASE,
        )

    assert len(frontier._age_heap) + len(frontier._due_heap) + len(frontier._ready_heap) <= 64
