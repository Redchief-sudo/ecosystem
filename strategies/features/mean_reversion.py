# trade_strategies/mean_reversion_strategy_v2.py
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from strategies.base_strategy import BaseStrategy, SignalType, TradeSignal, RiskProfile
from strategies.data_classes import StrategyDecision, DecisionAction, Rationale

logger = logging.getLogger("strategies.mean_reversion_v2")


class MeanReversionStrategyV2(BaseStrategy):
    """
    Elite Mean Reversion Strategy v2
    Aggressive/moderate mean reversion using:
    - AR(1) half-life estimation
    - Bollinger Bands
    - Hurst exponent regime filtering
    - Volatility-aware risk management
    - Bounded confidence & position sizing
    """

    IS_STRATEGY = True
    STRATEGY_NAME = "mean_reversion_v2"

    # ------------------------------------------------------------------
    # REQUIRED PROPERTIES
    # ------------------------------------------------------------------
    @property
    def strategy_id(self) -> str:
        return "elite_mean_reversion_v2"

    @property
    def description(self) -> str:
        return (
            "Statistical mean reversion v2 using AR(1) half-life, Bollinger Bands, "
            "Hurst regime filtering, and volatility-aware risk management."
        )

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def risk_profile(self) -> RiskProfile:
        return RiskProfile.MODERATE

    @property
    def signal_type(self) -> SignalType:
        return SignalType.BUY

    @property
    def required_features(self) -> List[str]:
        return ["price", "volume_24h", "symbol", "chain"]

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
        self.price_history: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # MAIN ENTRYPOINTS
    # ------------------------------------------------------------------
    async def evaluate(self, market_state: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[StrategyDecision]:
        """Evaluate market state using mean reversion strategy."""
        try:
            signal = await self.evaluate_token(market_state)
            if not signal:
                return None

            action = DecisionAction.BUY if signal.get("direction") == SignalType.BUY else DecisionAction.SELL

            return StrategyDecision(
                action=action,
                confidence=signal.get("confidence", 0.0),
                rationale=Rationale(
                    primary_signal=f"Mean reversion signal: zscore={signal['zscore']:.2f}",
                    supporting_factors=[
                        f"Half-life: {signal['half_life']:.1f}",
                        f"Hurst exponent: {signal['hurst']:.3f}",
                        f"Bollinger position: {(signal['price'] - signal['bollinger_mean']) / signal['bollinger_std']:.2f}σ"
                    ],
                    risk_factors=[
                        f"Stop loss: {signal['stop_loss_pct']:.1%}",
                        f"Target: {signal['take_profit_pct']:.1%}"
                    ]
                ),
                metadata={
                    "zscore": signal['zscore'],
                    "half_life": signal['half_life'],
                    "hurst": signal['hurst'],
                    "bollinger_mean": signal['bollinger_mean'],
                    "bollinger_std": signal['bollinger_std'],
                    "position_size": signal['position_size'],
                    "stop_loss": signal['stop_loss'],
                    "take_profit": signal['take_profit'],
                    "price": signal['price'],
                }
            )
        except Exception:
            logger.error("[MeanReversionV2] evaluation error", exc_info=True)
            return None

    async def evaluate_token(self, token_data: Dict[str, Any]) -> Optional[TradeSignal]:
        """Evaluate token using mean reversion strategy – returns TradeSignal."""
        try:
            c = self.strategy_config or {}
            symbol = token_data.get("symbol")
            price = self._safe(token_data, "price")
            volume = self._safe(token_data, "volume_24h", 0.0)

            if not symbol or not price or volume < c.get("min_volume_24h", 5_000):
                return None

            history = self.price_history.setdefault(symbol, [])
            history.append(price)

            if len(history) < max(self.warmup_period, 30):
                return None

            series = pd.Series(history[-200:])
            mean, std = self._bollinger(series, c)
            if std <= 0:
                return None

            zscore = (price - mean) / std
            if abs(zscore) < c.get("std_dev_threshold", 2.0):
                return None

            half_life = self._half_life_ar1(series)
            hurst = self._hurst(series)

            if not self._is_mean_reverting(half_life, hurst, c):
                return None

            direction = SignalType.BUY if zscore < 0 else SignalType.SELL
            confidence = self._confidence(zscore, half_life, hurst, c)
            if confidence < c.get("min_confidence", 0.35):
                return None

            stop_pct, tp_pct = self._risk_params(std, price, confidence, c)
            stop = price * (1 - stop_pct) if direction == SignalType.BUY else price * (1 + stop_pct)
            take = price + (tp_pct * price if direction == SignalType.BUY else -tp_pct * price)
            size = self._position_size(confidence, c)

            return self._create_signal(
                signal_type=direction,
                confidence=confidence,
                price=price,
                position_size=size,
                stop_loss=stop,
                take_profit=take,
                metadata={
                    "zscore": zscore,
                    "half_life": half_life,
                    "hurst": hurst,
                    "bollinger_mean": mean,
                    "bollinger_std": std,
                    "stop_loss_pct": stop_pct,
                    "take_profit_pct": tp_pct,
                },
            )
        except Exception:
            logger.error("[MeanReversionV2] evaluation error", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # STATISTICS
    # ------------------------------------------------------------------
    def _bollinger(self, series: pd.Series, c: Dict) -> Tuple[float, float]:
        window = c.get("bollinger_periods", 20)
        mean = series.rolling(window).mean().iloc[-1]
        std = series.rolling(window).std(ddof=0).iloc[-1]
        return float(mean), float(std)

    def _half_life_ar1(self, series: pd.Series) -> float:
        series = series.dropna()
        if len(series) < 20:
            return float("inf")
        y = series.diff().dropna()
        x = series.shift(1).dropna().loc[y.index]
        beta = np.polyfit(x, y, 1)[0]
        return float(np.log(2) / abs(beta)) if beta < 0 else float("inf")

    def _hurst(self, series: pd.Series) -> float:
        returns = np.diff(np.log(series))
        if len(returns) < 50:
            return 0.5
        tau = [np.std(returns[:i]) for i in range(10, 50)]
        poly = np.polyfit(np.log(range(10, 50)), np.log(tau), 1)
        return float(poly[0])

    # ------------------------------------------------------------------
    # VALIDATION / CONFIDENCE / RISK
    # ------------------------------------------------------------------
    def _is_mean_reverting(self, hl: float, hurst: float, c: Dict) -> bool:
        return hl < c.get("max_half_life", 50) and 0.3 <= hurst <= 0.5

    def _confidence(self, z: float, hl: float, hurst: float, c: Dict) -> float:
        z_factor = min(abs(z) / c.get("extreme_threshold", 3.0), 1.0)
        hl_factor = max(0.1, 1 - hl / c.get("max_half_life", 50))
        hurst_factor = max(0.1, 1 - hurst)
        return min(c.get("max_confidence", 0.9), z_factor * hl_factor * hurst_factor)

    def _risk_params(self, std: float, price: float, conf: float, c: Dict) -> Tuple[float, float]:
        vol_pct = std / price
        stop = max(0.03, min(0.12, vol_pct * (1.5 - conf)))
        take = stop * c.get("risk_reward_ratio", 2.0)
        return stop, take

    def _position_size(self, conf: float, c: Dict) -> float:
        max_size = c.get("max_position_size", 0.08)
        min_size = c.get("min_position_size", 0.01)
        return max(min_size, min(max_size, conf * max_size))

