#!/usr/bin/env python3
"""
Simple Scanner Test - Check what scanners are available and their basic structure.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_scanner_imports():
    """Test what scanners can be imported."""
    print("Testing scanner imports...")
    
    scanners = {}
    
    # Test DexScreenerScanner (the real one)
    try:
        from scanners.discovery.dex_screener_scanner import DexScreenerScanner
        scanners['DexScreenerScanner'] = DexScreenerScanner
        print("✓ DexScreenerScanner imported")
    except Exception as e:
        print(f"✗ DexScreenerScanner: {e}")
    
    # Test experimental scanners (should be removed)
    try:
        from scanners.experimental.dexscreener_ultra_scanner import DexScreenerUltraScanner
        scanners['DexScreenerUltraScanner'] = DexScreenerUltraScanner
        print("✓ DexScreenerUltraScanner imported (should be removed)")
    except Exception as e:
        print(f"✗ DexScreenerUltraScanner: {e}")
    
    # Test individual scanner imports
    try:
        from scanners.discovery.onchain_scanner import OnChainScannerUltra
        scanners['OnChainScannerUltra'] = OnChainScannerUltra
        print("✓ OnChainScannerUltra imported")
    except Exception as e:
        print(f"✗ OnChainScannerUltra: {e}")
    
    try:
        from scanners.discovery.mempool_scanner import MempoolScannerUltra
        scanners['MempoolScannerUltra'] = MempoolScannerUltra
        print("✓ MempoolScannerUltra imported")
    except Exception as e:
        print(f"✗ MempoolScannerUltra: {e}")
    
    return scanners

def test_scanner_structure(scanner_class, name):
    """Test the basic structure of a scanner."""
    print(f"\n--- Testing {name} structure ---")
    
    try:
        # Try to instantiate with minimal config
        scanner = scanner_class({})
        print(f"✓ {name} instantiated successfully")
        
        # Check what methods it has
        methods = [method for method in dir(scanner) if not method.startswith('_')]
        print(f"Available methods: {methods}")
        
        # Check if it has scan methods
        scan_methods = [m for m in methods if 'scan' in m.lower()]
        print(f"Scan methods: {scan_methods}")
        
        # Check if it inherits from ScannerBase
        from scanners.base_scanner import ScannerBase
        if isinstance(scanner, ScannerBase):
            print(f"✓ {name} inherits from ScannerBase")
        else:
            print(f"? {name} does not inherit from ScannerBase")
        
        return scanner
        
    except Exception as e:
        print(f"✗ Failed to test {name}: {e}")
        return None

def test_scanned_token_structure():
    """Test ScannedToken structure."""
    print("\n--- Testing ScannedToken structure ---")
    
    try:
        from scanners.scanned_token import ScannedToken
        
        # Create a test ScannedToken
        token = ScannedToken(
            address="0x1234567890123456789012345678901234567890",
            symbol="TEST",
            name="Test Token",
            decimals=18,
            price=1.23,
            volume_24h=1000000,
            liquidity_usd=500000,
            chain_id=1,
            chain_name="ethereum"
        )
        
        print(f"✓ ScannedToken created successfully")
        print(f"Fields: {list(token.__dict__.keys())}")
        print(f"Sample data: {token.__dict__}")
        
        return token
        
    except Exception as e:
        print(f"✗ ScannedToken test failed: {e}")
        return None

def main():
    """Main test function."""
    print("="*60)
    print("SIMPLE SCANNER STRUCTURE TEST")
    print("="*60)
    
    # Test imports
    scanners = test_scanner_imports()
    
    # Test each scanner structure
    working_scanners = {}
    for name, scanner_class in scanners.items():
        scanner = test_scanner_structure(scanner_class, name)
        if scanner:
            working_scanners[name] = scanner
    
    # Test ScannedToken
    token = test_scanned_token_structure()
    
    print(f"\n--- SUMMARY ---")
    print(f"Working scanners: {len(working_scanners)}")
    for name in working_scanners.keys():
        print(f"  - {name}")
    
    print(f"ScannedToken available: {'Yes' if token else 'No'}")

if __name__ == '__main__':
    main()
