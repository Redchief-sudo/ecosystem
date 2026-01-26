#!/usr/bin/env python3
"""Test the AI controller method fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from decimal import Decimal

from ai.elite_ai_controller import EliteAsyncAIController, TradeOpportunity

# Test the correct method name
controller = EliteAsyncAIController()

# Create a test opportunity
opportunity = TradeOpportunity(
    opportunity_id="test:0x123:spot",
    token_symbol="TEST",
    token_address="0x1234567890123456789012345678901234567890",
    chain_id="ethereum",
    opportunity_type="spot",
    current_price=Decimal("100.0"),
    target_price=Decimal("105.0"),
    stop_loss=Decimal("95.0"),
    potential_profit=Decimal("5.0"),
    potential_loss=Decimal("5.0"),
    risk_reward_ratio=1.0,
    confidence=0.8,
    volatility=0.05,
    volume_24h=Decimal("1000"),
    liquidity=Decimal("500"),
    market_regime="SIDEWAYS",
    required_capital=Decimal("100"),
    estimated_execution_time_ms=200,
    max_slippage=0.01,
    expires_at=None,
    urgency=0.8,
)

# Test if the method exists
if hasattr(controller, 'select_strategy'):
    print("✅ Method 'select_strategy' exists - fix should work!")
elif hasattr(controller, 'recommend_strategy'):
    print("❌ Method 'recommend_strategy' exists - this is the old method")
else:
    print("❌ Neither method found - checking available methods:")
    methods = [m for m in dir(controller) if not m.startswith('_') and callable(getattr(controller, m))]
    strategy_methods = [m for m in methods if 'strategy' in m.lower()]
    print(f"Available strategy methods: {strategy_methods}")
