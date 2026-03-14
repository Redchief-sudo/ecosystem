"""
Integration Test: RiskCapsStrategy with Trade History Tracker
==============================================================
Verify that RiskCapsStrategy uses historical win rates instead of heuristics.
"""
import unittest
from datetime import datetime, timezone
from strategies.features.risk_caps import RiskCapsStrategy, RiskMetrics
from core.trade_history_tracker import TradeHistoryTracker, TradeRecord


class TestRiskCapsTradeHistoryIntegration(unittest.TestCase):
    """Test RiskCapsStrategy integration with trade history tracker."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = TradeHistoryTracker(min_trades_for_statistics=5)
        self.strategy = RiskCapsStrategy(
            global_config={},
            strategy_config={
                "max_drawdown": 0.10,
                "min_position_size": 0.01,
                "max_position_size": 0.10,
                "kelly_fraction": 0.25,
            },
            trade_history_tracker=self.tracker
        )
    
    def test_win_probability_uses_historical_data(self):
        """Test that win probability uses historical data when available."""
        # Record 10 trades with 70% win rate
        for i in range(7):  # 7 wins
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=100.0,
                pnl_percent=5.0,
                entry_price=2000.0,
                exit_price=2100.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        for i in range(3):  # 3 losses
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=-50.0,
                pnl_percent=-2.5,
                entry_price=2000.0,
                exit_price=1950.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        # Create risk metrics
        risk_metrics = RiskMetrics(
            drawdown=0.05,
            volatility=0.02,
            sharpe_ratio=1.5,
            var_95=32.9,
            liquidity_score=0.8,
            volume_normalized=0.6
        )
        
        # Get win probability - should use historical 70% win rate
        win_prob = self.strategy._estimate_win_probability(risk_metrics, symbol="WETH")
        
        # Should be close to 0.7 (70% win rate from history)
        self.assertAlmostEqual(win_prob, 0.7, places=1)
    
    def test_win_probability_fallback_to_heuristic(self):
        """Test that win probability falls back to heuristic when insufficient data."""
        # Don't record any trades (insufficient data)
        risk_metrics = RiskMetrics(
            drawdown=0.05,
            volatility=0.02,
            sharpe_ratio=1.5,
            var_95=32.9,
            liquidity_score=0.8,
            volume_normalized=0.6
        )
        
        # Get win probability - should use heuristic
        win_prob = self.strategy._estimate_win_probability(risk_metrics, symbol="UNKNOWN")
        
        # Should be calculated from heuristic (not 0.5 default)
        self.assertGreater(win_prob, 0.0)
        self.assertLess(win_prob, 1.0)
        # Heuristic: 0.5 + 1.5*0.1 * 1/(1+0.02) * (1-0.05) ≈ 0.65
        self.assertGreater(win_prob, 0.5)
    
    def test_kelly_fraction_from_history(self):
        """Test that Kelly fraction can be retrieved from trade history."""
        # Record trades with known win/loss ratio
        for _ in range(6):  # 6 wins
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=100.0,
                pnl_percent=5.0,
                entry_price=2000.0,
                exit_price=2100.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        for _ in range(4):  # 4 losses
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=-50.0,
                pnl_percent=-2.5,
                entry_price=2000.0,
                exit_price=1950.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        # Get Kelly fraction from tracker
        kelly = self.tracker.get_kelly_fraction(strategy="risk_caps", symbol="WETH")
        
        # Should be calculated from historical data
        self.assertGreater(kelly, 0.0)
        self.assertLessEqual(kelly, 1.0)


if __name__ == '__main__':
    unittest.main()
