"""
Backpressure Management
Provides queue pressure monitoring and adaptive throttling.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PressureLevel(Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueueMetrics:
    name: str
    size: int
    max_size: int
    utilization: float
    pressure_level: PressureLevel
    timestamp: float


class BackpressureManager:
    """
    Monitors queue pressure and provides throttling recommendations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Thresholds
        self.elevated_threshold = self.config.get("elevated_threshold", 0.5)
        self.high_threshold = self.config.get("high_threshold", 0.8)
        self.critical_threshold = self.config.get("critical_threshold", 0.9)
        
        # Throttling config
        self.base_throttle_delay = self.config.get("base_throttle_delay", 0.1)
        self.max_throttle_delay = self.config.get("max_throttle_delay", 5.0)
        
        # State
        self._queue_metrics: Dict[str, QueueMetrics] = {}
        self._last_throttle_time: Dict[str, float] = {}
        
        logger.info("BackpressureManager initialized")
    
    def check_queue(self, name: str, size: int, max_size: int) -> PressureLevel:
        """Check pressure level for a queue."""
        utilization = size / max_size if max_size > 0 else 0.0
        
        if utilization >= self.critical_threshold:
            level = PressureLevel.CRITICAL
        elif utilization >= self.high_threshold:
            level = PressureLevel.HIGH
        elif utilization >= self.elevated_threshold:
            level = PressureLevel.ELEVATED
        else:
            level = PressureLevel.NORMAL
        
        # Store metrics
        self._queue_metrics[name] = QueueMetrics(
            name=name,
            size=size,
            max_size=max_size,
            utilization=utilization,
            pressure_level=level,
            timestamp=time.time()
        )
        
        return level
    
    def should_throttle(self, name: str) -> bool:
        """Check if throttling is recommended for a queue."""
        if name not in self._queue_metrics:
            return False
        
        metrics = self._queue_metrics[name]
        return metrics.pressure_level in [PressureLevel.HIGH, PressureLevel.CRITICAL]
    
    def get_throttle_delay(self, name: str) -> float:
        """Get recommended throttle delay for a queue."""
        if name not in self._queue_metrics:
            return 0.0
        
        metrics = self._queue_metrics[name]
        
        # Calculate delay based on pressure
        if metrics.pressure_level == PressureLevel.CRITICAL:
            delay = self.max_throttle_delay
        elif metrics.pressure_level == PressureLevel.HIGH:
            delay = self.base_throttle_delay * 10
        elif metrics.pressure_level == PressureLevel.ELEVATED:
            delay = self.base_throttle_delay * 2
        else:
            delay = 0.0
        
        # Record throttle
        self._last_throttle_time[name] = time.time()
        
        return delay
    
    def get_metrics(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for all queues or specific queue."""
        if name:
            metrics = self._queue_metrics.get(name)
            if metrics:
                return {
                    "name": metrics.name,
                    "size": metrics.size,
                    "max_size": metrics.max_size,
                    "utilization": metrics.utilization,
                    "pressure_level": metrics.pressure_level.value
                }
            return {}
        
        return {
            name: {
                "size": m.size,
                "max_size": m.max_size,
                "utilization": m.utilization,
                "pressure_level": m.pressure_level.value
            }
            for name, m in self._queue_metrics.items()
        }


class AdaptiveQueueManager:
    """
    Wraps an asyncio.Queue with backpressure-aware operations.
    """
    
    def __init__(
        self,
        queue: asyncio.Queue,
        queue_name: str,
        backpressure_manager: BackpressureManager
    ):
        self.queue = queue
        self.queue_name = queue_name
        self.backpressure_manager = backpressure_manager
    
    async def put(self, item: Any, timeout: Optional[float] = None) -> bool:
        """Put item to queue with backpressure check."""
        # Check pressure before putting
        pressure = self.backpressure_manager.check_queue(
            self.queue_name,
            self.queue.qsize(),
            self.queue.maxsize
        )
        
        if pressure == PressureLevel.CRITICAL:
            logger.warning(f"Queue {self.queue_name} at CRITICAL pressure, rejecting put")
            return False
        
        try:
            if timeout:
                await asyncio.wait_for(self.queue.put(item), timeout=timeout)
            else:
                await self.queue.put(item)
            return True
        except asyncio.TimeoutError:
            return False
    
    async def get(self, timeout: Optional[float] = None) -> Optional[Any]:
        """Get item from queue with optional timeout."""
        try:
            if timeout:
                return await asyncio.wait_for(self.queue.get(), timeout=timeout)
            else:
                return await self.queue.get()
        except asyncio.TimeoutError:
            return None
    
    def qsize(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self.queue.empty()
    
    def full(self) -> bool:
        """Check if queue is full."""
        return self.queue.full()


class AIControllerFailureIsolation:
    """
    Circuit breaker pattern for AI controller failures.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Circuit breaker config
        self.max_consecutive_failures = self.config.get("max_consecutive_failures", 5)
        self.circuit_reset_seconds = self.config.get("circuit_reset_seconds", 300)
        
        # State
        self._consecutive_failures = 0
        self._circuit_open = False
        self._circuit_opened_at: Optional[float] = None
        self._total_failures = 0
        self._total_successes = 0
    
    async def execute_with_isolation(self, func, *args, **kwargs):
        """
        Execute function with failure isolation.
        Returns (success, result) tuple.
        """
        # Check if circuit is open
        if self._circuit_open:
            if self._should_reset_circuit():
                self._reset_circuit()
            else:
                logger.warning("Circuit breaker open, skipping execution")
                return False, None
        
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return True, result
            
        except Exception as e:
            self._record_failure()
            return False, None
    
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._circuit_open and self._should_reset_circuit():
            self._reset_circuit()
        return self._circuit_open
    
    def _record_success(self):
        """Record successful execution."""
        self._consecutive_failures = 0
        self._total_successes += 1
        
        # Close circuit on success
        if self._circuit_open:
            self._reset_circuit()
    
    def _record_failure(self):
        """Record failed execution."""
        self._consecutive_failures += 1
        self._total_failures += 1
        
        # Open circuit if threshold reached
        if self._consecutive_failures >= self.max_consecutive_failures:
            self._open_circuit()
    
    def _open_circuit(self):
        """Open the circuit breaker."""
        self._circuit_open = True
        self._circuit_opened_at = time.time()
        logger.error(f"Circuit breaker opened after {self._consecutive_failures} consecutive failures")
    
    def _reset_circuit(self):
        """Reset the circuit breaker."""
        self._circuit_open = False
        self._consecutive_failures = 0
        self._circuit_opened_at = None
        logger.info("Circuit breaker reset")
    
    def _should_reset_circuit(self) -> bool:
        """Check if circuit should be reset."""
        if not self._circuit_opened_at:
            return True
        
        elapsed = time.time() - self._circuit_opened_at
        return elapsed >= self.circuit_reset_seconds
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "circuit_open": self._circuit_open,
            "consecutive_failures": self._consecutive_failures,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "circuit_opened_at": self._circuit_opened_at
        }
