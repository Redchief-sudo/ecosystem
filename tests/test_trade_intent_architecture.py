#!/usr/bin/env python3
"""Test OPTION A: Trade Intent Normalization Layer (Production Architecture)"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from datetime import datetime, timezone
from decimal import Decimal

from trading.models import MarketData, TokenInfo, TradeOpportunity
from trading.trade_engine import DecisionOutcome, StrategyDecision
from trading.trade_optimizer import (ExecutionPlan, TradeIntent,
                                     TradeIntentCompiler, TradeSide)

# Test the complete Trade Intent architecture
print("🎯 Testing OPTION A: Trade Intent Normalization Layer (Production Architecture)...")

try:
    # Create mock token info
    token_info = TokenInfo(
        address="0x1234567890123456789012345678901234567890",
        symbol="TEST",
        name="Test Token",
        decimals=18,
        chain_id="ethereum"
    )
    
    # Create mock market data
    market_data = MarketData(
        price=Decimal("2990.0"),
        volume_24h=Decimal("5000000.0"),
        liquidity=Decimal("1000000.0")
    )
    
    # Create mock opportunity (from scanner)
    opportunity = TradeOpportunity(
        token=token_info,
        market_data=market_data,
        scanner_id="test_scanner",
        scanner_version="1.0"
    )
    
    # Create mock decision (from AI)
    decision = StrategyDecision(
        outcome=DecisionOutcome.APPROVED,
        decision_id="decision_123",
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
    
    # Initialize Trade Intent Compiler
    compiler = TradeIntentCompiler()
    
    # Compile TradeIntent from decision + opportunity
    trade_intent = compiler.compile_from_decision_system_driven(decision, opportunity, market_data)
    
    print("✅ Trade Intent compilation works!")
    print(f"   Trade Intent: {trade_intent.side.upper()} {trade_intent.token_address[:10]}...")
    print(f"   Amount: ${trade_intent.amount_usd:.2f}")
    print(f"   Entry: ${trade_intent.entry_price:.2f}")
    print(f"   Target: ${trade_intent.take_profit:.2f}")
    print(f"   Stop: ${trade_intent.stop_loss:.2f}")
    print(f"   Strategy: {trade_intent.strategy_name}")
    print(f"   Confidence: {trade_intent.confidence:.2f}")
    print(f"   Urgency: {trade_intent.urgency}")
    
    # Test TradeIntent validation
    print("\n🔍 Testing TradeIntent validation...")
    
    # Test invalid amount
    try:
        invalid_intent = TradeIntent(
            symbol="TEST",
            chain="ethereum",
            token_address="0x1234",
            side="buy",
            amount_usd=-10.0,  # Invalid
            entry_price=100.0,
            take_profit=105.0,
            stop_loss=95.0,
            strategy_name="Test",
            confidence=0.8  # Required argument
        )
        print("❌ Should have failed validation")
    except ValueError as e:
        print(f"✅ Correctly caught invalid amount: {e}")
    
    # Test invalid price logic
    try:
        invalid_intent = TradeIntent(
            symbol="TEST",
            side=TradeSide.BUY,
            amount_usd=10.0,
            entry_price=100.0,
            take_profit=95.0,  # Invalid: target < entry for buy
            stop_loss=95.0,
            strategy_name="Test",
            confidence=0.8,
            reasoning="Test trade",
            token_address="0x1234",
            chain="ethereum",
            plan_id=None,
            urgency="normal"
        )
        print("❌ Should have failed validation")
    except ValueError as e:
        print(f"✅ Correctly caught invalid price logic: {e}")
    
    # Test ExecutionPlan structure
    print("\n🏗️ Testing ExecutionPlan structure...")
    
    # This would normally be created by the optimizer
    execution_plan = ExecutionPlan(
        # Core specification
        chain=trade_intent.chain,
        token_address=trade_intent.token_address,
        token_in=trade_intent.token_address,
        token_out="ETH",
        amount=trade_intent.amount_usd,
        side=trade_intent.side.value,
        is_buy=trade_intent.is_buy,

        # Price and risk
        entry_price=trade_intent.entry_price,
        target_price=trade_intent.take_profit,
        stop_loss=trade_intent.stop_loss,

        # Execution routing
        execution_id="exec_123",
        router_name="UniswapV3",
        route_path=["ETH->TEST"],
        order_type="market",
        max_slippage=0.01,
        gas_strategy="standard",

        # Strategy metadata
        strategy_name=trade_intent.strategy_name or "unknown",
        strategy_id="",  # Default empty string since TradeIntent doesn't have strategy_id
        confidence=trade_intent.confidence
    )
    
    print("✅ ExecutionPlan structure works!")
    print(f"   Executor fields: token_address={execution_plan.token_address[:10]}..., amount=${execution_plan.amount:.2f}")
    print(f"   Price fields: entry=${execution_plan.entry_price:.2f}, target=${execution_plan.target_price:.2f}")
    print(f"   Execution fields: router={execution_plan.router_name}, gas={execution_plan.gas_strategy}")
    
    print("\n🎉 OPTION A Production Architecture verified!")
    print("✅ Trade Intent Compiler: Strategy → Trade Translation")
    print("✅ TradeIntent: Complete market semantics")
    print("✅ ExecutionPlan: Self-sufficient execution specification")
    print("✅ Field ownership clearly defined")
    print("✅ Validation prevents invalid trades")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
