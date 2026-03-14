# trade_strategies/elite_aggressive_strategy.py
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set

import numpy as np

from ..base_strategy import BaseStrategy, SignalType, TradeSignal, RiskProfile
from core.numeric_constants import get_numeric_constants

logger = logging.getLogger("strategies.elite_aggressive")

class EliteAggressiveStrategy(BaseStrategy):
    """
    Elite aggressive strategy designed for high-risk, high-reward opportunities.
    
    Features:
    - Momentum surge detection
    - Volatility expansion trading
    - Early trend capture
    - Explosive volume detection
    - Rapid scalping opportunities
    - Dynamic leverage simulation
    - Aggressive pyramid positioning
    """
    IS_STRATEGY = True
    STRATEGY_NAME = "aggressive"

    # ------------------------------------------------------------------
    # REQUIRED ABSTRACT PROPERTIES
    # ------------------------------------------------------------------

    @property
    def strategy_id(self) -> str:
        return "elite_aggressive_v1"

    @property
    def description(self) -> str:
        return "High-risk, high-reward aggressive strategy focusing on momentum surges, volatility expansion, and early trend capture."

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def risk_profile(self) -> RiskProfile:
        return RiskProfile(
            max_drawdown=0.20,
            max_concurrent_positions=3,
            volatility_tolerance=3.0,
            min_confidence_threshold=0.35,
            max_position_size=0.005,
            max_loss_per_trade=0.02,
            risk_per_trade=0.01
        )

    @property
    def signal_type(self) -> SignalType:
        return SignalType.BUY

    @property
    def required_features(self) -> Set[str]:
        return {"price", "volume_24h", "volatility", "price_change_24h", "high_24h", "low_24h"}

    @property
    def supported_markets(self) -> List[str]:
        return ["crypto"]

    @property
    def timeframes(self) -> List[str]:
        return ["1m", "5m", "15m"]

    @property
    def warmup_period(self) -> int:
        return 20

    # ------------------------------------------------------------------
    # EVALUATION METHOD (required by BaseStrategy)
    # ------------------------------------------------------------------

    async def evaluate(self, market_state: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Core evaluation method - wraps evaluate_token for backward compatibility.
        """
        return await self.evaluate_token(market_state)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Momentum tracking
        self.price_history = {}  # symbol -> deque of prices
        self.volume_history = {}  # symbol -> deque of volumes
        self.momentum_scores = {}  # symbol -> momentum score
        
        # Volatility tracking
        self.volatility_expanding = {}  # symbol -> bool
        self.volatility_history = {}  # symbol -> deque of volatility
        
        # Hot streak tracking
        self.hot_symbols = set()
        self.symbol_momentum_streak = {}
        
        # Aggressive opportunity detection
        self.surge_threshold = 3.0  # 3x normal volume = surge
        self.momentum_threshold = 2.0  # 2x momentum = strong
        
        logger.info("🔥 Elite Aggressive Strategy initialized - HIGH RISK MODE")
    
    def _fuse_confidence(self, *scores, weights=None) -> float:
        """Fuse multiple scores into a confidence value."""
        if not scores:
            return 0.0
        
        if weights is None:
            weights = [1.0] * len(scores)
        
        if len(weights) != len(scores):
            weights = [1.0] * len(scores)
        
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)
        
        if total_weight == 0:
            return 0.0
            
        return min(1.0, max(0.0, weighted_sum / total_weight))

    async def evaluate_token(self, opportunity):
        try:
            c = self.strategy_config
            if not c:
                logger.error("[EliteAggressive] No configuration found")
                return None
            
            symbol = opportunity.get("symbol", "UNKNOWN")
            price = self._safe(opportunity, "price")
            vol = self._safe(opportunity, "volume_24h")
            volatility = self._safe(opportunity, "volatility", 0.5)
            price_change = self._safe(opportunity, "price_change_24h", 0)
            high_24h = self._safe(opportunity, "high_24h", price)
            low_24h = self._safe(opportunity, "low_24h", price)
            
            if not all([price, vol]):
                return None
            
            # === 1. MOMENTUM SURGE DETECTION ===
            momentum_score = self._detect_momentum_surge(symbol, price, price_change)
            if momentum_score < 0.5:
                return None
            
            # === 2. VOLUME EXPLOSION CHECK ===
            volume_explosion = self._detect_volume_explosion(symbol, vol)
            if volume_explosion < 0.4:
                return None
            
            # === 3. VOLATILITY EXPANSION DETECTION ===
            vol_expansion = self._detect_volatility_expansion(symbol, volatility)
            
            # === 4. TREND STRENGTH ASSESSMENT ===
            trend_strength = self._assess_trend_strength(
                price, high_24h, low_24h, price_change
            )
            
            # === 5. HOT SYMBOL BONUS ===
            is_hot = symbol in self.hot_symbols
            hot_bonus = 1.3 if is_hot else 1.0
            
            # === 6. EARLY ENTRY DETECTION ===
            early_entry_score = self._detect_early_entry_opportunity(
                symbol, price, vol, momentum_score
            )
            
            # === 7. AGGRESSIVE CONFLUENCE SCORING ===
            confluence = self._calculate_aggressive_confluence(
                momentum_score, volume_explosion, vol_expansion,
                trend_strength, early_entry_score
            )
            
            # Apply minimum thresholds
            min_vol = c.get("min_volume_24h", c.get("min_volume", 1500))
            if vol < min_vol:
                return None
            
            # === 8. CALCULATE AGGRESSIVE CONFIDENCE ===
            base_confidence = self._fuse_confidence(
                momentum_score,
                volume_explosion,
                trend_strength,
                early_entry_score,
                weights=[0.35, 0.30, 0.20, 0.15]
            )
            
            # Boost confidence with confluence and hot bonus
            confidence = min(base_confidence * (1 + confluence * 0.3) * hot_bonus, 0.98)
            
            # Aggressive minimum confidence (lower than conservative strategies)
            min_confidence = c.get("min_confidence", 0.35)
            if confidence < min_confidence:
                logger.debug(f"[EliteAggressive] {symbol}: Confidence {confidence:.2f} below {min_confidence}")
                return None
            
            # === 9. AGGRESSIVE POSITION SIZING ===
            risk_factor = c.get("risk_factor", 2.0)
            position_size = self._aggressive_position_sizing(
                confidence, volatility, momentum_score, risk_factor
            )
            
            # === 10. AGGRESSIVE RISK MANAGEMENT ===
            stop_loss_pct, take_profit_pct = self._aggressive_risk_targets(
                confidence, volatility, momentum_score, trend_strength
            )
            
            stop_loss = price * (1 - stop_loss_pct)
            take_profit = price * (1 + take_profit_pct)
            
            # === 11. UPDATE HOT SYMBOLS ===
            self._update_hot_symbols(symbol, confidence, momentum_score)
            
            # Build metadata
            metadata = {
                "strategy": "elite_aggressive",
                "momentum_score": round(momentum_score, 3),
                "volume_explosion": round(volume_explosion, 3),
                "volatility_expansion": round(vol_expansion, 3),
                "trend_strength": round(trend_strength, 3),
                "confluence": round(confluence, 3),
                "early_entry": round(early_entry_score, 3),
                "is_hot_symbol": is_hot,
                "risk_factor": risk_factor,
                "sl_pct": round(stop_loss_pct * 100, 2),
                "tp_pct": round(take_profit_pct * 100, 2)
            }
            
            logger.info(
                f"🔥 [EliteAggressive] {symbol} FIRE | "
                f"Conf: {confidence:.2f} | Mom: {momentum_score:.2f} | "
                f"VolExp: {volume_explosion:.2f} | Size: {position_size:.4f}"
            )
            
            return self._create_signal(
                SignalType.BUY,
                confidence,
                price,
                position_size,
                stop_loss,
                take_profit,
                metadata
            )

        except Exception as e:
            logger.error(f"[EliteAggressive] Error: {e}", exc_info=True)
            return None

    def _detect_momentum_surge(self, symbol: str, price: float, price_change: float) -> float:
        """Detect explosive momentum surges."""
        try:
            # Initialize history
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=20)
            
            history = self.price_history[symbol]
            history.append(price)
            
            if len(history) < 3:
                return 0.5
            
            # Calculate momentum metrics
            prices = list(history)
            
            # Recent acceleration (last 3 vs previous)
            if len(prices) >= 6:
                recent_avg = np.mean(prices[-3:])
                previous_avg = np.mean(prices[-6:-3])
                acceleration = (recent_avg - previous_avg) / previous_avg if previous_avg > 0 else 0
            else:
                acceleration = 0
            
            # Price velocity
            velocity = abs(price_change) / 100
            
            # Momentum strength
            momentum = self._normalize(velocity + abs(acceleration) * 10, 0.02, 0.15)
            
            # Store momentum score
            self.momentum_scores[symbol] = momentum
            
            return momentum
            
        except Exception as e:
            logger.debug(f"Momentum detection error: {e}")
            return 0.5

    def _detect_volume_explosion(self, symbol: str, volume: float) -> float:
        """Detect explosive volume increases."""
        try:
            if symbol not in self.volume_history:
                self.volume_history[symbol] = deque(maxlen=20)
            
            history = self.volume_history[symbol]
            history.append(volume)
            
            if len(history) < 5:
                return 0.5
            
            volumes = list(history)
            
            # Calculate average volume (excluding current)
            avg_volume = np.mean(volumes[:-1])
            
            if avg_volume == 0:
                return 0.5
            
            # Volume surge ratio
            surge_ratio = volume / avg_volume
            
            # Volume acceleration
            if len(volumes) >= 10:
                recent_avg = np.mean(volumes[-5:])
                older_avg = np.mean(volumes[-10:-5])
                vol_acceleration = recent_avg / older_avg if older_avg > 0 else 1.0
            else:
                vol_acceleration = 1.0
            
            # Combine surge and acceleration
            explosion_score = self._normalize(surge_ratio * vol_acceleration, 1.0, 5.0)
            
            return explosion_score
            
        except Exception as e:
            logger.debug(f"Volume explosion detection error: {e}")
            return 0.5

    def _detect_volatility_expansion(self, symbol: str, volatility: float) -> float:
        """Detect when volatility is expanding (good for aggressive trading)."""
        try:
            if symbol not in self.volatility_history:
                self.volatility_history[symbol] = deque(maxlen=15)
            
            history = self.volatility_history[symbol]
            history.append(volatility)
            
            if len(history) < 5:
                return 0.5
            
            vols = list(history)
            
            # Check if volatility is increasing
            recent_vol = np.mean(vols[-3:])
            older_vol = np.mean(vols[:-3])
            
            if older_vol == 0:
                return 0.5
            
            expansion_ratio = recent_vol / older_vol
            
            # Expanding volatility is good for aggressive strategies
            if expansion_ratio > 1.1:
                self.volatility_expanding[symbol] = True
                expansion_score = self._normalize(expansion_ratio, 1.0, 2.0)
            else:
                self.volatility_expanding[symbol] = False
                expansion_score = 0.3
            
            return expansion_score
            
        except Exception as e:
            logger.debug(f"Volatility expansion error: {e}")
            return 0.5

    def _assess_trend_strength(self, price: float, high_24h: float, 
                              low_24h: float, price_change: float) -> float:
        """Assess the strength of the current trend."""
        try:
            # Range strength
            range_24h = high_24h - low_24h
            if range_24h == 0:
                return 0.5
            
            # Position in range (prefer prices near highs for bullish)
            if price_change > 0:
                position_score = (price - low_24h) / range_24h
            else:
                position_score = (high_24h - price) / range_24h
            
            # Directional strength
            direction_strength = abs(price_change) / 100
            direction_score = self._normalize(direction_strength, 0.02, 0.10)
            
            # Combine
            trend_strength = (position_score * 0.4 + direction_score * 0.6)
            
            return trend_strength
            
        except Exception as e:
            logger.debug(f"Trend strength error: {e}")
            return 0.5

    def _detect_early_entry_opportunity(self, symbol: str, price: float, 
                                       volume: float, momentum: float) -> float:
        """Detect if this is an early entry opportunity (before the crowd)."""
        try:
            # Early entry indicators:
            # 1. Volume just starting to pick up (not yet extreme)
            # 2. Momentum building but not peaked
            # 3. Price action clean (not choppy)
            
            vol_history = self.volume_history.get(symbol, deque())
            if len(vol_history) < 5:
                return 0.5
            
            volumes = list(vol_history)
            avg_vol = np.mean(volumes[:-1])
            current_ratio = volume / avg_vol if avg_vol > 0 else 1
            
            # Sweet spot: 1.5x to 3x normal volume (not too early, not too late)
            if 1.5 <= current_ratio <= 3.0:
                volume_timing = 0.9
            elif 1.0 <= current_ratio < 1.5:
                volume_timing = 0.6  # Maybe too early
            elif 3.0 < current_ratio <= 5.0:
                volume_timing = 0.7  # Still okay
            else:
                volume_timing = 0.4  # Too late or too early
            
            # Momentum building (not peaked)
            momentum_timing = 0.8 if 0.5 <= momentum <= 0.85 else 0.5
            
            # Combine
            early_entry = (volume_timing * 0.6 + momentum_timing * 0.4)
            
            return early_entry
            
        except Exception as e:
            logger.debug(f"Early entry detection error: {e}")
            return 0.5

    def _calculate_aggressive_confluence(self, momentum: float, volume: float,
                                        volatility: float, trend: float,
                                        early_entry: float) -> float:
        """Calculate confluence of aggressive signals."""
        try:
            factors = [momentum, volume, volatility, trend, early_entry]
            
            # High confluence = all factors agree and are strong
            avg_score = np.mean(factors)
            
            # Low standard deviation = high agreement
            std_score = np.std(factors)
            agreement = 1 - min(std_score, 1.0)
            
            # Bonus for all factors being strong
            all_strong = all(f > 0.6 for f in factors)
            strength_bonus = 0.3 if all_strong else 0
            
            confluence = avg_score * agreement + strength_bonus
            
            return min(confluence, 1.0)
            
        except Exception as e:
            logger.debug(f"Confluence calculation error: {e}")
            return 0.5

    def _aggressive_position_sizing(self, confidence: float, volatility: float,
                                   momentum: float, risk_factor: float) -> float:
        """Calculate aggressive position sizes with proper volatility risk management."""
        try:
            # Get numeric constants for configuration
            nc = get_numeric_constants()
            
            c = self.strategy_config
            base_size = c.get("base_position_size", nc.aggressive_base_position_size)
            max_size = c.get("max_position_size", nc.aggressive_max_position_size)
            min_size = c.get("min_position_size", 0.001)
            
            # Base calculation with confidence
            size = base_size * confidence * risk_factor
            
            # Momentum multiplier (more momentum = larger position)
            # This is appropriate - strong momentum signals higher probability of success
            momentum_multiplier = 1 + (momentum * 0.5)
            size *= momentum_multiplier
            
            # FIXED: Volatility risk adjustment (higher vol = SMALLER position)
            # This is critical for risk management - aggressive strategies should
            # reduce position size when volatility increases, not increase it.
            # Using divisor approach: position = base / (1 + volatility * factor)
            vol_divisor = nc.aggressive_volatility_divisor  # Default 2.0
            vol_adjustment = 1.0 / (1.0 + volatility * vol_divisor)
            size *= vol_adjustment
            
            # Apply bounds
            return float(max(min_size, min(float(size), max_size)))
            
        except Exception as e:
            logger.debug(f"Position sizing error: {e}")
            return nc.aggressive_base_position_size

    def _aggressive_risk_targets(self, confidence: float, volatility: float,
                                momentum: float, trend_strength: float) -> tuple:
        """Calculate aggressive stop loss and take profit targets."""
        try:
            c = self.strategy_config
            
            # AGGRESSIVE STOP LOSS (tighter to maximize risk/reward)
            base_sl = c.get("stop_loss_pct", 0.06)  # 6% base stop
            
            # Tighter stops for high confidence
            confidence_adj = -0.02 * confidence
            
            # Wider stops for high volatility (but not too wide)
            vol_adj = volatility * 0.015
            
            # Tighter stops for strong trends
            trend_adj = -0.01 * trend_strength
            
            stop_loss_pct = base_sl + confidence_adj + vol_adj + trend_adj
            stop_loss_pct = max(0.03, min(stop_loss_pct, 0.12))  # 3-12% range
            
            # AGGRESSIVE TAKE PROFIT (let winners run!)
            base_tp = c.get("take_profit_pct", 0.25)  # 25% base target
            
            # Higher targets for strong momentum
            momentum_multiplier = 1 + (momentum * 0.8)
            
            # Higher targets for high confidence
            confidence_multiplier = 1 + (confidence * 0.4)
            
            # Higher targets for strong trends
            trend_multiplier = 1 + (trend_strength * 0.3)
            
            take_profit_pct = base_tp * momentum_multiplier * confidence_multiplier * trend_multiplier
            take_profit_pct = max(0.12, min(take_profit_pct, 0.60))  # 12-60% range
            
            return stop_loss_pct, take_profit_pct
            
        except Exception as e:
            logger.debug(f"Risk targets error: {e}")
            return 0.06, 0.25

    def _update_hot_symbols(self, symbol: str, confidence: float, momentum: float):
        """Track hot symbols that are performing well."""
        try:
            # Add to hot symbols if high confidence and momentum
            if confidence > 0.7 and momentum > 0.7:
                self.hot_symbols.add(symbol)
                
                # Track streak
                if symbol not in self.symbol_momentum_streak:
                    self.symbol_momentum_streak[symbol] = 1
                else:
                    self.symbol_momentum_streak[symbol] += 1
            else:
                # Remove if no longer hot
                self.hot_symbols.discard(symbol)
                self.symbol_momentum_streak.pop(symbol, None)
            
            # Keep hot symbols list manageable (top 10)
            if len(self.hot_symbols) > 10:
                # Remove least recent
                self.hot_symbols.pop()
            
        except Exception as e:
            logger.debug(f"Hot symbols update error: {e}")

    def get_strategy_stats(self) -> dict:
        """Get current strategy statistics."""
        return {
            "hot_symbols": list(self.hot_symbols),
            "hot_symbol_count": len(self.hot_symbols),
            "tracked_symbols": len(self.price_history),
            "momentum_streak_leaders": sorted(
                self.symbol_momentum_streak.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
