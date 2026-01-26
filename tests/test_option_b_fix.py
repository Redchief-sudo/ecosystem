#!/usr/bin/env python3
"""Test OPTION B: Temporary executor compatibility fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from trading.trade_optimizer import ExecutionPlan, GasStrategy, OrderType

# Test ExecutionPlan with executor compatibility fields
print("🎯 Testing OPTION B: Temporary executor compatibility fix...")

try:
    # Create an ExecutionPlan with both canonical and executor fields
    execution_plan = ExecutionPlan(
        # Core trade specification
        opportunity_id="ethereum:0x1234:spot",
        chain="ethereum",
        token_in="0x1234567890123456789012345678901234567890",
        token_out="ETH",
        amount_usd=8.0,
        side="buy",
        
        # Price and risk parameters
        entry_price=2990.0,
        target_price=3100.0,
        stop_loss=2840.0,
        
        # Execution routing
        execution_id="exec_123",
        router_name="UniswapV3",
        route_path=["ETH->USDC"],
        order_type=OrderType.MARKET,
        max_slippage=0.01,
        gas_strategy=GasStrategy.STANDARD,
        
        # TEMPORARY: Executor compatibility fields (OPTION B - test-only)
        token_address="0x1234567890123456789012345678901234567890",
        amount=8.0,
        is_buy=True,
        
        metadata={"test": "option_b"}
    )
    
    # Test all the fields that executor needs
    print("✅ Executor compatibility works!")
    print(f"   execution_plan.token_address: {execution_plan.token_address[:10]}...")
    print(f"   execution_plan.amount: ${execution_plan.amount:,.2f}")
    print(f"   execution_plan.is_buy: {execution_plan.is_buy}")
    print(f"   execution_plan.target_price: ${execution_plan.target_price:,.2f}")
    
    # Test executor call simulation
    executor_params = {
        "token_address": execution_plan.token_address,
        "amount": execution_plan.amount,
        "network": execution_plan.chain,
        "is_buy": execution_plan.is_buy,
        "price": execution_plan.target_price,
        "max_slippage": execution_plan.max_slippage,
    }
    
    print(f"   Executor params: {executor_params}")
    print("🎉 OPTION B temporary fix verified!")
    print("⚠️  WARNING: This is for testing only - implement Trade Intent layer for production!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
