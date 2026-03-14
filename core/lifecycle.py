"""
Lifecycle Management

This module provides a single authority for runtime lifecycle operations:

1. initialize()   - async initialization (I/O, network, DB)
2. start()        - start runtime loops/tasks
3. stop()         - graceful shutdown
4. restart()      - stop + start

Important Rules:
- No component construction occurs here (that belongs to compose.py)
- No side effects during initialization beyond what the components perform
- Components are initialized in dependency order
- Shutdown occurs in reverse dependency order
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Coroutine, Protocol, Union


class LifecycleError(RuntimeError):
    """Raised when lifecycle operations fail or are invalid."""


class LifecycleState:
    """Lifecycle states."""
    CONSTRUCTED = "constructed"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"


class ComponentState:
    """Deprecated alias for LifecycleState; kept for backward compatibility."""
    CONSTRUCTED = LifecycleState.CONSTRUCTED
    INITIALIZED = LifecycleState.INITIALIZED
    STARTED = LifecycleState.STARTED
    STOPPED = LifecycleState.STOPPED
    NOT_INITIALIZED = LifecycleState.CONSTRUCTED  # Alias for legacy code


class OrchestratorComponentState:
    """
    State for component in orchestrator view.
    Kept as an alias to support legacy code.
    """
    CONSTRUCTED = LifecycleState.CONSTRUCTED
    INITIALIZED = LifecycleState.INITIALIZED
    STARTED = LifecycleState.STARTED
    STOPPED = LifecycleState.STOPPED
    READY = LifecycleState.STARTED  # Alias for legacy code


class ComponentLifecycle(Protocol):
    """
    Optional lifecycle interface components may implement.

    Methods are optional; Lifecycle will call them if present.
    """

    async def initialize(self) -> None:
        ...

    async def start(self) -> None:
        ...

    async def stop(self, reason: str = "requested") -> None:
        ...

    async def shutdown(self, reason: str = "requested") -> None:
        ...


@dataclass(frozen=True)
class ComponentDescriptor:
    """
    Metadata for lifecycle management.

    Attributes:
        name: component name key in composition.components
        dependencies: list of names that must be initialized first
        required: if True, failure to initialize will abort startup
        timeout: optional per-component timeout for init/start/stop
    """
    name: str
    dependencies: List[str] = field(default_factory=list)
    required: bool = True
    timeout: Optional[float] = None


@dataclass
class Lifecycle:
    """
    Runtime lifecycle controller.

    This class is intentionally simple and deterministic.
    It operates on a SystemComposition (constructed by compose.py).
    """

    composition: Any
    descriptors: List[ComponentDescriptor] = field(default_factory=list)
    logger: Optional[Any] = None

    components: Dict[str, Any] = field(init=False)
    _state: str = field(default=LifecycleState.CONSTRUCTED, init=False)

    def __post_init__(self):
        self.components = getattr(self.composition, "components", {})
        if not isinstance(self.components, dict):
            raise LifecycleError("Invalid composition: components must be a dict")
        if not self.components:
            raise LifecycleError("Invalid composition: no components found")

    def register(self, descriptor: ComponentDescriptor) -> None:
        """
        Register a component descriptor for lifecycle ordering.
        """
        self.descriptors.append(descriptor)

    def _log(self, msg: str) -> None:
        if self.logger:
            try:
                self.logger.info(msg)
            except Exception:
                pass

    def _resolve_order(self) -> List[ComponentDescriptor]:
        """
        Resolve initialization order based on dependencies using topological sort.

        Raises LifecycleError on circular dependencies or missing required dependencies.
        """
        name_map = {d.name: d for d in self.descriptors}
        resolved: List[ComponentDescriptor] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str):
            if node in visited:
                return
            if node in visiting:
                raise LifecycleError(f"Circular dependency detected: {node}")
            visiting.add(node)

            descriptor = name_map.get(node)
            if descriptor is None:
                # Unknown descriptor: only allow if component is optional
                visiting.remove(node)
                visited.add(node)
                return

            for dep in descriptor.dependencies:
                if dep not in name_map:
                    raise LifecycleError(
                        f"Component '{descriptor.name}' depends on unknown component '{dep}'"
                    )
                visit(dep)

            resolved.append(descriptor)
            visiting.remove(node)
            visited.add(node)

        for descriptor in self.descriptors:
            visit(descriptor.name)

        return resolved

    async def _call_with_timeout(
        self,
        coro: Coroutine,
        timeout: Optional[float],
        component_name: str,
        action: str,
    ) -> None:
        if timeout is None:
            await coro
            return

        try:
            await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise LifecycleError(
                f"Timeout during {action} for component '{component_name}' after {timeout}s"
            ) from exc

    async def initialize(self) -> None:
        """
        Perform async initialization of all registered components.

        Initialization order is based on dependencies.

        If a required component fails, initialization aborts.
        Optional components may fail without aborting.
        """
        if self._state in (LifecycleState.INITIALIZED, LifecycleState.STARTED):
            return

        if self._state != LifecycleState.CONSTRUCTED:
            raise LifecycleError(f"Cannot initialize from state: {self._state}")

        order = self._resolve_order()

        errors: List[Exception] = []

        for descriptor in order:
            component = self.components.get(descriptor.name)

            if component is None:
                if descriptor.required:
                    raise LifecycleError(f"Missing required component: {descriptor.name}")
                continue

            init_fn = getattr(component, "initialize", None)
            if init_fn is None:
                continue

            try:
                self._log(f"Initializing {descriptor.name}")
                coro = init_fn() if asyncio.iscoroutinefunction(init_fn) else asyncio.to_thread(init_fn)
                await self._call_with_timeout(coro, descriptor.timeout, descriptor.name, "initialize")
            except Exception as exc:
                if descriptor.required:
                    raise LifecycleError(
                        f"Failed to initialize required component {descriptor.name}"
                    ) from exc
                errors.append(exc)

        if errors:
            # Optional component failures do not abort, but are recorded
            self._log(f"Optional component initialization errors: {len(errors)}")

        self._state = LifecycleState.INITIALIZED

    async def start(self) -> None:
        """
        Start the runtime.

        This method assumes initialize() has already been called.
        """
        if self._state == LifecycleState.STARTED:
            return

        if self._state == LifecycleState.CONSTRUCTED:
            await self.initialize()

        if self._state != LifecycleState.INITIALIZED:
            raise LifecycleError(f"Cannot start from state: {self._state}")

        order = self._resolve_order()
        errors: List[Exception] = []

        for descriptor in order:
            component = self.components.get(descriptor.name)
            if component is None:
                continue

            start_fn = getattr(component, "start", None)
            if start_fn is None:
                continue

            try:
                self._log(f"Starting {descriptor.name}")
                coro = start_fn() if asyncio.iscoroutinefunction(start_fn) else asyncio.to_thread(start_fn)
                await self._call_with_timeout(coro, descriptor.timeout, descriptor.name, "start")
            except Exception as exc:
                if descriptor.required:
                    raise LifecycleError(f"Failed to start required component {descriptor.name}") from exc
                errors.append(exc)

        if errors:
            self._log(f"Optional component start errors: {len(errors)}")

        self._state = LifecycleState.STARTED

    async def stop(self, reason: str = "requested") -> None:
        """
        Graceful shutdown in reverse dependency order.
        """
        if self._state not in (LifecycleState.STARTED, LifecycleState.INITIALIZED):
            return

        order = list(reversed(self._resolve_order()))
        errors: List[Exception] = []

        for descriptor in order:
            component = self.components.get(descriptor.name)
            if component is None:
                continue

            stop_fn = getattr(component, "shutdown", None) or getattr(component, "stop", None)
            if stop_fn is None:
                continue

            try:
                self._log(f"Stopping {descriptor.name}")
                coro = stop_fn(reason=reason) if asyncio.iscoroutinefunction(stop_fn) else asyncio.to_thread(stop_fn, reason)
                await self._call_with_timeout(coro, descriptor.timeout, descriptor.name, "stop")
            except Exception as exc:
                errors.append(exc)

        if errors:
            self._log(f"Errors during shutdown: {len(errors)}")

        self._state = LifecycleState.STOPPED

    async def restart(self) -> None:
        """
        Restart runtime by stopping and starting again.
        """
        await self.stop(reason="restart")
        await self.start()


# --------------------------------------------------------------------
# Factory helpers (single authority for lifecycle construction)
# --------------------------------------------------------------------

def get_lifecycle_orchestrator(
    composition: Any,
    descriptors: Optional[List[ComponentDescriptor]] = None,
    logger: Optional[Any] = None,
) -> Lifecycle:
    """
    Factory function to create a Lifecycle orchestrator.

    This is the ONLY place lifecycle is constructed.
    """
    if descriptors is None:
        descriptors = []
    return Lifecycle(
        composition=composition,
        descriptors=descriptors,
        logger=logger,
    )


def get_startup_director(
    composition: Any,
    descriptors: Optional[List[ComponentDescriptor]] = None,
    logger: Optional[Any] = None,
) -> Lifecycle:
    """
    Alias for get_lifecycle_orchestrator for backwards compatibility.
    """
    return get_lifecycle_orchestrator(
        composition=composition,
        descriptors=descriptors,
        logger=logger,
    )

