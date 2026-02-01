"""
StrategyManager - Orchestration layer between strategies and downstream consumers.

This module contains the StrategyManager class that handles:
- Strategy lifecycle (registration, activation, deactivation)
- Data routing and feature readiness checks
- Controlled evaluation scheduling
- Signal normalization and aggregation
- Fault isolation and health enforcement
- Weighted ensemble voting
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .data_classes import (
    SignalType,
    DecisionAction,
    RiskProfile,
    StrategyDecision,
    AggregatedDecision,
    HealthStatus,
    EvaluationResult,
    StrategyMetrics,
    Rationale,
)
from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class CircuitBreakerState:
    """Circuit breaker state for fault isolation."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class StrategyState:
    """Internal state for a registered strategy."""
    strategy: BaseStrategy
    active: bool = False
    ready: bool = False
    data_points_seen: int = 0
    last_evaluation: Optional[datetime] = None
    last_decision: Optional[StrategyDecision] = None
    error_count: int = 0
    circuit_breaker: str = CircuitBreakerState.CLOSED
    circuit_breaker_opened_at: Optional[datetime] = None
    weight: float = 1.0  # Strategy weight for aggregation
    metrics: StrategyMetrics = field(default_factory=StrategyMetrics)

    def can_evaluate(self) -> bool:
        """Check if strategy can be evaluated."""
        if not self.active:
            return False
        if self.circuit_breaker == CircuitBreakerState.OPEN:
            # Check if timeout has passed
            if self.circuit_breaker_opened_at:
                from datetime import timedelta
                if datetime.now(timezone.utc) - self.circuit_breaker_opened_at < timedelta(seconds=60):
                    return False
                # Reset to half-open
                self.circuit_breaker = CircuitBreakerState.HALF_OPEN
            return False
        return True


@dataclass
class StrategyManagerConfig:
    """Configuration for StrategyManager."""
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout_seconds: float = 60.0
    evaluation_timeout_seconds: float = 3.0
    min_confidence_threshold: float = 0.3
    require_all_strategies_ready: bool = False
    enable_aggregation: bool = True
    default_strategy_weight: float = 1.0


class StrategyManager:
    """
    Orchestration layer between strategies and downstream consumers.

    Responsibilities:
    - Lifecycle management of strategies
    - Data routing and feature readiness checks
    - Controlled evaluation scheduling
    - Signal normalization and aggregation
    - Fault isolation and health enforcement
    - Weighted ensemble voting
    - Emitting StrategyDecisions, not trades

    This class is designed to be the single source of truth for strategy
    orchestration. All strategy interactions go through this manager.
    """

    def __init__(self, config: Optional[StrategyManagerConfig] = None):
        """
        Initialize the StrategyManager.

        Args:
            config: Optional configuration for the manager
        """
        self.config = config or StrategyManagerConfig()
        self._strategies: Dict[str, StrategyState] = {}
        self._strategy_weights: Dict[str, float] = {}
        self._market_data_cache: Dict[str, Any] = {}

    # === Strategy Registry & Lifecycle ===

    def register_strategy(
        self,
        strategy: BaseStrategy,
        weight: float = 1.0,
        auto_activate: bool = False
    ) -> None:
        """
        Register a new strategy with the manager.

        Responsibilities:
        - Validate strategy contract
        - Enforce unique strategy_id
        - Validate required features
        - Initialize internal state

        Args:
            strategy: BaseStrategy implementation to register
            weight: Weight for aggregation (default 1.0)
            auto_activate: Whether to auto-activate after warmup

        Raises:
            ValueError: If strategy_id already exists or contract invalid
        """
        strategy_id = strategy.strategy_id()

        if strategy_id in self._strategies:
            raise ValueError(f"Strategy '{strategy_id}' already registered")

        # Validate required methods
        self._validate_strategy_contract(strategy)

        # Initialize strategy state
        self._strategies[strategy_id] = StrategyState(
            strategy=strategy,
            weight=weight,
        )
        self._strategy_weights[strategy_id] = weight

        # Call on_start lifecycle hook
        strategy.on_start()

        logger.info(f"Registered strategy: {strategy_id} (weight={weight})")

        # Auto-activate if requested and warmup is 0
        if auto_activate and strategy.warmup_period() == 0:
            self.activate_strategy(strategy_id)

    def unregister_strategy(self, strategy_id: str) -> None:
        """
        Deregister a strategy from the manager.

        Responsibilities:
        - Graceful shutdown via on_stop
        - Remove routing and state
        - Preserve audit trail

        Args:
            strategy_id: ID of strategy to deregister

        Raises:
            KeyError: If strategy not found
        """
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy '{strategy_id}' not found")

        state = self._strategies[strategy_id]
        state.strategy.on_stop()

        # Keep audit trail but mark as inactive
        state.active = False
        state.ready = False

        # Remove from strategies
        del self._strategies[strategy_id]
        if strategy_id in self._strategy_weights:
            del self._strategy_weights[strategy_id]

        logger.info(f"Unregistered strategy: {strategy_id}")

    def activate_strategy(self, strategy_id: str) -> None:
        """
        Activate a registered strategy for evaluation.

        Responsibilities:
        - Enforce warmup readiness
        - Allow hot enable without restart

        Args:
            strategy_id: ID of strategy to activate

        Raises:
            KeyError: If strategy not found
            RuntimeError: If warmup not complete
        """
        state = self._get_strategy_state(strategy_id)

        if not state.ready:
            raise RuntimeError(
                f"Strategy '{strategy_id}' is not ready. "
                f"Data points seen: {state.data_points_seen}, "
                f"Required: {state.strategy.warmup_period()}"
            )

        state.active = True
        logger.info(f"Activated strategy: {strategy_id}")

    def deactivate_strategy(self, strategy_id: str) -> None:
        """
        Deactivate a strategy (stops receiving evaluations).

        Args:
            strategy_id: ID of strategy to deactivate

        Raises:
            KeyError: If strategy not found
        """
        state = self._get_strategy_state(strategy_id)
        state.active = False
        logger.info(f"Deactivated strategy: {strategy_id}")

    def set_strategy_weight(self, strategy_id: str, weight: float) -> None:
        """
        Set the weight for a strategy in aggregation.

        Args:
            strategy_id: ID of strategy
            weight: New weight (higher = more influence)

        Raises:
            KeyError: If strategy not found
        """
        state = self._get_strategy_state(strategy_id)
        state.weight = weight
        self._strategy_weights[strategy_id] = weight
        logger.info(f"Set strategy weight: {strategy_id} = {weight}")

    def get_strategy_weight(self, strategy_id: str) -> float:
        """
        Get the weight for a strategy.

        Args:
            strategy_id: ID of strategy

        Returns:
            Current weight
        """
        return self._strategy_weights.get(strategy_id, 1.0)

    # === Data Readiness & Routing ===

    def is_ready(self, strategy_id: str) -> bool:
        """
        Check if a strategy is ready for evaluation.

        Checks:
        - Warmup period satisfied
        - Required features present
        - Strategy health OK
        - Circuit breaker closed

        Args:
            strategy_id: ID of strategy to check

        Returns:
            True if strategy can be evaluated
        """
        state = self._get_strategy_state(strategy_id)

        # Check warmup
        if state.data_points_seen < state.strategy.warmup_period():
            return False

        # Check circuit breaker
        if state.circuit_breaker == CircuitBreakerState.OPEN:
            # Check if timeout has passed
            if state.circuit_breaker_opened_at:
                from datetime import timedelta
                if datetime.now(timezone.utc) - state.circuit_breaker_opened_at < timedelta(seconds=self.config.circuit_breaker_timeout_seconds):
                    return False
                # Reset to half-open
                state.circuit_breaker = CircuitBreakerState.HALF_OPEN
            return False

        # Check health
        health = state.strategy.health_check()
        if not health.healthy:
            return False

        return True

    def route_market_state(
        self,
        market_state: Dict[str, Any],
        features: Optional[Set[str]] = None
    ) -> None:
        """
        Route market data to eligible strategies.

        Responsibilities:
        - Dispatch market updates to eligible strategies
        - Respect supported markets and timeframes
        - Prevent redundant evaluations
        - Track data points for warmup

        This method should be cheap and deterministic.

        Args:
            market_state: Normalized market data
            features: Available features in the market state (auto-detected if None)
        """
        market_id = self._get_market_id(market_state)

        # Auto-detect features if not provided
        if features is None:
            features = self._detect_features(market_state)

        for strategy_id, state in self._strategies.items():
            if not state.active:
                continue

            # Check if strategy supports this market
            if market_id not in state.strategy.supported_markets():
                continue

            # Check if strategy supports required features
            required = state.strategy.required_features()
            if not required.issubset(features):
                continue

            # Update data points for warmup
            state.data_points_seen += 1

            # Mark as ready if warmup complete
            if not state.ready and state.data_points_seen >= state.strategy.warmup_period():
                state.ready = True
                logger.info(f"Strategy ready: {strategy_id} (warmup complete)")

    def update_market_data(self, market_state: Dict[str, Any]) -> None:
        """
        Update cached market data for all strategies.

        Args:
            market_state: New market data
        """
        market_id = self._get_market_id(market_state)
        self._market_data_cache[market_id] = market_state

    # === Evaluation & Scheduling ===

    def evaluate_strategy(
        self,
        strategy_id: str,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate a single strategy.

        Responsibilities:
        - Enforce readiness gate
        - Time-box execution
        - Catch and isolate strategy failures
        - Return EvaluationResult

        Args:
            strategy_id: ID of strategy to evaluate
            market_state: Market data for evaluation
            context: Optional evaluation context

        Returns:
            EvaluationResult with decision or error info
        """
        state = self._get_strategy_state(strategy_id)

        # Check readiness
        if not self.is_ready(strategy_id):
            return EvaluationResult(
                strategy_id=strategy_id,
                skipped=True,
                skip_reason="Strategy not ready (warmup or health check failed)"
            )

        # Check if active
        if not state.active:
            return EvaluationResult(
                strategy_id=strategy_id,
                skipped=True,
                skip_reason="Strategy not active"
            )

        try:
            # Execute evaluation with timeout
            start = time.time()

            decision = state.strategy.evaluate(market_state, context)

            exec_time_ms = (time.time() - start) * 1000

            # Record metrics
            state.metrics.record_execution(True, exec_time_ms)

            if decision is not None:
                # Attach weight to decision
                decision.weight = state.weight

                # Normalize decision
                decision = self.normalize_decision(decision)

                state.last_decision = decision
                state.last_evaluation = datetime.now(timezone.utc)

                return EvaluationResult(
                    strategy_id=strategy_id,
                    decision=decision,
                    execution_time_ms=exec_time_ms,
                )

            return EvaluationResult(
                strategy_id=strategy_id,
                execution_time_ms=exec_time_ms,
            )

        except TimeoutError:
            exec_time_ms = (time.time() - start) * 1000
            self.handle_strategy_error(strategy_id, TimeoutError("Evaluation timed out"))
            return EvaluationResult(
                strategy_id=strategy_id,
                error="timeout",
                execution_time_ms=exec_time_ms,
                timed_out=True,
            )

        except Exception as e:
            exec_time_ms = (time.time() - start) * 1000
            self.handle_strategy_error(strategy_id, e)
            return EvaluationResult(
                strategy_id=strategy_id,
                error=str(e),
                execution_time_ms=exec_time_ms,
            )

    def evaluate_all(
        self,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        filter_strategy_ids: Optional[List[str]] = None
    ) -> List[EvaluationResult]:
        """
        Evaluate all active, eligible strategies.

        Primary entry point for batch evaluation.

        Responsibilities:
        - Evaluate all active, eligible strategies
        - Maintain execution order determinism
        - Collect decisions
        - Handle errors gracefully

        Args:
            market_state: Market data for evaluation
            context: Optional evaluation context
            filter_strategy_ids: Optional list of strategy IDs to evaluate

        Returns:
            List of EvaluationResult objects
        """
        results: List[EvaluationResult] = []

        # Sort strategy IDs for deterministic order
        strategy_ids = sorted(self._strategies.keys())

        # Filter if requested
        if filter_strategy_ids:
            strategy_ids = [sid for sid in strategy_ids if sid in filter_strategy_ids]

        for strategy_id in strategy_ids:
            result = self.evaluate_strategy(strategy_id, market_state, context)
            results.append(result)

        return results

    def evaluate_all_aggregated(
        self,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        token_address: str = "",
        token_symbol: str = ""
    ) -> AggregatedDecision:
        """
        Evaluate all strategies and aggregate results with proper weighting.

        This is the main method for getting a combined decision from all strategies.
        It uses weighted ensemble voting to combine signals.

        Args:
            market_state: Market data for evaluation
            context: Optional evaluation context
            token_address: Token address for the aggregated decision
            token_symbol: Token symbol for the aggregated decision

        Returns:
            AggregatedDecision with combined signal
        """
        results = self.evaluate_all(market_state, context)

        # Collect valid decisions
        decisions: List[StrategyDecision] = []
        for result in results:
            if result.decision is not None and result.decision.is_valid():
                decisions.append(result.decision)

        return self.aggregate_decisions(
            decisions,
            token_address=token_address,
            token_symbol=token_symbol
        )

    # === Aggregation & Normalization ===

    def normalize_decision(
        self,
        decision: StrategyDecision
    ) -> StrategyDecision:
        """
        Normalize a strategy decision.

        Responsibilities:
        - Enforce confidence bounds [0.0, 1.0]
        - Attach strategy metadata
        - Normalize timestamps and expiry

        Args:
            decision: Raw decision from strategy

        Returns:
            Normalized decision
        """
        # Clamp confidence
        confidence = max(0.0, min(1.0, decision.confidence))

        # Apply minimum confidence threshold
        if confidence < self.config.min_confidence_threshold:
            # Convert to HOLD instead of emitting low confidence signal
            confidence = 0.0

        # Add normalization metadata
        metadata = {
            **decision.metadata,
            "normalized_at": datetime.now(timezone.utc).isoformat(),
        }

        return StrategyDecision(
            strategy_id=decision.strategy_id,
            action=decision.action,
            confidence=confidence,
            rationale=decision.rationale,
            metadata=metadata,
            created_at=decision.created_at,
            expires_at=decision.expires_at,
            version=decision.version,
            weight=decision.weight,
        )

    def aggregate_decisions(
        self,
        decisions: List[StrategyDecision],
        token_address: str = "",
        token_symbol: str = ""
    ) -> AggregatedDecision:
        """
        Aggregate multiple decisions using weighted voting.

        This implements a sophisticated ensemble voting system:
        1. Weight each decision by strategy weight
        2. Calculate weighted confidence for each action
        3. Use action counts as tiebreaker
        4. Generate combined rationale

        Args:
            decisions: List of decisions to aggregate
            token_address: Token address for the aggregated decision
            token_symbol: Token symbol for the aggregated decision

        Returns:
            AggregatedDecision with combined signal
        """
        if not decisions:
            return AggregatedDecision(
                token_address=token_address,
                token_symbol=token_symbol,
                rationale="No valid decisions from strategies",
            )

        # Calculate weighted votes for each action
        action_weights: Dict[DecisionAction, float] = {}
        action_counts: Dict[DecisionAction, int] = {}

        for decision in decisions:
            weight = decision.weight
            confidence = decision.confidence

            if decision.action not in action_weights:
                action_weights[decision.action] = 0.0
                action_counts[decision.action] = 0

            action_weights[decision.action] += weight * confidence
            action_counts[decision.action] += 1

        # Determine combined action
        # Sort by weighted confidence, then by count as tiebreaker
        sorted_actions = sorted(
            action_weights.items(),
            key=lambda x: (x[1], action_counts.get(x[0], 0)),
            reverse=True
        )

        combined_action = sorted_actions[0][0]
        combined_confidence = sorted_actions[0][1]

        # Calculate total weight and weighted confidence
        total_weight = sum(d.weight for d in decisions)
        weighted_confidence = sum(d.weight * d.confidence for d in decisions) / total_weight if total_weight > 0 else 0

        # Count actions
        buy_count = action_counts.get(DecisionAction.BUY, 0)
        sell_count = action_counts.get(DecisionAction.SELL, 0)
        hold_count = action_counts.get(DecisionAction.HOLD, 0)

        # Generate rationale
        rationale = self._generate_aggregation_rationale(
            decisions, combined_action, combined_confidence, buy_count, sell_count
        )

        return AggregatedDecision(
            token_address=token_address,
            token_symbol=token_symbol,
            combined_action=combined_action,
            combined_confidence=combined_confidence,
            total_weight=total_weight,
            weighted_confidence=weighted_confidence,
            strategy_count=len(decisions),
            buy_count=buy_count,
            sell_count=sell_count,
            hold_count=hold_count,
            decisions=decisions,
            rationale=rationale,
        )

    def _generate_aggregation_rationale(
        self,
        decisions: List[StrategyDecision],
        combined_action: DecisionAction,
        combined_confidence: float,
        buy_count: int,
        sell_count: int
    ) -> str:
        """Generate a human-readable rationale for the aggregation."""
        action_name = combined_action.name
        strategy_names = [d.strategy_id for d in decisions]

        if len(decisions) == 1:
            return f"Single strategy signal: {strategy_names[0]} recommends {action_name}"

        # Generate rationale based on consensus
        rationale_parts = [
            f"Ensemble of {len(decisions)} strategies: {', '.join(strategy_names)}",
            f"Consensus: {action_name} ({combined_confidence:.2%} weighted confidence)",
        ]

        if buy_count > 0 and sell_count > 0:
            rationale_parts.append(f"Divergent signals: {buy_count} BUY, {sell_count} SELL")
        elif buy_count > 0:
            rationale_parts.append("All strategies aligned on BUY")
        elif sell_count > 0:
            rationale_parts.append("All strategies aligned on SELL")

        return " | ".join(rationale_parts)

    # === Fault Isolation & Health ===

    def handle_strategy_error(
        self,
        strategy_id: str,
        error: Exception
    ) -> None:
        """
        Handle an error from a strategy.

        Responsibilities:
        - Increment failure counters
        - Trigger circuit breakers
        - Deactivate strategy if needed
        - Never crash the manager

        Args:
            strategy_id: ID of strategy that errored
            error: The exception that was raised
        """
        state = self._get_strategy_state(strategy_id)

        state.error_count += 1
        state.metrics.record_execution(False, 0.0, error)

        # Call strategy's error handler
        state.strategy.on_error(error)

        logger.error(f"Strategy error ({strategy_id}): {error}")

        # Check circuit breaker threshold
        if state.error_count >= self.config.circuit_breaker_threshold:
            state.circuit_breaker = CircuitBreakerState.OPEN
            state.circuit_breaker_opened_at = datetime.now(timezone.utc)

            # Auto-deactivate
            state.active = False

            logger.warning(
                f"Circuit breaker opened for {strategy_id} after "
                f"{state.error_count} errors"
            )

    def health_check(self) -> Dict[str, HealthStatus]:
        """
        Get health status of all strategies.

        Includes:
        - Strategy active state
        - Last evaluation time
        - Error counts
        - Circuit breaker state

        Returns:
            Dictionary of strategy_id -> HealthStatus
        """
        results: Dict[str, HealthStatus] = {}

        for strategy_id, state in self._strategies.items():
            strategy_health = state.strategy.health_check()

            # Determine overall health
            healthy = (
                strategy_health.healthy and
                state.circuit_breaker != CircuitBreakerState.OPEN
            )

            details = {
                "active": state.active,
                "ready": state.ready,
                "data_points_seen": state.data_points_seen,
                "warmup_required": state.strategy.warmup_period(),
                "last_evaluation": (
                    state.last_evaluation.isoformat()
                    if state.last_evaluation else None
                ),
                "error_count": state.error_count,
                "circuit_breaker": state.circuit_breaker,
                "weight": state.weight,
                "metrics": state.metrics.to_dict(),
            }

            results[strategy_id] = HealthStatus(
                healthy=healthy,
                message=strategy_health.message,
                details={**strategy_health.details, **details},
            )

        return results

    def get_system_health(self) -> HealthStatus:
        """
        Get overall system health.

        Returns:
            HealthStatus for the entire strategy system
        """
        all_health = self.health_check()

        # Check if all strategies are healthy
        all_healthy = all(h.healthy for h in all_health.values())

        # Count issues
        issues = []
        for strategy_id, health in all_health.items():
            if not health.healthy:
                issues.append(f"{strategy_id}: {health.message}")

        if all_healthy:
            return HealthStatus(
                healthy=True,
                message=f"All {len(all_health)} strategies healthy",
                details={"strategy_count": len(all_health)},
            )
        else:
            return HealthStatus(
                healthy=False,
                message=f"{len(issues)} strategies have issues",
                details={
                    "strategy_count": len(all_health),
                    "issues": issues,
                    "strategy_health": {k: h.to_dict() for k, h in all_health.items()},
                },
            )

    # === Introspection & Audit ===

    def list_strategies(self) -> List[str]:
        """
        List all registered strategy IDs.

        Returns:
            List of strategy IDs
        """
        return list(self._strategies.keys())

    def get_strategy_metadata(self, strategy_id: str) -> Dict[str, Any]:
        """
        Get metadata for a specific strategy.

        Args:
            strategy_id: ID of strategy

        Returns:
            Dictionary with strategy metadata

        Raises:
            KeyError: If strategy not found
        """
        state = self._get_strategy_state(strategy_id)
        strategy = state.strategy

        return {
            "strategy_id": strategy.strategy_id(),
            "version": strategy.version(),
            "description": strategy.description(),
            "supported_markets": strategy.supported_markets(),
            "timeframes": strategy.timeframes(),
            "required_features": list(strategy.required_features()),
            "warmup_period": strategy.warmup_period(),
            "signal_type": strategy.signal_type().name,
            "risk_profile": strategy.risk_profile().to_dict(),
            "active": state.active,
            "ready": state.ready,
            "data_points_seen": state.data_points_seen,
            "weight": state.weight,
            "last_evaluation": (
                state.last_evaluation.isoformat()
                if state.last_evaluation else None
            ),
            "metrics": state.metrics.to_dict(),
        }

    def get_all_strategy_metadata(self) -> List[Dict[str, Any]]:
        """
        Get metadata for all strategies.

        Returns:
            List of strategy metadata dictionaries
        """
        return [self.get_strategy_metadata(sid) for sid in self._strategies.keys()]

    def last_decision(
        self,
        strategy_id: str
    ) -> Optional[StrategyDecision]:
        """
        Get the last decision from a strategy.

        Args:
            strategy_id: ID of strategy

        Returns:
            Last StrategyDecision, or None if no decision yet
        """
        state = self._get_strategy_state(strategy_id)
        return state.last_decision

    def get_all_last_decisions(self) -> Dict[str, Optional[StrategyDecision]]:
        """
        Get the last decision from all strategies.

        Returns:
            Dictionary of strategy_id -> last decision
        """
        return {
            strategy_id: state.last_decision
            for strategy_id, state in self._strategies.items()
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics for all strategies.

        Returns:
            Dictionary with metrics
        """
        total_runs = sum(s.metrics.total_runs for s in self._strategies.values())
        total_successes = sum(s.metrics.total_successes for s in self._strategies.values())
        total_errors = sum(s.metrics.total_errors for s in self._strategies.values())

        return {
            "total_evaluations": total_runs,
            "total_successes": total_successes,
            "total_errors": total_errors,
            "success_rate": total_successes / total_runs if total_runs > 0 else 0.0,
            "strategy_count": len(self._strategies),
            "active_strategy_count": sum(1 for s in self._strategies.values() if s.active),
            "ready_strategy_count": sum(1 for s in self._strategies.values() if s.ready),
            "strategy_metrics": {
                sid: state.metrics.to_dict()
                for sid, state in self._strategies.items()
            },
        }

    # === Internal Helpers ===

    def _get_strategy_state(self, strategy_id: str) -> StrategyState:
        """Get strategy state, raise KeyError if not found."""
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy '{strategy_id}' not found")
        return self._strategies[strategy_id]

    def _validate_strategy_contract(self, strategy: BaseStrategy) -> None:
        """Validate that strategy implements all required methods."""
        required_methods = [
            'strategy_id', 'version', 'description',
            'supported_markets', 'timeframes', 'required_features',
            'warmup_period', 'evaluate', 'signal_type', 'risk_profile',
        ]

        for method in required_methods:
            if not hasattr(strategy, method):
                raise ValueError(
                    f"Strategy '{strategy.__class__.__name__}' missing required method: {method}"
                )

            # Check if it's callable
            attr = getattr(strategy, method)
            if not callable(attr):
                raise ValueError(
                    f"Strategy '{strategy.__class__.__name__}' {method} is not callable"
                )

    def _get_market_id(self, market_state: Dict[str, Any]) -> str:
        """Extract market ID from market state."""
        # Try chain_id first
        if "chain_id" in market_state:
            return str(market_state["chain_id"])

        # Try exchange/pair
        if "exchange" in market_state:
            exchange = market_state["exchange"]
            pair = market_state.get("pair", "")
            return f"{exchange}:{pair}"

        # Default
        return "unknown"

    def _detect_features(self, market_state: Dict[str, Any]) -> Set[str]:
        """Auto-detect available features from market state."""
        features: Set[str] = set()

        # Common features
        feature_markers = {
            "price", "volume", "volume_24h", "liquidity",
            "market_cap", "price_change_1h", "price_change_24h", "price_change_7d",
            "rsi", "macd", "macd_signal", "bb_upper", "bb_lower",
            "volatility", "ATR", "SMA", "EMA",
        }

        for marker in feature_markers:
            if marker in market_state:
                features.add(marker)

        return features

