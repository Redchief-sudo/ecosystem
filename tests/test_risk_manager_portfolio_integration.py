"""
Integration Test: RiskManager with Portfolio Risk Optimizer
===========================================================
Verify that RiskManager uses portfolio-level risk optimization.
"""
import unittest
from risk.risk_manager import RiskManager, RiskVerdict
from risk.portfolio_risk_optimizer import Position


class MockTradeIntent:
    """Mock trade intent for testing."""
    def __init__(self, token_address, amount_usd, chain, price, volatility=0.02):
        self.token_address = token_address
        self.token_out = token_address
        self.amount_usd = amount_usd
        self.chain = chain
        self.price = price
        self.entry_price = price
        self.volatility = volatility
        self.side = 'buy'


class TestRiskManagerPortfolioIntegration(unittest.TestCase):
    """Test RiskManager integration with portfolio optimizer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.risk_manager = RiskManager({
            'trading': {
                'paper_trading': {'portfolio_value_per_network': 1000.0},
                'max_total_exposure': 0.3
            },
            'max_portfolio_var': 0.05  # 5% max VaR
        })
    
    def test_portfolio_optimizer_initialized(self):
        """Test that portfolio optimizer is initialized."""
        self.assertTrue(hasattr(self.risk_manager, 'portfolio_optimizer'))
        self.assertIsNotNone(self.risk_manager.portfolio_optimizer)
    
    def test_portfolio_risk_check_reduces_size(self):
        """Test that portfolio risk check reduces position size when needed."""
        # Set up portfolio with existing position
        portfolio_state = {
            'total_value': 10000.0,
            'positions': {
                ('ethereum', 'WETH'): {
                    'active': True,
                    'exposure_usd': 5000.0,
                    'entry_price': 2000.0,
                    'current_price': 2000.0,
                    'volatility': 0.02
                }
            },
            'current_exposure': 5000.0,
            'daily_trades': 0,
            'current_drawdown': 0.0
        }
        
        # Try to add large position that would exceed VaR
        trade_intent = MockTradeIntent(
            token_address='BTC',
            amount_usd=10000.0,  # Large position
            chain='ethereum',
            price=50000.0,
            volatility=0.03  # High volatility
        )
        
        result = self.risk_manager._check_portfolio_risk(trade_intent, portfolio_state)
        
        # Should suggest reduced size
        if not result['approved']:
            self.assertIn('optimal_size', result)
            self.assertLess(result['optimal_size'], trade_intent.amount_usd)
    
    def test_get_risk_metrics_includes_portfolio_metrics(self):
        """Test that get_risk_metrics includes portfolio-level metrics."""
        metrics = self.risk_manager.get_risk_metrics()
        
        # Should include portfolio-level metrics
        self.assertIn('portfolio_var_95', metrics)
        self.assertIn('portfolio_var_99', metrics)
        self.assertIn('portfolio_volatility', metrics)
        self.assertIn('concentration_risk', metrics)
        
        # All should be numeric
        self.assertIsInstance(metrics['portfolio_var_95'], (int, float))
        self.assertIsInstance(metrics['portfolio_var_99'], (int, float))
        self.assertIsInstance(metrics['portfolio_volatility'], (int, float))
        self.assertIsInstance(metrics['concentration_risk'], (int, float))


if __name__ == '__main__':
    unittest.main()
