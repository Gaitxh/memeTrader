import json
from pathlib import Path


def test_casebook_is_research_only_and_has_no_outcomes():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "research" / "historical_casebook.json").read_text(encoding="utf-8"))
    assert "Never load as production" in data["purpose"]
    forbidden = set(data["globally_forbidden_decision_fields"])
    assert len(data["cases"]) >= 10
    for case in data["cases"]:
        assert case["case_id"]
        assert case["event_trigger"]
        assert case["test_questions"]
        assert not forbidden.intersection(case)


def test_resident_runtime_does_not_import_casebook():
    root = Path(__file__).resolve().parents[1]
    for path in (root / "src" / "memetrader").glob("*.py"):
        assert "historical_casebook.json" not in path.read_text(encoding="utf-8").lower()
