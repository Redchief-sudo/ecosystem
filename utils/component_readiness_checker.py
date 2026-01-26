"""
Elite Component Readiness Checker
---------------------------------
Production-grade health monitoring and readiness verification system.
"""

import asyncio
import logging
import statistics
import time
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    """Component operational status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPED = "stopped"


class HealthCheckType(Enum):
    """Types of health checks."""
    LIVENESS = "liveness"  # Is component alive?
    READINESS = "readiness"  # Is component ready to serve?
    STARTUP = "startup"  # Has component started successfully?
    DEEP = "deep"  # Comprehensive check with dependencies


@dataclass
class ComponentMetrics:
    """Metrics for a component."""
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    uptime_start: Optional[datetime] = None
    total_checks: int = 0
    
    def record_success(self, response_time: float):
        """Record successful health check."""
        self.response_times.append(response_time)
        self.success_count += 1
        self.last_success = datetime.now()
        self.consecutive_failures = 0
        self.total_checks += 1
        
        if not self.uptime_start:
            self.uptime_start = datetime.now()
    
    def record_failure(self):
        """Record failed health check."""
        self.failure_count += 1
        self.last_failure = datetime.now()
        self.consecutive_failures += 1
        self.total_checks += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get metric statistics."""
        if not self.response_times:
            return {
                'avg_response_ms': 0,
                'p50_response_ms': 0,
                'p95_response_ms': 0,
                'p99_response_ms': 0
            }
        
        times = list(self.response_times)
        return {
            'avg_response_ms': statistics.mean(times),
            'p50_response_ms': statistics.median(times),
            'p95_response_ms': statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times),
            'p99_response_ms': statistics.quantiles(times, n=100)[98] if len(times) > 100 else max(times),
            'min_response_ms': min(times),
            'max_response_ms': max(times),
            'success_rate': self.success_count / max(1, self.total_checks),
            'total_checks': self.total_checks,
            'consecutive_failures': self.consecutive_failures
        }


@dataclass
class ReadinessResult:
    """Result of a component readiness check."""
    component_name: str
    component_type: str
    status: ComponentStatus
    is_ready: bool
    response_time_ms: float
    check_type: HealthCheckType
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'component_name': self.component_name,
            'component_type': self.component_type,
            'status': self.status.value,
            'is_ready': self.is_ready,
            'response_time_ms': self.response_time_ms,
            'check_type': self.check_type.value,
            'error_message': self.error_message,
            'details': self.details,
            'dependencies': self.dependencies,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class SystemHealthReport:
    """Comprehensive system health report."""
    overall_status: ComponentStatus
    all_ready: bool
    components: List[ReadinessResult]
    total_components: int
    healthy_components: int
    degraded_components: int
    unhealthy_components: int
    avg_response_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'overall_status': self.overall_status.value,
            'all_ready': self.all_ready,
            'total_components': self.total_components,
            'healthy_components': self.healthy_components,
            'degraded_components': self.degraded_components,
            'unhealthy_components': self.unhealthy_components,
            'avg_response_time': self.avg_response_time,
            'components': [c.to_dict() for c in self.components],
            'timestamp': self.timestamp.isoformat()
        }


class CircuitBreaker:
    """Circuit breaker for failing components."""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half_open
    
    def record_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
    
    def can_attempt(self) -> bool:
        """Check if call can be attempted."""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed > self.timeout_seconds:
                    self.state = "half_open"
                    return True
            return False
        
        # half_open state
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class EliteComponentReadinessChecker:
    """
    Production-grade component readiness and health monitoring system.
    
    Features:
    - Multiple health check types (liveness, readiness, startup, deep)
    - Dependency chain verification
    - Circuit breakers for failing components
    - Comprehensive metrics and statistics
    - Smart caching with TTL
    - Parallel health checks
    - Automatic remediation triggers
    - Historical health tracking
    - Alert generation
    """
    
    def __init__(self, 
                 timeout_seconds: int = 10,
                 cache_ttl_seconds: int = 30,
                 enable_circuit_breaker: bool = True,
                 parallel_checks: bool = True):
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.parallel_checks = parallel_checks
        
        # Component tracking
        self.metrics: Dict[str, ComponentMetrics] = defaultdict(ComponentMetrics)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.enable_circuit_breaker = enable_circuit_breaker
        
        # Caching
        self.check_cache: Dict[str, ReadinessResult] = {}
        self.last_check_time: Dict[str, datetime] = {}
        
        # Dependency graph
        self.dependencies: Dict[str, List[str]] = {}
        
        # Health check registry
        self.health_checks: Dict[str, Callable] = {}
        
        # Historical data
        self.health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Alerts
        self.active_alerts: Dict[str, List[Dict]] = defaultdict(list)
        
        logger.info("✅ Elite Component Readiness Checker initialized")
        logger.info(f"   Timeout: {timeout_seconds}s, Cache TTL: {cache_ttl_seconds}s")
    
    def register_component(self, 
                          name: str, 
                          health_check: Callable,
                          dependencies: Optional[List[str]] = None):
        """Register a component with its health check function."""
        self.health_checks[name] = health_check
        if dependencies:
            self.dependencies[name] = dependencies
        
        if self.enable_circuit_breaker:
            self.circuit_breakers[name] = CircuitBreaker()
        
        logger.info(f"📝 Registered component: {name}")
        if dependencies:
            logger.info(f"   Dependencies: {', '.join(dependencies)}")
    
    async def check_component(self,
                            name: str,
                            component: Any,
                            check_type: HealthCheckType = HealthCheckType.READINESS,
                            force_check: bool = False) -> ReadinessResult:
        """
        Check readiness of a single component.
        
        Args:
            name: Component name
            component: Component instance
            check_type: Type of health check to perform
            force_check: Bypass cache
            
        Returns:
            ReadinessResult with status and metrics
        """
        # Check cache first
        if not force_check and name in self.check_cache:
            last_check = self.last_check_time.get(name)
            if last_check and (datetime.now() - last_check).total_seconds() < self.cache_ttl_seconds:
                cached_result = self.check_cache[name]
                logger.debug(f"🔄 Using cached result for {name}")
                return cached_result
        
        # Check circuit breaker
        if self.enable_circuit_breaker and name in self.circuit_breakers:
            if not self.circuit_breakers[name].can_attempt():
                return ReadinessResult(
                    component_name=name,
                    component_type=type(component).__name__,
                    status=ComponentStatus.UNHEALTHY,
                    is_ready=False,
                    response_time_ms=0,
                    check_type=check_type,
                    error_message="Circuit breaker open",
                    details=self.circuit_breakers[name].get_status()
                )
        
        start_time = time.time()
        
        try:
            # Determine check method
            if name in self.health_checks:
                # Use registered health check
                check_func = self.health_checks[name]
                is_ready = await asyncio.wait_for(
                    check_func(component),
                    timeout=self.timeout_seconds
                )
            else:
                # Use component's built-in health check
                is_ready = await self._default_health_check(component, check_type)
            
            response_time = (time.time() - start_time) * 1000
            
            # Determine status
            if is_ready:
                status = ComponentStatus.HEALTHY
            else:
                status = ComponentStatus.DEGRADED
            
            # Create result
            result = ReadinessResult(
                component_name=name,
                component_type=type(component).__name__,
                status=status,
                is_ready=is_ready,
                response_time_ms=response_time,
                check_type=check_type,
                details=self._get_component_details(component)
            )
            
            # Update metrics
            self.metrics[name].record_success(response_time)
            if self.enable_circuit_breaker:
                self.circuit_breakers[name].record_success()
            
            # Cache result
            self.check_cache[name] = result
            self.last_check_time[name] = datetime.now()
            
            # Store in history
            self.health_history[name].append(result)
            
            # Clear alerts if component recovered
            if is_ready and name in self.active_alerts:
                del self.active_alerts[name]
            
            return result
            
        except asyncio.TimeoutError:
            response_time = self.timeout_seconds * 1000
            error_msg = f"Health check timed out after {self.timeout_seconds}s"
            
            result = ReadinessResult(
                component_name=name,
                component_type=type(component).__name__,
                status=ComponentStatus.UNHEALTHY,
                is_ready=False,
                response_time_ms=response_time,
                check_type=check_type,
                error_message=error_msg
            )
            
            self._handle_check_failure(name, result)
            return result
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            result = ReadinessResult(
                component_name=name,
                component_type=type(component).__name__,
                status=ComponentStatus.UNHEALTHY,
                is_ready=False,
                response_time_ms=response_time,
                check_type=check_type,
                error_message=error_msg,
                details={'traceback': traceback.format_exc()}
            )
            
            self._handle_check_failure(name, result)
            return result
    
    def _handle_check_failure(self, name: str, result: ReadinessResult):
        """Handle failed health check."""
        self.metrics[name].record_failure()
        
        if self.enable_circuit_breaker:
            self.circuit_breakers[name].record_failure()
        
        # Store in history
        self.health_history[name].append(result)
        
        # Generate alert
        alert = {
            'timestamp': datetime.now().isoformat(),
            'component': name,
            'error': result.error_message,
            'consecutive_failures': self.metrics[name].consecutive_failures
        }
        self.active_alerts[name].append(alert)
        
        # Log based on severity
        failures = self.metrics[name].consecutive_failures
        if failures == 1:
            logger.warning(f"⚠️  {name} health check failed: {result.error_message}")
        elif failures >= 3:
            logger.error(f"🚨 {name} has {failures} consecutive failures!")
    
    async def _default_health_check(self, component: Any, check_type: HealthCheckType) -> bool:
        """Default health check implementation."""
        # Try common health check methods
        for method_name in ['health_check', 'is_healthy', 'check_health', 'is_ready']:
            if hasattr(component, method_name):
                method = getattr(component, method_name)
                if asyncio.iscoroutinefunction(method):
                    return await method()
                else:
                    return method()
        
        # Check for session/connection
        if hasattr(component, '_session') and component._session:
            return not component._session.closed
        
        # Basic existence check
        return component is not None
    
    def _get_component_details(self, component: Any) -> Dict[str, Any]:
        """Extract relevant details from component."""
        details = {}
        
        # Common attributes to check
        attrs = ['status', 'state', 'is_connected', 'connection_state', 
                'active_tasks', 'queue_size', 'error_count']
        
        for attr in attrs:
            if hasattr(component, attr):
                value = getattr(component, attr)
                if not callable(value):
                    details[attr] = str(value)
        
        # Get metrics if available
        if hasattr(component, 'get_metrics'):
            try:
                metrics = component.get_metrics()
                if isinstance(metrics, dict):
                    details['metrics'] = metrics
            except:
                pass
        
        return details
    
    async def verify_all_components(self,
                                   components: Dict[str, Any],
                                   check_type: HealthCheckType = HealthCheckType.READINESS) -> SystemHealthReport:
        """
        Verify readiness of all components.
        
        Args:
            components: Dictionary of component_name -> component_instance
            check_type: Type of health check to perform
            
        Returns:
            SystemHealthReport with overall system health
        """
        logger.info(f"🔍 Starting {check_type.value} check for {len(components)} components...")
        
        start_time = time.time()
        
        if self.parallel_checks:
            # Run checks in parallel
            tasks = [
                self.check_component(name, comp, check_type)
                for name, comp in components.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    name = list(components.keys())[i]
                    logger.error(f"Exception checking {name}: {result}")
                    final_results.append(ReadinessResult(
                        component_name=name,
                        component_type="unknown",
                        status=ComponentStatus.UNHEALTHY,
                        is_ready=False,
                        response_time_ms=0,
                        check_type=check_type,
                        error_message=str(result)
                    ))
                else:
                    final_results.append(result)
        else:
            # Run checks sequentially
            final_results = []
            for name, comp in components.items():
                result = await self.check_component(name, comp, check_type)
                final_results.append(result)
        
        # Calculate statistics
        healthy = sum(1 for r in final_results if r.status == ComponentStatus.HEALTHY)
        degraded = sum(1 for r in final_results if r.status == ComponentStatus.DEGRADED)
        unhealthy = sum(1 for r in final_results if r.status == ComponentStatus.UNHEALTHY)
        
        all_ready = all(r.is_ready for r in final_results)
        avg_response = statistics.mean(r.response_time_ms for r in final_results) if final_results else 0
        
        # Determine overall status
        if unhealthy > 0:
            overall_status = ComponentStatus.UNHEALTHY
        elif degraded > 0:
            overall_status = ComponentStatus.DEGRADED
        elif healthy == len(final_results):
            overall_status = ComponentStatus.HEALTHY
        else:
            overall_status = ComponentStatus.UNKNOWN
        
        duration = (time.time() - start_time) * 1000
        
        # Create report
        report = SystemHealthReport(
            overall_status=overall_status,
            all_ready=all_ready,
            components=final_results,
            total_components=len(final_results),
            healthy_components=healthy,
            degraded_components=degraded,
            unhealthy_components=unhealthy,
            avg_response_time=avg_response
        )
        
        # Log summary
        status_emoji = "✅" if all_ready else "⚠️" if degraded > 0 else "🚨"
        logger.info(f"{status_emoji} Health check complete in {duration:.0f}ms:")
        logger.info(f"   Healthy: {healthy}/{len(final_results)}")
        if degraded > 0:
            logger.warning(f"   Degraded: {degraded}")
        if unhealthy > 0:
            logger.error(f"   Unhealthy: {unhealthy}")
        
        return report
    
    async def verify_with_dependencies(self,
                                      components: Dict[str, Any],
                                      check_type: HealthCheckType = HealthCheckType.DEEP) -> SystemHealthReport:
        """Verify components respecting dependency order."""
        logger.info("🔗 Performing dependency-aware health checks...")
        
        # Build dependency order
        order = self._topological_sort(list(components.keys()))
        
        results = []
        for name in order:
            if name not in components:
                continue
            
            # Check dependencies first
            deps = self.dependencies.get(name, [])
            deps_ready = True
            
            for dep in deps:
                if dep in self.check_cache:
                    if not self.check_cache[dep].is_ready:
                        deps_ready = False
                        break
            
            # Check component
            if deps_ready:
                result = await self.check_component(name, components[name], check_type)
            else:
                result = ReadinessResult(
                    component_name=name,
                    component_type=type(components[name]).__name__,
                    status=ComponentStatus.UNHEALTHY,
                    is_ready=False,
                    response_time_ms=0,
                    check_type=check_type,
                    error_message="Dependencies not ready",
                    dependencies=deps
                )
            
            results.append(result)
        
        # Build report
        healthy = sum(1 for r in results if r.status == ComponentStatus.HEALTHY)
        degraded = sum(1 for r in results if r.status == ComponentStatus.DEGRADED)
        unhealthy = sum(1 for r in results if r.status == ComponentStatus.UNHEALTHY)
        
        overall_status = ComponentStatus.HEALTHY if healthy == len(results) else \
                        ComponentStatus.DEGRADED if degraded > 0 else \
                        ComponentStatus.UNHEALTHY
        
        return SystemHealthReport(
            overall_status=overall_status,
            all_ready=all(r.is_ready for r in results),
            components=results,
            total_components=len(results),
            healthy_components=healthy,
            degraded_components=degraded,
            unhealthy_components=unhealthy,
            avg_response_time=statistics.mean(r.response_time_ms for r in results) if results else 0
        )
    
    def _topological_sort(self, components: List[str]) -> List[str]:
        """Sort components by dependency order."""
        visited = set()
        stack = []
        
        def dfs(node):
            if node in visited:
                return
            visited.add(node)
            
            for dep in self.dependencies.get(node, []):
                if dep in components:
                    dfs(dep)
            
            stack.append(node)
        
        for comp in components:
            dfs(comp)
        
        return stack
    
    def get_component_metrics(self, name: str) -> Dict[str, Any]:
        """Get detailed metrics for a component."""
        if name not in self.metrics:
            return {}
        
        metrics = self.metrics[name]
        stats = metrics.get_stats()
        
        result = {
            'component': name,
            'statistics': stats,
            'last_success': metrics.last_success.isoformat() if metrics.last_success else None,
            'last_failure': metrics.last_failure.isoformat() if metrics.last_failure else None,
            'uptime_seconds': (datetime.now() - metrics.uptime_start).total_seconds() 
                             if metrics.uptime_start else 0
        }
        
        if self.enable_circuit_breaker and name in self.circuit_breakers:
            result['circuit_breaker'] = self.circuit_breakers[name].get_status()
        
        return result
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all components."""
        return {
            name: self.get_component_metrics(name)
            for name in self.metrics.keys()
        }
    
    def get_active_alerts(self) -> Dict[str, List[Dict]]:
        """Get all active alerts."""
        return dict(self.active_alerts)
    
    def clear_alerts(self, component: Optional[str] = None):
        """Clear alerts for a component or all components."""
        if component:
            if component in self.active_alerts:
                del self.active_alerts[component]
                logger.info(f"🔔 Cleared alerts for {component}")
        else:
            self.active_alerts.clear()
            logger.info("🔔 Cleared all alerts")
    
    def get_health_history(self, 
                          component: str, 
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get health check history for a component."""
        if component not in self.health_history:
            return []
        
        history = list(self.health_history[component])[-limit:]
        return [h.to_dict() for h in history]
    
    def export_health_report(self, filepath: str, report: SystemHealthReport):
        """Export health report to file."""
        import json
        
        with open(filepath, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        
        logger.info(f"📊 Health report exported to {filepath}")
    
    def reset_component(self, name: str):
        """Reset metrics and state for a component."""
        if name in self.metrics:
            self.metrics[name] = ComponentMetrics()
        if name in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker()
        if name in self.check_cache:
            del self.check_cache[name]
        if name in self.last_check_time:
            del self.last_check_time[name]
        if name in self.active_alerts:
            del self.active_alerts[name]
        
        logger.info(f"🔄 Reset state for {name}")
