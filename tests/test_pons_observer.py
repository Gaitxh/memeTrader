import asyncio

from memetrader.four_meme_observer import EVENT_TOPICS, TOKEN_MANAGER2
from memetrader.pons_observer import FourMemeObserver, PonsV1Observer


class RPC:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def _rpc(self, network, method, params):
        self.calls.append((method, params))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def log(*, removed=False):
    words = [1, 2, 3, 4, 5, 6, 7]
    return {"address": "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB",
            "topics": [PonsV1Observer.TOPIC0,
                       "0x" + "00" * 12 + "11" * 20,
                       "0x" + "00" * 12 + "22" * 20,
                       "0x" + "00" * 12 + "33" * 20],
            "data": "0x" + "".join(f"{x:064x}" for x in words), "blockNumber": "0x200",
            "blockHash": "0xblock", "transactionHash": "0xtx", "logIndex": "0x2", "removed": removed}


def four_liquidity_log():
    address = lambda byte: "0" * 24 + byte * 40
    return {
        "address": TOKEN_MANAGER2,
        "topics": [EVENT_TOPICS["LiquidityAdded"]],
        "data": "0x" + address("1") + f"{25:064x}" + address("2") + f"{50:064x}",
        "blockNumber": "0x105",
        "blockHash": "0xfour-block",
        "transactionHash": "0xfour-tx",
        "logIndex": "0x1",
        "removed": False,
    }


def run(coro):
    return asyncio.run(coro)


def test_first_poll_seeds_without_backfill():
    rpc = RPC(["0x1237", "0x100"])
    out = run(PonsV1Observer(rpc).observe())
    assert out["status"] == "SEEDED_NO_WINDOW"
    assert out["events"] == []
    assert [call[0] for call in rpc.calls] == ["eth_chainId", "eth_blockNumber"]


def test_decodes_both_factory_filter_and_event():
    rpc = RPC(["0x1237", "0x200", "0x1237", "0x210", [log()]])
    observer = PonsV1Observer(rpc)
    run(observer.observe())
    out = run(observer.observe())
    assert out["status"] == "OK"
    assert out["events"][0]["version"] == "active"
    assert out["events"][0]["token"] == "0x" + "11" * 20
    assert out["events"][0]["pool"] == "0x" + "00" * 19 + "02"
    assert out["tokens"] == ["0x" + "11" * 20]
    assert out["chain"] == "robinhood"
    assert out["confirmation_depth"] == 3
    assert out["finality"] is False
    assert out["events"][0]["observed_at"] == out["recorded_at"]


def test_rpc_error_does_not_advance_frontier():
    rpc = RPC(["0x1237", "0x200", "0x1237", "0x210", RuntimeError("down"), "0x1237", "0x220", []])
    observer = PonsV1Observer(rpc)
    run(observer.observe())
    failed = run(observer.observe())
    assert failed["status"] == "ERROR"
    frontier = failed["frontier"]
    recovered = run(observer.observe())
    assert recovered["status"] == "OK"
    assert recovered["from_block"] == frontier + 1


def test_removed_log_rejected_without_advance():
    rpc = RPC(["0x1237", "0x200", "0x1237", "0x210", [log(removed=True)], "0x1237", "0x220", []])
    observer = PonsV1Observer(rpc)
    run(observer.observe())
    failed = run(observer.observe())
    assert failed["status"] == "ERROR"
    recovered = run(observer.observe())
    assert recovered["status"] == "OK"
    assert recovered["from_block"] == failed["frontier"] + 1


def test_pons_requires_exactly_four_topics_and_zero_padded_addresses():
    extra = log()
    extra["topics"].append("0x" + "00" * 32)
    rpc = RPC(["0x1237", "0x200", "0x1237", "0x210", [extra]])
    observer = PonsV1Observer(rpc)
    run(observer.observe())
    failed = run(observer.observe())
    assert failed["status"] == "ERROR"
    assert failed["error"] == "pons_v1_topic_invalid"

    unpadded = log()
    unpadded["topics"][1] = "0x" + "01" * 32
    rpc = RPC(["0x1237", "0x200", "0x1237", "0x210", [unpadded]])
    observer = PonsV1Observer(rpc)
    run(observer.observe())
    failed = run(observer.observe())
    assert failed["status"] == "ERROR"
    assert failed["error"] == "pons_v1_topic_address_invalid"


def test_large_frontier_gap_skips_old_blocks_and_reports_gap():
    rpc = RPC(["0x1237", "0x100", "0x1237", "0x300", []])
    observer = PonsV1Observer(rpc)
    run(observer.observe())
    out = run(observer.observe())
    assert out["status"] == "OK"
    assert out["from_block"] == 0x300 - 3 - 99
    assert out["to_block"] == 0x300 - 3
    assert out["skipped_blocks"] == out["from_block"] - (0x100 - 3 + 1)
    request = rpc.calls[-1]
    assert request[0] == "eth_getLogs"
    assert request[1][0]["fromBlock"] == hex(out["from_block"])


def test_four_meme_observer_reuses_bounded_native_event_polling():
    event = four_liquidity_log()
    rpc = RPC(["0x38", "0x100", "0x38", "0x110", [event]])
    observer = FourMemeObserver(rpc)
    seeded = run(observer.observe())
    assert seeded["status"] == "SEEDED_NO_WINDOW"
    out = run(observer.observe())
    assert out["status"] == "OK"
    assert out["chain"] == "bsc"
    assert out["events"][0]["event"] == "LiquidityAdded"
    assert out["events"][0]["token_id"] == "bsc:0x" + "1" * 40
    assert out["pools"] == [{
        "base": "0x" + "1" * 40,
        "quote": "0x" + "2" * 40,
        "source_contract": TOKEN_MANAGER2,
    }]
    assert "price" not in out["events"][0]
    assert "liquidity" not in out["events"][0]
    filter_body = rpc.calls[-1][1][0]
    assert filter_body["address"] == [TOKEN_MANAGER2]
    assert set(filter_body["topics"][0]) == set(EVENT_TOPICS.values())
