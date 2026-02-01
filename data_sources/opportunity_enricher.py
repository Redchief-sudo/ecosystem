"""
Opportunity Enricher
-------------------
Enriches trade opportunities with historical market data and calculated technical indicators.
Ensures opportunities have complete, accurate data before reaching the entry manager.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from core.models import TradeOpportunity
from utils.rsi_calculator import RSICalculator
from utils.macd_calculator import MACDCalculator

logger = logging.getLogger(__name__)


class OpportunityEnricher:
    """
    Enriches trade opportunities with:
    - Historical price/volume data (30+ data points)
    - Calculated technical indicators (RSI, MACD, Bollinger Bands)
    - Order book data when available
    - Social/sentiment signals
    """

    def __init__(self, data_manager=None, config: Optional[Dict] = None):
        """
        Initialize enricher.
        
        Args:
            data_manager: Data manager for fetching historical data
            config: Configuration dict
        """
        self.data_manager = data_manager
        self.config = config or {}
        self.cache = {}  # Simple cache for data requests
        self.cache_ttl = self.config.get("cache_ttl_seconds", 60)

    async def enrich(self, opportunity: TradeOpportunity) -> TradeOpportunity:
        """
        Enrich a trade opportunity with market data and indicators.
        
        Args:
            opportunity: Original opportunity
            
        Returns:
            Enriched opportunity with complete data
        """
        try:
            token_address = opportunity.token_address or opportunity.token.address
            chain = opportunity.chain

            # Fetch historical data
            price_history, volume_history = await self._fetch_historical_data(
                token_address, chain, lookback_periods=100
            )

            # If we don't have enough history, log warning but continue
            if len(price_history) < 2:
                logger.warning(
                    f"⚠️  Insufficient historical data for {opportunity.token.symbol} "
                    f"on {chain}: only {len(price_history)} data points. "
                    f"Using current price as single point."
                )
                price_history = [float(opportunity.market_data.price)]
                volume_history = [float(opportunity.market_data.volume_24h)]

            # Calculate technical indicators
            rsi = self._calculate_rsi(price_history)
            macd, signal, histogram = self._calculate_macd(price_history)
            bollinger_bands = self._calculate_bollinger_bands(price_history)
            volume_profile = self._calculate_volume_profile(volume_history)

            # Enrich opportunity metadata
            if opportunity.metadata is None:
                opportunity.metadata = {}

            opportunity.metadata.update({
                "price_history": price_history,
                "volume_history": volume_history,
                "price_history_length": len(price_history),
                "technical_indicators": {
                    "rsi": rsi,
                    "macd": macd,
                    "signal_line": signal,
                    "histogram": histogram,
                    "bollinger_upper": bollinger_bands.get("upper", None),
                    "bollinger_lower": bollinger_bands.get("lower", None),
                    "bollinger_middle": bollinger_bands.get("middle", None),
                    "bollinger_position": bollinger_bands.get("position", 0.5),
                },
                "volume_profile": volume_profile,
                "data_enriched": True,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
                "data_quality": self._assess_data_quality(price_history, volume_history),
            })

            logger.info(
                f"✅ Enriched opportunity: {opportunity.token.symbol} on {chain} "
                f"with {len(price_history)} price points, RSI={rsi:.1f}, MACD={macd:.4f}"
            )

            return opportunity

        except Exception as e:
            logger.error(f"❌ Failed to enrich opportunity: {e}", exc_info=True)
            # Return original opportunity if enrichment fails
            return opportunity

    async def _fetch_historical_data(
        self,
        token_address: str,
        chain: str,
        lookback_periods: int = 100,
    ) -> Tuple[List[float], List[float]]:
        """
        Fetch historical price and volume data from DataManager.
        
        DataManager stores token snapshots updated by scanners and market data sources.
        Each snapshot contains price, volume_24h, liquidity, and other market metrics.
        
        Args:
            token_address: Token contract address
            chain: Blockchain name
            lookback_periods: Number of periods to fetch (default 100)
            
        Returns:
            Tuple of (price_history, volume_history) lists, ordered oldest to newest
        """
        try:
            if not self.data_manager:
                logger.warning("No DataManager available, returning empty history")
                return [], []
            
            # Fetch historical snapshots from database
            snapshots = self.data_manager.get_price_history(
                token_address=token_address,
                chain=chain,
                limit=lookback_periods
            )
            
            if not snapshots:
                logger.debug(f"No historical data found for {token_address} on {chain}")
                return [], []
            
            # Extract prices and volumes from snapshots
            price_history = []
            volume_history = []
            
            for snapshot in snapshots:
                if snapshot.get('price') is not None:
                    price_history.append(float(snapshot['price']))
                
                if snapshot.get('volume_24h') is not None:
                    volume_history.append(float(snapshot['volume_24h']))
            
            logger.debug(
                f"Retrieved {len(price_history)} price points, {len(volume_history)} volume points "
                f"for {token_address} on {chain}"
            )
            
            return price_history, volume_history

        except Exception as e:
            logger.warning(f"Failed to fetch historical data for {token_address}: {e}")
            return [], []

    def _calculate_rsi(self, prices: List[float]) -> float:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            prices: List of prices (oldest to newest)
            
        Returns:
            RSI value (0-100)
        """
        if len(prices) < 15:  # Need at least 14 + 1 for calculation
            logger.debug(f"Insufficient data for RSI: {len(prices)} prices")
            return 50.0  # Neutral RSI

        try:
            calculator = RSICalculator(period=14)
            rsi = None

            for price in prices:
                rsi = calculator.add_price(price)

            if rsi is not None:
                logger.debug(f"Calculated RSI: {rsi:.2f}")
                return rsi

            return 50.0  # Neutral if calculation fails

        except Exception as e:
            logger.warning(f"RSI calculation failed: {e}")
            return 50.0

    def _calculate_macd(
        self, prices: List[float]
    ) -> Tuple[float, float, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: List of prices (oldest to newest)
            
        Returns:
            Tuple of (MACD, Signal Line, Histogram)
        """
        if len(prices) < 35:  # Need 26 + 9 for MACD
            logger.debug(f"Insufficient data for MACD: {len(prices)} prices")
            return 0.0, 0.0, 0.0

        try:
            from utils.macd_calculator import MACDCalculator

            calculator = MACDCalculator(fast_period=12, slow_period=26, signal_period=9)

            for price in prices:
                calculator.add_price(price)

            macd, signal, histogram = calculator.get_macd()

            if macd is not None:
                logger.debug(f"Calculated MACD: {macd:.6f}, Signal: {signal:.6f}, Histogram: {histogram:.6f}")
                return macd or 0.0, signal or 0.0, histogram or 0.0

            return 0.0, 0.0, 0.0

        except Exception as e:
            logger.warning(f"MACD calculation failed: {e}")
            return 0.0, 0.0, 0.0

    def _calculate_bollinger_bands(
        self, prices: List[float], period: int = 20, std_dev: float = 2.0
    ) -> Dict[str, float]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: List of prices (oldest to newest)
            period: Period for moving average (default 20)
            std_dev: Number of standard deviations (default 2)
            
        Returns:
            Dict with upper, lower, middle, and position (0-1)
        """
        if len(prices) < period:
            logger.debug(f"Insufficient data for Bollinger Bands: {len(prices)} < {period}")
            return {
                "upper": None,
                "lower": None,
                "middle": None,
                "position": 0.5,  # Neutral position
            }

        try:
            import numpy as np

            prices_array = np.array(prices[-period:])  # Use last 'period' prices
            middle = float(np.mean(prices_array))
            std = float(np.std(prices_array))

            upper = middle + (std * std_dev)
            lower = middle - (std * std_dev)

            # Calculate position (0 = at lower band, 1 = at upper band, 0.5 = at middle)
            current_price = prices[-1]
            if upper == lower:
                position = 0.5
            else:
                position = (current_price - lower) / (upper - lower)
                position = max(0.0, min(1.0, position))  # Clamp to 0-1

            logger.debug(
                f"Calculated Bollinger Bands: upper={upper:.2f}, middle={middle:.2f}, "
                f"lower={lower:.2f}, position={position:.2f}"
            )

            return {
                "upper": upper,
                "lower": lower,
                "middle": middle,
                "position": position,
            }

        except Exception as e:
            logger.warning(f"Bollinger Bands calculation failed: {e}")
            return {
                "upper": None,
                "lower": None,
                "middle": None,
                "position": 0.5,
            }

    def _calculate_volume_profile(self, volumes: List[float]) -> float:
        """
        Calculate volume profile strength (0-1).
        
        Args:
            volumes: List of volumes (oldest to newest)
            
        Returns:
            Volume profile score (0-1) where 1 = strong increasing volume
        """
        if len(volumes) < 2:
            return 0.5  # Neutral

        try:
            import numpy as np

            volumes_array = np.array(volumes)
            
            # Check if volume is trending up
            if len(volumes_array) >= 3:
                recent_avg = np.mean(volumes_array[-3:])
                older_avg = np.mean(volumes_array[:-3]) if len(volumes_array) > 3 else volumes_array[0]
                
                if older_avg == 0:
                    return 0.5
                
                volume_change = (recent_avg - older_avg) / older_avg
                # Clamp to -1 to +1 range, then normalize to 0-1
                volume_profile = 0.5 + (min(1.0, max(-1.0, volume_change)) / 2.0)
            else:
                volume_profile = 0.5  # Not enough data

            logger.debug(f"Calculated volume profile: {volume_profile:.2f}")
            return volume_profile

        except Exception as e:
            logger.warning(f"Volume profile calculation failed: {e}")
            return 0.5

    def _assess_data_quality(
        self, price_history: List[float], volume_history: List[float]
    ) -> Dict[str, Any]:
        """
        Assess quality of available data.
        
        Args:
            price_history: List of historical prices
            volume_history: List of historical volumes
            
        Returns:
            Data quality assessment dict
        """
        return {
            "price_points": len(price_history),
            "volume_points": len(volume_history),
            "sufficient_for_rsi": len(price_history) >= 15,
            "sufficient_for_macd": len(price_history) >= 35,
            "sufficient_for_bollinger": len(price_history) >= 20,
            "overall_quality": self._rate_data_quality(price_history, volume_history),
        }

    @staticmethod
    def _rate_data_quality(price_history: List[float], volume_history: List[float]) -> str:
        """
        Rate overall data quality.
        
        Returns:
            One of: "excellent", "good", "adequate", "limited"
        """
        price_count = len(price_history)
        volume_count = len(volume_history)

        if price_count >= 100 and volume_count >= 100:
            return "excellent"
        elif price_count >= 50 and volume_count >= 50:
            return "good"
        elif price_count >= 20 and volume_count >= 20:
            return "adequate"
        else:
            return "limited"
