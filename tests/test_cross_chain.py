#!/usr/bin/env python3
import sys

sys.path.append('.')
import asyncio

from scanners.experimental.dexscreener_ultra_scanner import \
    DexScreenerUltraScanner


async def test_cross_chain():
    print('🔍 Testing Cross-Chain Token Discovery...\n')
    
    scanner = DexScreenerUltraScanner({
        'min_liquidity': 100,
        'min_volume': 200
    })
    
    # Test chains that were previously unsupported
    test_chains = ['fuse', 'dogechain', 'kava', 'canto', 'blast', 'mode']
    
    for chain in test_chains:
        print(f'📍 Testing {chain}:')
        try:
            results = await scanner.scan_network(chain)
            if results:
                print(f'   ✅ Found {len(results)} tokens')
                token = results[0]
                print(f'   📈 Sample: {token.get("symbol")} - Liquidity: ${token.get("liquidity_usd", 0):,.0f}')
                print(f'      Actual chain from API: {token.get("chain")}')
            else:
                print(f'   ❌ No tokens found')
        except Exception as e:
            print(f'   ❌ Error: {e}')
        print()

if __name__ == "__main__":
    asyncio.run(test_cross_chain())
