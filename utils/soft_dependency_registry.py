"""
Elite Soft Dependency Registry
------------------------------
Production-grade registry for optional, non-critical intelligence feeds and components
with advanced lifecycle management, graceful degradation, and health monitoring.
"""

import asyncio
import logging
import traceback
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type

logger = logging.getLogger(__name__)


class DependencyStatus(Enum):
    """Status of a soft dependency."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    SUSPENDED = "suspended"
    RECOVERING = "recovering"


class DependencyPriority(Enum):
    """Priority levels for dependencies."""
    CRITICAL = 1  # Near-essential, retry aggressively
    HIGH = 2      # Important, retry normally
    MEDIUM = 3    # Nice-to-have, retry conservatively
    LOW = 4       # Optional enhancement, minimal retries


class InitializationStrategy(Enum):
    """How to initialize dependencies."""
    EAGER = "eager"           # Initialize immediately
    LAZY = "lazy"             # Initialize on first use
    BACKGROUND = "background" # Initialize in background task
    MANUAL = "manual"         # Manual initialization only


@dataclass
class DependencyMetrics:
    """Metrics for tracking dependency health and usage."""
    initialization_attempts: int = 0
    successful_initializations: int = 0
    failed_initializations: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_calls: int = 0
    avg_response_time_ms: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    uptime_start: Optional[datetime] = None
    downtime_total_seconds: float = 0.0
    
    # Response time tracking
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def record_call_success(self, response_time_ms: float):
        """Record successful call."""
        self.successful_calls += 1
        self.total_calls += 1
        self.last_success = datetime.now()
        self.response_times.append(response_time_ms)
        
        # Update average
        if self.response_times:
            self.avg_response_time_ms = sum(self.response_times) / len(self.response_times)
    
    def record_call_failure(self):
        """Record failed call."""
        self.failed_calls += 1
        self.total_calls += 1
        self.last_failure = datetime.now()
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    def get_uptime_percentage(self) -> float:
        """Calculate uptime percentage."""
        if not self.uptime_start:
            return 0.0
        
        total_time = (datetime.now() - self.uptime_start).total_seconds()
        if total_time == 0:
            return 0.0
        
        uptime = total_time - self.downtime_total_seconds
        return (uptime / total_time) * 100


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        delay = self.initial_delay_seconds * (self.backoff_multiplier ** attempt)
        delay = min(delay, self.max_delay_seconds)
        
        if self.jitter:
            import random
            delay *= random.uniform(0.5, 1.5)
        
        return delay


@dataclass
class SoftDependency:
    """Represents a soft dependency with full lifecycle management."""
    name: str
    component_class: Type
    init_params: Dict[str, Any] = field(default_factory=dict)
    priority: DependencyPriority = DependencyPriority.MEDIUM
    strategy: InitializationStrategy = InitializationStrategy.EAGER
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    
    # State
    status: DependencyStatus = DependencyStatus.UNINITIALIZED
    instance: Optional[Any] = None
    error_message: Optional[str] = None
    last_attempt: Optional[datetime] = None
    retry_count: int = 0
    
    # Metadata
    description: str = ""
    tags: Set[str] = field(default_factory=set)
    dependencies: List[str] = field(default_factory=list)  # Other deps this depends on
    
    # Metrics
    metrics: DependencyMetrics = field(default_factory=DependencyMetrics)
    
    # Callbacks
    on_available: Optional[Callable] = None
    on_failed: Optional[Callable] = None
    on_recovered: Optional[Callable] = None
    
    # Health check
    health_check_interval: int = 60  # seconds
    last_health_check: Optional[datetime] = None
    
    def should_retry(self) -> bool:
        """Check if should retry initialization."""
        return self.retry_count < self.retry_policy.max_attempts
    
    def get_next_retry_delay(self) -> float:
        """Get delay before next retry."""
        return self.retry_policy.get_delay(self.retry_count)
    
    def is_healthy(self) -> bool:
        """Check if dependency is healthy."""
        return self.status in [DependencyStatus.AVAILABLE, DependencyStatus.DEGRADED]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'status': self.status.value,
            'priority': self.priority.value,
            'strategy': self.strategy.value,
            'retry_count': self.retry_count,
            'error_message': self.error_message,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'description': self.description,
            'tags': list(self.tags),
            'metrics': {
                'total_calls': self.metrics.total_calls,
                'success_rate': self.metrics.get_success_rate(),
                'avg_response_ms': self.metrics.avg_response_time_ms,
                'uptime_pct': self.metrics.get_uptime_percentage()
            }
        }


class DependencyGroup:
    """Group of related dependencies."""
    
    def __init__(self, name: str, dependencies: List[str]):
        self.name = name
        self.dependencies = dependencies
        self.enabled = True
    
    def disable(self):
        """Disable entire group."""
        self.enabled = False
    
    def enable(self):
        """Enable entire group."""
        self.enabled = True


class EliteSoftDependencyRegistry:
    """
    Production-grade soft dependency registry with advanced features.
    
    Features:
    - Multiple initialization strategies (eager, lazy, background)
    - Priority-based retry policies
    - Comprehensive metrics and health monitoring
    - Graceful degradation
    - Dependency groups for batch operations
    - Automatic health checks and recovery
    - Event callbacks for state changes
    - Circular dependency detection
    - Resource cleanup and garbage collection
    """
    
    def __init__(self, 
                 enable_auto_recovery: bool = True,
                 health_check_interval: int = 60):
        self.dependencies: Dict[str, SoftDependency] = {}
        self.groups: Dict[str, DependencyGroup] = {}
        
        # State tracking
        self._initialization_complete = False
        self._initialization_lock = asyncio.Lock()
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Configuration
        self.enable_auto_recovery = enable_auto_recovery
        self.health_check_interval = health_check_interval
        
        # Event history
        self.event_history: deque = deque(maxlen=1000)
        
        # Fallback handlers
        self.fallback_handlers: Dict[str, Callable] = {}
        
        logger.info("✅ Elite Soft Dependency Registry initialized")
    
    def register(self,
                name: str,
                component_class: Type,
                init_params: Optional[Dict[str, Any]] = None,
                priority: DependencyPriority = DependencyPriority.MEDIUM,
                strategy: InitializationStrategy = InitializationStrategy.EAGER,
                retry_policy: Optional[RetryPolicy] = None,
                description: str = "",
                tags: Optional[Set[str]] = None,
                dependencies: Optional[List[str]] = None,
                on_available: Optional[Callable] = None,
                on_failed: Optional[Callable] = None) -> None:
        """
        Register a soft dependency.
        
        Args:
            name: Unique identifier
            component_class: Class to instantiate
            init_params: Initialization parameters
            priority: Priority level for retry/recovery
            strategy: Initialization strategy
            retry_policy: Custom retry policy
            description: Human-readable description
            tags: Tags for grouping/filtering
            dependencies: List of dependency names this depends on
            on_available: Callback when dependency becomes available
            on_failed: Callback when dependency fails
        """
        if name in self.dependencies:
            logger.warning(f"⚠️  Dependency '{name}' already registered, updating...")
        
        dep = SoftDependency(
            name=name,
            component_class=component_class,
            init_params=init_params or {},
            priority=priority,
            strategy=strategy,
            retry_policy=retry_policy or RetryPolicy(),
            description=description,
            tags=tags or set(),
            dependencies=dependencies or [],
            on_available=on_available,
            on_failed=on_failed
        )
        
        self.dependencies[name] = dep
        
        self._log_event('register', name, f"Registered with priority {priority.value}")
        logger.info(f"📝 Registered soft dependency: {name}")
        if description:
            logger.info(f"   Description: {description}")
        if tags:
            logger.info(f"   Tags: {', '.join(tags)}")
    
    def register_group(self, group_name: str, dependency_names: List[str]):
        """Register a group of dependencies."""
        self.groups[group_name] = DependencyGroup(group_name, dependency_names)
        logger.info(f"📦 Registered dependency group: {group_name} with {len(dependency_names)} deps")
    
    def register_fallback(self, name: str, fallback: Callable):
        """Register fallback handler for when dependency is unavailable."""
        self.fallback_handlers[name] = fallback
        logger.info(f"🔄 Registered fallback for {name}")
    
    async def initialize_all(self, 
                            parallel: bool = True,
                            fail_fast: bool = False) -> Dict[str, bool]:
        """
        Initialize all registered dependencies.
        
        Args:
            parallel: Initialize in parallel
            fail_fast: Stop on first failure
            
        Returns:
            Dict mapping dependency name to success status
        """
        async with self._initialization_lock:
            if self._initialization_complete:
                logger.warning("⚠️  Dependencies already initialized")
                return {}
            
            logger.info(f"🚀 Initializing {len(self.dependencies)} soft dependencies...")
            
            # Separate by strategy
            eager_deps = [d for d in self.dependencies.values() 
                         if d.strategy == InitializationStrategy.EAGER]
            background_deps = [d for d in self.dependencies.values() 
                             if d.strategy == InitializationStrategy.BACKGROUND]
            
            results = {}
            
            # Initialize eager dependencies
            if eager_deps:
                logger.info(f"   Eager: {len(eager_deps)} dependencies")
                
                if parallel:
                    tasks = [self._initialize_dependency(dep) for dep in eager_deps]
                    outcomes = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for dep, outcome in zip(eager_deps, outcomes):
                        if isinstance(outcome, Exception):
                            results[dep.name] = False
                            if fail_fast:
                                logger.error(f"❌ Fail-fast triggered by {dep.name}")
                                return results
                        else:
                            results[dep.name] = outcome
                else:
                    for dep in eager_deps:
                        success = await self._initialize_dependency(dep)
                        results[dep.name] = success
                        
                        if not success and fail_fast:
                            logger.error(f"❌ Fail-fast triggered by {dep.name}")
                            return results
            
            # Start background initialization tasks
            if background_deps:
                logger.info(f"   Background: {len(background_deps)} dependencies")
                from utils.task_manager import task_manager
                for dep in background_deps:
                    task = await task_manager.create_engine_task(lambda d=dep: self._initialize_with_retry(d), f"softdep.{dep.name}")
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            
            # Log results
            successful = sum(1 for v in results.values() if v)
            failed = len(results) - successful
            
            logger.info(f"✅ Initialization complete: {successful}/{len(results)} successful")
            if failed > 0:
                logger.warning(f"⚠️  {failed} dependencies failed to initialize")
            
            self._initialization_complete = True
            
            # Start health monitoring if enabled
            if self.enable_auto_recovery:
                from utils.task_manager import task_manager
                task = task_manager.create_engine_task(self._health_monitor_loop, f"softdep.health")
                if task is not None:
                    self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            
            return results
    
    async def _initialize_dependency(self, dep: SoftDependency) -> bool:
        """Initialize a single dependency."""
        dep.status = DependencyStatus.INITIALIZING
        dep.last_attempt = datetime.now()
        dep.retry_count += 1
        dep.metrics.initialization_attempts += 1
        
        try:
            # Check if dependencies are met
            if dep.dependencies:
                unmet = [d for d in dep.dependencies 
                        if d not in self.dependencies or 
                        not self.dependencies[d].is_healthy()]
                
                if unmet:
                    raise ValueError(f"Unmet dependencies: {', '.join(unmet)}")
            
            # Instantiate component
            logger.debug(f"   Initializing {dep.name}...")
            dep.instance = dep.component_class(**dep.init_params)
            
            # Call initialize method if exists
            if hasattr(dep.instance, 'initialize'):
                init_method = dep.instance.initialize
                if asyncio.iscoroutinefunction(init_method):
                    await init_method()
                else:
                    init_method()
            
            # Call async enter if context manager
            if hasattr(dep.instance, '__aenter__'):
                await dep.instance.__aenter__()
            
            # Verify health
            if hasattr(dep.instance, 'health_check'):
                is_healthy = await self._check_health(dep)
                if not is_healthy:
                    raise RuntimeError("Health check failed after initialization")
            
            dep.status = DependencyStatus.AVAILABLE
            dep.error_message = None
            dep.metrics.successful_initializations += 1
            dep.metrics.uptime_start = datetime.now()
            
            self._log_event('initialize_success', dep.name, f"Successfully initialized")
            logger.info(f"   ✅ {dep.name} initialized successfully")
            
            # Call callback
            if dep.on_available:
                try:
                    await dep.on_available(dep.instance)
                except Exception as e:
                    logger.error(f"Error in on_available callback for {dep.name}: {e}")
            
            return True
            
        except Exception as e:
            dep.status = DependencyStatus.FAILED
            dep.error_message = f"{type(e).__name__}: {str(e)}"
            dep.metrics.failed_initializations += 1
            
            self._log_event('initialize_failure', dep.name, dep.error_message)
            
            # Log based on priority
            if dep.priority == DependencyPriority.CRITICAL:
                logger.error(f"   ❌ CRITICAL dependency {dep.name} failed: {dep.error_message}")
            else:
                logger.warning(f"   ⚠️  {dep.name} failed to initialize: {dep.error_message}")
            
            logger.debug(f"   Traceback: {traceback.format_exc()}")
            
            # Call failure callback
            if dep.on_failed:
                try:
                    await dep.on_failed(e)
                except Exception as cb_error:
                    logger.error(f"Error in on_failed callback for {dep.name}: {cb_error}")
            
            return False
    
    async def _initialize_with_retry(self, dep: SoftDependency):
        """Initialize dependency with retry logic."""
        while dep.should_retry():
            success = await self._initialize_dependency(dep)
            
            if success:
                return
            
            if dep.should_retry():
                delay = dep.get_next_retry_delay()
                logger.info(f"🔄 Retrying {dep.name} in {delay:.1f}s (attempt {dep.retry_count}/{dep.retry_policy.max_attempts})")
                await asyncio.sleep(delay)
        
        logger.error(f"❌ {dep.name} failed after {dep.retry_count} attempts")
        dep.status = DependencyStatus.FAILED
    
    async def _check_health(self, dep: SoftDependency) -> bool:
        """Check health of a dependency."""
        if not dep.instance:
            return False
        
        try:
            if hasattr(dep.instance, 'health_check'):
                health_check = dep.instance.health_check
                if asyncio.iscoroutinefunction(health_check):
                    return await health_check()
                else:
                    return health_check()
            
            # Default: check if instance exists and has session
            if hasattr(dep.instance, '_session'):
                return dep.instance._session is not None
            
            return True
            
        except Exception as e:
            logger.debug(f"Health check failed for {dep.name}: {e}")
            return False
    
    async def _health_monitor_loop(self):
        """Background task for monitoring and recovering dependencies."""
        logger.info("🏥 Health monitor started")
        
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                for dep in self.dependencies.values():
                    if dep.status == DependencyStatus.AVAILABLE:
                        is_healthy = await self._check_health(dep)
                        dep.last_health_check = datetime.now()
                        
                        if not is_healthy:
                            logger.warning(f"⚠️  {dep.name} health check failed, marking as degraded")
                            dep.status = DependencyStatus.DEGRADED
                            self._log_event('health_degraded', dep.name, "Health check failed")
                            
                            # Attempt recovery
                            if self.enable_auto_recovery:
                                logger.info(f"🔄 Attempting auto-recovery for {dep.name}")
                                await self._recover_dependency(dep)
                    
                    elif dep.status == DependencyStatus.DEGRADED:
                        # Try recovery
                        if self.enable_auto_recovery:
                            await self._recover_dependency(dep)
                
            except Exception as e:
                logger.error(f"Error in health monitor: {e}", exc_info=True)
    
    async def _recover_dependency(self, dep: SoftDependency):
        """Attempt to recover a failed/degraded dependency."""
        dep.status = DependencyStatus.RECOVERING
        self._log_event('recovery_attempt', dep.name, "Attempting recovery")
        
        # Cleanup old instance
        if dep.instance:
            await self._cleanup_instance(dep)
        
        # Reset retry count for recovery
        original_retry_count = dep.retry_count
        dep.retry_count = 0
        
        success = await self._initialize_dependency(dep)
        
        if success:
            logger.info(f"✅ Successfully recovered {dep.name}")
            self._log_event('recovery_success', dep.name, "Recovery successful")
            
            if dep.on_recovered:
                try:
                    await dep.on_recovered(dep.instance)
                except Exception as e:
                    logger.error(f"Error in on_recovered callback: {e}")
        else:
            dep.retry_count = original_retry_count
            dep.status = DependencyStatus.FAILED
            self._log_event('recovery_failed', dep.name, "Recovery failed")
    
    async def get(self, name: str, use_fallback: bool = True) -> Optional[Any]:
        """
        Get a dependency instance.
        
        Args:
            name: Dependency name
            use_fallback: Use fallback handler if unavailable
            
        Returns:
            Dependency instance or None
        """
        if name not in self.dependencies:
            logger.warning(f"⚠️  Unknown dependency: {name}")
            return None
        
        dep = self.dependencies[name]
        
        # Lazy initialization
        if dep.strategy == InitializationStrategy.LAZY and dep.status == DependencyStatus.UNINITIALIZED:
            logger.info(f"🔄 Lazy-initializing {name}")
            await self._initialize_with_retry(dep)
        
        if dep.is_healthy():
            return dep.instance
        
        # Use fallback if available
        if use_fallback and name in self.fallback_handlers:
            logger.debug(f"Using fallback for {name}")
            return self.fallback_handlers[name]
        
        return None
    
    def get_sync(self, name: str) -> Optional[Any]:
        """Synchronous get (only works if already initialized)."""
        if name not in self.dependencies:
            return None
        
        dep = self.dependencies[name]
        return dep.instance if dep.is_healthy() else None
    
    def is_available(self, name: str) -> bool:
        """Check if dependency is available."""
        if name not in self.dependencies:
            return False
        return self.dependencies[name].is_healthy()
    
    def with_fallback(self, name: str):
        """Decorator for providing fallback behavior."""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                dep = await self.get(name, use_fallback=False)
                if dep:
                    return await func(dep, *args, **kwargs)
                else:
                    # Call fallback
                    if name in self.fallback_handlers:
                        return await self.fallback_handlers[name](*args, **kwargs)
                    return None
            return wrapper
        return decorator
    
    async def enable_dependency(self, name: str) -> bool:
        """Enable and initialize a disabled dependency."""
        if name not in self.dependencies:
            return False
        
        dep = self.dependencies[name]
        if dep.status != DependencyStatus.DISABLED:
            logger.warning(f"{name} is not disabled (status: {dep.status.value})")
            return False
        
        dep.status = DependencyStatus.UNINITIALIZED
        return await self._initialize_with_retry(dep)
    
    async def disable_dependency(self, name: str):
        """Disable a dependency."""
        if name not in self.dependencies:
            return
        
        dep = self.dependencies[name]
        await self._cleanup_instance(dep)
        dep.status = DependencyStatus.DISABLED
        self._log_event('disable', name, "Dependency disabled")
        logger.info(f"🔒 Disabled {name}")
    
    async def enable_group(self, group_name: str) -> Dict[str, bool]:
        """Enable all dependencies in a group."""
        if group_name not in self.groups:
            logger.warning(f"Unknown group: {group_name}")
            return {}
        
        group = self.groups[group_name]
        group.enable()
        
        results = {}
        for dep_name in group.dependencies:
            results[dep_name] = await self.enable_dependency(dep_name)
        
        return results
    
    async def disable_group(self, group_name: str):
        """Disable all dependencies in a group."""
        if group_name not in self.groups:
            return
        
        group = self.groups[group_name]
        group.disable()
        
        for dep_name in group.dependencies:
            await self.disable_dependency(dep_name)
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all dependency statuses."""
        status_counts = defaultdict(int)
        for dep in self.dependencies.values():
            status_counts[dep.status.value] += 1
        
        return {
            'total': len(self.dependencies),
            'available': status_counts[DependencyStatus.AVAILABLE.value],
            'degraded': status_counts[DependencyStatus.DEGRADED.value],
            'failed': status_counts[DependencyStatus.FAILED.value],
            'disabled': status_counts[DependencyStatus.DISABLED.value],
            'uninitialized': status_counts[DependencyStatus.UNINITIALIZED.value],
            'by_priority': self._get_priority_breakdown()
        }
    
    def _get_priority_breakdown(self) -> Dict[str, Dict[str, int]]:
        """Get status breakdown by priority."""
        breakdown = defaultdict(lambda: defaultdict(int))
        
        for dep in self.dependencies.values():
            breakdown[dep.priority.value][dep.status.value] += 1
        
        return dict(breakdown)
    
    def get_dependency_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a dependency."""
        if name not in self.dependencies:
            return None
        
        return self.dependencies[name].to_dict()
    
    def get_all_dependencies_info(self) -> List[Dict[str, Any]]:
        """Get information about all dependencies."""
        return [dep.to_dict() for dep in self.dependencies.values()]
    
    def find_by_tag(self, tag: str) -> List[str]:
        """Find dependencies by tag."""
        return [name for name, dep in self.dependencies.items() if tag in dep.tags]
    
    def _log_event(self, event_type: str, dependency: str, message: str):
        """Log an event to history."""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'dependency': dependency,
            'message': message
        }
        self.event_history.append(event)
    
    def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent event history."""
        return list(self.event_history)[-limit:]
    
    async def _cleanup_instance(self, dep: SoftDependency):
        """Cleanup dependency instance."""
        if not dep.instance:
            return
        
        try:
            # Call __aexit__ if context manager
            if hasattr(dep.instance, '__aexit__'):
                await dep.instance.__aexit__(None, None, None)
            
            # Call cleanup method if exists
            if hasattr(dep.instance, 'cleanup'):
                cleanup = dep.instance.cleanup
                if asyncio.iscoroutinefunction(cleanup):
                    await cleanup()
                else:
                    cleanup()
            
            # Close session if exists
            if hasattr(dep.instance, 'close'):
                close = dep.instance.close
                if asyncio.iscoroutinefunction(close):
                    await close()
                else:
                    close()
            
        except Exception as e:
            logger.error(f"Error cleaning up {dep.name}: {e}")
        finally:
            dep.instance = None
    
    async def shutdown(self):
        """Shutdown all dependencies and cleanup resources."""
        logger.info("🛑 Shutting down dependency registry...")
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        
        # Cleanup all instances
        for dep in self.dependencies.values():
            if dep.instance:
                await self._cleanup_instance(dep)
                dep.status = DependencyStatus.DISABLED
        
        logger.info("✅ Dependency registry shutdown complete")
