"""
Data classes for the strategy system.

This module contains all the data structures used by BaseStrategy and StrategyManager.
These are pure data containers with no business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class SignalType(Enum):
    """
    Directional classification of strategy signals.

    - DIRECTIONAL: Buy/Sell direction signals
    - MEAN_REVERSION: Mean reversion signals
    - BREAKOUT: Breakout signals
    - NEUTRAL: No action signal
    """
    DIRECTIONAL = auto()
    MEAN_REVERSION = auto()
    BREAKOUT = auto()
    NEUTRAL = auto()


class DecisionAction(Enum):
    """
    Action to take based on strategy decision.
    """
    BUY = auto()
    SELL = auto()
    HOLD = auto()
    REDUCE = auto()  # Reduce position size
    CLOSE = auto()   # Close position completely


@dataclass
class RiskProfile:
    """
    Risk declaration for a strategy (not enforcement).

    This declares the acceptable risk bounds for a strategy.
    Enforcement is handled by external risk management layers.
    """
    max_drawdown: float = 0.20              # 20% max drawdown
    max_concurrent_positions: int = 5       # Max concurrent positions
    volatility_tolerance: float = 2.0        # Max volatility multiplier
    min_confidence_threshold: float = 0.5   # Min confidence to emit signal
    max_position_size: float = 0.02         # Max 2% of portfolio per position
    max_loss_per_trade: float = 0.01        # Max 1% loss per trade
    risk_per_trade: float = 0.005           # 0.5% risk per trade

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_drawdown": self.max_drawdown,
            "max_concurrent_positions": self.max_concurrent_positions,
            "volatility_tolerance": self.volatility_tolerance,
            "min_confidence_threshold": self.min_confidence_threshold,
            "max_position_size": self.max_position_size,
            "max_loss_per_trade": self.max_loss_per_trade,
            "risk_per_trade": self.risk_per_trade,
        }


@dataclass
class StrategyMetadata:
    """
    Metadata about a strategy.

    Contains all the identity and capability information for a strategy.
    """
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "description": self.description,
            "supported_markets": self.supported_markets,
            "timeframes": self.timeframes,
            "required_features": list(self.required_features),
            "warmup_period": self.warmup_period,
            "signal_type": self.signal_type.name,
            "risk_profile": self.risk_profile.to_dict(),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class Rationale:
    """
    Structured reasoning for a strategy decision.

    This replaces free-text explanations with structured data
    for better auditability and analysis.
    """
    primary_reason: str                          # Main reason for the decision
    indicators_used: List[str] = field(default_factory=list)  # Technical indicators
    factors: Dict[str, float] = field(default_factory=dict)   # Factor values
    market_conditions: str = ""                  # e.g., "trending", "ranging", "volatile"
    regime_confidence: float = 0.5               # Confidence in regime detection
    additional_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_reason": self.primary_reason,
            "indicators_used": self.indicators_used,
            "factors": self.factors,
            "market_conditions": self.market_conditions,
            "regime_confidence": self.regime_confidence,
            "additional_notes": self.additional_notes,
        }


@dataclass
class StrategyDecision:
    """
    Core output of strategy evaluation.

    Contains intent, not action. This is the clean contract between
    strategies and the StrategyManager.

    The decision includes:
    - What action to take (BUY/SELL/HOLD)
    - How confident the strategy is (0.0 to 1.0)
    - Why the decision was made (structured rationale)
    - When the decision expires
    - Metadata for auditing
    """
    strategy_id: str
    action: DecisionAction
    confidence: float  # 0.0 to 1.0
    rationale: Rationale
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    version: str = "1.0.0"
    weight: float = 1.0  # Strategy weight for aggregation

    def is_expired(self) -> bool:
        """Check if the decision has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self) -> bool:
        """Check if the decision is valid (not expired, reasonable confidence)."""
        if self.is_expired():
            return False
        if not (0.0 <= self.confidence <= 1.0):
            return False
        if self.action == DecisionAction.HOLD and self.confidence < 0.5:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "action": self.action.name if isinstance(self.action, DecisionAction) else self.action,
            "confidence": self.confidence,
            "rationale": self.rationale.to_dict(),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyDecision":
        """Create a StrategyDecision from a dictionary."""
        action = data.get("action", "HOLD")
        if isinstance(action, str):
            action = DecisionAction[action.upper()]

        rationale = data.get("rationale", {})
        if isinstance(rationale, dict):
            rationale = Rationale(**rationale)

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        expires_at = data.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)

        return cls(
            strategy_id=data["strategy_id"],
            action=action,
            confidence=data["confidence"],
            rationale=rationale,
            metadata=data.get("metadata", {}),
            created_at=created_at or datetime.now(timezone.utc),
            expires_at=expires_at,
            version=data.get("version", "1.0.0"),
            weight=data.get("weight", 1.0),
        )


@dataclass
class AggregatedDecision:
    """
    Result of aggregating multiple strategy decisions.

    This combines signals from multiple strategies into a single
    weighted decision.
    """
    token_address: str = ""
    token_symbol: str = ""
    combined_action: DecisionAction = DecisionAction.HOLD
    combined_confidence: float = 0.0
    total_weight: float = 0.0
    weighted_confidence: float = 0.0
    strategy_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0
    decisions: List[StrategyDecision] = field(default_factory=list)
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "combined_action": self.combined_action.name,
            "combined_confidence": self.combined_confidence,
            "total_weight": self.total_weight,
            "weighted_confidence": self.weighted_confidence,
            "strategy_count": self.strategy_count,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "hold_count": self.hold_count,
            "decisions": [d.to_dict() for d in self.decisions],
            "rationale": self.rationale,
            "metadata": self.metadata,
        }


@dataclass
class HealthStatus:
    """
    Health status for a component.

    Used for monitoring strategy and system health.
    """
    healthy: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EvaluationResult:
    """
    Result of evaluating a strategy.

    Contains both the decision (if any) and metadata about the evaluation.
    """
    strategy_id: str
    decision: Optional[StrategyDecision] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timed_out: bool = False
    skipped: bool = False
    skip_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "decision": self.decision.to_dict() if self.decision else None,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "timed_out": self.timed_out,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


@dataclass
class StrategyMetrics:
    """
    Metrics for a single strategy.
    """
    consecutive_failures: int = 0
    total_runs: int = 0
    total_successes: int = 0
    total_errors: int = 0
    total_time_ms: float = 0.0
    last_evaluation: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[datetime] = None

    def record_execution(
        self,
        success: bool,
        execution_time_ms: float,
        error: Optional[Exception] = None
    ) -> None:
        """Record an execution result."""
        self.total_runs += 1
        self.total_time_ms += execution_time_ms
        self.last_evaluation = datetime.now(timezone.utc)

        if success:
            self.total_successes += 1
            self.consecutive_failures = 0
            self.last_success = self.last_evaluation
        else:
            self.total_errors += 1
            self.consecutive_failures += 1
            self.last_error = self.last_evaluation

    @property
    def success_rate(self) -> float:
        """Calculate the success rate."""
        if self.total_runs == 0:
            return 0.0
        return self.total_successes / self.total_runs

    @property
    def average_execution_time_ms(self) -> float:
        """Calculate the average execution time."""
        if self.total_runs == 0:
            return 0.0
        return self.total_time_ms / self.total_runs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consecutive_failures": self.consecutive_failures,
            "total_runs": self.total_runs,
            "total_successes": self.total_successes,
            "total_errors": self.total_errors,
            "total_time_ms": self.total_time_ms,
            "success_rate": self.success_rate,
            "average_execution_time_ms": self.average_execution_time_ms,
            "last_evaluation": (
                self.last_evaluation.isoformat()
                if self.last_evaluation else None
            ),
            "last_success": (
                self.last_success.isoformat()
                if self.last_success else None
            ),
            "last_error": (
                self.last_error.isoformat()
                if self.last_error else None
            ),
        }


@dataclass
class TradeSignal:
    """
    Trade signal for execution system.
    
    Contains all information needed for trade execution including
    entry/exit signals, position sizing, and risk parameters.
    """
    token_address: str
    chain: str
    action: DecisionAction  # BUY/SELL/HOLD
    confidence: float  # 0.0 to 1.0
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    position_size: float = 0.0  # Position size in base currency
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if signal is valid for execution."""
        if not (0.0 <= self.confidence <= 1.0):
            return False
        if self.position_size <= 0:
            return False
        if not self.token_address or not self.chain:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_address": self.token_address,
            "chain": self.chain,
            "action": self.action.name if isinstance(self.action, DecisionAction) else self.action,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "position_size": self.position_size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "timestamp": self.timestamp.isoformat(),
            "strategy_id": self.strategy_id,
            "metadata": self.metadata,
        }

