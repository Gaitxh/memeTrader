import asyncio

from memetrader.collectors import DexScreenerClient


def test_official_discovery_cache_matches_observed_serial_cycle():
    class Response:
        def json(self):
            return []

    class Http:
        def __init__(self):
            self.kwargs = None

        async def get(self, *args, **kwargs):
            self.kwargs = kwargs
            return Response()

    async def scenario():
        http = Http()
        await DexScreenerClient(http).discover_surface("token_profiles", {"solana"})
        assert http.kwargs == {"ttl": 30}

    asyncio.run(scenario())
