# trade_strategies/performance_tracker.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base_strategy import SignalType, TradeSignal

logger = logging.getLogger(__name__)

class StrategyPerformanceTracker:
    """Tracks performance metrics for trading strategies."""
    
    def __init__(self, lookback_period: int = 30):
        """
        Initialize the performance tracker.
        
        Args:
            lookback_period: Number of days to consider for performance metrics
        """
        self.lookback_period = timedelta(days=lookback_period)
        self.trades: List[Dict[str, Any]] = []  # List of all trades
        self.strategy_metrics: Dict[str, Dict[str, Any]] = {}  # Performance metrics by strategy
        
    def add_trade(self, strategy_name: str, signal: TradeSignal, 
                 entry_price: float, exit_price: Optional[float] = None, 
                 entry_time: Optional[datetime] = None, 
                 exit_time: Optional[datetime] = None) -> str:
        """
        Add a new trade to the tracker.
        
        Args:
            strategy_name: Name of the strategy
            signal: TradeSignal object
            entry_price: Entry price
            exit_price: Exit price (if trade is closed)
            entry_time: Timestamp of entry
            exit_time: Timestamp of exit (if trade is closed)
            
        Returns:
            Trade ID
        """
        if entry_time is None:
            entry_time = datetime.now(timezone.utc)
            
        trade = {
            'id': f"{strategy_name}_{len(self.trades)}",
            'strategy': strategy_name,
            'signal': signal.signal_type,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'size': signal.size,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'metadata': signal.metadata or {}
        }
        
        # Calculate PnL if trade is closed
        if exit_price is not None and exit_time is not None:
            trade['pnl'] = self._calculate_pnl(signal, entry_price, exit_price)
            trade['duration'] = (exit_time - entry_time).total_seconds() / 3600  # in hours
            
        self.trades.append(trade)
        self._update_strategy_metrics(strategy_name)
        
        return trade['id']
    
    def update_trade(self, trade_id: str, exit_price: float, exit_time: Optional[datetime] = None) -> bool:
        """
        Update a trade with exit information.
        
        Args:
            trade_id: ID of the trade to update
            exit_price: Exit price
            exit_time: Timestamp of exit (defaults to now)
            
        Returns:
            True if update was successful, False otherwise
        """
        if exit_time is None:
            exit_time = datetime.now(timezone.utc)
            
        for trade in self.trades:
            if trade['id'] == trade_id and 'exit_price' not in trade:
                trade['exit_price'] = exit_price
                trade['exit_time'] = exit_time
                trade['pnl'] = self._calculate_pnl(
                    TradeSignal(
                        signal_type=trade['signal'],
                        confidence=0,  # Not used for PnL calculation
                        price=trade['entry_price'],
                        size=trade['size'],
                        stop_loss=trade.get('stop_loss'),
                        take_profit=trade.get('take_profit'),
                        metadata=trade.get('metadata', {})
                    ),
                    trade['entry_price'],
                    exit_price
                )
                trade['duration'] = (exit_time - trade['entry_time']).total_seconds() / 3600
                
                self._update_strategy_metrics(trade['strategy'])
                return True
                
        return False
    
    def _calculate_pnl(self, signal: TradeSignal, entry_price: float, exit_price: float) -> float:
        """Calculate profit/loss for a trade."""
        if signal.signal_type == SignalType.BUY:
            return (exit_price - entry_price) / entry_price * signal.size
        elif signal.signal_type == SignalType.SELL:
            return (entry_price - exit_price) / entry_price * signal.size
        return 0.0
    
    def _update_strategy_metrics(self, strategy_name: str) -> None:
        """Update performance metrics for a strategy."""
        strategy_trades = [t for t in self.trades 
                         if t['strategy'] == strategy_name 
                         and 'pnl' in t]
        
        if not strategy_trades:
            return
            
        # Calculate basic metrics
        pnls = [t['pnl'] for t in strategy_trades]
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        total_trades = len(strategy_trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        avg_win = float(np.mean(winning_trades)) if winning_trades else 0.0
        avg_loss = abs(float(np.mean(losing_trades))) if losing_trades else 0.0
        profit_factor = (len(winning_trades) * avg_win) / (len(losing_trades) * avg_loss) if losing_trades else float('inf')
        
        # Calculate Sharpe ratio (annualized)
        returns = np.array(pnls, dtype=float)
        sharpe_ratio = float(np.sqrt(365) * np.mean(returns) / np.std(returns)) if len(returns) > 1 and np.std(returns) > 0 else 0.0
        
        # Calculate max drawdown
        cum_returns = np.cumsum(returns)
        max_drawdown = 0.0
        if len(cum_returns) > 0:
            peak = cum_returns[0]
            for r in cum_returns[1:]:
                if r > peak:
                    peak = r
                drawdown = (peak - r) / (1 + peak)  # Normalized drawdown
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        # Update metrics
        self.strategy_metrics[strategy_name] = {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': float(profit_factor),
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_return': float(np.sum(returns)),
            'avg_hold_time': float(np.mean([t.get('duration', 0) for t in strategy_trades] or [0])),
            'last_updated': datetime.now(timezone.utc),
            'recent_trades': strategy_trades[-10:]  # Keep last 10 trades for reference
        }
    
    def get_strategy_metrics(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get performance metrics for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dictionary with performance metrics
        """
        return self.strategy_metrics.get(strategy_name, {
            'total_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'total_return': 0.0,
            'avg_hold_time': 0.0,
            'last_updated': datetime.min,
            'recent_trades': []
        })
