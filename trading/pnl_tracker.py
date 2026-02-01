"""
PnL Tracker
===========
Tracks all trades and maintains historical performance metrics.

Features:
- CSV logging for trade history
- In-memory performance metrics per strategy/token/chain
- Profitability scoring for AI controller
- Dynamic position sizing based on historical performance
- Circuit breaker triggering on poor performance
"""

import csv
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from collections import defaultdict
import statistics

from trading.pnl_models import TradePnL, StrategyPerformance

logger = logging.getLogger(__name__)


class PnLTracker:
    """
    Central PnL tracking system for the trading bot.
    
    Maintains:
    - CSV log of all trades (historical record)
    - In-memory performance metrics per strategy
    - Dynamic position sizing recommendations
    - Circuit breaker status
    """
    
    def __init__(self, data_dir: Path = None):
        """
        Initialize PnL tracker.
        
        Args:
            data_dir: Directory to store CSV logs (default: data/)
        """
        self.data_dir = data_dir or Path("/home/damien/ecosystem/data")
        self.pnl_file = self.data_dir / "pnl_history.csv"
        self.strategy_perf_file = self.data_dir / "strategy_performance.csv"
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize CSV headers if files don't exist
        self._init_csv_files()
        
        # In-memory performance cache
        # Key: (strategy, token, chain) or (strategy, None, None) for aggregates
        self.performance_cache: Dict[Tuple, StrategyPerformance] = {}
        
        # Circuit breaker state
        # Key: (strategy, token, chain)
        self.circuit_breakers: Dict[Tuple, bool] = defaultdict(bool)
        
        # Track unrealized PnL
        # Key: trade_id
        self.open_trades: Dict[str, TradePnL] = {}
        
        # Load historical data
        self._load_from_csv()
        
        logger.info("PnLTracker initialized")

    def _init_csv_files(self):
        """Initialize CSV files with headers if they don't exist."""
        if not self.pnl_file.exists():
            with open(self.pnl_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'token', 'chain', 'strategy',
                    'entry_price', 'exit_price', 'size', 'fees',
                    'pnl', 'pnl_percent', 'roi', 'realized'
                ])
            logger.info(f"Created PnL history file: {self.pnl_file}")

    def _load_from_csv(self):
        """Load historical trades from CSV to rebuild performance metrics."""
        if not self.pnl_file.exists():
            return
        
        trades = []
        try:
            with open(self.pnl_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trade = TradePnL(
                        token=row['token'],
                        chain=row['chain'],
                        strategy=row['strategy'],
                        entry_price=float(row['entry_price']),
                        exit_price=float(row['exit_price']) if row['exit_price'] else None,
                        size=float(row['size']),
                        fees=float(row['fees']),
                        entry_time=row['timestamp'],
                        realized=row['realized'].lower() == 'true'
                    )
                    trades.append(trade)
            
            logger.info(f"Loaded {len(trades)} historical trades")
            
            # Rebuild performance metrics
            for trade in trades:
                if trade.realized:
                    self._update_performance(trade)
        
        except Exception as e:
            logger.error(f"Failed to load PnL history: {e}")

    def log_trade(self, trade: TradePnL) -> None:
        """
        Log a trade to CSV.
        
        Args:
            trade: TradePnL object to log
        """
        try:
            with open(self.pnl_file, 'a', newline='') as f:
                writer = csv.writer(f)
                data = trade.to_dict()
                writer.writerow([
                    data['timestamp'],
                    data['token'],
                    data['chain'],
                    data['strategy'],
                    data['entry_price'],
                    data['exit_price'],
                    data['size'],
                    data['fees'],
                    f"{data['pnl']:.6f}",
                    f"{data['pnl_percent']:.6f}",
                    f"{data['roi']:.2f}",
                    data['realized']
                ])
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    def enter_trade(self, trade_id: str, trade: TradePnL) -> None:
        """
        Record a new opened trade (unrealized).
        
        Args:
            trade_id: Unique trade identifier
            trade: TradePnL object (entry_price set, exit_price = None)
        """
        self.open_trades[trade_id] = trade
        logger.debug(f"Entered trade {trade_id}: {trade.token} @ {trade.entry_price}")

    def close_trade(self, trade_id: str, exit_price: float) -> Optional[TradePnL]:
        """
        Close an open trade and mark as realized.
        
        Args:
            trade_id: Unique trade identifier
            exit_price: Price at exit
            
        Returns:
            Closed TradePnL object or None if trade_id not found
        """
        if trade_id not in self.open_trades:
            logger.warning(f"Trade {trade_id} not found in open trades")
            return None
        
        trade = self.open_trades.pop(trade_id)
        trade.exit_price = exit_price
        trade.exit_time = datetime.now(timezone.utc).isoformat()
        trade.realized = True
        
        # Log to CSV
        self.log_trade(trade)
        
        # Update performance metrics
        self._update_performance(trade)
        
        logger.info(
            f"Closed trade {trade_id}: {trade.token} | "
            f"PnL: ${trade.pnl():.6f} ({trade.roi():.2f}%)"
        )
        
        return trade

    def _update_performance(self, trade: TradePnL) -> None:
        """
        Update performance metrics after a trade closes.
        
        Args:
            trade: Closed TradePnL object
        """
        # Update strategy-specific (token, chain)
        self._update_perf_key((trade.strategy, trade.token, trade.chain), trade)
        
        # Update strategy aggregate (all tokens, all chains)
        self._update_perf_key((trade.strategy, None, None), trade)

    def _update_perf_key(self, key: Tuple, trade: TradePnL) -> None:
        """Update performance metrics for a specific key."""
        if key not in self.performance_cache:
            strategy, token, chain = key
            self.performance_cache[key] = StrategyPerformance(
                strategy=strategy,
                token=token,
                chain=chain
            )
        
        perf = self.performance_cache[key]
        pnl_value = trade.pnl()
        roi_value = trade.roi()
        
        perf.total_trades += 1
        if pnl_value > 0:
            perf.winning_trades += 1
        elif pnl_value < 0:
            perf.losing_trades += 1
        
        perf.total_pnl += pnl_value
        perf.avg_pnl = perf.total_pnl / perf.total_trades
        perf.max_pnl = max(perf.max_pnl, pnl_value)
        perf.min_pnl = min(perf.min_pnl, pnl_value)
        
        perf.avg_roi = (perf.avg_roi * (perf.total_trades - 1) + roi_value) / perf.total_trades
        perf.max_roi = max(perf.max_roi, roi_value)
        perf.min_roi = min(perf.min_roi, roi_value)
        
        perf.win_rate = perf.winning_trades / perf.total_trades if perf.total_trades > 0 else 0.0
        perf.loss_rate = perf.losing_trades / perf.total_trades if perf.total_trades > 0 else 0.0
        
        perf.last_updated = datetime.now(timezone.utc).isoformat()

    def get_strategy_performance(
        self,
        strategy: str,
        token: Optional[str] = None,
        chain: Optional[str] = None
    ) -> Optional[StrategyPerformance]:
        """
        Get performance metrics for a strategy.
        
        Args:
            strategy: Strategy name
            token: Specific token (None = all tokens)
            chain: Specific chain (None = all chains)
            
        Returns:
            StrategyPerformance or None if no history
        """
        key = (strategy, token, chain)
        return self.performance_cache.get(key)

    def get_position_size(
        self,
        token: str,
        chain: str,
        strategy: str,
        base_size: float = 10.0  # $10 base
    ) -> float:
        """
        Determine dynamic position size based on strategy performance.
        
        Args:
            token: Token symbol
            chain: Blockchain name
            strategy: Strategy name
            base_size: Base position size in USD
            
        Returns:
            Adjusted position size
        """
        perf = self.get_strategy_performance(strategy, token, chain)
        
        if perf is None or perf.total_trades < 5:
            # Not enough history, use base size
            return base_size
        
        # Scale based on win rate and avg ROI
        # Losing strategies get scaled down, winning get scaled up
        win_factor = (perf.win_rate - 0.5) * 2  # -1.0 to 1.0
        roi_factor = min(0.5, perf.avg_roi / 10.0)  # Cap at 50% boost
        
        factor = 1.0 + win_factor * 0.3 + roi_factor * 0.2
        factor = max(0.5, min(1.5, factor))  # Bound between 0.5x and 1.5x
        
        adjusted_size = base_size * factor
        
        logger.debug(
            f"Position size for {strategy} on {token}/{chain}: "
            f"${base_size:.2f} * {factor:.2f} = ${adjusted_size:.2f}"
        )
        
        return adjusted_size

    def should_use_strategy(
        self,
        strategy: str,
        token: str,
        chain: str,
        min_win_rate: float = 0.4,
        min_trades: int = 3
    ) -> bool:
        """
        Determine if a strategy should be used for a token/chain.
        
        Circuit breaker logic: disable strategies with poor track record.
        
        Args:
            strategy: Strategy name
            token: Token symbol
            chain: Blockchain name
            min_win_rate: Minimum acceptable win rate
            min_trades: Minimum trades before disabling
            
        Returns:
            True if strategy should be used, False otherwise
        """
        key = (strategy, token, chain)
        
        # Check if circuit breaker is open
        if self.circuit_breakers.get(key, False):
            return False
        
        perf = self.get_strategy_performance(strategy, token, chain)
        
        if perf is None:
            # No history, allow (bootstrap phase)
            return True
        
        # Disable if losing consistently
        if perf.total_trades >= min_trades and perf.win_rate < min_win_rate:
            logger.warning(
                f"Circuit breaker OPEN for {strategy} on {token}/{chain}: "
                f"win_rate {perf.win_rate:.1%} < {min_win_rate:.1%}"
            )
            self.circuit_breakers[key] = True
            return False
        
        return True

    def reset_circuit_breaker(self, strategy: str, token: str, chain: str) -> None:
        """Reset circuit breaker for a strategy/token/chain combination."""
        key = (strategy, token, chain)
        if self.circuit_breakers[key]:
            self.circuit_breakers[key] = False
            logger.info(f"Circuit breaker RESET for {strategy} on {token}/{chain}")

    def get_all_performance_stats(self) -> Dict[str, StrategyPerformance]:
        """Get all cached performance metrics."""
        return self.performance_cache.copy()

    def print_performance_summary(self) -> None:
        """Print human-readable performance summary."""
        logger.info("=" * 80)
        logger.info("PnL PERFORMANCE SUMMARY")
        logger.info("=" * 80)
        
        # Aggregate across all strategies
        total_trades = 0
        total_pnl = 0.0
        total_winning = 0
        
        for key, perf in self.performance_cache.items():
            if perf.total_trades > 0:
                total_trades += perf.total_trades
                total_pnl += perf.total_pnl
                total_winning += perf.winning_trades
                
                strategy, token, chain = key
                token_str = f" on {token}/{chain}" if token and chain else " (aggregate)"
                
                logger.info(
                    f"{strategy}{token_str}: "
                    f"{perf.winning_trades}/{perf.total_trades} wins | "
                    f"${perf.total_pnl:+.2f} | "
                    f"ROI {perf.avg_roi:+.2f}%"
                )
        
        if total_trades > 0:
            logger.info("-" * 80)
            logger.info(
                f"TOTALS: {total_winning}/{total_trades} wins | "
                f"${total_pnl:+.2f} | "
                f"Win rate {total_winning/total_trades:.1%}"
            )
        logger.info("=" * 80)
