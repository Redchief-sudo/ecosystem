#!/usr/bin/env python3
"""
Alternative Scanner Test
=======================

Test alternative approaches to get tokens flowing.
"""

import sys
import yaml
import asyncio
from pathlib import Path
from yaml import Loader

async def test_dex_screener_trending():
    """Test DexScreener trending tokens."""
    print("🧪 Testing DexScreener Trending Tokens...\n")
    
    try:
        import aiohttp
        
        # Test trending tokens directly
        print(f"🔍 Testing DexScreener trending API...")
        
        async with aiohttp.ClientSession() as session:
            try:
                # Get trending tokens
                url = "https://api.dexscreener.com/latest/dex/trending"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        print(f"📊 Found {len(pairs)} trending pairs")
                        
                        if pairs:
                            print(f"✅ SUCCESS! Found trending tokens")
                            
                            # Show first few
                            for i, pair in enumerate(pairs[:3]):
                                print(f"   📋 Pair {i+1}:")
                                print(f"      Chain: {pair.get('chainId', 'unknown')}")
                                print(f"      Symbol: {pair.get('baseToken', {}).get('symbol', 'unknown')}")
                                print(f"      Price: {pair.get('priceUsd', 'unknown')}")
                                print(f"      Volume: {pair.get('volume', {}).get('h24', 'unknown')}")
                            
                            return True
                        else:
                            print(f"❌ No trending pairs found")
                    else:
                        print(f"❌ DexScreener API returned {response.status}")
                        
            except Exception as e:
                print(f"❌ DexScreener API call failed: {e}")
        
        return False
        
    except Exception as e:
        print(f"❌ Trending test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🎯 Alternative Scanner Approaches")
    print("=" * 40)
    
    # Test trending tokens
    trending_ok = await test_dex_screener_trending()
    
    print(f"\n📊 Test Results:")
    print(f"   Trending Tokens: {'✅ WORKING' if trending_ok else '❌ BROKEN'}")
    
    if trending_ok:
        print(f"\n🎉 SCANNER SOLUTION FOUND!")
        print(f"✅ Use trending tokens API")
        print(f"💡 The trading cycle should now get tokens!")
    else:
        print(f"\n❌ SCANNER APPROACH FAILED!")
    
    return trending_ok

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
