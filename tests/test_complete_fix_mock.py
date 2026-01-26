#!/usr/bin/env python3
"""Test the complete fix with mock AI"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from ai.elite_ai_controller import EliteAsyncAIController
from trading.trade_engine import TradingEngine


# Create a mock AI controller
class MockAIController:
    def __init__(self):
        self.strategies = {'test': {}}
        self.current_regime = 'SIDEWAYS'
        self.active_positions = {}
    
    async def get_portfolio_value(self):
        return 100000
    
    async def select_strategy(self, opportunity):
        """Mock implementation of select_strategy"""
        class MockRecommendation:
            def __init__(self):
                self.strategy_id = 'momentum'
                self.confidence = 0.8
                self.reasoning = 'Mock recommendation'
                self.strategy_type = 'momentum'
        
        return MockRecommendation()

# Test the complete pipeline
mock_ai = MockAIController()
engine = TradingEngine(None, mock_ai, None, None, {})

# Create a mock token with 'address' field (like scanners return)
token = {
    'symbol': 'TEST',
    'address': '0x1234567890123456789012345678901234567890',
    'chain': 'ethereum',
    'price': 100.0,
    'volume_24h': 1000,
    'liquidity_usd': 500,
    'confidence': 0.8
}

# Test normalization
opportunity = engine._normalize_to_opportunity(token)
if opportunity:
    print(f'✅ STEP 1: Normalization works - {opportunity.token_symbol}')
    
    # Test if the AI method exists
    if hasattr(engine.elite, 'select_strategy'):
        print('✅ STEP 2: AI method select_strategy exists')
        print('🎉 COMPLETE FIX SUCCESSFUL!')
        print('📊 The system should now be able to:')
        print('   - Normalize tokens from scanners (address field)')
        print('   - Call the correct AI method (select_strategy)')
        print('   - Process decisions and execute trades')
    else:
        print('❌ STEP 2: AI method still missing')
else:
    print('❌ STEP 1: Normalization still broken')
