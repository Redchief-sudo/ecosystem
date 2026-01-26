import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone

# Replace with your actual imports
from ai.elite_async_ai_controller import EliteAsyncAIController, ActivePosition, StrategyPerformance, SelectionMethod, StrategyType
from trading.models import TradeOpportunity, TokenInfo, MarketData
from ai.token_scoring_service import MarketRegime
from trading.trade_intent.trade_intent import TradeIntent
from trading.trade_intent.trade_intent_builder import TradeIntentBuilder


@pytest.fixture
def controller():
    ctrl = EliteAsyncAIController(config={
        "exploration_rate": 0.1,
        "ensemble_size": 2,
        "equal_weight_mode": False,
        "performance_decay_factor": 0.9,
        "rebalance_interval": 1,
    })
    ctrl._running = True
    ctrl._strategy_lock = asyncio.Lock()
    ctrl._position_lock = asyncio.Lock()
    ctrl._rotation_counter = 0
    ctrl.current_regime = ctrl.current_regime or MarketRegime.SIDEWAYS
    ctrl.regime_confidence = getattr(ctrl, "regime_confidence", 1.0)
    ctrl.allocator = ctrl.allocator or DummyAllocator()

    return ctrl


class DummyAllocator:
    def __init__(self):
        self.total_capital = Decimal("1000")
        self.available = Decimal("1000")

    async def get_available_capital(self):
        return self.available

    def get_utilization(self):
        return float((self.total_capital - self.available) / self.total_capital)

    async def release_allocation(self, amount: Decimal):
        self.available += amount


@pytest.mark.asyncio
async def test_locking_on_disable_quarantine(controller):
    # Ensure locks exist
    assert hasattr(controller, "_strategy_lock")

    # Insert dummy strategy
    sp = StrategyPerformance(strategy_id="s1", strategy_name="Test", strategy_type="test")
    controller.strategies["s1"] = sp

    # Should not raise
    await controller._disable_strategy("s1", "test")
    await controller._quarantine_strategy("s1", "error")

    assert "s1" in controller.disabled_strategies
    assert "s1" in controller.quarantined_strategies
    assert controller.strategies["s1"].status in ("disabled", "quarantined")


@pytest.mark.asyncio
async def test_state_consistency(controller):
    # Validate no duplicates in status and sets
    sp = StrategyPerformance(strategy_id="s1", strategy_name="Test", strategy_type=StrategyType.MOMENTUM)
    controller.strategies["s1"] = sp
    sp.status = "active"

    # Should not crash and must return dict
    state = await controller.get_complete_state()
    assert isinstance(state, dict)

    # should not crash on regime
    controller.current_regime = None
    state = await controller.get_complete_state()
    assert state["current_regime"] in (None, "UNKNOWN")


@pytest.mark.asyncio
async def test_position_closing_token_address(controller):
    # Create dummy position with token_address
    pos = ActivePosition(
        position_id="p1",
        strategy_id="s1",
        opportunity_id="o1",
        symbol="ETH",
        token_address="0x123",
        chain="ethereum",
        amount=Decimal("1"),
        entry_price=Decimal("1000")
    )
    controller.active_positions["p1"] = pos

    # Add strategy
    sp = StrategyPerformance(strategy_id="s1", strategy_name="Test", strategy_type="test")
    controller.strategies["s1"] = sp

    # Ensure trading engine exists
    controller._trading_engine = DummyTradingEngine()

    # Should not crash and should return False/True depending on engine
    result = await controller.close_position("p1", Decimal("1100"), reason="test")
    assert result in (True, False)


class DummyTradingEngine:
    async def execute_trade_intent(self, intent: TradeIntent):
        return {"success": True, "order_id": "123"}


@pytest.mark.asyncio
async def test_select_ensemble_total_score(controller):
    # Setup strategies
    for i in range(3):
        sp = StrategyPerformance(strategy_id=f"s{i}", strategy_name=f"Test{i}", strategy_type="test")
        sp.total_trades = 1
        sp.recent_performance = 0.1
        sp.sharpe_ratio = 1.0
        sp.win_rate = 0.6
        sp.consistency_score = 0.5
        sp.current_weight = 1.0 / 3
        controller.strategies[sp.strategy_id] = sp

    opp = TradeOpportunity(
        opportunity_id="o1",
        token_address="0x123",
        token_symbol="TST",
        chain="ethereum",
        price=Decimal("1"),
        volume=Decimal("1"),
        potential_profit=Decimal("0.1"),
        potential_loss=Decimal("0.05"),
        required_capital=Decimal("1"),
        risk_reward_ratio=2.0,
        confidence=0.8
    )

    # Must not crash and should return StrategyRecommendation
    rec = await controller._select_ensemble(["s0", "s1", "s2"], opp)
    assert rec.recommended_strategy_id in ["s0", "s1", "s2"]
    assert isinstance(rec.ensemble_strategies, list)
    assert rec.selection_method == SelectionMethod.ENSEMBLE


@pytest.mark.asyncio
async def test_confidence_calculation(controller):
    sp = StrategyPerformance(strategy_id="s1", strategy_name="Test", strategy_type="test")
    sp.win_rate = 0.8
    sp.sharpe_ratio = 1.2
    sp.consistency_score = 0.8
    controller.strategies["s1"] = sp

    opp = TradeOpportunity(
        opportunity_id="o1",
        token_address="0x123",
        token_symbol="TST",
        chain="ethereum",
        price=Decimal("1"),
        volume=Decimal("1"),
        potential_profit=Decimal("0.1"),
        potential_loss=Decimal("0.05"),
        required_capital=Decimal("1"),
        risk_reward_ratio=2.0,
        confidence=0.8
    )

    conf = controller._calculate_confidence(sp, opp)
    assert 0.0 <= conf <= 1.0


@pytest.mark.asyncio
async def test_shutdown_does_not_reset_flag(controller):
    controller._shutting_down = True
    await controller.shutdown()
    assert controller._shutting_down is True


@pytest.mark.asyncio
async def test_health_check_handles_missing_attributes(controller):
    # Should not raise
    ok = await controller.health_check()
    assert isinstance(ok, bool)


@pytest.mark.asyncio
async def test_ucb_thompson_zero_division(controller):
    # Should not raise even if counts are zero
    controller.strategy_alpha = {"s1": 0}
    controller.strategy_beta = {"s1": 0}
    controller.strategy_selection_count = {"s1": 0}

    # Add strategy
    sp = StrategyPerformance(strategy_id="s1", strategy_name="Test", strategy_type="test")
    controller.strategies["s1"] = sp

    # Should not crash
    ucb = await controller._select_ucb(["s1"])
    thompson = await controller._select_thompson(["s1"])
    assert ucb in ["s1", None]
    assert thompson in ["s1", None]
