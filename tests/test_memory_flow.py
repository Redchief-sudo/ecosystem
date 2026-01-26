#!/usr/bin/env python3
import sys

sys.path.append('.')
import asyncio

from scanners.experimental.ai_discovery_scanner import AIDiscoveryScanner
from scanners.experimental.dexscreener_ultra_scanner import \
    DexScreenerUltraScanner
from utils.memory import MemoryManager


async def test_memory_flow():
    print('🔍 Testing Memory Flow Between Scanners...\n')
    
    # Create memory manager
    memory = MemoryManager()
    print('✅ Memory Manager created')
    
    # Test DexScreener Ultra with memory
    print('\n1️⃣ DexScreener Ultra Scanner (with memory):')
    try:
        ds_scanner = DexScreenerUltraScanner({
            'min_liquidity': 100,
            'min_volume': 200
        }, memory=memory)
        
        results = await ds_scanner.scan_network('ethereum')
        print(f'   ✅ Found {len(results)} tokens')
        
        # Check memory
        memory_tokens = memory.get_recent_tokens(hours=1) or []
        print(f'   📊 Memory now has {len(memory_tokens)} tokens')
        
        if memory_tokens:
            token = memory_tokens[0]
            print(f'   📈 Sample in memory: {token.symbol} - Liquidity: ${token.liquidity_usd or 0:,.0f}')
        
    except Exception as e:
        print(f'   ❌ Error: {e}')
    
    print()
    
    # Test AI Discovery with populated memory
    print('2️⃣ AI Discovery Scanner (with populated memory):')
    try:
        ai_scanner = AIDiscoveryScanner({
            'min_liquidity': 100,
            'min_volume': 100
        }, memory=memory)
        
        results = await ai_scanner.scan_network('ethereum')
        print(f'   ✅ Found {len(results)} tokens')
        
        if results:
            token = results[0]
            print(f'   🤖 AI Score: {token.get("ai_score", 0):.3f}')
            print(f'   📊 Sample: {token.get("symbol")} - Liquidity: ${token.get("liquidity_usd", 0):,.0f}')
        
    except Exception as e:
        print(f'   ❌ Error: {e}')

if __name__ == "__main__":
    asyncio.run(test_memory_flow())
