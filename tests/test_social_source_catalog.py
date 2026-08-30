from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[1] / "docs" / "SOCIAL_SOURCE_CATALOG.json"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_social_source_catalog_v3_counts_and_required_entity_ids():
    catalog = load_catalog()
    sources = catalog["sources"]

    assert catalog["catalog_version"] == 3
    assert catalog["catalog_schema"] == "social-source-catalog/v3"
    assert catalog["counts"] == {
        "total": len(sources),
        **Counter(source["platform"] for source in sources),
    }
    assert all(source.get("entity_id") for source in sources)


def test_critical_watch_cadence_is_rotation_only_and_keeps_entities_distinct():
    catalog = load_catalog()
    policy = catalog["watch_cadence_policy"]
    assert policy["max_critical_accounts"] == 4
    assert policy["minimum_exploration_fraction"] == 0.4
    assert policy["minimum_exploration_slots_per_12"] == 5
    critical = [source for source in catalog["sources"] if source.get("watch_cadence") == "critical"]

    assert policy == {
        "purpose": "observation_rotation_priority_only",
        "allowed_values": ["normal", "critical"],
        "max_critical_accounts": 4,
        "minimum_exploration_fraction": 0.4,
        "minimum_exploration_slots_per_12": 5,
        "authority_signal": False,
        "role_signal": False,
        "freshness_override": False,
        "independence_signal": False,
        "decision_eligibility_override": False,
    }
    assert {(source["platform"], source["entity_id"]) for source in critical} == {
        ("x", "donald_trump"),
        ("truth", "donald_trump"),
        ("x", "elon_musk"),
        ("x", "changpeng_zhao"),
    }

    trump = [source for source in catalog["sources"] if source["entity_id"] == "donald_trump"]
    assert {(source["platform"], source["url"]) for source in trump} == {
        ("x", "https://x.com/realDonaldTrump"),
        ("truth", "https://truthsocial.com/@realDonaldTrump"),
    }
    white_house = next(source for source in catalog["sources"] if source["entity_id"] == "white_house")
    assert white_house["entity_id"] != trump[0]["entity_id"]


def test_telegram_catalog_entries_remain_manual_discovery_only():
    catalog = load_catalog()
    expected = catalog["platform_automation_defaults"]["telegram"]
    telegram = [source for source in catalog["sources"] if source["platform"] == "telegram"]

    assert len(telegram) == 2
    assert all(source["automation"] == expected for source in telegram)
