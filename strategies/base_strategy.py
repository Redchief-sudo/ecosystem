from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from .data_classes import (
    SignalType as NewSignalType,
    DecisionAction,
    RiskProfile,
    StrategyDecision,
    Rationale,
    HealthStatus,
)


class SignalType(Enum):
    BUY = auto()
    SELL = auto()
    NEUTRAL = auto()


@dataclass
class TradeSignal:
    """
    Standardized signal returned by strategies.
    """
    strategy_id: str
    signal_type: SignalType
    confidence: float
    score: float
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_size: float = 0.0
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    This class defines the contract that all strategies must implement.
    It provides both the new clean interface (StrategyDecision-based) and
    backward compatibility with the old interface (TradeSignal-based).

    Core Design Principle: A strategy produces intent, never action.
    This keeps the system auditable, testable, and composable.
    """

    IS_STRATEGY = True
    STRATEGY_NAME = "base"

    def __init__(self, strategy_config: Dict[str, Any], global_config: Dict[str, Any]):
        self.strategy_config = strategy_config
        self.global_config = global_config
        # Runtime enabled/disabled state (can be changed at runtime)
        self.enabled = strategy_config.get("enabled", True) if strategy_config else True

    def _safe(self, data, key, default=None):
        """Safely extract value from dictionary."""
        if not isinstance(data, dict):
            return default
        return data.get(key, default)

    # === NEW CLEAN INTERFACE (StrategyDecision-based) ===

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
    def signal_type(self) -> NewSignalType:
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

    # === OPTIONAL LIFECYCLE HOOKS ===

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

    # === BACKWARD COMPATIBILITY (TradeSignal-based) ===

    async def evaluate_token(self, token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        LEGACY METHOD - DEPRECATED

        This method is kept for backward compatibility during transition.
        New strategies should implement evaluate() instead.

        Args:
            token_data: Token data dictionary

        Returns:
            TradeSignal dictionary or None
        """
        import warnings
        warnings.warn(
            f"{self.__class__.__name__}.evaluate_token() is deprecated. "
            "Implement evaluate() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        # Try to convert new interface to old interface
        try:
            decision = self.evaluate(token_data)
            if decision is None:
                return None

            # Convert StrategyDecision to TradeSignal format
            return self._strategy_decision_to_trade_signal(decision, token_data)
        except Exception:
            # Fallback to old implementation if available
            return await self._legacy_evaluate_token(token_data)

    def _legacy_evaluate_token(self, token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Legacy implementation for backward compatibility.
        Subclasses can override this if they don't implement evaluate().
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement either evaluate() or _legacy_evaluate_token()"
        )

    def _strategy_decision_to_trade_signal(
        self,
        decision: StrategyDecision,
        market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert a StrategyDecision to the old TradeSignal format.

        This is used for backward compatibility during the transition.
        """
        # Map DecisionAction to SignalType
        signal_type_map = {
            DecisionAction.BUY: SignalType.BUY,
            DecisionAction.SELL: SignalType.SELL,
            DecisionAction.HOLD: SignalType.NEUTRAL,
            DecisionAction.REDUCE: SignalType.SELL,
            DecisionAction.CLOSE: SignalType.SELL,
        }

        signal_type = signal_type_map.get(decision.action, SignalType.NEUTRAL)

        # Extract price and other data
        price = market_state.get("price", 0.0)

        # Create basic position sizing (this would normally be done externally)
        position_size = decision.confidence * 0.01  # Conservative sizing

        # Basic risk management (this would normally be done externally)
        stop_loss = price * 0.95 if signal_type == SignalType.BUY else price * 1.05
        take_profit = price * 1.05 if signal_type == SignalType.BUY else price * 0.95

        return self._create_signal(
            signal_type=signal_type,
            confidence=decision.confidence,
            price=price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                "strategy_decision": decision.to_dict(),
                "rationale": decision.rationale.to_dict(),
            }
        )

    def _create_signal(
        self,
        signal_type: SignalType,
        confidence: float,
        price: float,
        position_size: float,
        stop_loss: float,
        take_profit: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TradeSignal:
        """
        Create a standardized trade signal as a TradeSignal dataclass.

        Args:
            signal_type: SignalType (BUY, SELL, NEUTRAL)
            confidence: Confidence score (0-1)
            price: Current token price
            position_size: Position size as fraction of portfolio
            stop_loss: Stop loss price
            take_profit: Take profit price
            metadata: Additional signal metadata

        Returns:
            TradeSignal object
        """
        # Calculate score based on confidence and position size
        score = confidence * (1 + position_size)

        return TradeSignal(
            strategy_id=self.STRATEGY_NAME,
            signal_type=signal_type,
            confidence=confidence,
            score=score,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            metadata=metadata or {},
        )

