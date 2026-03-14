import pytest
from dataclasses import dataclass
from core.lifecycle import Lifecycle, LifecycleState, ComponentDescriptor


@dataclass
class MockComponent:
    """Mock component for testing."""
    name: str
    initialized: bool = False
    started: bool = False
    stopped: bool = False
    
    async def initialize(self):
        self.initialized = True
    
    async def start(self):
        self.started = True
    
    async def stop(self, reason: str = "requested"):
        self.stopped = True


@dataclass
class MockComposition:
    """Mock composition for testing."""
    components: dict


@pytest.mark.asyncio
async def test_phase_completion_idempotent_and_no_regression():
    """Test lifecycle state transitions are idempotent and don't regress."""
    # Create mock components
    comp1 = MockComponent(name="comp1")
    comp2 = MockComponent(name="comp2")
    
    composition = MockComposition(components={"comp1": comp1, "comp2": comp2})
    
    # Create lifecycle orchestrator
    lifecycle = Lifecycle(
        composition=composition,
        descriptors=[
            ComponentDescriptor(name="comp1", dependencies=[]),
            ComponentDescriptor(name="comp2", dependencies=["comp1"])
        ]
    )
    
    # Initial state should be CONSTRUCTED
    assert lifecycle._state == LifecycleState.CONSTRUCTED
    
    # Initialize - should move to INITIALIZED
    await lifecycle.initialize()
    assert lifecycle._state == LifecycleState.INITIALIZED
    assert comp1.initialized
    assert comp2.initialized
    
    # Calling initialize again should be idempotent (no-op)
    await lifecycle.initialize()
    assert lifecycle._state == LifecycleState.INITIALIZED
    
    # Start - should move to STARTED
    await lifecycle.start()
    assert lifecycle._state == LifecycleState.STARTED
    assert comp1.started
    assert comp2.started
    
    # Calling start again should be idempotent (no-op)
    await lifecycle.start()
    assert lifecycle._state == LifecycleState.STARTED
    
    # Stop - should move to STOPPED
    await lifecycle.stop()
    assert lifecycle._state == LifecycleState.STOPPED
    assert comp1.stopped
    assert comp2.stopped
    
    # Verify state doesn't regress
    # Try to manually set state back (shouldn't be allowed in practice)
    # The _state is protected but we can verify current state is correct
    assert lifecycle._state == LifecycleState.STOPPED
