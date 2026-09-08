import asyncio

from memetrader.pons_observer import PonsV2Observer


FACTORY = PonsV2Observer.FACTORY
TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20
DEPLOYER = "0x" + "33" * 20
TX = "0x" + "44" * 32
BLOCK_HASH = "0x" + "55" * 32


def word(value):
    return f"{int(value):064x}"


def topic(address):
    return "0x" + "0" * 24 + address[2:]


def indexed_log(*, event, block, timestamp="2026-09-09T00:00:00.000000Z"):
    if event == "launch":
        return {
            "address": {"hash": FACTORY}, "block_number": block,
            "block_hash": BLOCK_HASH, "transaction_hash": TX, "index": 7,
            "block_timestamp": timestamp,
            "topics": [PonsV2Observer.TOKEN_LAUNCHED_TOPIC, topic(TOKEN), topic(CURVE), topic(DEPLOYER)],
            "data": "0x" + ("0" * 24 + "0" * 40) + word(4) + word(420),
        }
    return {
        "address": {"hash": FACTORY}, "block_number": block,
        "block_hash": BLOCK_HASH, "transaction_hash": TX, "index": 8,
        "block_timestamp": timestamp,
        "topics": [PonsV2Observer.POOL_GRADUATED_TOPIC, topic(TOKEN)],
        "data": "0x" + word(9) + word(100) + word(50),
    }


class Rpc:
    def __init__(self, *, latest, logs=()):
        self.latest = latest
        self.logs = list(logs)
        self.calls = []

    async def _rpc(self, _network, method, _params):
        self.calls.append(method)
        if method == "eth_chainId":
            return hex(4663)
        if method == "eth_blockNumber":
            return hex(self.latest)
        if method == "eth_getLogs":
            return self.logs
        raise AssertionError(method)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class IndexedHttp:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []

    async def get(self, url, *, params, ttl):
        self.calls.append((url, params, ttl))
        if self.error:
            raise self.error
        return Response(self.payload)


def test_pons_v2_indexed_launch_and_graduation_are_identity_only_after_seed():
    async def scenario():
        rpc = Rpc(latest=100)
        http = IndexedHttp({"items": [indexed_log(event="launch", block=100)]})
        observer = PonsV2Observer(rpc, http)
        assert (await observer.observe())["status"] == "SEEDED_NO_WINDOW"
        http.payload = {"items": [indexed_log(event="launch", block=101), indexed_log(event="graduated", block=102)]}
        result = await observer.observe()
        assert result["status"] == "OK"
        assert result["from_block"] == 101 and result["to_block"] == 102
        assert result["tokens"] == [TOKEN.lower()] and result["pools"] == []
        launch, graduated = result["events"]
        assert launch["event"] == "TokenLaunched" and launch["curve"] == CURVE.lower()
        assert launch["pool"] is None and launch["pair_token"] == "0x" + "0" * 40
        assert graduated["event"] == "PoolGraduated"
        assert (graduated["position_id"], graduated["token_amount"], graduated["pair_token_amount"]) == (9, 100, 50)
        assert all(event["source"] == "blockscout_indexed" for event in result["events"])
        assert launch["source_block_timestamp"] == "2026-09-09T00:00:00.000000Z"
        assert result["confirmation_depth"] is None and rpc.calls == []
        assert http.calls[-1] == (observer.INDEXED_LOGS_URL, {"items_count": 50}, 0)

    asyncio.run(scenario())


def test_pons_v2_skips_unknown_factory_events_and_reports_full_page_truncation():
    async def scenario():
        rpc = Rpc(latest=10_000)
        http = IndexedHttp({"items": [indexed_log(event="launch", block=100)]})
        observer = PonsV2Observer(rpc, http)
        await observer.observe()
        unknown = indexed_log(event="launch", block=102)
        unknown["topics"] = ["0x" + "99" * 32]
        http.payload = {"items": [indexed_log(event="launch", block=101), unknown] + [
            indexed_log(event="graduated", block=102) for _ in range(48)
        ]}
        result = await observer.observe()
        assert result["status"] == "TRUNCATED"
        assert result["truncated"] is True and result["indexed_page_limit"] == 50
        assert result["frontier"] == 102 and result["from_block"] == 101
        assert all(event["event"] != "unknown" for event in result["events"])
        assert len(result["events"]) == 49 and rpc.calls == []

    asyncio.run(scenario())


def test_pons_v2_records_bounded_rpc_fallback_when_indexed_endpoint_fails():
    async def scenario():
        rpc = Rpc(latest=100)
        observer = PonsV2Observer(rpc, IndexedHttp(error=RuntimeError("indexed unavailable")))
        first = await observer.observe()
        assert first["status"] == "SEEDED_NO_WINDOW"
        assert observer._frontier is None and observer._rpc_frontier == 97
        rpc.latest = 104
        rpc.logs = [{
            "address": FACTORY, "topics": [PonsV2Observer.TOKEN_LAUNCHED_TOPIC, topic(TOKEN), topic(CURVE), topic(DEPLOYER)],
            "data": "0x" + ("0" * 24 + "0" * 40) + word(0) + word(420),
            "blockNumber": hex(101), "blockHash": BLOCK_HASH,
            "transactionHash": TX, "logIndex": hex(1),
        }]
        result = await observer.observe()
        assert result["status"] == "OK" and result["indexed_source"] == "rpc_fallback"
        assert "bounded direct RPC" in result["indexed_limitation"]
        assert result["events"][0]["event"] == "TokenLaunched"

    asyncio.run(scenario())
