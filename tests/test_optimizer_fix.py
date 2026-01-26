#!/usr/bin/env python3
"""Test the optimizer fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from trading.trade_optimizer import TradeOptimizer

# Test the create_execution_plan method
print("🎯 Testing create_execution_plan fix...")

try:
    optimizer = TradeOptimizer({})
    
    # Test the method with available parameters
    import asyncio
    
    async def test_optimizer():
        plan = await optimizer.create_execution_plan(
            token_address="0x1234567890123456789012345678901234567890",
            chain="ethereum",
            amount=8.0,
            is_buy=True,
            target_price=105.0,
            max_slippage=0.01,
            urgency=0.8
        )
        
        print("✅ create_execution_plan works!")
        print(f"   Plan created: {plan is not None}")
        return plan
    
    plan = asyncio.run(test_optimizer())
    print("🎉 Optimizer fix verified!")
    
except Exception as e:
    print(f"❌ Optimizer error: {e}")
    import traceback
    traceback.print_exc()
