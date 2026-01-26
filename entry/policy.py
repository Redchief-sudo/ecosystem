"""
Entry Policy Configuration and Definitions.

Defines immutable, versioned entry policies enforced by the Entry Manager.
Policies are authoritative rules and must never be violated.
"""

from enum import Enum
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class EntryPolicyType(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


def _parse_version(version: str) -> Tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        raise ValueError(f"Invalid semantic version: {version}")


@dataclass(frozen=True)
class EntryPolicy:
    """
    Immutable entry policy definition.
    """
    name: str
    version: str
    type: EntryPolicyType

    # Score thresholds
    approval_threshold: float
    strong_entry_threshold: float
    review_threshold: float

    # Hard risk constraints
    min_liquidity_score: float
    min_volume_momentum: float
    max_rugpull_risk: float

    # Position sizing
    max_position_size_percent: float

    # Audit metadata
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        self._validate_policy()

    def _validate_policy(self):
        # ---- Threshold ordering
        if not (0.0 < self.review_threshold < self.approval_threshold <= self.strong_entry_threshold <= 1.0):
            raise ValueError(
                "Thresholds must satisfy: "
                "0 < review < approval <= strong_entry <= 1.0"
            )

        # ---- Risk bounds
        if not (0.0 <= self.min_liquidity_score <= 1.0):
            raise ValueError("min_liquidity_score must be between 0 and 1")

        if not (0.0 <= self.min_volume_momentum <= 2.0):
            raise ValueError("min_volume_momentum must be between 0 and 2")

        if not (0.0 <= self.max_rugpull_risk <= 1.0):
            raise ValueError("max_rugpull_risk must be between 0 and 1")

        if not (0.0 < self.max_position_size_percent <= 1.0):
            raise ValueError("max_position_size_percent must be between 0 and 1")

        # ---- Version sanity
        _parse_version(self.version)


class EntryPolicyRegistry:
    """Safe registry for immutable entry policies."""

    def __init__(self):
        self._policies: Dict[str, EntryPolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self):
        logger.info("Loading default entry policies")

        self.register_policy(
            EntryPolicy(
                name="conservative",
                version="1.0.0",
                type=EntryPolicyType.CONSERVATIVE,
                approval_threshold=0.70,
                strong_entry_threshold=0.85,
                review_threshold=0.55,
                min_liquidity_score=0.60,
                min_volume_momentum=1.00,
                max_rugpull_risk=0.20,
                max_position_size_percent=0.05,
            )
        )

        self.register_policy(
            EntryPolicy(
                name="moderate",
                version="1.0.0",
                type=EntryPolicyType.MODERATE,
                approval_threshold=0.60,
                strong_entry_threshold=0.80,
                review_threshold=0.45,
                min_liquidity_score=0.40,
                min_volume_momentum=0.80,
                max_rugpull_risk=0.35,
                max_position_size_percent=0.10,
            )
        )

        self.register_policy(
            EntryPolicy(
                name="aggressive",
                version="1.0.0",
                type=EntryPolicyType.AGGRESSIVE,
                approval_threshold=0.50,
                strong_entry_threshold=0.70,
                review_threshold=0.35,
                min_liquidity_score=0.25,
                min_volume_momentum=0.60,
                max_rugpull_risk=0.50,
                max_position_size_percent=0.20,
            )
        )

    def register_policy(self, policy: EntryPolicy):
        key = f"{policy.name}:{policy.version}"
        if key in self._policies:
            raise KeyError(f"Entry policy already registered: {key}")

        self._policies[key] = policy
        logger.info("Registered entry policy: %s", key)

    def get_policy(self, name: str, version: str) -> Optional[EntryPolicy]:
        policy = self._policies.get(f"{name}:{version}")
        if policy is None:
            logger.warning("Requested unknown policy: %s:%s", name, version)
        return policy

    def get_policy_by_type(self, policy_type: EntryPolicyType) -> Optional[EntryPolicy]:
        matching = [
            p for p in self._policies.values() if p.type is policy_type
        ]
        if not matching:
            logger.warning("No policy found for type: %s", policy_type.value)
            return None

        return max(matching, key=lambda p: _parse_version(p.version))


policy_registry = EntryPolicyRegistry()


def get_default_policy(
    policy_type: EntryPolicyType = EntryPolicyType.MODERATE,
) -> EntryPolicy:
    policy = policy_registry.get_policy_by_type(policy_type)
    if policy is None:
        raise RuntimeError(f"No default policy for type: {policy_type.value}")
    return policy

