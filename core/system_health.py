from typing import Any, Dict, List

"""System-wide health monitoring and aggregation."""
from typing import Any, Dict, List

from .health_check import HealthMonitor, HealthStatus, standard_health_check


class SystemHealth:
    """Aggregates health checks across all components."""
    
    def __init__(self, components: List[Any]):
        self.components = components
        self.health_monitor = HealthMonitor()
        
        # Register all components
        for component in components:
            name = component.__class__.__name__
            if hasattr(component, 'health_check'):
                self.health_monitor.register_component(name, component.health_check)
    
    @standard_health_check("System Health")
    async def overall_health(self) -> HealthStatus:
        """Get overall system health status."""
        results = await self.health_monitor.check_all()
        
        # Check if any critical components are unhealthy
        critical_components = [c for c in self.components if getattr(c, 'CRITICAL', False)]
        unhealthy_critical = [
            name for name, status in results.items() 
            if not status.status and name in [c.__class__.__name__ for c in critical_components]
        ]
        
        is_healthy = all(status.status for status in results.values())
        is_degraded = bool(unhealthy_critical)
        
        return HealthStatus(
            component="System",
            status=is_healthy and not is_degraded,
            message=(
                "All systems operational" if is_healthy and not is_degraded
                else "System degraded" if is_degraded
                else "System unhealthy"
            ),
            metrics={
                "status": (
                    "healthy" if is_healthy and not is_degraded
                    else "degraded" if is_degraded
                    else "unhealthy"
                ),
                "healthy_components": sum(1 for s in results.values() if s.status),
                "total_components": len(results),
                "unhealthy_critical": unhealthy_critical,
                "components": {
                    name: {
                        "status": "healthy" if status.status else "unhealthy",
                        "message": status.message
                    }
                    for name, status in results.items()
                }
            }
        )
