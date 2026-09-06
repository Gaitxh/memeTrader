import pytest

from memetrader.four_meme_observer import EVENT_TOPICS, TOKEN_MANAGER2, decode_four_meme_log


def word(value):
    return f"{value:064x}"


def addr(value):
    return "00" * 12 + value * 20


def base(event, data):
    return {"event_name": event, "address": TOKEN_MANAGER2,
            "topics": [EVENT_TOPICS[event]], "data": data,
            "blockNumber": "0x10", "blockHash": "0xblock",
            "transactionHash": "0xtx", "logIndex": "0x2"}


def test_token_create_decodes_identity_and_bounded_strings():
    head = [addr("11"), addr("22"), word(7), word(8 * 32), word(9 * 32), word(1_000), word(123), word(456)]
    name, symbol = b"Alpha", b"ALP"
    tail = [word(len(name)), name.hex().ljust(64, "0"), word(len(symbol)), symbol.hex().ljust(64, "0")]
    head[4] = word(10 * 32)
    out = decode_four_meme_log(base("TokenCreate", "0x" + "".join(head + tail)))
    assert out["token"] == "0x" + "22" * 20
    assert out["creator"] == "0x" + "11" * 20
    assert out["name"] == "Alpha" and out["symbol"] == "ALP"
    assert "price" not in out and "pool" not in out


def test_liquidity_added_does_not_invent_pool():
    data = "0x" + "".join([addr("11"), word(20), addr("22"), word(30)])
    out = decode_four_meme_log(base("LiquidityAdded", data))
    assert out["base"] == "0x" + "11" * 20
    assert out["quote"] == "0x" + "22" * 20
    assert "pool" not in out and "liquidity_usd" not in out


def test_wrong_contract_removed_and_bad_string_rejected():
    bad = base("LiquidityAdded", "0x" + "00" * 128)
    bad["address"] = "0x" + "33" * 20
    with pytest.raises(ValueError):
        decode_four_meme_log(bad)
    removed = base("LiquidityAdded", "0x" + "00" * 128)
    removed["removed"] = True
    with pytest.raises(ValueError):
        decode_four_meme_log(removed)


def test_wrong_topic_is_rejected_even_if_event_name_is_supplied():
    item = base("TokenCreate", "0x" + "00" * 8 * 32)
    item["topics"] = ["0x" + "00" * 32]
    with pytest.raises(ValueError):
        decode_four_meme_log(item)
