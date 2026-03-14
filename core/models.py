"""
Unified data models for the trading ecosystem.

This module contains standardized dataclasses used across the system
to ensure consistency and reduce duplication.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union


class StrategyType(str, Enum):
    """
    Strategy classification enum.

    Keep it minimal and stable; used for logging, persistence, and routing.
    """
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    VOLATILITY_BREAKOUT = "volatility_breakout"
    AGGRESSIVE = "aggressive"
    SAFE = "safe"
    SMART_MONEY = "smart_money"
    RISK_CAPS = "risk_caps"


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


# Type aliases
TokenAddress = str
ChainID = int
Symbol = str


@dataclass
class TokenMetadata:
    """Token metadata with comprehensive fields"""
    symbol: str = ""
    address: str = ""
    chain: str = ""
    decimals: int = 18
    name: str = ""
    status: str = "active"  # active, inactive, blacklisted
    last_updated: Optional[datetime] = None
    price: float = 0.01  # Small non-zero default to pass validation
    volume_24h: float = 0.0
    liquidity_usd: float = 0.0
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    strength: float = 0.0
    zscore: float = 0.0
    ai_score: float = 0.0
    holders: Optional[int] = None
    momentum: Dict[str, float] = field(default_factory=lambda: {'5m': 0.0, '1h': 0.0, '24h': 0.0})
    volatility: float = 0.0
    market_cap: float = 0.0  # Added for scoring service compatibility

    def __post_init__(self):
        # Ensure momentum is a dict even if constructed from legacy data
        if not isinstance(self.momentum, dict):
            self.momentum = {'5m': 0.0, '1h': 0.0, '24h': 0.0}
        if self.last_updated is None:
            self.last_updated = datetime.now(timezone.utc)


@dataclass
class StrategyPerformance:
    """
    Standardized performance record for a strategy evaluation.

    This should be lightweight and serializable.
    """
    strategy: str
    timestamp: datetime
    profit_loss: float
    strategy_name: str = ""
    strategy_type: StrategyType = StrategyType.MOMENTUM
    total_trades: int = 0
    win_rate: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    trades: Optional[int] = None
    notes: Optional[str] = None
    recent_performance: float = 0.0
    consistency_score: float = 0.0
    current_weight: float = 1.0
    performance_by_regime: Dict[str, float] = field(default_factory=dict)
    ucb_score: float = 0.0
    thompson_score: float = 0.0
    last_trade: Optional[datetime] = None
    status: str = "active"
    last_updated: Optional[datetime] = None
    profit_factor: float = 1.0

    async def calculate_metrics_async(self, trade_history: List[float]) -> None:
        """Calculate performance metrics from trade history."""
        if not trade_history:
            return

        self.total_trades = len(trade_history)
        profits = [t for t in trade_history if t > 0]
        losses = [t for t in trade_history if t < 0]

        if profits:
            self.win_rate = len(profits) / self.total_trades
            avg_profit = sum(profits) / len(profits)
            if losses:
                avg_loss = sum(losses) / len(losses)
                self.profit_factor = avg_profit / abs(avg_loss) if avg_loss != 0 else float('inf')
            else:
                self.profit_factor = float('inf')
        else:
            self.win_rate = 0.0
            self.profit_factor = 0.0

        if len(trade_history) > 1:
            returns = trade_history
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = variance ** 0.5
            self.sharpe_ratio = mean_return / std_dev if std_dev > 0 else 0.0
        else:
            self.sharpe_ratio = 0.0

        self.max_drawdown = min(trade_history) if trade_history else 0.0
        self.recent_performance = sum(trade_history[-10:]) / len(trade_history[-10:]) if trade_history else 0.0
        self.consistency_score = self.win_rate * (1 - abs(self.sharpe_ratio) / 10) if self.sharpe_ratio else self.win_rate
        self.last_updated = datetime.now(timezone.utc)


@dataclass(frozen=True)
class StrategyRecommendation:
    """
    Recommendation generated by a strategy evaluation.

    This is intended to be a lightweight DTO that can be persisted or sent to
    other services.
    """
    strategy: str
    timestamp: datetime
    recommendation: str  # e.g., "buy", "sell", "hold", "wait"
    confidence: Optional[float] = None  # 0.0 - 1.0
    rationale: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    opportunity_id: Optional[str] = None
    recommended_strategy_id: Optional[str] = None
    recommended_strategy_name: Optional[str] = None
    expected_profit: Optional[float] = None
    expected_risk: Optional[float] = None
    selection_method: Optional[str] = None
    market_regime: Optional[str] = None
    position_size: Optional[float] = None
    key_factors: Optional[List[str]] = None
    ensemble_strategies: Optional[List[Tuple[str, float]]] = None


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
        # STRICT: Validate address format matches chain type
        if not self.address:
            raise ValueError("Token address cannot be empty")
        
        # Get chain type from chain_id
        from networks.multi_chain_models import ChainType
        from networks.address_normalizers import MultiChainNormalizer
        
        # Map chain_id to chain type
        chain_type_mapping = {
            # EVM chains (official chain IDs)
            1: ChainType.EVM, 56: ChainType.EVM, 137: ChainType.EVM, 42161: ChainType.EVM,
            43114: ChainType.EVM, 10: ChainType.EVM, 8453: ChainType.EVM, 59144: ChainType.EVM,
            534352: ChainType.EVM, 5000: ChainType.EVM, 81457: ChainType.EVM, 250: ChainType.EVM,
            25: ChainType.EVM, 42262: ChainType.EVM, 128: ChainType.EVM, 1284: ChainType.EVM,
            1285: ChainType.EVM, 1088: ChainType.EVM, 321: ChainType.EVM, 66: ChainType.EVM,
            40: ChainType.EVM, 361: ChainType.EVM, 592: ChainType.EVM, 9001: ChainType.EVM,
            122: ChainType.EVM, 4689: ChainType.EVM, 1313161554: ChainType.EVM, 42170: ChainType.EVM,
            288: ChainType.EVM, 324: ChainType.EVM, 1101: ChainType.EVM, 59140: ChainType.EVM,
            1442: ChainType.EVM, 5001: ChainType.EVM, 534351: ChainType.EVM, 280: ChainType.EVM,
            43113: ChainType.EVM, 4002: ChainType.EVM, 84531: ChainType.EVM, 10200: ChainType.EVM,
            44787: ChainType.EVM, 1287: ChainType.EVM, 1313161555: ChainType.EVM, 1666700000: ChainType.EVM,
            599: ChainType.EVM, 97: ChainType.EVM, 80001: ChainType.EVM, 421613: ChainType.EVM,
            420: ChainType.EVM, 5: ChainType.EVM, 11155111: ChainType.EVM,
            
            # Non-EVM Networks (unique chain IDs > 100000)
            101001: ChainType.SOLANA,  # Solana mainnet
            101002: ChainType.APTOS,   # Sui mainnet  
            101003: ChainType.SUI,     # Aptos mainnet
            101004: ChainType.BITCOIN, # Cardano mainnet
            101005: ChainType.BITCOIN, # XRPL mainnet
            101006: ChainType.COSMOS,  # ThorChain mainnet
            101007: ChainType.BITCOIN, # Stacks mainnet
            101008: ChainType.BITCOIN, # Algorand mainnet
            101009: ChainType.COSMOS,  # Osmosis mainnet
            101010: ChainType.BITCOIN, # Tezos mainnet
            101011: ChainType.BITCOIN, # Stellar mainnet
            101012: ChainType.EVM,     # StarkNet mainnet
            
            # Official chain IDs for non-EVM networks
            0: ChainType.BITCOIN,      # Ton mainnet
            728126428: ChainType.BITCOIN, # Tron mainnet
            787: ChainType.COSMOS,      # Acala mainnet
        }
        
        chain_type = chain_type_mapping.get(self.chain_id, ChainType.EVM)  # Default to EVM for unknown
        
        # Validate address format for the specific chain type
        try:
            is_valid = MultiChainNormalizer.validate_address(self.address, chain_type)
            if not is_valid:
                raise ValueError(
                    f"Invalid address format for chain {self.chain_id} ({chain_type.value}): {self.address}"
                )
        except Exception as e:
            raise ValueError(f"Address validation failed for chain {self.chain_id}: {e}")
        
        if not self.symbol:
            raise ValueError("Token symbol cannot be empty")

    @property
    def chain(self) -> str:
        """Get canonical chain name from chain_id using the normaliser registry."""
        from networks.chain_normalizer import ChainNormalizer
        name = ChainNormalizer.CHAIN_ID_MAPPINGS.get(self.chain_id)
        if name:
            return name
        return str(self.chain_id)


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
        # Legacy parameters for backward compatibility
        token_symbol: Optional[str] = None,
        token_address_legacy: Optional[str] = None,
        current_price: float = 0.0,
        volume_24h: float = 0.0,
        liquidity: float = 0.0,
    ):
        # Backward compatibility: allow legacy parameters to construct required objects
        if token is None and token_symbol and token_address_legacy:
            token = TokenInfo(
                symbol=token_symbol,
                address=token_address_legacy,
                chain_id=1,
                decimals=18,
                name=token_symbol,
                asset_class=AssetClass.CRYPTO,
            )

        if market_data is None and current_price > 0:
            market_data = MarketData(
                price=Decimal(str(current_price)),
                volume_24h=Decimal(str(volume_24h)),
                liquidity=Decimal(str(liquidity)),
                timestamp=datetime.now(timezone.utc),
            )

        # Validate required fields are present
        if token is None:
            raise ValueError("TradeOpportunity: token is required")
        if market_data is None:
            raise ValueError("TradeOpportunity: market_data is required")
        if not scanner_id:
            raise ValueError("TradeOpportunity: scanner_id is required")
        if not scanner_version:
            raise ValueError("TradeOpportunity: scanner_version is required")

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
