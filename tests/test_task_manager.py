import asyncio

import pytest

from utils.task_manager import task_manager


@pytest.mark.asyncio
async def test_task_manager_create_and_duplicate_prevention():
    # Ensure clean slate
    task_manager.cancel_all()

    async def short_job():
        await asyncio.sleep(0.05)
        return "ok"

    t1 = await task_manager.create_engine_task(short_job, "tm.test")
    # Creating again with same id should return the same running task
    t2 = await task_manager.create_engine_task(short_job, "tm.test")
    assert t1 is t2

    assert task_manager.task_status("tm.test") in ("running", "done")

    # Wait for task to finish
    await asyncio.sleep(0.1)

    # After completion status should be done or None (task removed)
    status = task_manager.task_status("tm.test")
    assert status in ("done", None)

    # Shutdown should clear tasks
    await task_manager.shutdown()
    assert task_manager.tasks == {}

@pytest.mark.asyncio
async def test_task_manager_restart_behavior():
    task_manager.cancel_all()

    async def looping_job():
        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            return

    # Start long running task
    t = await task_manager.create_engine_task(looping_job, "tm.loop")
    assert task_manager.task_status("tm.loop") == "running"

    # Restart by creating with restart=True via internal API
    new_task = await task_manager.create_task(looping_job, "tm.loop", "engine", restart=True)
    assert new_task is not t

    # Cleanup
    await task_manager.shutdown()
    assert task_manager.tasks == {}
