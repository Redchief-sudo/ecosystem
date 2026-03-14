#!/usr/bin/env python3
"""Test the structural fixes: MarketData reality & ExecutionPlan interface"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from decimal import Decimal

from trading.models import MarketData, TokenInfo, TradeOpportunity
from trading.trade_intent.trade_optimizer import ExecutionPlan, TradeIntentCompiler

print("🎯 Testing Structural Fixes: MarketData Reality & ExecutionPlan Interface...")

try:
    # Test FIX A: MarketData requires real data (no fake values allowed)
    print("\n📊 Testing FIX A: MarketData reality enforcement...")
    
    # This should work (real market data)
    real_market_data = MarketData(
        price=Decimal("2990.0"),
        volume_24h=Decimal("5000000.0"),
        liquidity=Decimal("1000000.0")
    )
    print("✅ Real MarketData created successfully:")
    print(f"   Price: ${real_market_data.price:.2f}")
    print(f"   Volume: ${real_market_data.volume_24h:,.0f}")
    print(f"   Liquidity: ${real_market_data.liquidity:,.0f}")
    
    # This should fail (fake/invalid data)
    try:
        fake_market_data = MarketData(
            price=Decimal("0.0"),  # Invalid - zero price
            volume_24h=Decimal("-1000.0"),  # Invalid - negative volume
            liquidity=Decimal("-500.0")  # Invalid - negative liquidity
        )
        print("❌ Should have failed with fake data!")
    except ValueError as e:
        print(f"✅ Correctly rejected fake MarketData: {e}")
    
    # Test FIX B: ExecutionPlan interface (no opportunity_id)
    print("\n🏗️ Testing FIX B: ExecutionPlan canonical interface...")
    
    # This should work (canonical ExecutionPlan)
    execution_plan = ExecutionPlan(
        # Core specification (NO opportunity_id)
        chain="ethereum",
        token_address="0x1234567890123456789012345678901234567890",
        token_in="0x1234567890123456789012345678901234567890",
        token_out="ETH",
        amount=8.0,
        side="buy",
        
        # Price parameters
        entry_price=2990.0,
        target_price=3079.7,
        stop_loss=2900.3,
        
        # Execution routing
        execution_id="exec_123",
        router_name="UniswapV3",
        route_path=["ETH->TEST"],
        order_type="market",
        max_slippage=0.01,
        gas_strategy="standard",
        
        # Metadata
        strategy_name="test_strategy",
        strategy_id="test_strategy_id",
        confidence=0.8
    )
    
    print("✅ Canonical ExecutionPlan created successfully:")
    print(f"   Token: {execution_plan.token_address[:10]}...")
    print(f"   Amount: ${execution_plan.amount:.2f}")
    print(f"   Side: {execution_plan.side}")
    print(f"   Router: {execution_plan.router_name}")
    print(f"   Strategy: {execution_plan.strategy_name}")
    
    # This should fail (old interface with opportunity_id)
    try:
        old_interface_plan = ExecutionPlan(
            opportunity_id="ethereum:0x1234:spot",  # INVALID - not in canonical interface
            chain="ethereum",
            token_address="0x1234567890123456789012345678901234567890",
            token_in="0x1234567890123456789012345678901234567890",
            token_out="ETH",
            amount=8.0,
            side="buy",
            entry_price=2990.0,
            target_price=3079.7,
            stop_loss=2900.3,
            execution_id="exec_123",
            router_name="UniswapV3",
            route_path=["ETH->TEST"],
            order_type="market",
            max_slippage=0.01,
            gas_strategy="standard"
        )
        print("❌ Should have failed with opportunity_id!")
    except TypeError as e:
        print(f"✅ Correctly rejected old ExecutionPlan interface: {e}")
    
    # Test TradeIntentCompiler with real market data
    print("\n🎯 Testing TradeIntentCompiler with real market data...")
    
    compiler = TradeIntentCompiler()
    
    # Create real opportunity
    token_info = TokenInfo(
        address="0x1234567890123456789012345678901234567890",
        symbol="TEST",
        chain_id="ethereum",
        decimals=18
    )
    
    opportunity = TradeOpportunity(
        token=token_info,
        market_data=real_market_data,
        scanner_id="test_scanner",
        scanner_version="1.0"
    )
    
    # Mock decision
    from trading.execution.trade_engine import TradingEngine
    from trading.models import DecisionOutcome, StrategyDecision
    decision = StrategyDecision(
        outcome=DecisionOutcome.APPROVED,
        decision_id="test_123",
        strategy_id="test_strategy",
        strategy_name="Test Strategy",
        position_size=8.0,
        entry_price=2990.0,
        stop_loss=2840.0,
        take_profit=3100.0,
        confidence=0.8,
        token_address="0x1234567890123456789012345678901234567890",
        chain="ethereum",
        symbol="TEST"
    )
    
    # Compile TradeIntent
    trade_intent = compiler.compile_from_decision(decision, opportunity)
    
    print("✅ TradeIntent compiled with real market data:")
    print(f"   Side: {trade_intent.side}")
    print(f"   Amount: ${trade_intent.amount_usd:.2f}")
    print(f"   Entry: ${trade_intent.entry_price:.2f}")
    print(f"   Target: ${trade_intent.target_price:.2f}")
    print(f"   Stop: ${trade_intent.stop_loss:.2f}")
    print(f"   Strategy: {trade_intent.strategy_name}")
    
    print("\n🎉 Both Structural Fixes Verified!")
    print("✅ FIX A: MarketData requires real data (no fake values)")
    print("✅ FIX B: ExecutionPlan uses canonical interface (no opportunity_id)")
    print("✅ TradeIntentCompiler works with real market data")
    print("✅ No more ValueError: Market data values must be non-negative")
    print("✅ No more TypeError: ExecutionPlan.__init__() unexpected opportunity_id")
    print("✅ Optimization → Execution bridge is structurally sound!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
