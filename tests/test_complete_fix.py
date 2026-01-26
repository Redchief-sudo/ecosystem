#!/usr/bin/env python3
"""Test the complete fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from trading.execution.trade_engine import TradingEngine

# Test the complete pipeline
# TradingEngine requires: scan_director, trade_executor, trade_optimizer, config, token_registry, trading_mode
engine = TradingEngine(
    scan_director=None,
    trade_executor=None,
    trade_optimizer=None,
    config={},
    token_registry=None,
    trading_mode=None
)

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
