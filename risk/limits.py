"""
Risk management limits module.

Units:
- 'ratio': 0-1 float (e.g., 0.25 for 25%)
- 'usd': USD amount
- 'count': integer count
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict

class LimitType(Enum):
    """Types of risk limits that can be enforced."""
    EXPOSURE_PER_ASSET = "exposure_per_asset"  # USD exposure per asset
    TOTAL_EXPOSURE = "total_exposure"          # Total portfolio exposure (USD)
    LEVERAGE = "leverage"                      # Leverage ratio
    OPEN_POSITIONS = "open_positions"          # Number of open positions
    POSITIONS_PER_ASSET = "positions_per_asset"  # Positions per asset
    MAX_DRAWDOWN_RATIO = "max_drawdown_ratio"  # Portfolio drawdown ratio
    DRAWDOWN = "drawdown"                      # Portfolio drawdown % (deprecated)
    DAILY_DRAWDOWN = "daily_drawdown"          # Daily drawdown %
    TRADES_PER_DAY = "trades_per_day"          # Trades per day
    TRADES_PER_HOUR = "trades_per_hour"        # Trades per hour
    CONCENTRATION = "concentration"            # Concentration per asset %


@dataclass
class RiskViolation:
    """
    Represents a risk limit violation.

    Used to signal when limits are exceeded, enabling structured
    logging and clear risk decision-making.
    """
    limit_type: LimitType
    current_value: float
    threshold: float
    enforcement: str
    unit: str
    message: str
    asset_symbol: Optional[str] = None
    asset_id: Optional[str] = None  # Added

    def is_hard_violation(self) -> bool:
        """Check if this is a hard limit violation."""
        return self.enforcement == "hard"

    def is_soft_violation(self) -> bool:
        """Check if this is a soft limit violation."""
        return self.enforcement == "soft"





@dataclass
class RiskLimit:
    """
    A specific risk limit configuration.

    Defines a boundary that trading operations must not exceed.
    Units are explicit to prevent misinterpretation.
    """
    limit_type: LimitType
    threshold: float
    unit: str  # Now only accepts 'ratio', 'usd', 'count'
    enforcement: str
    description: str = ""
    enabled: bool = True

    def __post_init__(self):
        if self.enforcement not in ["hard", "soft", "warning"]:
            raise ValueError(f"enforcement must be 'hard', 'soft', or 'warning', got {self.enforcement}")

        if self.unit not in ['ratio', 'usd', 'count']:
            raise ValueError(f"unit must be 'ratio', 'usd', 'count', got {self.unit}")

        if self.threshold < 0:
            raise ValueError(f"threshold must be non-negative, got {self.threshold}")

    def is_hard_limit(self) -> bool:
        """Check if this is a hard limit (violations block trades)."""
        return self.enforcement == "hard"

    def is_soft_limit(self) -> bool:
        """Check if this is a soft limit (violations allow but constrain trades)."""
        return self.enforcement == "soft"

    def is_warning_only(self) -> bool:
        """Check if this is a warning-only limit (no enforcement)."""
        return self.enforcement == "warning"

    def check_violation(self, current_value: float, asset_id: Optional[str] = None) -> Optional[RiskViolation]:
        """
        Check if current value violates this limit.

        Returns RiskViolation if violated, None if compliant.
        All violations are returned - RiskManager handles enforcement.
        """
        if not self.enabled:
            return None

        if current_value > self.threshold:  # Fixed logic
            return RiskViolation(
                limit_type=self.limit_type,
                threshold=self.threshold,
                current_value=current_value,
                enforcement=self.enforcement,
                unit=self.unit,
                message=f"{self.description}: {current_value} exceeds threshold {self.threshold}",
                asset_id=asset_id
            )

        return None


@dataclass
class RiskLimits:
    """
    Complete set of risk limits for a trading operation.

    Pure data container - no enforcement logic. Enforcement belongs in RiskManager.
    """
    limits: List[RiskLimit]

    def __post_init__(self):
        limit_types = [limit.limit_type for limit in self.limits]
        if len(limit_types) != len(set(limit_types)):
            raise ValueError("Duplicate limit types not allowed")
        hard_limits = self.get_hard_limits()
        if not any(limit.limit_type == LimitType.CONCENTRATION for limit in hard_limits):
            raise ValueError("Hard limit for CONCENTRATION is required")
        # Add similar checks for other core limits as needed

    def get_hard_limits(self) -> List[RiskLimit]:
        return [limit for limit in self.limits if limit.enforcement == 'hard']

    def get_soft_limits(self) -> List[RiskLimit]:
        return [limit for limit in self.limits if limit.enforcement == 'soft']

    def get_warning_limits(self) -> List[RiskLimit]:
        return [limit for limit in self.limits if limit.enforcement == 'warning']

    def get_limit(self, limit_type: LimitType) -> Optional[RiskLimit]:
        """Get a specific limit by type."""
        for limit in self.limits:
            if limit.limit_type == limit_type:
                return limit
        return None

    def get_enabled_limits(self) -> List[RiskLimit]:
        """Get all enabled limits."""
        return [limit for limit in self.limits if limit.enabled]


class LimitCalculator:
    """
    Utility for calculating risk metrics and constraints.

    Provides common calculations used by the Risk Manager.
    """

    @staticmethod
    def calculate_concentration(position_value: float, portfolio_value: float) -> float:
        """Calculate concentration ratio for an asset (0-1)."""
        if portfolio_value == 0:
            return 0.0
        return position_value / portfolio_value  # Fixed to use portfolio_value

    @staticmethod
    def calculate_portfolio_exposure(positions: List[dict], direction: str = 'long') -> float:
        """Calculate total portfolio exposure from positions (direction-aware)."""
        exposure = 0.0
        for pos in positions:
            if direction == 'long' and pos.get('side') == 'long':
                exposure += pos.get('value', 0)
            elif direction == 'short' and pos.get('side') == 'short':
                exposure += abs(pos.get('value', 0))  # Direction-aware
        return exposure

    @staticmethod
    def calculate_drawdown(current_value: float, peak_value: float) -> float:
        """Calculate drawdown percentage."""
        if peak_value == 0:
            return 0.0
        return (peak_value - current_value) / peak_value  # Ratio semantics (0-1)

    @staticmethod
    def constrain_trade_amount(requested_amount: float,
                             available_limit: float,
                             buffer_pct: float = 0.1) -> float:
        """
        Constrain a trade amount to fit within available limit.

        Applies a buffer to ensure we don't exceed limits due to slippage.
        """
        buffered_limit = available_limit * (1.0 - buffer_pct)
        return min(requested_amount, buffered_limit)


# Predefined limit configurations for different risk profiles

def get_conservative_limits() -> RiskLimits:
    return RiskLimits([
        RiskLimit(LimitType.CONCENTRATION, 0.20, 'ratio', 'hard', 'Max 20% concentration'),
        RiskLimit(LimitType.TOTAL_EXPOSURE, 0.50, 'ratio', 'hard', 'Max 50% exposure'),
        RiskLimit(LimitType.DRAWDOWN, 0.10, 'ratio', 'hard', 'Max 10% drawdown'),
        RiskLimit(LimitType.MAX_DRAWDOWN_RATIO, 0.15, 'ratio', 'soft', 'Max drawdown ratio'),
        # Add other limits as needed
    ])

def get_moderate_limits() -> RiskLimits:
    return RiskLimits([
        RiskLimit(LimitType.CONCENTRATION, 0.25, 'ratio', 'hard', 'Max 25% concentration'),
        RiskLimit(LimitType.TOTAL_EXPOSURE, 0.75, 'ratio', 'soft', 'Max 75% exposure'),
        RiskLimit(LimitType.DRAWDOWN, 0.15, 'ratio', 'hard', 'Max 15% drawdown'),
        RiskLimit(LimitType.MAX_DRAWDOWN_RATIO, 0.20, 'ratio', 'soft', 'Max drawdown ratio'),
        # Add other limits as needed
    ])

def get_aggressive_limits() -> RiskLimits:
    return RiskLimits([
        RiskLimit(LimitType.CONCENTRATION, 0.30, 'ratio', 'soft', 'Max 30% concentration'),
        RiskLimit(LimitType.TOTAL_EXPOSURE, 1.0, 'ratio', 'soft', 'Max 100% exposure'),
        RiskLimit(LimitType.DRAWDOWN, 0.20, 'ratio', 'soft', 'Max 20% drawdown'),
        RiskLimit(LimitType.MAX_DRAWDOWN_RATIO, 0.25, 'ratio', 'soft', 'Max drawdown ratio'),
        # Add other limits as needed
    ])

def get_paper_trading_limits() -> RiskLimits:
    return RiskLimits([
        RiskLimit(LimitType.CONCENTRATION, 0.50, 'ratio', 'hard', 'Max 50% concentration'),  # Hard enforcement
        RiskLimit(LimitType.TOTAL_EXPOSURE, 1.0, 'ratio', 'hard', 'Max 100% exposure'),
        RiskLimit(LimitType.DRAWDOWN, 0.25, 'ratio', 'hard', 'Max 25% drawdown'),
        RiskLimit(LimitType.MAX_DRAWDOWN_RATIO, 0.30, 'ratio', 'hard', 'Max drawdown ratio'),
        # Add other limits as needed
    ])
