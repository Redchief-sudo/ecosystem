"""
Data Sources Module
Provides unified data acquisition and persistence for the trading system.
"""

from .data_manager import DataManager
from .data_source import (
    DataSourceBase, 
    DataSourceType, 
    DataSourceStatus, 
    MarketData, 
    TradingSignal
)

__all__ = [
    'DataManager',
    'DataSourceBase',
    'DataSourceType', 
    'DataSourceStatus',
    'MarketData',
    'TradingSignal'
]
