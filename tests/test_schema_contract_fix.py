#!/usr/bin/env python3
"""Test the ExecutionPlan schema contract fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from decimal import Decimal

from trading.trade_intent.trade_optimizer import ExecutionPlan, GasStrategy, OrderType

# Test ExecutionPlan with new required fields
print("🎯 Testing ExecutionPlan schema contract fix...")

try:
    # Create a complete ExecutionPlan with all required fields
    execution_plan = ExecutionPlan(
        execution_id="test_123",
        router_name="UniswapV3",
        route_path=["ETH->USDC"],
        order_type=OrderType.MARKET,
        max_slippage=0.01,
        gas_strategy=GasStrategy.STANDARD,
        amount=8.0,  # NEW: Direct amount field
        token_in="0x1234567890123456789012345678901234567890",  # NEW: Input token
        token_out="ETH",  # NEW: Output token
        chain="ethereum",  # NEW: Chain
        is_buy=True,  # NEW: Direction
        metadata={"test": "data"}
    )
    
    # Test all the fields that execution worker needs
    print("✅ ExecutionPlan schema contract works!")
    print(f"   execution_plan.amount: ${execution_plan.amount:,.2f}")
    print(f"   execution_plan.chain: {execution_plan.chain}")
    print(f"   execution_plan.is_buy: {execution_plan.is_buy}")
    print(f"   execution_plan.token_in: {execution_plan.token_in[:10]}...")
    print(f"   execution_plan.token_out: {execution_plan.token_out}")
    
    # Test the logging format that was fixed
    log_message = (
        f"⚙️ [OPTIMIZED #1] TEST | "
        f"Gas: {execution_plan.gas_strategy} | "
        f"Max Slippage: {execution_plan.max_slippage:.2%} | "
        f"Amount: ${execution_plan.amount:,.2f}"
    )
    
    print(f"   Log message: {log_message}")
    print("🎉 Schema contract fix verified!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
