"""Free-rider lane readout tests.

`scripts/free_rider_lane_readout.py` reconstructs `shared_batch148.offer`'s nine refusals offline,
because the module keeps no counter for WHY it refuses a token. Four things about that reconstruction
decide whether its numbers mean anything, and each gets a test:

  1. SEPARABILITY. Each condition must be able to refuse on its own. An earlier draft folded the three
     identity tests into one flag, which silently turned three conditions into one and would have made
     the per-condition table look authoritative while being wrong.
  2. THE PROVIDER TEST IS A SUBSTRING MATCH ON A NAME. `strategy-observer:dexscreener` passes and
     `strategy-observer:geckoterminal` does not, on identical pool data. If that ever stops being the
     literal behaviour, the round-87 finding is void.
  3. THE POPULATION MUST BE THE CALL-TIME ONE. The gate reads `now - observed_at <= 30 s`; a population
     of "newest row per token in an hour" is dominated by stale quotes (measured p50 1,738 s) and
     inflates every rate.
  4. THE LANE'S OWN COUNTERS. `active`/`waiting` decide whether the lane is idle or capped, and the two
     have opposite fixes.
"""
import importlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

frl = importlib.import_module("free_rider_lane_readout")


def _good(**over):
    """A snapshot that passes every condition, with named overrides."""
    base = dict(
        provider="dexscreener", price=1.0, liquidity=5000.0, volume=5000.0, buys=10, sells=10,
        created_ms=1_700_000_000_000.0,
        observed_at=datetime.fromtimestamp(1_700_000_060, timezone.utc),
        pair_address_present=True, chain_id_matches=True, base_token_is_token=True,
    )
    base.update(over)
    return frl.gate_checks(**base)


def test_a_good_snapshot_is_refused_by_nothing():
    checks = _good()
    assert [n for n, ok in checks if not ok] == []
    assert frl.first_refusal(checks) is None


@pytest.mark.parametrize("name,override", [
    ("pair_address_present", {"pair_address_present": False}),
    ("chain_id_matches", {"chain_id_matches": False}),
    ("base_token_is_token", {"base_token_is_token": False}),
    ("pool_created_known", {"created_ms": None}),
    ("pool_age_le_900s", {"created_ms": 1_600_000_000_000.0}),
    ("provider_dexscreener", {"provider": "strategy-observer:geckoterminal"}),
    ("price_positive", {"price": 0.0}),
    ("liquidity_ge_floor", {"liquidity": 999.0}),
    ("activity_3tx_or_200usd", {"buys": 1, "sells": 1, "volume": 10.0}),
])
def test_each_condition_can_refuse_on_its_own(name, override):
    """Separability: breaking one input must make that condition the FIRST refusal.

    `pool_created_known` is the one structural coupling: its check is `created_ms is not None`, and
    `pool_age_le_900s` is written as `created_ms is not None and ...`, so an unknown creation time
    fails both -- in the real gate exactly as here. It still refuses FIRST as itself, which is what
    the per-condition counter reports, so the coupling is asserted rather than hidden.
    """
    checks = _good(**override)
    failed = [n for n, ok in checks if not ok]
    assert frl.first_refusal(checks) == name, f"first refusal should be {name}, got {failed}"
    if name == "pool_created_known":
        assert failed == ["pool_created_known", "pool_age_le_900s"]
    else:
        assert failed == [name], f"expected only {name} to fail, got {failed}"


def test_the_provider_test_is_a_substring_match_on_the_name():
    """The finding's load-bearing detail: the SAME data passes or fails on the provider string."""
    good = "strategy-observer:dexscreener"
    bad = "strategy-observer:geckoterminal"
    assert frl.first_refusal(_good(provider=good)) is None
    assert frl.first_refusal(_good(provider=bad)) == "provider_dexscreener"
    assert frl.first_refusal(_good(provider="geckoterminal")) == "provider_dexscreener"
    # ...and case-insensitively, as the module does.
    assert frl.first_refusal(_good(provider="DexScreener")) is None


def test_pool_age_boundary_is_inclusive_at_nine_hundred_seconds():
    created = 1_700_000_000_000.0
    at = lambda secs: datetime.fromtimestamp(created / 1000 + secs, timezone.utc)
    assert frl.first_refusal(_good(created_ms=created, observed_at=at(900))) is None
    assert frl.first_refusal(_good(created_ms=created, observed_at=at(901))) == "pool_age_le_900s"
    assert frl.first_refusal(_good(created_ms=created, observed_at=at(-1))) == "pool_age_le_900s"


def test_lane_summary_flags_an_idle_lane():
    idle = {"enabled": True, "active": 0, "waiting": 0, "counts": {"OFFERED": 39, "ADMITTED": 32},
            "alpha149": {"eligible_batch": 3139, "no_spare": 2980, "selected_extra": 169},
            "recent": [{"windows": {"30": "OBSERVED"}}]}
    out = frl.lane_summary(idle)
    assert out["idle"] is True
    assert out["offered"] == 39 and out["eligible_batch"] == 3139
    assert out["window_results"] == {"30:OBSERVED": 1}
    busy = dict(idle, active=1, waiting=3)
    assert frl.lane_summary(busy)["idle"] is False


def test_reconstruct_on_an_empty_population_does_not_divide_by_zero():
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    out = frl.reconstruct([], ever_held=set(), now=now)
    assert out["population"] == 0
    assert out["pass_rate"] is None
    assert out["accepted"] == 0 and out["provider_only_near_miss"] == 0


def test_reconstruct_excludes_held_tokens_and_stale_quotes():
    now = datetime(2026, 9, 13, 2, 0, tzinfo=timezone.utc)

    def row(token_id, age_seconds, provider="dexscreener"):
        created_ms = (now - timedelta(seconds=age_seconds + 60)).timestamp() * 1000
        raw = {"pair": {
            "pairAddress": "0xpool", "chainId": token_id.split(":", 1)[0],
            "pairCreatedAt": created_ms,
            "baseToken": {"address": token_id.split(":", 1)[1]},
        }}
        return {"token_id": token_id, "observed_at": frl.iso(now - timedelta(seconds=age_seconds)),
                "provider": provider, "price_usd": 1.0, "liquidity_usd": 5000.0,
                "volume_5m_usd": 5000.0, "buys_5m": 9, "sells_5m": 9, "raw_json": json.dumps(raw)}

    rows = [
        row("bsc:0xfresh", 5),
        row("bsc:0xstale", 600),
        row("bsc:0xheld", 5),
    ]
    out = frl.reconstruct(rows, ever_held={"bsc:0xheld"}, now=now, max_age_seconds=45.0)
    assert out["never_held_seen"] == 2          # the held token is not in the population at all
    assert out["population"] == 1               # only the fresh one is call-time eligible
    assert out["accepted"] == 1


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_gate_refuses_more_on_provider_name_than_it_accepts():
    """The round-87 measurement, guarded so a silent change in the gate shows up here.

    It asserts the SHAPE of the finding on the WINDOW population, not on the instantaneous one. That
    choice is load-bearing: the fresh (<=45 s) slice holds ~100 tokens and its provider-only near-miss
    count swings between 0 and 30 from minute to minute, so an assertion there is a coin flip. The
    per-token evaluation over an hour is the stable quantity (measured 725 near-misses against 8
    acceptances).
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    has_kv = c.execute("select count(*) from sqlite_master where type='table' and name='kv'").fetchone()[0]
    if not has_kv:
        pytest.skip("kv table not present")
    recon, status, hourly = frl.fetch(minutes=60.0, max_age_seconds=45.0)
    if hourly is None or hourly["tokens"] == 0:
        pytest.skip("no snapshot population in the window")
    assert hourly["provider_only_near_miss"] >= hourly["accepted"], (
        "the provider-name condition no longer removes more candidates than the gate accepts; the "
        "round-87 conclusion must be re-derived before it is quoted again")
    top = max(hourly["first_refusal"].items(), key=lambda kv: kv[1])[0]
    assert top == "provider_dexscreener"
    lane = frl.lane_summary((status or {}).get("shared_batch148") or {})
    assert lane["additional_http_batches"] == 0, "the free-rider contract changed"
