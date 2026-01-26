"""
Health check base classes for the trading system.

This module provides standardized health checking patterns used throughout
the codebase to ensure consistent monitoring and reporting across all components.
"""

import asyncio
import logging
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

# Import HealthStatus directly from utils to avoid circular imports
try:
    from utils.health_check import HealthStatus
except ImportError:
    # Fallback for when utils.health_check is not available
    from dataclasses import dataclass
    from typing import Any, Dict
    
    @dataclass
    class HealthStatus:
        component: str
        status: bool
        message: str = ""
        timestamp: Optional[datetime] = None
        metrics: Dict[str, Any] = None

logger = logging.getLogger(__name__)


class HealthCheckable:
    """
    Base class for components that require health checking.
    
    This class provides a standardized interface and common functionality
    for health checking across all system components. Subclasses should
    implement the `_perform_health_check` method to provide component-specific
    health validation logic.
    
    Features:
    - Standardized health check interface
    - Configurable health check intervals
    - Health status caching with configurable TTL
    - Detailed health metrics collection
    - Asynchronous health check execution
    - Integration with system monitoring
    
    Usage:
        class MyComponent(HealthCheckable):
            async def _perform_health_check(self) -> HealthStatus:
                # Component-specific health check logic
                try:
                    # Check component functionality
                    return HealthStatus(
                        component=self.name,
                        status=True,
                        message="Component is healthy"
                    )
                except Exception as e:
                    logger.error(f"Health check failed: {e}")
                    return HealthStatus(
                        component=self.name,
                        status=False,
                        message=f"Health check failed: {str(e)}"
                    )
    """
    
    def __init__(self, name: str, check_interval: int = 60, cache_ttl: int = 30):
        """
        Initialize the health checkable component.
        
        Args:
            name: Human-readable name for this component
            check_interval: How often to perform health checks (seconds)
            cache_ttl: How long to cache health check results (seconds)
        """
        self.name = name
        self.check_interval = check_interval
        self.cache_ttl = cache_ttl
        self._last_check: Optional[datetime] = None
        self._cached_status: Optional[HealthStatus] = None
        self._health_metrics: Dict[str, Any] = {}
        self._health_history: List[Dict[str, Any]] = []
        self._max_history_size = 100
        
        logger.info(f"Initialized health checkable component: {self.name}")
    
    async def health_check(self) -> HealthStatus:
        """
        Perform a comprehensive health check.
        
        This method provides caching to avoid excessive health check calls,
        while ensuring that cached results are refreshed when stale.
        
        Returns:
            HealthStatus indicating the current health of the component
        """
        current_time = datetime.now(timezone.utc)
        
        # Check if we have a recent cached result
        if (self._last_check and self._cached_status and 
            (current_time - self._last_check).total_seconds() < self.cache_ttl):
            logger.debug(f"Using cached health status for {self.name}")
            return self._cached_status
        
        # Perform fresh health check
        try:
            logger.debug(f"Performing health check for {self.name}")
            status = await self._perform_health_check()
            
            # Cache the result
            self._last_check = current_time
            self._cached_status = status
            
            # Update health metrics
            self._update_health_metrics(status)
            
            # Log the result
            if status.status:
                logger.debug(f"Health check passed for {self.name}")
            else:
                logger.warning(f"Health check failed for {self.name}: {status.message}")
            
            return status
            
        except Exception as e:
            logger.error(f"Health check error for {self.name}: {e}", exc_info=True)
            
            error_status = HealthStatus(
                component=self.name,
                status=False,
                message=f"Health check error: {str(e)}"
            )
            
            # Cache the error status briefly
            self._last_check = current_time
            self._cached_status = error_status
            
            return error_status
    
    @abstractmethod
    async def _perform_health_check(self) -> HealthStatus:
        """
        Perform the actual health check logic.
        
        Subclasses must implement this method to provide component-specific
        health validation. This method should:
        1. Check component-specific functionality
        2. Validate required resources/dependencies
        3. Return appropriate HealthStatus with detailed information
        4. Raise exceptions for critical failures if needed
        
        Returns:
            HealthStatus with component health information
            
        Raises:
            Exception: For critical health check failures
        """
        pass
    
    def _update_health_metrics(self, status: HealthStatus) -> None:
        """
        Update health metrics with the latest check result.
        
        Args:
            status: The health status result from the latest check
        """
        metrics_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status.status,
            "message": status.message,
            "metrics": status.metrics.copy() if status.metrics else {}
        }
        
        # Add to history
        self._health_history.append(metrics_entry)
        
        # Maintain history size limit
        if len(self._health_history) > self._max_history_size:
            self._health_history.pop(0)
        
        # Update current metrics
        self._health_metrics.update(status.metrics or {})
        self._health_metrics["last_check"] = metrics_entry["timestamp"]
        self._health_metrics["last_status"] = status.status
        self._health_metrics["last_message"] = status.message
    
    async def force_refresh(self) -> HealthStatus:
        """
        Force a fresh health check without considering cache.
        
        Returns:
            HealthStatus from the fresh health check
        """
        # Clear cache
        self._last_check = None
        self._cached_status = None
        
        # Perform fresh check
        return await self.health_check()
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the component's health status.
        
        Returns:
            Dictionary containing health summary information
        """
        if not self._health_history:
            return {
                "component": self.name,
                "status": "unknown",
                "message": "No health checks performed yet"
            }
        
        latest = self._health_history[-1]
        
        return {
            "component": self.name,
            "status": "healthy" if latest["status"] else "unhealthy",
            "message": latest["message"],
            "last_check": latest["timestamp"],
            "metrics": self._health_metrics.copy(),
            "check_interval": self.check_interval,
            "cache_ttl": self.cache_ttl
        }
    
    def get_health_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the recent health check history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of health check history entries
        """
        return self._health_history[-limit:]
    
    def is_healthy(self) -> bool:
        """
        Check if the component is currently healthy based on cached status.
        
        Returns:
            True if the component appears healthy, False otherwise
        """
        if not self._cached_status:
            return False
        return self._cached_status.status
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get the current health metrics for this component.
        
        Returns:
            Dictionary containing health metrics
        """
        return self._health_metrics.copy()
    
    async def batch_health_check(self, components: List['HealthCheckable']) -> Dict[str, HealthStatus]:
        """
        Perform health checks on multiple components in parallel.
        
        Args:
            components: List of HealthCheckable components to check
            
        Returns:
            Dictionary mapping component names to their HealthStatus results
        """
        if not components:
            return {}
        
        logger.info(f"Performing batch health check on {len(components)} components")
        
        # Create tasks for parallel execution
        tasks = []
        for component in components:
            if hasattr(component, 'health_check') and callable(component.health_check):
                tasks.append(component.health_check())
            else:
                # Handle components that might not have health_check method
                logger.warning(f"Component {getattr(component, 'name', 'unknown')} does not have health_check method")
                tasks.append(asyncio.create_task(asyncio.sleep(0)))  # Dummy task
        
        # Execute all health checks in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            status_map = {}
            for i, result in enumerate(results):
                component = components[i]
                component_name = getattr(component, 'name', f'component_{i}')
                
                if isinstance(result, Exception):
                    status_map[component_name] = HealthStatus(
                        component=component_name,
                        status=False,
                        message=f"Health check exception: {str(result)}"
                    )
                else:
                    status_map[component_name] = result
            
            return status_map
            
        except Exception as e:
            logger.error(f"Batch health check failed: {e}", exc_info=True)
            raise


class AsyncHealthCheckable(HealthCheckable):
    """
    Extended health checkable class with additional async features.
    
    This class extends HealthCheckable with features specifically useful
    for async components that may need background health monitoring
    and periodic health checks.
    """
    
    def __init__(self, name: str, check_interval: int = 60, cache_ttl: int = 30, 
                 auto_monitor: bool = False):
        """
        Initialize the async health checkable component.
        
        Args:
            name: Human-readable name for this component
            check_interval: How often to perform health checks (seconds)
            cache_ttl: How long to cache health check results (seconds)
            auto_monitor: Whether to start automatic background monitoring
        """
        super().__init__(name, check_interval, cache_ttl)
        self.auto_monitor = auto_monitor
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
        if auto_monitor:
            self.start_monitoring()
    
    async def _background_monitor(self) -> None:
        """
        Background task for automatic health monitoring.
        
        This method runs in the background and performs periodic health checks
        to ensure the component remains healthy.
        """
        logger.info(f"Starting background health monitoring for {self.name}")
        self._is_monitoring = True
        
        while self._is_monitoring:
            try:
                await asyncio.sleep(self.check_interval)
                
                if self._is_monitoring:  # Check again to avoid race conditions
                    await self.health_check()
                    logger.debug(f"Background health check completed for {self.name}")
                    
            except asyncio.CancelledError:
                logger.info(f"Background health monitoring cancelled for {self.name}")
                break
            except Exception as e:
                logger.error(f"Background health monitoring error for {self.name}: {e}", exc_info=True)
                # Continue monitoring despite errors
                await asyncio.sleep(min(self.check_interval, 30))  # Shorter retry interval on error
        
        logger.info(f"Background health monitoring stopped for {self.name}")
        self._is_monitoring = False
    
    def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if not self._is_monitoring:
            self._monitoring_task = asyncio.create_task(self._background_monitor())
            logger.info(f"Started background monitoring for {self.name}")
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._is_monitoring:
            self._is_monitoring = False
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
            logger.info(f"Stopped background monitoring for {self.name}")
    
    async def wait_for_healthy(self, timeout: float = 30.0) -> bool:
        """
        Wait for the component to become healthy.
        
        Args:
            timeout: Maximum time to wait (seconds)
            
        Returns:
            True if component became healthy within timeout, False otherwise
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.is_healthy():
                return True
            await asyncio.sleep(1.0)  # Check every second
        
        return False

