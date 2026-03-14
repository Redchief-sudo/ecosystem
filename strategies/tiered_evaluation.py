"""
Tiered Strategy Evaluation
==========================
Multi-tier strategy evaluation based on available historical data.

Tier 1 (5-20 data points): Lightweight signals
- Price velocity
- Volume spike detection
- Liquidity inflow

Tier 2 (20-50 data points): Standard indicators
- RSI
- MACD
- Short-term momentum

Tier 3 (50+ data points): Full evaluation
- Volatility models
- Drawdown control
- Multi-factor confirmation
- AI scoring
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class EvaluationTier(Enum):
    """Strategy evaluation tiers based on data availability."""
    NO_DATA = 0      # < 5 points: Cannot evaluate
    TIER_1 = 1       # 5-20 points: Lightweight signals
    TIER_2 = 2       # 20-50 points: Standard indicators
    TIER_3 = 3       # 50+ points: Full evaluation


class TieredEvaluator:
    """
    Evaluates strategies using tiered approach based on data availability.
    
    This allows strategies to generate signals even with limited historical data,
    while maintaining quality by using appropriate indicators for each tier.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    def get_tier(self, data_point_count: int) -> EvaluationTier:
        """Determine evaluation tier from data point count."""
        if data_point_count < 5:
            return EvaluationTier.NO_DATA
        elif data_point_count < 20:
            return EvaluationTier.TIER_1
        elif data_point_count < 50:
            return EvaluationTier.TIER_2
        else:
            return EvaluationTier.TIER_3
    
    def evaluate_tier_1(
        self,
        market_data: Dict[str, Any],
        price_history: List[float],
        volume_history: List[float]
    ) -> Optional[Dict[str, Any]]:
        """
        Tier 1 evaluation: Lightweight signals for new tokens.
        
        Uses:
        - Price velocity (recent price change)
        - Volume spike detection
        - Liquidity inflow
        """
        if len(price_history) < 5:
            return None
        
        try:
            # Price velocity: (price_now - price_5) / price_5
            price_now = price_history[-1]
            price_5 = price_history[-min(5, len(price_history))]
            price_velocity = (price_now - price_5) / price_5 if price_5 > 0 else 0.0
            
            # Volume spike: current volume vs recent average
            if len(volume_history) >= 5:
                volume_now = volume_history[-1]
                volume_avg = sum(volume_history[-5:]) / len(volume_history[-5:])
                volume_spike = (volume_now - volume_avg) / volume_avg if volume_avg > 0 else 0.0
            else:
                volume_spike = 0.0
            
            # Liquidity check
            liquidity = market_data.get("liquidity_usd", 0)
            min_liquidity = self.config.get("tier_1_min_liquidity", 10_000)
            
            if liquidity < min_liquidity:
                return None
            
            # Generate signal if velocity and volume spike are significant
            min_velocity = self.config.get("tier_1_min_velocity", 0.05)  # 5% price change
            min_volume_spike = self.config.get("tier_1_min_volume_spike", 0.5)  # 50% volume increase
            
            if abs(price_velocity) < min_velocity or volume_spike < min_volume_spike:
                return None
            
            # Calculate confidence based on velocity and volume
            confidence = min(0.7, abs(price_velocity) * 5 + min(volume_spike, 2.0) * 0.15)
            direction = "buy" if price_velocity > 0 else "sell"
            
            return {
                "tier": 1,
                "direction": direction,
                "confidence": confidence,
                "price_velocity": price_velocity,
                "volume_spike": volume_spike,
                "indicators_used": ["price_velocity", "volume_spike", "liquidity"],
                "metadata": {
                    "price_now": price_now,
                    "price_5": price_5,
                    "volume_now": volume_now if len(volume_history) >= 5 else 0,
                    "liquidity": liquidity
                }
            }
            
        except Exception as e:
            logger.debug(f"Tier 1 evaluation failed: {e}")
            return None
    
    def evaluate_tier_2(
        self,
        market_data: Dict[str, Any],
        price_history: List[float],
        volume_history: List[float]
    ) -> Optional[Dict[str, Any]]:
        """
        Tier 2 evaluation: Standard indicators.
        
        Uses:
        - RSI (if available)
        - MACD (if available)
        - Short-term momentum
        """
        if len(price_history) < 20:
            return None
        
        try:
            # Use existing indicators from market_data if available
            rsi = market_data.get("rsi")
            macd = market_data.get("macd")
            macd_signal = market_data.get("macd_signal")
            
            # Price momentum
            price_now = price_history[-1]
            price_20 = price_history[-min(20, len(price_history))]
            momentum = (price_now - price_20) / price_20 if price_20 > 0 else 0.0
            
            # Volume trend
            if len(volume_history) >= 20:
                volume_now = volume_history[-1]
                volume_20 = volume_history[-20]
                volume_trend = (volume_now - volume_20) / volume_20 if volume_20 > 0 else 0.0
            else:
                volume_trend = 0.0
            
            # RSI-based signal
            rsi_signal = None
            if rsi is not None:
                if rsi < 30:  # Oversold
                    rsi_signal = "buy"
                elif rsi > 70:  # Overbought
                    rsi_signal = "sell"
            
            # MACD-based signal
            macd_signal_direction = None
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    macd_signal_direction = "buy"
                elif macd < macd_signal:
                    macd_signal_direction = "sell"
            
            # Combine signals
            buy_signals = sum([
                1 if momentum > 0.02 else 0,  # 2% momentum
                1 if rsi_signal == "buy" else 0,
                1 if macd_signal_direction == "buy" else 0,
                1 if volume_trend > 0.2 else 0  # 20% volume increase
            ])
            
            sell_signals = sum([
                1 if momentum < -0.02 else 0,
                1 if rsi_signal == "sell" else 0,
                1 if macd_signal_direction == "sell" else 0,
                1 if volume_trend < -0.2 else 0
            ])
            
            if buy_signals == 0 and sell_signals == 0:
                return None
            
            direction = "buy" if buy_signals > sell_signals else "sell"
            confidence = min(0.8, (max(buy_signals, sell_signals) / 4.0) * 0.8)
            
            return {
                "tier": 2,
                "direction": direction,
                "confidence": confidence,
                "momentum": momentum,
                "rsi": rsi,
                "macd": macd,
                "volume_trend": volume_trend,
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
                "indicators_used": ["momentum", "rsi", "macd", "volume_trend"],
                "metadata": {
                    "price_now": price_now,
                    "price_20": price_20,
                }
            }
            
        except Exception as e:
            logger.debug(f"Tier 2 evaluation failed: {e}")
            return None
    
    def evaluate_tier_3(
        self,
        market_data: Dict[str, Any],
        price_history: List[float],
        volume_history: List[float]
    ) -> Optional[Dict[str, Any]]:
        """
        Tier 3 evaluation: Full evaluation (delegates to standard strategies).
        
        With 50+ data points, all standard strategies can run normally.
        This tier just indicates full data availability.
        """
        # Tier 3 uses full strategy evaluation - no special handling needed
        # Strategies will use all their filters and indicators
        return {
            "tier": 3,
            "full_evaluation": True,
            "data_points": len(price_history),
            "indicators_used": "all"
        }
