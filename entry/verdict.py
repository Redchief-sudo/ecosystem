"""
Entry Verdict Types and Structures.

Defines authoritative verdicts and immutable assessment results produced
by the Entry Manager.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone


class EntryVerdict(Enum):
    APPROVE = "approve"
    CONDITIONAL = "conditional"
    REVIEW = "review"
    REJECT = "reject"
    ERROR = "error"


@dataclass(frozen=True)
class EntryAssessment:
    """
    Immutable result of an entry assessment.

    This object is authoritative and safe for logging, auditing,
    persistence, and downstream execution decisions.
    """
    verdict: EntryVerdict
    reason: str
    confidence: float
    signal_strength: str

    # Optional explanatory data
    key_factors: Optional[List[str]] = None

    # Full feature snapshot (for audit / replay)
    features: Optional[Dict[str, Any]] = None

    # System metadata (ids, timestamps, policy, etc.)
    metadata: Optional[Dict[str, Any]] = None

    # Audit timestamp (UTC ISO-8601)
    assessment_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

    # ----------------------------- Explicit properties (NO magic truthiness)

    @property
    def is_approved(self) -> bool:
        return self.verdict is EntryVerdict.APPROVE

    @property
    def is_conditional(self) -> bool:
        return self.verdict is EntryVerdict.CONDITIONAL

    @property
    def is_actionable(self) -> bool:
        return self.verdict in (EntryVerdict.APPROVE, EntryVerdict.CONDITIONAL)

    @property
    def requires_review(self) -> bool:
        return self.verdict is EntryVerdict.REVIEW

    @property
    def is_rejected(self) -> bool:
        return self.verdict is EntryVerdict.REJECT

    @property
    def is_error(self) -> bool:
        return self.verdict is EntryVerdict.ERROR

# Convenience functions for creating common verdicts

def approved(reason: str = "Entry approved", **kwargs) -> EntryAssessment:
    """Create an approved entry assessment."""
    return EntryAssessment(
        verdict=EntryVerdict.APPROVE,
        reason=reason,
        confidence=kwargs.get('confidence', 1.0),
        signal_strength=kwargs.get('signal_strength', 'high'),
        **{k: v for k, v in kwargs.items() if k not in ['confidence', 'signal_strength']}
    )


def rejected(reason: str, **kwargs) -> EntryAssessment:
    """Create a rejected entry assessment."""
    return EntryAssessment(
        verdict=EntryVerdict.REJECT,
        reason=reason,
        confidence=kwargs.get('confidence', 1.0),
        signal_strength=kwargs.get('signal_strength', 'low'),
        **{k: v for k, v in kwargs.items() if k not in ['confidence', 'signal_strength']}
    )

