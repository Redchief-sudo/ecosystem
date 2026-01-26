import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class ExecutionStatus(Enum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ApprovedOrder:
    order_id: str
    asset: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    price: Optional[float] = None
    time_in_force: str = "GTC"
    chain: str = "ethereum"
    policy_versions: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.order_id:
            raise ValueError("order_id is required")
        if not self.asset:
            raise ValueError("asset is required")
        if self.quantity <= 0:
            raise ValueError("quantity must be > 0")
        if self.order_type == OrderType.LIMIT and (self.price is None or self.price <= 0):
            raise ValueError("price is required for limit orders")


@dataclass(frozen=True)
class ExecutionReport:
    order_id: str
    status: ExecutionStatus
    filled_qty: float
    avg_price: Optional[float]
    venue: str
    timestamp: datetime
    transaction_hash: Optional[str] = None
    gas_used: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status.value,
            "filled_qty": self.filled_qty,
            "avg_price": self.avg_price,
            "venue": self.venue,
            "timestamp": self.timestamp.isoformat(),
            "transaction_hash": self.transaction_hash,
            "gas_used": self.gas_used,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class TradingEngine:
    """
    Pure Mechanical Trade Engine - No Decision Making
    """

    def __init__(self, config, ai, risk, executor, options):
        self.config = config
        self.ai = ai
        self.risk = risk
        self.executor = executor
        self.options = options

        self.active_orders: Dict[str, ApprovedOrder] = {}
        self.execution_history: List[ExecutionReport] = []

        logger.info("TradeEngine initialized - Pure mechanical executor")

    async def execute_approved_order(self, approved_order: ApprovedOrder) -> ExecutionReport:
        self.active_orders[approved_order.order_id] = approved_order

        try:
            execution_plan = self._translate_to_execution_plan(approved_order)
            result = await self._submit_to_venue(execution_plan)
            report = self._create_execution_report(approved_order, result)

            self.execution_history.append(report)
            self.active_orders.pop(approved_order.order_id, None)

            logger.info(f"Mechanical execution complete: {approved_order.order_id} - {report.status.value}")
            return report

        except Exception as e:
            error_report = ExecutionReport(
                order_id=approved_order.order_id,
                status=ExecutionStatus.REJECTED,
                filled_qty=0.0,
                avg_price=None,
                venue=approved_order.chain,
                timestamp=datetime.now(timezone.utc),
                error_message=str(e),
                metadata={"error_type": "execution_exception"},
            )

            self.execution_history.append(error_report)
            self.active_orders.pop(approved_order.order_id, None)
            logger.error(f"Mechanical execution failed: {approved_order.order_id} - {str(e)}")
            return error_report

    def _translate_to_execution_plan(self, approved_order: ApprovedOrder) -> Dict[str, Any]:
        return {
            "token_address": approved_order.asset,
            "chain": approved_order.chain,
            "amount": approved_order.quantity,
            "is_buy": approved_order.side == OrderSide.BUY,
            "target_price": approved_order.price,
            "order_type": approved_order.order_type.value,
            "time_in_force": approved_order.time_in_force,
            "policy_versions": approved_order.policy_versions,
            "metadata": approved_order.metadata,
        }

    async def _submit_to_venue(self, execution_plan: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = await self.executor.execute(execution_plan)

            if isinstance(result, dict):
                return result
            elif hasattr(result, "__dict__"):
                return result.__dict__
            else:
                return {
                    "success": False,
                    "error": f"Unknown response format: {type(result)}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "transaction_hash": None,
                "executed_price": None,
                "executed_amount": None,
                "gas_used": None
            }

    def _create_execution_report(self, approved_order: ApprovedOrder, result: Dict[str, Any]) -> ExecutionReport:
        success = result.get("success", False)

        if success:
            status = ExecutionStatus.FILLED
            filled_qty = float(result.get("executed_amount", approved_order.quantity))
            avg_price = float(result.get("executed_price", approved_order.price or 0.0))
        else:
            status = ExecutionStatus.REJECTED
            filled_qty = 0.0
            avg_price = None

        return ExecutionReport(
            order_id=approved_order.order_id,
            status=status,
            filled_qty=filled_qty,
            avg_price=avg_price,
            venue=approved_order.chain,
            timestamp=datetime.now(timezone.utc),
            transaction_hash=result.get("transaction_hash"),
            gas_used=result.get("gas_used"),
            error_message=result.get("error") if not success else None,
            metadata={
                "approved_order": asdict(approved_order),
                "venue_result": result,
            },
        )

    def get_order_status(self, order_id: str) -> Optional[ExecutionReport]:
        for report in self.execution_history:
            if report.order_id == order_id:
                return report
        return None

    def get_active_orders(self) -> List[ApprovedOrder]:
        return list(self.active_orders.values())

    def get_execution_history(self, limit: int = 100) -> List[ExecutionReport]:
        return self.execution_history[-limit:]

