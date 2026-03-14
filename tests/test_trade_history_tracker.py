"""
Tests for Trade History Tracker
================================
Verify data-driven win probability and performance metrics.
"""
import unittest
from datetime import datetime, timezone
from core.trade_history_tracker import TradeHistoryTracker, TradeRecord


class TestTradeHistoryTracker(unittest.TestCase):
    """Test TradeHistoryTracker class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = TradeHistoryTracker(min_trades_for_statistics=5, max_history=1000)
    
    def test_record_trade(self):
        """Test recording a trade."""
        trade = TradeRecord(
            symbol="WETH",
            strategy="risk_caps",
            pnl=100.0,
            pnl_percent=10.0,
            entry_price=2000.0,
            exit_price=2200.0,
            entry_time=datetime.now(timezone.utc),
            exit_time=datetime.now(timezone.utc)
        )
        self.tracker.record_trade(trade)
        self.assertEqual(len(self.tracker.trades), 1)
    
    def test_win_rate_insufficient_data(self):
        """Test win rate with insufficient data."""
        win_rate = self.tracker.get_win_rate(strategy="risk_caps", symbol="WETH")
        self.assertEqual(win_rate, 0.5)  # Default value
    
    def test_win_rate_with_data(self):
        """Test win rate calculation with sufficient data."""
        # Record 10 trades: 7 wins, 3 losses
        for i in range(7):
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=100.0 + i,  # Wins
                pnl_percent=5.0,
                entry_price=2000.0,
                exit_price=2100.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        for i in range(3):
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=-50.0 - i,  # Losses
                pnl_percent=-2.5,
                entry_price=2000.0,
                exit_price=1950.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        win_rate = self.tracker.get_win_rate(strategy="risk_caps", symbol="WETH")
        self.assertEqual(win_rate, 0.7)  # 7/10 = 0.7
    
    def test_avg_win_loss(self):
        """Test average win and loss calculation."""
        # Record trades with known win/loss amounts
        for pnl in [100.0, 120.0, 80.0]:  # Wins
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=pnl,
                pnl_percent=5.0,
                entry_price=2000.0,
                exit_price=2100.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        for pnl in [-50.0, -60.0, -40.0]:  # Losses
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=pnl,
                pnl_percent=-2.5,
                entry_price=2000.0,
                exit_price=1950.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        avg_win, avg_loss = self.tracker.get_avg_win_loss(strategy="risk_caps", symbol="WETH")
        self.assertAlmostEqual(avg_win, 100.0, places=1)  # (100+120+80)/3 = 100
        self.assertAlmostEqual(avg_loss, 50.0, places=1)  # abs((-50-60-40)/3) = 50
    
    def test_win_loss_ratio(self):
        """Test win/loss ratio calculation."""
        # Record trades
        for pnl in [100.0, 100.0]:  # Wins
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=pnl,
                pnl_percent=5.0,
                entry_price=2000.0,
                exit_price=2100.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        for pnl in [-50.0, -50.0]:  # Losses
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=pnl,
                pnl_percent=-2.5,
                entry_price=2000.0,
                exit_price=1950.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        ratio = self.tracker.get_win_loss_ratio(strategy="risk_caps", symbol="WETH")
        self.assertAlmostEqual(ratio, 2.0, places=1)  # 100/50 = 2.0
    
    def test_kelly_fraction(self):
        """Test Kelly fraction calculation."""
        # Record trades: 60% win rate, 2:1 win/loss ratio
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
        
        kelly = self.tracker.get_kelly_fraction(strategy="risk_caps", symbol="WETH")
        # Kelly = (0.6 * 2.0 - 0.4) / 2.0 = 0.4, fractional = 0.4 * 0.25 = 0.1
        self.assertGreater(kelly, 0.0)
        self.assertLessEqual(kelly, 1.0)
    
    def test_filtering_by_strategy(self):
        """Test filtering trades by strategy."""
        # Record trades for different strategies
        for strategy in ["risk_caps", "momentum"]:
            for i in range(5):
                trade = TradeRecord(
                    symbol="WETH",
                    strategy=strategy,
                    pnl=100.0 if i % 2 == 0 else -50.0,
                    pnl_percent=5.0,
                    entry_price=2000.0,
                    exit_price=2100.0,
                    entry_time=datetime.now(timezone.utc),
                    exit_time=datetime.now(timezone.utc)
                )
                self.tracker.record_trade(trade)
        
        risk_caps_trades = self.tracker.get_trade_count(strategy="risk_caps")
        self.assertEqual(risk_caps_trades, 5)
        
        momentum_trades = self.tracker.get_trade_count(strategy="momentum")
        self.assertEqual(momentum_trades, 5)
    
    def test_filtering_by_symbol(self):
        """Test filtering trades by symbol."""
        # Record trades for different symbols
        for symbol in ["WETH", "USDC"]:
            for i in range(5):
                trade = TradeRecord(
                    symbol=symbol,
                    strategy="risk_caps",
                    pnl=100.0,
                    pnl_percent=5.0,
                    entry_price=2000.0,
                    exit_price=2100.0,
                    entry_time=datetime.now(timezone.utc),
                    exit_time=datetime.now(timezone.utc)
                )
                self.tracker.record_trade(trade)
        
        weth_trades = self.tracker.get_trade_count(symbol="WETH")
        self.assertEqual(weth_trades, 5)
        
        usdc_trades = self.tracker.get_trade_count(symbol="USDC")
        self.assertEqual(usdc_trades, 5)
    
    def test_get_statistics(self):
        """Test comprehensive statistics."""
        # Record enough trades
        for i in range(10):
            trade = TradeRecord(
                symbol="WETH",
                strategy="risk_caps",
                pnl=100.0 if i < 7 else -50.0,  # 7 wins, 3 losses
                pnl_percent=5.0 if i < 7 else -2.5,
                entry_price=2000.0,
                exit_price=2100.0 if i < 7 else 1950.0,
                entry_time=datetime.now(timezone.utc),
                exit_time=datetime.now(timezone.utc)
            )
            self.tracker.record_trade(trade)
        
        stats = self.tracker.get_statistics(strategy="risk_caps", symbol="WETH")
        
        self.assertEqual(stats['trade_count'], 10)
        self.assertTrue(stats['sufficient_data'])
        self.assertAlmostEqual(stats['win_rate'], 0.7, places=1)
        self.assertGreater(stats['avg_win'], 0)
        self.assertGreater(stats['avg_loss'], 0)
        self.assertGreater(stats['win_loss_ratio'], 0)
        self.assertGreaterEqual(stats['kelly_fraction'], 0)
        self.assertLessEqual(stats['kelly_fraction'], 1.0)
    
    def test_clear_history(self):
        """Test clearing trade history."""
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
        self.assertEqual(len(self.tracker.trades), 1)
        
        self.tracker.clear_history()
        self.assertEqual(len(self.tracker.trades), 0)
        self.assertEqual(self.tracker.get_trade_count(), 0)


if __name__ == '__main__':
    unittest.main()
