"""Integration tests for complete trading cycle"""
import asyncio

from ai.elite_async_ai_controller import EliteAsyncAIController


async def test_strategy_integration():
    """Test strategy mapping and instantiation"""
    controller = EliteAsyncAIController(config={}, total_capital=10000)
    await controller.initialize()
    assert len(controller.strategies) > 0, "Should initialize strategies"
    print("Integration test passed")
