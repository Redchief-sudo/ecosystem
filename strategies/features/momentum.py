# trade_strategies/momentum_strategy_elite.py
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Union

import numpy as np

from ..base_strategy import BaseStrategy, SignalType, TradeSignal
from ..data_classes import (
    SignalType as DataSignalType,
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
    - Bollinger Bands and MACD confirmation
    - Dynamic risk management
    """
    IS_STRATEGY = True
    STRATEGY_NAME = "momentum"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.price_history: Dict[str, deque[float]] = {}       # token -> deque of prices
        self.volume_history: Dict[str, deque[float]] = {}      # token -> deque of volumes
        self.momentum_signals: deque = deque(maxlen=500)
        self.regime_cache: Dict[str, Dict[str, Any]] = {}     # token -> cached regime
        self.performance_by_regime: Dict[str, List[float]] = {"trending": [], "ranging": [], "volatile": []}

    # === INTERFACE METHODS ===

    def strategy_id(self) -> str:
        return "momentum_elite_v1"

    def version(self) -> str:
        return "1.0.0"

    def description(self) -> str:
        return "Elite momentum strategy identifying trending tokens with volume, regime, and multi-timeframe confirmation."

    def supported_markets(self) -> List[str]:
        return ["ethereum", "base", "solana", "polygon", "arbitrum", "optimism"]

    def timeframes(self) -> List[str]:
        return ["1h", "4h", "24h", "7d"]

    def required_features(self) -> Set[str]:
        return {
            "price", "volume_24h", "liquidity_usd", "rsi",
            "price_change_1h", "price_change_24h", "price_change_7d",
            "volatility", "market_cap", "macd", "macd_signal",
            "bb_upper", "bb_lower", "volume_change_24h"
        }

    def warmup_period(self) -> int:
        return 20

    def signal_type(self) -> DataSignalType:
        return DataSignalType.DIRECTIONAL

    def risk_profile(self) -> RiskProfile:
        return RiskProfile(
            max_drawdown=0.15,
            max_concurrent_positions=3,
            volatility_tolerance=1.5,
            min_confidence_threshold=0.35,
            max_position_size=0.05,
            max_loss_per_trade=0.02,
            risk_per_trade=0.01,
        )

    # === CORE EVALUATION ===

    def evaluate(self, market_state: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[StrategyDecision]:
        """Synchronous evaluation wrapper."""
        return self._compute_decision(market_state)

    async def evaluate_token(self, o: Dict[str, Any]) -> Optional[TradeSignal]:
        """Async evaluation – returns a TradeSignal consumed by EliteStrategyManager."""
        decision = self._compute_decision(o)
        if decision is None:
            return None

        md = decision.metadata
        # Map DecisionAction → base_strategy.SignalType for _create_signal
        action = decision.action
        if action == DecisionAction.BUY:
            sig_type = SignalType.BUY
        elif action in (DecisionAction.SELL, DecisionAction.REDUCE, DecisionAction.CLOSE):
            sig_type = SignalType.SELL
        else:
            sig_type = SignalType.NEUTRAL

        return self._create_signal(
            signal_type=sig_type,
            confidence=decision.confidence,
            price=md.get("price", 0.0),
            position_size=md.get("position_size", 0.0),
            stop_loss=md.get("stop_loss", 0.0),
            take_profit=md.get("take_profit", 0.0),
            metadata=md,
        )

    def _compute_decision(self, data: Dict[str, Any]) -> Optional[StrategyDecision]:
        """Unified evaluation logic used by both sync and async calls."""
        try:
            c = self.strategy_config or {}
            token = data.get("token") or data.get("symbol") or "UNKNOWN"

            # === EXTRACT DATA ===
            price = self._safe(data, "price")
            vol24 = self._safe(data, "volume_24h")
            liq = self._safe(data, "liquidity_usd")
            rsi = self._safe(data, "rsi", 50)
            pchange_1h = self._safe(data, "price_change_1h", 0)
            pchange_24h = self._safe(data, "price_change_24h", 0)
            pchange_7d = self._safe(data, "price_change_7d", 0)
            volatility = self._safe(data, "volatility", 1)
            market_cap = self._safe(data, "market_cap", 0)
            macd = self._safe(data, "macd", 0)
            macd_signal = self._safe(data, "macd_signal", 0)
            bb_upper = self._safe(data, "bb_upper")
            bb_lower = self._safe(data, "bb_lower")
            volume_change = self._safe(data, "volume_change_24h", 0)

            if price is None or vol24 is None or liq is None:
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: Missing required data (price={price}, vol24={vol24}, liq={liq})")
                return None

            # === UPDATE HISTORIES ===
            self._update_history(token, price, vol24)
            
            # Check warmup period
            history_len = len(self.price_history.get(token, []))
            warmup = self.warmup_period()
            if history_len < warmup:
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: Insufficient history ({history_len}/{warmup} data points)")
                return None

            # === DETECT REGIME ===
            regime = self._detect_regime(token, price, vol24, volatility)

            # === CONFIGURE THRESHOLDS ===
            thresholds = self._get_regime_thresholds(c, regime)

            # === BASIC FILTERS ===
            if vol24 < thresholds["min_vol"] or liq < thresholds["min_liq"] or (market_cap and market_cap < thresholds["min_market_cap"]):
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: Failed basic filters (vol24={vol24:.0f} < {thresholds['min_vol']:.0f} or liq={liq:.0f} < {thresholds['min_liq']:.0f})")
                return None

            abs_pchange_1h, abs_pchange_24h, abs_pchange_7d = abs(pchange_1h), abs(pchange_24h), abs(pchange_7d)

            if not (thresholds["min_price_change"] <= abs_pchange_24h <= thresholds["max_price_change"]):
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: Price change out of range ({abs_pchange_24h:.2%} not in [{thresholds['min_price_change']:.2%}, {thresholds['max_price_change']:.2%}])")
                return None

            if thresholds.get("require_momentum_alignment", True):
                if not self._check_momentum_alignment(pchange_1h, pchange_24h, pchange_7d):
                    logger.debug(f"[{self.STRATEGY_NAME}] {token}: Momentum misalignment (1h={pchange_1h:.2%}, 24h={pchange_24h:.2%}, 7d={pchange_7d:.2%})")
                    return None

            if not (thresholds["rsi_oversold"] <= rsi <= thresholds["rsi_overbought"]):
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: RSI out of range ({rsi:.1f} not in [{thresholds['rsi_oversold']:.1f}, {thresholds['rsi_overbought']:.1f}])")
                return None

            # === ADVANCED ANALYSIS ===
            volume_score = self._analyze_volume_profile(vol24, volume_change, self.volume_history[token])
            if volume_score < c.get("min_volume_score", 0.3):
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: Volume score too low ({volume_score:.3f} < {c.get('min_volume_score', 0.3):.3f})")
                return None

            divergence_type = self._detect_divergence(price, rsi, self.price_history[token])
            if divergence_type == "bearish" and pchange_24h > 0:
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: Bearish divergence detected")
                return None

            macd_bullish = macd > macd_signal if macd_signal else True
            if thresholds.get("require_macd_confirmation", True) and not macd_bullish and pchange_24h > 0:
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: MACD not bullish (macd={macd:.4f}, signal={macd_signal:.4f})")
                return None

            bb_score = self._analyze_bb_position(price, bb_upper, bb_lower)
            acceleration = self._calculate_acceleration(token, pchange_1h, pchange_24h)
            if acceleration < thresholds.get("min_acceleration", -0.5):
                logger.debug(f"[{self.STRATEGY_NAME}] {token}: Acceleration too low ({acceleration:.3f} < {thresholds.get('min_acceleration', -0.5):.3f})")
                return None

            # === SCORING SYSTEM ===
            scores = self._compute_scores(
                vol24, liq, abs_pchange_24h, rsi, abs_pchange_1h, abs_pchange_24h, abs_pchange_7d,
                acceleration, volume_score, divergence_type, bb_score, market_cap, macd_bullish, regime
            )

            weights = self._get_weights_for_regime(regime)
            confidence_raw = sum(scores[k] * weights.get(k, 0.0) for k in scores)
            confidence_raw = max(0.0, min(1.0, confidence_raw))
            confidence = confidence_raw * self._get_regime_performance(regime)

            if confidence < thresholds.get("min_confidence", 0.35):
                return None

            # === POSITION SIZING ===
            size, stop_loss, take_profit, signal_type_enum, tp_multiplier = self._compute_position_and_risk(
                price, confidence, volatility, regime, abs_pchange_24h, scores["momentum"]
            )

            # === CREATE RATIONALE AND DECISION ===
            rationale = Rationale(
                primary_reason=f"Momentum detected in {regime} regime",
                indicators_used=["rsi", "price_change_1h", "price_change_24h", "price_change_7d", "volume", "macd", "bb_position"],
                factors={
                    "momentum_24h": pchange_24h,
                    "momentum_1h": pchange_1h,
                    "acceleration": acceleration,
                    "volume_score": volume_score,
                    "regime_confidence": scores.get("regime", 0.6)
                },
                market_conditions=regime,
                regime_confidence=scores.get("regime", 0.6),
                additional_notes=f"Divergence: {divergence_type}, RSI: {rsi:.1f}, MACD: {macd_bullish}, BB: {bb_score:.2f}"
            )

            decision = StrategyDecision(
                strategy_id=self.strategy_id(),
                action=DecisionAction.BUY if pchange_24h > 0 else DecisionAction.HOLD,
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
                    "confidence_raw": confidence_raw,
                    "volatility_adj": 1.0 / max(volatility, 0.5),
                    "stop_distance_pct": abs(price - stop_loss) / price,
                    "risk_reward_ratio": tp_multiplier,
                    "price": price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "position_size": size,
                    "signal_type": signal_type_enum,
                    "volume_24h": vol24,
                    "liquidity": liq,
                    "market_cap": market_cap,
                },
                version=self.version(),
            )

            # Track signal
            self._track_signal(decision, regime)

            logger.info(
                f"[EliteMomentum] {token} | {signal_type_enum.value} | "
                f"Regime: {regime} | Confidence: {confidence:.1%} | "
                f"24h: {pchange_24h:+.1%} | Accel: {acceleration:+.2f} | "
                f"Size: {size:.3%} | R:R {tp_multiplier:.1f}x"
            )

            return decision

        except Exception as e:
            logger.error(f"[EliteMomentum] Error evaluating token {data.get('token')}: {e}", exc_info=True)
            return None

    # === HELPER METHODS ===

    def _safe(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        val = data.get(key, default)
        try:
            if val is None:
                return default
            return float(val) if isinstance(val, (int, float, str)) else val
        except Exception:
            return default

    def _update_history(self, token: str, price: float, volume: float):
        """Update price and volume history with consistent float types."""
        if token not in self.price_history:
            self.price_history[token] = deque(maxlen=100)
        if token not in self.volume_history:
            self.volume_history[token] = deque(maxlen=100)
        self.price_history[token].append(float(price))
        self.volume_history[token].append(float(volume))

    def _detect_regime(self, token: str, price: float, volume: float, volatility: float) -> str:
        """Detect market regime: trending, ranging, or volatile."""
        now = datetime.now()
        if token in self.regime_cache:
            cache = self.regime_cache[token]
            if now - cache["timestamp"] < timedelta(minutes=5):
                return cache["regime"]

        history = self.price_history.get(token, deque())
        if len(history) < 20:
            regime = "ranging"
        else:
            prices = np.array(history)
            x = np.arange(len(prices))
            coeffs = np.polyfit(x, prices, 1)
            slope = coeffs[0]
            y_pred = np.polyval(coeffs, x)
            ss_res = np.sum((prices - y_pred) ** 2)
            ss_tot = np.sum((prices - np.mean(prices)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            if volatility > 2.0:
                regime = "volatile"
            elif r_squared > 0.7 and abs(slope) > 0.001:
                regime = "trending"
            else:
                regime = "ranging"

        self.regime_cache[token] = {"regime": regime, "timestamp": now}
        return regime

    def _check_momentum_alignment(self, p1h: float, p24h: float, p7d: float) -> bool:
        return (p1h * p24h > 0) and (p7d == 0 or p24h * p7d > 0)

    def _analyze_volume_profile(self, current_vol: float, vol_change: float, history: deque) -> float:
        avg_vol = float(np.mean(history)) if history else current_vol
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        vol_trend = 1.0 if vol_change > 0 else 0.6
        score = min(1.0, max(0.0, (vol_ratio - 0.8)/2.0*0.7 + vol_trend*0.3))
        return score

    def _detect_divergence(self, price: float, rsi: float, history: deque) -> str:
        if len(history) < 10:
            return "none"
        recent = list(history)[-10:]
        if price > max(recent) and rsi < 65:
            return "bearish"
        if price < min(recent) and rsi > 35:
            return "bullish"
        return "none"

    def _analyze_bb_position(self, price: float, bb_upper: Optional[float], bb_lower: Optional[float]) -> float:
        if not bb_upper or not bb_lower or bb_upper == bb_lower:
            return 0.5
        pos = (price - bb_lower) / (bb_upper - bb_lower)
        distance_from_middle = abs(pos - 0.5)
        score = max(0.0, min(1.0, 1.0 - distance_from_middle * 1.5))
        return score

    def _calculate_acceleration(self, token: str, p1h: float, p24h: float) -> float:
        expected_1h = p24h / 24
        return (p1h - expected_1h) / abs(expected_1h) if expected_1h != 0 else 0

    def _compute_scores(self, vol, liq, momentum_24h, rsi, p1h, p24h, p7d, acceleration, volume_score, divergence_type, bb_score, mcap, macd_bullish, regime) -> Dict[str, float]:
        return {
            "volume": self._normalize(vol, 100_000, 1_000_000),
            "liquidity": self._normalize(liq, 50_000, 500_000),
            "momentum": self._normalize(momentum_24h, 0.02, 0.25),
            "rsi": 1.0 - abs(rsi - 50) / 50,
            "timeframe": self._calculate_timeframe_score(p1h, p24h, p7d),
            "regime": {"trending": 1.0, "volatile": 0.7, "ranging": 0.5}.get(regime, 0.6),
            "acceleration": self._normalize(acceleration, 0, 2.0),
            "volume_profile": volume_score,
            "divergence": {"bullish": 1.0, "none": 0.7, "bearish": 0.2}.get(divergence_type, 0.5),
            "bb_position": bb_score,
            "market_cap": self._calculate_mcap_score(mcap),
            "macd": 1.0 if macd_bullish else 0.3
        }

    def _get_weights_for_regime(self, regime: str) -> Dict[str, float]:
        if regime == "trending":
            return {"volume":0.12,"liquidity":0.08,"momentum":0.20,"rsi":0.05,"timeframe":0.15,"regime":0.10,"acceleration":0.12,"volume_profile":0.08,"macd":0.05,"divergence":0.03,"bb_position":0.01,"market_cap":0.01}
        elif regime == "volatile":
            return {"volume":0.15,"liquidity":0.12,"momentum":0.15,"rsi":0.10,"timeframe":0.10,"regime":0.08,"acceleration":0.10,"volume_profile":0.10,"macd":0.05,"divergence":0.03,"bb_position":0.01,"market_cap":0.01}
        else:
            return {"volume":0.10,"liquidity":0.10,"momentum":0.15,"rsi":0.15,"timeframe":0.10,"regime":0.10,"acceleration":0.08,"volume_profile":0.08,"macd":0.08,"divergence":0.04,"bb_position":0.01,"market_cap":0.01}

    def _get_regime_performance(self, regime: str) -> float:
        history = self.performance_by_regime.get(regime, [])
        if not history:
            return 0.8
        avg_perf = np.mean(history)
        return max(0.5, min(1.0, avg_perf))

    def _calculate_timeframe_score(self, p1h: float, p24h: float, p7d: float) -> float:
        return (abs(p1h)*0.2 + abs(p24h)*0.5 + abs(p7d)*0.3) / 0.25  # scaled

    def _calculate_mcap_score(self, mcap: float) -> float:
        if mcap > 500_000_000:
            return 1.0
        elif mcap > 50_000_000:
            return 0.7
        elif mcap > 10_000_000:
            return 0.5
        return 0.3

    def _compute_position_and_risk(self, price, confidence, volatility, regime, momentum_24h, momentum_score):
        # Confidence-based sizing
        vol_adj = 1.0 / max(volatility, 0.5)
        size = min(confidence * vol_adj, self.risk_profile().max_position_size)
        stop_loss_pct = 0.02 * vol_adj
        take_profit_multiplier = max(1.5, momentum_score * 3)
        stop_loss = price * (1 - stop_loss_pct)
        take_profit = price * (1 + stop_loss_pct * take_profit_multiplier)
        signal_type_enum = DecisionAction.BUY if momentum_24h > 0 else DecisionAction.HOLD
        return size, stop_loss, take_profit, signal_type_enum, take_profit_multiplier

    def _get_regime_thresholds(self, config: Dict[str, Any], regime: str) -> Dict[str, float]:
        base = {
            "min_vol": 50_000,
            "min_liq": 20_000,
            "min_market_cap": 10_000_000,
            "min_price_change": 0.01,
            "max_price_change": 0.5,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "min_confidence": 0.35,
            "require_momentum_alignment": True,
            "require_macd_confirmation": True,
            "min_acceleration": -0.5
        }
        return {**base, **(config.get("regimes", {}).get(regime, {}))}

    def _normalize(self, val: float, min_val: float, max_val: float) -> float:
        if min_val == max_val:
            return 0.0
        return max(0.0, min(1.0, (val - min_val) / (max_val - min_val)))

    def _track_signal(self, decision: StrategyDecision, regime: str):
        self.performance_by_regime.setdefault(regime, []).append(decision.confidence)
        self.momentum_signals.append((decision, datetime.now()))

