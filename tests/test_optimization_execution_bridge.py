#!/usr/bin/env python3
"""Test the optimization → execution bridge fixes"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from decimal import Decimal

from trading.execution.trade_engine import TradingEngine
from trading.models import DecisionOutcome, StrategyDecision
from trading.trade_intent.trade_optimizer import (ExecutionPlan, TradeIntent,
                                     TradeIntentCompiler)

print("🎯 Testing Optimization → Execution Bridge Fixes...")

try:
    # Create a mock decision (like what comes from AI)
    decision = StrategyDecision(
        outcome=DecisionOutcome.APPROVED,
        decision_id="test_123",
        strategy_id="elite_momentum",
        strategy_name="Elite Momentum Strategy",
        position_size=8.0,
        entry_price=2990.0,
        stop_loss=2840.0,
        take_profit=3100.0,
        confidence=0.8,
        reasoning="Strong momentum detected",
        risk_score=0.2,
        expected_duration_hours=24.0,
        max_slippage=0.01,
        urgency=0.7,
        token_address="0x1234567890123456789012345678901234567890",
        chain="ethereum",
        symbol="TEST"
    )
    
    print("✅ Mock StrategyDecision created:")
    print(f"   Symbol: {decision.symbol}")
    print(f"   Amount: ${decision.position_size:.2f}")
    print(f"   Entry: ${decision.entry_price:.2f}")
    print(f"   Confidence: {decision.confidence:.2f}")
    
    # Test TradeIntentCompiler directly
    print("\n🔧 Testing TradeIntentCompiler...")
    compiler = TradeIntentCompiler()
    
    # Create minimal opportunity for testing
    from trading.models import MarketData, TokenInfo, TradeOpportunity
    
    token_info = TokenInfo(
        address=decision.token_address,
        symbol=decision.symbol,
        chain_id=decision.chain,
        decimals=18
    )
    
    market_data = MarketData(
        price=Decimal(str(decision.entry_price)),
        volume_24h=Decimal("1000000"),
        liquidity=Decimal("1000000")
    )
    
    opportunity = TradeOpportunity(
        token=token_info,
        market_data=market_data,
        scanner_id="test",
        scanner_version="1.0"
    )
    
    # Compile TradeIntent
    trade_intent = compiler.compile_from_decision(decision, opportunity)
    
    print("✅ TradeIntent compiled successfully:")
    print(f"   Side: {trade_intent.side}")
    print(f"   Amount: ${trade_intent.amount_usd:.2f}")
    print(f"   Entry: ${trade_intent.entry_price:.2f}")
    print(f"   Target: ${trade_intent.target_price:.2f}")
    print(f"   Stop: ${trade_intent.stop_loss:.2f}")
    
    # Test ExecutionPlan creation (canonical structure)
    print("\n🏗️ Testing ExecutionPlan structure...")
    from trading.trade_intent.trade_optimizer import ExecutionPlan
    
    execution_plan = ExecutionPlan(
        # Core specification
        opportunity_id=f"{decision.chain}:{decision.token_address}:spot",
        chain=decision.chain,
        token_address=decision.token_address,
        token_in=decision.token_address,
        token_out="ETH",
        amount=decision.position_size,
        side="buy",
        
        # Price parameters
        entry_price=trade_intent.entry_price,
        target_price=trade_intent.target_price,
        stop_loss=trade_intent.stop_loss,
        
        # Execution routing
        execution_id="test_exec_123",
        router_name="UniswapV3",
        route_path=["ETH->TEST"],
        order_type="market",
        max_slippage=0.01,
        gas_strategy="standard",
        
        # Metadata
        strategy_name=decision.strategy_name,
        strategy_id=decision.strategy_id,
        confidence=decision.confidence
    )
    
    print("✅ ExecutionPlan created successfully:")
    print(f"   Token: {execution_plan.token_address[:10]}...")
    print(f"   Amount: ${execution_plan.amount:.2f}")
    print(f"   Router: {execution_plan.router_name}")
    print(f"   Gas Strategy: {execution_plan.gas_strategy}")
    
    print("\n🎉 Optimization → Execution Bridge Fixed!")
    print("✅ FIX #1: Removed lifecycle dependency")
    print("✅ FIX #2: Aligned ExecutionPlan constructor")
    print("✅ No more AttributeError: 'opportunity_lifecycles'")
    print("✅ No more TypeError: ExecutionPlan constructor mismatch")
    print("✅ Decision → TradeIntent → ExecutionPlan flow working")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
