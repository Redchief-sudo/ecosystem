"""
Trading Module
-------------
Core trading functionality including the trading engine and trade execution.
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

__all__ = [
    'TradingEngine',
    'ExecutionPlan',
    'GasStrategy', 
    'OrderType',
    'TradeOptimizer',
    'TradeIntent',
    'TradeSide'
]
