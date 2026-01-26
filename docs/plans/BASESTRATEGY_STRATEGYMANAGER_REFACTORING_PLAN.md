# BaseStrategy & StrategyManager Refactoring Plan

## Executive Summary

This document outlines the comprehensive refactoring of the `BaseStrategy` and `StrategyManager` to follow a clean, production-grade architecture where:
- **BaseStrategy** is a pure, opinionated contract that produces intent, never action
- **StrategyManager** is the authoritative orchestration layer between strategies and downstream consumers

---

## Part 1: Current State Analysis

### Current BaseStrategy Issues

| Issue | Location | Impact |
|-------|----------|--------|
| Returns trade signal dict with execution details | `_create_signal()` | Violates separation of concerns |
| Missing identity methods | N/A | No strategy_id, version, description |
| Missing capability declaration | N/A | No supported_markets, timeframes, required_features |
| evaluate_token returns raw dict | `evaluate_token()` | Not a structured StrategyDecision |
| Contains position sizing logic | `EliteMomentumStrategy` | Risk enforcement belongs to external layer |

### Current EliteStrategyManager Issues

| Issue | Location | Impact |
|-------|----------|--------|
| No proper registration/deregistration | `__init__()` | No lifecycle control |
| No activation/deactivation | N/A | Can't hot-enable/disable strategies |
| No market state routing | N/A | No proper data routing |
| Missing readiness checks | N/A | No warmup period enforcement |
| Missing health reporting | N/A | No observability |
| Missing introspection | N/A | No list_strategies, get_strategy_metadata |

---

## Part 2: Target Architecture

### BaseStrategy Responsibilities

```
┌─────────────────────────────────────────────────────────────────┐
│                        BaseStrategy                              │
├─────────────────────────────────────────────────────────────────┤
│  CONSUME:    • Normalized market data                           │
│  APPLY:      • Strategy-specific logic                          │
│  PRODUCE:    • Strategy decisions (not trades)                  │
│  DECLARE:    • Constraints and metadata                         │
├─────────────────────────────────────────────────────────────────┤
│  MUST NOT:                                                   │
│  • Execute trades                                             │
│  • Manage capital                                             │
│  • Handle retries, throttling, circuit breaking                │
│  • Coordinate other strategies                                 │
│  • Touch exchange adapters or wallets                          │
└─────────────────────────────────────────────────────────────────┘
```

### StrategyManager Responsibilities

```
┌─────────────────────────────────────────────────────────────────┐
│                      StrategyManager                             │
├─────────────────────────────────────────────────────────────────┤
│  LIFECYCLE:   • Register/deregister strategies                  │
│               • Activate/deactivate strategies                   │
│  ROUTING:     • Route market data to eligible strategies        │
│               • Enforce warmup and feature readiness            │
│  EVALUATION:  • Controlled evaluation scheduling                 │
│               • Signal normalization and aggregation            │
│  FAULT ISOLATION: • Error handling and health reporting         │
│  INTROSPECTION:   • List strategies, get metadata               │
├─────────────────────────────────────────────────────────────────┤
│  MUST NOT:                                                   │
│  • Contain trading logic                                       │
│  • Modify strategy internals                                    │
│  • Enforce risk rules (only gate)                              │
│  • Create TradeIntents                                         │
│  • Touch execution infrastructure                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Required Changes

### 3.1 New Data Classes (strategies/base_strategy.py)

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod

class SignalType(Enum):
    """Directional classification of strategy signals."""
    DIRECTIONAL = auto()      # Buy/Sell direction
    MEAN_REVERSION = auto()   # Mean reversion signal
    BREAKOUT = auto()         # Breakout signal
    NEUTRAL = auto()          # No action

@dataclass
class RiskProfile:
    """Risk declaration for a strategy (not enforcement)."""
    max_drawdown: float = 0.20          # 20% max drawdown
    max_concurrent_positions: int = 5   # Max concurrent positions
    volatility_tolerance: float = 2.0    # Max volatility multiplier
    min_confidence_threshold: float = 0.5  # Min confidence to emit

@dataclass
class StrategyMetadata:
    """Metadata about a strategy."""
    strategy_id: str
    version: str
    description: str
    supported_markets: List[str]
    timeframes: List[str]
    required_features: Set[str]
    warmup_period: int
    signal_type: SignalType
    risk_profile: RiskProfile
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class StrategyDecision:
    """
    Core output of strategy evaluation.
    Contains intent, not action.
    """
    strategy_id: str
    action: SignalType
    confidence: float  # 0.0 to 1.0
    rationale: Dict[str, Any]  # Structured reasoning
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    version: str = "1.0.0"

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "action": self.action.name if isinstance(self.action, SignalType) else self.action,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
        }

@dataclass
class HealthStatus:
    """Health status for a component."""
    healthy: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
```

### 3.2 Refactored BaseStrategy (strategies/base_strategy.py)

```python
class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    A strategy produces intent, never action. This keeps the system:
    - Auditable: Every decision is traceable
    - Testable: Pure functions without side effects
    - Composable: Multiple strategies can be combined

    Core Design Principle: A strategy produces StrategyDecision objects,
    never raw signals or trade intents.
    """

    # Subclasses must implement these abstract methods

    @abstractmethod
    def strategy_id(self) -> str:
        """
        Globally unique strategy identifier.

        Returns:
            Unique ID like 'momentum_v1', 'mean_reversion_elite', etc.
        """
        ...

    @abstractmethod
    def version(self) -> str:
        """
        Semantic version of the strategy logic.

        Returns:
            Semantic version string (e.g., '1.0.0')
        """
        ...

    @abstractmethod
    def description(self) -> str:
        """
        Human-readable explanation of strategy intent.

        Returns:
            Plain text description of what the strategy does
        """
        ...

    @abstractmethod
    def supported_markets(self) -> List[str]:
        """
        Chains/exchanges/instruments supported by this strategy.

        Returns:
            List like ['ethereum', 'base', 'solana'] or ['uniswap_v3', 'pancakeswap']
        """
        ...

    @abstractmethod
    def timeframes(self) -> List[str]:
        """
        Expected candle or tick intervals.

        Returns:
            List like ['1m', '5m', '1h', '4h']
        """
        ...

    @abstractmethod
    def required_features(self) -> Set[str]:
        """
        Market features required for evaluation.

        Returns:
            Set like {'price', 'volume', 'rsi', 'macd'}
        """
        ...

    @abstractmethod
    def warmup_period(self) -> int:
        """
        Minimum data points before evaluation can begin.

        Returns:
            Number of data points required before first decision
        """
        ...

    @abstractmethod
    def evaluate(
        self,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategyDecision]:
        """
        Core logic: converts market state into a decision.

        This is the heart of the strategy. Output must be:
        - Deterministic: Same input → same output
        - Side-effect free: No external state changes
        - Stateless or explicitly state-aware

        Args:
            market_state: Normalized market data dictionary
            context: Optional strategy context (e.g., portfolio state)

        Returns:
            StrategyDecision if signal generated, None otherwise
        """
        ...

    @abstractmethod
    def signal_type(self) -> SignalType:
        """
        Classification of signal type.

        Returns:
            SignalType enum value
        """
        ...

    @abstractmethod
    def risk_profile(self) -> RiskProfile:
        """
        Declares acceptable risk bounds (enforcement is external).

        Returns:
            RiskProfile with declared risk parameters
        """
        ...

    # Optional lifecycle hooks (default implementations)

    def on_start(self) -> None:
        """Called when strategy is activated."""
        pass

    def on_stop(self) -> None:
        """Graceful shutdown hook."""
        pass

    def on_error(self, error: Exception) -> None:
        """Strategy-local error handling."""
        pass

    def health_check(self) -> HealthStatus:
        """Strategy self-diagnostics."""
        return HealthStatus(healthy=True, message="Strategy is operational")

    # Default implementation for confidence calculation
    def confidence_score(self) -> float:
        """
        Returns normalized confidence [0.0–1.0] for weighting/ranking.

        Subclasses can override this for custom confidence calculation.
        """
        return 0.5  # Default neutral confidence
```

### 3.3 New StrategyManager (strategies/strategy_manager.py)

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from enum import Enum, auto

class CircuitBreakerState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()

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
    circuit_breaker: CircuitBreakerState = CircuitBreakerState.CLOSED

@dataclass
class StrategyManagerMetrics:
    """Metrics for the strategy manager."""
    total_evaluations: int = 0
    total_decisions: int = 0
    total_errors: int = 0
    average_evaluation_time_ms: float = 0.0

class StrategyManager:
    """
    Orchestration layer between strategies and downstream consumers.

    Responsibilities:
    - Lifecycle management of strategies
    - Data routing and feature readiness checks
    - Controlled evaluation scheduling
    - Signal normalization and aggregation
    - Fault isolation and health enforcement
    - Emitting StrategyDecisions, not trades
    """

    def __init__(
        self,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_timeout: float = 60.0,
        evaluation_timeout_seconds: float = 3.0,
    ):
        self._strategies: Dict[str, StrategyState] = {}
        self._metrics = StrategyManagerMetrics()
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_timeout = circuit_breaker_timeout
        self._evaluation_timeout = evaluation_timeout_seconds

    # === Strategy Registry & Lifecycle ===

    def register_strategy(self, strategy: BaseStrategy) -> None:
        """
        Register a new strategy with the manager.

        Responsibilities:
        - Validate strategy contract
        - Enforce unique strategy_id
        - Validate required features
        - Initialize internal state

        Args:
            strategy: BaseStrategy implementation to register

        Raises:
            ValueError: If strategy_id already exists or contract invalid
        """
        strategy_id = strategy.strategy_id()

        if strategy_id in self._strategies:
            raise ValueError(f"Strategy '{strategy_id}' already registered")

        # Validate required methods
        self._validate_strategy_contract(strategy)

        # Initialize strategy state
        self._strategies[strategy_id] = StrategyState(strategy=strategy)

        # Call on_start lifecycle hook
        strategy.on_start()

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
            return False

        # Check health
        health = state.strategy.health_check()
        if not health.healthy:
            return False

        return True

    def route_market_state(
        self,
        market_state: Dict[str, Any],
        features: Set[str]
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
            features: Available features in the market state
        """
        market_id = self._get_market_id(market_state)

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
            if state.ready:
                continue

            if state.data_points_seen >= state.strategy.warmup_period():
                state.ready = True

    # === Evaluation & Scheduling ===

    def evaluate_strategy(
        self,
        strategy_id: str,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategyDecision]:
        """
        Evaluate a single strategy.

        Responsibilities:
        - Enforce readiness gate
        - Time-box execution
        - Catch and isolate strategy failures
        - Return one StrategyDecision or None

        No retries here. Fail fast.

        Args:
            strategy_id: ID of strategy to evaluate
            market_state: Market data for evaluation
            context: Optional evaluation context

        Returns:
            StrategyDecision if generated, None otherwise
        """
        state = self._get_strategy_state(strategy_id)

        # Check readiness
        if not self.is_ready(strategy_id):
            return None

        # Check circuit breaker
        if state.circuit_breaker == CircuitBreakerState.OPEN:
            return None

        try:
            # Execute evaluation with timeout
            import time
            start = time.time()

            decision = state.strategy.evaluate(market_state, context)

            exec_time = (time.time() - start) * 1000  # ms

            # Update metrics
            self._metrics.total_evaluations += 1
            self._update_avg_evaluation_time(exec_time)

            if decision is not None:
                # Validate and normalize decision
                decision = self.normalize_decision(decision)
                state.last_decision = decision
                state.last_evaluation = datetime.now(timezone.utc)
                self._metrics.total_decisions += 1

            return decision

        except Exception as e:
            self._handle_strategy_error(strategy_id, e)
            return None

    def evaluate_all(
        self,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[StrategyDecision]:
        """
        Evaluate all active, eligible strategies.

        Primary entry point for batch evaluation.

        Responsibilities:
        - Evaluate all active, eligible strategies
        - Maintain execution order determinism
        - Collect decisions
        - Drop invalid or stale decisions

        Args:
            market_state: Market data for evaluation
            context: Optional evaluation context

        Returns:
            List of StrategyDecision objects
        """
        decisions: List[StrategyDecision] = []

        # Sort strategy IDs for deterministic order
        for strategy_id in sorted(self._strategies.keys()):
            decision = self.evaluate_strategy(strategy_id, market_state, context)
            if decision is not None:
                decisions.append(decision)

        # Optional aggregation
        return self.aggregate(decisions)

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

        No logic mutation allowed.

        Args:
            decision: Raw decision from strategy

        Returns:
            Normalized decision
        """
        # Clamp confidence
        confidence = max(0.0, min(1.0, decision.confidence))

        # Add metadata
        metadata = {
            **decision.metadata,
            "normalized_at": datetime.now(timezone.utc).isoformat(),
            "strategy_version": decision.version,
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
        )

    def aggregate(
        self,
        decisions: List[StrategyDecision]
    ) -> List[StrategyDecision]:
        """
        Aggregate multiple decisions.

        Examples:
        - Deduplication
        - Conflict tagging
        - Ensemble voting (optional)

        Aggregation must be explicit, never implicit.

        Args:
            decisions: List of decisions to aggregate

        Returns:
            Aggregated decisions
        """
        # Default: return as-is (can be extended for voting/aggregation)
        return decisions

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
        self._metrics.total_errors += 1

        # Call strategy's error handler
        state.strategy.on_error(error)

        # Check circuit breaker threshold
        if state.error_count >= self._circuit_breaker_threshold:
            state.circuit_breaker = CircuitBreakerState.OPEN

            # Auto-deactivate
            state.active = False

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
                "circuit_breaker": state.circuit_breaker.name,
            }

            results[strategy_id] = HealthStatus(
                healthy=healthy,
                message=strategy_health.message,
                details={**strategy_health.details, **details},
            )

        return results

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
            "risk_profile": {
                "max_drawdown": strategy.risk_profile().max_drawdown,
                "max_concurrent_positions": strategy.risk_profile().max_concurrent_positions,
                "volatility_tolerance": strategy.risk_profile().volatility_tolerance,
            },
            "active": state.active,
            "ready": state.ready,
            "last_evaluation": (
                state.last_evaluation.isoformat()
                if state.last_evaluation else None
            ),
        }

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

    def _update_avg_evaluation_time(self, new_time_ms: float) -> None:
        """Update running average of evaluation time."""
        current = self._metrics.average_evaluation_time_ms
        count = self._metrics.total_evaluations
        self._metrics.average_evaluation_time_ms = (
            (current * (count - 1) + new_time_ms) / count
        )
```

---

## Part 4: Migration Plan

### Phase 1: Create New Files
1. Create `strategies/data_classes.py` with StrategyDecision, RiskProfile, etc.
2. Create `strategies/strategy_manager.py` with new StrategyManager
3. Update `strategies/__init__.py` to export new classes

### Phase 2: Update BaseStrategy
1. Add new abstract methods (strategy_id, version, description, etc.)
2. Change `evaluate_token` to `evaluate` returning StrategyDecision
3. Remove execution concerns (stop_loss, take_profit, position_size)
4. Keep `_create_signal` for backward compatibility during transition

### Phase 3: Update Concrete Strategies
1. Update `EliteMomentumStrategy` to implement new interface
2. Update `EliteMeanReversionStrategy` similarly
3. Update all other strategy implementations

### Phase 4: Update EliteStrategyManager
1. Keep backward compatibility with existing interface
2. Wrap new StrategyManager internally
3. Gradually migrate callers to new interface

### Phase 5: Update Callers
1. Update `ai/elite_ai_controller.py`
2. Update `ai/elite_async_ai_controller.py`
3. Update any other callers

---

## Part 5: Backward Compatibility

### During Transition
- Keep old `evaluate_token` method with deprecation warning
- Add new `evaluate` method returning StrategyDecision
- Old code continues to work

### After Transition
- Remove deprecated methods
- Update all callers to new interface

---

## Files to Create/Modify

### New Files
1. `strategies/data_classes.py` - New data classes
2. `strategies/strategy_manager.py` - New StrategyManager

### Files to Modify
1. `strategies/base_strategy.py` - Add new abstract methods
2. `strategies/__init__.py` - Export new classes
3. `strategies/features/momentum.py` - Implement new interface
4. `strategies/features/mean_reversion.py` - Implement new interface
5. `strategies/features/breakout.py` - Implement new interface
6. `strategies/features/aggressive.py` - Implement new interface
7. `strategies/features/safe.py` - Implement new interface
8. `strategies/features/smart_money.py` - Implement new interface
9. `strategies/features/volatility_breakout.py` - Implement new interface
10. `strategies/elite_strategy_manager.py` - Wrap new StrategyManager
11. `ai/elite_ai_controller.py` - Update to use new interface
12. `ai/elite_async_ai_controller.py` - Update to use new interface

---

## Summary

This refactoring will:

1. **Enforce Clean Architecture**
   - BaseStrategy produces intent only
   - StrategyManager orchestrates without execution

2. **Improve Testability**
   - Pure functions without side effects
   - Easy to mock and test in isolation

3. **Enhance Observability**
   - Health checks for all strategies
   - Metrics and introspection APIs
   - Audit trail for all decisions

4. **Enable Composability**
   - Multiple strategies can be combined
   - Aggregation and voting systems

5. **Improve Reliability**
   - Circuit breakers for fault isolation
   - Graceful error handling
   - Hot-reload capability

The result will be a production-grade system that is auditable, testable, and composable.

