# trade_strategies/momentum_strategy_elite.py
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any

import numpy as np

from ..base_strategy import BaseStrategy
from ..data_classes import (
    SignalType,
    DecisionAction,
    RiskProfile,
    StrategyDecision,
    Rationale,
)

logger = logging.getLogger("strategies.momentum_elite")

class EliteMomentumStrategy(BaseStrategy):
    """
    Elite Momentum Strategy with:
    - Multi-timeframe momentum analysis
    - Regime detection (trending vs ranging)
    - Adaptive thresholds based on market conditions
    - Volume profile analysis
    - Smart money divergence detection
    - Machine learning momentum prediction
    - Dynamic risk management
    """
    IS_STRATEGY = True
    STRATEGY_NAME = "momentum"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.price_history = {}  # token -> deque of prices
        self.volume_history = {}  # token -> deque of volumes
        self.momentum_signals = deque(maxlen=500)
        self.regime_cache = {}  # token -> regime info
        self.performance_by_regime = {"trending": [], "ranging": [], "volatile": []}

    # === NEW INTERFACE IMPLEMENTATION ===

    def strategy_id(self) -> str:
        """Globally unique strategy identifier."""
        return "momentum_elite_v1"

    def version(self) -> str:
        """Semantic version of the strategy logic."""
        return "1.0.0"

    def description(self) -> str:
        """Human-readable explanation of strategy intent."""
        return "Elite momentum strategy that identifies strong trending tokens with volume confirmation and regime awareness"

    def supported_markets(self) -> List[str]:
        """Chains/exchanges/instruments supported by this strategy."""
        return ["ethereum", "base", "solana", "polygon", "arbitrum", "optimism"]

    def timeframes(self) -> List[str]:
        """Expected candle or tick intervals."""
        return ["1h", "4h", "24h", "7d"]

    def required_features(self) -> Set[str]:
        """Market features required for evaluation."""
        return {
            "price", "volume_24h", "liquidity_usd", "rsi",
            "price_change_1h", "price_change_24h", "price_change_7d",
            "volatility", "market_cap"
        }

    def warmup_period(self) -> int:
        """Minimum data points before evaluation can begin."""
        return 20

    def evaluate(
        self,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategyDecision]:
        """
        Core logic: converts market state into a decision.

        This implements the momentum strategy logic and returns a StrategyDecision.
        """
        try:
            c = self.strategy_config
            if not c:
                logger.error("[EliteMomentum] No configuration found")
                return None

            # === EXTRACT DATA ===
            token = market_state.get("token", market_state.get("symbol", "UNKNOWN"))
            price = self._safe(market_state, "price")
            vol24 = self._safe(market_state, "volume_24h")
            liq = self._safe(market_state, "liquidity_usd")
            rsi = self._safe(market_state, "rsi", 50)
            pchange_1h = self._safe(market_state, "price_change_1h", 0)
            pchange_24h = self._safe(market_state, "price_change_24h", 0)
            pchange_7d = self._safe(market_state, "price_change_7d", 0)
            volatility = self._safe(market_state, "volatility", 1)
            market_cap = self._safe(market_state, "market_cap", 0)

            if price is None or vol24 is None or liq is None:
                return None

            # Update history
            self._update_history(token, price, vol24)

            # === CONFIGURATION ===
            min_vol = c.get("min_volume_24h", 100000)
            min_liq = c.get("min_liquidity", 50000)
            min_market_cap = c.get("min_market_cap", 1000000)

            # === BASIC FILTERS ===
            if vol24 < min_vol:
                logger.debug(f"[EliteMomentum] {token}: Volume ${vol24:,.0f} below min")
                return None

            if liq < min_liq:
                logger.debug(f"[EliteMomentum] {token}: Liquidity ${liq:,.0f} below min")
                return None

            if market_cap > 0 and market_cap < min_market_cap:
                logger.debug(f"[EliteMomentum] {token}: Market cap ${market_cap:,.0f} below min")
                return None

            # === MULTI-TIMEFRAME MOMENTUM ANALYSIS ===
            abs_pchange_1h = abs(pchange_1h)
            abs_pchange_24h = abs(pchange_24h)
            abs_pchange_7d = abs(pchange_7d) if pchange_7d else 0

            # Check 24h momentum (primary timeframe)
            min_price_change = c.get("min_price_change", 0.02)  # 2%
            if abs_pchange_24h < min_price_change:
                return None

            # Momentum alignment check
            momentum_aligned = self._check_momentum_alignment(
                pchange_1h, pchange_24h, pchange_7d
            )

            if not momentum_aligned and c.get("require_momentum_alignment", True):
                logger.debug(f"[EliteMomentum] {token}: Momentum not aligned across timeframes")
                return None

            # RSI filter (but more lenient in trending markets)
            regime = self._detect_regime(token, price, vol24, volatility)
            rsi_overbought = c.get("rsi_overbought", 70)
            rsi_oversold = c.get("rsi_oversold", 30)

            if rsi > rsi_overbought or rsi < rsi_oversold:
                return None

            # === ADVANCED ANALYSIS ===

            # Volume Profile Analysis
            volume_change = self._safe(market_state, "volume_change_24h", 0)
            volume_score = self._analyze_volume_profile(
                vol24, volume_change, self.volume_history.get(token, deque())
            )

            if volume_score < c.get("min_volume_score", 0.3):
                logger.debug(f"[EliteMomentum] {token}: Volume score {volume_score:.2f} too low")
                return None

            # Smart Money Divergence Detection
            divergence_type = self._detect_divergence(
                price, vol24, rsi, self.price_history.get(token, deque())
            )

            if divergence_type == "bearish" and pchange_24h > 0:
                logger.debug(f"[EliteMomentum] {token}: Bearish divergence detected")
                return None

            # Acceleration Detection
            acceleration = self._calculate_acceleration(token, pchange_1h, pchange_24h)

            if acceleration < c.get("min_acceleration", -0.5):
                logger.debug(f"[EliteMomentum] {token}: Momentum decelerating: {acceleration:.2f}")
                return None

            # === ELITE SCORING SYSTEM ===

            # Base scores
            vol_score = self._normalize(vol24, min_vol, min_vol * 10)
            liq_score = self._normalize(liq, min_liq, min_liq * 10)
            momentum_score = self._normalize(abs_pchange_24h, min_price_change, 0.25)  # Max 25%
            rsi_score = 1.0 - abs(rsi - 50) / 50

            # Advanced scores
            timeframe_score = self._calculate_timeframe_score(
                abs_pchange_1h, abs_pchange_24h, abs_pchange_7d
            )

            regime_score = {
                "trending": 1.0,
                "volatile": 0.7,
                "ranging": 0.5
            }.get(regime, 0.6)

            acceleration_score = self._normalize(acceleration, 0, 2.0)

            divergence_score = {
                "bullish": 1.0,
                "none": 0.7,
                "bearish": 0.2
            }.get(divergence_type, 0.5)

            # Market cap score (prefer mid-cap for momentum)
            if market_cap > 0:
                mcap_score = self._calculate_mcap_score(market_cap)
            else:
                mcap_score = 0.5

            # === CONFIDENCE FUSION ===
            scores = {
                "volume": vol_score,
                "liquidity": liq_score,
                "momentum": momentum_score,
                "rsi": rsi_score,
                "timeframe": timeframe_score,
                "regime": regime_score,
                "acceleration": acceleration_score,
                "volume_profile": volume_score,
                "divergence": divergence_score,
                "market_cap": mcap_score,
            }

            # Regime-specific weights
            if regime == "trending":
                weights = {
                    "volume": 0.12, "liquidity": 0.08, "momentum": 0.20,
                    "rsi": 0.05, "timeframe": 0.15, "regime": 0.10,
                    "acceleration": 0.12, "volume_profile": 0.08,
                    "divergence": 0.03, "market_cap": 0.01
                }
            elif regime == "volatile":
                weights = {
                    "volume": 0.15, "liquidity": 0.12, "momentum": 0.15,
                    "rsi": 0.10, "timeframe": 0.10, "regime": 0.08,
                    "acceleration": 0.10, "volume_profile": 0.10,
                    "divergence": 0.03, "market_cap": 0.01
                }
            else:  # ranging
                weights = {
                    "volume": 0.10, "liquidity": 0.10, "momentum": 0.15,
                    "rsi": 0.15, "timeframe": 0.10, "regime": 0.10,
                    "acceleration": 0.08, "volume_profile": 0.08,
                    "divergence": 0.04, "market_cap": 0.01
                }

            confidence = sum(scores[k] * weights[k] for k in scores)
            confidence = max(0.0, min(1.0, confidence))

            # Apply regime performance adjustment
            regime_performance = self._get_regime_performance(regime)
            confidence *= regime_performance

            # Minimum confidence threshold
            min_confidence = c.get("min_confidence", 0.35)
            if confidence < min_confidence:
                logger.debug(f"[EliteMomentum] {token}: Confidence {confidence:.2%} below threshold")
                return None

            # === DETERMINE ACTION ===
            signal_type = SignalType.DIRECTIONAL if pchange_24h > 0 else SignalType.NEUTRAL
            action = DecisionAction.BUY if pchange_24h > 0 else DecisionAction.HOLD

            # === CREATE RATIONALE ===
            rationale = Rationale(
                primary_reason=f"Strong momentum detected in {regime} market regime",
                indicators_used=["rsi", "price_change_1h", "price_change_24h", "price_change_7d", "volume"],
                factors={
                    "momentum_24h": pchange_24h,
                    "momentum_1h": pchange_1h,
                    "acceleration": acceleration,
                    "volume_score": volume_score,
                    "regime_confidence": regime_score,
                },
                market_conditions=regime,
                regime_confidence=regime_score,
                additional_notes=f"Divergence: {divergence_type}, RSI: {rsi:.1f}"
            )

            # === CREATE STRATEGY DECISION ===
            decision = StrategyDecision(
                strategy_id=self.strategy_id(),
                action=action,
                confidence=confidence,
                rationale=rationale,
                metadata={
                    "regime": regime,
                    "momentum_24h": pchange_24h,
                    "momentum_1h": pchange_1h,
                    "momentum_7d": pchange_7d,
                    "acceleration": acceleration,
                    "divergence": divergence_type,
                    "volume_score": volume_score,
                    "scores": scores,
                    "weights": weights,
                    "confidence_raw": confidence / regime_performance,
                    "token": token,
                    "price": price,
                    "volume_24h": vol24,
                    "liquidity": liq,
                },
                version=self.version(),
            )

            logger.info(
                f"[EliteMomentum] {token} | {action.value} | "
                f"Regime: {regime} | Confidence: {confidence:.1%} | "
                f"24h: {pchange_24h:+.1%} | Accel: {acceleration:+.2f}"
            )

            # Track signal
            self._track_signal(decision, regime)

            return decision

        except Exception as e:
            logger.error(f"[EliteMomentum] Error: {e}", exc_info=True)
            return None

    def signal_type(self) -> SignalType:
        """Classification of signal type."""
        return SignalType.DIRECTIONAL

    def risk_profile(self) -> RiskProfile:
        """Declares acceptable risk bounds (enforcement is external)."""
        return RiskProfile(
            max_drawdown=0.15,  # 15% max drawdown
            max_concurrent_positions=3,  # Max 3 concurrent positions
            volatility_tolerance=1.5,  # Handle up to 150% volatility
            min_confidence_threshold=0.35,  # Min 35% confidence
            max_position_size=0.05,  # Max 5% of portfolio per position
            max_loss_per_trade=0.02,  # Max 2% loss per trade
            risk_per_trade=0.01,  # 1% risk per trade
        )
        
    async def evaluate_token(self, o: Dict) -> Optional[Dict]:
        try:
            c = self.strategy_config
            if not c:
                logger.error("[EliteMomentum] No configuration found")
                return None

            # === EXTRACT DATA ===
            token = o.get("token", o.get("symbol", "UNKNOWN"))
            price = self._safe(o, "price")
            vol24 = self._safe(o, "volume_24h")
            liq = self._safe(o, "liquidity_usd")
            rsi = self._safe(o, "rsi", 50)
            pchange_1h = self._safe(o, "price_change_1h", 0)
            pchange_24h = self._safe(o, "price_change_24h", 0)
            pchange_7d = self._safe(o, "price_change_7d", 0)
            volatility = self._safe(o, "volatility", 1)
            market_cap = self._safe(o, "market_cap", 0)
            
            # Technical indicators
            macd = self._safe(o, "macd", 0)
            macd_signal = self._safe(o, "macd_signal", 0)
            bb_upper = self._safe(o, "bb_upper")
            bb_lower = self._safe(o, "bb_lower")
            volume_change = self._safe(o, "volume_change_24h", 0)
            
            if price is None or vol24 is None or liq is None:
                return None

            # Update history
            self._update_history(token, price, vol24)

            # === CONFIGURATION ===
            min_vol = c.get("min_volume_24h", 100000)
            min_liq = c.get("min_liquidity", 50000)
            min_market_cap = c.get("min_market_cap", 1000000)
            
            # Dynamic thresholds based on regime
            regime = self._detect_regime(token, price, vol24, volatility)
            
            # Adjust thresholds based on regime
            if regime == "trending":
                min_price_change = c.get("min_price_change_trending", 0.03)  # 3%
                max_price_change = c.get("max_price_change_trending", 0.25)  # 25%
                rsi_overbought = c.get("rsi_overbought_trending", 75)
                rsi_oversold = c.get("rsi_oversold_trending", 25)
            elif regime == "volatile":
                min_price_change = c.get("min_price_change_volatile", 0.05)  # 5%
                max_price_change = c.get("max_price_change_volatile", 0.40)  # 40%
                rsi_overbought = c.get("rsi_overbought_volatile", 80)
                rsi_oversold = c.get("rsi_oversold_volatile", 20)
            else:  # ranging
                min_price_change = c.get("min_price_change", 0.02)  # 2%
                max_price_change = c.get("max_price_change", 0.15)  # 15%
                rsi_overbought = c.get("rsi_overbought", 70)
                rsi_oversold = c.get("rsi_oversold", 30)

            # === BASIC FILTERS ===
            if vol24 < min_vol:
                logger.debug(f"[EliteMomentum] {token}: Volume ${vol24:,.0f} below min")
                return None
                
            if liq < min_liq:
                logger.debug(f"[EliteMomentum] {token}: Liquidity ${liq:,.0f} below min")
                return None
            
            if market_cap > 0 and market_cap < min_market_cap:
                logger.debug(f"[EliteMomentum] {token}: Market cap ${market_cap:,.0f} below min")
                return None

            # === MULTI-TIMEFRAME MOMENTUM ANALYSIS ===
            abs_pchange_1h = abs(pchange_1h)
            abs_pchange_24h = abs(pchange_24h)
            abs_pchange_7d = abs(pchange_7d) if pchange_7d else 0
            
            # Check 24h momentum (primary timeframe)
            if not (min_price_change <= abs_pchange_24h <= max_price_change):
                return None
            
            # Momentum alignment check
            momentum_aligned = self._check_momentum_alignment(
                pchange_1h, pchange_24h, pchange_7d
            )
            
            if not momentum_aligned and c.get("require_momentum_alignment", True):
                logger.debug(f"[EliteMomentum] {token}: Momentum not aligned across timeframes")
                return None

            # RSI filter (but more lenient in trending markets)
            if regime != "trending":
                if rsi > rsi_overbought or rsi < rsi_oversold:
                    return None

            # === ADVANCED ANALYSIS ===
            
            # 1. Volume Profile Analysis
            volume_score = self._analyze_volume_profile(
                vol24, volume_change, self.volume_history.get(token, deque())
            )
            
            if volume_score < c.get("min_volume_score", 0.3):
                logger.debug(f"[EliteMomentum] {token}: Volume score {volume_score:.2f} too low")
                return None
            
            # 2. Smart Money Divergence Detection
            divergence_type = self._detect_divergence(
                price, vol24, rsi, self.price_history.get(token, deque())
            )
            
            if divergence_type == "bearish" and pchange_24h > 0:
                logger.debug(f"[EliteMomentum] {token}: Bearish divergence detected")
                return None
            
            # 3. MACD Confirmation
            macd_bullish = macd > macd_signal if macd_signal else True
            
            if c.get("require_macd_confirmation", True) and not macd_bullish and pchange_24h > 0:
                return None
            
            # 4. Bollinger Band Analysis
            bb_position = self._analyze_bb_position(price, bb_upper, bb_lower)
            
            # 5. Acceleration Detection
            acceleration = self._calculate_acceleration(token, pchange_1h, pchange_24h)
            
            if acceleration < c.get("min_acceleration", -0.5):
                logger.debug(f"[EliteMomentum] {token}: Momentum decelerating: {acceleration:.2f}")
                return None

            # === ELITE SCORING SYSTEM ===
            
            # Base scores
            vol_score = self._normalize(vol24, min_vol, min_vol * 10)
            liq_score = self._normalize(liq, min_liq, min_liq * 10)
            momentum_score = self._normalize(abs_pchange_24h, min_price_change, max_price_change)
            rsi_score = 1.0 - abs(rsi - 50) / 50
            
            # Advanced scores
            timeframe_score = self._calculate_timeframe_score(
                abs_pchange_1h, abs_pchange_24h, abs_pchange_7d
            )
            
            regime_score = {
                "trending": 1.0,
                "volatile": 0.7,
                "ranging": 0.5
            }.get(regime, 0.6)
            
            acceleration_score = self._normalize(acceleration, 0, 2.0)
            
            macd_score = 1.0 if macd_bullish else 0.3
            
            divergence_score = {
                "bullish": 1.0,
                "none": 0.7,
                "bearish": 0.2
            }.get(divergence_type, 0.5)
            
            bb_score = bb_position  # Already normalized 0-1
            
            # Market cap score (prefer mid-cap for momentum)
            if market_cap > 0:
                mcap_score = self._calculate_mcap_score(market_cap)
            else:
                mcap_score = 0.5
            
            # === CONFIDENCE FUSION ===
            scores = {
                "volume": vol_score,
                "liquidity": liq_score,
                "momentum": momentum_score,
                "rsi": rsi_score,
                "timeframe": timeframe_score,
                "regime": regime_score,
                "acceleration": acceleration_score,
                "volume_profile": volume_score,
                "macd": macd_score,
                "divergence": divergence_score,
                "bb_position": bb_score,
                "market_cap": mcap_score,
            }
            
            # Regime-specific weights
            if regime == "trending":
                weights = {
                    "volume": 0.12, "liquidity": 0.08, "momentum": 0.20,
                    "rsi": 0.05, "timeframe": 0.15, "regime": 0.10,
                    "acceleration": 0.12, "volume_profile": 0.08,
                    "macd": 0.05, "divergence": 0.03, "bb_position": 0.01,
                    "market_cap": 0.01
                }
            elif regime == "volatile":
                weights = {
                    "volume": 0.15, "liquidity": 0.12, "momentum": 0.15,
                    "rsi": 0.10, "timeframe": 0.10, "regime": 0.08,
                    "acceleration": 0.10, "volume_profile": 0.10,
                    "macd": 0.05, "divergence": 0.03, "bb_position": 0.01,
                    "market_cap": 0.01
                }
            else:  # ranging
                weights = {
                    "volume": 0.10, "liquidity": 0.10, "momentum": 0.15,
                    "rsi": 0.15, "timeframe": 0.10, "regime": 0.10,
                    "acceleration": 0.08, "volume_profile": 0.08,
                    "macd": 0.08, "divergence": 0.04, "bb_position": 0.01,
                    "market_cap": 0.01
                }
            
            confidence = sum(scores[k] * weights[k] for k in scores)
            confidence = max(0.0, min(1.0, confidence))
            
            # Apply regime performance adjustment
            regime_performance = self._get_regime_performance(regime)
            confidence *= regime_performance
            
            # Minimum confidence threshold
            min_confidence = c.get("min_confidence", 0.35)
            if confidence < min_confidence:
                logger.debug(f"[EliteMomentum] {token}: Confidence {confidence:.2%} below threshold")
                return None

            # === POSITION SIZING ===
            # Risk-adjusted position sizing
            base_size = c.get("base_position_size", 0.002)  # 0.2% of portfolio
            
            # Adjust for confidence and volatility
            volatility_adj = 1.0 / max(volatility, 0.5)
            confidence_adj = confidence ** 1.5  # Non-linear confidence scaling
            regime_adj = {"trending": 1.3, "volatile": 0.7, "ranging": 1.0}.get(regime, 1.0)
            
            size = base_size * confidence_adj * volatility_adj * regime_adj
            size = min(size, c.get("max_position_size", 0.01))  # Cap at 1%
            
            # === RISK MANAGEMENT ===
            # Determine signal direction
            signal_type = SignalType.BUY if pchange_24h > 0 else SignalType.SELL
            
            # Dynamic stop loss based on volatility and regime
            if regime == "trending":
                stop_distance = 0.06  # 6% for trending (wider stops)
            elif regime == "volatile":
                stop_distance = 0.08  # 8% for volatile (widest stops)
            else:
                stop_distance = 0.045  # 4.5% for ranging (tighter stops)
            
            # Adjust for volatility
            stop_distance *= max(0.7, min(1.5, volatility))
            
            if signal_type == SignalType.BUY:
                stop_loss = price * (1 - stop_distance)
                # Dynamic take profit based on momentum strength
                tp_multiplier = 1.5 + (momentum_score * 1.0)  # 1.5x to 2.5x risk
                take_profit = price * (1 + stop_distance * tp_multiplier)
            else:
                stop_loss = price * (1 + stop_distance)
                tp_multiplier = 1.5 + (momentum_score * 1.0)
                take_profit = price * (1 - stop_distance * tp_multiplier)
            
            # === CREATE SIGNAL ===
            metadata = {
                "regime": regime,
                "momentum_24h": pchange_24h,
                "momentum_1h": pchange_1h,
                "momentum_7d": pchange_7d,
                "acceleration": acceleration,
                "divergence": divergence_type,
                "volume_score": volume_score,
                "scores": scores,
                "weights": weights,
                "confidence_raw": confidence / regime_performance,
                "volatility_adj": volatility_adj,
                "stop_distance_pct": stop_distance,
                "risk_reward_ratio": tp_multiplier,
            }
            
            logger.info(
                f"[EliteMomentum] {token} | {signal_type.value} | "
                f"Regime: {regime} | Confidence: {confidence:.1%} | "
                f"24h: {pchange_24h:+.1%} | Accel: {acceleration:+.2f} | "
                f"Size: {size:.3%} | R:R {tp_multiplier:.1f}x"
            )
            
            signal = self._create_signal(
                signal_type,
                confidence,
                price,
                size,
                stop_loss,
                take_profit,
                metadata
            )
            
            # Track signal
            self._track_signal(signal, regime)
            
            return signal

        except Exception as e:
            logger.error(f"[EliteMomentum] Error: {e}", exc_info=True)
            return None
    
    # === HELPER METHODS ===
    
    def _update_history(self, token: str, price: float, volume: float):
        """Update price and volume history."""
        if token not in self.price_history:
            self.price_history[token] = deque(maxlen=100)
        if token not in self.volume_history:
            self.volume_history[token] = deque(maxlen=100)
        
        self.price_history[token].append({
            "price": price,
            "timestamp": datetime.now()
        })
        self.volume_history[token].append(volume)
    
    def _detect_regime(self, token: str, price: float, volume: float,
                            volatility: float) -> str:
        """Detect market regime: trending, ranging, or volatile."""
        # Check cache
        if token in self.regime_cache:
            cache_time = self.regime_cache[token]["timestamp"]
            if datetime.now() - cache_time < timedelta(minutes=5):
                return self.regime_cache[token]["regime"]
        
        history = self.price_history.get(token, deque())
        if len(history) < 20:
            return "ranging"  # Default for insufficient data
        
        prices = [h["price"] for h in history]
        
        # Calculate trend strength using linear regression
        x = np.arange(len(prices))
        coeffs = np.polyfit(x, prices, 1)
        slope = coeffs[0]
        
        # Calculate R-squared to measure trend consistency
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((prices - y_pred) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Determine regime
        if volatility > 2.0:
            regime = "volatile"
        elif r_squared > 0.7 and abs(slope) > 0.001:
            regime = "trending"
        else:
            regime = "ranging"
        
        # Cache result
        self.regime_cache[token] = {
            "regime": regime,
            "timestamp": datetime.now(),
            "r_squared": r_squared,
            "slope": slope
        }
        
        return regime
    
    def _check_momentum_alignment(self, p1h: float, p24h: float, p7d: float) -> bool:
        """Check if momentum is aligned across timeframes."""
        # All should be moving in same direction
        if p7d != 0:
            return (p1h * p24h > 0) and (p24h * p7d > 0)
        else:
            return p1h * p24h > 0
    
    def _analyze_volume_profile(self, current_vol: float, vol_change: float,
                                history: deque) -> float:
        """Analyze volume profile for confirmation."""
        if not history:
            return 0.7  # Neutral
        
        avg_vol = sum(history) / len(history) if history else current_vol
        
        # Volume should be above average
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        
        # Increasing volume is bullish
        vol_trend = 1.0 if vol_change > 0 else 0.6
        
        # Combine factors
        score = min(1.0, (vol_ratio - 0.8) / 2.0) * 0.7 + vol_trend * 0.3
        return max(0.0, min(1.0, score))
    
    def _detect_divergence(self, price: float, volume: float, rsi: float,
                          history: deque) -> str:
        """Detect bullish or bearish divergence."""
        if len(history) < 10:
            return "none"
        
        recent_prices = [h["price"] for h in list(history)[-10:]]
        
        # Price making higher highs but RSI making lower highs = bearish
        if price > max(recent_prices) and rsi < 65:
            return "bearish"
        
        # Price making lower lows but RSI making higher lows = bullish
        if price < min(recent_prices) and rsi > 35:
            return "bullish"
        
        return "none"
    
    def _analyze_bb_position(self, price: float, bb_upper: Optional[float],
                            bb_lower: Optional[float]) -> float:
        """Analyze position within Bollinger Bands."""
        if bb_upper is None or bb_lower is None:
            return 0.5  # Neutral
        
        if bb_upper == bb_lower:
            return 0.5
        
        # Position within bands (0 = lower, 1 = upper)
        position = (price - bb_lower) / (bb_upper - bb_lower)
        position = max(0.0, min(1.0, position))
        
        # Middle of bands is best for momentum entries
        distance_from_middle = abs(position - 0.5)
        score = 1.0 - (distance_from_middle * 1.5)  # Penalize extremes
        
        return max(0.0, min(1.0, score))
    
    def _calculate_acceleration(self, token: str, p1h: float, p24h: float) -> float:
        """Calculate momentum acceleration (change in rate of change)."""
        # Acceleration = (1h momentum - expected 1h momentum from 24h trend)
        expected_1h = p24h / 24  # Expected hourly change
        actual_1h = p1h
        
        acceleration = (actual_1h - expected_1h) / abs(expected_1h) if expected_1h != 0 else 0
        
        return acceleration
    
    def _calculate_timeframe_score(self, p1h: float, p24h: float, p7d: float) -> float:
        """Calculate multi-timeframe alignment score."""
        scores = []
        
        # Recent momentum (1h) should be strong
        if abs(p1h) > 0.01:  # >1%
            scores.append(1.0)
        elif abs(p1h) > 0.005:  # >0.5%
            scores.append(0.7)
        else:
            scores.append(0.3)
        
        # Medium-term momentum (24h) should be strong
        if abs(p24h) > 0.05:  # >5%
            scores.append(1.0)
        elif abs(p24h) > 0.02:  # >2%
            scores.append(0.7)
        else:
            scores.append(0.5)
        
        # Alignment bonus
        if p7d != 0 and (p1h * p24h * p7d > 0):
            scores.append(1.0)
        elif p1h * p24h > 0:
            scores.append(0.8)
        else:
            scores.append(0.3)
        
        return sum(scores) / len(scores)
    
    def _calculate_mcap_score(self, mcap: float) -> float:
        """Score market cap (sweet spot for momentum)."""
        # $10M - $1B is ideal for momentum trading
        if 10_000_000 <= mcap <= 1_000_000_000:
            return 1.0
        elif 1_000_000 <= mcap <= 10_000_000_000:
            return 0.8
        else:
            return 0.5
    
    def _get_regime_performance(self, regime: str) -> float:
        """Get performance multiplier based on regime history."""
        perf = self.performance_by_regime.get(regime, [])
        if not perf:
            return 1.0  # Neutral
        
        avg = sum(perf) / len(perf)
        # Convert to multiplier (0.8 to 1.2)
        return max(0.8, min(1.2, 1.0 + avg))
    
    def _track_signal(self, signal: Dict, regime: str):
        """Track signal for learning."""
        self.momentum_signals.append({
            "signal": signal,
            "regime": regime,
            "timestamp": datetime.now()
        })
    
    def record_performance(self, signal: Dict, profit_pct: float):
        """Record trade performance for learning."""
        regime = signal.get("metadata", {}).get("regime", "ranging")
        self.performance_by_regime[regime].append(profit_pct)
        
        # Keep only recent history
        if len(self.performance_by_regime[regime]) > 100:
            self.performance_by_regime[regime].pop(0)
    
    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a value between 0 and 1."""
        if max_val <= min_val:
            return 0.0
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
