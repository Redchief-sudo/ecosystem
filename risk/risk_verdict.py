"""
Risk Verdict Types and Structures.

This module defines the verdict types and data structures used by the
Risk Manager to communicate risk assessment results.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class RiskVerdict(Enum):
    """
    Risk assessment verdicts.

    These are the possible outcomes of a risk assessment.
    """
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVED_WITH_CONSTRAINTS = "approved_with_constraints"


@dataclass
class RiskConstraint:
    """
    A specific constraint applied to a trade.

    Constraints modify trade parameters to make them compliant with risk policy.
    """
    constraint_type: str  # e.g., "max_amount", "max_leverage", "time_restriction"
    parameter: str        # e.g., "amount_usd", "leverage_ratio"
    original_value: Any
    constrained_value: Any
    reason: str

    def __str__(self) -> str:
        return f"{self.constraint_type}: {self.parameter} {self.original_value} -> {self.constrained_value} ({self.reason})"


@dataclass
class RiskAssessment:
    """
    Complete result of a risk assessment.

    This is the primary output of the Risk Manager.
    """
    verdict: RiskVerdict
    reason: str
    constraints: Optional[List[RiskConstraint]] = None
    metadata: Optional[Dict[str, Any]] = None
    policy_name: Optional[str] = None
    policy_version: Optional[str] = None
    assessment_timestamp: Optional[float] = None

    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.assessment_timestamp is None:
            import time
            self.assessment_timestamp = time.time()

    def __bool__(self) -> bool:
        """Boolean evaluation based on approval status."""
        return self.verdict in [RiskVerdict.APPROVED, RiskVerdict.APPROVED_WITH_CONSTRAINTS]

    def is_approved(self) -> bool:
        """Check if the assessment result is approved."""
        return bool(self)

    def is_rejected(self) -> bool:
        """Check if the assessment result is rejected."""
        return self.verdict == RiskVerdict.REJECTED

    def has_constraints(self) -> bool:
        """Check if the assessment has constraints."""
        return self.verdict == RiskVerdict.APPROVED_WITH_CONSTRAINTS and self.constraints is not None

    def get_constraint_summary(self) -> str:
        """Get a summary of applied constraints."""
        if not self.has_constraints():
            return "No constraints applied"

        constraint_summaries = [str(c) for c in self.constraints]
        return f"Applied {len(constraint_summaries)} constraints: {', '.join(constraint_summaries)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            'verdict': self.verdict.value,
            'reason': self.reason,
            'policy_name': self.policy_name,
            'policy_version': self.policy_version,
            'assessment_timestamp': self.assessment_timestamp,
        }

        if self.constraints:
            result['constraints'] = [
                {
                    'constraint_type': c.constraint_type,
                    'parameter': c.parameter,
                    'original_value': c.original_value,
                    'constrained_value': c.constrained_value,
                    'reason': c.reason
                }
                for c in self.constraints
            ]

        if self.metadata:
            result['metadata'] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskAssessment':
        """Create from dictionary."""
        constraints = None
        if 'constraints' in data:
            constraints = [
                RiskConstraint(**c) for c in data['constraints']
            ]

        return cls(
            verdict=RiskVerdict(data['verdict']),
            reason=data['reason'],
            constraints=constraints,
            metadata=data.get('metadata'),
            policy_name=data.get('policy_name'),
            policy_version=data.get('policy_version'),
            assessment_timestamp=data.get('assessment_timestamp')
        )


class RiskVerdictAggregator:
    """
    Aggregates multiple risk assessments into a single verdict.

    Useful when multiple risk policies need to be evaluated.
    """

    def __init__(self):
        self.assessments: List[RiskAssessment] = []

    def add_assessment(self, assessment: RiskAssessment):
        """Add a risk assessment to the aggregator."""
        self.assessments.append(assessment)

    def get_aggregate_verdict(self) -> RiskAssessment:
        """
        Get the aggregate verdict from all assessments.

        Logic:
        - If any assessment is REJECTED, the aggregate is REJECTED
        - If all are APPROVED, the aggregate is APPROVED
        - If some have constraints, the aggregate is APPROVED_WITH_CONSTRAINTS
        """
        if not self.assessments:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason="No risk assessments provided"
            )

        # Check for any rejections
        rejections = [a for a in self.assessments if a.is_rejected()]
        if rejections:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason=f"Rejected by {len(rejections)}/{len(self.assessments)} assessments",
                metadata={'rejection_reasons': [a.reason for a in rejections]}
            )

        # Check for constraints
        constrained_assessments = [a for a in self.assessments if a.has_constraints()]
        all_constraints = []
        for assessment in constrained_assessments:
            if assessment.constraints:
                all_constraints.extend(assessment.constraints)

        if all_constraints:
            return RiskAssessment(
                verdict=RiskVerdict.APPROVED_WITH_CONSTRAINTS,
                reason=f"Approved with constraints from {len(constrained_assessments)} assessments",
                constraints=all_constraints,
                metadata={'total_constraints': len(all_constraints)}
            )

        # All assessments approved without constraints
        return RiskAssessment(
            verdict=RiskVerdict.APPROVED,
            reason=f"Approved by all {len(self.assessments)} assessments"
        )

    def clear(self):
        """Clear all assessments."""
        self.assessments.clear()


# Convenience functions for creating common verdicts

def approved(reason: str = "Risk check passed", **kwargs) -> RiskAssessment:
    """Create an approved verdict."""
    return RiskAssessment(verdict=RiskVerdict.APPROVED, reason=reason, **kwargs)


def rejected(reason: str, **kwargs) -> RiskAssessment:
    """Create a rejected verdict."""
    return RiskAssessment(verdict=RiskVerdict.REJECTED, reason=reason, **kwargs)


def approved_with_constraints(reason: str, constraints: List[RiskConstraint], **kwargs) -> RiskAssessment:
    """Create an approved with constraints verdict."""
    return RiskAssessment(
        verdict=RiskVerdict.APPROVED_WITH_CONSTRAINTS,
        reason=reason,
        constraints=constraints,
        **kwargs
    )
