import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GasReservation:
    reservation_id: str
    chain: str
    wallet_address: str
    estimated_gas_cost: Decimal
    reserved_at: datetime
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class GasTreasury:
    """
    Production-grade gas reserve manager.

    Guarantees:
    - No oversubscription
    - Deterministic expiration
    - Atomic reservation
    """

    def __init__(self, config: Dict[str, Any]):
        treasury_cfg = config.get("gas_treasury", {})

        self.gas_reserves: Dict[str, Decimal] = {
            chain: Decimal(str(amount))
            for chain, amount in treasury_cfg.get(
                "reserves",
                {
                    "polygon": 10.0,
                    "ethereum": 0.5,
                    "bsc": 0.5,
                    "arbitrum": 0.01,
                    "optimism": 0.01,
                    "base": 0.01,
                },
            ).items()
        }

        self.reservation_timeout = timedelta(
            seconds=int(treasury_cfg.get("reservation_timeout_seconds", 300))
        )

        self._reservations: Dict[str, GasReservation] = {}
        self._locks: Dict[str, asyncio.Lock] = {
            chain: asyncio.Lock() for chain in self.gas_reserves
        }

        logger.info("GasTreasury initialized")
        logger.info("Gas reserves: %s", self.gas_reserves)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def reserve_gas(
        self,
        chain: str,
        wallet_address: str,
        estimated_gas_cost: float,
    ) -> Optional[GasReservation]:

        if chain not in self.gas_reserves:
            logger.error("Unknown chain for gas reservation: %s", chain)
            return None

        if estimated_gas_cost <= 0:
            logger.error("Invalid gas cost: %s", estimated_gas_cost)
            return None

        cost = Decimal(str(estimated_gas_cost))

        async with self._locks[chain]:
            available = self.gas_reserves[chain]

            if available < cost:
                logger.warning(
                    "Insufficient gas reserve | chain=%s required=%s available=%s",
                    chain,
                    cost,
                    available,
                )
                return None

            reservation_id = uuid4().hex
            now = datetime.now(timezone.utc)

            reservation = GasReservation(
                reservation_id=reservation_id,
                chain=chain,
                wallet_address=wallet_address,
                estimated_gas_cost=cost,
                reserved_at=now,
                expires_at=now + self.reservation_timeout,
            )

            self._reservations[reservation_id] = reservation
            self.gas_reserves[chain] -= cost

            logger.info(
                "Gas reserved | id=%s chain=%s cost=%s remaining=%s",
                reservation_id[:12],
                chain,
                cost,
                self.gas_reserves[chain],
            )

            return reservation

    async def release_gas_reservation(self, reservation_id: str) -> bool:
        reservation = self._reservations.pop(reservation_id, None)

        if not reservation:
            logger.warning("Gas reservation not found: %s", reservation_id)
            return False

        async with self._locks[reservation.chain]:
            self.gas_reserves[reservation.chain] += reservation.estimated_gas_cost

        logger.info(
            "Gas reservation released | id=%s chain=%s returned=%s",
            reservation_id[:12],
            reservation.chain,
            reservation.estimated_gas_cost,
        )
        return True

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def cleanup_expired_reservations(self) -> int:
        expired = [
            rid for rid, r in self._reservations.items() if r.is_expired
        ]

        for rid in expired:
            await self.release_gas_reservation(rid)

        if expired:
            logger.info("Expired gas reservations cleaned: %d", len(expired))

        return len(expired)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_gas_reserves_status(self) -> Dict[str, Any]:
        return {
            "reserves": {k: float(v) for k, v in self.gas_reserves.items()},
            "active_reservations": len(self._reservations),
            "reservation_timeout_seconds": int(self.reservation_timeout.total_seconds()),
        }

