#!/usr/bin/env python3
import sys

sys.path.append('.')
import asyncio

from scanners.experimental.dexscreener_ultra_scanner import \
    DexScreenerUltraScanner


async def test_scanner():
    scanner = DexScreenerUltraScanner({
        'min_liquidity': 100,
        'min_volume': 200
    })
    
    print('🔍 Testing DexScreener Ultra Scanner...')
    results = await scanner.scan_network('ethereum')
    
    print(f'📊 Found {len(results)} tokens')
    if results:
        for i, token in enumerate(results[:3], 1):
            print(f'  {i}. {token.get("symbol", "Unknown")}:')
            print(f'     Liquidity: ${token.get("liquidity_usd", 0):,.0f}')
            print(f'     Volume: ${token.get("volume_24h", 0):,.0f}')
            print(f'     Price: ${token.get("price", 0):,.4f}')
            print(f'     Chain: {token.get("chain", "Unknown")}')
    else:
        print('❌ No tokens found')

if __name__ == "__main__":
    asyncio.run(test_scanner())
