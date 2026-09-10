from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from solders.pubkey import Pubkey

from memetrader.capital_policies import (
    capital_policies,
    direct_lp_amount_specific_policy,
    event_actual_flow_policy,
    opportunity_policies,
    second_discussion_policies,
)
from memetrader.migration_absorption import migration_amount_absorption_policy
from memetrader.models import TokenCandidate, TokenSnapshot
from memetrader.runtime import Runtime
from memetrader.store import Store


UTC = timezone.utc
TARGET_VERSION = "test-evidence-extension-funding-v1"


def _policies():
    policies = [
        *capital_policies(),
        *second_discussion_policies(),
        *opportunity_policies(),
        direct_lp_amount_specific_policy(),
        event_actual_flow_policy(),
        migration_amount_absorption_policy(),
    ]
    return {policy["arm_id"]: policy for policy in policies}


CASES = [
    (
        "direct_lp_amount_specific_confirmed_v1",
        [(10, 1.00, 10_000, 2_000, 14, 6)],
        120,
        "replacement_early_quality_confirmed",
    ),
    (
        "official_event_actual_flow_v1",
        [
            (10, 1.00, 10_000, 1_000, 14, 6),
            (20, 1.02, 10_000, 1_000, 14, 6),
            (30, 1.05, 10_000, 1_000, 14, 6),
        ],
        500,
        "replacement_continuation_confirmed",
    ),
    (
        "finite_capital_ranker_v1",
        [(10, 1.00, 10_000, 2_000, 14, 6)],
        500,
        "replacement_quality_gate_confirmed",
    ),
    (
        "event_reawakening_v1",
        [
            (10, 1.00, 10_000, 100, 1, 1),
            (20, 1.00, 10_000, 100, 1, 1),
            (30, 1.00, 10_000, 100, 1, 1),
            (40, 1.12, 9_000, 1_200, 14, 6),
        ],
        4_000,
        "replacement_reawakening_confirmed",
    ),
    (
        "surface_lifecycle_pipeline_v1",
        [
            (10, 1.00, 10_000, 1_000, 14, 6),
            (20, 1.02, 11_000, 1_000, 14, 6),
            (30, 1.05, 12_000, 1_000, 14, 6),
        ],
        4_000,
        "replacement_liquidity_lead_confirmed",
    ),
    (
        "no_ca_event_flow_leader_v1",
        [
            (10, 1.00, 10_000, 500, 14, 6),
            (20, 1.00, 10_000, 500, 14, 6),
            (30, 1.00, 10_000, 500, 14, 6),
            (40, 1.10, 10_000, 1_000, 14, 6),
        ],
        500,
        "replacement_compression_breakout_confirmed",
    ),
    (
        "migration_amount_rate_absorption_v1",
        [
            (10, 1.00, 10_000, 1_200, 14, 6),
            (20, 1.02, 10_000, 1_200, 14, 6),
            (30, 1.06, 10_000, 1_200, 14, 6),
        ],
        500,
        "replacement_young_absorption_confirmed",
    ),
]


def _snapshot(token, pair, observed_at, created_at, *, price, liquidity, volume,
              buys, sells):
    return TokenSnapshot(
        token.chain,
        token.address,
        price,
        liquidity,
        100_000.0,
        volume,
        buys,
        sells,
        observed_at=observed_at,
        ingested_at=observed_at,
        provider="dexscreener",
        raw={
            "pair": {
                "chainId": token.chain,
                "pairAddress": pair,
                "dexId": "pumpswap",
                "pairCreatedAt": round(created_at.timestamp() * 1_000),
                "baseToken": {"address": token.address},
                "priceUsd": str(price),
                "liquidity": {"usd": liquidity},
            }
        },
    )


@pytest.mark.parametrize("arm_id,frames,base_age,ready_reason", CASES)
def test_revised_evidence_arm_uses_l0_then_next_frame_buy_and_can_time_exit(
    tmp_path, monkeypatch, arm_id, frames, base_age, ready_reason,
):
    clock = [datetime(2026, 9, 6, 15, 0, tzinfo=UTC)]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / f"{arm_id}.sqlite3", initial_cash_usd=1_000)
    source_version = Store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    source_policy = _policies()[arm_id]
    try:
        store.activate_chain_meme_trader_funded_period()
        source_row = store.append_chain_meme_trader_policy(
            source_policy, activated_at=clock[0]
        )
        source_hash = str(source_row["behavior_contract_hash"])
        source_json = str(source_row["policy_json"])

        store.activate_chain_meme_trader_funding_epoch(
            target_version=TARGET_VERSION,
            source_version=source_version,
            at=clock[0] + timedelta(seconds=1),
            apply_strategy_revisions=True,
        )
        monkeypatch.setattr(Store, "CHAIN_MEME_TRADER_ACTIVE_VERSION", TARGET_VERSION)
        target_row = store.db.execute(
            "SELECT * FROM chain_meme_trader_policy_additions "
            "WHERE definition_version=? AND arm_id=?",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        revised = json.loads(target_row["policy_json"])
        assert revised["entry_family"] == "evidence_extension_l0"
        assert revised["arm_id"] == source_policy["arm_id"]
        assert revised["canonical_id"] == source_policy["canonical_id"]
        assert str(target_row["behavior_contract_hash"]) != source_hash
        assert store.db.execute(
            "SELECT behavior_contract_hash,policy_json FROM "
            "chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?",
            (source_version, arm_id),
        ).fetchone()[:] == (source_hash, source_json)
        if arm_id == "finite_capital_ranker_v1":
            assert store.capital_cross_section([], now=clock[0]) == {}

        token = TokenCandidate(
            "solana", str(Pubkey.new_unique()), "Extension", "EXT", source="test"
        )
        pair = str(Pubkey.new_unique())
        activated_at = clock[0] + timedelta(seconds=1)
        created_at = activated_at - timedelta(seconds=base_age)
        for seconds, price, liquidity, volume, buys, sells in frames:
            clock[0] = activated_at + timedelta(seconds=seconds)
            assert store.observe_chain_meme_pattern(
                token,
                _snapshot(
                    token, pair, clock[0], created_at, price=price,
                    liquidity=liquidity, volume=volume, buys=buys, sells=sells,
                ),
                recorded_at=clock[0],
            ) == 0

        ready = json.loads(store.db.execute(
            "SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations "
            "WHERE definition_version=? ORDER BY id DESC LIMIT 1",
            (TARGET_VERSION,),
        ).fetchone()[0])
        assert ready["outcomes"][arm_id] == ready_reason
        assert arm_id in ready["ready_arm_ids"]

        # The confirmed frame is only the signal. A later same-pool frame fills.
        seconds, price, liquidity, volume, buys, sells = frames[-1]
        clock[0] = activated_at + timedelta(seconds=seconds + 10)
        assert store.observe_chain_meme_pattern(
            token,
            _snapshot(
                token, pair, clock[0], created_at, price=price,
                liquidity=liquidity, volume=volume, buys=buys, sells=sells,
            ),
            recorded_at=clock[0],
        ) == 1
        position = store.db.execute(
            "SELECT * FROM chain_meme_trader_positions WHERE definition_version=? "
            "AND arm_id=?",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert position is not None and position["status"] == "open"
        decision = store.db.execute(
            "SELECT * FROM chain_meme_trader_entry_decisions WHERE definition_version=? "
            "AND arm_id=? ORDER BY id DESC LIMIT 1",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert decision["status"] == "admitted"
        assert decision["reason"] == "pattern_next_observation"

        if arm_id == 'event_reawakening_v1':
            from memetrader.microstructure_shadow_worker import MicrostructureWorker
            from memetrader.models import iso
            from memetrader.market_microstructure import branch_decision
            worker=MicrostructureWorker(store,SimpleNamespace(),lambda:asyncio.Event())
            cohort=store.db.execute('SELECT * FROM chain_meme_trader_v6_cohorts WHERE id=?',
                (position['shadow_cohort_id'],)).fetchone()
            features=json.loads(cohort['feature_json'])
            assert cohort['entry_family']=='broad_launch' and not features['reactivation_ready']
            item=dict(version=TARGET_VERSION,cohort_id=cohort['id'],token_id=token.token_id,
                pool=pair,requested_at=iso(clock[0]),expires_at=iso(clock[0]+timedelta(seconds=120)))
            worker.enqueue(item)
            queued=next(iter(worker.pending.values()))
            assert queued['reactivation']
            proof=queued['reawakening_source']
            assert proof['snapshot_id']==features['fill_signal_snapshot_id']
            assert proof['outcome']=='replacement_reawakening_confirmed'
            # Wrong source ready/outcome/clock/identity is not rescued by carrier flags.
            db=store.db
            class ChangedRead:
                def __init__(self,field,value):self.field,self.value=field,value
                def execute(self,sql,args):
                    row=dict(db.execute(sql,args).fetchone())
                    if self.field=='evaluated_at':row[self.field]=self.value
                    else:
                        f=json.loads(row['feature_json']);f[self.field]=self.value
                        row['feature_json']=json.dumps(f)
                    return SimpleNamespace(fetchone=lambda:row)
            for field,value in [('ready_arm_ids',[]),('outcomes',{}),('pair_address','wrong'),
                                ('evaluated_at',iso(clock[0]+timedelta(seconds=1)))]:
                worker.store=SimpleNamespace(db=ChangedRead(field,value))
                assert worker._reawakening_source(item,cohort,features) is None
            worker.store=store
            assert worker._reawakening_source({**item,'token_id':'solana:other'},cohort,features) is None
            assert worker._reawakening_source(item,cohort,{**features,'fill_signal_snapshot_id':None}) is None
            later=iso(clock[0]+timedelta(seconds=1))
            assert branch_decision(dict(state='ORGANIC_BREADTH_NET_BUY',token_id=token.token_id,
                pool=pair,recorded_at=iso(clock[0])),token_id=token.token_id,pool=pair,
                frame_observed=later,frame_recorded=later,price=1,liquidity=10000,
                reawakening=queued['reactivation'],safety_allow=False,require_safety=False,
                surface=dict(kind='OBSERVED_DEX_PAPER_ORIGINAL_POOL',token_id=token.token_id,
                    pool=pair,observed_at=later,recorded_at=later))=='ORGANIC_SHADOW_ELIGIBLE'
            queued['shadow_costs']={}
            worker._capture('actual-source',{'item':queued,'result':dict(
                state='ORGANIC_BREADTH_NET_BUY',token_id=token.token_id,pool=pair,
                recorded_at=iso(clock[0]),signal_at=item['requested_at'])},
                dict(eligible=True,price_usd=1,liquidity_usd=10000,observed_at=later,recorded_at=later,
                    surface=dict(kind='OBSERVED_DEX_PAPER_ORIGINAL_POOL',token_id=token.token_id,
                        pool=pair,observed_at=later,recorded_at=later)),clock[0]+timedelta(seconds=1))
            routed=worker.ready['actual-source']
            assert routed['arm']=='organic_reawakening_flow_v1'
            assert routed['signal']['decision_evidence']['reawakening_source']==proof

        if arm_id == "direct_lp_amount_specific_confirmed_v1":
            assert store.due_direct_lp_entry_preflight_quote(now=clock[0]) is None
            assert store.db.execute(
                "SELECT COUNT(*) FROM chain_meme_pattern_evidence "
                "WHERE kind='direct_lp_entry_preflight_request'"
            ).fetchone()[0] == 0

        # Every replacement retains an ordinary maximum-hold escape, including
        # arms whose optional specialist exit evidence never arrives.
        clock[0] = clock[0] + timedelta(
            minutes=float(revised.get("max_hold_minutes") or 240) + 1
        )
        mark = _snapshot(
            token, pair, clock[0], created_at, price=price,
            liquidity=liquidity, volume=volume, buys=buys, sells=sells,
        )
        store.upsert_chain_meme_trader_market_mark(token, mark, recorded_at=clock[0])
        assert store.evaluate_chain_meme_trader_market_marks(
            definition_version=TARGET_VERSION, now=clock[0]
        ) == 1
        pending = store.db.execute(
            "SELECT reason,status FROM chain_meme_trader_marks WHERE definition_version=? "
            "AND arm_id=? ORDER BY id DESC LIMIT 1",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert pending["reason"] == "market_mark_max_hold"
        assert pending["status"] == "pending"

        clock[0] = clock[0] + timedelta(seconds=2)
        mark = _snapshot(
            token, pair, clock[0], created_at, price=price,
            liquidity=liquidity, volume=volume, buys=buys, sells=sells,
        )
        store.upsert_chain_meme_trader_market_mark(token, mark, recorded_at=clock[0])
        assert store.evaluate_chain_meme_trader_market_marks(
            definition_version=TARGET_VERSION, now=clock[0]
        ) == 1
        closed = store.db.execute(
            "SELECT status,close_reason FROM chain_meme_trader_positions "
            "WHERE definition_version=? AND arm_id=?",
            (TARGET_VERSION, arm_id),
        ).fetchone()
        assert closed["status"] == "closed"
        assert closed["close_reason"].startswith("market_mark_max_hold")
    finally:
        store.close()


def test_pattern_observer_waits_once_per_chain_not_again_per_token(monkeypatch):
    async def run():
        runtime = Runtime.__new__(Runtime)
        runtime._chain_meme_active_idle_event = asyncio.Event()
        runtime._chain_meme_active_idle_event.set()
        runtime._remember_pattern_quotes = lambda quoted: None
        runtime._rank_no_ca_events = lambda: None
        runtime._paper_quote_rejections = lambda *args: []
        now = datetime(2026, 9, 6, 15, 0, tzinfo=UTC)
        monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
        created_at = now - timedelta(seconds=120)
        tokens = [
            TokenCandidate(
                "solana", str(Pubkey.new_unique()), "Extension", f"E{index}",
                source="test",
            )
            for index in range(2)
        ]
        pairs = [str(Pubkey.new_unique()) for _ in tokens]
        runtime._pattern_watch = {
            token.token_id: {
                "token": token,
                "pair_address": pair,
                "quote": _snapshot(
                    token, pair, now, created_at, price=1.0, liquidity=10_000,
                    volume=1_000, buys=14, sells=6,
                ),
            }
            for token, pair in zip(tokens, pairs)
        }
        runtime._pattern_held_tokens = set(runtime._pattern_watch)
        observed = []

        def observe(token, *args, **kwargs):
            observed.append(token.token_id)
            if len(observed) == 1:
                runtime._chain_meme_active_idle_event.clear()
            return 0

        runtime.store = SimpleNamespace(
            capital_cross_section=lambda *args: {},
            observe_chain_meme_pattern=observe,
            heartbeat=lambda *args, **kwargs: None,
        )
        await asyncio.wait_for(runtime.chain_meme_pattern_observer_once(), timeout=.2)
        assert observed == [token.token_id for token in tokens]

    asyncio.run(run())


@pytest.mark.parametrize("available", [True, False])
def test_pattern_observer_batches_each_due_chain_with_shared_priority_gate(monkeypatch, available):
    async def run():
        runtime = Runtime.__new__(Runtime)
        runtime.chain_meme_trader_only = False
        runtime._rank_no_ca_events = lambda: None
        runtime._paper_quote_rejections = lambda *args: []
        runtime._dex_quote_low_priority_available = lambda: available
        now = datetime(2026, 9, 6, 15, 0, tzinfo=UTC)
        monkeypatch.setattr("memetrader.runtime.utcnow", lambda: now)
        runtime._pattern_watch = {}
        for chain in ("bsc", "robinhood", "solana"):
            for i in range(2):
                address = str(Pubkey.new_unique()) if chain == "solana" else "0x" + str(i+1) * 40
                token = TokenCandidate(chain, address, "Due")
                pair = str(Pubkey.new_unique()) if chain == "solana" else "0x" + str(i+3) * 40
                old = now - timedelta(seconds=46)
                runtime._pattern_watch[token.token_id] = {"token": token, "pair_address": pair,
                    "sampled_at": old, "quote": _snapshot(token, pair, old, old-timedelta(minutes=2),
                        price=1., liquidity=10000, volume=1000, buys=14, sells=6)}
        def remember(quoted):
            for token_id, (_, snapshot) in quoted.items():
                runtime._pattern_watch[token_id]["quote"] = snapshot
        runtime._remember_pattern_quotes = remember
        calls, observed = [], []
        held_response_applied = []
        all_started = asyncio.Event()
        peer_applied = asyncio.Event()
        async def fresh(chain, addresses, **kwargs):
            assert kwargs == {"fresh": True, "high_priority": False}
            calls.append((chain, list(addresses)))
            if len(calls) == 3:
                all_started.set()
            # Every chain must start before any response is required to finish.
            await asyncio.wait_for(all_started.wait(), timeout=.2)
            if chain == "bsc":
                # The fast peer must be processed without waiting for this chain.
                await asyncio.wait_for(peer_applied.wait(), timeout=.2)
            result = {}
            for token_id, item in runtime._pattern_watch.items():
                if item["token"].chain == chain:
                    result[token_id] = (item["token"], _snapshot(item["token"], item["pair_address"],
                        now, now-timedelta(minutes=3), price=1., liquidity=10000, volume=1000, buys=14, sells=6))
            return result
        runtime._dex_batch_quote = fresh
        def observe(token, *args, **kwargs):
            if observed:
                assert held_response_applied == [True]
            else:
                asyncio.get_running_loop().call_soon(held_response_applied.append, True)
            observed.append(token.token_id)
            if token.chain != "bsc":
                peer_applied.set()
            return 0
        runtime.store = SimpleNamespace(capital_cross_section=lambda *args: {},
            observe_chain_meme_pattern=observe,
            heartbeat=lambda *args, **kwargs: None, set_kv=lambda *args: None)
        await runtime.chain_meme_pattern_observer_once()
        assert [chain for chain, _ in calls] == (["bsc", "robinhood", "solana"] if available else [])
        assert all(len(addresses) == 2 for _, addresses in calls)
        assert len(observed) == (6 if available else 0)
    asyncio.run(run())
