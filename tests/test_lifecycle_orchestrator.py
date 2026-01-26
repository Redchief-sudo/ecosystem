import pytest

from utils.lifecycle_orchestrator import LifecycleOrchestrator, SystemPhase


def test_phase_completion_idempotent_and_no_regression():
    orch = LifecycleOrchestrator()
    assert orch.current_phase == SystemPhase.BOOT

    orch.mark_phase_complete(SystemPhase.BOOT)
    # Should advance to CORE_INIT
    assert orch.current_phase == SystemPhase.CORE_INIT

    # Calling complete again should not regress or change phase
    orch.mark_phase_complete(SystemPhase.BOOT)
    assert orch.current_phase == SystemPhase.CORE_INIT

    # Try to regress phase explicitly - should be ignored
    orch.current_phase = SystemPhase.BOOT
    assert orch.current_phase == SystemPhase.CORE_INIT

    # Ensure init lock exists
    assert hasattr(orch, '_init_lock')
    assert orch._init_lock is not None
