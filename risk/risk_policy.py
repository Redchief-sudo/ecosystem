"""
Risk Policy Configuration and Definitions.

This module defines the risk policies that govern trading operations.
Policies are explicit, versioned rules that the Risk Manager enforces.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class RiskPolicyType(Enum):
    """Types of risk policies available."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    PAPER_TRADING = "paper_trading"


@dataclass
class RiskPolicy:
    """
    A complete risk policy configuration.

    Policies define the boundaries within which trading is allowed.
    They are explicit, versioned rules that cannot be violated.
    """
    name: str
    version: str
    type: RiskPolicyType

    # Exposure limits
    max_exposure_per_asset: float  # Max % of portfolio per asset
    max_total_exposure: float      # Max % total portfolio exposure
    max_leverage: float            # Max leverage ratio

    # Position limits
    max_open_positions: int        # Max concurrent positions
    max_positions_per_asset: int   # Max positions per asset

    # Drawdown limits
    max_drawdown_pct: float        # Max portfolio drawdown %
    max_daily_drawdown_pct: float  # Max daily drawdown %

    # Trading frequency limits
    max_trades_per_day: int        # Max trades per day
    max_trades_per_hour: int       # Max trades per hour

    # Concentration limits
    max_concentration_pct: float   # Max concentration per asset %

    # Time-based restrictions
    restricted_trading_hours: Optional[Dict[str, Any]] = None

    # Asset-specific overrides
    asset_specific_limits: Optional[Dict[str, Dict[str, Any]]] = None

    def __post_init__(self):
        """Validate policy configuration."""
        self._validate_policy()

    def _validate_policy(self):
        """Validate that policy parameters are within acceptable ranges."""
        if not (0 < self.max_exposure_per_asset <= 1.0):
            raise ValueError(f"max_exposure_per_asset must be between 0 and 1.0, got {self.max_exposure_per_asset}")

        if not (0 < self.max_total_exposure <= 2.0):  # Allow leverage
            raise ValueError(f"max_total_exposure must be between 0 and 2.0, got {self.max_total_exposure}")

        if self.max_leverage < 1.0:
            raise ValueError(f"max_leverage must be >= 1.0, got {self.max_leverage}")

        if self.max_open_positions < 1:
            raise ValueError(f"max_open_positions must be >= 1, got {self.max_open_positions}")

        if not (0 < self.max_drawdown_pct <= 1.0):
            raise ValueError(f"max_drawdown_pct must be between 0 and 1.0, got {self.max_drawdown_pct}")

    def get_asset_limit(self, asset_symbol: str, limit_type: str) -> Optional[float]:
        """Get asset-specific limit if defined, otherwise return None."""
        if self.asset_specific_limits and asset_symbol in self.asset_specific_limits:
            return self.asset_specific_limits[asset_symbol].get(limit_type)
        return None


class RiskPolicyRegistry:
    """
    Registry of available risk policies.

    Provides access to predefined policies and allows custom policy registration.
    """

    def __init__(self):
        self._policies: Dict[str, RiskPolicy] = {}
        self._load_default_policies()

    def _load_default_policies(self):
        """Load the default risk policies."""

        # Conservative policy - very safe, low risk
        conservative = RiskPolicy(
            name="conservative",
            version="1.0.0",
            type=RiskPolicyType.CONSERVATIVE,
            max_exposure_per_asset=0.05,    # 5% per asset
            max_total_exposure=0.25,        # 25% total exposure
            max_leverage=1.0,               # No leverage
            max_open_positions=5,           # Max 5 positions
            max_positions_per_asset=1,      # 1 position per asset
            max_drawdown_pct=0.05,          # 5% max drawdown
            max_daily_drawdown_pct=0.02,    # 2% daily drawdown
            max_trades_per_day=10,          # 10 trades/day
            max_trades_per_hour=2,          # 2 trades/hour
            max_concentration_pct=10.0,     # 10% concentration limit
        )

        # Moderate policy - balanced risk/reward
        moderate = RiskPolicy(
            name="moderate",
            version="1.0.0",
            type=RiskPolicyType.MODERATE,
            max_exposure_per_asset=0.10,    # 10% per asset
            max_total_exposure=0.50,        # 50% total exposure
            max_leverage=1.0,               # No leverage
            max_open_positions=10,          # Max 10 positions
            max_positions_per_asset=2,      # 2 positions per asset
            max_drawdown_pct=0.10,          # 10% max drawdown
            max_daily_drawdown_pct=0.05,    # 5% daily drawdown
            max_trades_per_day=25,          # 25 trades/day
            max_trades_per_hour=5,          # 5 trades/hour
            max_concentration_pct=15.0,     # 15% concentration limit
        )

        # Aggressive policy - higher risk tolerance
        aggressive = RiskPolicy(
            name="aggressive",
            version="1.0.0",
            type=RiskPolicyType.AGGRESSIVE,
            max_exposure_per_asset=0.20,    # 20% per asset
            max_total_exposure=1.0,         # 100% total exposure
            max_leverage=1.5,               # 1.5x leverage allowed
            max_open_positions=20,          # Max 20 positions
            max_positions_per_asset=3,      # 3 positions per asset
            max_drawdown_pct=0.20,          # 20% max drawdown
            max_daily_drawdown_pct=0.10,    # 10% daily drawdown
            max_trades_per_day=50,          # 50 trades/day
            max_trades_per_hour=10,         # 10 trades/hour
            max_concentration_pct=25.0,     # 25% concentration limit
        )

        # Paper trading policy - relaxed for testing
        paper_trading = RiskPolicy(
            name="paper_trading",
            version="1.0.0",
            type=RiskPolicyType.PAPER_TRADING,
            max_exposure_per_asset=0.50,    # 50% per asset (for testing)
            max_total_exposure=2.0,         # 200% total exposure
            max_leverage=2.0,               # 2x leverage
            max_open_positions=50,          # Max 50 positions
            max_positions_per_asset=5,      # 5 positions per asset
            max_drawdown_pct=0.50,          # 50% max drawdown (for testing)
            max_daily_drawdown_pct=0.25,    # 25% daily drawdown
            max_trades_per_day=200,         # 200 trades/day
            max_trades_per_hour=50,         # 50 trades/hour
            max_concentration_pct=50.0,     # 50% concentration limit
        )

        self.register_policy(conservative)
        self.register_policy(moderate)
        self.register_policy(aggressive)
        self.register_policy(paper_trading)

    def register_policy(self, policy: RiskPolicy):
        """Register a risk policy."""
        key = f"{policy.name}:{policy.version}"
        if key in self._policies:
            logger.warning(f"Policy {key} already registered, overwriting")
        self._policies[key] = policy
        logger.info(f"Registered risk policy: {key}")

    def get_policy(self, name: str, version: str = "1.0.0") -> Optional[RiskPolicy]:
        """Get a risk policy by name and version."""
        key = f"{name}:{version}"
        return self._policies.get(key)

    def list_policies(self) -> Dict[str, RiskPolicy]:
        """List all registered policies."""
        return self._policies.copy()

    def get_policy_by_type(self, policy_type: RiskPolicyType) -> Optional[RiskPolicy]:
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
policy_registry = RiskPolicyRegistry()


def get_default_policy(policy_type: RiskPolicyType = RiskPolicyType.MODERATE) -> RiskPolicy:
    """Get the default risk policy for a given type."""
    policy = policy_registry.get_policy_by_type(policy_type)
    if policy is None:
        raise ValueError(f"No default policy found for type: {policy_type.value}")
    return policy
