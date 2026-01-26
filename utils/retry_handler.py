"""
Retry Handler with Exponential Backoff
------------------------------------
Robust retry logic for transient failures with configurable backoff strategies.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, List, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0   # Maximum delay in seconds
    exponential_base: float = 2.0  # Multiplier for exponential backoff
    jitter: bool = True  # Add random jitter to prevent thundering herd
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    
class RetryHandler:
    """
    Handles retry logic with exponential backoff and jitter.
    
    Features:
    - Exponential backoff with configurable base
    - Random jitter to prevent thundering herd
    - Configurable retryable exceptions
    - Detailed logging and metrics
    - Async and sync support
    """
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.total_retries = 0
        self.successful_retries = 0
        self.failed_retries = 0
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt using exponential backoff.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay = base_delay * (exponential_base ^ attempt)
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter if enabled
        if self.config.jitter:
            # Add up to 25% random jitter
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        # Ensure non-negative delay
        return max(0, delay)
    
    async def execute_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic (async version).
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                self.total_retries += 1
                
                if attempt > 0:
                    delay = self.calculate_delay(attempt)
                    logger.info(f"Retrying {func.__name__} (attempt {attempt + 1}/{self.config.max_attempts}) after {delay:.2f}s")
                    await asyncio.sleep(delay)
                
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self.successful_retries += 1
                    logger.info(f"Retry successful for {func.__name__} on attempt {attempt + 1}")
                
                return result
                
            except self.config.retryable_exceptions as e:
                last_exception = e
                
                if attempt < self.config.max_attempts - 1:
                    delay = self.calculate_delay(attempt + 1)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.failed_retries += 1
                    logger.error(
                        f"All {self.config.max_attempts} attempts failed for {func.__name__}. "
                        f"Last error: {e}"
                    )
        
        # Re-raise the last exception
        raise last_exception
    
    def execute_sync(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic (sync version).
        
        Args:
            func: Sync function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        import time
        
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                self.total_retries += 1
                
                if attempt > 0:
                    delay = self.calculate_delay(attempt)
                    logger.info(f"Retrying {func.__name__} (attempt {attempt + 1}/{self.config.max_attempts}) after {delay:.2f}s")
                    time.sleep(delay)
                
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.successful_retries += 1
                    logger.info(f"Retry successful for {func.__name__} on attempt {attempt + 1}")
                
                return result
                
            except self.config.retryable_exceptions as e:
                last_exception = e
                
                if attempt < self.config.max_attempts - 1:
                    delay = self.calculate_delay(attempt + 1)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    self.failed_retries += 1
                    logger.error(
                        f"All {self.config.max_attempts} attempts failed for {func.__name__}. "
                        f"Last error: {e}"
                    )
        
        # Re-raise the last exception
        raise last_exception
    
    def get_metrics(self) -> dict:
        """Get retry handler metrics."""
        return {
            'total_retries': self.total_retries,
            'successful_retries': self.successful_retries,
            'failed_retries': self.failed_retries,
            'success_rate': (
                self.successful_retries / max(self.total_retries, 1)
            ),
            'config': {
                'max_attempts': self.config.max_attempts,
                'base_delay': self.config.base_delay,
                'max_delay': self.config.max_delay,
                'exponential_base': self.config.exponential_base,
                'jitter': self.config.jitter
            }
        }

def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for automatic async retry with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Multiplier for exponential backoff
        jitter: Add random jitter to prevent thundering herd
        retryable_exceptions: Tuple of exception types to retry on
    """
    def decorator(func: Callable) -> Callable:
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            retryable_exceptions=retryable_exceptions
        )
        retry_handler = RetryHandler(config)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_handler.execute_async(func, *args, **kwargs)
        
        # Attach retry handler for metrics access
        wrapper._retry_handler = retry_handler
        
        return wrapper
    return decorator

def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for automatic sync retry with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Multiplier for exponential backoff
        jitter: Add random jitter to prevent thundering herd
        retryable_exceptions: Tuple of exception types to retry on
    """
    def decorator(func: Callable) -> Callable:
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            retryable_exceptions=retryable_exceptions
        )
        retry_handler = RetryHandler(config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_handler.execute_sync(func, *args, **kwargs)
        
        # Attach retry handler for metrics access
        wrapper._retry_handler = retry_handler
        
        return wrapper
    return decorator

# Network-specific retry configurations
NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        OSError,
        # Add specific network exceptions as needed
    )
)

API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        # Add API-specific exceptions
    )
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.1,
    max_delay=5.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(
        ConnectionError,
        TimeoutError,
        # Add database-specific exceptions
    )
)
