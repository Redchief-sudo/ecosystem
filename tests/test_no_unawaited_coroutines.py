from decimal import Decimal

import pytest

from ai.elite_ai_controller import EliteAsyncAIController


@pytest.mark.asyncio
async def test_elite_ai_controller_start_and_shutdown_no_unawaited_warnings():
    controller = EliteAsyncAIController(config={'health_check_interval': 0.01}, total_capital=Decimal('1000'))
    # Initialize and start background tasks
    await controller.async_initialize()
    # Shutdown should cancel background tasks cleanly without leaking coroutines
    await controller.shutdown()
    # If any ResourceWarnings or RuntimeWarnings about unawaited coroutines exist, pytest will fail due to strict filterwarnings
    assert True
