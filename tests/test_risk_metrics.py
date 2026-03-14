"""
Tests for Risk Metrics Calculator
==================================
Verify proper risk metric calculations.
"""
import unittest
import numpy as np
from core.risk_metrics import RiskMetricsCalculator


class TestSharpeRatio(unittest.TestCase):
    """Test Sharpe ratio calculation."""
    
    def test_basic_sharpe(self):
        """Test basic Sharpe ratio calculation."""
        returns = np.array([0.01, 0.02, -0.01, 0.03, 0.01])
        sharpe = RiskMetricsCalculator.calculate_sharpe_ratio(returns)
        self.assertIsInstance(sharpe, float)
        self.assertGreater(sharpe, 0)  # Should be positive for these returns
    
    def test_insufficient_data(self):
        """Test with insufficient data."""
        returns = np.array([0.01])
        sharpe = RiskMetricsCalculator.calculate_sharpe_ratio(returns)
        self.assertEqual(sharpe, 0.0)
    
    def test_zero_volatility(self):
        """Test with zero volatility."""
        returns = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        sharpe = RiskMetricsCalculator.calculate_sharpe_ratio(returns)
        self.assertEqual(sharpe, 0.0)
    
    def test_negative_returns(self):
        """Test with negative returns."""
        returns = np.array([-0.01, -0.02, -0.01, -0.03])
        sharpe = RiskMetricsCalculator.calculate_sharpe_ratio(returns)
        self.assertLess(sharpe, 0)  # Should be negative
    
    def test_annualization(self):
        """Test annualization factor."""
        returns = np.array([0.01] * 365)  # Daily returns
        sharpe_daily = RiskMetricsCalculator.calculate_sharpe_ratio(returns, periods_per_year=365)
        sharpe_monthly = RiskMetricsCalculator.calculate_sharpe_ratio(returns[:30], periods_per_year=12)
        # Both should be reasonable values
        self.assertIsInstance(sharpe_daily, float)
        self.assertIsInstance(sharpe_monthly, float)


class TestSortinoRatio(unittest.TestCase):
    """Test Sortino ratio calculation."""
    
    def test_basic_sortino(self):
        """Test basic Sortino ratio."""
        returns = np.array([0.01, 0.02, -0.01, -0.005, 0.03, 0.01, -0.002])
        sortino = RiskMetricsCalculator.calculate_sortino_ratio(returns)
        self.assertIsInstance(sortino, float)
        self.assertGreater(sortino, 0)
    
    def test_no_downside(self):
        """Test with no downside returns."""
        returns = np.array([0.01, 0.02, 0.01, 0.03])
        sortino = RiskMetricsCalculator.calculate_sortino_ratio(returns)
        self.assertEqual(sortino, 10.0)  # High value when no downside


class TestVaR(unittest.TestCase):
    """Test Value at Risk calculation."""
    
    def test_basic_var(self):
        """Test basic VaR calculation."""
        var_95 = RiskMetricsCalculator.calculate_var(price=1000.0, volatility=0.02, confidence=0.95)
        self.assertIsInstance(var_95, float)
        self.assertGreater(var_95, 0)
        # VaR at 95% with 2% volatility should be around 32-33
        self.assertGreater(var_95, 30)
        self.assertLess(var_95, 40)
    
    def test_var_99(self):
        """Test VaR at 99% confidence."""
        var_99 = RiskMetricsCalculator.calculate_var(price=1000.0, volatility=0.02, confidence=0.99)
        var_95 = RiskMetricsCalculator.calculate_var(price=1000.0, volatility=0.02, confidence=0.95)
        # 99% VaR should be higher than 95% VaR
        self.assertGreater(var_99, var_95)
    
    def test_var_scales_with_price(self):
        """Test that VaR scales with price."""
        var_1000 = RiskMetricsCalculator.calculate_var(price=1000.0, volatility=0.02, confidence=0.95)
        var_2000 = RiskMetricsCalculator.calculate_var(price=2000.0, volatility=0.02, confidence=0.95)
        # Should scale linearly
        self.assertAlmostEqual(var_2000 / var_1000, 2.0, places=1)


class TestCalmarRatio(unittest.TestCase):
    """Test Calmar ratio calculation."""
    
    def test_basic_calmar(self):
        """Test basic Calmar ratio."""
        returns = np.array([0.01, 0.02, -0.01, 0.03, 0.01])
        calmar = RiskMetricsCalculator.calculate_calmar_ratio(returns)
        self.assertIsInstance(calmar, float)


class TestInformationRatio(unittest.TestCase):
    """Test Information ratio calculation."""
    
    def test_basic_information_ratio(self):
        """Test basic Information ratio."""
        strategy_returns = np.array([0.01, 0.02, -0.01, 0.03, 0.01])
        benchmark_returns = np.array([0.005, 0.01, -0.005, 0.015, 0.005])
        info_ratio = RiskMetricsCalculator.calculate_information_ratio(strategy_returns, benchmark_returns)
        self.assertIsInstance(info_ratio, float)
    
    def test_mismatched_length(self):
        """Test with mismatched array lengths."""
        strategy_returns = np.array([0.01, 0.02])
        benchmark_returns = np.array([0.005, 0.01, 0.005])
        info_ratio = RiskMetricsCalculator.calculate_information_ratio(strategy_returns, benchmark_returns)
        self.assertEqual(info_ratio, 0.0)


if __name__ == '__main__':
    unittest.main()
