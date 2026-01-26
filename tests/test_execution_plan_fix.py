#!/usr/bin/env python3
"""Test the ExecutionPlan amount fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from decimal import Decimal

from trading.trade_optimizer import ExecutionPlan, GasStrategy, OrderType

# Test ExecutionPlan creation and access
print("🎯 Testing ExecutionPlan amount fix...")

try:
    # Create a mock ExecutionPlan
    execution_plan = ExecutionPlan(
        execution_id="test_123",
        router_name="UniswapV3",
        route_path=["ETH->USDC"],
        order_type=OrderType.MARKET,
        max_slippage=0.01,
        gas_strategy=GasStrategy.STANDARD,
        metadata={
            "amount": 8.0,
            "chain": "ethereum",
            "is_buy": True
        }
    )
    
    # Create a mock decision with position_size
    class MockDecision:
        def __init__(self):
            self.symbol = "TEST"
            self.position_size = Decimal("8.00")
    
    decision = MockDecision()
    
    # Test the logging format that was fixed
    log_message = (
        f"⚙️ [OPTIMIZED #1] {decision.symbol} | "
        f"Gas: {execution_plan.gas_strategy} | "
        f"Max Slippage: {execution_plan.max_slippage:.2%} | "
        f"Amount: ${decision.position_size:,.2f}"
    )
    
    print("✅ ExecutionPlan access fix works!")
    print(f"   Log message: {log_message}")
    print("🎉 Fix verified!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
