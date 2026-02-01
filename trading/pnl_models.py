"""
PnL Data Models
===============
Dataclasses and structures for tracking Profit & Loss across trades.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from decimal import Decimal


@dataclass
class TradePnL:
    """
    Track PnL for a single trade (realized or unrealized).
    
    Attributes:
        token: Token symbol (e.g., 'WETH')
        chain: Blockchain name (e.g., 'ethereum')
        strategy: Strategy that generated the signal
        entry_price: Price at trade entry
        exit_price: Price at trade exit (None if unrealized)
        size: Position size in base currency (USD or equivalent)
        fees: Transaction fees in base currency
        entry_time: When the trade was entered
        exit_time: When the trade was closed (None if unrealized)
        realized: Whether PnL is realized (closed) or unrealized (open)
        metadata: Additional trade info (order_id, slippage, etc.)
    """
    token: str
    chain: str
    strategy: str
    entry_price: float
    size: float
    fees: float = 0.0
    exit_price: Optional[float] = None
    entry_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    exit_time: Optional[str] = None
    realized: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def pnl(self) -> float:
        """Calculate realized PnL in base currency."""
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.size - self.fees

    def pnl_percent(self) -> float:
        """Calculate PnL as percentage of entry cost."""
        if self.entry_price == 0:
            return 0.0
        entry_cost = self.entry_price * self.size
        if entry_cost == 0:
            return 0.0
        return self.pnl() / entry_cost

    def roi(self) -> float:
        """Return on investment percentage."""
        return self.pnl_percent() * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV/logging."""
        return {
            'timestamp': self.entry_time,
            'token': self.token,
            'chain': self.chain,
            'strategy': self.strategy,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'size': self.size,
            'fees': self.fees,
            'pnl': self.pnl(),
            'pnl_percent': self.pnl_percent(),
            'roi': self.roi(),
            'realized': self.realized,
        }


@dataclass
class StrategyPerformance:
    """
    Aggregated performance metrics for a strategy on a specific token/chain.
    
    Used by AI controller to weight strategy recommendations based on
    historical profitability and risk.
    """
    strategy: str
    token: Optional[str] = None  # None = aggregate across all tokens
    chain: Optional[str] = None  # None = aggregate across all chains
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    max_pnl: float = 0.0
    min_pnl: float = 0.0
    
    avg_roi: float = 0.0  # percentage
    max_roi: float = 0.0
    min_roi: float = 0.0
    
    win_rate: float = 0.0  # 0.0 to 1.0
    loss_rate: float = 0.0
    
    max_consecutive_losses: int = 0
    max_drawdown: float = 0.0
    
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def profitability_score(self) -> float:
        """
        Calculate composite score for AI weighting.
        
        Combines:
        - Win rate (higher is better)
        - ROI (higher is better)
        - Drawdown (lower is better)
        
        Returns value 0.0 to 1.0.
        """
        if self.total_trades == 0:
            return 0.5  # No data = neutral
        
        # Win rate component: 0.0 to 1.0
        win_rate_score = self.win_rate
        
        # ROI component: normalize to 0.0 to 1.0 (10% ROI = 1.0)
        roi_score = min(1.0, max(0.0, self.avg_roi / 10.0))
        
        # Drawdown component: penalize large drawdowns
        drawdown_score = max(0.0, 1.0 - abs(self.max_drawdown) * 10)
        
        # Weighted composite: 50% win_rate, 35% ROI, 15% drawdown protection
        composite = (
            win_rate_score * 0.50 +
            roi_score * 0.35 +
            drawdown_score * 0.15
        )
        
        return min(1.0, max(0.0, composite))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/display."""
        return {
            'strategy': self.strategy,
            'token': self.token,
            'chain': self.chain,
            'total_trades': self.total_trades,
            'win_rate': f"{self.win_rate * 100:.1f}%",
            'avg_pnl': f"${self.avg_pnl:.4f}",
            'avg_roi': f"{self.avg_roi:.2f}%",
            'max_drawdown': f"{self.max_drawdown * 100:.2f}%",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'profitability_score': f"{self.profitability_score():.3f}",
        }
