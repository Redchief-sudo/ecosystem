"""
Data Source Interface for Market Data Providers
"""
import abc
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class DataSourceType(Enum):
    """Types of data sources."""
    MARKET_DATA = "market_data"
    TRADING_SIGNALS = "trading_signals"
    LIQUIDITY_DATA = "liquidity_data"
    PRICE_FEEDS = "price_feeds"

class DataSourceStatus(Enum):
    """Data source operational status."""
    IDLE = "idle"
    ACTIVE = "active"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    HEALTHY = "healthy"

@dataclass
class MarketData:
    """Market data structure."""
    symbol: str
    price: float
    volume_24h: float
    market_cap: float
    price_change_24h: float
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

@dataclass
class TradingSignal:
    """Trading signal structure."""
    symbol: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

class DataSourceBase(abc.ABC):
    """
    Base class for all data sources.

    Data sources provide market data and trading signals to the trading system.
    They are NOT token scanners - they provide data for trading decisions.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        self.config = config or {}
        self.name = self.__class__.__name__
        self.enabled = True
        self.data_source_type = DataSourceType.MARKET_DATA
        self._status = DataSourceStatus.IDLE
        self.last_update_time: Optional[datetime] = None
        self.update_count = 0

    def set_config(self, config: Dict[str, Any]) -> None:
        """Update data source configuration."""
        self.config = {**self.config, **config}

    async def initialize(self) -> None:
        """Initialize data source resources (optional override)."""
        pass

    async def cleanup(self) -> None:
        """Clean up data source resources (optional override)."""
        pass

    @abc.abstractmethod
    async def fetch_market_data(self, symbols: List[str]) -> Dict[str, MarketData]:
        """
        Fetch current market data for given symbols.

        Args:
            symbols: List of trading symbols

        Returns:
            Dict mapping symbols to MarketData objects
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def fetch_trading_signals(self, symbols: List[str]) -> Dict[str, TradingSignal]:
        """
        Fetch trading signals for given symbols.

        Args:
            symbols: List of trading symbols

        Returns:
            Dict mapping symbols to TradingSignal objects
        """
        raise NotImplementedError

    async def get_historical_data(self, symbol: str, timeframe: str = "1d", limit: int = 100) -> List[MarketData]:
        """
        Get historical market data (optional implementation).

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '1m', '1h', '1d')
            limit: Number of data points

        Returns:
            List of historical MarketData objects
        """
        raise NotImplementedError("Historical data not supported by this data source")

    def get_data_source_info(self) -> Dict[str, Any]:
        """Return data source information."""
        return {
            "name": self.name,
            "type": self.data_source_type.value,
            "enabled": self.enabled,
            "status": self._status.value,
            "last_update_time": self.last_update_time.isoformat() if self.last_update_time else None,
            "update_count": self.update_count,
            "config": self.config,
        }

    def __str__(self) -> str:
        return f"{self.name}({self.data_source_type.value})"

    def __repr__(self) -> str:
        return f"<{self.name} type={self.data_source_type.value} status={self._status.value} updates={self.update_count}>"
