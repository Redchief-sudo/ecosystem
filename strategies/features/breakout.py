# trade_strategies/elite_breakout_strategy_v2.py
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple

import numpy as np

from strategies.base_strategy import BaseStrategy, SignalType, RiskProfile
from strategies.data_classes import StrategyDecision, DecisionAction, Rationale

logger = logging.getLogger("strategies.elite_breakout_v2")

class EliteBreakoutStrategyV2(BaseStrategy):
    """
    Elite Breakout Strategy v2
    Aggressive breakout logic with:
    - volatility regime detection
    - multi-timeframe momentum confirmation
    - volume profile validation
    - false breakout suppression
    - confluence scoring
    - bounded confidence & risk controls
    """

    IS_STRATEGY = True
    STRATEGY_NAME = "breakout_v2"

    # ------------------------------------------------------------------
    # REQUIRED PROPERTIES
    # ------------------------------------------------------------------
    @property
    def strategy_id(self) -> str:
        return "elite_breakout_v2"

    @property
    def description(self) -> str:
        return "Advanced breakout strategy v2 using volatility, volume, multi-timeframe momentum, and confluence."

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def risk_profile(self) -> RiskProfile:
        return RiskProfile.AGGRESSIVE

    @property
    def signal_type(self) -> SignalType:
        return SignalType.BUY

    @property
    def required_features(self) -> List[str]:
        return [
            "price", "volume_24h", "price_change_24h", "price_change_7d",
            "high_24h", "low_24h", "volatility", "volume_7d_avg"
        ]

    @property
    def supported_markets(self) -> List[str]:
        return ["crypto"]

    @property
    def timeframes(self) -> List[str]:
        return ["5m", "15m", "1h"]

    @property
    def warmup_period(self) -> int:
        return 50

    # ------------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.breakout_history: Dict[str, List[Tuple[float, float, float]]] = {}
        self.volatility_history: Dict[str, List[float]] = {}
        self.hot_symbols: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # MAIN EVALUATION ENTRYPOINT
    # ------------------------------------------------------------------
    async def evaluate_token(self, token_data: Dict) -> Optional[dict]:
        """Evaluate token using breakout strategy."""
        try:
            c = self.strategy_config or {}
            symbol = token_data.get("symbol", "UNKNOWN")
            price = self._safe(token_data, "price")
            vol24 = self._safe(token_data, "volume_24h")
            change_24h = self._safe(token_data, "price_change_24h")
            change_7d = self._safe(token_data, "price_change_7d", 0.0)
            volatility = max(self._safe(token_data, "volatility", 1.0), 0.1)
            high_24h = self._safe(token_data, "high_24h", price)
            low_24h = self._safe(token_data, "low_24h", price)
            vol_7d_avg = max(self._safe(token_data, "volume_7d_avg", vol24 or 1.0), 1.0)

            if not price or not vol24 or not change_24h:
                return None

            # 1. Volatility regime
            regime = self._detect_volatility_regime(symbol, volatility)
            if regime == "extreme":
                return None

            # 2. Multi-timeframe momentum
            mtf_score = self._multi_timeframe_score(change_24h, change_7d)
            if mtf_score < c.get("min_mtf_score", 0.35):
                return None

            # 3. Volume profile
            volume_score = self._volume_profile_score(vol24, vol_7d_avg, change_24h)
            if volume_score < c.get("min_volume_profile", 0.4):
                return None

            # 4. Breakout quality
            quality = self._breakout_quality(price, high_24h, low_24h, change_24h, vol24, vol_7d_avg)
            if quality < c.get("min_breakout_quality", 0.5):
                return None

            # 5. False breakout filter
            if self._false_breakout(symbol, change_24h, volume_score):
                return None

            # 6. Confluence scoring
            confluence = self._confluence(quality, mtf_score, volume_score)

            # 7. Confidence computation
            confidence = np.clip(
                0.5 * quality + 0.3 * mtf_score + 0.2 * volume_score,
                0.0,
                0.95,
            )
            confidence *= self._regime_multiplier(regime)
            if confidence < c.get("min_confidence", 0.35):
                return None

            # 8. Position sizing
            size = self._position_size(confidence, volatility, quality)

            # 9. Risk targets
            stop_pct = self._stop_loss(volatility, quality, regime)
            tp_pct = self._take_profit(change_24h, confidence, regime)
            stop_loss = price * (1 - stop_pct)
            take_profit = price * (1 + tp_pct)

            self._record_breakout(symbol, price, change_24h)
            self._update_hot_symbols(symbol, confidence)

            return self._create_signal(
                SignalType.BUY,
                confidence,
                price,
                size,
                stop_loss,
                take_profit,
                {
                    "quality": round(quality, 3),
                    "mtf_score": round(mtf_score, 3),
                    "volume_score": round(volume_score, 3),
                    "confluence": round(confluence, 3),
                    "regime": regime,
                    "is_hot": symbol in self.hot_symbols
                },
            )
        except Exception as e:
            logger.error("[EliteBreakoutV2] evaluation error", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # INTERNAL LOGIC
    # ------------------------------------------------------------------
    def _detect_volatility_regime(self, symbol: str, vol: float) -> str:
        hist = self.volatility_history.setdefault(symbol, [])
        hist.append(vol)
        if len(hist) > 20:
            hist[:] = hist[-20:]
        if len(hist) < 5:
            return "normal"
        avg, std = np.mean(hist), np.std(hist)
        if vol > avg + 2 * std:
            return "extreme"
        if vol > avg + std:
            return "high"
        if vol < max(avg - std, 0.1):
            return "low"
        return "normal"

    def _multi_timeframe_score(self, d1, d7):
        st = self._normalize(abs(d1), 0.5, 5.0)
        mt = self._normalize(abs(d7), 2.0, 15.0)
        alignment = 1.25 if d1 * d7 > 0 else 1.0
        return np.clip((0.6 * st + 0.4 * mt) * alignment, 0, 1)

    def _volume_profile_score(self, v24, v7, strength):
        ratio = v24 / v7
        surge = self._normalize(ratio, 1.0, 3.0)
        corr = min(abs(strength) * ratio / 10, 1.0)
        return np.clip(0.6 * surge + 0.4 * corr, 0, 1)

    def _breakout_quality(self, price, high, low, strength, v24, v7):
        rng = max(high - low, price * 0.01)
        magnitude = self._normalize(abs(strength) / 100, 0.5, 5.0)
        volume = min(v24 / (v7 * 1.5), 1.0)
        position = (price - low) / rng if strength > 0 else (high - price) / rng
        accel = min(abs(strength) / 10, 1.0)
        return np.clip(0.35*magnitude + 0.30*volume + 0.20*position + 0.15*accel, 0, 1)

    def _false_breakout(self, symbol, strength, volume_score):
        history = self.breakout_history.get(symbol, [])
        for _, prev_strength, _ in history[-3:]:
            if prev_strength * strength < 0:
                return True
        return volume_score < 0.3

    def _confluence(self, quality, mtf, volume_score):
        arr = np.array([quality, mtf, volume_score])
        return np.mean(arr) * (1 - np.std(arr))

    def _regime_multiplier(self, regime):
        return {"low": 1.1, "normal": 1.0, "high": 0.85, "extreme": 0.7}.get(regime, 1.0)

    def _position_size(self, confidence, volatility, quality):
        cfg = self.strategy_config or {}
        base = cfg.get("base_position_size", 0.0015)
        max_size = cfg.get("max_position_size", 0.005)
        size = base * confidence * (0.8 + 0.4*quality) / volatility
        return min(size, max_size)

    def _stop_loss(self, volatility, quality, regime):
        base = self.strategy_config.get("stop_loss_pct", 0.08)
        adj = volatility*0.02 - quality*0.01
        regime_adj = {"low": -0.01, "high": 0.02}.get(regime, 0)
        return np.clip(base + adj + regime_adj, 0.04, 0.15)

    def _take_profit(self, strength, confidence, regime):
        base = self.strategy_config.get("take_profit_pct", 0.15)
        tp = base*(1 + abs(strength)/10)*(0.8 + 0.4*confidence)
        return np.clip(tp*self._regime_multiplier(regime), 0.08, 0.40)

    def _record_breakout(self, symbol, price, strength):
        history = self.breakout_history.setdefault(symbol, [])
        history.append((price, strength, time.time()))
        if len(history) > 10:
            history[:] = history[-10:]

    def _update_hot_symbols(self, symbol, confidence):
        streak = self.hot_symbols.get(symbol, 0)
        if confidence > 0.7:
            self.hot_symbols[symbol] = streak + 1
        else:
            self.hot_symbols.pop(symbol, None)
        if len(self.hot_symbols) > 10:
            # Keep top 10 by streak
            sorted_syms = sorted(self.hot_symbols.items(), key=lambda x: x[1], reverse=True)
            self.hot_symbols = dict(sorted_syms[:10])

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        if max_val <= min_val:
            return 0.0
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


