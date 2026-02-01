#!/usr/bin/env python3
import sys

sys.path.append('.')
import asyncio

from scanners.experimental.dexscreener_ultra_scanner import \
    DexScreenerUltraScanner


async def test_scanners():
    print('🔍 Testing Multiple Scanners...\n')
    
    # Test DexScreener Ultra
    print('1️⃣ DexScreener Ultra Scanner:')
    try:
        ds_scanner = DexScreenerUltraScanner({
            'min_liquidity': 100,
            'min_volume': 200
        })
        results = await ds_scanner.scan_network('ethereum')
        print(f'   ✅ Found {len(results)} tokens')
        if results:
            token = results[0]
            print(f'   📊 Sample: {token.get("symbol")} - Liquidity: ${token.get("liquidity_usd", 0):,.0f}')
    except Exception as e:
        print(f'   ❌ Error: {e}')
    
    print()
    
    # Test AI Discovery
    print('2️⃣ AI Discovery Scanner:')
    try:
        ai_scanner = AIDiscoveryScanner({
            'min_liquidity': 100,
            'min_volume': 100
        })
        results = await ai_scanner.scan_network('ethereum')
        print(f'   ✅ Found {len(results)} tokens')
        if results:
            token = results[0]
            print(f'   📊 Sample: {token.get("symbol")} - Liquidity: ${token.get("liquidity_usd", 0):,.0f}')
    except Exception as e:
        print(f'   ❌ Error: {e}')
    
    print()
    
    # Test D3 Scanner
    print('3️⃣ D3 Scanner:')
    try:
        d3_scanner = D3Scanner({
            'min_delta_volume': 100,
            'min_delta_liq': 50
        })
        results = await d3_scanner.scan_network('ethereum')
        print(f'   ✅ Found {len(results)} tokens')
        if results:
            token = results[0]
            print(f'   📊 Sample: {token.get("symbol")} - Volume: ${token.get("volume_24h", 0):,.0f}')
    except Exception as e:
        print(f'   ❌ Error: {e}')

if __name__ == "__main__":
    asyncio.run(test_scanners())
