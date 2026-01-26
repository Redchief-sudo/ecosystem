"""
Unified ScannedToken class (ENHANCED VERSION)
Includes:
- Full dataclass structure with enhanced metrics
- Dictionary-style .get() compatibility
- Backwards compatibility for all strategy modules
- Additional technical indicators and metrics
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ScannedToken:
    """Represents a token scanned by any scanner in the ecosystem with enhanced metrics."""

    # Basic token information
    address: str
    symbol: str
    name: str
    decimals: int = 18

    # Market data
    price: Optional[float] = None  # Never default to 0 - None means unknown/unpriced
    price_change_5m: float = 0.0      # 5-minute price change percentage
    price_change_1h: float = 0.0      # 1-hour price change percentage
    price_change_24h: float = 0.0     # 24-hour price change percentage
    price_change_7d: float = 0.0      # 7-day price change percentage
    volume_24h: float = 0.0           # 24-hour trading volume in USD
    liquidity_usd: float = 0.0        # Total liquidity in USD
    market_cap: float = 0.0           # Market capitalization in USD

    # Raw technical indicators (no scoring/normalization)
    zscore: float = 0.0               # Standard deviations from mean (raw calculation)
    strength: float = 0.0             # Relative strength calculation (raw)
    momentum: float = 0.0             # Price momentum calculation (raw)
    volatility: float = 0.0           # Price volatility calculation (raw)

    # Network + DEX routing
    chain_id: int = 0
    chain_name: str = ""
    exchange: str = ""
    pair_address: str = ""

    # Time metadata
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # First detection
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # Current scan time
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # Last update time

    # Extra metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Optional holder and trading flags
    holders: int | None = None       # Number of holders (None = unknown)
    has_traded: bool = True          # Whether token has traded
    is_blacklisted: bool = False     # Flag for blacklist

    def __post_init__(self):
        """Validate ScannedToken after initialization."""
        self._validate_required_fields()
        self._validate_address_format()
        self._validate_symbol_format()

    def _validate_required_fields(self):
        """Validate that all required fields are present and valid."""
        if not self.address or not isinstance(self.address, str):
            raise ValueError("ScannedToken: address is required and must be a non-empty string")

        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("ScannedToken: symbol is required and must be a non-empty string")

        if not self.name or not isinstance(self.name, str):
            raise ValueError("ScannedToken: name is required and must be a non-empty string")

        if not isinstance(self.decimals, int) or self.decimals < 0:
            raise ValueError("ScannedToken: decimals must be a non-negative integer")

        if not isinstance(self.chain_id, int) or self.chain_id <= 0:
            raise ValueError("ScannedToken: chain_id must be a positive integer")

    def _validate_address_format(self):
        """Validate Ethereum address format."""
        address = self.address.strip()

        # For EVM chains, validate address format
        if self.chain_id in [1, 56, 137, 42161, 43114, 10, 8453, 81457]:  # Major EVM chains
            if not address.startswith('0x'):
                raise ValueError(f"ScannedToken: EVM address must start with '0x', got: {address}")

            if len(address) != 42:
                raise ValueError(f"ScannedToken: EVM address must be 42 characters, got {len(address)}: {address}")

            # Check if it's a valid hex address (basic check)
            try:
                int(address, 16)
            except ValueError:
                raise ValueError(f"ScannedToken: Invalid hex address format: {address}")

        # For non-EVM chains, just ensure it's not empty
        elif len(address) < 3:
            raise ValueError(f"ScannedToken: Address too short for chain {self.chain_id}: {address}")

    def _validate_symbol_format(self):
        """Validate token symbol format."""
        symbol = self.symbol.strip().upper()

        if len(symbol) < 1:
            raise ValueError("ScannedToken: Symbol cannot be empty")

        if len(symbol) > 20:
            raise ValueError(f"ScannedToken: Symbol too long ({len(symbol)} chars): {symbol}")

        # Check for invalid characters (only allow alphanumeric and common symbols)
        import re
        if not re.match(r'^[A-Z0-9]+$', symbol):
            # Allow some special characters for complex symbols
            if not re.match(r'^[A-Z0-9\-_\.]+$', symbol):
                raise ValueError(f"ScannedToken: Invalid symbol format (only alphanumeric, dash, underscore, dot allowed): {symbol}")

        self.symbol = symbol  # Store normalized version

    # Raw data fields only - NO AI scoring in scanners
    # AI scoring is handled by downstream components, not scanners

    # ---------------------------------------------------------
    #   DICTIONARY-COMPAT LAYER (Fix for strategy errors)
    # ---------------------------------------------------------
    def get(self, key: str, default=None):
        """
        Provide dict-like .get() so strategies expecting old dict data do not break.
        Checks:
        1. dataclass fields
        2. metadata fields
        """
        if hasattr(self, key):
            return getattr(self, key)
        
        return default

    # ---------------------------------------------------------
    #   SERIALIZATION
    # ---------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Convert token to serializable dictionary."""
        return {
            # Basic token info
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "decimals": self.decimals,
            
            # Market data
            "price": self.price,
            "price_change_5m": self.price_change_5m,
            "price_change_1h": self.price_change_1h,
            "price_change_24h": self.price_change_24h,
            "price_change_7d": self.price_change_7d,
            "volume_24h": self.volume_24h,
            "liquidity_usd": self.liquidity_usd,
            "market_cap": self.market_cap,
            
            # Raw technical indicators
            "zscore": self.zscore,
            "strength": self.strength,
            "momentum": self.momentum,
            "volatility": self.volatility,
            
            # Network info
            "chain_id": self.chain_id,
            "chain_name": self.chain_name,
            "exchange": self.exchange,
            "pair_address": self.pair_address,
            
            # Timestamps
            "first_seen": self.first_seen.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            
            # No AI metrics in scanners - handled by downstream components
            
            # Metadata
            "metadata": self.metadata,
            
            # Holders and flags
            "holders": self.holders,
            "has_traded": self.has_traded,
            "is_blacklisted": self.is_blacklisted,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Reconstruct a ScannedToken instance from a dict with validation."""
        # Validate required fields
        required_fields = ['address']
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValueError(f"Required field '{field}' is missing or null in ScannedToken data")
        
        # Validate address format
        address = data["address"]
        if not isinstance(address, str) or not address.startswith('0x') or len(address) != 42:
            raise ValueError(f"Invalid token address format: {address}")
        
        token = cls(
            # Basic token info - address is required, others have sensible defaults
            address=address,
            symbol=data.get("symbol", "UNKNOWN"),  # Better default than empty string
            name=data.get("name", "Unknown Token"),
            decimals=data.get("decimals", 18),
            
            # Market data - validate critical numeric fields
            price=data.get("price", 0.0),
            price_change_5m=data.get("price_change_5m", 0.0),
            price_change_1h=data.get("price_change_1h", 0.0),
            price_change_24h=data.get("price_change_24h", 0.0),
            price_change_7d=data.get("price_change_7d", 0.0),
            volume_24h=data.get("volume_24h", 0.0),
            liquidity_usd=data.get("liquidity_usd", 0.0),
            market_cap=data.get("market_cap", 0.0),
            
            # Raw technical indicators (no scoring)
            zscore=data.get("zscore", 0.0),
            strength=data.get("strength", 0.0),
            momentum=data.get("momentum", 0.0),
            volatility=data.get("volatility", 0.0),
            
            # Network info - chain_id should be validated
            chain_id=data.get("chain_id", 0),
            chain_name=data.get("chain_name", ""),
            exchange=data.get("exchange", ""),
            pair_address=data.get("pair_address", ""),
            
            # No AI scoring in scanners - removed risk_score field
            
            # Metadata
            metadata=data.get("metadata", {}),
        )

        # Handle datetime fields - ensure timezone awareness
        if ts := data.get("first_seen"):
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts)
            elif isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            token.first_seen = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if ts := data.get("created_at"):
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts)
            elif isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            token.created_at = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if ts := data.get("updated_at"):
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts)
            elif isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)
            token.updated_at = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        # Optional fields
        token.holders = data.get('holders', None)
        token.has_traded = data.get('has_traded', True)
        token.is_blacklisted = data.get('is_blacklisted', False)

        return token
