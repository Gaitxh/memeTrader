import json

from memetrader.chain_web import ChainWebData


def test_update_history_uses_recorded_time_not_file_tail(tmp_path):
    history = tmp_path / "docs" / "PROJECT_CONTEXT"
    history.mkdir(parents=True)
    entries = [
        {"id": "latest", "recorded_at": "2026-09-16T09:40:00Z"},
        *({"id": str(i), "recorded_at": "2026-09-15T09:40:00Z"}
          for i in range(105)),
    ]
    (history / "SYSTEM_UPDATE_HISTORY.json").write_text(
        json.dumps({"entries": entries}), encoding="utf-8",
    )
    data = ChainWebData.__new__(ChainWebData)
    data.root = tmp_path
    result = data.update_history()["entries"]
    assert len(result) == 100
    assert result[0]["id"] == "latest"
    assert result[1]["id"] == "104"
