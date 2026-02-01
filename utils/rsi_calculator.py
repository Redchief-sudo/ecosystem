"""
RSI (Relative Strength Index) Calculator
-----------------------------------------
Implements real RSI calculation (14-period standard) for technical analysis.
"""

import logging
from typing import List, Optional
from collections import deque

logger = logging.getLogger(__name__)


class RSICalculator:
    """
    Calculate Relative Strength Index (RSI) for price momentum analysis.
    
    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss
    """
    
    def __init__(self, period: int = 14):
        """
        Initialize RSI calculator.
        
        Args:
            period: Number of periods for RSI calculation (default 14)
        """
        self.period = period
        self.prices = deque(maxlen=period + 1)
        self.gains = deque(maxlen=period)
        self.losses = deque(maxlen=period)
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
    
    def add_price(self, price: float) -> Optional[float]:
        """
        Add a new price point and calculate RSI if enough data.
        
        Args:
            price: Current price
            
        Returns:
            RSI value (0-100) if enough data, None otherwise
        """
        self.prices.append(price)
        
        # Need at least 2 prices to calculate change
        if len(self.prices) < 2:
            return None
        
        # Calculate gain/loss
        change = self.prices[-1] - self.prices[-2]
        gain = change if change > 0 else 0
        loss = abs(change) if change < 0 else 0
        
        self.gains.append(gain)
        self.losses.append(loss)
        
        # Need period points to calculate RSI
        if len(self.gains) < self.period:
            return None
        
        # Calculate average gain and loss
        if len(self.gains) == self.period:
            # Initial calculation (simple average)
            self.avg_gain = sum(self.gains) / self.period
            self.avg_loss = sum(self.losses) / self.period
        else:
            # Subsequent calculations (exponential smoothing)
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
        
        # Avoid division by zero
        if self.avg_loss == 0:
            return 100.0 if self.avg_gain > 0 else 50.0
        
        # Calculate RSI
        rs = self.avg_gain / self.avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        logger.debug(f"RSI calculated: {rsi:.2f} (gain: {self.avg_gain:.4f}, loss: {self.avg_loss:.4f})")
        return rsi
    
    def get_rsi(self) -> Optional[float]:
        """
        Get current RSI value.
        
        Returns:
            Current RSI (0-100) or None if not enough data
        """
        if self.avg_gain is None or self.avg_loss is None:
            return None
        
        if self.avg_loss == 0:
            return 100.0 if self.avg_gain > 0 else 50.0
        
        rs = self.avg_gain / self.avg_loss
        return 100 - (100 / (1 + rs))
    
    def is_overbought(self, threshold: float = 70.0) -> bool:
        """
        Check if price is overbought.
        
        Args:
            threshold: Overbought threshold (default 70)
            
        Returns:
            True if RSI > threshold
        """
        rsi = self.get_rsi()
        return rsi is not None and rsi > threshold
    
    def is_oversold(self, threshold: float = 30.0) -> bool:
        """
        Check if price is oversold.
        
        Args:
            threshold: Oversold threshold (default 30)
            
        Returns:
            True if RSI < threshold
        """
        rsi = self.get_rsi()
        return rsi is not None and rsi < threshold
    
    def reset(self):
        """Reset calculator state."""
        self.prices.clear()
        self.gains.clear()
        self.losses.clear()
        self.avg_gain = None
        self.avg_loss = None


def calculate_rsi_from_prices(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate RSI from a list of prices.
    
    Args:
        prices: List of prices
        period: RSI period (default 14)
        
    Returns:
        RSI value or None if insufficient data
    """
    if len(prices) < period + 1:
        logger.warning(f"Insufficient prices for RSI: {len(prices)} < {period + 1}")
        return None
    
    calculator = RSICalculator(period)
    rsi = None
    
    for price in prices:
        rsi = calculator.add_price(price)
    
    return rsi
