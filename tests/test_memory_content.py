#!/usr/bin/env python3
import sys

sys.path.append('.')
import asyncio

from scanners.experimental.dexscreener_ultra_scanner import \
    DexScreenerUltraScanner
from utils.memory import MemoryManager


async def test_memory_content():
    print('🔍 Examining Memory Content...\n')
    
    # Create memory manager
    memory = MemoryManager()
    
    # Run DexScreener Ultra
    ds_scanner = DexScreenerUltraScanner({
        'min_liquidity': 100,
        'min_volume': 200
    }, memory=memory)
    
    await ds_scanner.scan_network('ethereum')
    
    # Examine memory content
    tokens = memory.get_recent_tokens(hours=1) or []
    print(f'📊 Memory contains {len(tokens)} tokens\n')
    
    if tokens:
        token = tokens[0]
        print('🔍 First token analysis:')
        print(f'   Type: {type(token)}')
        print(f'   Attributes: {dir(token)[:10]}')  # First 10 attributes
        
        # Check if it has required attributes
        required_attrs = ["liquidity_usd", "volume_24h", "price", "symbol"]
        print(f'\n   Required attributes check:')
        for attr in required_attrs:
            has_attr = hasattr(token, attr)
            value = getattr(token, attr, 'N/A') if has_attr else 'N/A'
            print(f'     {attr}: {"✅" if has_attr else "❌"} = {value}')
        
        # If it's a dict, check its keys
        if isinstance(token, dict):
            print(f'\n   Dictionary keys: {list(token.keys())[:10]}')

if __name__ == "__main__":
    asyncio.run(test_memory_content())
