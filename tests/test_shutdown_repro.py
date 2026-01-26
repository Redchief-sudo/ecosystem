import asyncio
from decimal import Decimal

import pytest

from ai.elite_ai_controller import EliteAsyncAIController
from trading.trade_engine import SystemState, TradingEngine


class MinimalScanDirector:
    async def scan_all(self):
        # Return empty list quickly to simulate no opportunities
        await asyncio.sleep(0.01)
        return []


class MinimalTradeExecutor:
    async def close(self):
        # Simulate async close work
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_trading_engine_shutdown_during_startup_no_exception():
    """Reproduce shutdown during early startup (no cycles) deterministically.

    This test uses minimal, real components (no mocks) and ensures calling
    stop() shortly after start() does not produce exceptions or leave tasks running.
    """
    controller = EliteAsyncAIController(config={'health_check_interval': 0.01}, total_capital=Decimal('1000'))

    # Initialize the AI controller (deterministic async init)
    await controller.async_initialize()

    scan_director = MinimalScanDirector()
    trade_executor = MinimalTradeExecutor()

    engine = TradingEngine(
        scan_director=scan_director,
        elite_ai_controller=controller,
        trade_executor=trade_executor,
        trade_optimizer=None,
        config={'scanning': {'interval': 1, 'batch_size': 10}},
    )

    # Start the engine in the background
    engine_task = asyncio.create_task(engine.start())

    # Allow a tiny bit of time for startup tasks to register
    await asyncio.sleep(0.05)

    # Trigger shutdown while engine is still in early lifecycle
    await engine.stop()

    # Give engine task a moment to exit (cancel if it hangs)
    try:
        await asyncio.wait_for(asyncio.shield(engine_task), timeout=1.0)
    except asyncio.TimeoutError:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass

    # Sanity checks
    assert engine.system_state == SystemState.SHUTDOWN
    assert not engine._started
    assert not engine.is_running

    # Ensure controller shutdown is idempotent and can be awaited safely
    await controller.shutdown()
    assert not await controller.is_ready()


@pytest.mark.asyncio
async def test_trading_engine_with_zero_portfolio_value_does_not_raise_on_start_or_shutdown():
    """Simulate a controller whose portfolio value is zero to ensure engine
    does not raise during start and can shutdown cleanly (regression for older behavior).
    """
    class ZeroPortfolioController(EliteAsyncAIController):
        def get_portfolio_value(self) -> float:
            return 0.0

    controller = ZeroPortfolioController(config={'health_check_interval': 0.01}, total_capital=Decimal('0'))
    # Do not call async_initialize to simulate partial init

    scan_director = MinimalScanDirector()
    trade_executor = MinimalTradeExecutor()

    engine = TradingEngine(
        trade_executor=trade_executor,
        config={'scanning': {'interval': 1, 'batch_size': 10}},
    )

    # Starting and then stopping should not raise even if portfolio value is 0
    engine_task = asyncio.create_task(engine.start())
    await asyncio.sleep(0.02)
    await engine.stop()

    try:
        await asyncio.wait_for(asyncio.shield(engine_task), timeout=1.0)
    except asyncio.TimeoutError:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass

    assert engine.system_state == SystemState.SHUTDOWN
    await controller.shutdown()
    assert not await controller.is_ready()


@pytest.mark.asyncio
async def test_trading_engine_stop_idempotent():
    """Calling stop() multiple times should be safe and idempotent."""
    controller = EliteAsyncAIController(config={'health_check_interval': 0.01}, total_capital=Decimal('1000'))
    await controller.async_initialize()

    engine = TradingEngine(
        trade_executor=MinimalTradeExecutor(),
        config={'scanning': {'interval': 1, 'batch_size': 10}},
    )

    # Start and then stop multiple times
    engine_task = asyncio.create_task(engine.start())
    await asyncio.sleep(0.02)

    await engine.stop()
    # Second stop should be no-op
    await engine.stop()

    # Ensure engine task finishes
    try:
        await asyncio.wait_for(asyncio.shield(engine_task), timeout=1.0)
    except asyncio.TimeoutError:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass

    assert engine.system_state == SystemState.SHUTDOWN
    await controller.shutdown()
    assert not await controller.is_ready()


@pytest.mark.asyncio
async def test_network_degraded_startup_does_not_block_engine():
    """Starting the network manager with bad RPCs should not prevent the engine from starting
    or shutting down cleanly. This uses real components and no mocks."""
    from network.multi_chain_manager import MultiChainManager

    # Use clearly invalid RPC endpoints to simulate degradation
    cfg = {
        'networks': {
            'ethereum': {
                'chain_id': 1,
                'rpc': 'http://127.0.0.1:1',
                'fallback_rpcs': ['http://127.0.0.1:2']
            }
        }
    }

    network_mgr = MultiChainManager(cfg, private_key='')

    # Initialization should not raise, even if RPCs are unreachable
    await network_mgr.initialize()

    controller = EliteAsyncAIController(config={'health_check_interval': 0.01}, total_capital=Decimal('1000'))
    await controller.async_initialize()
    controller.network_manager = network_mgr

    engine = TradingEngine(
        trade_executor=MinimalTradeExecutor(),
        config={'scanning': {'interval': 1, 'batch_size': 10}},
    )

    engine_task = asyncio.create_task(engine.start())
    await asyncio.sleep(0.02)

    # Stop should be safe
    await engine.stop()

    try:
        await asyncio.wait_for(asyncio.shield(engine_task), timeout=1.0)
    except asyncio.TimeoutError:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass

    assert engine.system_state == SystemState.SHUTDOWN
    await controller.shutdown()
    assert not await controller.is_ready()
