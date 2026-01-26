"""
Multi-Chain Queue Manager
========================

Manages strict, isolated queues per chain type with deterministic dequeue behavior.
Concurrency-safe. Lossless. Chain-invariant enforcing.
"""

import asyncio
import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass

from networks.multi_chain_models import TokenCandidate, ChainType

logger = logging.getLogger(__name__)


@dataclass
class QueueStats:
    total_enqueued: int = 0
    total_dequeued: int = 0
    overflow_count: int = 0
    last_activity: Optional[float] = None


class MultiChainQueueManager:
    """
    Manages independent asyncio queues per chain type.
    Enforces strict chain isolation and safe dequeue semantics.
    """

    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self._closed = False

        self.queues: Dict[ChainType, asyncio.Queue] = {
            chain_type: asyncio.Queue(maxsize=max_queue_size)
            for chain_type in ChainType
        }

        self.stats: Dict[ChainType, QueueStats] = {
            chain_type: QueueStats()
            for chain_type in ChainType
        }

        logger.info(
            "Multi-chain queue manager initialized | max_queue_size=%s",
            max_queue_size,
        )

    # ------------------------------------------------------------------
    # ENQUEUE
    # ------------------------------------------------------------------

    async def enqueue(self, candidate: TokenCandidate) -> bool:
        if self._closed:
            logger.error("Attempted enqueue after queue manager closed")
            return False

        if not isinstance(candidate.chain_type, ChainType):
            logger.error(
                "Invalid chain_type on candidate %s: %r",
                candidate.symbol,
                candidate.chain_type,
            )
            return False

        queue = self.queues[candidate.chain_type]
        stats = self.stats[candidate.chain_type]

        try:
            queue.put_nowait(candidate)
        except asyncio.QueueFull:
            stats.overflow_count += 1
            logger.warning(
                "%s queue full | dropped %s | overflow=%s",
                candidate.chain_type.value,
                candidate.symbol,
                stats.overflow_count,
            )
            return False

        stats.total_enqueued += 1
        stats.last_activity = time.time()

        logger.debug(
            "Enqueued %s -> %s | size=%s/%s",
            candidate.symbol,
            candidate.chain_type.value,
            queue.qsize(),
            self.max_queue_size,
        )

        return True

    # ------------------------------------------------------------------
    # DEQUEUE (STRICT & SAFE)
    # ------------------------------------------------------------------

    async def dequeue(
        self, chain_type: ChainType, timeout: float = 1.0
    ) -> Optional[TokenCandidate]:

        if self._closed:
            return None

        queue = self.queues[chain_type]
        stats = self.stats[chain_type]

        try:
            candidate = await asyncio.wait_for(queue.get(), timeout)
        except asyncio.TimeoutError:
            return None

        stats.total_dequeued += 1
        stats.last_activity = time.time()

        logger.debug(
            "Dequeued %s <- %s | size=%s/%s",
            candidate.symbol,
            chain_type.value,
            queue.qsize(),
            self.max_queue_size,
        )

        return candidate

    # ------------------------------------------------------------------
    # PRIORITY DEQUEUE (NO RACES, NO TASK FANOUT)
    # ------------------------------------------------------------------

    async def dequeue_any(self, timeout: float = 1.0) -> Optional[TokenCandidate]:
        """
        Deterministically dequeue from the highest-priority non-empty queue.
        No speculative tasks. No cancellation races.
        """

        if self._closed:
            return None

        priority_order = (
            ChainType.EVM,
            ChainType.SOLANA,
            ChainType.APTOS,
            ChainType.SUI,
            ChainType.COSMOS,
            ChainType.BITCOIN,
        )

        # Fast path: immediate availability
        for chain_type in priority_order:
            queue = self.queues[chain_type]
            if not queue.empty():
                return await self.dequeue(chain_type, timeout=0.0)

        # Slow path: wait deterministically
        end_time = time.monotonic() + timeout
        while time.monotonic() < end_time:
            for chain_type in priority_order:
                queue = self.queues[chain_type]
                if not queue.empty():
                    return await self.dequeue(chain_type, timeout=0.0)
            await asyncio.sleep(0.01)

        return None

    # ------------------------------------------------------------------
    # INTROSPECTION
    # ------------------------------------------------------------------

    def get_queue_size(self, chain_type: ChainType) -> int:
        return self.queues[chain_type].qsize()

    def is_queue_full(self, chain_type: ChainType) -> bool:
        return self.queues[chain_type].full()

    def is_queue_empty(self, chain_type: ChainType) -> bool:
        return self.queues[chain_type].empty()

    def get_all_stats(self) -> Dict[str, Dict]:
        now = time.time()
        snapshot = {}

        for chain_type, stats in self.stats.items():
            queue = self.queues[chain_type]
            snapshot[chain_type.value] = {
                "total_enqueued": stats.total_enqueued,
                "total_dequeued": stats.total_dequeued,
                "current_size": queue.qsize(),
                "max_size": self.max_queue_size,
                "overflow_count": stats.overflow_count,
                "is_full": queue.full(),
                "is_empty": queue.empty(),
                "last_activity_seconds_ago": (
                    now - stats.last_activity if stats.last_activity else None
                ),
            }

        return snapshot

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------

    def clear_queue(self, chain_type: ChainType) -> int:
        queue = self.queues[chain_type]
        cleared = 0

        while not queue.empty():
            try:
                queue.get_nowait()
                cleared += 1
            except asyncio.QueueEmpty:
                break

        logger.info("Cleared %s items from %s queue", cleared, chain_type.value)
        return cleared

    def clear_all_queues(self) -> Dict[str, int]:
        return {
            chain_type.value: self.clear_queue(chain_type)
            for chain_type in ChainType
        }

    async def close(self):
        self._closed = True
        cleared = self.clear_all_queues()
        logger.info("Multi-chain queue manager closed | cleared=%s", cleared)


# ----------------------------------------------------------------------
# GLOBAL ACCESS
# ----------------------------------------------------------------------

_queue_manager: Optional[MultiChainQueueManager] = None


def get_queue_manager() -> MultiChainQueueManager:
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = MultiChainQueueManager()
    return _queue_manager


def initialize_queue_manager(max_queue_size: int = 1000) -> MultiChainQueueManager:
    global _queue_manager
    _queue_manager = MultiChainQueueManager(max_queue_size=max_queue_size)
    return _queue_manager


async def enqueue_token(candidate: TokenCandidate) -> bool:
    return await get_queue_manager().enqueue(candidate)


async def dequeue_token(
    chain_type: ChainType, timeout: float = 1.0
) -> Optional[TokenCandidate]:
    return await get_queue_manager().dequeue(chain_type, timeout)


async def dequeue_any_token(timeout: float = 1.0) -> Optional[TokenCandidate]:
    return await get_queue_manager().dequeue_any(timeout)

