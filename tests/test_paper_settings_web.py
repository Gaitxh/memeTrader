import json
import sqlite3

import pytest

from memetrader.chain_web import ChainWebData


def make_data(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    database = tmp_path / "x.sqlite3"
    sqlite3.connect(database).close()
    path.write_text(json.dumps({"database": str(database), "other": "keep"}), encoding="utf-8")
    data = object.__new__(ChainWebData)
    data.config_path = path
    data.database = database
    data.config = {"database": str(database), "other": "keep"}
    monkeypatch.setattr(data, "_active_paper_definition", lambda: {
        "slippage_bps": 400, "additional_fee_usd_each_fill": 0.0,
        "min_pool_liquidity_usd": 1000.0,
    })
    return data


def test_paper_settings_save_is_pending_and_preserves_config(tmp_path, monkeypatch):
    data = make_data(tmp_path, monkeypatch)
    before = data.paper_settings()
    data.config_path.write_text(json.dumps({"database": str(data.database), "other": "changed"}), encoding="utf-8")
    result = data.update_paper_settings({
        "buy_slippage_pct": 3.0, "sell_slippage_pct": 5.0,
        "additional_fee_usd_each_fill": 0.25, "min_pool_liquidity_usd": 1200.0,
    })
    assert before["effective"] == result["effective"]
    assert result["configured"]["sell_slippage_pct"] == 5.0
    assert result["restart_required"] is True
    assert json.loads(data.config_path.read_text(encoding="utf-8"))["other"] == "changed"
    assert data.paper_settings()["configured"] == result["configured"]


def test_paper_settings_rejects_bad_values_and_unknown_keys(tmp_path, monkeypatch):
    data = make_data(tmp_path, monkeypatch)
    body = {"buy_slippage_pct": 4, "sell_slippage_pct": 4,
            "additional_fee_usd_each_fill": 0, "min_pool_liquidity_usd": 1000}
    with pytest.raises(ValueError):
        data.update_paper_settings({**body, "unknown": 1})
    with pytest.raises(ValueError):
        data.update_paper_settings({**body, "buy_slippage_pct": 51})
    for invalid in (True, float("nan")):
        with pytest.raises(ValueError):
            data.update_paper_settings({**body, "buy_slippage_pct": invalid})
    assert data.update_paper_settings({**body, "buy_slippage_pct": 0, "sell_slippage_pct": 50})["configured"] == {
        "buy_slippage_pct": 0.0, "sell_slippage_pct": 50.0,
        "additional_fee_usd_each_fill": 0.0, "min_pool_liquidity_usd": 1000.0,
    }


def test_zero_slippage_is_preserved_as_effective_value(tmp_path, monkeypatch):
    data = make_data(tmp_path, monkeypatch)
    monkeypatch.setattr(data, "_active_paper_definition", lambda: {
        "buy_slippage_bps": 0, "sell_slippage_bps": 0,
        "additional_fee_usd_each_fill": 0.0, "min_pool_liquidity_usd": 1000.0,
    })
    effective = data.paper_settings()["effective"]
    assert effective["buy_slippage_pct"] == 0.0
    assert effective["sell_slippage_pct"] == 0.0
