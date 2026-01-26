"""
Elite Circuit Breaker Implementation
====================================
Production-grade circuit breaker for fault tolerance.
"""

import asyncio
import functools
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking calls
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5      # Number of failures to open circuit
    timeout: int = 60              # Seconds to wait before half-open
    success_threshold: int = 3     # Successes needed to close from half-open
    expected_exception: type = Exception  # Exception type to count as failure

class CircuitBreaker:
    """
    Elite production-grade circuit breaker implementation.
    
    Features:
    - Configurable failure thresholds
    - Automatic recovery detection
    - Thread-safe operations
    - Metrics and observability
    - Graceful degradation
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = threading.RLock()
        
        # Metrics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.blocked_calls = 0
        self.state_changes = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or raises CircuitBreakerOpenError
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            Exception: Original function exceptions (if circuit is closed/half-open)
        """
        with self._lock:
            self.total_calls += 1
            
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.blocked_calls += 1
                    raise CircuitBreakerOpenError("Circuit breaker is OPEN")
            
            # Execute function
            try:
                result = func(*args, **kwargs)
                self._record_success()
                return result
                
            except self.config.expected_exception as e:
                self._record_failure()
                raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self.last_failure_time:
            return False
        
        elapsed = datetime.now() - self.last_failure_time
        return elapsed.total_seconds() >= self.config.timeout

    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN state"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.state_changes += 1
        logger.info("Circuit breaker transitioning to HALF_OPEN state")

    def _record_success(self):
        """Record successful function call"""
        self.successful_calls += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)

    def _record_failure(self):
        """Record failed function call"""
        self.failed_calls += 1
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()

    def _transition_to_open(self):
        """Transition to OPEN state"""
        self.state = CircuitState.OPEN
        self.state_changes += 1
        logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")

    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.state_changes += 1
        logger.info("Circuit breaker CLOSED - system recovered")

    def get_state(self) -> dict:
        """Get current circuit breaker state and metrics"""
        with self._lock:
            return {
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'total_calls': self.total_calls,
                'successful_calls': self.successful_calls,
                'failed_calls': self.failed_calls,
                'blocked_calls': self.blocked_calls,
                'state_changes': self.state_changes,
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
                'success_rate': (
                    self.successful_calls / max(self.total_calls, 1)
                ),
                'failure_rate': (
                    self.failed_calls / max(self.total_calls, 1)
                )
            }

    def reset(self):
        """Manually reset circuit breaker to CLOSED state"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.state_changes += 1
            logger.info("Circuit breaker manually reset to CLOSED state")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreakerDecorator:
    """Decorator for easy circuit breaker integration"""

    def __init__(self, circuit_breaker: CircuitBreaker):
        self.circuit_breaker = circuit_breaker

    def __call__(self, func: Callable) -> Callable:
        """Decorate function with circuit breaker"""
        def wrapper(*args, **kwargs):
            return self.circuit_breaker.call(func, *args, **kwargs)
        return wrapper

    def __get__(self, obj, objtype=None):
        """Support instance methods"""
        if obj is None:
            return self
        return functools.partial(self.__call__, obj)


def circuit_breaker(failure_threshold: int = 5, timeout: int = 60, 
                   success_threshold: int = 3, expected_exception: type = Exception):
    """
    Decorator for automatic circuit breaker protection.
    
    Args:
        failure_threshold: Number of failures to open circuit
        timeout: Seconds to wait before attempting reset
        success_threshold: Successes needed to close circuit
        expected_exception: Exception type to count as failure
    """
    def decorator(func: Callable) -> Callable:
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout=timeout,
            success_threshold=success_threshold,
            expected_exception=expected_exception
        )
        circuit_breaker_instance = CircuitBreaker(config)
        decorator_instance = CircuitBreakerDecorator(circuit_breaker_instance)
        return decorator_instance(func)
    return decorator