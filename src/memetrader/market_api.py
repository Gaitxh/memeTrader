"""Quota-bounded complementary market API clients.

This module does not choose or cross-check providers.  It exposes one queued
CoinGecko Demo pool-batch call and a pure normalizer so Runtime can use the same
shape for already-fetched Gecko payloads without another request.
"""

from __future__ import annotations

import copy
import math
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Mapping


PROVIDER = "coingecko-demo"
HOST = "api.coingecko.com"
BASE_URL = "https://api.coingecko.com/api/v3/onchain"
USAGE_KEY = "market_api:coingecko-demo:usage"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _count(value: Any) -> int | None:
    parsed = _number(value)
    return None if parsed is None else int(parsed)


def _pool_key(address: str) -> str:
    value = str(address or "").strip()
    return value.lower() if value.startswith(("0x", "0X")) else value


def _resource_id_matches(value: Any, network: str, address: str) -> bool:
    resource_id = str(value or "").strip()
    return not resource_id or resource_id == f"{network}_{address}"


def _created_millis(value: Any) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round(_utc(parsed).timestamp() * 1000)


def _related(
    pool: Mapping[str, Any],
    included_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    name: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    relationships = pool.get("relationships")
    relationships = relationships if isinstance(relationships, Mapping) else {}
    relationship = relationships.get(name)
    relationship = relationship if isinstance(relationship, Mapping) else {}
    data = relationship.get("data")
    data = data if isinstance(data, Mapping) else {}
    key = (str(data.get("type") or ""), str(data.get("id") or ""))
    included = included_by_key.get(key) or {}
    return data, included


def normalize_gecko_pool(
    pool: Mapping[str, Any],
    included: list[Any] | tuple[Any, ...],
    network: str,
    observed_at: datetime | str,
    provider: str = PROVIDER,
) -> dict[str, Any] | None:
    """Normalize one CoinGecko on-chain pool into a Dex-shaped pair payload.

    ``observedAt`` is the caller's local receipt time.  Provider update times
    are retained only inside ``raw`` and are never asserted as observation
    time.  Missing chain, pool, base token, quote token, or DEX identity fails
    closed.
    """
    chain = str(network or "").strip()
    provider_name = str(provider or "").strip()
    if not chain or not provider_name or not isinstance(pool, Mapping):
        return None
    if isinstance(observed_at, datetime):
        receipt = _iso(observed_at)
    else:
        try:
            receipt = _iso(datetime.fromisoformat(str(observed_at).replace("Z", "+00:00")))
        except ValueError:
            return None

    included_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in included:
        if isinstance(item, Mapping):
            key = (str(item.get("type") or ""), str(item.get("id") or ""))
            if all(key):
                included_by_key[key] = item

    attrs = pool.get("attributes")
    attrs = attrs if isinstance(attrs, Mapping) else {}
    pool_address = str(attrs.get("address") or "").strip()
    base_relation, base_item = _related(pool, included_by_key, "base_token")
    quote_relation, quote_item = _related(pool, included_by_key, "quote_token")
    dex_relation, dex_item = _related(pool, included_by_key, "dex")
    base_attrs = base_item.get("attributes") if isinstance(base_item, Mapping) else {}
    quote_attrs = quote_item.get("attributes") if isinstance(quote_item, Mapping) else {}
    base_attrs = base_attrs if isinstance(base_attrs, Mapping) else {}
    quote_attrs = quote_attrs if isinstance(quote_attrs, Mapping) else {}
    base_address = str(base_attrs.get("address") or "").strip()
    quote_address = str(quote_attrs.get("address") or "").strip()
    dex_id = str(dex_relation.get("id") or dex_item.get("id") or "").strip()
    if not pool_address or not base_address or not quote_address or not dex_id:
        return None
    if not (
        _resource_id_matches(pool.get("id"), chain, pool_address)
        and _resource_id_matches(base_relation.get("id"), chain, base_address)
        and _resource_id_matches(quote_relation.get("id"), chain, quote_address)
    ):
        return None

    volumes = attrs.get("volume_usd")
    volumes = volumes if isinstance(volumes, Mapping) else {}
    transactions = attrs.get("transactions")
    transactions = transactions if isinstance(transactions, Mapping) else {}
    tx_m5 = transactions.get("m5")
    tx_m5 = tx_m5 if isinstance(tx_m5, Mapping) else {}
    price = attrs.get("base_token_price_usd")
    reserve = attrs.get("reserve_in_usd")
    volume_m5 = volumes.get("m5")

    return {
        "chainId": chain,
        "tokenAddress": base_address,
        "pairAddress": pool_address,
        "baseToken": {
            "address": base_address,
            "name": str(base_attrs.get("name") or ""),
            "symbol": str(base_attrs.get("symbol") or ""),
        },
        "quoteToken": {
            "address": quote_address,
            "name": str(quote_attrs.get("name") or ""),
            "symbol": str(quote_attrs.get("symbol") or ""),
        },
        "dexId": dex_id,
        "priceUsd": str(price) if price is not None else None,
        "liquidity": {"usd": _number(reserve)},
        "volume": {"m5": _number(volume_m5)},
        "txns": {
            "m5": {
                "buys": _count(tx_m5.get("buys")),
                "sells": _count(tx_m5.get("sells")),
            }
        },
        "pairCreatedAt": _created_millis(attrs.get("pool_created_at")),
        "marketCap": _number(attrs.get("market_cap_usd")),
        "fdv": _number(attrs.get("fdv_usd")),
        "url": f"https://www.geckoterminal.com/{urllib.parse.quote(chain, safe='')}/pools/{urllib.parse.quote(pool_address, safe='')}",
        "source": provider_name,
        "provider": provider_name,
        "observedAt": receipt,
        "raw": {"provider": provider_name, "pool": copy.deepcopy(dict(pool))},
    }


class CoinGeckoDemoPoolClient:
    """One-shot CoinGecko Demo multi-pool client with local quota reserves."""

    def __init__(
        self,
        http: Any,
        api_key: str,
        *,
        store: Any | None = None,
        now_fn: Callable[[], datetime] = _utcnow,
        monthly_limit: int = 8_000,
        daily_limit: int = 240,
        cache_ttl_seconds: float = 60.0,
        max_cache_entries: int = 512,
        transport_backoff_seconds: float = 5.0,
    ) -> None:
        self.http = http
        self._api_key = str(api_key or "").strip()
        self.store = store
        self.now_fn = now_fn
        self.monthly_limit = max(0, int(monthly_limit))
        self.daily_limit = max(0, int(daily_limit))
        self.cache_ttl_seconds = max(0.0, min(60.0, float(cache_ttl_seconds)))
        self.max_cache_entries = max(1, int(max_cache_entries))
        self.transport_backoff_seconds = max(0.0, float(transport_backoff_seconds))
        self._local_usage: dict[str, Any] = {}
        self._cache: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}
        self._disabled = False
        self._cooldown_until: datetime | None = None
        self._last_error = ""

    def _now(self) -> datetime:
        return _utc(self.now_fn())

    def _read_usage(self, now: datetime) -> dict[str, Any]:
        raw = self.store.get_kv(USAGE_KEY, {}) if self.store is not None else self._local_usage
        raw = dict(raw) if isinstance(raw, Mapping) else {}
        month, day = now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")
        if str(raw.get("month") or "") != month:
            return {"month": month, "monthly": 0, "day": day, "daily": 0}
        if str(raw.get("day") or "") != day:
            raw.update(day=day, daily=0)
        raw["monthly"] = max(0, int(raw.get("monthly") or 0))
        raw["daily"] = max(0, int(raw.get("daily") or 0))
        return raw

    def _write_usage(self, usage: Mapping[str, Any]) -> None:
        payload = dict(usage)
        if self.store is not None:
            self.store.set_kv(USAGE_KEY, payload)
        else:
            self._local_usage = payload

    def _charge(self, now: datetime) -> None:
        usage = self._read_usage(now)
        usage["monthly"] += 1
        usage["daily"] += 1
        self._write_usage(usage)

    def _availability_reason(self, now: datetime) -> str:
        if not self._api_key:
            return "missing_api_key"
        if self._disabled:
            return "disabled_auth_until_restart"
        if self._cooldown_until is not None and now < self._cooldown_until:
            return "cooldown"
        try:
            usage = self._read_usage(now)
        except Exception:
            return "usage_store_unavailable"
        if usage["monthly"] >= self.monthly_limit:
            return "local_monthly_budget_exhausted"
        if usage["daily"] >= self.daily_limit:
            return "local_daily_budget_exhausted"
        return "available"

    def available(self) -> bool:
        return self._availability_reason(self._now()) == "available"

    def _prune_cache(self, now: datetime) -> None:
        expired = [key for key, (expires_at, _) in self._cache.items() if expires_at <= now]
        for key in expired:
            self._cache.pop(key, None)
        overflow = len(self._cache) - self.max_cache_entries
        if overflow > 0:
            for key, _ in sorted(self._cache.items(), key=lambda item: item[1][0])[:overflow]:
                self._cache.pop(key, None)

    def status(self) -> dict[str, Any]:
        now = self._now()
        try:
            usage = self._read_usage(now)
            monthly, daily = usage["monthly"], usage["daily"]
        except Exception:
            monthly = daily = None
        self._prune_cache(now)
        return {
            "provider": PROVIDER,
            "available": self._availability_reason(now) == "available",
            "availability_reason": self._availability_reason(now),
            "local_usage_only": True,
            "local_daily_used": daily,
            "local_monthly_used": monthly,
            "remaining_local_daily": None if daily is None else max(0, self.daily_limit - daily),
            "remaining_local_monthly": None if monthly is None else max(0, self.monthly_limit - monthly),
            "daily_limit": self.daily_limit,
            "monthly_limit": self.monthly_limit,
            "cooldown_until": _iso(self._cooldown_until) if self._cooldown_until else None,
            "disabled_until_restart": self._disabled,
            "last_error": self._last_error or None,
            "cache_count": len(self._cache),
        }

    @staticmethod
    def _retry_after_seconds(value: Any, now: datetime) -> float:
        raw = str(value or "").strip()
        try:
            return max(1.0, float(raw))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
            except (TypeError, ValueError, OverflowError):
                return 60.0
            return max(1.0, (_utc(parsed) - now).total_seconds())

    async def get_pools(
        self,
        network: str,
        addresses: list[str] | tuple[str, ...],
    ) -> dict[str, dict[str, Any]]:
        chain = str(network or "").strip()
        requested_by_key: dict[str, str] = {}
        for value in addresses:
            address = str(value).strip()
            if address:
                requested_by_key.setdefault(_pool_key(address), address)
        unique = list(requested_by_key.values())
        if not chain:
            raise ValueError("network_required")
        if len(unique) > 30:
            raise ValueError("coingecko_pool_batch_max_30")
        if not unique:
            return {}

        now = self._now()
        self._prune_cache(now)
        result: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        for address in unique:
            cached = self._cache.get((chain, _pool_key(address)))
            if cached is None:
                missing.append(address)
            else:
                result[address] = copy.deepcopy(cached[1])
        if not missing or self._availability_reason(now) != "available":
            return result

        joined = urllib.parse.quote(",".join(missing), safe=",")
        quoted_network = urllib.parse.quote(chain, safe="")
        url = f"{BASE_URL}/networks/{quoted_network}/pools/multi/{joined}"
        try:
            await self.http._reserve_host_request_start(HOST)
            request_now = self._now()
            if self._availability_reason(request_now) != "available":
                return result
            self._charge(request_now)
            response = await self.http.client.get(
                url,
                params={"include": "base_token,quote_token,dex"},
                headers={"x-cg-demo-api-key": self._api_key},
                follow_redirects=False,
            )
        except Exception:
            self._last_error = "transport_failure"
            self._cooldown_until = self._now() + timedelta(seconds=self.transport_backoff_seconds)
            return result

        received_at = self._now()
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code == 429:
            headers = getattr(response, "headers", {}) or {}
            delay = self._retry_after_seconds(headers.get("Retry-After"), received_at)
            self._cooldown_until = received_at + timedelta(seconds=delay)
            self._last_error = "rate_limited"
            return result
        if status_code in {401, 403}:
            self._disabled = True
            self._last_error = "authentication_rejected"
            return result
        if status_code != 200:
            self._last_error = f"http_{status_code or 'error'}"
            return result
        try:
            payload = response.json()
        except Exception:
            self._last_error = "invalid_json"
            return result
        if not isinstance(payload, Mapping):
            self._last_error = "invalid_payload"
            return result
        data = payload.get("data")
        included = payload.get("included")
        data = data if isinstance(data, list) else []
        included = included if isinstance(included, list) else []
        requested = {_pool_key(address): address for address in missing}
        for pool in data:
            normalized = normalize_gecko_pool(pool, included, chain, received_at)
            if normalized is None:
                continue
            address = str(normalized["pairAddress"])
            address_key = _pool_key(address)
            if address_key not in requested:
                continue
            requested_address = requested[address_key]
            self._cache[(chain, address_key)] = (
                received_at + timedelta(seconds=self.cache_ttl_seconds),
                copy.deepcopy(normalized),
            )
            result[requested_address] = normalized
        self._prune_cache(received_at)
        self._last_error = ""
        return result


__all__ = ["CoinGeckoDemoPoolClient", "normalize_gecko_pool"]
