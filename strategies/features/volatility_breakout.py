# trade_strategies/volatility_breakout_strategy.py

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set

import numpy as np

from ..base_strategy import BaseStrategy, SignalType, RiskProfile

logger = logging.getLogger("strategies.volatility_breakout")


class VolatilityRegime(Enum):
    COMPRESSED = "compressed"
    EXPANDING = "expanding"
    CHOPPY = "choppy"
    TRENDING = "trending"
    UNKNOWN = "unknown"


@dataclass
class CompressionState:
    start_time: datetime
    duration: int
    min_atr: float
    min_bb_width: float
    max_compression: float
    last_update: datetime
    invalidated: bool = False


class VolatilityBreakoutStrategy(BaseStrategy):
    IS_STRATEGY = True
    STRATEGY_NAME = "volatility_breakout"

    # ------------------------------------------------------------------
    # REQUIRED ABSTRACT PROPERTIES
    # ------------------------------------------------------------------

    @property
    def strategy_id(self) -> str:
        return "volatility_breakout_v1"

    @property
    def description(self) -> str:
        return "Volatility breakout strategy that detects compression periods and trades explosive moves when volatility expands."

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def risk_profile(self) -> RiskProfile:
        return RiskProfile(
            max_drawdown=0.15,
            max_concurrent_positions=5,
            volatility_tolerance=2.0,
            min_confidence_threshold=0.35,
            max_position_size=0.002,
            max_loss_per_trade=0.01,
            risk_per_trade=0.005
        )

    @property
    def signal_type(self) -> SignalType:
        return SignalType.BUY

    @property
    def required_features(self) -> Set[str]:
        return {"price", "volume_24h", "high_24h", "low_24h", "liquidity_usd"}

    @property
    def supported_markets(self) -> List[str]:
        return ["crypto"]

    @property
    def timeframes(self) -> List[str]:
        return ["5m", "15m", "1h"]

    @property
    def warmup_period(self) -> int:
        return 40

    # ------------------------------------------------------------------
    # EVALUATION METHOD (required by BaseStrategy)
    # ------------------------------------------------------------------

    async def evaluate(self, market_state: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Core evaluation method - wraps evaluate_token for backward compatibility.
        """
        return await self.evaluate_token(market_state)

    DEFAULTS = {
        "enabled": True,
        "min_volume_24h": 50_000,
        "min_liquidity": 50_000,
        "min_history": 40,
        "bb_period": 20,
        "bb_std": 2.0,
        "atr_period": 14,
        "compression_percentile": 20,
        "min_compression_score": 0.7,
        "volume_breakout_multiplier": 1.5,
        "min_strength": 0.6,
        "stop_atr_multiplier": 1.5,
        "target_atr_multiplier": 4.0,
        "max_position_size": 0.002,
        "min_confidence": 0.35,
        "max_squeeze_duration": 40,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.price = {}
        self.high = {}
        self.low = {}
        self.volume = {}
        self.squeezes: Dict[str, CompressionState] = {}

    # ============================================================
    # ENTRY POINT
    # ============================================================

    async def evaluate_token(self, o: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            c = {**self.DEFAULTS, **(self.strategy_config or {})}

            token = o.get("symbol") or o.get("id")
            if not token:
                return None

            self._update_history(token, o)

            if len(self.price[token]) < c["min_history"]:
                return None

            if o["volume_24h"] < c["min_volume_24h"] or o["liquidity_usd"] < c["min_liquidity"]:
                return None

            bb_width = self._bb_width(token, c)
            atr = self._atr(token, c)

            compression_score = self._compression_score(token, bb_width, atr, c)
            if compression_score < c["min_compression_score"]:
                return None

            breakout = self._detect_breakout(token, o["price"], atr, c)
            if not breakout:
                return None

            if not self._confirm_volume(token, o["volume_24h"], c):
                return None

            confidence = self._confidence(compression_score, breakout["strength"], self.squeezes[token].duration)
            if confidence < c["min_confidence"]:
                return None

            stop = o["price"] - atr * c["stop_atr_multiplier"]
            target = o["price"] + atr * c["target_atr_multiplier"]

            size = min(c["max_position_size"], confidence * c["max_position_size"])

            return self._create_signal(
                SignalType.BUY,
                confidence,
                o["price"],
                size,
                stop,
                target,
                {
                    "compression_score": compression_score,
                    "breakout_strength": breakout["strength"],
                    "atr": atr,
                    "bb_width": bb_width,
                    "duration": self.squeezes[token].duration,
                    "strategy_version": "2.0_true_volatility_breakout"
                }
            )

        except Exception as e:
            logger.error(f"[VolBreakout] Error: {e}", exc_info=True)
            return None

    # ============================================================
    # HISTORY
    # ============================================================

    def _update_history(self, token, o):
        for store, key in [
            (self.price, "price"),
            (self.high, "high_24h"),
            (self.low, "low_24h"),
            (self.volume, "volume_24h"),
        ]:
            store.setdefault(token, deque(maxlen=200))
            store[token].append(float(o.get(key, o["price"])))

    # ============================================================
    # TRUE INDICATORS
    # ============================================================

    def _atr(self, token, c):
        highs = list(self.high[token])
        lows = list(self.low[token])
        closes = list(self.price[token])

        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)

        period = c["atr_period"]
        return np.mean(trs[-period:])

    def _bb_width(self, token, c):
        prices = np.array(self.price[token][-c["bb_period"]:])
        mean = prices.mean()
        std = prices.std(ddof=0)
        return (2 * c["bb_std"] * std) / mean if mean > 0 else 0

    # ============================================================
    # COMPRESSION & BREAKOUT
    # ============================================================

    def _compression_score(self, token, bb_width, atr, c):
        hist_widths = []
        prices = list(self.price[token])

        for i in range(len(prices) - c["bb_period"]):
            w = np.std(prices[i:i + c["bb_period"]]) / np.mean(prices[i:i + c["bb_period"]])
            hist_widths.append(w)

        if not hist_widths:
            return 0

        threshold = np.percentile(hist_widths, c["compression_percentile"])
        score = max(0.0, min(1.0, threshold / bb_width)) if bb_width > 0 else 0

        state = self.squeezes.get(token)
        if score > 0.6:
            if not state:
                self.squeezes[token] = CompressionState(
                    start_time=datetime.utcnow(),
                    duration=1,
                    min_atr=atr,
                    min_bb_width=bb_width,
                    max_compression=score,
                    last_update=datetime.utcnow(),
                )
            else:
                state.duration += 1
                state.min_atr = min(state.min_atr, atr)
                state.min_bb_width = min(state.min_bb_width, bb_width)
                state.max_compression = max(state.max_compression, score)
                state.last_update = datetime.utcnow()
        else:
            self.squeezes.pop(token, None)

        return score

    def _detect_breakout(self, token, price, atr, c):
        prices = list(self.price[token])
        high = max(prices[-20:])
        strength = (price - high) / atr if atr > 0 else 0

        if strength <= 0:
            return None

        return {
            "direction": "BULLISH",
            "strength": min(1.0, strength / 2.0),
        }

    def _confirm_volume(self, token, vol, c):
        avg = np.mean(self.volume[token][-10:])
        return vol >= avg * c["volume_breakout_multiplier"]

    # ============================================================
    # CONFIDENCE
    # ============================================================

    def _confidence(self, compression, strength, duration):
        return min(
            1.0,
            0.4 * compression +
            0.4 * strength +
            0.2 * min(1.0, duration / 20),
        )

