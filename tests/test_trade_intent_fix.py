#!/usr/bin/env python3
"""Test the TradeIntent fix"""

from decimal import Decimal

from trading.models import MarketData, TokenInfo, TradeOpportunity, DecisionOutcome, StrategyDecision
from trading.trade_intent.trade_optimizer import TradeIntent, TradeIntentCompiler, TradeSide

print("🎯 Testing TradeIntent fix...")

try:
    # Test the fix
    compiler = TradeIntentCompiler()
    decision = StrategyDecision(
        outcome=DecisionOutcome.APPROVED,
        decision_id='test_123',
        strategy_id='momentum_strategy',
        strategy_name='Test Strategy',
        position_size=10.0,
        entry_price=0.0,
        stop_loss=0.0,
        take_profit=0.0,
        confidence=0.8,
        token_address='0x123456789012345678901234567890',
        chain='ethereum',
        symbol='TEST',
        side='buy'
    )

    market_data = MarketData(
        price=Decimal('2990.50'),
        volume_24h=Decimal('1200000000'),
        liquidity=Decimal('500000000')
    )

    token_info = TokenInfo(
        address=decision.token_address,
        symbol=decision.symbol,
        chain_id=decision.chain,
        decimals=18
    )

    opportunity = TradeOpportunity(
        token=token_info,
        market_data=market_data,
        scanner_id='test',
        scanner_version='1.0'
    )

    trade_intent = compiler.compile_from_decision_system_driven(
        decision, opportunity, market_data
    )

    print('✅ TradeIntent created successfully')
    print(f'Side: {trade_intent.side}')
    print(f'Amount: ${trade_intent.amount_usd:.2f}')
    print(f'Entry: ${trade_intent.entry_price:.2f}')
    print(f'Target: ${trade_intent.take_profit:.2f}')
    print(f'Stop: ${trade_intent.stop_loss:.2f}')
    print(f'is_buy: {trade_intent.is_buy}')
    
    print("\n🎉 TradeIntent fix verified!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
