"""
Exit Verdict Types and Structures.

This module defines the verdict types and data structures used by the
Exit Manager to communicate exit assessment results.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import time

logger = logging.getLogger(__name__)


class ExitVerdict(Enum):
    """Exit assessment verdicts."""
    HOLD = "hold"
    PARTIAL_EXIT = "partial_exit"
    FULL_EXIT = "full_exit"
    EMERGENCY_EXIT = "emergency_exit"
    ERROR = "error"


class ExitSignal(Enum):
    """Exit signal types."""
    NONE = "none"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    MODEL_PREDICTION = "model_prediction"
    RISK_MANAGEMENT = "risk_management"
    MARKET_REVERSAL = "market_reversal"
    TIME_BASED = "time_based"


@dataclass
class ExitAssessment:
    """
    Complete result of an exit assessment.

    All percentages are expressed as decimals:
    e.g. 0.25 == 25%, -0.10 == -10%
    """

    verdict: ExitVerdict
    reason: str
    confidence: float
    signal_type: ExitSignal
    pnl_percent: float

    exit_size_percent: Optional[float] = None
    key_factors: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    assessment_timestamp: Optional[float] = None

    def __post_init__(self) -> None:
        if self.assessment_timestamp is None:
            self.assessment_timestamp = time.time()

        self._validate()

    def _validate(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

        if self.exit_size_percent is not None:
            if not (0.0 < self.exit_size_percent <= 1.0):
                raise ValueError("exit_size_percent must be between 0 and 1")

            if self.verdict != ExitVerdict.PARTIAL_EXIT:
                raise ValueError(
                    "exit_size_percent is only valid for PARTIAL_EXIT verdicts"
                )

        if self.verdict in (ExitVerdict.FULL_EXIT, ExitVerdict.EMERGENCY_EXIT):
            if self.exit_size_percent is not None:
                raise ValueError(
                    "exit_size_percent must not be set for full or emergency exits"
                )

    def __bool__(self) -> bool:
        """
        Truthiness indicates that an exit action should be taken.
        HOLD and ERROR evaluate to False.
        """
        return self.should_exit()

    def should_exit(self) -> bool:
        return self.verdict in (
            ExitVerdict.PARTIAL_EXIT,
            ExitVerdict.FULL_EXIT,
            ExitVerdict.EMERGENCY_EXIT,
        )

    def is_emergency(self) -> bool:
        return self.verdict == ExitVerdict.EMERGENCY_EXIT

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "verdict": self.verdict.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "signal_type": self.signal_type.value,
            "pnl_percent": self.pnl_percent,
            "timestamp": self.assessment_timestamp,
        }

        if self.exit_size_percent is not None:
            result["exit_size_percent"] = self.exit_size_percent

        if self.key_factors:
            result["key_factors"] = self.key_factors

        if self.metadata:
            result["metadata"] = self.metadata

        return result


# -------------------------
# Factory helpers
# -------------------------

def hold(
    reason: str = "No exit conditions met",
    pnl_percent: float = 0.0,
    **kwargs,
) -> ExitAssessment:
    return ExitAssessment(
        verdict=ExitVerdict.HOLD,
        reason=reason,
        confidence=0.75,
        signal_type=ExitSignal.NONE,
        pnl_percent=pnl_percent,
        **kwargs,
    )


def partial_exit(
    reason: str,
    pnl_percent: float,
    exit_size: float,
    signal_type: ExitSignal = ExitSignal.TAKE_PROFIT,
    **kwargs,
) -> ExitAssessment:
    return ExitAssessment(
        verdict=ExitVerdict.PARTIAL_EXIT,
        reason=reason,
        confidence=0.85,
        signal_type=signal_type,
        pnl_percent=pnl_percent,
        exit_size_percent=exit_size,
        **kwargs,
    )


def full_exit(
    reason: str,
    pnl_percent: float,
    signal_type: ExitSignal = ExitSignal.MODEL_PREDICTION,
    **kwargs,
) -> ExitAssessment:
    return ExitAssessment(
        verdict=ExitVerdict.FULL_EXIT,
        reason=reason,
        confidence=0.90,
        signal_type=signal_type,
        pnl_percent=pnl_percent,
        **kwargs,
    )


def emergency_exit(
    reason: str,
    pnl_percent: float,
    **kwargs,
) -> ExitAssessment:
    return ExitAssessment(
        verdict=ExitVerdict.EMERGENCY_EXIT,
        reason=reason,
        confidence=0.99,
        signal_type=ExitSignal.RISK_MANAGEMENT,
        pnl_percent=pnl_percent,
        **kwargs,
    )

