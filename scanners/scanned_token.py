from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re


EVM_CHAIN_IDS = {1, 10, 56, 137, 42161, 43114, 8453, 81457}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return _utc_now()


@dataclass(slots=True)
class ScannedToken:
    """Canonical scanned token representation. Raw data only."""

    # ─── Core Identity ───────────────────────────────────────────
    address: str
    symbol: str
    name: str
    chain_id: int

    decimals: int = 18

    # ─── Market Data ─────────────────────────────────────────────
    price: Optional[float] = None
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    volume_24h: float = 0.0
    liquidity_usd: float = 0.0
    market_cap: float = 0.0

    # ─── Raw Indicators ──────────────────────────────────────────
    zscore: float = 0.0
    strength: float = 0.0
    momentum: float = 0.0
    volatility: float = 0.0

    # ─── Routing / Network ───────────────────────────────────────
    chain_name: str = ""
    exchange: str = ""
    pair_address: str = ""

    # ─── Temporal Metadata ───────────────────────────────────────
    first_seen: datetime = field(default_factory=_utc_now)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    # ─── Extras ──────────────────────────────────────────────────
    metadata: Dict[str, Any] = field(default_factory=dict)
    holders: Optional[int] = None
    has_traded: bool = True
    is_blacklisted: bool = False

    # ─── Validation ──────────────────────────────────────────────
    def __post_init__(self):
        self._validate_identity()
        self._validate_address()
        self._normalize_symbol()

    def _validate_identity(self):
        if not isinstance(self.chain_id, int) or self.chain_id <= 0:
            raise ValueError("chain_id must be a positive integer")

        if not self.address or not isinstance(self.address, str):
            raise ValueError("address must be a non-empty string")

        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("symbol must be a non-empty string")

        if not self.name or not isinstance(self.name, str):
            raise ValueError("name must be a non-empty string")

        if not isinstance(self.decimals, int) or self.decimals < 0:
            raise ValueError("decimals must be >= 0")

    def _validate_address(self):
        addr = self.address.strip()

        if self.chain_id in EVM_CHAIN_IDS:
            if not addr.startswith("0x") or len(addr) != 42:
                raise ValueError(f"Invalid EVM address: {addr}")
            try:
                int(addr, 16)
            except ValueError:
                raise ValueError(f"Invalid hex EVM address: {addr}")
        else:
            if len(addr) < 3:
                raise ValueError(f"Invalid non-EVM address: {addr}")

        self.address = addr

    def _normalize_symbol(self):
        sym = self.symbol.strip().upper()
        if len(sym) > 20:
            raise ValueError(f"Symbol too long: {sym}")
        if not re.match(r"^[A-Z0-9._-]+$", sym):
            raise ValueError(f"Invalid symbol format: {sym}")
        self.symbol = sym

    # ─── Dict Compatibility ──────────────────────────────────────
    def get(self, key: str, default=None):
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    # ─── Serialization ───────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "decimals": self.decimals,
            "price": self.price,
            "price_change_5m": self.price_change_5m,
            "price_change_1h": self.price_change_1h,
            "price_change_24h": self.price_change_24h,
            "price_change_7d": self.price_change_7d,
            "volume_24h": self.volume_24h,
            "liquidity_usd": self.liquidity_usd,
            "market_cap": self.market_cap,
            "zscore": self.zscore,
            "strength": self.strength,
            "momentum": self.momentum,
            "volatility": self.volatility,
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "exchange": self.exchange,
            "pair_address": self.pair_address,
            "first_seen": self.first_seen.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "holders": self.holders,
            "has_traded": self.has_traded,
            "is_blacklisted": self.is_blacklisted,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScannedToken":
        if "address" not in data or "chain_id" not in data:
            raise ValueError("address and chain_id are required")

        token = cls(
            address=data["address"],
            symbol=data.get("symbol", "UNKNOWN"),
            name=data.get("name", "Unknown Token"),
            chain_id=int(data["chain_id"]),
            decimals=data.get("decimals", 18),
            price=data.get("price"),
            price_change_5m=data.get("price_change_5m", 0.0),
            price_change_1h=data.get("price_change_1h", 0.0),
            price_change_24h=data.get("price_change_24h", 0.0),
            price_change_7d=data.get("price_change_7d", 0.0),
            volume_24h=data.get("volume_24h", 0.0),
            liquidity_usd=data.get("liquidity_usd", 0.0),
            market_cap=data.get("market_cap", 0.0),
            zscore=data.get("zscore", 0.0),
            strength=data.get("strength", 0.0),
            momentum=data.get("momentum", 0.0),
            volatility=data.get("volatility", 0.0),
            chain_name=data.get("chain_name", ""),
            exchange=data.get("exchange", ""),
            pair_address=data.get("pair_address", ""),
            metadata=dict(data.get("metadata", {})),
            holders=data.get("holders"),
            has_traded=data.get("has_traded", True),
            is_blacklisted=data.get("is_blacklisted", False),
        )

        token.first_seen = _parse_datetime(data.get("first_seen"))
        token.created_at = _parse_datetime(data.get("created_at"))
        token.updated_at = _parse_datetime(data.get("updated_at"))

        return token

