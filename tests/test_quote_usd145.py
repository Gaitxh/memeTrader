from memetrader.collectors import DexScreenerClient


def pair(*, price="1.25", liquidity="5000", quote_address="quote", quote_symbol="USDC"):
    return {
        "chainId": "bsc", "pairAddress": "0xPool", "priceUsd": price,
        "liquidity": {"usd": liquidity},
        "baseToken": {"address": "0xBase", "name": "Fixture", "symbol": "FIX"},
        "quoteToken": {"address": quote_address, "symbol": quote_symbol},
        "txns": {"m5": {"buys": 2, "sells": 1}}, "volume": {"m5": "10"},
    }


def test_exact_quote_usd_audit_preserves_identity_and_accepts_unusual_valid_quote():
    snapshot = DexScreenerClient._snapshot(pair(quote_address="0xWeth", quote_symbol="WETH"))
    audit = snapshot.raw["quote_usd_audit"]
    assert snapshot.price_usd == 1.25 and snapshot.liquidity_usd == 5000.0
    assert audit == {
        "status": "QUOTE_USD_AVAILABLE", "reason": None, "chain": "bsc",
        "base_address": "0xbase", "pool_address": "0xpool", "quote_address": "0xweth",
        "quote_class": "provider_claimed_symbol",
    }


def test_missing_or_nonfinite_usd_is_unknown_without_zero_or_other_pool_fallback():
    missing = DexScreenerClient._snapshot(pair(price=None, liquidity=None))
    audit = missing.raw["quote_usd_audit"]
    assert missing.price_usd is None and missing.liquidity_usd is None
    assert audit["status"] == "QUOTE_USD_UNKNOWN"
    assert audit["reason"] == "missing_or_nonfinite:priceUsd,liquidityUsd"
    assert audit["pool_address"] == "0xpool"

    nonfinite = DexScreenerClient._snapshot(pair(price="NaN", liquidity="Infinity"))
    assert nonfinite.price_usd is None and nonfinite.liquidity_usd is None
    assert nonfinite.raw["quote_usd_audit"]["status"] == "QUOTE_USD_UNKNOWN"

    no_registry = DexScreenerClient._snapshot(pair(quote_address="", quote_symbol=""))
    assert no_registry.raw["quote_usd_audit"]["quote_class"] == "UNKNOWN"
    assert no_registry.raw["quote_usd_audit"]["status"] == "QUOTE_USD_AVAILABLE"
