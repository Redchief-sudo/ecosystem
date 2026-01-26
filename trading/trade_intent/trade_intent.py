"""
Trade Intent - Canonical trade specification with execution parameters.

This is the single source of truth for all trade execution.
All components must convert to/from this format.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from eth_typing import Address

logger = logging.getLogger(__name__)


class ExecutionType(Enum):
    """Trade execution types."""
    IMMEDIATE = "immediate"
    LIMIT = "limit"
    SANDWICH_SAFE = "sandwich_safe"
    FLASHLOAN = "flashloan"


class TradeSide(Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


class SlippageMode(Enum):
    """Slippage handling mode."""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


@dataclass(frozen=True)
class TradeIntent:
    """
    Canonical trade intent specification.

    This is the ONLY valid input to the trading system.
    All decisions must be converted to this format before execution.
    """

    # Core identification
    chain: str
    router: str  # Router contract address or identifier
    token_in: Address  # Input token address
    token_out: Address  # Output token address

    # Trade parameters
    amount_in: Decimal  # Exact input amount
    min_amount_out: Decimal  # Minimum output (slippage protection)
    deadline: datetime  # Block deadline

    # Metadata
    opportunity_id: str

    # Defaulted fields (must come after all non-default fields)
    slippage_bps: int = 50  # Max slippage in basis points
    slippage_mode: SlippageMode = SlippageMode.RELATIVE
    execution_type: ExecutionType = ExecutionType.IMMEDIATE
    side: TradeSide = TradeSide.BUY
    confidence: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional routing hints
    gas_limit: Optional[int] = None
    gas_price: Optional[Decimal] = None

    # Optional additional fields for production
    route: Optional[List[str]] = None  # list of token addresses
    fee_token: Optional[Address] = None
    max_fee_usd: Optional[Decimal] = None
    intent_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "chain": self.chain,
            "router": self.router,
            "token_in": str(self.token_in),
            "token_out": str(self.token_out),
            "amount_in": str(self.amount_in),
            "min_amount_out": str(self.min_amount_out),
            "slippage_bps": self.slippage_bps,
            "slippage_mode": self.slippage_mode.value,
            "deadline": self.deadline.isoformat(),
            "execution_type": self.execution_type.value,
            "side": self.side.value,
            "opportunity_id": self.opportunity_id,
            "confidence": float(self.confidence),
            "created_at": self.created_at.isoformat(),
            "gas_limit": self.gas_limit,
            "gas_price": str(self.gas_price) if self.gas_price is not None else None,
            "route": self.route,
            "fee_token": str(self.fee_token) if self.fee_token is not None else None,
            "max_fee_usd": str(self.max_fee_usd) if self.max_fee_usd is not None else None,
            "intent_id": self.intent_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeIntent":
        """Create from dictionary."""
        token_in = data.get("token_in")
        token_out = data.get("token_out")

        if isinstance(token_in, Address):
            token_in_addr = token_in
        else:
            token_in_addr = Address(token_in)

        if isinstance(token_out, Address):
            token_out_addr = token_out
        else:
            token_out_addr = Address(token_out)

        fee_token = data.get("fee_token")
        if fee_token is not None:
            fee_token = Address(fee_token)

        created_at = data.get("created_at")
        if created_at:
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(timezone.utc)

        deadline = data.get("deadline")
        if isinstance(deadline, str):
            deadline = datetime.fromisoformat(deadline)

        return cls(
            chain=data["chain"],
            router=data["router"],
            token_in=token_in_addr,
            token_out=token_out_addr,
            amount_in=Decimal(data["amount_in"]),
            min_amount_out=Decimal(data["min_amount_out"]),
            slippage_bps=int(data.get("slippage_bps", 50)),
            slippage_mode=SlippageMode(data.get("slippage_mode", SlippageMode.RELATIVE.value)),
            deadline=deadline,
            execution_type=ExecutionType(data.get("execution_type", ExecutionType.IMMEDIATE.value)),
            side=TradeSide(data.get("side", TradeSide.BUY.value)),
            opportunity_id=data["opportunity_id"],
            confidence=float(data.get("confidence", 0.0)),
            created_at=created_at,
            gas_limit=data.get("gas_limit"),
            gas_price=Decimal(data["gas_price"]) if data.get("gas_price") else None,
            route=data.get("route"),
            fee_token=fee_token,
            max_fee_usd=Decimal(data["max_fee_usd"]) if data.get("max_fee_usd") else None,
            intent_id=data.get("intent_id", str(uuid.uuid4())),
        )

    def is_executable(self) -> bool:
        """Check if intent has all required fields for execution."""
        # Required fields
        if not self.chain or not self.router:
            return False

        if not isinstance(self.token_in, Address) or not isinstance(self.token_out, Address):
            return False

        if self.amount_in <= 0 or self.min_amount_out <= 0:
            return False

        if self.deadline <= datetime.now(timezone.utc):
            return False

        if self.slippage_bps < 0 or self.slippage_bps > 1000:
            return False

        if self.confidence < 0.0 or self.confidence > 1.0:
            return False

        return True

    def __str__(self) -> str:
        return (
            f"TradeIntent({self.side.value} {self.amount_in} "
            f"{str(self.token_in)[:8]}... → {str(self.token_out)[:8]}... on {self.chain})"
        )

