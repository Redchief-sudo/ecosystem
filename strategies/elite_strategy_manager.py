import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .base_strategy import BaseStrategy, TradeSignal, SignalType
from core.health_check import HealthStatus, standard_health_check

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    CLOSED = auto()
    OPEN = auto()


@dataclass
class NormalizedSignal:
    strategy_id: str
    signal_type: SignalType
    direction: str  # "buy" | "sell"
    confidence: float
    expected_edge: float
    max_risk: float
    token_address: str
    token_symbol: str
    price: float
    ttl: int
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class SignalExecutionResult:
    def __init__(
        self,
        strategy_id: str,
        success: bool,
        signal: Optional[NormalizedSignal] = None,
        error: Optional[str] = None,
        execution_time: float = 0.0,
        timeout: bool = False,
        neutral: bool = False,
    ):
        self.strategy_id = strategy_id
        self.success = success
        self.signal = signal
        self.error = error
        self.execution_time = execution_time
        self.timeout = timeout
        self.neutral = neutral


class SignalNormalizer:

    @staticmethod
    def normalize_trade_signal(
        strategy_id: str,
        trade_signal: TradeSignal,
        market_data: Dict[str, Any],
    ) -> NormalizedSignal:

        base_edge = trade_signal.confidence * 0.1
        volatility_adj = SignalNormalizer._calculate_volatility_adjustment(market_data)
        expected_edge = base_edge * (1 + volatility_adj)

        if trade_signal.stop_loss and trade_signal.take_profit:
            price_risk = abs(trade_signal.stop_loss - trade_signal.price) / trade_signal.price
            volatility_factor = market_data.get("volatility_factor", 0.2)
            liquidity_factor = min(1.0, market_data.get("liquidity", 0) / 1_000_000)
            max_risk = price_risk * (1 + volatility_factor) * (1 - liquidity_factor * 0.3)
        else:
            max_risk = 0.05

        return NormalizedSignal(
            strategy_id=strategy_id,
            signal_type=trade_signal.signal_type,
            direction=SignalNormalizer._map_signal_to_direction(trade_signal.signal_type),
            confidence=trade_signal.confidence,
            expected_edge=expected_edge,
            max_risk=max_risk,
            token_address=trade_signal.token_address,
            token_symbol=trade_signal.token_symbol,
            price=trade_signal.price,
            ttl=SignalNormalizer._calculate_ttl(trade_signal.signal_type),
            created_at=datetime.now(timezone.utc),
            metadata=trade_signal.metadata or {},
        )

    @staticmethod
    def _map_signal_to_direction(signal_type: SignalType) -> str:
        if signal_type == SignalType.BUY:
            return "buy"
        if signal_type == SignalType.SELL:
            return "sell"
        raise ValueError("Unsupported SignalType")

    @staticmethod
    def _calculate_volatility_adjustment(market_data: Dict[str, Any]) -> float:
        return market_data.get("volatility", 0.0)

    @staticmethod
    def _calculate_ttl(signal_type: SignalType) -> int:
        return 30 if signal_type == SignalType.BUY else 30


class ExecutionGuardrails:

    @staticmethod
    def validate_no_direct_trading(strategy_name: str) -> None:
        logger.warning(f"Execution guardrails: {strategy_name} must not execute trades directly")

    @staticmethod
    def block_trade_execution(strategy_name: str, action: str) -> None:
        logger.error(f"BLOCKED: {strategy_name} attempted {action} directly")
        raise PermissionError(f"Strategy {strategy_name} cannot execute {action} directly.")

    @staticmethod
    def enforce_signal_only_mode(strategy_name: str) -> None:
        logger.info(f"{strategy_name} is operating in signal-only mode")


@dataclass
class StrategyMetrics:
    consecutive_failures: int = 0
    total_runs: int = 0
    total_successes: int = 0
    total_time: float = 0.0

    def record_execution(self, success: bool, execution_time: float, error: Optional[Exception] = None, timed_out: bool = False):
        self.total_runs += 1
        self.total_time += execution_time

        if success:
            self.total_successes += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1


class EliteStrategyManager:
    def __init__(
        self,
        strategies: List[BaseStrategy],
        strategy_timeout_seconds: float = 3.0,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: float = 60.0,
    ):
        self.strategies = strategies
        self.strategy_timeout_seconds = strategy_timeout_seconds
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        self.metrics: Dict[str, StrategyMetrics] = {}
        self.circuit_breaker_states: Dict[str, tuple[CircuitBreakerState, float]] = {}

        for s in strategies:
            sid = self._get_strategy_name(s)
            self.metrics[sid] = StrategyMetrics()
            self.circuit_breaker_states[sid] = (CircuitBreakerState.CLOSED, 0.0)

    def _get_strategy_name(self, strategy: BaseStrategy) -> str:
        return getattr(strategy, "strategy_id", strategy.__class__.__name__)

    def _is_strategy_enabled(self, strategy: BaseStrategy) -> bool:
        return getattr(strategy, "enabled", True)

    async def _execute_single_strategy(
        self,
        strategy: BaseStrategy,
        strategy_id: str,
        market_data: Dict[str, Any],
        timeout_seconds: float,
    ) -> SignalExecutionResult:

        state, last_failure = self.circuit_breaker_states[strategy_id]

        if state == CircuitBreakerState.OPEN:
            if time.time() - last_failure < self.circuit_breaker_timeout:
                return SignalExecutionResult(
                    strategy_id=strategy_id,
                    success=False,
                    error="circuit_breaker_open",
                )
            self.circuit_breaker_states[strategy_id] = (CircuitBreakerState.CLOSED, 0.0)

        timeout = min(timeout_seconds, self.strategy_timeout_seconds)
        start = time.time()

        try:
            trade_signal = await asyncio.wait_for(
                strategy.evaluate_token(market_data),
                timeout=timeout,
            )
            exec_time = time.time() - start

            if trade_signal is None:
                return SignalExecutionResult(
                    strategy_id=strategy_id,
                    success=False,
                    execution_time=exec_time,
                )

            normalized = SignalNormalizer.normalize_trade_signal(
                strategy_id,
                trade_signal,
                market_data,
            )

            return SignalExecutionResult(
                strategy_id=strategy_id,
                success=True,
                signal=normalized,
                execution_time=exec_time,
            )

        except asyncio.TimeoutError:
            exec_time = time.time() - start
            return SignalExecutionResult(
                strategy_id=strategy_id,
                success=False,
                error="timeout",
                execution_time=exec_time,
                timeout=True,
            )

        except Exception as e:
            exec_time = time.time() - start
            return SignalExecutionResult(
                strategy_id=strategy_id,
                success=False,
                error=str(e),
                execution_time=exec_time,
            )

    async def execute_strategies_parallel(
        self,
        market_data: Dict[str, Any],
        timeout_seconds: float = 3.0,
    ) -> List[SignalExecutionResult]:

        if not self.strategies:
            return []

        tasks = {
            self._get_strategy_name(strategy): asyncio.create_task(
                self._execute_single_strategy(
                    strategy,
                    self._get_strategy_name(strategy),
                    market_data,
                    timeout_seconds,
                )
            )
            for strategy in self.strategies
            if self._is_strategy_enabled(strategy)
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        output: List[SignalExecutionResult] = []

        for strategy_id, res in zip(tasks.keys(), results):
            metrics = self.metrics[strategy_id]

            if isinstance(res, Exception):
                metrics.record_execution(False, timeout_seconds, error=res, timed_out=True)
                output.append(
                    SignalExecutionResult(
                        strategy_id=strategy_id,
                        success=False,
                        error=str(res),
                        timeout=True,
                    )
                )
                continue

            output.append(res)

            if res.success:
                metrics.record_execution(True, res.execution_time)
            else:
                metrics.record_execution(
                    False,
                    res.execution_time,
                    error=Exception(res.error) if res.error else None,
                    timed_out=res.timeout,
                )

                if metrics.consecutive_failures >= self.circuit_breaker_threshold:
                    self.circuit_breaker_states[strategy_id] = (
                        CircuitBreakerState.OPEN,
                        time.time(),
                    )

        return output

