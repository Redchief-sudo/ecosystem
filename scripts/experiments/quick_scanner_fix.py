#!/usr/bin/env python3
"""
Quick Scanner Fix Test
===================

Quick test to fix scanner initialization and get tokens flowing.
"""

import sys
import yaml
import asyncio
from pathlib import Path
from yaml import Loader

async def test_dex_screener_fix():
    """Test and fix DexScreener scanner."""
    print("🧪 Testing DexScreener Scanner Fix...\n")
    
    try:
        from scanners.discovery.dex_screener_scanner import DexScreenerScanner
        
        # Load configuration
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.load(f, Loader=Loader)
        
        scanner_config = config.get('scanners', {}).get('dex_screener', {})
        
        print(f"📋 DexScreener Config:")
        for key, value in scanner_config.items():
            print(f"   {key}: {value}")
        
        # Initialize scanner
        scanner = DexScreenerScanner(config=scanner_config)
        print(f"\n✅ DexScreener scanner created")
        
        # Initialize the scanner (this is the missing step!)
        await scanner.initialize()
        print(f"✅ DexScreener scanner initialized")
        
        # Test scanning
        print(f"\n🔍 Testing scan...")
        results = await scanner.scan("ethereum")
        
        print(f"📊 Scan Results:")
        print(f"   Total results: {len(results)}")
        
        if results:
            print(f"   ✅ SUCCESS! Found {len(results)} tokens!")
            
            # Show first few results
            for i, result in enumerate(results[:3]):
                print(f"   📋 Result {i+1}:")
                if isinstance(result, dict):
                    print(f"      Chain: {result.get('chainId', 'unknown')}")
                    print(f"      Symbol: {result.get('symbol', 'unknown')}")
                    print(f"      Price: {result.get('priceUsd', 'unknown')}")
                    print(f"      Volume: {result.get('volume', {}).get('h24', 'unknown')}")
        else:
            print(f"   ❌ No tokens found")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ DexScreener test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    print("🎯 Quick Scanner Fix Test")
    print("=" * 30)
    
    # Test DexScreener fix
    dex_ok = await test_dex_screener_fix()
    
    print(f"\n📊 Test Results:")
    print(f"   DexScreener: {'✅ WORKING' if dex_ok else '❌ BROKEN'}")
    
    if dex_ok:
        print(f"\n🎉 SCANNER FIX SUCCESSFUL!")
        print(f"✅ DexScreener scanner is now working")
        print(f"✅ Tokens will flow into the trading cycle")
        print(f"✅ The trading cycle should no longer be stuck")
    else:
        print(f"\n❌ SCANNER FIX FAILED!")
        print(f"   Check the error messages above")
    
    return dex_ok

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
