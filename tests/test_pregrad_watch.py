import asyncio
import base64
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from solders.pubkey import Pubkey

from memetrader.collectors import (SolanaHeldAccountCollector, PUMP_PROGRAM_ID,
                                  PUMP_BONDING_CURVE_DISCRIMINATOR, SOLANA_SYSTEM_PROGRAM_ID)
from memetrader.pregrad_watch import PregradWatch, bonding_curve_identity


def stamp(seconds=0):
    return (datetime(2026, 9, 5, 12, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def launch(seed=1):
    mint = str(Pubkey.new_unique())
    value = dict(id=1, chain="solana", address=mint, token_id="solana:" + mint,
                 launch_event_type="create", initial_quote_amount=seed,
                 source_observed_at=stamp(), ingested_at=stamp(), recorded_at=stamp())
    value["bonding_curve_key"] = bonding_curve_identity(value)["curve_address"]
    return value


def frame(item, seconds=10, slot=100, amount=10**9, **extra):
    return dict(**bonding_curve_identity(item), status="verified", identity_verified=True,
                observed_at=stamp(seconds), recorded_at=stamp(seconds), slot=slot,
                real_quote_reserves_raw=amount, real_token_reserves_raw=200,
                quote_mint=SOLANA_SYSTEM_PROGRAM_ID, data_hash="account-bytes-hash",
                curve_complete=False, **extra)


def test_seed_bound_priority_and_ttl_do_not_create_velocity_or_buy():
    watch = PregradWatch()
    seeds = [launch(n) for n in range(1, 5)]
    for item in seeds:
        watch.observe_launch(item, now=stamp())
    ranked = watch.ranked(now=stamp())
    assert len(watch.targets(now=stamp())) == 3
    assert [r["initial_quote_amount"] for r in ranked] == [4, 3, 2]
    assert all(r["net_reserve_growth_quote_per_second"] is None for r in ranked)
    assert all(r["priority_basis"] == "launch_seed_size" and not r["decision_eligible"] for r in ranked)
    assert watch.targets(now=stamp(300)) == []
    assert watch.observe_launch(seeds[0], now=stamp(300)) is None


def test_two_increasing_real_frames_negative_growth_and_bounded_history():
    watch, item = PregradWatch(), launch()
    watch.observe_launch(item, now=stamp())
    first = watch.apply_observation(frame(item), now=stamp(10))
    assert first["net_reserve_growth_quote_per_second"] is None
    second = watch.apply_observation(frame(item, 40, 101, 4 * 10**9), now=stamp(40))
    assert second["net_reserve_growth_quote_per_second"] == .1
    assert second["priority_basis"] == "observed_net_reserve_growth_not_gross_flow"
    watch.observe_launch(launch(100), now=stamp(40))
    assert watch.targets(now=stamp(40))[0]["token_id"] == item["token_id"]
    third = watch.apply_observation(frame(item, 70, 102, 10**9), now=stamp(70))
    assert third["net_reserve_growth_quote_per_second"] == -.1
    assert len(third["reserve_frames"]) == 2


def test_unknown_quote_keeps_atomic_reserves_without_assuming_sol_units():
    watch, item = PregradWatch(), launch()
    watch.observe_launch(item, now=stamp())
    quote = str(Pubkey.new_unique())
    for seconds, slot, amount in ((10, 100, 0), (40, 101, 3000)):
        value = frame(item, seconds, slot, amount)
        value["quote_mint"] = quote
        result = watch.apply_observation(value, now=stamp(seconds))
    assert len(result["reserve_frames"]) == 2
    assert result["net_reserve_growth_quote_per_second"] is None
    assert "net_reserve_growth_usd_per_second" not in result


@pytest.mark.parametrize("change", [
    {"slot": 100}, {"observed_at": stamp(10)}, {"recorded_at": stamp(50)},
    {"identity_verified": False}, {"base_mint": str(Pubkey.new_unique())},
    {"curve_address": str(Pubkey.new_unique())}, {"status": "UNKNOWN_ACCOUNT"},
])
def test_invalid_future_repeated_frames_do_not_create_growth(change):
    watch, item = PregradWatch(), launch()
    watch.observe_launch(item, now=stamp())
    watch.apply_observation(frame(item), now=stamp(10))
    value = frame(item, 40, 101, 4 * 10**9)
    value.update(change)
    assert watch.apply_observation(value, now=stamp(40)) is None
    assert watch.ranked(now=stamp(40))[0]["net_reserve_growth_quote_per_second"] is None


def test_complete_stops_queries_without_claiming_migration_then_handoffs_once():
    watch, item = PregradWatch(), launch()
    watch.observe_launch(item, now=stamp())
    value = frame(item)
    value["curve_complete"] = True
    assert watch.apply_observation(value, now=stamp(10))["stage"] == "CURVE_COMPLETE"
    assert watch.targets(now=stamp(10)) == []
    migration = {**item, "id": 2, "launch_event_type": "migration",
                 "source_observed_at": stamp(20), "ingested_at": stamp(20), "recorded_at": stamp(20)}
    assert watch.observe_launch(migration, now=stamp(20))["requeue_hydration"] is True
    assert watch.observe_launch(migration, now=stamp(20)) is None
    assert watch.apply_observation(frame(item, 30, 101), now=stamp(30)) is None


def test_bad_launch_identity_future_and_non_sol_are_not_watched():
    watch, item = PregradWatch(), launch()
    assert watch.observe_launch({**item, "bonding_curve_key": str(Pubkey.new_unique())}, now=stamp()) is None
    assert watch.observe_launch({**item, "chain": "bsc"}, now=stamp()) is None
    assert watch.observe_launch({**item, "recorded_at": stamp(1)}, now=stamp()) is None
    assert watch.targets(now=stamp()) == []


def test_collector_reuses_confirmed_bounded_account_read_and_real_decode():
    async def run():
        seeds = [launch() for _ in range(4)]
        calls = []
        raw = bytearray(115)
        raw[:8] = PUMP_BONDING_CURVE_DISCRIMINATOR
        raw[24:32] = (200).to_bytes(8, "little")
        raw[32:40] = (1234567890).to_bytes(8, "little")
        value = dict(owner=PUMP_PROGRAM_ID, lamports=100,
                     data=[base64.b64encode(raw).decode(), "base64"])

        def respond(request):
            import json
            payload = json.loads(request.content)
            calls.append(payload)
            return httpx.Response(200, json={"result": {"context": {"slot": 123},
                                  "value": [value, {**value, "owner": str(Pubkey.new_unique())}, None]}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            collector = SolanaHeldAccountCollector.__new__(SolanaHeldAccountCollector)
            collector.http, collector.rpc_url, collector.max_multiple_accounts = client, "https://rpc.test", 100
            observed = await collector.bonding_curve_observations(seeds)
            assert len(calls) == 1 and len(calls[0]["params"][0]) == 3
            assert calls[0]["method"] == "getMultipleAccounts"
            assert calls[0]["params"][1]["commitment"] == "confirmed"
            assert observed[0]["real_quote_reserves_raw"] == 1234567890
            assert observed[0]["identity_verified"] is True
            assert [r["status"] for r in observed] == ["verified", "UNKNOWN_ACCOUNT", "UNKNOWN_ACCOUNT"]
            assert all("input_amount_raw" not in r for r in observed)
            assert await collector.bonding_curve_observations([]) == []
            assert await collector.bonding_curve_observations([{**seeds[0], "stage": "CURVE_COMPLETE"}]) == []
            rejected = await collector.bonding_curve_observations([{**seeds[0], "bonding_curve_key": str(Pubkey.new_unique())}])
            assert rejected[0]["status"] == "UNKNOWN_IDENTITY" and len(calls) == 1
    asyncio.run(run())
