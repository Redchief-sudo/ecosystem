"""
Exit Policy Configuration and Definitions.

This module defines the exit policies that govern position exit decisions.
Policies are explicit, versioned rules that the Exit Manager enforces.
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ExitPolicyType(Enum):
    """Types of exit policies available."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class ExitPolicy:
    """
    A complete, immutable exit policy configuration.

    All numeric values are expressed as decimal percentages:
    e.g. -0.10 == -10%, 0.25 == +25%
    """

    name: str
    version: str
    type: ExitPolicyType

    # Stop loss thresholds
    hard_stop_loss: float              # Negative decimal (e.g. -0.10)
    trailing_stop_activation: float    # Positive decimal
    trailing_stop_distance: float      # Positive decimal

    # Take profit thresholds
    take_profit_1: float
    take_profit_1_size: float
    take_profit_2: float
    take_profit_2_size: float

    # Time-based exits
    max_hold_hours: float
    time_based_exit_threshold: float

    # Risk thresholds
    max_drawdown_for_exit: float        # Decimal (e.g. 0.20 == 20%)
    volatility_exit_threshold: float    # Normalized volatility metric

    def __post_init__(self):
        self._validate_policy()

    def _validate_policy(self) -> None:
        # --- Stop loss validation ---
        if not (-1.0 < self.hard_stop_loss < 0.0):
            raise ValueError("hard_stop_loss must be a negative decimal (e.g. -0.10)")

        if self.trailing_stop_activation <= 0:
            raise ValueError("trailing_stop_activation must be > 0")

        if self.trailing_stop_distance <= 0:
            raise ValueError("trailing_stop_distance must be > 0")

        if self.trailing_stop_distance >= self.trailing_stop_activation:
            raise ValueError(
                "trailing_stop_distance must be smaller than trailing_stop_activation"
            )

        # --- Take profit validation ---
        if self.take_profit_1 <= 0 or self.take_profit_2 <= 0:
            raise ValueError("take profit targets must be > 0")

        if self.take_profit_2 <= self.take_profit_1:
            raise ValueError("take_profit_2 must be greater than take_profit_1")

        if not (0 < self.take_profit_1_size <= 1):
            raise ValueError("take_profit_1_size must be between 0 and 1")

        if not (0 < self.take_profit_2_size <= 1):
            raise ValueError("take_profit_2_size must be between 0 and 1")

        if (self.take_profit_1_size + self.take_profit_2_size) > 1.0:
            raise ValueError("total take profit exit size cannot exceed 100%")

        # --- Time-based exits ---
        if self.max_hold_hours <= 0:
            raise ValueError("max_hold_hours must be > 0")

        if self.time_based_exit_threshold < 0:
            raise ValueError("time_based_exit_threshold cannot be negative")

        # --- Risk thresholds ---
        if not (0 < self.max_drawdown_for_exit < 1.0):
            raise ValueError("max_drawdown_for_exit must be between 0 and 1")

        if self.volatility_exit_threshold <= 0:
            raise ValueError("volatility_exit_threshold must be > 0")


class ExitPolicyRegistry:
    """Registry of available exit policies."""

    def __init__(self):
        self._policies: Dict[str, ExitPolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        self.register_policy(
            ExitPolicy(
                name="conservative",
                version="1.0.0",
                type=ExitPolicyType.CONSERVATIVE,
                hard_stop_loss=-0.10,
                trailing_stop_activation=0.05,
                trailing_stop_distance=0.03,
                take_profit_1=0.08,
                take_profit_1_size=0.30,
                take_profit_2=0.15,
                take_profit_2_size=0.40,
                max_hold_hours=48.0,
                time_based_exit_threshold=0.05,
                max_drawdown_for_exit=0.15,
                volatility_exit_threshold=0.50,
            )
        )

        self.register_policy(
            ExitPolicy(
                name="moderate",
                version="1.0.0",
                type=ExitPolicyType.MODERATE,
                hard_stop_loss=-0.15,
                trailing_stop_activation=0.08,
                trailing_stop_distance=0.04,
                take_profit_1=0.12,
                take_profit_1_size=0.40,
                take_profit_2=0.25,
                take_profit_2_size=0.30,
                max_hold_hours=72.0,
                time_based_exit_threshold=0.08,
                max_drawdown_for_exit=0.20,
                volatility_exit_threshold=0.60,
            )
        )

        self.register_policy(
            ExitPolicy(
                name="aggressive",
                version="1.0.0",
                type=ExitPolicyType.AGGRESSIVE,
                hard_stop_loss=-0.25,
                trailing_stop_activation=0.15,
                trailing_stop_distance=0.05,
                take_profit_1=0.20,
                take_profit_1_size=0.50,
                take_profit_2=0.40,
                take_profit_2_size=0.30,
                max_hold_hours=120.0,
                time_based_exit_threshold=0.15,
                max_drawdown_for_exit=0.30,
                volatility_exit_threshold=0.70,
            )
        )

    def register_policy(self, policy: ExitPolicy) -> None:
        key = f"{policy.name}:{policy.version}"
        self._policies[key] = policy
        logger.info("Registered exit policy: %s", key)

    def get_policy(self, name: str, version: str = "1.0.0") -> Optional[ExitPolicy]:
        return self._policies.get(f"{name}:{version}")

    def get_policy_by_type(self, policy_type: ExitPolicyType) -> Optional[ExitPolicy]:
        candidates = [p for p in self._policies.values() if p.type == policy_type]
        if not candidates:
            return None
        return max(candidates, key=lambda p: [int(x) for x in p.version.split(".")])


_policy_registry = ExitPolicyRegistry()


def get_default_policy(
    policy_type: ExitPolicyType = ExitPolicyType.MODERATE,
) -> ExitPolicy:
    """Return the latest default exit policy for a given type."""
    policy = _policy_registry.get_policy_by_type(policy_type)
    if policy is None:
        raise ValueError(f"No default exit policy found for type: {policy_type.value}")
    return policy

