"""
Trade History Tracker - INSTITUTIONAL GRADE
===========================================
Tracks trade history for data-driven probability estimation.
Replaces heuristic win probability with actual historical performance.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    symbol: str
    strategy: str
    pnl: float
    pnl_percent: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    position_size: float = 0.0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class TradeHistoryTracker:
    """
    Track trade history and calculate performance metrics.
    
    Provides data-driven win probability, average win/loss, and Kelly fraction
    based on actual trade performance instead of heuristics.
    """
    
    def __init__(self, min_trades_for_statistics: int = 10, max_history: int = 10000):
        """
        Initialize trade history tracker.
        
        Args:
            min_trades_for_statistics: Minimum trades needed for reliable statistics
            max_history: Maximum number of trades to keep in memory
        """
        self.min_trades = min_trades_for_statistics
        self.max_history = max_history
        self.trades: List[TradeRecord] = []
        self.trades_by_strategy: Dict[str, List[TradeRecord]] = defaultdict(list)
        self.trades_by_symbol: Dict[str, List[TradeRecord]] = defaultdict(list)
        self.trades_by_strategy_symbol: Dict[Tuple[str, str], List[TradeRecord]] = defaultdict(list)
        
        logger.info(f"TradeHistoryTracker initialized (min_trades={min_trades_for_statistics}, max_history={max_history})")
    
    def record_trade(self, trade: TradeRecord):
        """
        Record a completed trade.
        
        Args:
            trade: TradeRecord to add to history
        """
        self.trades.append(trade)
        self.trades_by_strategy[trade.strategy].append(trade)
        self.trades_by_symbol[trade.symbol].append(trade)
        self.trades_by_strategy_symbol[(trade.strategy, trade.symbol)].append(trade)
        
        # Keep only last N trades to prevent memory issues
        if len(self.trades) > self.max_history:
            oldest = self.trades.pop(0)
            self.trades_by_strategy[oldest.strategy].remove(oldest)
            self.trades_by_symbol[oldest.symbol].remove(oldest)
            self.trades_by_strategy_symbol[(oldest.strategy, oldest.symbol)].remove(oldest)
        
        logger.debug(f"Recorded trade: {trade.symbol} via {trade.strategy}, PnL: ${trade.pnl:.2f} ({trade.pnl_percent:.2%})")
    
    def get_win_rate(
        self, 
        strategy: Optional[str] = None, 
        symbol: Optional[str] = None
    ) -> float:
        """
        Calculate win rate from historical trades.
        
        Args:
            strategy: Optional strategy filter
            symbol: Optional symbol filter
        
        Returns:
            Win rate (0.0-1.0), or 0.5 if insufficient data
        """
        trades = self._filter_trades(strategy, symbol)
        
        if len(trades) < self.min_trades:
            return 0.5  # Default if insufficient data
        
        wins = sum(1 for t in trades if t.pnl > 0)
        win_rate = wins / len(trades)
        
        logger.debug(
            f"Win rate for strategy={strategy}, symbol={symbol}: "
            f"{win_rate:.2%} ({wins}/{len(trades)} trades)"
        )
        
        return win_rate
    
    def get_avg_win_loss(
        self, 
        strategy: Optional[str] = None, 
        symbol: Optional[str] = None
    ) -> Tuple[float, float]:
        """
        Calculate average win and average loss.
        
        Args:
            strategy: Optional strategy filter
            symbol: Optional symbol filter
        
        Returns:
            Tuple of (avg_win, avg_loss) in absolute terms
        """
        trades = self._filter_trades(strategy, symbol)
        
        if len(trades) < self.min_trades:
            return 0.08, 0.04  # Default values
        
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl <= 0]
        
        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = abs(float(np.mean(losses))) if losses else 0.0
        
        return avg_win, avg_loss
    
    def get_win_loss_ratio(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> float:
        """
        Calculate win/loss ratio (average win / average loss).
        
        Args:
            strategy: Optional strategy filter
            symbol: Optional symbol filter
        
        Returns:
            Win/loss ratio, or 2.0 if insufficient data
        """
        avg_win, avg_loss = self.get_avg_win_loss(strategy, symbol)
        
        if avg_loss == 0:
            return 2.0  # Default
        
        return avg_win / avg_loss
    
    def get_kelly_fraction(
        self, 
        strategy: Optional[str] = None, 
        symbol: Optional[str] = None
    ) -> float:
        """
        Calculate optimal Kelly fraction from historical performance.
        
        Kelly = (Win Rate * Win/Loss Ratio - (1 - Win Rate)) / Win/Loss Ratio
        
        Args:
            strategy: Optional strategy filter
            symbol: Optional symbol filter
        
        Returns:
            Kelly fraction (0.0-1.0), fractional Kelly (25% of full Kelly)
        """
        win_rate = self.get_win_rate(strategy, symbol)
        avg_win, avg_loss = self.get_avg_win_loss(strategy, symbol)
        
        if avg_loss == 0:
            return 0.0
        
        win_loss_ratio = avg_win / avg_loss
        
        # Full Kelly formula
        kelly_full = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # Fractional Kelly (25% of full Kelly for safety)
        kelly_fraction = max(0.0, min(1.0, kelly_full * 0.25))
        
        logger.debug(
            f"Kelly fraction for strategy={strategy}, symbol={symbol}: "
            f"{kelly_fraction:.4f} (full={kelly_full:.4f}, win_rate={win_rate:.2%}, w/l={win_loss_ratio:.2f})"
        )
        
        return kelly_fraction
    
    def get_sharpe_ratio(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> float:
        """
        Calculate Sharpe ratio from trade returns.
        
        Args:
            strategy: Optional strategy filter
            symbol: Optional symbol filter
        
        Returns:
            Sharpe ratio, or 0.0 if insufficient data
        """
        trades = self._filter_trades(strategy, symbol)
        
        if len(trades) < self.min_trades:
            return 0.0
        
        # Convert PnL percentages to returns
        returns = [t.pnl_percent / 100.0 for t in trades]
        
        from core.risk_metrics import RiskMetricsCalculator
        return RiskMetricsCalculator.calculate_sharpe_ratio(
            np.array(returns),
            risk_free_rate=0.02,
            periods_per_year=365
        )
    
    def get_trade_count(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> int:
        """Get number of trades matching filters."""
        return len(self._filter_trades(strategy, symbol))
    
    def get_total_pnl(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> float:
        """Get total PnL for filtered trades."""
        trades = self._filter_trades(strategy, symbol)
        return sum(t.pnl for t in trades)
    
    def get_statistics(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Get comprehensive statistics for filtered trades.
        
        Returns:
            Dictionary with win_rate, avg_win, avg_loss, kelly_fraction, sharpe, etc.
        """
        trades = self._filter_trades(strategy, symbol)
        
        if len(trades) < self.min_trades:
            return {
                'trade_count': len(trades),
                'sufficient_data': False,
                'win_rate': 0.5,
                'avg_win': 0.08,
                'avg_loss': 0.04,
                'win_loss_ratio': 2.0,
                'kelly_fraction': 0.0,
                'sharpe_ratio': 0.0,
                'total_pnl': sum(t.pnl for t in trades),
            }
        
        win_rate = self.get_win_rate(strategy, symbol)
        avg_win, avg_loss = self.get_avg_win_loss(strategy, symbol)
        win_loss_ratio = self.get_win_loss_ratio(strategy, symbol)
        kelly_fraction = self.get_kelly_fraction(strategy, symbol)
        sharpe = self.get_sharpe_ratio(strategy, symbol)
        total_pnl = self.get_total_pnl(strategy, symbol)
        
        return {
            'trade_count': len(trades),
            'sufficient_data': True,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'win_loss_ratio': win_loss_ratio,
            'kelly_fraction': kelly_fraction,
            'sharpe_ratio': sharpe,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(trades) if trades else 0.0,
        }
    
    def _filter_trades(
        self, 
        strategy: Optional[str], 
        symbol: Optional[str]
    ) -> List[TradeRecord]:
        """Filter trades by strategy and/or symbol."""
        if strategy and symbol:
            return self.trades_by_strategy_symbol.get((strategy, symbol), [])
        elif strategy:
            return self.trades_by_strategy.get(strategy, [])
        elif symbol:
            return self.trades_by_symbol.get(symbol, [])
        else:
            return self.trades
    
    def clear_history(self):
        """Clear all trade history (for testing/reset)."""
        self.trades.clear()
        self.trades_by_strategy.clear()
        self.trades_by_symbol.clear()
        self.trades_by_strategy_symbol.clear()
        logger.info("Trade history cleared")
    
    def export_history(self) -> List[Dict]:
        """Export trade history as list of dictionaries."""
        return [
            {
                'symbol': t.symbol,
                'strategy': t.strategy,
                'pnl': t.pnl,
                'pnl_percent': t.pnl_percent,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'entry_time': t.entry_time.isoformat(),
                'exit_time': t.exit_time.isoformat(),
                'position_size': t.position_size,
                'metadata': t.metadata or {},
            }
            for t in self.trades
        ]
