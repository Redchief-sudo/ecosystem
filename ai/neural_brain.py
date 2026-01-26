from enum import Enum
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class SignalQuality(Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXCELLENT = "excellent"


class ConfidenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class NeuralBrain:
    """
    Generates TradeIntents based purely on strategy signal quality.

    NO risk reasoning
    NO portfolio awareness
    NO sizing in dollars
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        self.signal_thresholds = config.get("signal_thresholds", {
            "min_confidence": 0.3,
            "excellent_threshold": 0.8,
            "strong_threshold": 0.6,
            "moderate_threshold": 0.4,
        })

        self.strategy_weights = config.get("strategy_weights", {
            "technical": 0.4,
            "fundamental": 0.3,
            "sentiment": 0.2,
            "order_flow": 0.1,
        })

        logger.info("NeuralBrain initialized")

    # -------------------------
    # Public API
    # -------------------------

    def evaluate_signal(
        self,
        market_data: Dict[str, Any],
        strategy_signals: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        if self.fail_fast(market_data):
            return None

        signal_quality = self._assess_signal_quality(market_data, strategy_signals)

        if signal_quality["confidence"] < self.signal_thresholds["min_confidence"]:
            return None

        direction = self._determine_direction(strategy_signals)
        if direction is None:
            return None

        intent = self._generate_standardized_intent(
            market_data,
            strategy_signals,
            signal_quality,
            direction,
        )

        self._log_signal_reasoning(intent, signal_quality)
        return intent

    # -------------------------
    # Core Evaluation
    # -------------------------

    def _assess_signal_quality(
        self,
        market_data: Dict[str, Any],
        strategy_signals: Dict[str, Any],
    ) -> Dict[str, Any]:

        weighted_sum = 0.0
        active_weight = 0.0
        factors: List[str] = []

        def apply(name: str, score: float):
            nonlocal weighted_sum, active_weight
            weight = self.strategy_weights.get(name, 0.0)
            if weight > 0:
                weighted_sum += score * weight
                active_weight += weight
                factors.append(f"{name}:{score:.2f}")

        if "technical" in strategy_signals:
            apply("technical", self._evaluate_technical_signals(strategy_signals["technical"]))

        if "fundamental" in strategy_signals:
            apply("fundamental", self._evaluate_fundamental_signals(strategy_signals["fundamental"]))

        if "sentiment" in strategy_signals:
            apply("sentiment", self._evaluate_sentiment_signals(strategy_signals["sentiment"]))

        if "order_flow" in strategy_signals:
            apply("order_flow", self._evaluate_order_flow_signals(strategy_signals["order_flow"]))

        confidence = weighted_sum / active_weight if active_weight > 0 else 0.0

        if confidence >= self.signal_thresholds["excellent_threshold"]:
            quality = SignalQuality.EXCELLENT
            level = ConfidenceLevel.VERY_HIGH
        elif confidence >= self.signal_thresholds["strong_threshold"]:
            quality = SignalQuality.STRONG
            level = ConfidenceLevel.HIGH
        elif confidence >= self.signal_thresholds["moderate_threshold"]:
            quality = SignalQuality.MODERATE
            level = ConfidenceLevel.MEDIUM
        else:
            quality = SignalQuality.WEAK
            level = ConfidenceLevel.LOW

        return {
            "confidence": round(confidence, 4),
            "quality": quality,
            "confidence_level": level,
            "factors": factors,
            "market_conditions": self._extract_market_conditions(market_data),
        }

    # -------------------------
    # Signal Evaluation Methods
    # -------------------------

    def _evaluate_technical_signals(self, technical_signals: Dict[str, Any]) -> float:
        """Evaluate technical signals and return a score between 0 and 1."""
        if not technical_signals:
            return 0.0

        score = 0.0
        factors = 0

        # Trend strength
        trend = technical_signals.get("trend")
        if trend == "bullish":
            score += 0.8
        elif trend == "bearish":
            score += 0.2
        elif trend == "neutral":
            score += 0.5
        factors += 1

        # Momentum indicators
        rsi = technical_signals.get("rsi")
        if rsi is not None:
            if 30 <= rsi <= 70:
                score += 0.5
            elif rsi < 30:
                score += 0.8  # Oversold
            else:
                score += 0.2  # Overbought
            factors += 1

        # Moving averages
        ma_signal = technical_signals.get("ma_signal")
        if ma_signal == "golden_cross":
            score += 0.9
            factors += 1
        elif ma_signal == "death_cross":
            score += 0.1
            factors += 1

        return score / factors if factors > 0 else 0.0

    def _evaluate_fundamental_signals(self, fundamental_signals: Dict[str, Any]) -> float:
        """Evaluate fundamental signals and return a score between 0 and 1."""
        if not fundamental_signals:
            return 0.0

        score = 0.0
        factors = 0

        # Market outlook
        outlook = fundamental_signals.get("outlook")
        if outlook == "positive":
            score += 0.8
        elif outlook == "negative":
            score += 0.2
        elif outlook == "neutral":
            score += 0.5
        factors += 1

        # Valuation metrics
        pe_ratio = fundamental_signals.get("pe_ratio")
        if pe_ratio is not None:
            if pe_ratio < 15:
                score += 0.8  # Undervalued
            elif pe_ratio > 25:
                score += 0.3  # Overvalued
            else:
                score += 0.6  # Fairly valued
            factors += 1

        return score / factors if factors > 0 else 0.0

    def _evaluate_sentiment_signals(self, sentiment_signals: Dict[str, Any]) -> float:
        """Evaluate sentiment signals and return a score between 0 and 1."""
        if not sentiment_signals:
            return 0.0

        # Overall sentiment score (assuming 0-1 scale)
        overall_score = sentiment_signals.get("overall_score", 0.5)
        return min(max(overall_score, 0.0), 1.0)

    def _evaluate_order_flow_signals(self, order_flow_signals: Dict[str, Any]) -> float:
        """Evaluate order flow signals and return a score between 0 and 1."""
        if not order_flow_signals:
            return 0.0

        score = 0.0
        factors = 0

        # Buy/sell pressure
        buy_pressure = order_flow_signals.get("buy_pressure", 0.5)
        sell_pressure = order_flow_signals.get("sell_pressure", 0.5)

        if buy_pressure > sell_pressure:
            score += 0.8
        elif sell_pressure > buy_pressure:
            score += 0.2
        else:
            score += 0.5
        factors += 1

        # Large orders
        large_orders = order_flow_signals.get("large_orders_ratio", 0.5)
        score += large_orders
        factors += 1

        return score / factors if factors > 0 else 0.0

    # -------------------------
    # Helper Methods
    # -------------------------

    def _extract_market_conditions(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant market conditions from market data."""
        return {
            "price": market_data.get("price"),
            "volume_24h": market_data.get("volume_24h"),
            "market_cap": market_data.get("market_cap"),
            "volatility": market_data.get("volatility"),
            "liquidity": market_data.get("liquidity"),
        }

    def _extract_trigger_conditions(self, strategy_signals: Dict[str, Any]) -> List[str]:
        """Extract conditions that triggered the signal."""
        conditions = []

        if "technical" in strategy_signals:
            tech = strategy_signals["technical"]
            if tech.get("trend") in ["bullish", "bearish"]:
                conditions.append(f"trend_{tech['trend']}")
            if tech.get("rsi"):
                conditions.append(f"rsi_{tech['rsi']:.1f}")

        if "fundamental" in strategy_signals:
            fund = strategy_signals["fundamental"]
            if fund.get("outlook"):
                conditions.append(f"outlook_{fund['outlook']}")

        if "sentiment" in strategy_signals:
            sent = strategy_signals["sentiment"]
            if sent.get("overall_score"):
                conditions.append(f"sentiment_{sent['overall_score']:.2f}")

        return conditions

    # -------------------------
    # Direction & Size
    # -------------------------

    def _determine_direction(self, strategy_signals: Dict[str, Any]) -> Optional[str]:
        buy = 0
        sell = 0

        tech = strategy_signals.get("technical", {})
        if tech.get("trend") == "bullish":
            buy += 1
        elif tech.get("trend") == "bearish":
            sell += 1

        fund = strategy_signals.get("fundamental", {})
        if fund.get("outlook") == "positive":
            buy += 1
        elif fund.get("outlook") == "negative":
            sell += 1

        sentiment = strategy_signals.get("sentiment", {})
        s = sentiment.get("overall_score")
        if s is not None:
            if s > 0.6:
                buy += 1
            elif s < 0.4:
                sell += 1

        if buy == sell:
            return None

        return "buy" if buy > sell else "sell"

    def _calculate_abstract_size(self, confidence: float) -> str:
        if confidence >= 0.8:
            return "large_unit"
        if confidence >= 0.6:
            return "medium_unit"
        if confidence >= 0.4:
            return "small_unit"
        return "micro_unit"

    # -------------------------
    # Intent Construction
    # -------------------------

    def _generate_standardized_intent(
        self,
        market_data: Dict[str, Any],
        strategy_signals: Dict[str, Any],
        signal_quality: Dict[str, Any],
        direction: str,
    ) -> Dict[str, Any]:

        return {
            "direction": direction,
            "instrument": {
                "token_address": market_data["token_address"],
                "symbol": market_data["symbol"],
                "chain": market_data["chain"],
            },
            "confidence": signal_quality["confidence"],
            "confidence_level": signal_quality["confidence_level"],
            "signal_quality": signal_quality["quality"],
            "abstract_size": self._calculate_abstract_size(signal_quality["confidence"]),
            "market_conditions": signal_quality["market_conditions"],
            "strategy_signals": strategy_signals,
            "generated_at": market_data.get("timestamp"),
            "reasoning": {
                "factors": signal_quality["factors"],
                "conditions_triggered": self._extract_trigger_conditions(strategy_signals),
            },
        }

    # -------------------------
    # Guards
    # -------------------------

    def fail_fast(self, market_data: Dict[str, Any]) -> bool:
        for key in ("token_address", "symbol", "chain", "price"):
            if not market_data.get(key):
                return True
        return market_data.get("price", 0) <= 0

    # -------------------------
    # Logging
    # -------------------------

    def _log_signal_reasoning(self, intent: Dict[str, Any], quality: Dict[str, Any]) -> None:
        logger.info(
            "NeuralBrain intent generated | %s %s | confidence=%.3f | size=%s",
            intent["direction"].upper(),
            intent["instrument"]["symbol"],
            quality["confidence"],
            intent["abstract_size"],
        )

