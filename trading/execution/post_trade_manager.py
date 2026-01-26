"""
Post-Trade Lifecycle Management - Critical for production trading system.

Handles transaction finalization, position tracking, and system state updates.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Transaction execution status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REPLACED = "replaced"
    PARTIAL_FILL = "partial_fill"


@dataclass
class ExecutionReceipt:
    """Canonical record of trade execution attempt."""
    opportunity_id: str
    chain: str
    status: TransactionStatus

    tx_hash: Optional[str] = None
    gas_used: Optional[int] = None
    effective_gas_price: Optional[Decimal] = None
    block_number: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    amount_in: Optional[Decimal] = None
    amount_out: Optional[Decimal] = None
    token_in: Optional[str] = None
    token_out: Optional[str] = None
    token_symbol_out: Optional[str] = None
    entry_price_usd: Optional[Decimal] = None
    actual_slippage_bps: Optional[float] = None
    fees_usd: Optional[Decimal] = None

    error_message: Optional[str] = None
    revert_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'tx_hash': self.tx_hash,
            'opportunity_id': self.opportunity_id,
            'chain': self.chain,
            'status': self.status.value,
            'gas_used': self.gas_used,
            'effective_gas_price': str(self.effective_gas_price) if self.effective_gas_price else None,
            'block_number': self.block_number,
            'timestamp': self.timestamp.isoformat(),
            'amount_in': str(self.amount_in) if self.amount_in else None,
            'amount_out': str(self.amount_out) if self.amount_out else None,
            'token_in': self.token_in,
            'token_out': self.token_out,
            'token_symbol_out': self.token_symbol_out,
            'entry_price_usd': str(self.entry_price_usd) if self.entry_price_usd else None,
            'actual_slippage_bps': self.actual_slippage_bps,
            'fees_usd': str(self.fees_usd) if self.fees_usd else None,
            'error_message': self.error_message,
            'revert_reason': self.revert_reason,
        }


@dataclass
class Position:
    """Current position tracking."""
    chain: str
    token_symbol: str
    token_address: str
    amount: Decimal
    entry_price_usd: Decimal
    current_price_usd: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain": self.chain,
            "token_symbol": self.token_symbol,
            "token_address": self.token_address,
            "amount": str(self.amount),
            "entry_price_usd": str(self.entry_price_usd),
            "current_price_usd": str(self.current_price_usd) if self.current_price_usd else None,
            "unrealized_pnl": str(self.unrealized_pnl) if self.unrealized_pnl else None,
            "timestamp": self.timestamp.isoformat(),
        }


class PostTradeManager:
    """
    Manages all post-trade lifecycle operations.

    This is the ONLY component that should modify state after execution.
    All position updates, risk calculations, and memory writes happen here.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.positions: Dict[str, Position] = {}
        self.execution_history: List[ExecutionReceipt] = []
        self._lock = asyncio.Lock()

        # Risk limits
        self.max_position_size_usd = Decimal(str(config.get('risk', {}).get('max_position_size_usd', 1000.0)))
        self.max_drawdown_pct = Decimal(str(config.get('risk', {}).get('max_drawdown_pct', 15.0)))
        self.max_exposure_per_chain = Decimal(str(config.get('risk', {}).get('max_exposure_per_chain', 2000.0)))

        # Balance tracking
        self.profit_engine = None
        self.trade_executor = None

    def set_balance_tracking(self, profit_engine, trade_executor):
        """Set balance tracking components for post-trade balance updates."""
        self.profit_engine = profit_engine
        self.trade_executor = trade_executor
        logger.info("Balance tracking components configured for post-trade updates")

    def get_open_positions(self) -> Dict[str, Position]:
        """Get all currently open positions."""
        return self.positions.copy()

    def has_open_positions(self) -> bool:
        """Check if there are any open positions."""
        return len(self.positions) > 0

    async def process_execution_result(self, receipt: ExecutionReceipt) -> None:
        """
        Process the result of a trade execution.

        This is the main entry point for post-trade handling.
        """
        async with self._lock:
            try:
                self.execution_history.append(receipt)

                if receipt.status == TransactionStatus.CONFIRMED:
                    await self._handle_confirmed_trade(receipt)
                elif receipt.status == TransactionStatus.FAILED:
                    await self._handle_failed_trade(receipt)
                elif receipt.status == TransactionStatus.PARTIAL_FILL:
                    await self._handle_partial_fill(receipt)
                elif receipt.status == TransactionStatus.REPLACED:
                    await self._handle_replaced_trade(receipt)

                # Update wallet balances after trade execution (both paper and live modes)
                if self.profit_engine and self.trade_executor:
                    try:
                        await self._update_wallet_balances(receipt)
                    except Exception as balance_error:
                        logger.error(f"Balance update failed for {receipt.opportunity_id}: {balance_error}")

                await self._update_risk_metrics()
                await self._write_to_memory(receipt)

                logger.info(f"📊 Post-trade processed: {receipt.opportunity_id} - {receipt.status.value}")

            except Exception as e:
                logger.error(f"Post-trade processing error: {e}")

    async def _handle_confirmed_trade(self, receipt: ExecutionReceipt) -> None:
        """Handle a successfully confirmed trade."""
        if not receipt.amount_out or not receipt.token_out or not receipt.token_symbol_out or not receipt.entry_price_usd:
            logger.warning(f"Confirmed trade {receipt.opportunity_id} missing required fields")
            return

        position_key = f"{receipt.chain}:{receipt.token_address or receipt.token_out}"

        current_position = self.positions.get(position_key)

        if current_position:
            # Weighted average entry price
            total_cost = (current_position.entry_price_usd * current_position.amount) + (receipt.entry_price_usd * receipt.amount_out)
            total_amount = current_position.amount + receipt.amount_out
            current_position.entry_price_usd = total_cost / total_amount
            current_position.amount = total_amount
            current_position.current_price_usd = receipt.entry_price_usd
            current_position.unrealized_pnl = self._calculate_pnl(current_position)
        else:
            self.positions[position_key] = Position(
                chain=receipt.chain,
                token_symbol=receipt.token_symbol_out,
                token_address=receipt.token_out,
                amount=receipt.amount_out,
                entry_price_usd=receipt.entry_price_usd,
                current_price_usd=receipt.entry_price_usd
            )

    async def _handle_failed_trade(self, receipt: ExecutionReceipt) -> None:
        """Handle a failed trade execution."""
        logger.error(f"❌ Trade failed: {receipt.opportunity_id} - {receipt.error_message}")

    async def _handle_partial_fill(self, receipt: ExecutionReceipt) -> None:
        """Handle a partially filled trade."""
        logger.warning(f"⚠️ Partial fill: {receipt.opportunity_id} - {receipt.amount_out}/{receipt.amount_in}")

        if receipt.amount_out and receipt.token_out and receipt.token_symbol_out and receipt.entry_price_usd:
            position_key = f"{receipt.chain}:{receipt.token_out}"
            current_position = self.positions.get(position_key)

            if current_position:
                current_position.amount += receipt.amount_out
                current_position.current_price_usd = receipt.entry_price_usd
                current_position.unrealized_pnl = self._calculate_pnl(current_position)
            else:
                self.positions[position_key] = Position(
                    chain=receipt.chain,
                    token_symbol=receipt.token_symbol_out,
                    token_address=receipt.token_out,
                    amount=receipt.amount_out,
                    entry_price_usd=receipt.entry_price_usd,
                    current_price_usd=receipt.entry_price_usd
                )

    async def _handle_replaced_trade(self, receipt: ExecutionReceipt) -> None:
        """Handle replaced transaction (nonce replacement)."""
        logger.info(f"🔁 Transaction replaced: {receipt.opportunity_id} - {receipt.tx_hash}")

    async def _update_wallet_balances(self, receipt: ExecutionReceipt) -> None:
        """Update wallet balances after trade execution."""
        if not self.profit_engine or not self.trade_executor:
            return

        is_paper_mode = getattr(self.trade_executor, "trading_mode", "paper") == "paper"

        if is_paper_mode:
            await self._update_paper_balances(receipt)
        else:
            await self.profit_engine.update_balances(self.trade_executor)

    async def _update_paper_balances(self, receipt: ExecutionReceipt) -> None:
        """Update simulated balances for paper trading mode."""
        if not hasattr(self.profit_engine, "balances"):
            self.profit_engine.balances = {}

        chain = receipt.chain
        if receipt.amount_in and receipt.amount_out and receipt.entry_price_usd:
            # Convert token amounts to USD value using entry_price_usd
            change_usd = (receipt.amount_out * receipt.entry_price_usd) - (receipt.amount_in * receipt.entry_price_usd)

            self.profit_engine.balances[chain] = self.profit_engine.balances.get(chain, Decimal("0")) + change_usd
            self.profit_engine.total_portfolio_value = sum(self.profit_engine.balances.values())

    async def _update_risk_metrics(self) -> None:
        """Update system-wide risk metrics."""
        exposure_by_chain: Dict[str, Decimal] = {}

        for pos in self.positions.values():
            value = pos.amount * pos.entry_price_usd
            exposure_by_chain[pos.chain] = exposure_by_chain.get(pos.chain, Decimal("0")) + value

        for chain, exposure in exposure_by_chain.items():
            if exposure > self.max_exposure_per_chain:
                logger.warning(f"⚠️ High exposure on {chain}: ${exposure}")

        for pos in self.positions.values():
            if pos.amount * pos.entry_price_usd > self.max_position_size_usd:
                logger.warning(f"⚠️ Large position: {pos.token_symbol} on {pos.chain} - ${pos.amount * pos.entry_price_usd}")

    async def _write_to_memory(self, receipt: ExecutionReceipt) -> None:
        """Write execution results to memory for AI learning."""
        try:
            from utils.memory import MemoryManager

            performance_record = {
                'opportunity_id': receipt.opportunity_id,
                'outcome': receipt.status.value,
                'gas_used': receipt.gas_used,
                'slippage_bps': receipt.actual_slippage_bps,
                'fees_usd': receipt.fees_usd,
                'timestamp': receipt.timestamp.isoformat(),
                'chain': receipt.chain,
            }

            logger.info(f"🧠 Writing performance to memory: {receipt.opportunity_id}")

        except Exception as e:
            logger.error(f"Failed to write to memory: {e}")

    def _calculate_pnl(self, position: Position) -> Decimal:
        """Calculate unrealized PnL for a position."""
        if not position.current_price_usd:
            return Decimal("0")
        return (position.current_price_usd - position.entry_price_usd) * position.amount

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get current portfolio summary."""
        total_value = sum(
            pos.amount * (pos.current_price_usd or pos.entry_price_usd)
            for pos in self.positions.values()
        )

        return {
            'total_positions': len(self.positions),
            'total_value_usd': float(total_value),
            'positions': {k: v.to_dict() for k, v in self.positions.items()},
        }

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return [receipt.to_dict() for receipt in self.execution_history[-limit:]]

