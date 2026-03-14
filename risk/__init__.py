"""
Risk Management Domain Package

This package contains components for enforcing hard risk policy
on trading operations. It operates on portfolio state and enforces
limits like max exposure per asset, max leverage, max drawdown, etc.

Key architectural rule: Risk Manager enforces safety.
It contains NO inference, NO learning, and NO strategy logic.
"""

from .risk_manager import RiskManager
from .risk_policy import RiskPolicy, RiskPolicyType, RiskPolicyRegistry, get_default_policy
from .risk_verdict import (
    RiskVerdict, RiskConstraint, RiskAssessment,
    RiskVerdictAggregator, approved, rejected, approved_with_constraints
)
from .limits import (
    LimitType, RiskLimit, RiskLimits, RiskViolation, LimitCalculator,
    get_conservative_limits, get_moderate_limits, get_aggressive_limits, get_paper_trading_limits
)

__all__ = [
    # Risk Manager
    'RiskManager',

    # Risk Policies
    'RiskPolicy', 'RiskPolicyType', 'RiskPolicyRegistry', 'get_default_policy',

    # Risk Verdicts
    'RiskVerdict', 'RiskConstraint', 'RiskAssessment',
    'RiskVerdictAggregator', 'approved', 'rejected', 'approved_with_constraints',

    # Risk Limits
    'LimitType', 'RiskLimit', 'RiskLimits', 'LimitCalculator',
    'get_conservative_limits', 'get_moderate_limits', 'get_aggressive_limits', 'get_paper_trading_limits',
]

