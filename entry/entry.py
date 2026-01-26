"""
Entry Manager
-------------
Production-grade entry strategy engine for evaluating trade entry opportunities.
Handles opportunity assessment, signal generation, and entry decision making.

Version: 1.1.0
Author: Trading System
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging
import math
from datetime import datetime, timezone

import numpy as np

from .policy import EntryPolicy, get_default_policy
from .verdict import EntryVerdict, EntryAssessment

logger = logging.getLogger(__name__)


class EntrySignalStrength(Enum):
    NONE = 0
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


@dataclass(frozen=True)
class EntryFeatures:
    liquidity_score: float
    volume_momentum: float
    volatility_index: float
    rsi: float
    market_cap_tier: int
    macd_signal: float
    bollinger_position: float
    volume_profile_strength: float
    order_book_imbalance: float
    social_momentum: float
    holder_concentration: float
    whale_activity: float
    time_of_day_factor: float
    market_regime: int
    rugpull_risk_score: float
    smart_money_flow: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EntryManager:
    """Evaluates trade entry opportunities."""

    SCORE_WEIGHTS: Dict[str, float] = {
        "liquidity_score": 0.20,
        "volume_momentum": 0.15,
        "volatility_index": 0.10,
        "rsi": 0.10,
        "market_cap_tier": 0.08,
        "macd_signal": 0.08,
        "volume_profile_strength": 0.07,
        "order_book_imbalance": 0.06,
        "social_momentum": 0.06,
        "smart_money_flow": 0.05,
        "time_of_day_factor": 0.03,
        "rugpull_risk_score": 0.02,
    }

    def __init__(self, config: Dict[str, Any], policy: Optional[EntryPolicy] = None):
        self.config = config
        self.policy = policy or get_default_policy()
        self.max_history = int(config.get("max_history", 1000))
        # FIX: Read from entry config section, not root level
        entry_config = config.get("entry", {}) if isinstance(config, dict) else {}
        self.min_liquidity = float(entry_config.get("min_liquidity", 10_000))
        self.min_volume = float(entry_config.get("min_volume", 5_000))
        self.evaluation_history: List[EntryAssessment] = []

        if not math.isclose(sum(self.SCORE_WEIGHTS.values()), 1.0, rel_tol=1e-6):
            raise ValueError("Entry score weights must sum to 1.0")

        logger.info("EntryManager initialized with policy: %s", self.policy.name)

    # ------------------------------------------------------------------ PUBLIC

    def assess_opportunity(self, opportunity_id: str, data: Dict[str, Any]) -> EntryAssessment:
        try:
            validation = self._validate_opportunity(data)
            if not validation["passed"]:
                return self._reject(validation["reason"], metadata=validation)

            features = self._extract_features(data)

            policy_block = self._policy_hard_gates(features)
            if policy_block:
                return self._reject(policy_block, features)

            assessment = self._evaluate_features(features, opportunity_id)
            self._store_history(assessment)
            return assessment

        except Exception as exc:
            logger.exception("Entry assessment failed for %s", opportunity_id)
            return EntryAssessment(
                verdict=EntryVerdict.ERROR,
                reason=str(exc),
                confidence=0.0,
                signal_strength=EntrySignalStrength.NONE.name,
            )

    # ---------------------------------------------------------------- INTERNAL

    def _reject(self, reason: str, features: Optional[Any] = None, metadata: Optional[Dict] = None):
        return EntryAssessment(
            verdict=EntryVerdict.REJECT,
            reason=reason,
            confidence=0.0,
            signal_strength=EntrySignalStrength.NONE.name,
            metadata={
                "features": features.to_dict() if hasattr(features, "to_dict") else None,
                "details": metadata,
            },
        )

    def _store_history(self, assessment: EntryAssessment):
        self.evaluation_history.append(assessment)
        if len(self.evaluation_history) > self.max_history:
            self.evaluation_history = self.evaluation_history[-self.max_history :]

    # --------------------------------------------------------------- VALIDATION

    def _validate_opportunity(self, data: Dict[str, Any]) -> Dict[str, Any]:
        price = float(data.get("price", 0))
        liquidity = float(data.get("liquidity", 0))
        volume_24h = float(data.get("volume_24h", 0))

        if price <= 0:
            return {"passed": False, "reason": "Invalid price"}

        if liquidity < self.min_liquidity:
            return {"passed": False, "reason": f"Liquidity below minimum ({liquidity:.0f})"}

        if volume_24h < self.min_volume:
            return {"passed": False, "reason": f"Volume below minimum ({volume_24h:.0f})"}

        return {"passed": True}

    def _policy_hard_gates(self, features: EntryFeatures) -> Optional[str]:
        # Use getattr with defaults for missing policy attributes
        max_rugpull_risk = getattr(self.policy, 'max_rugpull_risk', 0.8)
        max_holder_concentration = getattr(self.policy, 'max_holder_concentration', 0.8)
        
        if features.rugpull_risk_score >= max_rugpull_risk:
            return "Rejected by policy: excessive rugpull risk"

        if features.holder_concentration >= max_holder_concentration:
            return "Rejected by policy: holder concentration too high"

        return None

    # ------------------------------------------------------------- FEATURE EXTR

    def _extract_features(self, data: Dict[str, Any]) -> EntryFeatures:
        return EntryFeatures(
            liquidity_score=self._liquidity_score(data),
            volume_momentum=self._volume_momentum(data.get("volume_history", [])),
            volatility_index=self._volatility(data.get("price_history", [])),
            rsi=self._normalize(data.get("rsi", 50) / 100),
            market_cap_tier=self._market_cap_tier(data.get("market_cap", 0)),
            macd_signal=self._macd(data.get("price_history", [])),
            bollinger_position=self._bollinger(data),
            volume_profile_strength=self._normalize(data.get("volume_profile", 0.5)),
            order_book_imbalance=self._order_book(data),
            social_momentum=self._normalize(data.get("social_score", 0.5)),
            holder_concentration=self._normalize(data.get("holder_concentration", 0.5)),
            whale_activity=self._normalize(data.get("whale_activity", 0.0)),
            time_of_day_factor=self._time_factor(),
            market_regime=int(data.get("market_regime", 0)),
            rugpull_risk_score=self._normalize(data.get("rugpull_risk", 0.0)),
            smart_money_flow=self._normalize(data.get("smart_money_flow", 0.0)),
        )

    # --------------------------------------------------------------- CALCULATORS

    @staticmethod
    def _normalize(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return float(np.clip(x, lo, hi))

    def _liquidity_score(self, data: Dict[str, Any]) -> float:
        liquidity = float(data.get("liquidity", 0))
        volume = float(data.get("volume_24h", 0))
        if liquidity <= 0 or volume <= 0:
            return 0.0
        ratio = math.log1p(liquidity) / math.log1p(volume)
        return self._normalize(1 / (1 + math.exp(-5 * (ratio - 1))))

    def _volume_momentum(self, volumes: List[float]) -> float:
        if len(volumes) < 2:
            return 0.5
        recent = np.array(volumes[-5:], dtype=float)
        avg = np.mean(recent)
        return self._normalize(np.mean(recent[-3:]) / avg if avg > 0 else 0.5)

    def _volatility(self, prices: List[float]) -> float:
        if len(prices) < 2:
            return 0.5
        returns = np.diff(np.log(np.array(prices[-20:], dtype=float)))
        return self._normalize(np.std(returns) * 10)

    def _macd(self, prices: List[float]) -> float:
        if len(prices) < 26:
            return 0.0
        # Simplified MACD calculation without pandas
        prices_arr = np.array(prices, dtype=float)
        # Exponential moving averages using numpy
        ema12 = self._ema(prices_arr, 12)
        ema26 = self._ema(prices_arr, 26)
        macd = ema12 - ema26
        signal = self._ema(macd, 9)
        return self._normalize(macd[-1] - signal[-1], -1, 1)

    def _bollinger(self, data: Dict[str, Any]) -> float:
        prices = data.get("price_history", [])
        price = float(data.get("price", 0))
        if len(prices) < 20:
            return 0.5
        arr = np.array(prices[-20:], dtype=float)
        std = np.std(arr)
        if std == 0:
            return 0.5
        lower, upper = np.mean(arr) - 2 * std, np.mean(arr) + 2 * std
        return self._normalize((price - lower) / (upper - lower))

    def _order_book(self, data: Dict[str, Any]) -> float:
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        if not bids or not asks:
            return 0.0
        bid_vol = sum(bids[:10])
        ask_vol = sum(asks[:10])
        total = bid_vol + ask_vol
        return self._normalize((bid_vol - ask_vol) / total, -1, 1) if total > 0 else 0.0

    def _time_factor(self) -> float:
        hour = datetime.now(timezone.utc).hour
        return 1.0 if 9 <= hour <= 16 else 0.7 if 6 <= hour <= 20 else 0.4

    @staticmethod
    def _market_cap_tier(cap: float) -> int:
        # Handle None or invalid values
        if cap is None or not isinstance(cap, (int, float)) or cap <= 0:
            return 0
        if cap >= 10_000_000:
            return 3
        if cap >= 1_000_000:
            return 2
        if cap >= 100_000:
            return 1
        return 0

    # --------------------------------------------------------------- SCORING

    def _evaluate_features(self, f: EntryFeatures, opportunity_id: str) -> EntryAssessment:
        # Detect if we have limited historical data (many indicators at default/neutral values)
        has_limited_data = (
            f.volume_momentum == 0.5 or  # Default when history < 2
            f.volatility_index == 0.5 or  # Default when history < 2
            f.macd_signal == 0.0 or  # Default when history < 26
            f.order_book_imbalance == 0.0  # Default when no order book data
        )
        
        # When historical data is limited, be more lenient with scoring
        # Boost neutral indicators slightly to account for missing data
        volume_momentum_score = f.volume_momentum
        volatility_score = (1 - f.volatility_index)
        macd_score = max(0, f.macd_signal)
        order_book_score = max(0, f.order_book_imbalance)
        
        if has_limited_data:
            # When data is limited, give moderate boost to neutral indicators
            # This prevents penalizing opportunities just because we lack historical data
            # The boost helps compensate for missing technical indicators
            if volume_momentum_score == 0.5:
                volume_momentum_score = 0.65  # Moderate positive bias
            if volatility_score == 0.5:
                volatility_score = 0.60  # Moderate positive bias  
            if macd_score == 0.0:
                macd_score = 0.15  # Small positive signal
            if order_book_score == 0.0:
                order_book_score = 0.10  # Small positive signal
            logger.debug(
                f"Adjusted scores for limited data: volume_momentum={volume_momentum_score:.2f}, "
                f"volatility={volatility_score:.2f}, macd={macd_score:.2f}, order_book={order_book_score:.2f}"
            )
        
        score = (
            self.SCORE_WEIGHTS["liquidity_score"] * f.liquidity_score +
            self.SCORE_WEIGHTS["volume_momentum"] * volume_momentum_score +
            self.SCORE_WEIGHTS["volatility_index"] * volatility_score +
            self.SCORE_WEIGHTS["rsi"] * f.rsi +
            self.SCORE_WEIGHTS["market_cap_tier"] * (f.market_cap_tier / 3) +
            self.SCORE_WEIGHTS["macd_signal"] * macd_score +
            self.SCORE_WEIGHTS["volume_profile_strength"] * f.volume_profile_strength +
            self.SCORE_WEIGHTS["order_book_imbalance"] * order_book_score +
            self.SCORE_WEIGHTS["social_momentum"] * f.social_momentum +
            self.SCORE_WEIGHTS["smart_money_flow"] * max(0, f.smart_money_flow) +
            self.SCORE_WEIGHTS["time_of_day_factor"] * f.time_of_day_factor +
            self.SCORE_WEIGHTS["rugpull_risk_score"] * (1 - f.rugpull_risk_score)
        )

        score = self._normalize(score)
        
        # For paper trading or when data is limited, use more lenient thresholds
        # Check if we're in a mode that should be more permissive
        # (This will be enhanced when trading mode is passed to entry manager)
        effective_approval_threshold = self.policy.approval_threshold
        effective_strong_threshold = self.policy.strong_entry_threshold
        
        if has_limited_data:
            # When historical data is missing, be much more lenient
            # Reduce thresholds significantly to account for missing indicators
            # This allows opportunities to pass when we have good liquidity/volume but lack history
            effective_approval_threshold = max(0.35, self.policy.approval_threshold * 0.70)
            effective_strong_threshold = max(0.55, self.policy.strong_entry_threshold * 0.75)
            logger.info(
                f"Limited historical data detected for {opportunity_id}. "
                f"Using adjusted thresholds: approval={effective_approval_threshold:.2%} "
                f"(was {self.policy.approval_threshold:.2%}), "
                f"strong={effective_strong_threshold:.2%} (was {self.policy.strong_entry_threshold:.2%})"
            )

        verdict = (
            EntryVerdict.APPROVE if score >= effective_strong_threshold else
            EntryVerdict.CONDITIONAL if score >= effective_approval_threshold else
            EntryVerdict.REVIEW if score >= self.policy.review_threshold else
            EntryVerdict.REJECT
        )
        
        reason = f"Entry score {score:.2%}"
        if has_limited_data:
            reason += " (limited historical data - adjusted thresholds applied)"

        return EntryAssessment(
            verdict=verdict,
            reason=reason,
            confidence=score,
            signal_strength=self._signal_strength(score),
            metadata={
                "opportunity_id": opportunity_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "features": f.to_dict(),
                "has_limited_data": has_limited_data,
                "effective_thresholds": {
                    "approval": effective_approval_threshold,
                    "strong": effective_strong_threshold,
                },
            },
        )

    @staticmethod
    def _signal_strength(score: float) -> str:
        if score < 0.55:
            return EntrySignalStrength.NONE.name
        if score < 0.65:
            return EntrySignalStrength.WEAK.name
        if score < 0.75:
            return EntrySignalStrength.MODERATE.name
        if score < 0.85:
            return EntrySignalStrength.STRONG.name
        return EntrySignalStrength.VERY_STRONG.name


def create_entry_manager(config: Dict[str, Any], policy: Optional[EntryPolicy] = None) -> EntryManager:
    """Factory function to create an EntryManager instance."""
    return EntryManager(config, policy)

