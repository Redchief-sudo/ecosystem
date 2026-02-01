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
    results = await scanner.scan()
    
    print(f'📊 Found {len(results)} tokens')
    if results:
        for i, token in enumerate(results[:3], 1):
            print(f'  {i}. {token.symbol if hasattr(token, "symbol") else token.get("symbol", "Unknown")}:')
            print(f'     Liquidity: ${token.liquidity_usd if hasattr(token, "liquidity_usd") else token.get("liquidity_usd", 0):,.0f}')
            print(f'     Volume: ${token.volume_24h if hasattr(token, "volume_24h") else token.get("volume_24h", 0):,.0f}')
            print(f'     Price: ${token.price if hasattr(token, "price") else token.get("price", 0):,.4f}')
            print(f'     Chain: {token.chain if hasattr(token, "chain") else token.get("chain", "Unknown")}')
    else:
        print('❌ No tokens found')

if __name__ == "__main__":
    asyncio.run(test_scanner())
