import asyncio
import pytest
from datetime import datetime, timezone

from strategies.base_strategy import BaseStrategy, TradeSignal, SignalType
from strategies.elite_strategy_manager import EliteStrategyManager
from ai.elite_async_ai_controller import EliteAsyncAIController


# ============================================================
# Fixtures
# ============================================================

class DummyStrategy(BaseStrategy):
    STRATEGY_NAME = "DummyStrategy"

    async def evaluate_token(self, token):
        return TradeSignal(
            signal_type=SignalType.BUY,
            confidence=0.9,
            reason="test",
            token_address=token["address"],
            token_symbol=token["symbol"],
            price=token["price"],
            position_size=1.0
        )


@pytest.fixture
def valid_token():
    return {
        "address": "0x123",
        "symbol": "TEST",
        "price": 1.0,
        "volume_24h": 100000,
        "liquidity": 50000,
    }


@pytest.fixture
def disabled_strategy_config():
    return {
        "strategies": {
            "DummyStrategy": {
                "enabled": False,
                "position_size": 1.0,
                "stop_loss": 0.1,
                "take_profit": 0.2,
            }
        }
    }


@pytest.fixture
def enabled_strategy_config():
    return {
        "strategies": {
            "DummyStrategy": {
                "enabled": True,
                "position_size": 1.0,
                "stop_loss": 0.1,
                "take_profit": 0.2,
            }
        }
    }


# ============================================================
# BaseStrategy Tests
# ============================================================

def test_strategy_fails_closed_without_enabled_flag():
    config = {"strategies": {"DummyStrategy": {}}}
    strategy = DummyStrategy(config=config)

    with pytest.raises(ValueError):
        strategy.is_enabled()


def test_stop_loss_is_fraction():
    config = {
        "strategies": {
            "DummyStrategy": {
                "enabled": True,
                "position_size": 1.0,
                "stop_loss": 2.0,  # invalid
                "take_profit": 0.2,
            }
        }
    }

    strategy = DummyStrategy(config=config)
    with pytest.raises(ValueError):
        strategy.get_stop_loss()


# ============================================================
# EliteStrategyManager Tests
# ============================================================

@pytest.mark.asyncio
async def test_disabled_strategy_is_not_executed(disabled_strategy_config, valid_token):
    manager = EliteStrategyManager(config=disabled_strategy_config)
    manager.strategies = [DummyStrategy(config=disabled_strategy_config)]

    results = await manager.execute_strategies_parallel(valid_token)

    assert results == [] or all(r.signal is None for r in results)


@pytest.mark.asyncio
async def test_strategy_timeout_enforced(enabled_strategy_config, valid_token):
    class SlowStrategy(DummyStrategy):
        async def evaluate_token(self, token):
            await asyncio.sleep(10)
            return None

    manager = EliteStrategyManager(
        config=enabled_strategy_config,
        strategy_timeout_seconds=0.1
    )
    manager.strategies = [SlowStrategy(config=enabled_strategy_config)]

    start = asyncio.get_event_loop().time()
    results = await manager.execute_strategies_parallel(valid_token)
    duration = asyncio.get_event_loop().time() - start

    assert duration < 1.0
    assert results[0].timeout is True


# ============================================================
# EliteAsyncAIController Tests
# ============================================================

@pytest.mark.asyncio
async def test_ai_controller_has_single_decision_path():
    controller = EliteAsyncAIController()

    decision_methods = [
        m for m in dir(controller)
        if "decide" in m.lower() or "evaluate" in m.lower()
    ]

    # Should not have multiple competing decision paths
    assert len(decision_methods) <= 2


@pytest.mark.asyncio
async def test_ai_controller_shutdown_is_idempotent():
    controller = EliteAsyncAIController()
    await controller.shutdown()
    await controller.shutdown()  # should not raise


@pytest.mark.asyncio
async def test_exceptions_are_logged_not_swallowed(caplog):
    controller = EliteAsyncAIController()

    async def broken(*args, **kwargs):
        raise RuntimeError("boom")

    controller._evaluate_strategies = broken

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            await controller.run_once({})

    assert any("boom" in rec.message for rec in caplog.records)
