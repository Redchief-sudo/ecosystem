"""
Position Verdict Types and Structures.

This module defines the verdict types and data structures used by the
Position Manager to communicate position assessment results.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PositionVerdict(Enum):
    """
    Position assessment verdicts.

    These are the possible outcomes of a position assessment.
    """
    HEALTHY = "healthy"
    MONITOR = "monitor"
    MONITOR_CLOSELY = "monitor_closely"
    REDUCE_RISK = "reduce_risk"
    CLOSE_POSITION = "close_position"
    UNKNOWN = "unknown"


@dataclass
class PositionRecommendation:
    """
    A specific recommendation for position management.
    """
    recommendation_type: str  # e.g., "reduce_size", "set_stop_loss", "close"
    parameter: str            # e.g., "amount_usd", "stop_loss_price"
    value: Any
    reason: str
    priority: int             # 1 = high, 5 = low

    def __str__(self) -> str:
        return f"{self.recommendation_type}: {self.parameter}={self.value} ({self.reason})"


class PositionRiskLevel(Enum):
    """Position risk assessment levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PositionAssessment:
    """
    Complete result of a position assessment.

    This is the primary output of the Position Manager.
    """
    verdict: PositionVerdict
    reason: str
    risk_level: PositionRiskLevel
    confidence: float
    recommendations: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    assessment_timestamp: Optional[float] = None

    def __post_init__(self):
        """Set timestamp if not provided."""
        import time
        if self.assessment_timestamp is None:
            self.assessment_timestamp = time.time()

    def __bool__(self) -> bool:
        """Boolean evaluation based on approval status."""
        return self.verdict == PositionVerdict.HEALTHY

    def is_healthy(self) -> bool:
        """Check if the position is healthy."""
        return self.verdict == PositionVerdict.HEALTHY

    def needs_monitoring(self) -> bool:
        """Check if the position needs monitoring."""
        return self.verdict in [PositionVerdict.MONITOR, PositionVerdict.MONITOR_CLOSELY]

    def needs_action(self) -> bool:
        """Check if the position needs immediate action."""
        return self.verdict in [PositionVerdict.REDUCE_RISK, PositionVerdict.CLOSE_POSITION]

    def get_risk_summary(self) -> str:
        """Get a summary of the risk assessment."""
        if self.is_healthy():
            return f"Healthy position - {self.reason}"
        elif self.needs_monitoring():
            return f"Monitor position - {self.reason}"
        elif self.needs_action():
            return f"Action required - {self.reason}"
        return f"Unknown status - {self.reason}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            'verdict': self.verdict.value,
            'reason': self.reason,
            'risk_level': self.risk_level.value,
            'confidence': self.confidence,
            'assessment_timestamp': self.assessment_timestamp,
        }

        if self.recommendations:
            result['recommendations'] = self.recommendations

        if self.metadata:
            result['metadata'] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PositionAssessment':
        """Create from dictionary."""
        return cls(
            verdict=PositionVerdict(data['verdict']),
            reason=data['reason'],
            risk_level=PositionRiskLevel(data['risk_level'].lower()),
            confidence=data['confidence'],
            recommendations=data.get('recommendations'),
            metadata=data.get('metadata'),
            assessment_timestamp=data.get('assessment_timestamp')
        )


class PositionVerdictAggregator:
    """
    Aggregates multiple position assessments into a single verdict.

    Useful when multiple position policies need to be evaluated.
    """

    def __init__(self):
        self.assessments: List[PositionAssessment] = []

    def add_assessment(self, assessment: PositionAssessment):
        """Add a position assessment to the aggregator."""
        self.assessments.append(assessment)

    def get_aggregate_verdict(self) -> PositionAssessment:
        """
        Get the aggregate verdict from all assessments.

        Logic:
        - If any assessment is REDUCE_RISK or CLOSE_POSITION, the aggregate is the most severe
        - If all are HEALTHY, the aggregate is HEALTHY
        - If some need monitoring, the aggregate is MONITOR_CLOSELY
        """
        if not self.assessments:
            return PositionAssessment(
                verdict=PositionVerdict.UNKNOWN,
                reason="No position assessments provided",
                risk_level=PositionRiskLevel.CRITICAL,
                confidence=0.0
            )

        # Check for action required verdicts
        action_assessments = [a for a in self.assessments if a.needs_action()]
        if action_assessments:
            severity_order = [PositionVerdict.CLOSE_POSITION, PositionVerdict.REDUCE_RISK]
            most_severe = min(action_assessments, key=lambda a: severity_order.index(a.verdict) if a.verdict in severity_order else len(severity_order))
            return PositionAssessment(
                verdict=most_severe.verdict,
                reason=f"Action required by {len(action_assessments)}/{len(self.assessments)} assessments",
                risk_level=most_severe.risk_level,
                confidence=sum(a.confidence for a in action_assessments) / len(action_assessments),
                recommendations=[r for a in action_assessments for r in (a.recommendations or [])]
            )

        # Check for monitoring verdicts
        monitor_assessments = [a for a in self.assessments if a.needs_monitoring()]
        if monitor_assessments:
            close_monitor = [a for a in monitor_assessments if a.verdict == PositionVerdict.MONITOR_CLOSELY]
            if close_monitor:
                return PositionAssessment(
                    verdict=PositionVerdict.MONITOR_CLOSELY,
                    reason=f"Monitor closely - {len(monitor_assessments)} assessments indicate attention needed",
                    risk_level=PositionRiskLevel.HIGH,
                    confidence=sum(a.confidence for a in monitor_assessments) / len(monitor_assessments)
                )
            return PositionAssessment(
                verdict=PositionVerdict.MONITOR,
                reason=f"Monitor - {len(monitor_assessments)} assessments indicate attention",
                risk_level=PositionRiskLevel.MODERATE,
                confidence=sum(a.confidence for a in monitor_assessments) / len(monitor_assessments)
            )

        # All assessments are healthy
        return PositionAssessment(
            verdict=PositionVerdict.HEALTHY,
            reason=f"All {len(self.assessments)} assessments indicate healthy position",
            risk_level=PositionRiskLevel.LOW,
            confidence=sum(a.confidence for a in self.assessments) / len(self.assessments)
        )

    def clear(self):
        """Clear all assessments."""
        self.assessments.clear()


# Convenience functions for creating common verdicts

def healthy(reason: str = "Position is within acceptable parameters", **kwargs) -> PositionAssessment:
    """Create a healthy verdict."""
    return PositionAssessment(
        verdict=PositionVerdict.HEALTHY,
        reason=reason,
        risk_level="LOW",
        confidence=0.9,
        **kwargs
    )


def monitor(reason: str, **kwargs) -> PositionAssessment:
    """Create a monitor verdict."""
    return PositionAssessment(
        verdict=PositionVerdict.MONITOR,
        reason=reason,
        risk_level="MODERATE",
        confidence=0.7,
        **kwargs
    )


def monitor_closely(reason: str, **kwargs) -> PositionAssessment:
    """Create a monitor closely verdict."""
    return PositionAssessment(
        verdict=PositionVerdict.MONITOR_CLOSELY,
        reason=reason,
        risk_level="HIGH",
        confidence=0.85,
        **kwargs
    )


def reduce_risk(reason: str, recommendations: List[str], **kwargs) -> PositionAssessment:
    """Create a reduce risk verdict."""
    return PositionAssessment(
        verdict=PositionVerdict.REDUCE_RISK,
        reason=reason,
        risk_level="CRITICAL",
        confidence=0.95,
        recommendations=recommendations,
        **kwargs
    )


def close_position(reason: str, **kwargs) -> PositionAssessment:
    """Create a close position verdict."""
    return PositionAssessment(
        verdict=PositionVerdict.CLOSE_POSITION,
        reason=reason,
        risk_level="CRITICAL",
        confidence=0.99,
        **kwargs
    )
