"""
Type-Safe Configuration Models
===============================

Pydantic-based configuration for elite-tier type safety.
Replaces dict-based config access with validated models.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


class TradingConfig(BaseModel):
    """Trading configuration with validation."""
    mode: str = Field("paper", description="Trading mode: paper or live")
    paper_trading: bool = Field(True, description="Enable paper trading")
    private_key: Optional[str] = Field(None, description="Private key for live trading")
    starting_balance: float = Field(100.0, gt=0, description="Starting balance in USD")
    max_position_size: float = Field(0.1, gt=0, lt=1, description="Max position size as fraction")
    
    @validator("mode")
    def validate_mode(cls, v):
        if v not in ["paper", "live"]:
            raise ValueError(f"mode must be 'paper' or 'live', got: {v}")
        return v
    
    @validator("private_key")
    def validate_private_key(cls, v, values):
        mode = values.get("mode")
        paper = values.get("paper_trading")
        if mode == "live" and not paper and not v:
            raise ValueError("private_key required for live trading")
        return v


class StrategyConfig(BaseModel):
    """Strategy configuration with validation."""
    enabled: bool = Field(True, description="Enable this strategy")
    min_volume_24h: float = Field(5000, gt=0, description="Minimum 24h volume in USD")
    min_liquidity: float = Field(10000, gt=0, description="Minimum liquidity in USD")
    max_drawdown: float = Field(0.10, gt=0, lt=1, description="Maximum drawdown threshold")
    max_position_risk: float = Field(0.02, gt=0, lt=1, description="Maximum position risk")
    kelly_fraction: float = Field(0.25, gt=0, lt=1, description="Kelly criterion fraction")
    enabled_chains: List[str] = Field(default_factory=list, description="Enabled chains for this strategy")
    
    @validator("enabled_chains")
    def validate_chains(cls, v):
        valid_chains = {
            "ethereum", "bsc", "polygon", "arbitrum", "optimism",
            "avalanche", "fantom", "base", "blast", "linea"
        }
        for chain in v:
            if chain not in valid_chains:
                raise ValueError(f"Unknown chain: {chain}")
        return v


class RiskConfig(BaseModel):
    """Risk management configuration."""
    max_daily_loss: float = Field(0.05, gt=0, lt=1, description="Maximum daily loss threshold")
    max_position_size: float = Field(0.10, gt=0, lt=1, description="Maximum position size")
    max_concurrent_positions: int = Field(10, gt=0, description="Maximum concurrent positions")
    circuit_breaker_loss: float = Field(0.03, gt=0, lt=1, description="Loss threshold for circuit breaker")
    stop_loss_pct: float = Field(0.05, gt=0, lt=1, description="Default stop loss percentage")
    take_profit_pct: float = Field(0.15, gt=0, description="Default take profit percentage")


class AIConfig(BaseModel):
    """AI controller configuration."""
    dedup_ttl_seconds: int = Field(3600, gt=0, description="Deduplication TTL in seconds")
    max_dedup_size: int = Field(50000, gt=0, description="Maximum deduplication cache size")
    regime_cache_ttl: float = Field(300.0, gt=0, description="Market regime cache TTL in seconds")


class ScannerConfig(BaseModel):
    """Scanner configuration."""
    enabled: bool = Field(True, description="Enable scanner")
    scan_interval: int = Field(30, gt=0, description="Scan interval in seconds")
    max_concurrent_chains: int = Field(5, gt=0, description="Maximum concurrent chains to scan")
    per_chain_timeout: float = Field(10.0, gt=0, description="Per-chain timeout in seconds")
    enabled_chains: List[str] = Field(default_factory=list, description="Chains to scan")


class EliteConfig(BaseModel):
    """
    Elite-tier configuration model.
    
    Provides type safety and validation for all system configuration.
    """
    trading: TradingConfig = Field(default_factory=TradingConfig)
    strategies: Dict[str, StrategyConfig] = Field(default_factory=dict)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    scanners: Dict[str, ScannerConfig] = Field(default_factory=dict)
    
    class Config:
        """Pydantic configuration."""
        extra = "allow"  # Allow additional fields for backward compatibility
        validate_assignment = True  # Validate on attribute assignment
