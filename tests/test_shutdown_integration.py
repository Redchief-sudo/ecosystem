import asyncio
from decimal import Decimal

import pytest

from ai.elite_async_ai_controller import EliteAsyncAIController
from core.task_manager import task_manager


@pytest.mark.asyncio
async def test_shutdown_cleans_up_tasks():
    controller = EliteAsyncAIController(config={'health_check_interval': 0.01})
    await controller.async_initialize()

    # Ensure TaskManager has tasks (background monitors registered)
    tasks_before = task_manager.tasks
    assert tasks_before, "Expected TaskManager to have tasks after controller initialization"

    # Shutdown controller and verify tasks are cancelled/removed
    await controller.shutdown()

    # Wait for cancellations to process and for TaskManager to remove finished tasks
    for _ in range(20):
        if not task_manager.tasks:
            break
        await asyncio.sleep(0.05)

    # All tasks started by controller should be either done or cancelled
    for tid, t in task_manager.tasks.items():
        assert t.task.done(), f"Task {tid} should be done after shutdown"

    # Ensure any lingering tasks are cleared from the manager
    await task_manager._cancel_all_tasks()
    assert task_manager.tasks == {}, "TaskManager should be empty after cancel_all()"