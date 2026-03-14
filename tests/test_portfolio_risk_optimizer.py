"""
Tests for Portfolio Risk Optimizer
===================================
Verify portfolio-level risk calculations and position sizing optimization.
"""
import unittest
import numpy as np
from risk.portfolio_risk_optimizer import PortfolioRiskOptimizer, Position, PortfolioRiskMetrics


class TestPortfolioRiskOptimizer(unittest.TestCase):
    """Test PortfolioRiskOptimizer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.optimizer = PortfolioRiskOptimizer(max_portfolio_var=0.05)  # 5% max VaR
    
    def test_empty_portfolio_var(self):
        """Test VaR calculation with empty portfolio."""
        var = self.optimizer.calculate_portfolio_var()
        self.assertEqual(var, 0.0)
    
    def test_single_position_var(self):
        """Test VaR calculation with single position."""
        position = Position(
            symbol="WETH",
            chain="ethereum",
            size_usd=1000.0,
            entry_price=2000.0,
            current_price=2000.0,
            volatility=0.02
        )
        self.optimizer.update_positions({"WETH": position})
        
        var_95 = self.optimizer.calculate_portfolio_var(confidence=0.95)
        self.assertGreater(var_95, 0)
        # VaR should be approximately: 1000 * 0.02 * 1.645 ≈ 32.9
        self.assertGreater(var_95, 30)
        self.assertLess(var_95, 40)
    
    def test_multiple_positions_var(self):
        """Test VaR calculation with multiple positions."""
        positions = {
            "WETH": Position(
                symbol="WETH",
                chain="ethereum",
                size_usd=1000.0,
                entry_price=2000.0,
                current_price=2000.0,
                volatility=0.02
            ),
            "USDC": Position(
                symbol="USDC",
                chain="ethereum",
                size_usd=500.0,
                entry_price=1.0,
                current_price=1.0,
                volatility=0.001  # Low volatility for stablecoin
            )
        }
        self.optimizer.update_positions(positions)
        
        var_95 = self.optimizer.calculate_portfolio_var(confidence=0.95)
        self.assertGreater(var_95, 0)
        # Should be less than sum of individual VaRs due to diversification
        var_weth = 1000.0 * 0.02 * 1.645
        var_usdc = 500.0 * 0.001 * 1.645
        self.assertLess(var_95, var_weth + var_usdc)  # Diversification benefit
    
    def test_position_size_optimization(self):
        """Test position size optimization."""
        # Add existing position
        existing = Position(
            symbol="WETH",
            chain="ethereum",
            size_usd=1000.0,
            entry_price=2000.0,
            current_price=2000.0,
            volatility=0.02
        )
        self.optimizer.update_positions({"WETH": existing})
        
        # Try to add large new position that would exceed VaR limit
        new_position = Position(
            symbol="BTC",
            chain="ethereum",
            size_usd=10000.0,  # Large position
            entry_price=50000.0,
            current_price=50000.0,
            volatility=0.03  # High volatility
        )
        
        optimal_size, metadata = self.optimizer.optimize_position_size(new_position)
        
        # Should reduce size if it exceeds limits
        self.assertLessEqual(optimal_size, new_position.size_usd)
        self.assertGreater(optimal_size, 0)
        self.assertIn('reason', metadata)
    
    def test_position_size_within_limits(self):
        """Test position size when within limits."""
        # Small existing position
        existing = Position(
            symbol="WETH",
            chain="ethereum",
            size_usd=100.0,
            entry_price=2000.0,
            current_price=2000.0,
            volatility=0.01
        )
        self.optimizer.update_positions({"WETH": existing})
        
        # Small new position
        new_position = Position(
            symbol="USDC",
            chain="ethereum",
            size_usd=50.0,
            entry_price=1.0,
            current_price=1.0,
            volatility=0.001
        )
        
        optimal_size, metadata = self.optimizer.optimize_position_size(new_position)
        
        # Should keep original size if within limits
        self.assertEqual(optimal_size, new_position.size_usd)
        self.assertEqual(metadata['reason'], 'within_limits')
    
    def test_portfolio_metrics(self):
        """Test comprehensive portfolio metrics calculation."""
        positions = {
            "WETH": Position(
                symbol="WETH",
                chain="ethereum",
                size_usd=1000.0,
                entry_price=2000.0,
                current_price=2000.0,
                volatility=0.02
            ),
            "USDC": Position(
                symbol="USDC",
                chain="ethereum",
                size_usd=500.0,
                entry_price=1.0,
                current_price=1.0,
                volatility=0.001
            )
        }
        self.optimizer.update_positions(positions)
        
        metrics = self.optimizer.calculate_portfolio_metrics()
        
        self.assertIsInstance(metrics, PortfolioRiskMetrics)
        self.assertEqual(metrics.total_value, 1500.0)
        self.assertGreater(metrics.portfolio_var_95, 0)
        self.assertGreater(metrics.portfolio_var_99, metrics.portfolio_var_95)
        self.assertGreater(metrics.portfolio_volatility, 0)
        self.assertGreater(metrics.concentration_risk, 0)
        self.assertLessEqual(metrics.concentration_risk, 1.0)
    
    def test_concentration_check(self):
        """Test concentration limit checking."""
        # Add existing position
        existing = Position(
            symbol="WETH",
            chain="ethereum",
            size_usd=1000.0,
            entry_price=2000.0,
            current_price=2000.0,
            volatility=0.02
        )
        self.optimizer.update_positions({"WETH": existing})
        
        # Try to add position that would exceed 25% concentration
        new_position = Position(
            symbol="BTC",
            chain="ethereum",
            size_usd=2000.0,  # Would be 66% of portfolio
            entry_price=50000.0,
            current_price=50000.0,
            volatility=0.03
        )
        
        within_limit, concentration = self.optimizer.check_concentration_limit(
            new_position,
            max_concentration=0.25
        )
        
        self.assertFalse(within_limit)
        self.assertAlmostEqual(concentration, 2/3, places=1)  # 2000/(1000+2000) = 0.67
    
    def test_position_weights(self):
        """Test position weight calculation."""
        positions = {
            "WETH": Position(
                symbol="WETH",
                chain="ethereum",
                size_usd=1000.0,
                entry_price=2000.0,
                current_price=2000.0,
                volatility=0.02
            ),
            "USDC": Position(
                symbol="USDC",
                chain="ethereum",
                size_usd=500.0,
                entry_price=1.0,
                current_price=1.0,
                volatility=0.001
            )
        }
        self.optimizer.update_positions(positions)
        
        weights = self.optimizer.get_position_weights()
        
        self.assertEqual(len(weights), 2)
        self.assertAlmostEqual(weights["WETH"], 2/3, places=2)  # 1000/1500
        self.assertAlmostEqual(weights["USDC"], 1/3, places=2)  # 500/1500
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=2)


if __name__ == '__main__':
    unittest.main()
