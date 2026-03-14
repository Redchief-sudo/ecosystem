"""
Risk Manager for trading system.

This module provides the RiskManager class for enforcing hard risk policy
on TradeIntents. It approves, rejects, or constrains TradeIntents based on
portfolio state and risk limits.

IMPORTANT: This module contains NO inference, NO learning, and NO strategy logic.
It is purely rule-based and deterministic. No ML imports, no torch, no sklearn.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from decimal import Decimal
import logging

from risk.portfolio_risk_optimizer import PortfolioRiskOptimizer, Position

logger = logging.getLogger(__name__)


class RiskVerdict(Enum):
    """Risk assessment verdicts"""
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVED_WITH_CONSTRAINTS = "approved_with_constraints"


@dataclass
class RiskAssessment:
    """Result of risk assessment"""
    verdict: RiskVerdict
    reason: str
    constraints: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.verdict == RiskVerdict.APPROVED


class RiskManager:
    """
    Risk Manager enforces hard risk policy on TradeIntents.

    This component operates on portfolio state and enforces limits like:
    - Max exposure per asset
    - Max leverage
    - Max drawdown
    - Max open trades
    - Max concentration per asset
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Risk Manager.

        Args:
            config: Risk management configuration
        """
        self.config = config

        # FIX: Use realistic paper trading values from config
        trading_config = config.get('trading', {})
        paper_config = trading_config.get('paper_trading', {})
        position_config = trading_config.get('position_sizing', {})

        # Portfolio value based on paper trading config (default $100 per network × networks)
        portfolio_value = paper_config.get('portfolio_value_per_network', 100.0) * 20  # ~20 networks

        self.risk_limits = config.get('limits', {
            'max_exposure_per_asset': position_config.get('max_size', 0.05),  # 5% max per asset
            'max_total_exposure': trading_config.get('max_total_exposure', 0.3),  # 30% max total
            'max_leverage': trading_config.get('max_leverage', 1.0),  # No leverage
            'max_drawdown': trading_config.get('max_drawdown', 0.15),  # 15% max drawdown
            'max_open_trades': 10,  # Max concurrent trades
            'max_daily_trades': 50,  # Max trades per day
            'max_concentration_pct': 25,  # Max concentration %
        })

        # FIX: Use realistic portfolio state from config
        self.portfolio_state = {
            'total_value': portfolio_value,
            'cash_available': portfolio_value,  # All cash available in paper trading
            'positions': {},  # asset -> position details
            'current_exposure': 0.0,
            'daily_trades': 0,
            'current_drawdown': 0.0,
        }

        # Initialize portfolio risk optimizer (institutional-grade)
        max_portfolio_var = config.get('max_portfolio_var', 0.05)  # 5% default
        self.portfolio_optimizer = PortfolioRiskOptimizer(max_portfolio_var=max_portfolio_var)

        logger.info("✅ Risk Manager initialized")
        logger.info(f"📊 Portfolio value: ${portfolio_value:.2f}")
        logger.info(f"📊 Risk limits: {self.risk_limits}")
        logger.info(f"📊 Portfolio optimizer: max_var={max_portfolio_var:.1%}")

    def assess_trade_intent(self, trade_intent, portfolio_state: Optional[Dict] = None) -> RiskAssessment:
        """
        Assess a TradeIntent against risk policy.

        Args:
            trade_intent: The trade intent to assess
            portfolio_state: Current portfolio state (optional, uses internal if not provided)

        Returns:
            RiskAssessment with verdict and constraints
        """
        # Pure assessment: read-only portfolio view
        state = portfolio_state or self.portfolio_state

        # Extract trade parameters
        token_address = getattr(trade_intent, 'token_out', getattr(trade_intent, 'token_address', ''))
        amount_usd = getattr(trade_intent, 'amount_usd', 0)
        side = getattr(trade_intent, 'side', '').lower()
        chain = getattr(trade_intent, 'chain', 'unknown')

        asset_key = (chain, token_address)

        # 1. Check max exposure per asset
        exposure_check = self._check_asset_exposure(state, asset_key, amount_usd, side)
        if not exposure_check:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason=f"Asset exposure limit exceeded for {token_address}",
                metadata={'limit_type': 'asset_exposure', 'token': token_address}
            )

        # 2. Check total exposure limit
        total_exposure_check = self._check_total_exposure(state, amount_usd, side)
        if not total_exposure_check:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason="Total portfolio exposure limit exceeded",
                metadata={'limit_type': 'total_exposure'}
            )

        # 3. Check max open trades
        open_trades_check = self._check_open_trades_limit(state)
        if not open_trades_check:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason="Maximum open trades limit exceeded",
                metadata={'limit_type': 'open_trades'}
            )

        # 4. Check daily trade limit
        daily_trades_check = self._check_daily_trades_limit(state)
        if not daily_trades_check:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason="Daily trade limit exceeded",
                metadata={'limit_type': 'daily_trades'}
            )

        # 5. Check drawdown limit
        drawdown_check = self._check_drawdown_limit(state)
        if not drawdown_check:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason="Portfolio drawdown limit exceeded",
                metadata={'limit_type': 'drawdown'}
            )

        # 6. Check concentration limit
        concentration_check = self._check_concentration_limit(state, asset_key, amount_usd, side)
        if not concentration_check:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason="Portfolio concentration limit exceeded",
                metadata={'limit_type': 'concentration', 'token': token_address}
            )

        # 7. NEW: Portfolio-level risk check (institutional-grade)
        portfolio_risk_check = self._check_portfolio_risk(trade_intent, state)
        if not portfolio_risk_check['approved']:
            if portfolio_risk_check.get('optimal_size'):
                # Suggest reduced size
                return RiskAssessment(
                    verdict=RiskVerdict.APPROVED_WITH_CONSTRAINTS,
                    reason=f"Portfolio risk limit: reduce size to ${portfolio_risk_check['optimal_size']:.2f}",
                    constraints={'max_amount_usd': portfolio_risk_check['optimal_size']},
                    metadata={
                        'limit_type': 'portfolio_var',
                        'current_var': portfolio_risk_check.get('current_var'),
                        'max_var': portfolio_risk_check.get('max_var'),
                        'original_size': amount_usd,
                        'optimal_size': portfolio_risk_check['optimal_size']
                    }
                )
            else:
                return RiskAssessment(
                    verdict=RiskVerdict.REJECTED,
                    reason="Portfolio risk limit exceeded",
                    metadata={'limit_type': 'portfolio_var'}
                )

        # All checks passed - determine if constraints needed
        constraints = self._calculate_constraints(state, trade_intent)

        if constraints:
            return RiskAssessment(
                verdict=RiskVerdict.REJECTED,
                reason="Trade exceeds limits; resubmit with constraints",
                constraints=constraints,
                metadata={'constraints_applied': list(constraints.keys())}
            )

        return RiskAssessment(
            verdict=RiskVerdict.APPROVED,
            reason="All risk checks passed",
            metadata={'checks_passed': ['asset_exposure', 'total_exposure', 'open_trades', 'daily_trades', 'drawdown', 'concentration']}
        )

    def update_portfolio_state(self, portfolio_state: Dict[str, Any]):
        """
        Update the internal portfolio state.

        Args:
            portfolio_state: New portfolio state
        """
        self.portfolio_state.update(portfolio_state)
        logger.debug(f"📊 Portfolio state updated: {len(portfolio_state)} fields")

    def _check_asset_exposure(self, state: Dict[str, Any], asset_key, amount_usd: float, side: str) -> bool:
        """Check per-asset exposure with direction awareness."""
        positions = state.get('positions', {})
        current_exposure = positions.get(asset_key, {}).get('exposure_usd', 0)
        delta = amount_usd if side == 'buy' else -amount_usd
        new_exposure = max(0.0, current_exposure + delta)
        max_exposure = state['total_value'] * self.risk_limits['max_exposure_per_asset']
        return new_exposure <= max_exposure

    def _check_total_exposure(self, state: Dict[str, Any], amount_usd: float, side: str) -> bool:
        """Check total exposure with direction awareness."""
        current = state.get('current_exposure', 0.0)
        delta = amount_usd if side == 'buy' else -amount_usd
        new_total_exposure = max(0.0, current + delta)
        max_total_exposure = state['total_value'] * self.risk_limits['max_total_exposure']
        return new_total_exposure <= max_total_exposure

    def _check_open_trades_limit(self, state: Dict[str, Any]) -> bool:
        """Check if we're under the open trades limit."""
        current_open_trades = len([p for p in state.get('positions', {}).values() if p.get('active', False)])
        return current_open_trades < self.risk_limits['max_open_trades']

    def _check_daily_trades_limit(self, state: Dict[str, Any]) -> bool:
        """Check if we're under the daily trades limit."""
        return state.get('daily_trades', 0) < self.risk_limits['max_daily_trades']

    def _check_drawdown_limit(self, state: Dict[str, Any]) -> bool:
        """Check if current drawdown is within limits."""
        return state.get('current_drawdown', 0) <= self.risk_limits['max_drawdown']

    def _check_concentration_limit(self, state: Dict[str, Any], asset_key, amount_usd: float, side: str) -> bool:
        """Check if this trade would exceed concentration limits."""
        current_exposure = state.get('positions', {}).get(asset_key, {}).get('exposure_usd', 0)
        delta = amount_usd if side == 'buy' else -amount_usd
        new_exposure = max(0.0, current_exposure + delta)
        concentration_ratio = new_exposure / state['total_value']
        return concentration_ratio <= self.risk_limits['max_exposure_per_asset']
    
    def _check_portfolio_risk(self, trade_intent, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check portfolio-level risk using PortfolioRiskOptimizer (institutional-grade).
        
        Args:
            trade_intent: Trade intent to check
            state: Portfolio state
        
        Returns:
            Dictionary with 'approved', 'optimal_size', 'current_var', 'max_var'
        """
        try:
            # Extract trade parameters
            token_address = getattr(trade_intent, 'token_out', getattr(trade_intent, 'token_address', ''))
            amount_usd = getattr(trade_intent, 'amount_usd', 0)
            chain = getattr(trade_intent, 'chain', 'unknown')
            price = getattr(trade_intent, 'price', 0) or getattr(trade_intent, 'entry_price', 0)
            volatility = getattr(trade_intent, 'volatility', 0.02)  # Default 2% if not provided
            
            if amount_usd <= 0 or price <= 0:
                return {'approved': True}  # Skip if invalid data
            
            # Build current portfolio positions for optimizer
            current_positions = {}
            positions_dict = state.get('positions', {})
            
            for asset_key, pos_data in positions_dict.items():
                if pos_data.get('active', False):
                    chain_pos, token_pos = asset_key if isinstance(asset_key, tuple) else ('unknown', str(asset_key))
                    current_positions[f"{chain_pos}:{token_pos}"] = Position(
                        symbol=token_pos,
                        chain=chain_pos,
                        size_usd=pos_data.get('exposure_usd', 0),
                        entry_price=pos_data.get('entry_price', 0),
                        current_price=pos_data.get('current_price', pos_data.get('entry_price', 0)),
                        volatility=pos_data.get('volatility', 0.02)
                    )
            
            # Update optimizer with current positions
            self.portfolio_optimizer.update_positions(current_positions)
            
            # Create new position object
            new_position = Position(
                symbol=token_address,
                chain=chain,
                size_usd=amount_usd,
                entry_price=price,
                current_price=price,
                volatility=volatility
            )
            
            # Optimize position size
            optimal_size, metadata = self.portfolio_optimizer.optimize_position_size(new_position)
            
            if optimal_size < amount_usd:
                # Position size needs to be reduced
                return {
                    'approved': False,
                    'optimal_size': optimal_size,
                    'current_var': metadata.get('current_var', 0),
                    'max_var': metadata.get('max_var', 0),
                    'metadata': metadata
                }
            
            # Position size is acceptable
            return {
                'approved': True,
                'optimal_size': amount_usd,
                'current_var': metadata.get('current_var', 0),
                'max_var': metadata.get('max_var', 0)
            }
            
        except Exception as e:
            logger.warning(f"Portfolio risk check error: {e}", exc_info=True)
            # Fail open - allow trade if portfolio check fails
            return {'approved': True}

    def _calculate_constraints(self, state: Dict[str, Any], trade_intent) -> Optional[Dict[str, Any]]:
        """
        Calculate any risk-based constraints that should be applied to the trade.

        Returns:
            Dict of constraints or None if no constraints needed
        """
        constraints = {}

        amount_usd = getattr(trade_intent, 'amount_usd', 0)
        token_address = getattr(trade_intent, 'token_out', getattr(trade_intent, 'token_address', ''))
        chain = getattr(trade_intent, 'chain', 'unknown')
        asset_key = (chain, token_address)
        side = getattr(trade_intent, 'side', '').lower()

        positions = state.get('positions', {})
        current_exposure = positions.get(asset_key, {}).get('exposure_usd', 0)
        max_asset_exposure = state['total_value'] * self.risk_limits['max_exposure_per_asset']
        max_additional = max_asset_exposure - current_exposure

        if side == 'sell':
            return None

        if amount_usd > max_additional:
            constraints['max_amount_usd'] = max(0.0, max_additional)

        return constraints if constraints else None

    def log_risk_decision(self, trade_intent, assessment: RiskAssessment):
        """Log the risk decision for audit purposes."""
        token = getattr(trade_intent, 'token_out', getattr(trade_intent, 'token_address', 'unknown'))
        amount = getattr(trade_intent, 'amount_usd', 0)

        if assessment.verdict == RiskVerdict.APPROVED:
            logger.info(f"✅ Risk APPROVED: {token} | Amount: ${amount:.2f} | Reason: {assessment.reason}")
        elif assessment.verdict == RiskVerdict.APPROVED_WITH_CONSTRAINTS:
            logger.warning(f"⚠️ Risk APPROVED WITH CONSTRAINTS: {token} | Amount: ${amount:.2f} | Constraints: {assessment.constraints}")
        else:
            logger.error(f"❌ Risk REJECTED: {token} | Amount: ${amount:.2f} | Reason: {assessment.reason}")

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics for monitoring."""
        # Get portfolio metrics from optimizer
        portfolio_metrics = self.portfolio_optimizer.calculate_portfolio_metrics()
        
        return {
            'portfolio_value': self.portfolio_state['total_value'],
            'current_exposure': self.portfolio_state['current_exposure'],
            'exposure_ratio': self.portfolio_state['current_exposure'] / self.portfolio_state['total_value'],
            'open_positions': len([p for p in self.portfolio_state['positions'].values() if p.get('active', False)]),
            'daily_trades': self.portfolio_state['daily_trades'],
            'current_drawdown': self.portfolio_state['current_drawdown'],
            'risk_limits': self.risk_limits,
            # NEW: Portfolio-level metrics (institutional-grade)
            'portfolio_var_95': portfolio_metrics.portfolio_var_95,
            'portfolio_var_99': portfolio_metrics.portfolio_var_99,
            'portfolio_volatility': portfolio_metrics.portfolio_volatility,
            'concentration_risk': portfolio_metrics.concentration_risk,
        }
