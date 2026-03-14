"""
Health check utilities for monitoring system components.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import (Any, Awaitable, Callable, Dict, List, Optional, Tuple,
                    TypeVar, Union)

# Type variable for the decorated function
F = TypeVar('F', bound=Callable[..., Any])

# Type alias for health check return types
HealthCheckResult = Union[bool, Tuple[bool, str], Dict[str, Any], 'HealthStatus', Awaitable[Any]]

# Set up logging
logger = logging.getLogger(__name__)

def standard_health_check(component_name: str = None):
    """
    Decorator to standardize health check methods.
    
    Ensures all health checks return a HealthStatus object with consistent structure.
    Handles both sync and async health check functions.
    
    Args:
        component_name: Name of the component being checked. If None, uses function name.
    """
    def decorator(func: F) -> Callable[..., Awaitable['HealthStatus']]:
        component = component_name or func.__name__.lstrip('check_').replace('_', ' ').title()
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> 'HealthStatus':
            try:
                # Call the original function
                result = func(*args, **kwargs)
                
                # Handle async functions
                if hasattr(result, '__await__'):
                    result = await result
                
                # Convert result to HealthStatus
                if isinstance(result, HealthStatus):
                    return result
                elif isinstance(result, bool):
                    return HealthStatus(
                        component=component,
                        status=result,
                        message="Health check completed" if result else "Health check failed"
                    )
                elif isinstance(result, tuple) and len(result) == 2:
                    return HealthStatus(
                        component=component,
                        status=result[0],
                        message=str(result[1]),
                        metrics=result[2] if len(result) > 2 else {}
                    )
                elif isinstance(result, dict):
                    return HealthStatus(
                        component=component,
                        status=result.get('status', False),
                        message=result.get('message', ''),
                        metrics=result.get('metrics', {})
                    )
                else:
                    return HealthStatus(
                        component=component,
                        status=bool(result),
                        message=f"Unexpected return type: {type(result).__name__}"
                    )
                    
            except Exception as e:
                return HealthStatus(
                    component=component,
                    status=False,
                    message=f"Health check error: {str(e)}",
                    metrics={"error": str(type(e).__name__)}
                )
        
        return wrapper
    return decorator

@dataclass
class HealthStatus:
    """Represents the health status of a component."""
    component: str
    status: bool
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: Dict[str, Any] = field(default_factory=dict)

class HealthMonitor:
    """Monitors the health of system components."""
    
    def __init__(self):
        self.components: Dict[str, callable] = {}
        self.status_history: Dict[str, List[HealthStatus]] = {}
        self.max_history = 100  # Keep last 100 status updates per component
    
    def register_component(self, name: str, check_func: callable) -> None:
        """Register a component and its health check function."""
        self.components[name] = check_func
        self.status_history[name] = []
    
    async def check_component(self, name: str) -> HealthStatus:
        """Check the health of a single component."""
        if name not in self.components:
            return HealthStatus(
                component=name,
                status=False,
                message=f"Component '{name}' not registered"
            )
        
        try:
            # Run the health check function
            result = await self.components[name]()
            
            # Handle different return types
            if isinstance(result, HealthStatus):
                status = result
            elif isinstance(result, bool):
                status = HealthStatus(
                    component=name,
                    status=result,
                    message="Health check completed"
                )
            elif isinstance(result, tuple) and len(result) == 2:
                status = HealthStatus(
                    component=name,
                    status=result[0],
                    message=str(result[1])
                )
            else:
                status = HealthStatus(
                    component=name,
                    status=False,
                    message=f"Invalid health check return type: {type(result)}"
                )
            
        except Exception as e:
            logger.error(f"Health check failed for {name}: {str(e)}", exc_info=True)
            status = HealthStatus(
                component=name,
                status=False,
                message=f"Health check error: {str(e)}"
            )
        
        # Store the status in history
        if name in self.status_history:
            self.status_history[name].append(status)
            # Trim history if needed
            if len(self.status_history[name]) > self.max_history:
                self.status_history[name].pop(0)
        
        return status
    
    async def check_all(self) -> Dict[str, HealthStatus]:
        """Check the health of all registered components."""
        results = {}
        for name in self.components:
            results[name] = await self.check_component(name)
        return results
    
    def get_component_status(self, name: str) -> Optional[HealthStatus]:
        """Get the latest status of a component."""
        if not self.status_history.get(name):
            return None
        return self.status_history[name][-1]
    
    def get_uptime(self, name: str, period_hours: int = 24) -> float:
        """Calculate the uptime percentage for a component over the specified period."""
        if name not in self.status_history or not self.status_history[name]:
            return 0.0
        
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=period_hours)
        
        # Filter statuses within the period
        recent_statuses = [
            status for status in self.status_history[name]
            if status.timestamp >= cutoff
        ]
        
        if not recent_statuses:
            return 0.0
        
        # Calculate uptime percentage
        successful_checks = sum(1 for s in recent_statuses if s.status)
        return (successful_checks / len(recent_statuses)) * 100

# Global health monitor instance
health_monitor = HealthMonitor()

# Common health check functions
async def check_database_connection(db_manager) -> HealthStatus:
    """Check if the database is accessible."""
    try:
        # Try a simple query to check database connectivity
        result = await db_manager.execute("SELECT 1")
        if result and result[0][0] == 1:
            return HealthStatus(
                component="database",
                status=True,
                message="Database connection successful"
            )
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    return HealthStatus(
        component="database",
        status=False,
        message="Failed to connect to database"
    )

async def check_network_connectivity(network_manager) -> HealthStatus:
    """Check if network connections are working."""
    try:
        # Try to get the latest block from a network
        block = await network_manager.get_latest_block()
        if block:
            return HealthStatus(
                component="network",
                status=True,
                message=f"Network connection successful (block: {block.number})",
                metrics={"block_number": block.number}
            )
    except Exception as e:
        logger.error(f"Network health check failed: {e}")
    
    return HealthStatus(
        component="network",
        status=False,
        message="Failed to connect to network"
    )

async def check_disk_space(min_gb: float = 1.0) -> HealthStatus:
    """Check if there's enough disk space."""
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (2**30)  # Convert to GB
        
        status = free_gb >= min_gb
        return HealthStatus(
            component="disk_space",
            status=status,
            message=f"Free disk space: {free_gb:.2f}GB",
            metrics={"free_gb": free_gb, "min_required_gb": min_gb}
        )
    except Exception as e:
        logger.error(f"Disk space check failed: {e}")
        return HealthStatus(
            component="disk_space",
            status=False,
            message=f"Failed to check disk space: {e}"
        )

# Example usage:
# health_monitor.register_component("database", lambda: check_database_connection(db_manager))
# health_monitor.register_component("network", lambda: check_network_connectivity(network_manager))
# health_monitor.register_component("disk", lambda: check_disk_space(min_gb=5.0))
