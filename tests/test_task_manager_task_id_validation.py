import asyncio

import pytest

from utils.task_manager import task_manager


@pytest.mark.asyncio
async def test_valid_and_invalid_task_ids():
    # Valid id should succeed
    async def short_job():
        await asyncio.sleep(0.01)
        return True

    t = await task_manager.create_engine_task(short_job, "engine.valid_test")
    assert t is not None

    # Invalid ids should raise
    with pytest.raises(ValueError):
        await task_manager.create_engine_task(short_job, "invalidTask")

    with pytest.raises(ValueError):
        await task_manager.create_engine_task(short_job, "bad-id-withoutdot")

    # Cleanup
    await task_manager.shutdown()