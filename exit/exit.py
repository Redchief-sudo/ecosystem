"""
Exit Manager
------------
Production-grade exit strategy engine.

Evaluates active positions against exit policies and produces
authoritative, auditable exit decisions.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import numpy as np
from datetime import datetime, timezone

from .policy import ExitPolicy, get_default_policy
from .verdict import ExitVerdict, ExitAssessment, ExitSignal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExitFeatures:
    position_duration_hours: float
    current_pnl_percent: float
    unrealized_pnl_usd: float
    position_size_usd: float

    price_momentum: float
    volume_momentum: float

    volatility_current: float
    rsi: float
    macd_histogram: float

    drawdown_from_peak: float
    liquidity_deterioration: float
    time_of_day_factor: float

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


class ExitManager:
    """
    Authoritative exit decision engine.
    """

    def __init__(self, config: Dict[str, Any], policy: Optional[ExitPolicy] = None):
        self.config = config
        self.policy = policy or get_default_policy()

        self.active_positions: Dict[str, Dict[str, Any]] = {}
        self.evaluation_history: List[ExitAssessment] = []
        self.max_history = config.get("max_history", 1000)

        logger.info("Exit Manager initialized with policy: %s", self.policy.name)

    # ------------------------------------------------------------------ Public API

    def assess_position(self, position_id: str, position_data: Dict[str, Any]) -> ExitAssessment:
        try:
            features = self._extract_features(position_data)
            pnl = features.current_pnl_percent

            state = self._get_or_init_position_state(position_id, pnl)

            assessment = (
                self._check_hard_stop(pnl)
                or self._check_take_profit(position_id, pnl, state)
                or self._check_trailing_stop(position_id, pnl, state)
                or self._check_time_exit(features)
                or self._check_risk_exit(features)
                or self._hold_decision(features)
            )

            self._finalize_position_state(position_id, assessment)
            self._record_assessment(assessment)

            return assessment

        except Exception as e:
            logger.exception("Exit assessment error for %s", position_id)
            assessment = ExitAssessment(
                verdict=ExitVerdict.ERROR,
                reason=str(e),
                confidence=0.0,
                signal_type=ExitSignal.NONE.name,
                pnl_percent=0.0,
            )
            self._record_assessment(assessment)
            return assessment

    # ------------------------------------------------------------------ Core Checks

    def _check_hard_stop(self, pnl: float) -> Optional[ExitAssessment]:
        if pnl <= self.policy.hard_stop_loss:
            return self._exit(
                ExitVerdict.FULL_EXIT,
                ExitSignal.STOP_LOSS,
                f"Hard stop loss hit ({pnl:.2f}%)",
                pnl,
                confidence=1.0,
            )
        return None

    def _check_take_profit(self, pid: str, pnl: float, state: Dict[str, Any]) -> Optional[ExitAssessment]:
        for name, threshold, size in self.policy.take_profit_targets:
            if name not in state["executed_tps"] and pnl >= threshold:
                state["executed_tps"].add(name)
                return self._exit(
                    ExitVerdict.PARTIAL_EXIT,
                    ExitSignal.TAKE_PROFIT,
                    f"{name} triggered at {pnl:.2f}%",
                    pnl,
                    exit_size_percent=size,
                    confidence=0.9,
                )
        return None

    def _check_trailing_stop(self, pid: str, pnl: float, state: Dict[str, Any]) -> Optional[ExitAssessment]:
        state["peak_pnl"] = max(state["peak_pnl"], pnl)

        if state["peak_pnl"] >= self.policy.trailing_stop_activation:
            stop = state["peak_pnl"] - self.policy.trailing_stop_distance
            if pnl <= stop:
                return self._exit(
                    ExitVerdict.FULL_EXIT,
                    ExitSignal.TRAILING_STOP,
                    f"Trailing stop hit ({pnl:.2f}%)",
                    pnl,
                    confidence=0.85,
                )
        return None

    def _check_time_exit(self, f: ExitFeatures) -> Optional[ExitAssessment]:
        if f.position_duration_hours >= self.policy.max_hold_hours:
            urgent = f.current_pnl_percent < 0
            return self._exit(
                ExitVerdict.FULL_EXIT if urgent else ExitVerdict.PARTIAL_EXIT,
                ExitSignal.TIME_BASED,
                f"Max hold exceeded ({f.position_duration_hours:.1f}h)",
                f.current_pnl_percent,
                confidence=0.8 if urgent else 0.7,
            )
        return None

    def _check_risk_exit(self, f: ExitFeatures) -> Optional[ExitAssessment]:
        if f.volatility_current >= self.policy.volatility_exit_threshold:
            urgent = f.volatility_current >= self.policy.volatility_exit_threshold * 1.5
            return self._exit(
                ExitVerdict.EMERGENCY_EXIT if urgent else ExitVerdict.FULL_EXIT,
                ExitSignal.RISK_MANAGEMENT,
                f"Volatility spike ({f.volatility_current:.2f})",
                f.current_pnl_percent,
                confidence=0.95,
            )
        return None

    def _hold_decision(self, f: ExitFeatures) -> ExitAssessment:
        return ExitAssessment(
            verdict=ExitVerdict.HOLD,
            reason="No exit conditions met",
            confidence=0.6,
            signal_type=ExitSignal.NONE.name,
            pnl_percent=f.current_pnl_percent,
            key_factors=self._hold_factors(f),
        )

    # ------------------------------------------------------------------ Utilities

    def _exit(
        self,
        verdict: ExitVerdict,
        signal: ExitSignal,
        reason: str,
        pnl: float,
        confidence: float,
        exit_size_percent: Optional[float] = None,
    ) -> ExitAssessment:
        return ExitAssessment(
            verdict=verdict,
            reason=reason,
            confidence=confidence,
            signal_type=signal.name,
            pnl_percent=pnl,
            exit_size_percent=exit_size_percent,
            metadata={"ts": datetime.now(timezone.utc).isoformat()},
        )

    def _get_or_init_position_state(self, pid: str, pnl: float) -> Dict[str, Any]:
        return self.active_positions.setdefault(
            pid,
            {"peak_pnl": pnl, "executed_tps": set()},
        )

    def _finalize_position_state(self, pid: str, assessment: ExitAssessment):
        if assessment.verdict in (ExitVerdict.FULL_EXIT, ExitVerdict.EMERGENCY_EXIT):
            self.active_positions.pop(pid, None)

    def _record_assessment(self, assessment: ExitAssessment):
        self.evaluation_history.append(assessment)
        if len(self.evaluation_history) > self.max_history:
            self.evaluation_history = self.evaluation_history[-self.max_history:]

    def _hold_factors(self, f: ExitFeatures) -> List[str]:
        factors = []
        if f.price_momentum > 0:
            factors.append("Positive momentum")
        if f.current_pnl_percent > 10:
            factors.append("Strong profit")
        return factors or ["Neutral conditions"]

    # ------------------------------------------------------------------ Feature Extraction

    def _extract_features(self, data: Dict[str, Any]) -> ExitFeatures:
        return ExitFeatures(
            position_duration_hours=float(data.get("duration_hours", 0)),
            current_pnl_percent=float(data.get("pnl_percent", 0)),
            unrealized_pnl_usd=float(data.get("unrealized_pnl_usd", 0)),
            position_size_usd=float(data.get("position_size_usd", 0)),
            price_momentum=self._momentum(data.get("price_history", [])),
            volume_momentum=self._momentum(data.get("volume_history", [])),
            volatility_current=float(data.get("volatility", 0)),
            rsi=float(data.get("rsi", 50)) / 100,
            macd_histogram=self._momentum(data.get("price_history", [])),
            drawdown_from_peak=float(data.get("drawdown_from_peak", 0)),
            liquidity_deterioration=float(data.get("liquidity_deterioration", 0)),
            time_of_day_factor=self._time_factor(),
        )

    def _momentum(self, series: List[float]) -> float:
        if len(series) < 2:
            return 0.0
        return float(np.clip((series[-1] - series[0]) / abs(series[0]), -1, 1))

    def _time_factor(self) -> float:
        hour = datetime.now(timezone.utc).hour
        if 9 <= hour <= 16:
            return 1.0
        if 6 <= hour < 9 or 16 < hour <= 20:
            return 0.7
        return 0.4


def create_exit_manager(config: Dict[str, Any], policy: Optional[ExitPolicy] = None) -> ExitManager:
    return ExitManager(config, policy)

