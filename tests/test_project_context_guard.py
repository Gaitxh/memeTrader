from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "codex_project_context_guard.py"
SPEC = spec_from_file_location("codex_project_context_guard", SCRIPT)
assert SPEC and SPEC.loader
GUARD = module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


def test_select_pending_group_ignores_closed_and_uses_newest_release_blocker():
    groups = [
        {"status": "ACKED_RESOLVED", "artifact": "closed.md", "blocks_release": True},
        {"status": "ATTENTION_REQUIRED", "artifact": "older.md", "blocks_release": True, "fact_cutoff_utc": "2026-09-03T01:00:00Z"},
        {"status": "OPEN", "artifact": "newer.md", "blocks_release": True, "fact_cutoff_utc": "2026-09-03T02:00:00Z"},
    ]

    assert GUARD._select_pending_group(groups)["artifact"] == "newer.md"


def test_select_pending_group_prefers_release_blocker():
    groups = [
        {"status": "ATTENTION_REQUIRED", "artifact": "blocking.md", "blocks_release": True, "fact_cutoff_utc": "2026-09-03T01:00:00Z"},
        {"status": "OPEN", "artifact": "newer-nonblocking.md", "blocks_release": False, "fact_cutoff_utc": "2026-09-03T03:00:00Z"},
    ]

    assert GUARD._select_pending_group(groups)["artifact"] == "blocking.md"


def test_select_pending_group_returns_none_when_every_group_is_closed():
    assert GUARD._select_pending_group(
        [{"status": "SUPERSEDED", "artifact": "old.md", "blocks_release": True}]
    ) is None
