import json

from memetrader.store import Store


KEY = "chain-meme-account-loss-retirement/v1"


def test_unreachable_contract_file_pauses_only_named_entry_arms(tmp_path):
    store = Store(tmp_path / "retire.sqlite3", initial_cash_usd=1000)
    try:
        authority = store.path.parent / "authority"
        authority.mkdir(exist_ok=True)
        payload = {
            "definition_version": store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            "rule": "frozen contract is unreachable",
            "arms": [{
                "arm_id": "old-wide-arm",
                "replacement": "corrected-wide-arm",
                "reason": "registered before corrected routing",
            }],
        }
        (authority / "unreachable_arms_r165.json").write_text(
            json.dumps(payload), encoding="utf-8",
        )

        assert store.register_chain_meme_loss_retirements() == 1
        record = store.get_kv(
            f"{KEY}:{store.CHAIN_MEME_TRADER_ACTIVE_VERSION}",
        )
        state = record["arms"]["old-wide-arm"]
        assert state["state"] == "RETIRED_UNREACHABLE_CONTRACT"
        assert state["replacement"] == "corrected-wide-arm"
        assert state["reason"] == "registered before corrected routing"
        assert state["source"] == "data/authority/unreachable_arms_r165.json"
    finally:
        store.close()


def test_missing_unreachable_file_does_not_change_existing_sources(tmp_path):
    store = Store(tmp_path / "retire.sqlite3", initial_cash_usd=1000)
    try:
        authority = store.path.parent / "authority"
        authority.mkdir(exist_ok=True)
        (authority / "failed_arms_r39.json").write_text(json.dumps({
            "rule": "cash below order size",
            "arms": [{"arm_id": "depleted", "cash_usd": 1.0}],
        }), encoding="utf-8")
        assert store.register_chain_meme_loss_retirements() == 1
        record = store.get_kv(
            f"{KEY}:{store.CHAIN_MEME_TRADER_ACTIVE_VERSION}",
        )
        assert set(record["arms"]) == {"depleted"}
        assert record["arms"]["depleted"]["state"] == "FAILED_ACCOUNT_DEPLETED"
    finally:
        store.close()
