"""
Position Policy Configuration and Definitions.

This module defines the position policies that govern position management.
Policies are explicit, versioned rules that the Position Manager enforces.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PositionPolicyType(Enum):
    """Types of position policies available."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    HIGH_FREQUENCY = "high_frequency"


@dataclass
class PositionPolicy:
    """
    A complete position policy configuration.

    Policies define the boundaries within which position management is allowed.
    They are explicit, versioned rules that cannot be violated.
    """
    name: str
    version: str
    type: PositionPolicyType

    # Risk thresholds
    max_drawdown_percent: float        # Max drawdown before intervention
    max_position_duration_hours: float # Max time to hold position
    high_risk_threshold: float         # Risk score threshold for high risk
    critical_risk_threshold: float     # Risk score threshold for critical risk

    # Monitoring intervals
    monitoring_interval_minutes: int   # How often to check positions
    alert_interval_minutes: int        # How often to send alerts

    # Intervention thresholds
    auto_reduce_threshold: float       # Auto-reduce position at this drawdown
    auto_close_threshold: float        # Auto-close position at this drawdown

    # Position size limits
    max_position_size_percent: float   # Max position size as % of portfolio

    def __post_init__(self):
        """Validate policy configuration."""
        self._validate_policy()

    def _validate_policy(self):
        """Validate that policy parameters are within acceptable ranges."""
        if not (0 < self.max_drawdown_percent <= 1.0):
            raise ValueError(f"max_drawdown_percent must be between 0 and 1.0, got {self.max_drawdown_percent}")

        if self.max_position_duration_hours <= 0:
            raise ValueError(f"max_position_duration_hours must be > 0, got {self.max_position_duration_hours}")

        if not (0 < self.high_risk_threshold < self.critical_risk_threshold <= 1.0):
            raise ValueError("Risk thresholds must satisfy: 0 < high < critical <= 1.0")

        if self.monitoring_interval_minutes <= 0:
            raise ValueError(f"monitoring_interval_minutes must be > 0, got {self.monitoring_interval_minutes}")


class PositionPolicyRegistry:
    """
    Registry of available position policies.

    Provides access to predefined policies and allows custom policy registration.
    """

    def __init__(self):
        self._policies: Dict[str, PositionPolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self):
        """Load the default position policies."""

        # Conservative policy - very safe position management
        conservative = PositionPolicy(
            name="conservative",
            version="1.0.0",
            type=PositionPolicyType.CONSERVATIVE,
            max_drawdown_percent=0.10,      # 10% max drawdown
            max_position_duration_hours=72, # 3 days max
            high_risk_threshold=0.6,        # High risk at 60%
            critical_risk_threshold=0.8,    # Critical at 80%
            monitoring_interval_minutes=15, # Check every 15 min
            alert_interval_minutes=30,      # Alert every 30 min
            auto_reduce_threshold=0.15,     # Auto-reduce at 15%
            auto_close_threshold=0.25,      # Auto-close at 25%
            max_position_size_percent=0.05  # 5% max position size
        )

        # Moderate policy - balanced risk management
        moderate = PositionPolicy(
            name="moderate",
            version="1.0.0",
            type=PositionPolicyType.MODERATE,
            max_drawdown_percent=0.20,      # 20% max drawdown
            max_position_duration_hours=120, # 5 days max
            high_risk_threshold=0.7,        # High risk at 70%
            critical_risk_threshold=0.85,   # Critical at 85%
            monitoring_interval_minutes=10, # Check every 10 min
            alert_interval_minutes=20,      # Alert every 20 min
            auto_reduce_threshold=0.20,     # Auto-reduce at 20%
            auto_close_threshold=0.35,      # Auto-close at 35%
            max_position_size_percent=0.10  # 10% max position size
        )

        # Aggressive policy - higher risk tolerance
        aggressive = PositionPolicy(
            name="aggressive",
            version="1.0.0",
            type=PositionPolicyType.AGGRESSIVE,
            max_drawdown_percent=0.35,      # 35% max drawdown
            max_position_duration_hours=168, # 7 days max
            high_risk_threshold=0.8,        # High risk at 80%
            critical_risk_threshold=0.9,    # Critical at 90%
            monitoring_interval_minutes=5,  # Check every 5 min
            alert_interval_minutes=10,      # Alert every 10 min
            auto_reduce_threshold=0.30,     # Auto-reduce at 30%
            auto_close_threshold=0.50,      # Auto-close at 50%
            max_position_size_percent=0.20  # 20% max position size
        )

        # High frequency policy - for short-term scalping
        high_frequency = PositionPolicy(
            name="high_frequency",
            version="1.0.0",
            type=PositionPolicyType.HIGH_FREQUENCY,
            max_drawdown_percent=0.15,      # 15% max drawdown
            max_position_duration_hours=4,  # 4 hours max
            high_risk_threshold=0.5,        # High risk at 50%
            critical_risk_threshold=0.7,    # Critical at 70%
            monitoring_interval_minutes=2,  # Check every 2 min
            alert_interval_minutes=5,       # Alert every 5 min
            auto_reduce_threshold=0.10,     # Auto-reduce at 10%
            auto_close_threshold=0.20,      # Auto-close at 20%
            max_position_size_percent=0.03  # 3% max position size
        )

        self.register_policy(conservative)
        self.register_policy(moderate)
        self.register_policy(aggressive)
        self.register_policy(high_frequency)

    def register_policy(self, policy: PositionPolicy):
        """Register a position policy."""
        key = f"{policy.name}:{policy.version}"
        if key in self._policies:
            logger.warning(f"Policy {key} already registered, overwriting")
        self._policies[key] = policy
        logger.info(f"Registered position policy: {key}")

    def get_policy(self, name: str, version: str = "1.0.0") -> Optional[PositionPolicy]:
        """Get a position policy by name and version."""
        key = f"{name}:{version}"
        return self._policies.get(key)

    def list_policies(self) -> Dict[str, PositionPolicy]:
        """List all registered policies."""
        return self._policies.copy()

    def get_policy_by_type(self, policy_type: PositionPolicyType) -> Optional[PositionPolicy]:
        """Get the latest version of a policy by type."""
        matching_policies = [
            policy for policy in self._policies.values()
            if policy.type == policy_type
        ]

        if not matching_policies:
            return None

        # Return the highest version
        return max(matching_policies, key=lambda p: [int(x) for x in p.version.split('.')])


# Global policy registry instance
policy_registry = PositionPolicyRegistry()


def get_default_policy(policy_type: PositionPolicyType = PositionPolicyType.MODERATE) -> PositionPolicy:
    """Get the default position policy for a given type."""
    policy = policy_registry.get_policy_by_type(policy_type)
    if policy is None:
        raise ValueError(f"No default policy found for type: {policy_type.value}")
    return policy
