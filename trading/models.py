"""
Canonical data models for the trading system.

This module defines the core data contracts used across all trading system components.
All models are immutable dataclasses with validation to ensure data integrity.
"""
import hashlib
import json
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from decimal import Decimal
# Execution models moved here to avoid circular imports
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass(frozen=True)
class TradeIntent:
    """
    Represents a planned trade based on strategy decision.
    This object bridges StrategyDecision -> ExecutionPlan

    FROZEN: Immutable - once created by optimizer, cannot be modified.
    This ensures the optimizer remains the single source of truth.
    """
    symbol: str
    side: TradeSide
    amount_usd: float
    entry_price: float
    stop_loss: float
    take_profit: float
    strategy_name: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    token_address: Optional[str] = None
    chain: Optional[str] = None
    plan_id: Optional[str] = None  # Execution plan identifier
    urgency: str = "normal"  # Execution urgency: "low", "normal", "high"

    # Derived property for optimizer compatibility
    @property
    def is_buy(self) -> bool:
        return self.side == TradeSide.BUY

    @classmethod
    def from_strategy_decision(cls, symbol: str, decision):
        """
        DEPRECATED: Use TradeOptimizer._build_trade_intent() instead.
        This factory method is kept for backward compatibility.
        """
        # Default logic if strategy doesn't provide side
        side = getattr(decision, "side", None)
        if side is None:
            # Infer side from strategy name / risk preference
            # Example: Aggressive / Momentum -> BUY
            side = "buy"

        return cls(
            symbol=symbol,
            side=TradeSide(side),
            amount_usd=getattr(decision, "size", 0.0),
            entry_price=getattr(decision, "entry", 0.0),
            stop_loss=getattr(decision, "stop_loss", 0.0),
            take_profit=getattr(decision, "take_profit", 0.0),
            strategy_name=getattr(decision, "strategy", None),
            confidence=getattr(decision, "confidence", 0.0),
            reasoning=getattr(decision, "reasoning", None),
            token_address=getattr(decision, "token_address", ''),
            chain=getattr(decision, "chain", ''),
        )

    def to_execution_plan_dict(self):
        """
        Converts this TradeIntent to the dict format required by ExecutionPlan
        """
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "amount_usd": self.amount_usd,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "strategy_name": self.strategy_name,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "token_address": self.token_address,
            "chain": self.chain,
        }

    def __repr__(self):
        return (
            f"<TradeIntent symbol={self.symbol} side={self.side} "
            f"amount_usd={self.amount_usd:.2f} entry={self.entry_price:.6f} "
            f"stop_loss={self.stop_loss:.6f} take_profit={self.take_profit:.6f} "
            f"strategy={self.strategy_name} confidence={self.confidence:.2f}>"
        )

# Type aliases
TokenAddress = str
ChainID = int
Symbol = str

class DecisionOutcome(str, Enum):
    """The possible outcomes of a trading decision."""
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"

class AssetClass(str, Enum):
    """Classification of tradable assets."""
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCK = "stock"
    COMMODITY = "commodity"

class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    """Order types for trade execution."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class TimeInForce(str, Enum):
    """Time in force for orders."""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"   # Immediate or Cancel
    FOK = "FOK"   # Fill or Kill
    DAY = "DAY"   # Day order

@dataclass(frozen=True)
class TokenInfo:
    """Immutable representation of a token's identity."""
    symbol: Symbol
    address: TokenAddress
    chain_id: ChainID
    decimals: int = 18
    name: Optional[str] = None
    asset_class: AssetClass = AssetClass.CRYPTO
    
    def __post_init__(self):
        self._validate()
    
    def _validate(self):
        # Accept both EVM and non-EVM address formats
        if not self.address:
            raise ValueError("Token address cannot be empty")
        
        # For EVM chains, validate 0x format (but allow special MEV addresses and other formats)
        if self.chain_id in [1, 56, 137, 42161, 43114, 10]:  # Ethereum, BSC, Polygon, etc.
            # Allow special address formats that start with common prefixes
            special_prefixes = ['mev_', 'factory/', 'ibc/', 'aaaaaa']
            # Also allow any non-0x address that's at least 8 chars (for cross-chain compatibility)
            if not self.address.startswith("0x") and not any(self.address.startswith(prefix) for prefix in special_prefixes):
                if len(self.address) < 8:
                    raise ValueError(f"Invalid token address (too short): {self.address}")
                # Log a warning but don't fail for non-standard addresses
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Non-standard address format on EVM chain: {self.address[:20]}...")
        # For other chains, accept any non-empty format
        else:
            if len(self.address) < 1:
                raise ValueError(f"Invalid token address (too short): {self.address}")
        
        if not self.symbol:
            raise ValueError("Token symbol cannot be empty")
    
    @property
    def chain(self) -> str:
        """Get chain name from chain_id"""
        try:
            from networks.chain_constants import get_chain_name
            return get_chain_name(self.chain_id)
        except Exception:
            # Fallback to chain_id as string if mapping fails
            return str(self.chain_id)

@dataclass(frozen=True)
class MarketData:
    """Time-series market data snapshot."""
    price: Decimal
    volume_24h: Decimal
    liquidity: Decimal
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self):
        # Convert numeric types to Decimal
        object.__setattr__(self, 'price', Decimal(str(self.price)))
        object.__setattr__(self, 'volume_24h', Decimal(str(self.volume_24h)))
        object.__setattr__(self, 'liquidity', Decimal(str(self.liquidity)))
        
        if self.price <= 0 or self.volume_24h < 0 or self.liquidity < 0:
            raise ValueError("Market data values must be non-negative")

class TradeOpportunity:
    """A potential trading opportunity identified by the scanner.

    This is the primary input to the AI controller's decision process.
    Consolidated version with all fields from AI controller for consistency.
    """

    def __init__(
        self,
        token: TokenInfo,
        market_data: MarketData,
        scanner_id: str,
        scanner_version: str,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        opportunity_type: str = "unknown",
        target_price: Decimal = Decimal('0'),
        stop_loss: Decimal = Decimal('0'),
        potential_profit: Decimal = Decimal('0'),
        potential_loss: Decimal = Decimal('0'),
        risk_reward_ratio: float = 0.0,
        confidence: float = 0.0,
        volatility: float = 0.0,
        required_capital: Decimal = Decimal('0'),
        estimated_execution_time_ms: float = 0.0,
        max_slippage: float = 0.0,
        urgency: float = 0.0,
        technical_indicators: Optional[Dict[str, float]] = None,
        market_sentiment: float = 0.5,
        chain: str = "",
        token_address: str = "",
        detected_at: Optional[datetime] = None,
        opportunity_id: Optional[str] = None,
    ):
        # Handle backward compatibility - create TokenInfo and MarketData from legacy parameters
        if token is None and token_symbol and token_address:
            # Create TokenInfo from legacy parameters
            token = TokenInfo(
                symbol=token_symbol,
                address=token_address,
                chain_id=1,  # Default to Ethereum, can be overridden
                decimals=18,
                name=token_symbol,
                asset_class=AssetClass.CRYPTO
            )

        if market_data is None and current_price > 0:
            # Create MarketData from legacy parameters
            market_data = MarketData(
                price=current_price,
                volume_24h=volume_24h,
                liquidity=liquidity,
                timestamp=datetime.now(timezone.utc)
            )

        # Validate required fields
        if token is None:
            raise ValueError("Either 'token' parameter or legacy 'token_symbol' and 'token_address' must be provided")
        if market_data is None:
            raise ValueError("Either 'market_data' parameter or legacy 'current_price' must be provided")

        self.token = token
        self.market_data = market_data
        self.scanner_id = scanner_id
        self.scanner_version = scanner_version
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now(timezone.utc)
        self.expires_at = expires_at

        # Enhanced fields from AI controller consolidation
        self.opportunity_type = opportunity_type
        self.target_price = target_price
        self.stop_loss = stop_loss
        self._potential_profit = potential_profit
        self._potential_loss = potential_loss
        self._risk_reward_ratio = risk_reward_ratio
        self._confidence = confidence
        self.volatility = volatility
        self._required_capital = required_capital
        self.estimated_execution_time_ms = estimated_execution_time_ms
        self.max_slippage = max_slippage
        self.urgency = urgency
        self.technical_indicators = technical_indicators or {}
        self.market_sentiment = market_sentiment
        self.chain = chain or "ethereum"  # Default chain
        self.token_address = token_address or token.address
        self.detected_at = detected_at or datetime.now(timezone.utc)

        # Store legacy opportunity_id if provided
        if opportunity_id:
            self._legacy_opportunity_id = opportunity_id
    
    @property
    def opportunity_id(self) -> str:
        """Generate a deterministic ID for this opportunity."""
        components = (
            str(self.token.chain_id),
            self.token.address.lower(),
            str(int(self.market_data.timestamp.timestamp())),
            self.scanner_id
        )
        return hashlib.sha256("_".join(components).encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            'opportunity_id': self.opportunity_id,
            'token': {
                'symbol': self.token.symbol,
                'address': self.token.address,
                'chain_id': self.token.chain_id,
                'decimals': self.token.decimals,
                'name': self.token.name,
                'asset_class': self.token.asset_class.value
            },
            'market_data': {
                'price': str(self.market_data.price),
                'volume_24h': str(self.market_data.volume_24h),
                'liquidity': str(self.market_data.liquidity),
                'timestamp': self.market_data.timestamp.isoformat()
            },
            'scanner_id': self.scanner_id,
            'scanner_version': self.scanner_version,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'metadata': self.metadata,
            # Enhanced fields
            'opportunity_type': self.opportunity_type,
            'target_price': str(self.target_price),
            'stop_loss': str(self.stop_loss),
            'potential_profit': str(self.potential_profit),
            'potential_loss': str(self.potential_loss),
            'risk_reward_ratio': self.risk_reward_ratio,
            'confidence': self.confidence,
            'volatility': self.volatility,
            'required_capital': str(self.required_capital),
            'estimated_execution_time_ms': self.estimated_execution_time_ms,
            'max_slippage': self.max_slippage,
            'urgency': self.urgency,
            'technical_indicators': self.technical_indicators,
            'market_sentiment': self.market_sentiment,
            'chain': self.chain,
            'token_address': self.token_address,
            'detected_at': self.detected_at.isoformat()
        }
    
    # Compatibility properties for AI controller
    @property
    def current_price(self) -> float:
        """Current price for compatibility with AI controller."""
        return float(self.market_data.price)
    
    @property
    def volume_24h(self) -> float:
        """24h volume for compatibility with AI controller."""
        return float(self.market_data.volume_24h)
    
    @property
    def token_symbol(self) -> str:
        """Token symbol for compatibility with AI controller."""
        return self.token.symbol
    
    @property
    def required_capital(self) -> float:
        """Required capital for compatibility with AI controller."""
        # Return stored value if available, otherwise compute default
        if self._required_capital > 0:
            return float(self._required_capital)
        # Calculate based on liquidity - use 10% of available liquidity as max position
        from decimal import Decimal
        return float(self.market_data.liquidity * Decimal('0.1'))

    @property
    def confidence(self) -> float:
        """Confidence score for compatibility with AI controller."""
        # Return stored value if available, otherwise compute default
        if self._confidence > 0:
            return self._confidence
        # Calculate based on volume and liquidity ratio
        if self.market_data.liquidity > 0:
            volume_to_liquidity_ratio = float(self.market_data.volume_24h / self.market_data.liquidity)
            # Higher confidence for good volume-to-liquidity ratio, capped at 0.9
            confidence = min(volume_to_liquidity_ratio * 0.5 + 0.4, 0.9)
        else:
            confidence = 0.5  # Default confidence
        return confidence
    
    @confidence.setter
    def confidence(self, value: float):
        """Set confidence score."""
        self._confidence = float(value)
    
    @property
    def potential_profit(self) -> float:
        """Potential profit for compatibility with AI controller."""
        # Return stored value if available, otherwise compute default
        if self._potential_profit > 0:
            return float(self._potential_profit)
        # Estimate based on liquidity and volatility (simplified)
        # Assume 2-5% potential profit based on market conditions
        from decimal import Decimal
        return float(self.market_data.liquidity * Decimal('0.03'))  # 3% of liquidity as potential profit

    @property
    def potential_loss(self) -> float:
        """Potential loss for compatibility with AI controller."""
        # Return stored value if available, otherwise compute default
        if self._potential_loss > 0:
            return float(self._potential_loss)
        # Estimate based on liquidity (simplified risk management)
        # Assume 1-2% potential loss
        from decimal import Decimal
        return float(self.market_data.liquidity * Decimal('0.015'))  # 1.5% of liquidity as potential loss

    @property
    def risk_reward_ratio(self) -> float:
        """Risk/reward ratio for compatibility with AI controller."""
        # Return stored value if available
        if self._risk_reward_ratio > 0:
            return self._risk_reward_ratio
        # Otherwise compute from potential profit/loss
        if self.potential_loss > 0:
            return self.potential_profit / self.potential_loss
        return 2.0  # Default 2:1 ratio
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeOpportunity':
        """Create from a dictionary."""
        # Validate required fields
        if 'decimals' not in data['token']:
            raise ValueError("Token decimals is required - cannot use fallback")
        
        return cls(
            token=TokenInfo(
                symbol=data['token']['symbol'],
                address=data['token']['address'],
                chain_id=data['token']['chain_id'],
                decimals=data['token']['decimals'],  # Required field - no fallback
                name=data['token'].get('name'),  # Optional field
                asset_class=AssetClass(data['token'].get('asset_class', 'crypto'))  # Sensible default
            ),
            market_data=MarketData(
                price=Decimal(data['market_data']['price']),
                volume_24h=Decimal(data['market_data']['volume_24h']),
                liquidity=Decimal(data['market_data']['liquidity']),
                timestamp=datetime.fromisoformat(data['market_data']['timestamp'])
            ),
            scanner_id=data['scanner_id'],
            scanner_version=data['scanner_version'],
            metadata=data.get('metadata', {}),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        )

@dataclass(frozen=True)
class StrategyDecision:
    """
    A trading decision made by the AI controller.

    This is the primary output of the AI controller and input to the execution engine.
    """
    opportunity_id: str
    decision_id: str
    token: TokenInfo
    outcome: DecisionOutcome
    strategy_name: str
    strategy_id: str
    confidence: float
    position_size: Decimal
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.GTC
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    risk_parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Market data fields for execution planning
    market_data: Optional[MarketData] = None
    current_price: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    liquidity: Optional[Decimal] = None
    
    # Additional fields for AI controller compatibility
    required_capital: Optional[Decimal] = None
    potential_profit: Optional[Decimal] = None
    potential_loss: Optional[Decimal] = None
    risk_reward_ratio: Optional[float] = None
    volatility: Optional[float] = None
    estimated_execution_time_ms: Optional[float] = None
    max_slippage: Optional[float] = None
    urgency: Optional[float] = None
    
    def __post_init__(self):
        # Type conversion and validation
        object.__setattr__(self, 'position_size', Decimal(str(self.position_size)))
        object.__setattr__(self, 'confidence', float(self.confidence))
        
        if self.limit_price is not None:
            object.__setattr__(self, 'limit_price', Decimal(str(self.limit_price)))
        if self.stop_price is not None:
            object.__setattr__(self, 'stop_price', Decimal(str(self.stop_price)))
        
        if not (0 <= self.confidence <= 1):
            raise ValueError("Confidence must be between 0 and 1")
        if self.position_size <= 0:
            raise ValueError("Position size must be positive")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            'opportunity_id': self.opportunity_id,
            'token': {
                'symbol': self.token.symbol,
                'address': self.token.address,
                'chain_id': self.token.chain_id,
                'decimals': self.token.decimals,
                'name': self.token.name,
                'asset_class': self.token.asset_class.value
            },
            'outcome': self.outcome.value,
            'strategy_name': self.strategy_name,
            'strategy_id': self.strategy_id,
            'confidence': self.confidence,
            'position_size': str(self.position_size),
            'side': self.side.value,
            'order_type': self.order_type.value,
            'time_in_force': self.time_in_force.value,
            'limit_price': str(self.limit_price) if self.limit_price is not None else None,
            'stop_price': str(self.stop_price) if self.stop_price is not None else None,
            'risk_parameters': self.risk_parameters,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyDecision':
        """Create from a dictionary."""
        # Validate required fields
        if 'decimals' not in data['token']:
            raise ValueError("Token decimals is required - cannot use fallback")
        
        return cls(
            opportunity_id=data['opportunity_id'],
            decision_id=data.get('decision_id', data['opportunity_id']),  # Sensible fallback
            token=TokenInfo(
                symbol=data['token']['symbol'],
                address=data['token']['address'],
                chain_id=data['token']['chain_id'],
                decimals=data['token']['decimals'],  # Required field - no fallback
                name=data['token'].get('name'),  # Optional field
                asset_class=AssetClass(data['token'].get('asset_class', 'crypto'))  # Sensible default
            ),
            outcome=DecisionOutcome(data['outcome']),
            strategy_name=data['strategy_name'],
            strategy_id=data['strategy_id'],
            confidence=float(data['confidence']),
            position_size=Decimal(data['position_size']),
            side=OrderSide(data['side']),
            order_type=OrderType(data.get('order_type', 'market')),
            time_in_force=TimeInForce(data.get('time_in_force', 'GTC')),
            limit_price=Decimal(data['limit_price']) if data.get('limit_price') else None,
            stop_price=Decimal(data['stop_price']) if data.get('stop_price') else None,
            risk_parameters=data.get('risk_parameters', {}),
            metadata=data.get('metadata', {}),
            created_at=datetime.fromisoformat(data['created_at'])
        )

@dataclass(frozen=True)
class TradeExecution:
    """
    Represents an executed trade with final execution details.
    
    This is the output of the execution engine and input to the position manager.
    """
    decision: StrategyDecision
    execution_id: str
    executed_price: Decimal
    executed_size: Decimal
    fees: Decimal
    exchange_id: str
    exchange_order_id: str
    execution_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Type conversion
        object.__setattr__(self, 'executed_price', Decimal(str(self.executed_price)))
        object.__setattr__(self, 'executed_size', Decimal(str(self.executed_size)))
        object.__setattr__(self, 'fees', Decimal(str(self.fees)))
        
        if self.executed_price <= 0 or self.executed_size <= 0 or self.fees < 0:
            raise ValueError("Invalid execution values")

# Type aliases for better semantics
TokenCandidate = Dict[str, Any]  # Raw scanner output before validation
DecisionResult = Tuple[StrategyDecision, Dict[str, Any]]  # Decision + metadata

# Export execution models for backward compatibility
__all__ = ["TradeIntent", "TradeSide"]
