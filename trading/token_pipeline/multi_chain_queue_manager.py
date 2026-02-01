"""
Multi-Chain Queue Manager
========================

Manages strict, isolated queues per chain type with deterministic dequeue behavior.
Concurrency-safe. Lossless. Chain-invariant enforcing.
"""

import asyncio
import logging
import threading
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

        logger.info(
            "[QM-ENQUEUE] %s -> %s | size=%s/%s | id=%s",
            candidate.symbol,
            candidate.chain_type.value,
            queue.qsize(),
            self.max_queue_size,
            id(self),  # Track which queue manager instance
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
            logger.info("[QM-DEQUEUE] Timeout waiting for %s", chain_type.value)
            return None

        stats.total_dequeued += 1
        stats.last_activity = time.time()

        logger.info(
            "[QM-DEQUEUE] %s <- %s | size=%s/%s",
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

        logger.info(
            "[QM-DEQUEUE_ANY] Checking queues (id=%s): EVM=%s, SOLANA=%s, APTOS=%s, SUI=%s, COSMOS=%s, BTC=%s",
            id(self),
            self.queues[ChainType.EVM].qsize(),
            self.queues[ChainType.SOLANA].qsize(),
            self.queues[ChainType.APTOS].qsize(),
            self.queues[ChainType.SUI].qsize(),
            self.queues[ChainType.COSMOS].qsize(),
            self.queues[ChainType.BITCOIN].qsize(),
        )

        # Fast path: immediate availability
        for chain_type in priority_order:
            queue = self.queues[chain_type]
            if not queue.empty():
                logger.info("[QM-DEQUEUE_ANY] Found token in %s queue, attempting dequeue with timeout=0.5s", chain_type.value)
                result = await self.dequeue(chain_type, timeout=0.5)  # Use 0.5s instead of 0.0s to allow queue.get() to complete
                if result:
                    return result
                logger.info("[QM-DEQUEUE_ANY] Dequeue timed out for %s despite queue showing %d items", chain_type.value, queue.qsize())

        # Slow path: wait deterministically
        end_time = time.monotonic() + timeout
        while time.monotonic() < end_time:
            for chain_type in priority_order:
                queue = self.queues[chain_type]
                if not queue.empty():
                    logger.info("[QM-DEQUEUE_ANY] Found token in %s queue (slow path), attempting dequeue", chain_type.value)
                    result = await self.dequeue(chain_type, timeout=0.5)  # Use 0.5s instead of 0.0s
                    if result:
                        return result
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
# GLOBAL ACCESS - SINGLETON PATTERN
# ----------------------------------------------------------------------

_queue_manager: Optional[MultiChainQueueManager] = None
_queue_manager_lock = threading.Lock()
_queue_manager_initialized = False


def get_queue_manager() -> MultiChainQueueManager:
    """
    Get the global queue manager instance.
    Thread-safe singleton pattern to ensure all components use the same instance.
    """
    global _queue_manager, _queue_manager_initialized
    
    if _queue_manager is None:
        with _queue_manager_lock:
            # Double-check pattern
            if _queue_manager is None:
                _queue_manager = MultiChainQueueManager()
                _queue_manager_initialized = True
                logger.info(f"[QM-SINGLETON] Created new queue manager instance: {id(_queue_manager)}")
            else:
                logger.info(f"[QM-SINGLETON] Using existing queue manager instance: {id(_queue_manager)}")
    else:
        logger.debug(f"[QM-SINGLETON] Returning existing queue manager instance: {id(_queue_manager)}")
    
    return _queue_manager


def initialize_queue_manager(max_queue_size: int = 1000) -> MultiChainQueueManager:
    """
    Initialize the global queue manager with explicit parameters.
    Should be called once during system startup.
    """
    global _queue_manager, _queue_manager_initialized
    
    with _queue_manager_lock:
        if _queue_manager is not None and _queue_manager_initialized:
            logger.info(f"[QM-SINGLETON] Queue manager already initialized: {id(_queue_manager)} - returning existing instance")
            return _queue_manager
        
        if _queue_manager is None:
            _queue_manager = MultiChainQueueManager(max_queue_size=max_queue_size)
            _queue_manager_initialized = True
            logger.info(f"[QM-SINGLETON] Created new queue manager: {id(_queue_manager)} with max_size={max_queue_size}")
        else:
            logger.warning(f"[QM-SINGLETON] Queue manager exists but not marked as initialized - marking as initialized: {id(_queue_manager)}")
            _queue_manager_initialized = True
            
        return _queue_manager


def is_queue_manager_initialized() -> bool:
    """Check if the queue manager has been initialized."""
    return _queue_manager is not None and _queue_manager_initialized


async def enqueue_token(candidate: TokenCandidate) -> bool:
    """Enqueue a token candidate with instance tracking for debugging."""
    queue_manager = get_queue_manager()
    logger.debug(f"[ENQUEUE] Using queue manager instance: {id(queue_manager)} for {candidate.symbol}")
    return await queue_manager.enqueue(candidate)


async def dequeue_token(
    chain_type: ChainType, timeout: float = 1.0
) -> Optional[TokenCandidate]:
    return await get_queue_manager().dequeue(chain_type, timeout)


async def dequeue_any_token(timeout: float = 1.0) -> Optional[TokenCandidate]:
    """Dequeue from any chain with instance tracking for debugging."""
    queue_manager = get_queue_manager()
    logger.debug(f"[DEQUEUE_ANY] Using queue manager instance: {id(queue_manager)}")
    return await queue_manager.dequeue_any(timeout)

