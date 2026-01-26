#!/usr/bin/env python3
"""
Scanner Test - Check if scanners are finding tokens
===============================================

Test if the scanner director is actually finding tokens and putting them in the queue.
"""

import sys
import yaml
import asyncio
from pathlib import Path
from yaml import Loader

async def test_scanner_director():
    """Test the scanner director directly."""
    print("🧪 Testing Scanner Director...\n")
    
    try:
        from scanners.scan_director import ScanDirector
        
        # Load configuration
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.load(f, Loader=Loader)
        
        scanner_config = config.get('scanners', {})
        
        print(f"📋 Scanner Configuration:")
        for name, cfg in scanner_config.items():
            if name == 'settings':
                continue
            status = "✅ ENABLED" if cfg.get('enabled', False) else "❌ DISABLED"
            print(f"   {status} {name}")
        
        # Initialize scan director
        scan_director = ScanDirector(config=scanner_config)
        print(f"\n✅ ScanDirector initialized")
        
        # Test scanning
        print(f"\n🔍 Running scan...")
        scan_results = await scan_director.scan_all()
        
        print(f"📊 Scan Results:")
        print(f"   Total results: {len(scan_results)}")
        
        if scan_results:
            print(f"   ✅ Found {len(scan_results)} tokens!")
            
            # Show first few results
            for i, result in enumerate(scan_results[:3]):
                print(f"   📋 Result {i+1}:")
                if hasattr(result, 'symbol'):
                    print(f"      Symbol: {result.symbol}")
                if hasattr(result, 'address'):
                    print(f"      Address: {result.address}")
                if hasattr(result, 'price'):
                    print(f"      Price: {result.price}")
                if hasattr(result, 'volume_24h'):
                    print(f"      Volume: {result.volume_24h}")
        else:
            print(f"   ❌ No tokens found!")
            print(f"   💡 This is likely why the trading cycle is stuck")
        
        return len(scan_results) > 0
        
    except Exception as e:
        print(f"❌ Scanner test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_individual_scanners():
    """Test individual scanners."""
    print(f"\n🧪 Testing Individual Scanners...\n")
    
    try:
        # Test DexScreener
        print(f"📊 Testing DexScreener Scanner...")
        from scanners.discovery.dex_screener_scanner import DexScreenerScanner
        
        dex_config = {
            'enabled': True,
            'min_liquidity': 10000.0,
            'min_volume_24h': 50000.0,
            'min_market_cap': 100000.0,
            'supported_chains': ['ethereum', 'bsc', 'polygon']
        }
        
        dex_scanner = DexScreenerScanner(config=dex_config)
        print(f"   ✅ DexScreener initialized")
        
        # Test a simple scan
        try:
            results = await dex_scanner.scan()
            print(f"   📊 DexScreener results: {len(results)}")
            if results:
                print(f"   ✅ DexScreener found tokens!")
            else:
                print(f"   ❌ DexScreener found no tokens")
        except Exception as e:
            print(f"   ❌ DexScreener scan failed: {e}")
        
        # Test Mempool Scanner
        print(f"\n📊 Testing Mempool Scanner...")
        from scanners.discovery.mempool_scanner import MempoolScanner
        
        mempool_config = {
            'enabled': True,
            'min_liquidity': 5000.0,
            'min_volume_24h': 25000.0,
            'supported_chains': ['ethereum', 'bsc', 'polygon']
        }
        
        mempool_scanner = MempoolScanner(config=mempool_config)
        print(f"   ✅ Mempool initialized")
        
        try:
            results = await mempool_scanner.scan()
            print(f"   📊 Mempool results: {len(results)}")
            if results:
                print(f"   ✅ Mempool found tokens!")
            else:
                print(f"   ❌ Mempool found no tokens")
        except Exception as e:
            print(f"   ❌ Mempool scan failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Individual scanner test failed: {e}")
        return False

async def test_network_connectivity():
    """Test network connectivity."""
    print(f"\n🧪 Testing Network Connectivity...\n")
    
    try:
        import aiohttp
        import asyncio
        
        # Test DexScreener API
        print(f"🌐 Testing DexScreener API...")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://api.dexscreener.com/latest/dex/tokens/0x7213a321f1855cf7791cf986ecde6a765e794f1f", timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        print(f"   ✅ DexScreener API reachable")
                    else:
                        print(f"   ❌ DexScreener API returned {response.status}")
            except Exception as e:
                print(f"   ❌ DexScreener API failed: {e}")
        
        # Test basic internet connectivity
        print(f"🌐 Testing Internet Connectivity...")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://httpbin.org/get", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        print(f"   ✅ Internet connectivity working")
                    else:
                        print(f"   ❌ Internet connectivity issue: {response.status}")
            except Exception as e:
                print(f"   ❌ Internet connectivity failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Network connectivity test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🎯 Scanner and Trading Cycle Debugging")
    print("=" * 50)
    
    # Test 1: Network connectivity
    network_ok = await test_network_connectivity()
    
    # Test 2: Individual scanners
    individual_ok = await test_individual_scanners()
    
    # Test 3: Scanner director
    director_ok = await test_scanner_director()
    
    print(f"\n📊 Test Results:")
    print(f"   Network Connectivity: {'✅ WORKING' if network_ok else '❌ BROKEN'}")
    print(f"   Individual Scanners: {'✅ WORKING' if individual_ok else '❌ BROKEN'}")
    print(f"   Scanner Director: {'✅ WORKING' if director_ok else '❌ BROKEN'}")
    
    overall_ok = network_ok and individual_ok and director_ok
    
    if overall_ok:
        print(f"\n🎉 SCANNERS ARE WORKING!")
        print(f"✅ Network connectivity is good")
        print(f"✅ Individual scanners are functional")
        print(f"✅ Scanner director is finding tokens")
        print(f"\n💡 If still stuck, check:")
        print(f"   - Token pipeline processing")
        print(f"   - Queue management")
        print(f"   - Strategy evaluation")
        print(f"   - System logs for specific errors")
    else:
        print(f"\n❌ SCANNER ISSUES FOUND!")
        
        if not network_ok:
            print(f"\n🔍 NETWORK ISSUES:")
            print(f"   - Check internet connection")
            print(f"   - Check firewall settings")
            print(f"   - Check DNS resolution")
        
        if not individual_ok:
            print(f"\n🔍 SCANNER ISSUES:")
            print(f"   - Check scanner configurations")
            print(f"   - Check API endpoints")
            print(f"   - Check rate limits")
        
        if not director_ok:
            print(f"\n🔍 DIRECTOR ISSUES:")
            print(f"   - Check scanner director configuration")
            print(f"   - Check scanner initialization")
            print(f"   - Check scanner permissions")
    
    return overall_ok

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
