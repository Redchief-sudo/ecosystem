"""
Centralized Numeric Constants for Trading System
=================================================
All hardcoded numeric values are defined here with documentation
and justification for each value.

These values can be overridden via configuration.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class NumericConstants:
    """
    Centralized numeric constants with documentation.
    
    All constants have documentation explaining their derivation
    and can be overridden via configuration.
    """
    
    # =========================================================================
    # REGIME DETECTION THRESHOLDS
    # =========================================================================
    # Based on typical crypto market behavior. 15% daily volatility is
    # approximately 3x the typical daily volatility of major crypto assets.
    volatility_high_threshold: float = 0.15
    
    # Low volatility threshold - assets below 2% daily volatility are
    # considered to be in a calm/sideways market.
    volatility_low_threshold: float = 0.02
    
    # Price change threshold for trend detection - 5% is a significant
    # daily move in most markets.
    price_change_trend_threshold: float = 0.05
    
    # =========================================================================
    # MARKET CAP SCORING
    # =========================================================================
    # Optimal market cap for scoring - mid-cap tokens tend to have the
    # best risk/reward ratio. $100M is a sweet spot between safety and upside.
    market_cap_optimal_usd: float = 100_000_000
    
    # Market cap scoring steepness - controls how quickly scores fall off
    # from the optimal market cap. Higher = narrower range of good scores.
    market_cap_score_steepness: float = 2.0
    
    # =========================================================================
    # REGIME WEIGHT BLENDING
    # =========================================================================
    # How much to weight regime-specific weights vs current adaptive weights.
    # 60/40 split gives regime proper influence while allowing adaptation.
    regime_weight_blend_ratio: float = 0.60
    
    # =========================================================================
    # PERFORMANCE FEEDBACK
    # =========================================================================
    # Performance threshold for weight adjustment - require 10% outperformance
    # before adjusting weights to avoid overfitting to noise.
    performance_adjustment_threshold: float = 0.10
    
    # Weight adjustment factor - 5% change is conservative to avoid
    # overreacting to short-term performance.
    weight_adjustment_factor: float = 0.05
    
    # =========================================================================
    # MINIMUM THRESHOLDS
    # =========================================================================
    # Minimum position size in USD - set to $5 to ensure meaningful trades
    # while not being too restrictive for small accounts.
    min_position_size_usd: float = 5.0
    
    # Minimum 24h volume in USD - filters for liquid tokens.
    # $5000 is a minimum for basic liquidity.
    min_volume_24h_usd: float = 5000.0
    
    # Minimum liquidity in USD - $250k is a reasonable floor for
    # institutional-grade liquidity requirements.
    min_liquidity_usd: float = 250_000.0
    
    # =========================================================================
    # AGGRESSIVE STRATEGY
    # =========================================================================
    # Base position size as fraction of capital - 1.5% is aggressive
    # but allows for proper diversification.
    aggressive_base_position_size: float = 0.015
    
    # Maximum position size for aggressive strategy - 8% of capital
    # is the upper bound for any single trade.
    aggressive_max_position_size: float = 0.08
    
    # Volatility divisor for position sizing - higher values mean
    # less sensitivity to volatility. 2.0 is a balanced choice.
    aggressive_volatility_divisor: float = 2.0
    
    # Minimum confidence for aggressive trades - lower than conservative
    # to allow more opportunities.
    aggressive_min_confidence: float = 0.35
    
    # =========================================================================
    # SAFE/CONSERVATIVE STRATEGY
    # =========================================================================
    # Base position size - 0.1% is conservative.
    safe_base_position_size: float = 0.001
    
    # Maximum position size for safe strategy - 2% cap.
    safe_max_position_size: float = 0.02
    
    # Kelly fraction for safe strategy - quarter Kelly is standard
    # for risk-averse positioning.
    safe_kelly_fraction: float = 0.25
    
    # =========================================================================
    # MEAN REVERSION STRATEGY
    # =========================================================================
    # Standard deviation threshold for mean reversion signal - 2 standard
    # deviations is a common choice in statistical trading.
    mean_reversion_std_threshold: float = 2.0
    
    # Extreme deviation threshold - 3 SD is a rare, high-conviction signal.
    mean_reversion_extreme_threshold: float = 3.0
    
    # Maximum mean reversion half-life in periods - if reversion takes
    # longer than 50 periods, the opportunity is likely not mean-reverting.
    mean_reversion_max_half_life: float = 50.0
    
    # Minimum Hurst exponent for mean reversion - below 0.5 indicates
    # anti-persistent (mean-reverting) behavior.
    mean_reversion_min_hurst: float = 0.30
    
    # Maximum Hurst exponent for mean reversion - below 0.5 is the
    # threshold for mean-reverting behavior.
    mean_reversion_max_hurst: float = 0.50
    
    # Volume surge threshold - 150% of average is significant volume.
    mean_reversion_volume_surge_threshold: float = 1.5
    
    # Maximum position size for mean reversion - 8% cap.
    mean_reversion_max_position_size: float = 0.08
    
    # Minimum position size for mean reversion - 1% floor.
    mean_reversion_min_position_size: float = 0.01
    
    # Bollinger squeeze threshold - below 0.3 indicates squeeze.
    mean_reversion_squeeze_threshold: float = 0.30
    
    # Minimum Hurst exponent allowed (anti-persistent).
    mean_reversion_hurst_min: float = 0.30
    
    # Maximum Hurst exponent allowed (mean-reverting).
    mean_reversion_hurst_max: float = 0.50
    
    # Z-score EWMA decay factor for velocity calculation.
    mean_reversion_zscore_decay: float = 0.90
    
    # =========================================================================
    # STOP LOSS AND TAKE PROFIT
    # =========================================================================
    # Base stop loss percentage - 5% is a standard stop loss.
    stop_loss_pct: float = 0.05
    
    # Base take profit percentage - 10% is a standard target.
    take_profit_pct: float = 0.10
    
    # Risk-reward ratio minimum - require at least 2:1 R:R.
    risk_reward_ratio_min: float = 2.0
    
    # =========================================================================
    # SLIPPAGE ESTIMATION
    # =========================================================================
    # Base slippage for high liquidity tokens - 0.3% is realistic
    # for major pairs on established DEXs.
    slippage_base_pct: float = 0.003
    
    # Slippage divisor for high liquidity - adjusts based on liquidity.
    # Higher liquidity = lower slippage.
    slippage_liquidity_high_divisor: float = 1.25  # 0.8x base
    
    # Slippage divisor for medium liquidity.
    slippage_liquidity_medium_divisor: float = 1.0  # 1.0x base
    
    # Slippage divisor for low liquidity.
    slippage_liquidity_low_divisor: float = 0.77  # 1.3x base
    
    # Slippage adjustment for low volatility regime.
    slippage_regime_low_vol_pct: float = 1.25  # 0.8x base
    
    # Slippage adjustment for high volatility regime.
    slippage_regime_high_vol_pct: float = 0.67  # 1.5x base
    
    # Slippage adjustment for trending regime.
    slippage_regime_trending_pct: float = 0.91  # 1.1x base
    
    # Slippage adjustment for ranging regime.
    slippage_regime_ranging_pct: float = 1.0  # 1.0x base
    
    # =========================================================================
    # AI CONTROLLER
    # =========================================================================
    # Baseline score for strategies with no trading history - low score
    # prevents bias toward new strategies while still allowing exploration.
    untested_strategy_baseline: float = 0.10
    
    # Minimum win rate threshold for strategy inclusion - 55% win rate
    # is a reasonable minimum for live trading.
    min_win_rate: float = 0.55
    
    # Minimum Sharpe ratio for strategy inclusion - 0.5 is a basic
    # threshold for acceptable risk-adjusted returns.
    min_sharpe_ratio: float = 0.50
    
    # Maximum drawdown threshold - 30% is a common maximum.
    max_drawdown: float = 0.30
    
    # Maximum position size as percentage of capital - 10% cap
    # ensures proper diversification.
    max_position_size_pct: float = 0.10
    
    # Exploration rate for epsilon-greedy selection - 10% exploration
    # balances exploitation of good strategies with discovery.
    exploration_rate: float = 0.10
    
    # UCB confidence parameter - 2.0 is the standard UCB1 parameter.
    ucb_confidence: float = 2.0
    
    # Minimum trades before strategy is considered for selection.
    min_trades_for_inclusion: int = 20
    
    # Ensemble size - 5 strategies provides diversification.
    ensemble_size: int = 5
    
    # Minimum strategy weight - prevents any single strategy
    # from dominating the ensemble.
    min_strategy_weight: float = 0.05
    
    # Rebalance interval - rebalance every 100 trades.
    rebalance_interval: int = 100
    
    # Performance decay factor - recent performance weighted more.
    performance_decay_factor: float = 0.95
    
    # Quarantine threshold drawdown - 50% drawdown triggers quarantine.
    quarantine_threshold_drawdown: float = 0.50
    
    # =========================================================================
    # REGIME WEIGHTS BY MARKET REGIME
    # =========================================================================
    # Weights for different scoring factors in bull trending markets.
    weights_bull_trending: Dict[str, float] = None
    
    # Weights for bear trending markets.
    weights_bear_trending: Dict[str, float] = None
    
    # Weights for bull markets.
    weights_bull: Dict[str, float] = None
    
    # Weights for bear markets.
    weights_bear: Dict[str, float] = None
    
    # Weights for sideways markets.
    weights_sideways: Dict[str, float] = None
    
    # Weights for high volatility markets.
    weights_high_volatility: Dict[str, float] = None
    
    # Weights for low volatility markets.
    weights_low_volatility: Dict[str, float] = None
    
    def __post_init__(self):
        """Initialize complex weight structures."""
        self.weights_bull_trending = {
            'price_momentum': 0.45,
            'volume_liquidity': 0.15,
            'market_cap': 0.10,
            'volatility': 0.15,
            'social_sentiment': 0.15
        }
        
        self.weights_bear_trending = {
            'price_momentum': 0.10,
            'volume_liquidity': 0.35,
            'market_cap': 0.40,
            'volatility': 0.05,
            'social_sentiment': 0.10
        }
        
        self.weights_bull = {
            'price_momentum': 0.40,
            'volume_liquidity': 0.20,
            'market_cap': 0.15,
            'volatility': 0.10,
            'social_sentiment': 0.15
        }
        
        self.weights_bear = {
            'price_momentum': 0.15,
            'volume_liquidity': 0.30,
            'market_cap': 0.35,
            'volatility': 0.15,
            'social_sentiment': 0.05
        }
        
        self.weights_sideways = {
            'price_momentum': 0.20,
            'volume_liquidity': 0.30,
            'market_cap': 0.25,
            'volatility': 0.15,
            'social_sentiment': 0.10
        }
        
        self.weights_high_volatility = {
            'price_momentum': 0.10,
            'volume_liquidity': 0.35,
            'market_cap': 0.35,
            'volatility': 0.05,
            'social_sentiment': 0.15
        }
        
        self.weights_low_volatility = {
            'price_momentum': 0.35,
            'volume_liquidity': 0.25,
            'market_cap': 0.20,
            'volatility': 0.15,
            'social_sentiment': 0.05
        }


# Global instance for easy import
NUMERIC_CONSTANTS = NumericConstants()


def get_numeric_constants() -> NumericConstants:
    """Get the global numeric constants instance."""
    return NUMERIC_CONSTANTS


def override_numeric_constants(overrides: Dict[str, float]) -> None:
    """
    Override numeric constants with custom values.
    
    Args:
        overrides: Dictionary of constant names to new values
        
    Example:
        override_numeric_constants({
            'min_liquidity_usd': 500000,
            'stop_loss_pct': 0.03
        })
    """
    for key, value in overrides.items():
        if hasattr(NUMERIC_CONSTANTS, key):
            setattr(NUMERIC_CONSTANTS, key, value)
            # Validate the type
            current_type = type(getattr(NUMERIC_CONSTANTS, key))
            if not isinstance(value, current_type):
                raise TypeError(f"{key} must be {current_type.__name__}, got {type(value).__name__}")
        else:
            raise ValueError(f"Unknown numeric constant: {key}")

