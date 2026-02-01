"""
Treasury Manager Module
=======================

Manages treasury operations including gas reserves, capital allocation,
and financial risk management for trading operations.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional

from core.health_check import HealthStatus, standard_health_check

logger = logging.getLogger(__name__)


class TreasuryStatus(Enum):
    """Treasury operational status."""
    ACTIVE = "active"
    FROZEN = "frozen"
    MAINTENANCE = "maintenance"
    INSUFFICIENT_FUNDS = "insufficient_funds"


@dataclass
class TreasuryBalance:
    """Represents treasury balance for a specific chain/token."""
    chain: str
    token_symbol: str
    token_address: str
    balance: Decimal
    usd_value: float
    last_updated: datetime
    reserved_amount: Decimal = Decimal("0")

    @property
    def available_amount(self) -> Decimal:
        """Calculate available amount after reservations."""
        return max(Decimal("0"), self.balance - self.reserved_amount)


@dataclass
class CapitalAllocation:
    """Represents capital allocation to a strategy or operation."""
    allocation_id: str
    strategy_name: str
    chain: str
    allocated_amount: Decimal
    allocated_at: datetime
    expires_at: Optional[datetime] = None
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


@dataclass
class TreasuryMetrics:
    """Treasury performance and operational metrics."""
    total_value_usd: float
    daily_pnl: float
    utilization_rate: float
    gas_efficiency: float
    allocation_count: int
    last_rebalance: datetime
    risk_score: float


class TreasuryManager:
    """
    Manages treasury operations across multiple chains and tokens.

    Responsibilities:
    - Track treasury balances across all chains
    - Manage gas reserves for trading operations
    - Allocate capital to trading strategies
    - Monitor treasury health and performance
    - Handle risk management and limits
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.status = TreasuryStatus.ACTIVE

        # Treasury storage
        self.balances: Dict[str, TreasuryBalance] = {}
        self.allocations: Dict[str, CapitalAllocation] = {}
        self.reservations: Dict[str, Dict[str, Decimal]] = {}

        # Locks
        self._lock = asyncio.Lock()

        # Configuration
        self.min_balance_thresholds = config.get(
            "min_balance_thresholds",
            {
                "ethereum": {"ETH": Decimal("0.1")},
                "polygon": {"MATIC": Decimal("10")},
                "bsc": {"BNB": Decimal("0.1")},
                "arbitrum": {"ETH": Decimal("0.05")},
                "optimism": {"ETH": Decimal("0.05")},
                "base": {"ETH": Decimal("0.05")},
            },
        )

        self.max_allocation_pct = Decimal(str(config.get("max_allocation_pct", 0.8)))
        self.rebalance_threshold = Decimal(str(config.get("rebalance_threshold", 0.1)))

        # Metrics
        self.metrics = TreasuryMetrics(
            total_value_usd=0.0,
            daily_pnl=0.0,
            utilization_rate=0.0,
            gas_efficiency=0.0,
            allocation_count=0,
            last_rebalance=datetime.now(timezone.utc),
            risk_score=0.0,
        )

        # Background tasks
        self._tasks: List[asyncio.Task] = []

        logger.info("Treasury Manager initialized")

    # -----------------------------
    # Health Check
    # -----------------------------
    @standard_health_check("Treasury Manager")
    async def health_check(self) -> HealthStatus:
        async with self._lock:
            try:
                self._update_metrics()

                low_balances = []
                for key, balance in self.balances.items():
                    threshold = self.min_balance_thresholds.get(balance.chain, {}).get(
                        balance.token_symbol, Decimal("0")
                    )
                    if balance.available_amount < threshold:
                        low_balances.append(key)

                high_utilization = self.metrics.utilization_rate > 0.9
                status_healthy = (
                    self.status == TreasuryStatus.ACTIVE and
                    len(low_balances) == 0 and
                    not high_utilization
                )

                return HealthStatus(
                    component="Treasury Manager",
                    status=status_healthy,
                    message=(
                        f"Treasury healthy - Total: ${self.metrics.total_value_usd:,.2f}, "
                        f"Utilization: {self.metrics.utilization_rate:.1%}"
                        if status_healthy
                        else f"Treasury issues - Status: {self.status.value}, "
                             f"Low balances: {low_balances}, "
                             f"High utilization: {high_utilization}"
                    ),
                    metrics={
                        "status": self.status.value,
                        "total_value_usd": self.metrics.total_value_usd,
                        "daily_pnl": self.metrics.daily_pnl,
                        "utilization_rate": self.metrics.utilization_rate,
                        "allocation_count": self.metrics.allocation_count,
                        "low_balances": low_balances,
                        "risk_score": self.metrics.risk_score,
                    },
                )

            except Exception as e:
                return HealthStatus(
                    component="Treasury Manager",
                    status=False,
                    message=f"Health check failed: {e}",
                    metrics={},
                )

    # -----------------------------
    # Balance & Accounting
    # -----------------------------
    async def update_balance(
        self,
        chain: str,
        token_symbol: str,
        token_address: str,
        balance: Decimal,
        usd_value: float,
    ) -> None:
        async with self._lock:
            key = f"{chain}:{token_symbol}"
            existing_reserved = self.balances.get(key, TreasuryBalance(
                chain=chain,
                token_symbol=token_symbol,
                token_address=token_address,
                balance=Decimal("0"),
                usd_value=0.0,
                last_updated=datetime.now(timezone.utc),
            )).reserved_amount

            self.balances[key] = TreasuryBalance(
                chain=chain,
                token_symbol=token_symbol,
                token_address=token_address,
                balance=balance,
                usd_value=usd_value,
                last_updated=datetime.now(timezone.utc),
                reserved_amount=existing_reserved,
            )
            self._update_metrics()

    # -----------------------------
    # Gas Reservation
    # -----------------------------
    async def reserve_gas(
        self,
        chain: str,
        token_symbol: Optional[str] = None,
        amount: Decimal = Decimal("0"),
        strategy_name: str = "unknown",
    ) -> bool:
        async with self._lock:
            token_symbol = token_symbol or self._get_gas_token(chain)
            if token_symbol is None:
                logger.error(f"Unknown gas token for chain {chain}")
                return False

            key = f"{chain}:{token_symbol}"
            if key not in self.balances:
                logger.error(f"No balance found for {key}")
                return False

            balance = self.balances[key]
            if balance.available_amount < amount:
                logger.warning(
                    f"Insufficient gas balance for {key}: need {amount}, available {balance.available_amount}"
                )
                return False

            balance.reserved_amount += amount
            self.reservations.setdefault(key, {})[strategy_name] = (
                self.reservations.setdefault(key, {}).get(strategy_name, Decimal("0")) + amount
            )
            self._update_metrics()
            logger.info(f"Reserved {amount} {token_symbol} for {strategy_name} on {chain}")
            return True

    async def release_gas(
        self,
        chain: str,
        token_symbol: Optional[str] = None,
        amount: Decimal = Decimal("0"),
        strategy_name: str = "unknown",
    ) -> None:
        async with self._lock:
            token_symbol = token_symbol or self._get_gas_token(chain)
            if token_symbol is None:
                return

            key = f"{chain}:{token_symbol}"
            if key not in self.balances or key not in self.reservations:
                return

            strategy_reserved = self.reservations[key].get(strategy_name, Decimal("0"))
            release_amount = min(amount, strategy_reserved, self.balances[key].reserved_amount)

            self.balances[key].reserved_amount -= release_amount
            if strategy_reserved <= release_amount:
                self.reservations[key].pop(strategy_name, None)
            else:
                self.reservations[key][strategy_name] = strategy_reserved - release_amount

            if not self.reservations[key]:
                self.reservations.pop(key, None)

            self._update_metrics()
            logger.info(f"Released {release_amount} {token_symbol} for {strategy_name} on {chain}")

    # -----------------------------
    # Capital Allocation
    # -----------------------------
    async def allocate_capital(
        self,
        strategy_name: str,
        chain: str,
        amount: Decimal,
        duration_hours: Optional[int] = None,
    ) -> str:
        async with self._lock:
            total_available = self.get_available_capital(chain)
            max_allowed = total_available * self.max_allocation_pct

            if amount > max_allowed:
                raise ValueError(
                    f"Allocation exceeds allowed limit. "
                    f"Requested: {amount}, Allowed: {max_allowed}"
                )

            allocation_id = f"{strategy_name}:{chain}:{datetime.now(timezone.utc).timestamp()}"

            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=duration_hours)
                if duration_hours
                else None
            )

            allocation = CapitalAllocation(
                allocation_id=allocation_id,
                strategy_name=strategy_name,
                chain=chain,
                allocated_amount=amount,
                allocated_at=datetime.now(timezone.utc),
                expires_at=expires_at,
            )

            self.allocations[allocation_id] = allocation
            self._update_metrics()
            logger.info(f"Allocated {amount} to {strategy_name} on {chain}")
            return allocation_id

    async def deallocate_capital(self, allocation_id: str) -> bool:
        async with self._lock:
            if allocation_id not in self.allocations:
                return False

            allocation = self.allocations[allocation_id]
            allocation.is_active = False
            self._update_metrics()
            logger.info(f"Deallocated capital from {allocation.strategy_name}")
            return True

    def get_available_capital(self, chain: str) -> Decimal:
        total_available = Decimal("0")
        for key, balance in self.balances.items():
            if balance.chain == chain:
                total_available += balance.available_amount
        return total_available

    # -----------------------------
    # Metrics & Internal Helpers
    # -----------------------------
    def _get_gas_token(self, chain: str) -> Optional[str]:
        gas_tokens = {
            "ethereum": "ETH",
            "polygon": "MATIC",
            "bsc": "BNB",
            "arbitrum": "ETH",
            "optimism": "ETH",
            "base": "ETH",
        }
        return gas_tokens.get(chain)

    def _update_metrics(self) -> None:
        self.metrics.total_value_usd = sum(b.usd_value for b in self.balances.values())

        total_balance = sum(b.balance for b in self.balances.values())
        total_reserved = sum(b.reserved_amount for b in self.balances.values())
        self.metrics.utilization_rate = (
            float(total_reserved / total_balance) if total_balance > 0 else 0.0
        )

        self.metrics.allocation_count = sum(1 for a in self.allocations.values() if a.is_active)

        # Simple risk score and gas efficiency model
        self.metrics.risk_score = min(1.0, self.metrics.utilization_rate + (0.1 * self.metrics.allocation_count))
        self.metrics.gas_efficiency = (
            float(1.0 - self.metrics.utilization_rate)
            if self.metrics.utilization_rate <= 1.0
            else 0.0
        )

    # -----------------------------
    # Lifecycle
    # -----------------------------
    async def start(self) -> None:
        async with self._lock:
            if self.status != TreasuryStatus.ACTIVE:
                self.status = TreasuryStatus.ACTIVE
            self._tasks = [
                asyncio.create_task(self._monitor_allocations()),
                asyncio.create_task(self._rebalance_check()),
            ]

    async def stop(self) -> None:
        async with self._lock:
            self.status = TreasuryStatus.MAINTENANCE
            for task in self._tasks:
                task.cancel()
            self._tasks.clear()

    async def _monitor_allocations(self) -> None:
        while self.status == TreasuryStatus.ACTIVE:
            try:
                now = datetime.now(timezone.utc)
                expired = [
                    alloc_id for alloc_id, alloc in self.allocations.items()
                    if alloc.expires_at and alloc.expires_at < now and alloc.is_active
                ]
                for alloc_id in expired:
                    await self.deallocate_capital(alloc_id)

                await asyncio.sleep(300)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Error monitoring allocations: {e}")
                await asyncio.sleep(60)

    async def _rebalance_check(self) -> None:
        while self.status == TreasuryStatus.ACTIVE:
            try:
                if Decimal(str(self.metrics.utilization_rate)) > self.rebalance_threshold:
                    logger.info(f"High utilization detected ({self.metrics.utilization_rate:.1%})")

                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Error in rebalance check: {e}")
                await asyncio.sleep(300)

