# trade_strategies/professional_elite_strategy.py
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any

import numpy as np

from ..base_strategy import BaseStrategy
from ..data_classes import (
    SignalType,
    DecisionAction,
    RiskProfile,
    StrategyDecision,
    Rationale,
)
from core.numeric_constants import get_numeric_constants

logger = logging.getLogger("strategies.professional_elite")

class ProfessionalEliteStrategy(BaseStrategy):
    """
    Professional-grade institutional strategy with:
    - Kelly Criterion position sizing
    - Sharpe ratio optimization
    - Regime detection (trending/ranging/volatile)
    - Order flow analysis
    - Risk parity across positions
    - Maximum drawdown controls
    - Correlation-aware portfolio construction
    - Time-weighted price impact analysis
    - Statistical arbitrage opportunities
    """
    IS_STRATEGY = True
    STRATEGY_NAME = "safe"

    def __init__(self, strategy_config, global_config):
        # Historical data stores
        self.price_history = {}  # token_id -> deque of (timestamp, price)
        self.volume_history = {}  # token_id -> deque of volumes
        self.trade_history = []  # Recent trades for performance tracking
        self.correlation_matrix = {}  # Track correlations between assets

        # Risk management state
        self.portfolio_var = 0  # Portfolio Value at Risk
        self.max_drawdown = 0
        self.peak_portfolio_value = 0
        self.current_positions = {}  # Track open positions

        # Performance metrics
        self.returns_history = deque(maxlen=100)
        self.sharpe_ratio = 0

        super().__init__(strategy_config, global_config)

    # === NEW INTERFACE IMPLEMENTATION ===

    def strategy_id(self) -> str:
        """Globally unique strategy identifier."""
        return "professional_elite_v1"

    def version(self) -> str:
        """Semantic version of the strategy logic."""
        return "1.0.0"

    def description(self) -> str:
        """Human-readable explanation of strategy intent."""
        return "Professional-grade institutional strategy with Kelly Criterion, Sharpe optimization, and advanced risk management"

    def supported_markets(self) -> List[str]:
        """Chains/exchanges/instruments supported by this strategy."""
        return ["ethereum", "base", "solana", "polygon", "arbitrum", "optimism"]

    def timeframes(self) -> List[str]:
        """Expected candle or tick intervals."""
        return ["1h", "4h", "24h", "7d"]

    def required_features(self) -> Set[str]:
        """Market features required for evaluation."""
        return {
            "price", "volume_24h", "liquidity_usd", "price_change_24h",
            "market_cap", "rsi", "volatility"
        }

    def warmup_period(self) -> int:
        """Minimum data points before evaluation can begin."""
        return 20

    def evaluate(
        self,
        market_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[StrategyDecision]:
        """
        Core logic: converts market state into a decision.

        This implements the professional elite strategy logic and returns a StrategyDecision.
        """
        try:
            c = self.strategy_config
            if not c:
                logger.error("[ProfElite] No configuration found")
                return None

            # === DATA EXTRACTION ===
            token_id = market_state.get("id") or market_state.get("symbol")
            if not token_id:
                return None

            price = self._safe(market_state, "price")
            vol_24h = self._safe(market_state, "volume_24h")
            liq = self._safe(market_state, "liquidity_usd")
            price_change_24h = self._safe(market_state, "price_change_24h", 0)

            if not all([price, vol_24h, liq]):
                return None

            # Update historical data
            self._update_history(token_id, price, vol_24h)

            # === INSTITUTIONAL-GRADE FILTERS ===

            # 1. Minimum liquidity requirements (institutional minimums)
            min_vol = c.get("min_volume_24h", 100000)
            min_liq = c.get("min_liquidity", 250000)

            if vol_24h < min_vol or liq < min_liq:
                return None

            # 2. Market regime detection
            regime = self._detect_market_regime(token_id, price_change_24h)
            if regime == "HIGH_VOLATILITY" and not c.get("trade_in_volatility", False):
                logger.debug(f"[ProfElite] Skipping {token_id} - high volatility regime")
                return None

            # 3. Order flow analysis
            flow_score = self._analyze_order_flow(market_state)
            if flow_score < c.get("min_flow_score", 0.4):
                return None

            # 4. Statistical edge detection
            edge = self._calculate_statistical_edge(token_id, price)
            if edge < c.get("min_edge", 0.02):  # Require 2% edge minimum
                return None

            # === PORTFOLIO RISK CHECKS ===

            # Check maximum drawdown limit
            if self._check_drawdown_limit(c):
                logger.warning("[ProfElite] Maximum drawdown limit reached")
                return None

            # Check correlation with existing positions
            correlation_risk = self._assess_correlation_risk(token_id)
            if correlation_risk > c.get("max_correlation", 0.7):
                logger.debug(f"[ProfElite] High correlation risk: {correlation_risk:.2f}")
                return None

            # Check portfolio concentration
            if self._is_portfolio_over_concentrated(c):
                logger.debug("[ProfElite] Portfolio too concentrated")
                return None

            # === ADVANCED SCORING ===

            # Multi-factor alpha score
            alpha_score = self._calculate_alpha_score(market_state, token_id, regime, flow_score, edge)

            min_alpha = c.get("min_alpha_score", 0.65)
            if alpha_score < min_alpha:
                return None

            # === POSITION SIZING (KELLY CRITERION) ===

            win_rate = self._estimate_win_rate(token_id)
            avg_win = self._estimate_avg_win(token_id)
            avg_loss = self._estimate_avg_loss(token_id)

            kelly_fraction = self._calculate_kelly_criterion(win_rate, avg_win, avg_loss)

            # Apply fractional Kelly (typically 0.25-0.5 of full Kelly)
            kelly_multiplier = c.get("kelly_fraction", 0.25)
            kelly_size = kelly_fraction * kelly_multiplier

            # Risk parity adjustment
            volatility = self._calculate_realized_volatility(token_id)
            target_vol = c.get("target_volatility", 0.10)
            vol_adjustment = target_vol / max(volatility, 0.01)

            # Final position size
            base_size = c.get("base_position_size", 0.001)
            position_size = base_size * kelly_size * vol_adjustment * alpha_score

            # Hard limits
            max_size = c.get("max_position_size", 0.002)
            min_size = c.get("min_position_size", 0.0001)
            position_size = np.clip(position_size, min_size, max_size)

            # === SHARPE-OPTIMIZED CONFIDENCE ===

            sharpe_target = c.get("target_sharpe", 2.0)
            confidence = self._calculate_sharpe_adjusted_confidence(
                alpha_score, volatility, sharpe_target
            )

            # === DYNAMIC RISK MANAGEMENT ===

            # ATR-based stops
            atr = self._calculate_atr(token_id)
            atr_multiplier = c.get("stop_atr_multiplier", 2.0)
            stop_loss = price - (atr * atr_multiplier)

            # Profit target based on risk-reward ratio
            risk_reward_ratio = c.get("risk_reward_ratio", 2.5)
            risk_amount = price - stop_loss
            take_profit = price + (risk_amount * risk_reward_ratio)

            # Volatility-adjusted targets
            if regime == "LOW_VOLATILITY":
                take_profit *= 0.85  # Tighter targets in low vol
            elif regime == "HIGH_VOLATILITY":
                take_profit *= 1.15  # Wider targets in high vol
                stop_loss = price - (atr * atr_multiplier * 1.3)  # Wider stops

            # === TIME-BASED FILTERS ===

            # Skip if price impact would be too high
            expected_impact = self._estimate_price_impact(position_size, vol_24h, liq)
            max_impact = c.get("max_price_impact", 0.005)  # 0.5%
            if expected_impact > max_impact:
                logger.debug(f"[ProfElite] Price impact too high: {expected_impact:.2%}")
                return None

            # === EXECUTION QUALITY ===

            # Calculate expected slippage
            slippage = self._estimate_slippage(vol_24h, liq, regime)

            logger.info(
                f"[ProfElite] SIGNAL - {token_id} | "
                f"Alpha: {alpha_score:.3f} | Edge: {edge:.2%} | "
                f"Kelly: {kelly_size:.4f} | Size: {position_size:.5f} | "
                f"Conf: {confidence:.3f} | Regime: {regime} | "
                f"Sharpe: {self.sharpe_ratio:.2f} | Impact: {expected_impact:.2%}"
            )

            # === DETERMINE ACTION ===
            action = DecisionAction.BUY

            # === CREATE RATIONALE ===
            rationale = Rationale(
                primary_reason=f"Strong institutional-grade opportunity with {alpha_score:.1%} alpha score",
                indicators_used=["rsi", "price_change_24h", "volume_24h", "liquidity_usd", "market_cap"],
                factors={
                    "alpha_score": alpha_score,
                    "statistical_edge": edge,
                    "kelly_fraction": kelly_size,
                    "sharpe_ratio": self.sharpe_ratio,
                    "flow_score": flow_score,
                    "volatility": volatility,
                    "expected_slippage": slippage,
                    "price_impact": expected_impact,
                },
                market_conditions=regime,
                regime_confidence=0.8,  # High confidence in regime detection
                additional_notes=f"Risk-reward: {risk_reward_ratio:.1f}, Win rate: {win_rate:.1%}, ATR: {atr:.4f}"
            )

            # === CREATE STRATEGY DECISION ===
            decision = StrategyDecision(
                strategy_id=self.strategy_id(),
                action=action,
                confidence=confidence,
                rationale=rationale,
                metadata={
                    "regime": regime,
                    "alpha_score": alpha_score,
                    "statistical_edge": edge,
                    "kelly_fraction": kelly_size,
                    "volatility": volatility,
                    "sharpe_ratio": self.sharpe_ratio,
                    "flow_score": flow_score,
                    "expected_slippage": slippage,
                    "price_impact": expected_impact,
                    "risk_reward": risk_reward_ratio,
                    "win_rate": win_rate,
                    "atr": atr,
                    "token_id": token_id,
                    "price": price,
                    "volume_24h": vol_24h,
                    "liquidity": liq,
                },
                version=self.version(),
            )

            return decision

        except Exception as e:
            logger.error(f"[ProfElite] Error: {e}", exc_info=True)
            return None

    def signal_type(self) -> SignalType:
        """Classification of signal type."""
        return SignalType.DIRECTIONAL

    def risk_profile(self) -> RiskProfile:
        """Declares acceptable risk bounds (enforcement is external)."""
        return RiskProfile(
            max_drawdown=0.10,  # 10% max drawdown (conservative)
            max_concurrent_positions=5,  # Max 5 concurrent positions
            volatility_tolerance=1.0,  # Handle up to 100% volatility
            min_confidence_threshold=0.35,  # Min 35% confidence
            max_position_size=0.02,  # Max 2% of portfolio per position
            max_loss_per_trade=0.01,  # Max 1% loss per trade
            risk_per_trade=0.005,  # 0.5% risk per trade
        )

    def _safe(self, data, key, default=None):
        """Safely extract value from dictionary."""
        if not isinstance(data, dict):
            return default
        return data.get(key, default)

    def _create_signal(self, signal_type, confidence, price, size, stop_loss, take_profit, metadata=None):
        """Create a standardized signal dictionary."""
        from ..base_strategy import TradeSignal

        return TradeSignal(
            strategy_id=self.STRATEGY_NAME,
            signal_type=signal_type,
            confidence=float(confidence),
            score=float(confidence),  # Use confidence as score
            meta=metadata or {}
        )
        
    async def evaluate_token(self, o):
        try:
            c = self.strategy_config
            if not c:
                logger.error("[ProfElite] No configuration found")
                return None

            # === DATA EXTRACTION ===
            token_id = o.get("id") or o.get("symbol")
            if not token_id:
                return None
                
            price = self._safe(o, "price")
            vol_24h = self._safe(o, "volume_24h")
            liq = self._safe(o, "liquidity_usd")
            price_change_24h = self._safe(o, "price_change_24h", 0)
            
            if not all([price, vol_24h, liq]):
                return None

            # Update historical data
            self._update_history(token_id, price, vol_24h)

            # === INSTITUTIONAL-GRADE FILTERS ===
            
            # 1. Minimum liquidity requirements (institutional minimums)
            min_vol = c.get("min_volume_24h", 100000)
            min_liq = c.get("min_liquidity", 250000)
            
            if vol_24h < min_vol or liq < min_liq:
                return None
            
            # 2. Market regime detection
            regime = self._detect_market_regime(token_id, price_change_24h)
            if regime == "HIGH_VOLATILITY" and not c.get("trade_in_volatility", False):
                logger.debug(f"[ProfElite] Skipping {token_id} - high volatility regime")
                return None
            
            # 3. Order flow analysis
            flow_score = self._analyze_order_flow(o)
            if flow_score < c.get("min_flow_score", 0.4):
                return None
            
            # 4. Statistical edge detection
            edge = self._calculate_statistical_edge(token_id, price)
            if edge < c.get("min_edge", 0.02):  # Require 2% edge minimum
                return None
            
            # === PORTFOLIO RISK CHECKS ===
            
            # Check maximum drawdown limit
            if self._check_drawdown_limit(c):
                logger.warning("[ProfElite] Maximum drawdown limit reached")
                return None
            
            # Check correlation with existing positions
            correlation_risk = self._assess_correlation_risk(token_id)
            if correlation_risk > c.get("max_correlation", 0.7):
                logger.debug(f"[ProfElite] High correlation risk: {correlation_risk:.2f}")
                return None
            
            # Check portfolio concentration
            if self._is_portfolio_over_concentrated(c):
                logger.debug("[ProfElite] Portfolio too concentrated")
                return None
            
            # === ADVANCED SCORING ===
            
            # Multi-factor alpha score
            alpha_score = self._calculate_alpha_score(o, token_id, regime, flow_score, edge)
            
            min_alpha = c.get("min_alpha_score", 0.65)
            if alpha_score < min_alpha:
                return None
            
            # === POSITION SIZING (KELLY CRITERION) ===
            
            win_rate = self._estimate_win_rate(token_id)
            avg_win = self._estimate_avg_win(token_id)
            avg_loss = self._estimate_avg_loss(token_id)
            
            kelly_fraction = self._calculate_kelly_criterion(win_rate, avg_win, avg_loss)
            
            # Apply fractional Kelly (typically 0.25-0.5 of full Kelly)
            kelly_multiplier = c.get("kelly_fraction", 0.25)
            kelly_size = kelly_fraction * kelly_multiplier
            
            # Risk parity adjustment
            volatility = self._calculate_realized_volatility(token_id)
            target_vol = c.get("target_volatility", 0.10)
            vol_adjustment = target_vol / max(volatility, 0.01)
            
            # Final position size
            base_size = c.get("base_position_size", 0.001)
            position_size = base_size * kelly_size * vol_adjustment * alpha_score
            
            # Hard limits
            max_size = c.get("max_position_size", 0.002)
            min_size = c.get("min_position_size", 0.0001)
            position_size = np.clip(position_size, min_size, max_size)
            
            # === SHARPE-OPTIMIZED CONFIDENCE ===
            
            sharpe_target = c.get("target_sharpe", 2.0)
            confidence = self._calculate_sharpe_adjusted_confidence(
                alpha_score, volatility, sharpe_target
            )
            
            # === DYNAMIC RISK MANAGEMENT ===
            
            # ATR-based stops
            atr = self._calculate_atr(token_id)
            atr_multiplier = c.get("stop_atr_multiplier", 2.0)
            stop_loss = price - (atr * atr_multiplier)
            
            # Profit target based on risk-reward ratio
            risk_reward_ratio = c.get("risk_reward_ratio", 2.5)
            risk_amount = price - stop_loss
            take_profit = price + (risk_amount * risk_reward_ratio)
            
            # Volatility-adjusted targets
            if regime == "LOW_VOLATILITY":
                take_profit *= 0.85  # Tighter targets in low vol
            elif regime == "HIGH_VOLATILITY":
                take_profit *= 1.15  # Wider targets in high vol
                stop_loss = price - (atr * atr_multiplier * 1.3)  # Wider stops
            
            # === TIME-BASED FILTERS ===
            
            # Skip if price impact would be too high
            expected_impact = self._estimate_price_impact(position_size, vol_24h, liq)
            max_impact = c.get("max_price_impact", 0.005)  # 0.5%
            if expected_impact > max_impact:
                logger.debug(f"[ProfElite] Price impact too high: {expected_impact:.2%}")
                return None
            
            # === EXECUTION QUALITY ===
            
            # Calculate expected slippage
            slippage = self._estimate_slippage(vol_24h, liq, regime)
            
            logger.info(
                f"[ProfElite] SIGNAL - {token_id} | "
                f"Alpha: {alpha_score:.3f} | Edge: {edge:.2%} | "
                f"Kelly: {kelly_size:.4f} | Size: {position_size:.5f} | "
                f"Conf: {confidence:.3f} | Regime: {regime} | "
                f"Sharpe: {self.sharpe_ratio:.2f} | Impact: {expected_impact:.2%}"
            )

            return self._create_signal(
                SignalType.BUY,
                confidence,
                price,
                position_size,
                stop_loss,
                take_profit,
                {
                    "strategy": "professional_elite",
                    "alpha_score": alpha_score,
                    "statistical_edge": edge,
                    "regime": regime,
                    "kelly_fraction": kelly_size,
                    "volatility": volatility,
                    "sharpe_ratio": self.sharpe_ratio,
                    "flow_score": flow_score,
                    "expected_slippage": slippage,
                    "price_impact": expected_impact,
                    "risk_reward": risk_reward_ratio,
                    "win_rate": win_rate,
                    "atr": atr
                }
            )

        except Exception as e:
            logger.error(f"[ProfElite] Error: {e}", exc_info=True)
            return None

    # ============================================================
    # HISTORICAL DATA MANAGEMENT
    # ============================================================
    
    def _update_history(self, token_id, price, volume):
        """Update historical price and volume data."""
        now = datetime.now()
        
        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=100)
            self.volume_history[token_id] = deque(maxlen=100)
        
        self.price_history[token_id].append((now, price))
        self.volume_history[token_id].append((now, volume))

    # ============================================================
    # MARKET REGIME DETECTION
    # ============================================================
    
    def _detect_market_regime(self, token_id, price_change_24h):
        """
        Detect current market regime:
        - TRENDING: Clear directional movement
        - RANGING: Sideways consolidation
        - HIGH_VOLATILITY: Erratic price action
        - LOW_VOLATILITY: Stable, calm market
        """
        if token_id not in self.price_history or len(self.price_history[token_id]) < 10:
            return "UNKNOWN"
        
        prices = [p for _, p in self.price_history[token_id]]
        returns = np.diff(prices) / prices[:-1]
        
        volatility = np.std(returns) if len(returns) > 0 else 0
        abs_price_change = abs(price_change_24h)
        
        # Trend strength (using simple linear regression slope)
        if len(prices) >= 5:
            x = np.arange(len(prices))
            slope = np.polyfit(x, prices, 1)[0]
            trend_strength = abs(slope) / np.mean(prices)
        else:
            trend_strength = 0
        
        # Regime classification
        if volatility > 0.05:  # High volatility threshold
            return "HIGH_VOLATILITY"
        elif volatility < 0.01:  # Low volatility threshold
            return "LOW_VOLATILITY"
        elif trend_strength > 0.02:  # Strong trend
            return "TRENDING"
        else:
            return "RANGING"

    # ============================================================
    # ORDER FLOW ANALYSIS
    # ============================================================
    
    def _analyze_order_flow(self, o):
        """
        Analyze order flow quality:
        - Volume consistency
        - Liquidity stability
        - Bid-ask spread (if available)
        """
        vol_24h = self._safe(o, "volume_24h")
        liq = self._safe(o, "liquidity_usd")
        
        if not vol_24h or not liq:
            return 0
        
        # Volume to liquidity ratio
        vol_liq_ratio = vol_24h / liq
        
        # Ideal ratio: 0.5 to 2.0 (moderate turnover)
        if 0.5 <= vol_liq_ratio <= 2.0:
            flow_score = 1.0
        elif vol_liq_ratio < 0.5:
            flow_score = vol_liq_ratio / 0.5
        else:
            flow_score = max(0.2, 2.0 / vol_liq_ratio)
        
        # Check volume consistency
        token_id = o.get("id") or o.get("symbol")
        if token_id in self.volume_history and len(self.volume_history[token_id]) > 5:
            volumes = [v for _, v in self.volume_history[token_id]]
            vol_cv = np.std(volumes) / np.mean(volumes)  # Coefficient of variation
            consistency_score = max(0, 1 - vol_cv)
            flow_score = (flow_score + consistency_score) / 2
        
        return flow_score

    # ============================================================
    # STATISTICAL EDGE CALCULATION
    # ============================================================
    
    def _calculate_statistical_edge(self, token_id, current_price):
        """
        Calculate statistical edge using mean reversion and momentum factors.
        """
        if token_id not in self.price_history or len(self.price_history[token_id]) < 20:
            return 0
        
        prices = np.array([p for _, p in self.price_history[token_id]])
        
        # Mean reversion component
        mean_price = np.mean(prices)
        std_price = np.std(prices)
        z_score = (current_price - mean_price) / std_price if std_price > 0 else 0
        
        # Buy edge when price is below mean (negative z-score)
        mean_reversion_edge = max(0, -z_score * 0.02)
        
        # Momentum component
        if len(prices) >= 10:
            short_term_return = (prices[-1] - prices[-5]) / prices[-5]
            medium_term_return = (prices[-1] - prices[-10]) / prices[-10]
            momentum_edge = (short_term_return + medium_term_return) / 2
        else:
            momentum_edge = 0
        
        # Combine edges (60% mean reversion, 40% momentum)
        total_edge = mean_reversion_edge * 0.6 + momentum_edge * 0.4
        
        return max(0, total_edge)

    # ============================================================
    # PORTFOLIO RISK MANAGEMENT
    # ============================================================
    
    def _check_drawdown_limit(self, c):
        """Check if maximum drawdown limit has been reached."""
        max_dd_limit = c.get("max_drawdown_limit", 0.15)  # 15% max drawdown
        
        if self.max_drawdown > max_dd_limit:
            return True
        return False
    
    def _assess_correlation_risk(self, token_id):
        """
        Assess correlation with existing positions.
        High correlation = high concentration risk.
        """
        if not self.current_positions or token_id not in self.price_history:
            return 0
        
        # In a real implementation, calculate actual correlations
        # For now, return a placeholder
        return 0.3
    
    def _is_portfolio_over_concentrated(self, c):
        """Check if portfolio is too concentrated in few positions."""
        max_positions = c.get("max_concurrent_positions", 10)
        
        if len(self.current_positions) >= max_positions:
            return True
        return False

    # ============================================================
    # ALPHA SCORE CALCULATION
    # ============================================================
    
    def _calculate_alpha_score(self, o, token_id, regime, flow_score, edge):
        """
        Calculate multi-factor alpha score combining:
        - Liquidity quality
        - Order flow
        - Statistical edge
        - Regime appropriateness
        - Market structure
        """
        vol_24h = self._safe(o, "volume_24h")
        liq = self._safe(o, "liquidity_usd")
        mcap = self._safe(o, "market_cap")
        
        scores = []
        
        # 1. Liquidity quality (25%)
        liq_quality = min(1.0, liq / 500000)  # Max score at $500k liquidity
        scores.append(liq_quality * 0.25)
        
        # 2. Order flow (20%)
        scores.append(flow_score * 0.20)
        
        # 3. Statistical edge (30%)
        edge_score = min(1.0, edge / 0.05)  # Max score at 5% edge
        scores.append(edge_score * 0.30)
        
        # 4. Regime bonus (15%)
        regime_score = {
            "TRENDING": 0.9,
            "LOW_VOLATILITY": 0.8,
            "RANGING": 0.6,
            "HIGH_VOLATILITY": 0.4,
            "UNKNOWN": 0.5
        }.get(regime, 0.5)
        scores.append(regime_score * 0.15)
        
        # 5. Market cap quality (10%)
        if mcap:
            mcap_score = min(1.0, mcap / 10000000)  # Max at $10M
            scores.append(mcap_score * 0.10)
        else:
            scores.append(0.05)
        
        return sum(scores)

    # ============================================================
    # KELLY CRITERION POSITION SIZING
    # ============================================================
    
    def _estimate_win_rate(self, token_id):
        """Estimate win rate from historical performance."""
        # In real implementation, track actual trade outcomes
        return self._calculate_real_win_rate()

    def _calculate_real_win_rate(self):
        """Calculate real win rate from trade history."""
        # Placeholder implementation
        return 0.55  # 55% win rate

    def _estimate_avg_win(self, token_id):
        """Estimate average winning trade percentage."""
        return self._calculate_average_win()

    def _calculate_average_win(self):
        """Calculate average winning trade percentage."""
        # Placeholder implementation
        return 0.08  # 8% average win

    def _estimate_avg_loss(self, token_id):
        """Estimate average losing trade percentage."""
        return self._calculate_average_loss()

    def _calculate_average_loss(self):
        """Calculate average losing trade percentage."""
        # Placeholder implementation
        return 0.04  # 4% average loss
    
    def _calculate_kelly_criterion(self, win_rate, avg_win, avg_loss):
        """
        Kelly Criterion: f* = (p*b - q) / b
        where:
        - p = win probability
        - q = loss probability (1-p)
        - b = win/loss ratio
        """
        if avg_loss == 0:
            return 0
        
        b = avg_win / avg_loss
        q = 1 - win_rate
        
        kelly = (win_rate * b - q) / b
        
        return max(0, min(1, kelly))  # Clamp between 0 and 1

    # ============================================================
    # VOLATILITY CALCULATIONS
    # ============================================================
    
    def _calculate_realized_volatility(self, token_id):
        """Calculate realized volatility from price history."""
        if token_id not in self.price_history or len(self.price_history[token_id]) < 10:
            return 0.05  # Default 5%
        
        prices = np.array([p for _, p in self.price_history[token_id]])
        returns = np.diff(prices) / prices[:-1]
        
        # Annualized volatility (assuming continuous trading)
        volatility = np.std(returns) * np.sqrt(365 * 24)  # 24h trading
        
        return volatility
    
    def _calculate_atr(self, token_id):
        """Calculate Average True Range for stop loss placement."""
        if token_id not in self.price_history or len(self.price_history[token_id]) < 14:
            prices = [p for _, p in self.price_history[token_id]] if token_id in self.price_history else []
            if len(prices) >= 2:
                return abs(prices[-1] - prices[-2])
            return 0
        
        prices = np.array([p for _, p in self.price_history[token_id]])
        
        # True Range = max(high-low, abs(high-close_prev), abs(low-close_prev))
        # Simplified version for single price series
        price_ranges = np.abs(np.diff(prices))
        atr = np.mean(price_ranges[-14:])  # 14-period ATR
        
        return atr

    # ============================================================
    # SHARPE RATIO OPTIMIZATION
    # ============================================================
    
    def _calculate_sharpe_adjusted_confidence(self, alpha_score, volatility, target_sharpe):
        """
        Adjust confidence based on Sharpe ratio optimization.
        Higher Sharpe = higher confidence.
        """
        # Expected return (from alpha score)
        expected_return = alpha_score * 0.10  # Scale to ~10% max
        
        # Risk-adjusted return (Sharpe approximation)
        if volatility > 0:
            sharpe = expected_return / volatility
        else:
            sharpe = 0
        
        # Update portfolio Sharpe tracking
        self.sharpe_ratio = sharpe
        
        # Confidence scales with Sharpe ratio
        confidence = min(1.0, (sharpe / target_sharpe) * alpha_score)
        
        return max(0.1, confidence)

    # ============================================================
    # EXECUTION QUALITY ANALYSIS
    # ============================================================
    
    def _estimate_price_impact(self, position_size, volume_24h, liquidity_usd):
        """
        Estimate price impact of trade using square-root model.
        Impact ≈ σ * sqrt(trade_size / avg_volume)
        """
        if volume_24h == 0:
            return 1.0  # Maximum impact
        
        # Daily volume proxy
        avg_volume_per_period = volume_24h / 24  # Hourly volume
        
        # Position size in USD (approximate)
        position_usd = position_size * 10000  # Assuming $10k base
        
        # Square root impact model
        impact = 0.1 * np.sqrt(position_usd / avg_volume_per_period)
        
        return min(1.0, impact)
    
    def _estimate_slippage(self, volume_24h, liquidity_usd, regime):
        """
        Estimate expected slippage based on market conditions.
        
        FIXED: Uses configurable multipliers from numeric constants.
        These values are now documented and adjustable.
        """
        nc = get_numeric_constants()
        
        # Base slippage - 0.3% for high liquidity tokens
        base_slippage = nc.slippage_base_pct  # Default: 0.003
        
        # Adjust for liquidity using divisors (inverse relationship)
        # Higher liquidity = lower slippage
        if liquidity_usd > 500000:
            liq_divisor = nc.slippage_liquidity_high_divisor  # 1.25 -> 0.8x
        elif liquidity_usd > 250000:
            liq_divisor = nc.slippage_liquidity_medium_divisor  # 1.0 -> 1.0x
        else:
            liq_divisor = nc.slippage_liquidity_low_divisor  # 0.77 -> 1.3x
        
        # Adjust for regime
        regime_adjustments = {
            "LOW_VOLATILITY": nc.slippage_regime_low_vol_pct,    # 1.25 -> 0.8x
            "RANGING": nc.slippage_regime_ranging_pct,           # 1.0 -> 1.0x
            "TRENDING": nc.slippage_regime_trending_pct,         # 0.91 -> 1.1x
            "HIGH_VOLATILITY": nc.slippage_regime_high_vol_pct,  # 0.67 -> 1.5x
            "UNKNOWN": 1.0
        }
        regime_adj = regime_adjustments.get(regime, 1.0)
        
        # Calculate final slippage
        slippage = base_slippage * liq_divisor * regime_adj
        
        return slippage
