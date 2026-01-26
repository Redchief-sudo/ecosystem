"""
Position management for active trading positions.

This module defines the ActivePosition class used to track
open trading positions in the system.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional


@dataclass
class ActivePosition:
    """
    Represents an active trading position.

    Tracks position details, entry information, and provides
    methods for calculating P&L and position management.
    """
    position_id: str
    symbol: str
    amount: Decimal
    entry_price: Decimal
    strategy_id: str
    opportunity_id: str
    token_address: str
    chain: int
    decimals: int
    entry_time: Optional[datetime] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.entry_time is None:
            self.entry_time = datetime.now(timezone.utc)

        # Ensure decimal types
        self.amount = Decimal(str(self.amount))
        self.entry_price = Decimal(str(self.entry_price))

    def get_pnl_percentage(self, current_price: Decimal) -> float:
        """
        Calculate the percentage P&L for this position.

        Args:
            current_price: Current market price

        Returns:
            Percentage P&L (e.g., 0.05 for 5% gain)
        """
        current_price = Decimal(str(current_price))
        if self.entry_price == 0:
            return 0.0

        return float((current_price - self.entry_price) / self.entry_price)

    def get_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """
        Calculate the unrealized P&L in USD value.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L in USD
        """
        current_price = Decimal(str(current_price))
        price_change = current_price - self.entry_price
        return price_change * self.amount

    def get_position_value(self, current_price: Optional[Decimal] = None) -> Decimal:
        """
        Get the current value of the position.

        Args:
            current_price: Current market price (uses entry_price if None)

        Returns:
            Current position value in USD
        """
        price = current_price if current_price is not None else self.entry_price
        price = Decimal(str(price))
        return price * self.amount

    def to_dict(self) -> dict:
        """Convert position to dictionary for serialization."""
        return {
            'position_id': self.position_id,
            'symbol': self.symbol,
            'amount': str(self.amount),
            'entry_price': str(self.entry_price),
            'strategy_id': self.strategy_id,
            'opportunity_id': self.opportunity_id,
            'token_address': self.token_address,
            'chain': self.chain,
            'decimals': self.decimals,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ActivePosition':
        """Create position from dictionary."""
        return cls(
            position_id=data['position_id'],
            symbol=data['symbol'],
            amount=Decimal(data['amount']),
            entry_price=Decimal(data['entry_price']),
            strategy_id=data['strategy_id'],
            opportunity_id=data['opportunity_id'],
            token_address=data['token_address'],
            chain=data['chain'],
            decimals=data['decimals'],
            entry_time=datetime.fromisoformat(data['entry_time'])
        )
