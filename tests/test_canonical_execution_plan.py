#!/usr/bin/env python3
"""Test the canonical ExecutionPlan schema contract"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from trading.trade_optimizer import ExecutionPlan, GasStrategy, OrderType

# Test canonical ExecutionPlan with all required fields
print("🎯 Testing canonical ExecutionPlan schema contract...")

try:
    # Create a complete canonical ExecutionPlan
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
        
        metadata={"test": "canonical"}
    )
    
    # Test all the fields that execution worker needs
    print("✅ Canonical ExecutionPlan schema works!")
    print(f"   execution_plan.amount_usd: ${execution_plan.amount_usd:,.2f}")
    print(f"   execution_plan.target_price: ${execution_plan.target_price:,.2f}")
    print(f"   execution_plan.entry_price: ${execution_plan.entry_price:,.2f}")
    print(f"   execution_plan.stop_loss: ${execution_plan.stop_loss:,.2f}")
    print(f"   execution_plan.side: {execution_plan.side}")
    print(f"   execution_plan.chain: {execution_plan.chain}")
    print(f"   execution_plan.token_in: {execution_plan.token_in[:10]}...")
    print(f"   execution_plan.token_out: {execution_plan.token_out}")
    
    # Test the logging formats that were fixed
    opt_log_message = (
        f"⚙️ [OPTIMIZED #1] TEST | "
        f"Gas: {execution_plan.gas_strategy} | "
        f"Max Slippage: {execution_plan.max_slippage:.2%} | "
        f"Amount: ${execution_plan.amount_usd:,.2f}"
    )
    
    exec_log_message = (
        f"🚀 [EXECUTING] TEST | "
        f"Strategy: TestStrategy | "
        f"Amount: ${execution_plan.amount_usd:,.2f} | "
        f"Target Price: ${execution_plan.target_price:.6f}"
    )
    
    print(f"   Optimization log: {opt_log_message}")
    print(f"   Execution log: {exec_log_message}")
    print("🎉 Canonical ExecutionPlan contract verified!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
