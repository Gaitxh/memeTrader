import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("held_flap160", Path(__file__).parents[1]/"scripts/resolve_held_flap160.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def abi(status=4, successor="1234567890123456789012345678901234567890"):
    words = ["0"*64 for _ in range(15)]
    words[0] = f"{status:064x}"
    words[13] = successor.rjust(64, "0")
    return "0x"+"".join(words)


def test_exact_official_migration_state():
    assert module.decode_state(abi()) == "0x1234567890123456789012345678901234567890"


@pytest.mark.parametrize("raw", [abi(1), abi(successor="0"*40), "0x", abi()+"0"*64,
                                   abi(successor="f"*64)])
def test_unknown_not_migration(raw):
    with pytest.raises(ValueError):
        module.decode_state(raw)


def test_binding_requires_open_exact_original_flap_token(tmp_path):
    import sqlite3, json
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE chain_meme_trader_positions(entry_snapshot_id,token_id,status)")
    con.execute("CREATE TABLE token_snapshots(id,raw_json)")
    token = "bsc:0x"+"1"*40
    pair = "0x"+"2"*40
    raw = {"pair": {"pairAddress": pair, "chainId": "bsc", "dexId": "flapsh",
                    "baseToken": {"address": token[4:]}}}
    con.execute("INSERT INTO token_snapshots VALUES(1,?)", (json.dumps(raw),))
    con.execute("INSERT INTO chain_meme_trader_positions VALUES(1,?,'open')", (token,))
    assert module.held_binding(con, token, pair) == [1]
    with pytest.raises(ValueError):
        module.held_binding(con, token, "0x"+"3"*40)
    con.execute("UPDATE chain_meme_trader_positions SET status='closed'")
    with pytest.raises(ValueError):
        module.held_binding(con, token, pair)
