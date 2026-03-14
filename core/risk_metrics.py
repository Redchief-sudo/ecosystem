"""
Institutional-Grade Risk Metrics
=================================
Proper implementations of Sharpe, Sortino, and other risk metrics.
"""
import numpy as np
from typing import List, Optional
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)

class RiskMetricsCalculator:
    """Calculate proper risk metrics from historical returns."""
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: np.ndarray,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 365
    ) -> float:
        """
        Calculate Sharpe Ratio: (Mean Return - Risk-Free Rate) / StdDev(Returns)
        
        Args:
            returns: Array of periodic returns (e.g., daily returns)
            risk_free_rate: Annual risk-free rate (default 2%)
            periods_per_year: Number of periods per year (365 for daily, 252 for trading days)
        
        Returns:
            Annualized Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0
        
        # Convert to numpy array
        returns = np.array(returns, dtype=float)
        
        # Calculate excess returns
        period_rf_rate = risk_free_rate / periods_per_year
        excess_returns = returns - period_rf_rate
        
        # Calculate mean and std dev
        mean_excess_return = np.mean(excess_returns)
        std_dev = np.std(returns, ddof=1)  # Sample std dev (ddof=1)
        
        if std_dev == 0:
            return 0.0
        
        # Annualize
        sharpe = (mean_excess_return / std_dev) * np.sqrt(periods_per_year)
        
        return float(sharpe)
    
    @staticmethod
    def calculate_sortino_ratio(
        returns: np.ndarray,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 365
    ) -> float:
        """
        Calculate Sortino Ratio: (Mean Return - Risk-Free Rate) / Downside StdDev
        
        Sortino only penalizes downside volatility (negative returns).
        """
        if len(returns) < 2:
            return 0.0
        
        returns = np.array(returns, dtype=float)
        period_rf_rate = risk_free_rate / periods_per_year
        excess_returns = returns - period_rf_rate
        
        # Downside deviation (only negative returns)
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0:
            # No downside, return high ratio
            return 10.0
        
        if len(downside_returns) < 2:
            # Need at least 2 points for std dev calculation
            # Use absolute value of the single downside return as proxy
            downside_std = abs(downside_returns[0])
        else:
            downside_std = np.std(downside_returns, ddof=1)
        
        if downside_std == 0:
            return 0.0
        
        mean_excess_return = np.mean(excess_returns)
        sortino = (mean_excess_return / downside_std) * np.sqrt(periods_per_year)
        
        return float(sortino)
    
    @staticmethod
    def calculate_calmar_ratio(
        returns: np.ndarray,
        periods_per_year: int = 365
    ) -> float:
        """
        Calculate Calmar Ratio: Annual Return / Max Drawdown
        
        Higher is better. Measures return per unit of maximum drawdown.
        """
        if len(returns) < 2:
            return 0.0
        
        returns = np.array(returns, dtype=float)
        
        # Calculate cumulative returns
        cumulative = np.cumprod(1 + returns)
        
        # Calculate max drawdown
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(np.min(drawdown))
        
        if max_drawdown == 0:
            return 0.0
        
        # Annualized return
        total_return = cumulative[-1] / cumulative[0] - 1
        annual_return = (1 + total_return) ** (periods_per_year / len(returns)) - 1
        
        calmar = annual_return / max_drawdown
        
        return float(calmar)
    
    @staticmethod
    def calculate_information_ratio(
        strategy_returns: np.ndarray,
        benchmark_returns: np.ndarray,
        periods_per_year: int = 365
    ) -> float:
        """
        Calculate Information Ratio: Mean(Active Return) / StdDev(Active Return)
        
        Measures risk-adjusted returns relative to a benchmark.
        """
        if len(strategy_returns) != len(benchmark_returns) or len(strategy_returns) < 2:
            return 0.0
        
        strategy_returns = np.array(strategy_returns, dtype=float)
        benchmark_returns = np.array(benchmark_returns, dtype=float)
        
        # Active returns (strategy - benchmark)
        active_returns = strategy_returns - benchmark_returns
        
        mean_active = np.mean(active_returns)
        std_active = np.std(active_returns, ddof=1)
        
        if std_active == 0:
            return 0.0
        
        # Annualize
        information_ratio = (mean_active / std_active) * np.sqrt(periods_per_year)
        
        return float(information_ratio)
    
    @staticmethod
    def calculate_var(
        price: float,
        volatility: float,
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Value at Risk with proper z-scores from scipy.
        
        Args:
            price: Current price
            volatility: Volatility (standard deviation)
            confidence: Confidence level (0.95 for 95%, 0.99 for 99%)
        
        Returns:
            VaR in absolute terms
        """
        z_score = norm.ppf(confidence)  # Use scipy instead of hardcoded values
        return price * volatility * z_score
