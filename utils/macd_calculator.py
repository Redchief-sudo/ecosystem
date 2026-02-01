"""
MACD (Moving Average Convergence Divergence) Calculator
------------------------------------------------------
Implements real MACD calculation with signal line and histogram for momentum analysis.
"""

import logging
from typing import List, Optional, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class EMACalculator:
    """Calculate Exponential Moving Average."""
    
    def __init__(self, period: int):
        """
        Initialize EMA calculator.
        
        Args:
            period: EMA period
        """
        self.period = period
        self.multiplier = 2 / (period + 1)
        self.ema: Optional[float] = None
        self.prices = deque(maxlen=period)
    
    def add_price(self, price: float) -> Optional[float]:
        """
        Add price and calculate EMA.
        
        Args:
            price: Current price
            
        Returns:
            EMA value if enough data, None otherwise
        """
        self.prices.append(price)
        
        # Initialize EMA with simple average
        if self.ema is None and len(self.prices) == self.period:
            self.ema = sum(self.prices) / self.period
            return self.ema
        
        # Update EMA
        if self.ema is not None:
            self.ema = (price * self.multiplier) + (self.ema * (1 - self.multiplier))
        
        return self.ema
    
    def get_ema(self) -> Optional[float]:
        """Get current EMA value."""
        return self.ema
    
    def reset(self):
        """Reset calculator."""
        self.ema = None
        self.prices.clear()


class MACDCalculator:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    MACD = 12-period EMA - 26-period EMA
    Signal Line = 9-period EMA of MACD
    Histogram = MACD - Signal Line
    """
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        Initialize MACD calculator.
        
        Args:
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)
        """
        self.fast_ema = EMACalculator(fast_period)
        self.slow_ema = EMACalculator(slow_period)
        self.signal_ema = EMACalculator(signal_period)
        
        self.macd_values = deque(maxlen=signal_period)
        self.macd: Optional[float] = None
        self.signal: Optional[float] = None
        self.histogram: Optional[float] = None
    
    def add_price(self, price: float) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Add price and calculate MACD components.
        
        Args:
            price: Current price
            
        Returns:
            Tuple of (MACD, Signal, Histogram) or (None, None, None) if insufficient data
        """
        # Update EMAs
        fast_ema = self.fast_ema.add_price(price)
        slow_ema = self.slow_ema.add_price(price)
        
        # Calculate MACD line
        if fast_ema is not None and slow_ema is not None:
            self.macd = fast_ema - slow_ema
            self.macd_values.append(self.macd)
            
            # Calculate signal line (EMA of MACD)
            signal = self.signal_ema.add_price(self.macd)
            if signal is not None:
                self.signal = signal
                self.histogram = self.macd - self.signal
        
        return self.macd, self.signal, self.histogram
    
    def get_macd(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Get current MACD values.
        
        Returns:
            Tuple of (MACD, Signal, Histogram)
        """
        return self.macd, self.signal, self.histogram
    
    def is_bullish_crossover(self) -> bool:
        """
        Check if MACD just crossed above signal line (bullish signal).
        
        Returns:
            True if bullish crossover, False otherwise
        """
        if self.macd is None or self.signal is None or len(self.macd_values) < 2:
            return False
        
        # Get previous MACD value
        prev_macd = self.macd_values[-2]
        
        # Bullish crossover: MACD crosses above signal
        return prev_macd <= self.signal and self.macd > self.signal
    
    def is_bearish_crossover(self) -> bool:
        """
        Check if MACD just crossed below signal line (bearish signal).
        
        Returns:
            True if bearish crossover, False otherwise
        """
        if self.macd is None or self.signal is None or len(self.macd_values) < 2:
            return False
        
        # Get previous MACD value
        prev_macd = self.macd_values[-2]
        
        # Bearish crossover: MACD crosses below signal
        return prev_macd >= self.signal and self.macd < self.signal
    
    def has_positive_histogram(self) -> bool:
        """
        Check if histogram is positive (MACD above signal).
        
        Returns:
            True if positive, False otherwise
        """
        return self.histogram is not None and self.histogram > 0
    
    def has_negative_histogram(self) -> bool:
        """
        Check if histogram is negative (MACD below signal).
        
        Returns:
            True if negative, False otherwise
        """
        return self.histogram is not None and self.histogram < 0
    
    def reset(self):
        """Reset calculator."""
        self.fast_ema.reset()
        self.slow_ema.reset()
        self.signal_ema.reset()
        self.macd_values.clear()
        self.macd = None
        self.signal = None
        self.histogram = None


def calculate_macd_from_prices(prices: List[float], 
                               fast_period: int = 12, 
                               slow_period: int = 26, 
                               signal_period: int = 9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Calculate MACD from a list of prices.
    
    Args:
        prices: List of prices
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line EMA period
        
    Returns:
        Tuple of (MACD, Signal, Histogram) or (None, None, None) if insufficient data
    """
    if len(prices) < slow_period + signal_period:
        logger.warning(f"Insufficient prices for MACD: {len(prices)} < {slow_period + signal_period}")
        return None, None, None
    
    calculator = MACDCalculator(fast_period, slow_period, signal_period)
    
    for price in prices:
        calculator.add_price(price)
    
    return calculator.get_macd()
