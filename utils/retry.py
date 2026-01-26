"""Retry utilities with exponential backoff."""
import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar, cast

T = TypeVar('T')

class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception

async def async_retry(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: The async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each attempt
        jitter: Whether to add random jitter to the delay
        exceptions: Tuple of exceptions to catch and retry on
        logger: Optional logger for retry attempts
        
    Returns:
        The result of the function call if successful
        
    Raises:
        RetryError: If all retry attempts are exhausted
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
                
        except exceptions as e:
            last_exception = e
            if attempt == max_retries:
                break
                
            # Calculate next delay with exponential backoff and jitter
            delay = min(delay * backoff_factor, max_delay)
            if jitter:
                delay = random.uniform(0, delay)
            
            if logger:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {str(e)[:200]}. "
                    f"Retrying in {delay:.2f}s..."
                )
            
            await asyncio.sleep(delay)
    
    error_msg = f"All {max_retries} retry attempts failed"
    if logger:
        logger.error(f"{error_msg}. Last error: {str(last_exception)}")
    
    raise RetryError(error_msg, last_exception)

def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[Type[Exception], ...] = (Exception,)
    
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each attempt
        jitter: Whether to add random jitter to the delay
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            return await async_retry(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor,
                jitter=jitter,
                exceptions=exceptions,
                logger=logging.getLogger(func.__module__)
            )
            
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if max_retries > 0:
                    return cast(T, async_retry(
                        lambda: func(*args, **kwargs),
                        max_retries=max_retries,
                        initial_delay=initial_delay,
                        max_delay=max_delay,
                        backoff_factor=backoff_factor,
                        jitter=jitter,
                        exceptions=exceptions,
                        logger=logging.getLogger(func.__module__)
                    ))
                raise
                
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
        
    return decorator
