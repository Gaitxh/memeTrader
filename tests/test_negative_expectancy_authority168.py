import importlib.util
import json
from pathlib import Path

from memetrader.store import Store


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sync_negative_expectancy_authority",
    ROOT / "scripts" / "sync_negative_expectancy_authority.py",
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_summary_requires_independent_sample_loss_and_robust_negative_interval():
    result = sync.summarize_arm(
        "bad", [-8.0] * 30, min_tokens=30, min_total_loss_usd=200,
        confidence=0.99, iterations=500,
    )
    assert result is not None
    assert result["independent_token_count"] == 30
    assert result["cluster_bootstrap_interval_usd"] == [-8.0, -8.0]
    assert sync.summarize_arm(
        "too-few", [-8.0] * 29, min_tokens=30, min_total_loss_usd=200,
        confidence=0.99, iterations=500,
    ) is None
    assert sync.summarize_arm(
        "too-small", [-1.0] * 30, min_tokens=30, min_total_loss_usd=200,
        confidence=0.99, iterations=500,
    ) is None


def test_merge_is_latched_and_idempotent():
    authority = {"count": 1, "arms": [{"arm_id": "old"}]}
    candidates = [{"arm_id": "old"}, {"arm_id": "new", "realized_pnl_usd": -300.0}]
    updated, added = sync.merge_candidates(authority, candidates)
    assert [item["arm_id"] for item in added] == ["new"]
    assert updated["count"] == 2
    again, second = sync.merge_candidates(updated, candidates)
    assert second == [] and again == updated


def test_negative_expectancy_source_pauses_entry_but_keeps_evidence(tmp_path):
    store = Store(tmp_path / "expectancy.sqlite3", initial_cash_usd=1000)
    try:
        authority = store.path.parent / "authority"
        authority.mkdir(exist_ok=True)
        evidence = {
            "arm_id": "losing-arm",
            "independent_token_count": 40,
            "realized_pnl_usd": -400.0,
            "open_position_count": 2,
            "reason": "robust forward loss",
        }
        (authority / "negative_expectancy_arms_r168.json").write_text(
            json.dumps({"arms": [evidence]}), encoding="utf-8",
        )
        assert store.register_chain_meme_loss_retirements() == 1
        record = store.get_kv(
            f"chain-meme-account-loss-retirement/v1:{store.CHAIN_MEME_TRADER_ACTIVE_VERSION}",
        )
        state = record["arms"]["losing-arm"]
        assert state["state"] == "FAILED_FORWARD_EXPECTANCY"
        assert state["open_position_count"] == 2
        assert state["reason"] == "robust forward loss"
        assert state["source"] == "data/authority/negative_expectancy_arms_r168.json"
    finally:
        store.close()
