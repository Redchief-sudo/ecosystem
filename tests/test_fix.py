#!/usr/bin/env python3
"""Test the field mapping fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from trading.execution.trade_engine import TradingEngine

# Test the field mapping fix
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
    print(f'✅ SUCCESS: Normalized {opportunity.token_symbol} with address {opportunity.token_address[:10]}...')
    print(f'   Chain: {opportunity.chain}, Price: ${opportunity.current_price}')
else:
    print('❌ FAILED: Could not normalize token')
