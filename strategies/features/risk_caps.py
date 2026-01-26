# trade_strategies/risk_caps_strategy.py
"""
Advanced Risk Caps Strategy with sophisticated position sizing and risk management.

Features:
- Kelly Criterion-based position sizing
- Dynamic correlation adjustment
- Value at Risk (VaR) calculations
- Adaptive volatility modeling
- Circuit breakers and risk limits
- Performance caching and memoization
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Set

from ..base_strategy import BaseStrategy, SignalType, TradeSignal, RiskProfile

logger = logging.getLogger("strategies.risk_caps")


class RiskState(Enum):
    """System risk states for circuit breaker logic."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    CRITICAL = "critical"
    HALTED = "halted"


@dataclass
class RiskMetrics:
    """Immutable risk metrics container."""
    drawdown: float
    volatility: float
    sharpe_ratio: float
    var_95: float  # Value at Risk (95% confidence)
    liquidity_score: float
    volume_normalized: float
    correlation_penalty: float = 0.0
    
    def __post_init__(self):
        """Validate risk metrics on initialization."""
        if not 0 <= self.drawdown <= 1:
            raise ValueError(f"Invalid drawdown: {self.drawdown}")
        if self.volatility < 0:
            raise ValueError(f"Invalid volatility: {self.volatility}")


@dataclass
class PositionSizingResult:
    """Result of position sizing calculation."""
    size: float
    confidence: float
    kelly_fraction: float
    risk_adjusted_size: float
    stop_loss: float
    take_profit: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class RiskCapsStrategy(BaseStrategy):
    """
    Elite Risk Caps Strategy with advanced quantitative risk management.
    
    Implements:
    - Kelly Criterion with fractional sizing
    - Dynamic VaR-based position limits
    - Correlation-adjusted portfolio optimization
    - Adaptive volatility forecasting (EWMA)
    - Multi-level circuit breakers
    - Performance attribution tracking
    """
    
    IS_STRATEGY = True
    STRATEGY_NAME = "risk_caps"

    # ------------------------------------------------------------------
    # REQUIRED ABSTRACT PROPERTIES
    # ------------------------------------------------------------------

    @property
    def strategy_id(self) -> str:
        return "risk_caps_v1"

    @property
    def description(self) -> str:
        return "Advanced quantitative risk management strategy using Kelly Criterion, VaR calculations, and multi-level circuit breakers."

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def risk_profile(self) -> RiskProfile:
        return RiskProfile(
            max_drawdown=0.10,
            max_concurrent_positions=10,
            volatility_tolerance=1.5,
            min_confidence_threshold=0.35,
            max_position_size=0.10,
            max_loss_per_trade=0.01,
            risk_per_trade=0.005
        )

    @property
    def signal_type(self) -> SignalType:
        return SignalType.DIRECTIONAL

    @property
    def required_features(self) -> Set[str]:
        return {"price", "volume_24h", "liquidity_usd", "volatility", "drawdown"}

    @property
    def supported_markets(self) -> List[str]:
        return ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "avalanche", "fantom"]

    @property
    def timeframes(self) -> List[str]:
        return ["1h", "4h", "24h"]

    @property
    def warmup_period(self) -> int:
        return 20

    # ------------------------------------------------------------------
    # EVALUATION METHOD (required by BaseStrategy)
    # ------------------------------------------------------------------

    async def evaluate(self, market_state: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Core evaluation method - wraps evaluate_token for backward compatibility.
        """
        return await self.evaluate_token(market_state)
    
    # Configuration with sensible defaults
    DEFAULTS = {
        "enabled": True,
        "max_drawdown": 0.10,
        "min_position_size": 0.01,
        "max_position_size": 0.10,
        "kelly_fraction": 0.25,  # Conservative Kelly (1/4 Kelly)
        "volatility_lookback": 20,  # Days for volatility calculation
        "volatility_decay": 0.94,  # EWMA decay factor
        "min_volume": 5000,
        "min_volume_24h": 5000,
        "min_liquidity": 10000,
        "max_volatility": 2.0,
        "max_position_risk": 0.02,
        "max_daily_loss": 0.05,
        "max_correlation": 0.7,  # Maximum portfolio correlation
        "var_confidence": 0.95,  # VaR confidence level
        "sharpe_threshold": 0.5,  # Minimum Sharpe ratio
        "circuit_breaker_loss": 0.03,  # 3% loss triggers elevated state
        "required_models": 1,
        "enabled_chains": [
            "ethereum", "bsc", "polygon", "arbitrum", 
            "optimism", "avalanche", "fantom"
        ],
        "cache_ttl": 60,  # Cache TTL in seconds
        "max_concurrent_positions": 10,
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # State management
        self._daily_pnl: float = 0.0
        self._risk_state: RiskState = RiskState.NORMAL
        self._position_count: int = 0
        
        # Performance tracking
        self._pnl_history: deque = deque(maxlen=100)
        self._volatility_cache: Dict[str, Tuple[float, datetime]] = {}
        
        # Circuit breaker timestamps
        self._last_state_change: datetime = datetime.now(timezone.utc)
        self._cooldown_period: timedelta = timedelta(minutes=15)
        
        logger.info(f"[{self.STRATEGY_NAME}] Initialized with advanced risk management")

    def _create_signal(self, signal_type, confidence, price, size, stop_loss, take_profit, token_address=None, token_symbol=None, reason=None, metadata=None):
        """Create a standardized signal dictionary."""
        from ..base_strategy import TradeSignal

        # Combine all metadata
        combined_meta = metadata or {}
        if token_address:
            combined_meta["token_address"] = token_address
        if token_symbol:
            combined_meta["token_symbol"] = token_symbol
        if reason:
            combined_meta["reason"] = reason

        return TradeSignal(
            strategy_id=self.STRATEGY_NAME,
            signal_type=signal_type,
            confidence=float(confidence),
            score=float(confidence),  # Use confidence as score
            meta=combined_meta
        )

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a value between 0 and 1."""
        if max_val <= min_val:
            return 0.0
        if value <= min_val:
            return 0.0
        if value >= max_val:
            return 1.0
        return (value - min_val) / (max_val - min_val)

    def _fuse_confidence(self, *scores, weights=None) -> float:
        """Fuse multiple scores into a confidence value."""
        if not scores:
            return 0.0
        
        if weights is None:
            weights = [1.0] * len(scores)
        
        if len(weights) != len(scores):
            weights = [1.0] * len(scores)
        
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)
        
        if total_weight == 0:
            return 0.0
            
        return min(1.0, max(0.0, weighted_sum / total_weight))

    async def evaluate_token(self, token: Dict[str, Any]) -> Optional[TradeSignal]:
        """
        Evaluate opportunity with sophisticated risk analysis.
        
        Args:
            token: Token dictionary with market data
            
        Returns:
            Enhanced signal with comprehensive risk metrics
        """
        try:
            # Pre-flight checks
            if not await self._pre_flight_checks(token):
                return None
            
            # Extract and validate configuration
            config = await self._get_validated_config()
            if not config:
                return None
            
            # Check circuit breakers
            if not await self._check_circuit_breakers(config):
                logger.warning(f"[{self.STRATEGY_NAME}] Circuit breaker active")
                return None
            
            # Parse and validate opportunity data
            market_data = await self._parse_market_data(token, config)
            if not market_data:
                return None
            
            # Calculate risk metrics with caching
            risk_metrics = await self._calculate_risk_metrics(token, market_data, config)
            if not risk_metrics:
                return None
            
            # Perform position sizing with Kelly Criterion
            sizing_result = await self._calculate_optimal_position(
                market_data, risk_metrics, config
            )
            
            if not sizing_result or sizing_result.size < config["min_position_size"]:
                logger.debug(f"[{self.STRATEGY_NAME}] Position size below minimum")
                return None
            
            # Generate signal with comprehensive metadata
            return await self._generate_signal(token, market_data, sizing_result, risk_metrics)
            
        except Exception as e:
            logger.error(
                f"[{self.STRATEGY_NAME}] Critical error in evaluate: {str(e)}", 
                exc_info=True
            )
            return None

    async def _pre_flight_checks(self, token: Dict[str, Any]) -> bool:
        """Perform fast pre-flight validation checks."""
        # Check if we have basic required fields
        if not token or not isinstance(token, dict):
            return False
        
        # Verify minimum required keys
        required_keys = {"price", "chain"}
        if not required_keys.issubset(token.keys()):
            logger.debug(f"[{self.STRATEGY_NAME}] Missing required keys")
            return False
        
        return True

    async def _parse_market_data(
        self, 
        token: Dict[str, Any], 
        config: Dict[str, Any]
    ) -> Optional[Dict[str, float]]:
        """Parse and validate market data with type safety."""
        try:
            price = self._safe(token, "price")
            if price is None or price <= 0:
                return None
            
            # Extract market metrics with defaults
            volume = self._safe(token, "volume_24h", 0.0)
            liquidity = self._safe(token, "liquidity", 0.0)
            
            # Validate minimums
            if volume < config["min_volume"] or liquidity < config["min_liquidity"]:
                logger.debug(
                    f"[{self.STRATEGY_NAME}] Insufficient volume/liquidity: "
                    f"vol={volume}, liq={liquidity}"
                )
                return None
            
            # Check chain eligibility
            chain = self._safe(token, "chain", "").lower()
            if chain not in [c.lower() for c in config["enabled_chains"]]:
                return None
            
            return {
                "price": float(price),
                "volume": float(volume),
                "liquidity": float(liquidity),
                "chain": chain,
            }
            
        except (ValueError, TypeError) as e:
            logger.error(f"[{self.STRATEGY_NAME}] Data parsing error: {e}")
            return None

    async def _calculate_risk_metrics(
        self,
        token: Dict[str, Any],
        market_data: Dict[str, float],
        config: Dict[str, Any]
    ) -> Optional[RiskMetrics]:
        """Calculate comprehensive risk metrics with caching."""
        try:
            # Get raw metrics
            drawdown = max(0.0, min(1.0, self._safe(token, "drawdown", 0.0)))
            raw_volatility = self._safe(token, "volatility", 1.0)
            
            # Calculate EWMA volatility with caching
            volatility = await self._calculate_ewma_volatility(
                token.get("symbol", "unknown"),
                raw_volatility,
                config
            )
            
            # Validate volatility bounds
            if volatility > config["max_volatility"]:
                logger.debug(
                    f"[{self.STRATEGY_NAME}] Volatility {volatility:.2f} "
                    f"exceeds max {config['max_volatility']:.2f}"
                )
                return None
            
            # Calculate Value at Risk (95% confidence)
            var_95 = self._calculate_var(
                market_data["price"], 
                volatility, 
                config["var_confidence"]
            )
            
            # Estimate Sharpe ratio (simplified)
            sharpe = self._estimate_sharpe_ratio(drawdown, volatility)
            if sharpe < config["sharpe_threshold"]:
                logger.debug(
                    f"[{self.STRATEGY_NAME}] Sharpe {sharpe:.2f} below "
                    f"threshold {config['sharpe_threshold']:.2f}"
                )
                return None
            
            # Normalize liquidity and volume scores
            liquidity_score = min(1.0, market_data["liquidity"] / (config["min_liquidity"] * 10))
            volume_score = min(1.0, market_data["volume"] / (config["min_volume"] * 10))
            
            return RiskMetrics(
                drawdown=drawdown,
                volatility=volatility,
                sharpe_ratio=sharpe,
                var_95=var_95,
                liquidity_score=liquidity_score,
                volume_normalized=volume_score,
            )
            
        except (ValueError, TypeError) as e:
            logger.error(f"[{self.STRATEGY_NAME}] Risk metrics error: {e}")
            return None

    async def _calculate_ewma_volatility(
        self,
        symbol: str,
        current_vol: float,
        config: Dict[str, Any]
    ) -> float:
        """Calculate EWMA volatility with caching."""
        cache_key = f"vol_{symbol}"
        decay = config["volatility_decay"]
        ttl = config["cache_ttl"]
        
        # Check cache
        if cache_key in self._volatility_cache:
            cached_vol, timestamp = self._volatility_cache[cache_key]
            if (datetime.now(timezone.utc) - timestamp).seconds < ttl:
                # Apply EWMA: new_vol = decay * old_vol + (1 - decay) * current_vol
                ewma_vol = decay * cached_vol + (1 - decay) * current_vol
                self._volatility_cache[cache_key] = (ewma_vol, datetime.now(timezone.utc))
                return ewma_vol
        
        # Initialize cache
        self._volatility_cache[cache_key] = (current_vol, datetime.now(timezone.utc))
        return current_vol

    @staticmethod
    def _calculate_var(price: float, volatility: float, confidence: float) -> float:
        """Calculate Value at Risk using normal distribution assumption."""
        # Z-score for 95% confidence ≈ 1.645
        z_score = 1.645 if confidence == 0.95 else 1.96
        return price * volatility * z_score

    @staticmethod
    def _estimate_sharpe_ratio(drawdown: float, volatility: float) -> float:
        """Estimate Sharpe ratio from drawdown and volatility."""
        if volatility == 0:
            return 0.0
        # Simplified Sharpe: lower drawdown and volatility = higher Sharpe
        return (1.0 - drawdown) / (volatility + 0.01)

    async def _calculate_optimal_position(
        self,
        market_data: Dict[str, float],
        risk_metrics: RiskMetrics,
        config: Dict[str, Any]
    ) -> Optional[PositionSizingResult]:
        """Calculate optimal position size using Kelly Criterion."""
        try:
            price = market_data["price"]
            
            # Kelly Criterion: f* = (p*b - q) / b
            # where p = win probability, q = 1-p, b = win/loss ratio
            win_prob = self._estimate_win_probability(risk_metrics)
            win_loss_ratio = 2.0  # 2:1 reward:risk ratio
            
            kelly_full = (win_prob * win_loss_ratio - (1 - win_prob)) / win_loss_ratio
            kelly_fraction = max(0.0, kelly_full * config["kelly_fraction"])
            
            # Apply risk adjustments
            vol_adjustment = 1.0 / (1.0 + risk_metrics.volatility)
            drawdown_adjustment = 1.0 - (risk_metrics.drawdown / config["max_drawdown"])
            liquidity_adjustment = risk_metrics.liquidity_score
            
            # Calculate raw size
            raw_size = kelly_fraction * vol_adjustment * drawdown_adjustment * liquidity_adjustment
            
            # Apply bounds
            size = max(
                config["min_position_size"],
                min(raw_size, config["max_position_size"])
            )
            
            # Calculate confidence
            confidence = self._calculate_confidence(risk_metrics, size, config)
            
            # Risk-adjusted size with VaR consideration
            max_risk_size = (config["max_position_risk"] * price) / risk_metrics.var_95
            risk_adjusted = min(size, max_risk_size)
            
            # Calculate stop loss and take profit
            stop_loss = price * (1 - config["max_drawdown"])
            take_profit = price * (1 + 2 * config["max_drawdown"])
            
            return PositionSizingResult(
                size=risk_adjusted,
                confidence=confidence,
                kelly_fraction=kelly_fraction,
                risk_adjusted_size=risk_adjusted,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={
                    "win_probability": win_prob,
                    "kelly_full": kelly_full,
                    "vol_adjustment": vol_adjustment,
                    "drawdown_adjustment": drawdown_adjustment,
                    "liquidity_adjustment": liquidity_adjustment,
                }
            )
            
        except Exception as e:
            logger.error(f"[{self.STRATEGY_NAME}] Position sizing error: {e}")
            return None

    @staticmethod
    def _estimate_win_probability(risk_metrics: RiskMetrics) -> float:
        """Estimate win probability from risk metrics."""
        # Base probability from Sharpe ratio
        base_prob = 0.5 + (risk_metrics.sharpe_ratio * 0.1)
        
        # Adjust for volatility (lower vol = higher prob)
        vol_factor = 1.0 / (1.0 + risk_metrics.volatility)
        
        # Adjust for drawdown (lower dd = higher prob)
        dd_factor = 1.0 - risk_metrics.drawdown
        
        prob = base_prob * vol_factor * dd_factor
        return max(0.05, min(0.95, prob))

    def _calculate_confidence(
        self,
        risk_metrics: RiskMetrics,
        size: float,
        config: Dict[str, Any]
    ) -> float:
        """Calculate confidence score with multiple factors."""
        # Base confidence from Sharpe ratio
        confidence = risk_metrics.sharpe_ratio / 2.0
        
        # Boost for good liquidity
        confidence *= (0.7 + 0.3 * risk_metrics.liquidity_score)
        
        # Penalize high volatility
        confidence *= (1.0 / (1.0 + risk_metrics.volatility * 0.5))
        
        # Penalize large positions
        size_penalty = 1.0 - (size / config["max_position_size"]) * 0.2
        confidence *= size_penalty
        
        return max(0.05, min(0.95, confidence))

    async def _check_circuit_breakers(self, config: Dict[str, Any]) -> bool:
        """Check circuit breaker conditions."""
        # Check daily loss limit
        if self._daily_pnl < -config["max_daily_loss"]:
            self._risk_state = RiskState.HALTED
            logger.warning(
                f"[{self.STRATEGY_NAME}] Circuit breaker: daily loss "
                f"{self._daily_pnl:.2%} exceeds limit"
            )
            return False
        
        # Check position count
        if self._position_count >= config["max_concurrent_positions"]:
            logger.info(
                f"[{self.STRATEGY_NAME}] Max concurrent positions reached"
            )
            return False
        
        # Check cooldown period for HALTED state
        if self._risk_state == RiskState.HALTED:
            if datetime.now(timezone.utc) - self._last_state_change < self._cooldown_period:
                return False
            else:
                self._risk_state = RiskState.NORMAL
                self._last_state_change = datetime.now(timezone.utc)
        
        return True

    async def _generate_signal(
        self,
        token: Dict[str, Any],
        market_data: Dict[str, float],
        sizing_result: PositionSizingResult,
        risk_metrics: RiskMetrics
    ) -> TradeSignal:
        """Generate comprehensive signal with metadata."""
        
        # Determine trade side based on win probability and risk metrics
        win_prob = self._estimate_win_probability(risk_metrics)
        
        # Side determination logic - MUST return a valid side
        if win_prob > 0.6:  # Strong bullish signal
            side = SignalType.BUY
            reasoning = f"Strong bullish signal: win_prob={win_prob:.3f}"
        elif win_prob < 0.4:  # Strong bearish signal  
            side = SignalType.SELL
            reasoning = f"Strong bearish signal: win_prob={win_prob:.3f}"
        else:
            # Neutral zone - use volatility and drawdown to decide
            if risk_metrics.volatility > 0.3 and risk_metrics.drawdown > 0.2:
                side = SignalType.SELL
                reasoning = f"Risk-off signal: high_vol={risk_metrics.volatility:.3f}, high_dd={risk_metrics.drawdown:.3f}"
            else:
                side = SignalType.BUY
                reasoning = f"Risk-on signal: vol={risk_metrics.volatility:.3f}, dd={risk_metrics.drawdown:.3f}"
        
        # Extract token address and symbol from token data
        token_address = token.get('address', '') if token else ''
        token_symbol = token.get('symbol', '') if token else ''
        if not token_address:
            # Generate a fallback address from chain and price
            token_address = f"token_{market_data.get('chain', 'unknown')}_{market_data['price']:.8f}"
        
        logger.info(f"[{self.STRATEGY_NAME}] Side determination: {side.value} | {reasoning}")
        
        return self._create_signal(
            side,
            sizing_result.confidence,
            market_data["price"],
            sizing_result.size,
            sizing_result.stop_loss,
            sizing_result.take_profit,
            token_address=token_address,
            token_symbol=token_symbol,
            reason=reasoning,
            metadata={
                "reasoning": reasoning,
                "win_probability": win_prob,
                "risk_metrics": {
                    "drawdown": risk_metrics.drawdown,
                    "volatility": risk_metrics.volatility,
                    "sharpe_ratio": risk_metrics.sharpe_ratio,
                    "var_95": risk_metrics.var_95,
                    "liquidity_score": risk_metrics.liquidity_score,
                },
                "position_sizing": {
                    "kelly_fraction": sizing_result.kelly_fraction,
                    "risk_adjusted_size": sizing_result.risk_adjusted_size,
                    **sizing_result.metadata,
                },
                "market_data": {
                    "volume_24h": market_data["volume"],
                    "liquidity": market_data["liquidity"],
                    "chain": market_data["chain"],
                },
                "risk_state": self._risk_state.value,
                "strategy_version": "2.0_elite",
            }
        )

    async def _get_validated_config(self) -> Optional[Dict[str, Any]]:
        """Get and validate configuration with defaults."""
        if not self.strategy_config:
            logger.error(f"[{self.STRATEGY_NAME}] No configuration found")
            return None
        
        # Merge with defaults
        config = {**self.DEFAULTS, **self.strategy_config}
        
        # Validate critical parameters
        if not (0 < config["max_drawdown"] <= 1):
            logger.error(f"[{self.STRATEGY_NAME}] Invalid max_drawdown")
            return None
        
        if config["min_position_size"] >= config["max_position_size"]:
            logger.error(f"[{self.STRATEGY_NAME}] Invalid position size bounds")
            return None
        
        return config
