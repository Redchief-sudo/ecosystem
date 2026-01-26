"""
Trading Execution Module
========================

Handles trade execution across multiple networks.
"""

# Legacy execution components (EVM-only)
from .trade_executor import HybridTradeExecutor
from .trade_engine import TradingEngine
from .post_trade_manager import PostTradeManager
from .execution_admission_controller import ExecutionAdmissionController

# New multi-chain execution
from .multi_chain_executor import (
    BaseNetworkExecutor,
    EVMExecutor,
    SolanaExecutor,
    AptosExecutor,
    SuiExecutor,
    MultiChainExecutor,
    ExecutionResult,
    ExecutionStatus,
    get_multi_chain_executor,
    initialize_multi_chain_executor
)

__all__ = [
    # Legacy execution
    'HybridTradeExecutor',
    'TradingEngine',
    'PostTradeManager',
    'ExecutionAdmissionController',
    
    # Multi-chain execution
    'BaseNetworkExecutor',
    'EVMExecutor',
    'SolanaExecutor',
    'AptosExecutor',
    'SuiExecutor',
    'MultiChainExecutor',
    'ExecutionResult',
    'ExecutionStatus',
    'get_multi_chain_executor',
    'initialize_multi_chain_executor',
]
