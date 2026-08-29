from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_time(value: str | datetime | None) -> datetime:
    if value is None:
        return utcnow()
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"timezone is required: {value!r}")
    return dt.astimezone(UTC)


def iso(value: datetime | None = None) -> str:
    return (value or utcnow()).astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class Observation:
    source: str
    source_kind: str
    title: str
    text: str = ""
    url: str = ""
    author: str = ""
    published_at: datetime | None = None
    observed_at: datetime = field(default_factory=utcnow)
    ingested_at: datetime = field(default_factory=utcnow)
    availability_proof: str = "local_poll"
    role: str = "feature"
    source_item_id: str = ""
    capture_phase: str = "live"
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.published_at is not None:
            self.published_at = parse_time(self.published_at)
        self.observed_at = parse_time(self.observed_at)
        self.ingested_at = parse_time(self.ingested_at)


@dataclass(slots=True)
class EventView:
    id: int
    title: str
    aliases: list[str]
    attention: float
    first_seen_at: datetime
    last_seen_at: datetime
    status: str = "active"


@dataclass(slots=True)
class TokenCandidate:
    chain: str
    address: str
    name: str
    symbol: str = ""
    created_at: datetime | None = None
    first_seen_at: datetime | None = None
    source: str = ""
    url: str = ""
    social_urls: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at is not None:
            self.created_at = parse_time(self.created_at)
        if self.first_seen_at is not None:
            self.first_seen_at = parse_time(self.first_seen_at)

    @property
    def token_id(self) -> str:
        return f"{self.chain.lower()}:{self.address}"

    @property
    def token_key(self) -> str:
        return self.token_id


@dataclass(slots=True)
class TokenSnapshot:
    chain: str
    address: str
    price_usd: float | None
    liquidity_usd: float | None
    market_cap_usd: float | None
    volume_5m_usd: float | None
    buys_5m: int | None
    sells_5m: int | None
    buyers_5m: int | None = None
    holders: int | None = None
    buy_tax_pct: float | None = None
    sell_tax_pct: float | None = None
    honeypot: bool | None = None
    sellable: bool | None = None
    observed_at: datetime = field(default_factory=utcnow)
    provider: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.observed_at = parse_time(self.observed_at)

    @property
    def token_id(self) -> str:
        return f"{self.chain.lower()}:{self.address}"

    @property
    def token_key(self) -> str:
        return self.token_id


@dataclass(slots=True)
class CandidateDecision:
    event_id: int
    token_id: str
    action: str
    score: float
    match_score: float
    canonical_margin: float
    reasons: list[str]
    rejected_reasons: list[str] = field(default_factory=list)
    position_usd: float = 0.0
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.created_at = parse_time(self.created_at)


@dataclass(slots=True)
class Position:
    token_id: str
    event_id: int
    chain: str
    address: str
    symbol: str
    quantity: float
    entry_price: float
    cost_usd: float
    remaining_cost_usd: float
    highest_price: float
    opened_at: datetime
    realized_pnl_usd: float = 0.0
    take_profit_index: int = 0

    def __post_init__(self) -> None:
        self.opened_at = parse_time(self.opened_at)
