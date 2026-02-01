"""
Trading Module
-------------
Core trading functionality including the trading engine and trade execution.

Canonical structure:
- execution: Trade execution engines and management
- trade_intent: Trade optimization and intent compilation
- treasury: Capital and gas management
- token_pipeline: Token data processing
- bridges: Cross-chain and external integrations
"""

from .execution.trade_engine import TradingEngine
from .trade_intent.trade_optimizer import (
    ExecutionPlan, 
    GasStrategy, 
    OrderType, 
    TradeOptimizer,
    TradeIntent,
    TradeSide
)
from .treasury.treasury_manager import TreasuryManager
from .treasury.gas_treasury import GasTreasury

__all__ = [
    # Execution
    'TradingEngine',
    # Trade Intent & Optimization
    'ExecutionPlan',
    'GasStrategy', 
    'OrderType',
    'TradeOptimizer',
    'TradeIntent',
    'TradeSide',
    # Treasury
    'TreasuryManager',
    'GasTreasury',]