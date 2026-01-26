"""
Trading Execution Protocols
============================

Protocol-based interfaces for decoupling execution components.
Enables testing with mocks and swapping implementations.
"""

from typing import Any, Dict, Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class ExecutionPlan:
    """Execution plan passed to executor."""
    token_address: str
    chain: str
    amount: float
    is_buy: bool
    target_price: float
    order_type: str
    time_in_force: str
    policy_versions: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class ExecutionResult:
    """Result from trade execution."""
    success: bool
    transaction_hash: str | None = None
    error: str | None = None
    executed_price: float | None = None
    executed_amount: float | None = None
    gas_used: int | None = None
    router_used: str | None = None
    router_type: str | None = None


@runtime_checkable
class ITradeExecutor(Protocol):
    """
    Protocol for trade executors.
    
    Any class implementing this protocol can be used as an executor,
    enabling easy testing and component swapping.
    """
    
    async def execute(self, execution_plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a trade based on execution plan.
        
        Args:
            execution_plan: Plan containing trade parameters
            
        Returns:
            ExecutionResult with success status and details
        """
        ...
    
    async def execute_trade(
        self,
        token_address: str,
        amount: float,
        chain: str,
        side: str,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a trade (alternative interface).
        
        Args:
            token_address: Token contract address
            amount: Amount to trade
            chain: Blockchain network
            side: "buy" or "sell"
            **kwargs: Additional parameters
            
        Returns:
            ExecutionResult with success status and details
        """
        ...


@runtime_checkable
class IRouterManager(Protocol):
    """Protocol for router managers."""
    
    async def select_best_router(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: int
    ):
        """Select best router for a trade."""
        ...


@runtime_checkable
class IStrategyManager(Protocol):
    """Protocol for strategy managers."""
    
    async def execute_strategies_parallel(self, token_data: dict):
        """Execute all strategies in parallel."""
        ...
    
    async def evaluate_all(self, token_data: dict):
        """Evaluate all strategies and return decisions."""
        ...


class MockTradeExecutor:
    """
    Mock executor for testing.
    
    Implements ITradeExecutor protocol without actual blockchain calls.
    """
    
    def __init__(self, success_rate: float = 1.0):
        self.success_rate = success_rate
        self.execution_history = []
    
    async def execute(self, execution_plan: ExecutionPlan) -> ExecutionResult:
        """Mock execution that always succeeds or fails based on success_rate."""
        import random
        
        success = random.random() < self.success_rate
        
        result = ExecutionResult(
            success=success,
            transaction_hash=f"0x{'1234' * 16}" if success else None,
            error=None if success else "Mock execution failure",
            executed_price=execution_plan.target_price if success else None,
            executed_amount=execution_plan.amount if success else None,
            gas_used=21000 if success else None
        )
        
        self.execution_history.append({
            "plan": execution_plan,
            "result": result
        })
        
        return result
    
    async def execute_trade(
        self,
        token_address: str,
        amount: float,
        chain: str,
        side: str,
        **kwargs
    ) -> ExecutionResult:
        """Mock trade execution."""
        plan = ExecutionPlan(
            token_address=token_address,
            chain=chain,
            amount=amount,
            is_buy=(side.lower() == "buy"),
            target_price=kwargs.get("price", 1.0),
            order_type="market",
            time_in_force="GTC",
            policy_versions={},
            metadata=kwargs
        )
        return await self.execute(plan)
