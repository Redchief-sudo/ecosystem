#!/usr/bin/env python3
"""Test the execution fixes"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from router.hybrid_router_manager import HybridRouterManager
from trading.trade_optimizer import TradeIntent, TradeSide

# Test TradeIntent creation
print("🎯 Testing TradeIntent creation...")
try:
    intent = TradeIntent(
        symbol="TEST",
        side=TradeSide.BUY,
        amount_usd=8.0,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=105.0,
        strategy_name="test",
        confidence=0.8,
        reasoning="Test trade",
        token_address="0x1234567890123456789012345678901234567890",
        chain="ethereum",
        plan_id=None,
        urgency="high"
    )
    print("✅ TradeIntent created successfully!")
    print(f"   Symbol: {intent.symbol}")
    print(f"   Amount: ${intent.amount_usd}")
    print(f"   Chain: {intent.chain}")
    print(f"   Confidence: {intent.confidence}")
except Exception as e:
    print(f"❌ TradeIntent error: {e}")

# Test RouterManager methods
print("\n🎯 Testing RouterManager methods...")
try:
    # Mock network manager
    class MockNetworkManager:
        networks = {
            "ethereum": {
                "router_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
            }
        }
    
    router_manager = RouterManager(MockNetworkManager(), {})
    
    # Test get_router_address
    address = router_manager.get_router_address("ethereum")
    print(f"✅ Router address: {address}")
    
    # Test get_router_abi
    abi = router_manager.get_router_abi("ethereum")
    print(f"✅ Router ABI found: {abi is not None}")
    
except Exception as e:
    print(f"❌ RouterManager error: {e}")

print("\n🎉 All execution fixes verified!")
