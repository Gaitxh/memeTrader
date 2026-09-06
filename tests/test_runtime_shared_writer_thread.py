from __future__ import annotations

import asyncio
import threading
from collections import deque
from datetime import timedelta

from solders.pubkey import Pubkey

from memetrader.models import TokenCandidate, utcnow
from memetrader.runtime import Runtime
from test_l0_store import _snapshot


class _ThreadRecordingStore:
    CHAIN_MEME_TRADER_ACTIVE_VERSION = "test-version"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def _record(self, name: str) -> None:
        self.calls.append((name, threading.get_ident()))

    def enroll_chain_meme_universe_outcomes(self, **_kwargs):
        self._record("enroll_outcomes")
        return {"targets_enrolled": 1}

    def finalize_chain_meme_universe_outcomes(self, **_kwargs):
        self._record("finalize_outcomes")
        return {"observed": 1, "unknown": 0}

    def update_chain_opportunity_regimes(self, *_args):
        self._record("update_regimes")

    def chain_meme_cohort_receipts(self, *_args):
        self._record("cohort_receipts")
        return {}, []

    def observe_chain_meme_pattern(self, *_args, **_kwargs):
        self._record("observe_pattern")
        return 1

    def set_kv(self, *_args):
        self._record("set_kv")

    def heartbeat(self, *_args, **_kwargs):
        self._record("heartbeat")


def test_outcomes_and_cohort_store_calls_stay_on_event_loop_thread(monkeypatch):
    now = utcnow()
    token = TokenCandidate("solana", str(Pubkey.new_unique()), "Thread", "THR")
    pair = str(Pubkey.new_unique())
    identity = (token.token_id, pair)

    def consume(frames, state, **_kwargs):
        assert frames
        return state, {
            identity: {
                "thread_identity_arm": {
                    "episode_id": "thread-episode",
                    "decision_key": "thread-episode|thread_identity_arm",
                    "selected": {"token_id": token.token_id, "pair_address": pair},
                    "decision_evidence": {},
                }
            }
        }

    monkeypatch.setattr(
        "memetrader.cohort_experiments.consume_passive_cohort_batch", consume
    )
    store = _ThreadRecordingStore()
    runtime = Runtime.__new__(Runtime)
    runtime.store = store
    runtime._chain_outcome_version = "outcomes-test"
    runtime._cohort_started_at = now - timedelta(seconds=1)
    runtime._cohort_state = {}
    runtime._cohort_batches = deque([(now, [(token, _snapshot(token, pair, now))])])
    runtime._paper_quote_rejections = lambda *_args: []

    async def run() -> int:
        event_loop_thread = threading.get_ident()
        idle = asyncio.Event()
        idle.set()
        runtime._chain_meme_active_idle = lambda: idle
        await runtime.chain_meme_universe_outcomes_once()
        await runtime.chain_meme_cohort_observer_once()
        return event_loop_thread

    event_loop_thread = asyncio.run(run())
    required = {
        "enroll_outcomes",
        "finalize_outcomes",
        "update_regimes",
        "cohort_receipts",
        "observe_pattern",
        "set_kv",
    }
    assert required <= {name for name, _ in store.calls}
    assert {thread_id for _, thread_id in store.calls} == {event_loop_thread}
