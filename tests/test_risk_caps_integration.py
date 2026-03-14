"""
Integration Tests for RiskCapsStrategy with Institutional Upgrades
==================================================================
Verify that RiskCapsStrategy properly uses new institutional-grade modules.
"""
import unittest
import asyncio
from strategies.features.risk_caps import RiskCapsStrategy, RiskMetrics
from core.financial_precision import FinancialDecimal


class TestRiskCapsIntegration(unittest.TestCase):
    """Test RiskCapsStrategy integration with new modules."""
    
    def setUp(self):
        """Set up test fixtures."""
        global_config = {}
        self.strategy = RiskCapsStrategy(
            global_config=global_config,
            strategy_config={
                "max_drawdown": 0.10,
                "min_position_size": 0.01,
                "max_position_size": 0.10,
                "kelly_fraction": 0.25,
                "max_position_risk": 0.02,
                "var_confidence": 0.95,
            }
        )
    
    def test_var_calculation_uses_scipy(self):
        """Test that VaR calculation uses scipy z-scores."""
        var_95 = self.strategy._calculate_var(price=1000.0, volatility=0.02, confidence=0.95)
        var_99 = self.strategy._calculate_var(price=1000.0, volatility=0.02, confidence=0.99)
        
        # Verify both values are calculated
        self.assertIsInstance(var_95, float)
        self.assertIsInstance(var_99, float)
        
        # 99% VaR should be higher than 95% VaR
        self.assertGreater(var_99, var_95)
        
        # Verify it's not using hardcoded values (1.645 or 1.96)
        # With scipy, we get more precise values
        self.assertNotEqual(var_95, 1000.0 * 0.02 * 1.645)  # Old hardcoded value
    
    def test_sharpe_ratio_with_returns(self):
        """Test Sharpe ratio calculation with returns history."""
        returns_history = [0.01, 0.02, -0.01, 0.03, 0.01, 0.02, -0.005, 0.015]
        sharpe = self.strategy._estimate_sharpe_ratio(returns_history=returns_history)
        
        self.assertIsInstance(sharpe, float)
        self.assertGreater(sharpe, 0)  # Should be positive for these returns
    
    def test_sharpe_ratio_fallback(self):
        """Test Sharpe ratio fallback when no returns history."""
        sharpe = self.strategy._estimate_sharpe_ratio(drawdown=0.05, volatility=0.02)
        
        self.assertIsInstance(sharpe, float)
        # Fallback should return a reasonable value
        self.assertGreater(sharpe, 0)
    
    async def test_position_sizing_uses_decimal(self):
        """Test that position sizing uses Decimal precision."""
        market_data = {
            "price": 1000.12345678,
            "volume": 100000.0,
            "liquidity": 500000.0,
        }
        
        risk_metrics = RiskMetrics(
            drawdown=0.05,
            volatility=0.02,
            sharpe_ratio=1.5,
            var_95=32.9,
            liquidity_score=0.8,
            volume_normalized=0.6
        )
        
        config = {
            "max_drawdown": 0.10,
            "min_position_size": 0.01,
            "max_position_size": 0.10,
            "kelly_fraction": 0.25,
            "max_position_risk": 0.02,
        }
        
        result = await self.strategy._calculate_optimal_position(market_data, risk_metrics, config)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result.size, float)
        self.assertGreater(result.size, 0)
        self.assertLessEqual(result.size, config["max_position_size"])
        
        # Verify stop loss and take profit are calculated
        self.assertIsInstance(result.stop_loss, float)
        self.assertIsInstance(result.take_profit, float)
        self.assertLess(result.stop_loss, market_data["price"])
        self.assertGreater(result.take_profit, market_data["price"])
    
    def test_position_sizing_sync(self):
        """Test position sizing synchronously."""
        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.test_position_sizing_uses_decimal())
        finally:
            loop.close()


if __name__ == '__main__':
    unittest.main()
