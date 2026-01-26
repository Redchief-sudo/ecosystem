#!/usr/bin/env python3
"""Test the lowered confidence thresholds"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from datetime import datetime
from decimal import Decimal

from ai.elite_ai_controller import EliteAsyncAIController, TradeOpportunity
from trading.trade_engine import TradingEngine


# Create a mock AI controller with higher confidence
class MockAIController:
    def __init__(self):
        self.strategies = {'test': {}}
        self.current_regime = 'SIDEWAYS'
        self.active_positions = {}
    
    async def get_portfolio_value(self):
        return 100000
    
    async def select_strategy(self, opportunity):
        """Mock implementation of select_strategy with higher confidence"""
        class MockRecommendation:
            def __init__(self):
                self.opportunity_id = opportunity.opportunity_id
                self.recommended_strategy_id = 'momentum'
                self.recommended_strategy_name = 'Momentum Strategy'
                self.confidence = 0.45  # This should now be > 0.3 threshold
                self.expected_profit = Decimal('100.0')
                self.expected_risk = 0.1
                self.position_size = Decimal('1000.0')
                self.selection_method = 'ENSEMBLE'
                self.market_regime = 'SIDEWAYS'
                self.ensemble_strategies = [('momentum', 0.8), ('arbitrage', 0.2)]
                self.key_factors = ['price_momentum', 'volume_increase']
        
        return MockRecommendation()

# Test the complete pipeline
mock_ai = MockAIController()
engine = TradingEngine(None, mock_ai, None, None, {})

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
    expires_at=datetime.utcnow(),
    urgency=0.8,
)

# Test AI decision with new thresholds
import asyncio


async def test_decision():
    decision = await engine._request_elite_decision(opportunity)
    
    print(f"🎯 CONFIDENCE: {decision.confidence}")
    print(f"🎯 THRESHOLD: 0.3 (lowered from 0.5)")
    print(f"🎯 OUTCOME: {decision.outcome.value}")
    print(f"🎯 STRATEGY: {decision.strategy_name}")
    print(f"🎯 POSITION SIZE: ${decision.position_size}")
    
    if decision.outcome.value == 'approved':
        print('✅ SUCCESS! Trade should execute now!')
    else:
        print('❌ Still rejected - confidence too low')

# Run the test
asyncio.run(test_decision())
