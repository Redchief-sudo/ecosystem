"""
Portfolio Risk Optimizer - INSTITUTIONAL GRADE
==============================================
Portfolio-level risk management with correlation matrices.
Optimizes position sizing based on portfolio-level VaR and correlations.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a position in the portfolio."""
    symbol: str
    chain: str
    size_usd: float
    entry_price: float
    current_price: float
    volatility: float
    beta: float = 1.0  # Beta relative to market


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""
    total_value: float
    total_exposure: float
    portfolio_var_95: float
    portfolio_var_99: float
    portfolio_volatility: float
    max_drawdown: float
    correlation_matrix: np.ndarray
    concentration_risk: float


class PortfolioRiskOptimizer:
    """
    Optimize position sizing based on portfolio-level risk.
    
    Uses variance-covariance method for portfolio VaR calculation,
    considering correlations between positions.
    """
    
    def __init__(self, max_portfolio_var: float = 0.05):
        """
        Initialize portfolio risk optimizer.
        
        Args:
            max_portfolio_var: Maximum portfolio VaR as % of portfolio value (default 5%)
        """
        self.max_portfolio_var = max_portfolio_var
        self.positions: Dict[str, Position] = {}
        self.correlation_matrix: Optional[np.ndarray] = None
        self.symbols: List[str] = []
        
        logger.info(f"PortfolioRiskOptimizer initialized (max_portfolio_var={max_portfolio_var:.1%})")
    
    def update_positions(self, positions: Dict[str, Position]):
        """
        Update portfolio positions.
        
        Args:
            positions: Dictionary of {symbol: Position}
        """
        self.positions = positions
        self.symbols = list(positions.keys())
        self._update_correlation_matrix()
        
        logger.debug(f"Updated portfolio positions: {len(self.positions)} positions")
    
    def _update_correlation_matrix(self):
        """
        Update correlation matrix from price history.
        
        In production, this would use historical price data to calculate
        actual correlations. For now, uses simplified correlation estimates.
        """
        n = len(self.symbols)
        if n == 0:
            self.correlation_matrix = None
            return
        
        # Default correlation matrix (can be enhanced with real data)
        # Assumes moderate correlation (0.3) between different assets
        # and perfect correlation (1.0) with itself
        base_correlation = 0.3
        self.correlation_matrix = np.eye(n) * (1.0 - base_correlation) + np.ones((n, n)) * base_correlation
        np.fill_diagonal(self.correlation_matrix, 1.0)
        
        logger.debug(f"Updated correlation matrix: {n}x{n}")
    
    def calculate_portfolio_var(
        self,
        confidence: float = 0.95,
        time_horizon_days: int = 1
    ) -> float:
        """
        Calculate portfolio Value at Risk using variance-covariance method.
        
        VaR = sqrt(w' * Σ * w) * Z_score * sqrt(time_horizon)
        
        Where:
        - w = position weights vector
        - Σ = covariance matrix
        - Z_score = confidence level z-score
        
        Args:
            confidence: Confidence level (0.95 for 95%, 0.99 for 99%)
            time_horizon_days: Time horizon in days
        
        Returns:
            Portfolio VaR in absolute terms (USD)
        """
        if len(self.positions) == 0:
            return 0.0
        
        # Get position values and volatilities
        values = np.array([p.size_usd for p in self.positions.values()])
        volatilities = np.array([p.volatility for p in self.positions.values()])
        
        total_value = np.sum(values)
        if total_value == 0:
            return 0.0
        
        # Position weights (normalized)
        weights = values / total_value
        
        # Ensure correlation matrix is updated
        if self.correlation_matrix is None:
            self._update_correlation_matrix()
        
        # Covariance matrix = correlation * volatility * volatility'
        vol_matrix = np.outer(volatilities, volatilities)
        covariance_matrix = self.correlation_matrix * vol_matrix
        
        # Portfolio variance: w' * Σ * w
        portfolio_variance = weights.T @ covariance_matrix @ weights
        
        # Portfolio volatility (standard deviation)
        portfolio_vol = np.sqrt(portfolio_variance)
        
        # Z-score for confidence level
        z_score = norm.ppf(confidence)
        
        # VaR = Total Value * Portfolio Volatility * Z-score * sqrt(time_horizon)
        var = total_value * portfolio_vol * z_score * np.sqrt(time_horizon_days)
        
        logger.debug(
            f"Portfolio VaR ({confidence:.0%}): ${var:.2f} "
            f"(vol={portfolio_vol:.4f}, z={z_score:.2f})"
        )
        
        return float(var)
    
    def optimize_position_size(
        self,
        new_position: Position,
        max_additional_var: Optional[float] = None
    ) -> Tuple[float, Dict[str, any]]:
        """
        Optimize position size for new position considering portfolio risk.
        
        Calculates incremental VaR and adjusts position size to stay within limits.
        
        Args:
            new_position: Proposed new position
            max_additional_var: Maximum additional VaR allowed (default: max_portfolio_var)
        
        Returns:
            Tuple of (optimal_size, metadata)
        """
        if max_additional_var is None:
            max_additional_var = self.max_portfolio_var
        
        # Calculate current portfolio VaR
        current_var = self.calculate_portfolio_var()
        portfolio_value = sum(p.size_usd for p in self.positions.values())
        
        # Simplified incremental VaR calculation
        # In production, would calculate full portfolio VaR with new position
        new_position_var = new_position.size_usd * new_position.volatility
        
        # Estimate total VaR with new position (simplified)
        # More accurate would be: recalculate full portfolio VaR including new position
        total_var = current_var + new_position_var
        max_var_limit = portfolio_value * max_additional_var
        
        if total_var > max_var_limit:
            # Reduce position size to stay within limits
            max_size = (max_var_limit - current_var) / new_position.volatility
            optimal_size = max(0.0, max_size)
            
            logger.info(
                f"Portfolio risk limit: reducing position size from ${new_position.size_usd:.2f} "
                f"to ${optimal_size:.2f} (current_var=${current_var:.2f}, max=${max_var_limit:.2f})"
            )
            
            return optimal_size, {
                'reason': 'portfolio_var_limit',
                'current_var': current_var,
                'max_var': max_var_limit,
                'reduced_from': new_position.size_usd,
                'reduced_to': optimal_size,
                'var_reduction': new_position_var - (optimal_size * new_position.volatility)
            }
        
        logger.debug(
            f"Position size within limits: ${new_position.size_usd:.2f} "
            f"(current_var=${current_var:.2f}, new_var=${total_var:.2f}, max=${max_var_limit:.2f})"
        )
        
        return new_position.size_usd, {
            'reason': 'within_limits',
            'current_var': current_var,
            'new_var': total_var,
            'max_var': max_var_limit
        }
    
    def calculate_portfolio_metrics(self) -> PortfolioRiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics.
        
        Returns:
            PortfolioRiskMetrics with all calculated metrics
        """
        total_value = sum(p.size_usd for p in self.positions.values())
        total_exposure = sum(p.size_usd for p in self.positions.values())
        
        var_95 = self.calculate_portfolio_var(confidence=0.95)
        var_99 = self.calculate_portfolio_var(confidence=0.99)
        
        # Portfolio volatility
        if len(self.positions) == 0:
            portfolio_vol = 0.0
            concentration = 0.0
        else:
            values = np.array([p.size_usd for p in self.positions.values()])
            volatilities = np.array([p.volatility for p in self.positions.values()])
            weights = values / total_value if total_value > 0 else np.zeros(len(values))
            
            if self.correlation_matrix is not None and len(self.correlation_matrix) > 0:
                vol_matrix = np.outer(volatilities, volatilities)
                covariance_matrix = self.correlation_matrix * vol_matrix
                portfolio_variance = weights.T @ covariance_matrix @ weights
                portfolio_vol = np.sqrt(portfolio_variance)
            else:
                # Fallback: weighted average volatility
                portfolio_vol = np.average(volatilities, weights=weights)
            
            # Concentration risk (Herfindahl index)
            concentration = np.sum(weights ** 2)
        
        # Handle correlation matrix properly
        corr_matrix = self.correlation_matrix if self.correlation_matrix is not None else np.array([])
        
        return PortfolioRiskMetrics(
            total_value=total_value,
            total_exposure=total_exposure,
            portfolio_var_95=var_95,
            portfolio_var_99=var_99,
            portfolio_volatility=float(portfolio_vol),
            max_drawdown=0.0,  # Would need historical data
            correlation_matrix=corr_matrix,
            concentration_risk=float(concentration)
        )
    
    def get_position_weights(self) -> Dict[str, float]:
        """
        Get position weights (as % of portfolio).
        
        Returns:
            Dictionary of {symbol: weight}
        """
        total_value = sum(p.size_usd for p in self.positions.values())
        if total_value == 0:
            return {}
        
        return {
            symbol: p.size_usd / total_value
            for symbol, p in self.positions.items()
        }
    
    def check_concentration_limit(
        self,
        new_position: Position,
        max_concentration: float = 0.25
    ) -> Tuple[bool, float]:
        """
        Check if adding position would exceed concentration limit.
        
        Args:
            new_position: Proposed new position
            max_concentration: Maximum concentration per asset (default 25%)
        
        Returns:
            Tuple of (within_limit, concentration_ratio)
        """
        total_value = sum(p.size_usd for p in self.positions.values())
        new_total = total_value + new_position.size_usd
        
        if new_total == 0:
            return True, 0.0
        
        # Calculate concentration for new position
        concentration = new_position.size_usd / new_total
        
        within_limit = concentration <= max_concentration
        
        return within_limit, concentration
