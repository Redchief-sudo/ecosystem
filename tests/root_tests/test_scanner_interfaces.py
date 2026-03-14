#!/usr/bin/env python3
"""
Test script to verify scanner interface compatibility and dynamic network verification.
Tests the fixes for mismatching interfaces, improper configurations, and dynamic token pulling.
"""

import asyncio
import sys
import traceback
from typing import Dict, List, Any
from dataclasses import asdict

# Add current directory to path for imports
sys.path.insert(0, '.')

async def test_scanner_interfaces():
    """Test all scanner interfaces for compatibility."""

    results = {
        "sentiment_scanner": {},
        "dex_screener_scanner": {},
        "onchain_scanner": {},
        "overall": {"passed": 0, "failed": 0, "total": 0}
    }

    print("🧪 Testing Scanner Interface Compatibility")
    print("=" * 60)

    # Test 1: SentimentScanner interface
    print("\n1. Testing SentimentScanner Interface")
    print("-" * 40)

    try:
        from scanners.discovery.sentiment_scanner import SentimentScanner
        from scanners.scan_director import ScanResult

        # Initialize scanner
        scanner = SentimentScanner(max_concurrent=1, log_level="WARNING")
        await scanner.initialize()

        # Test scan_network method
        class MockChainType:
            value = "ethereum"

        chain_type = MockChainType()
        result = await scanner.scan_network(chain_type)

        # Verify result is ScanResult
        assert isinstance(result, ScanResult), f"Expected ScanResult, got {type(result)}"
        assert hasattr(result, 'scanner_name'), "Missing scanner_name"
        assert hasattr(result, 'chain_type'), "Missing chain_type"
        assert hasattr(result, 'tokens'), "Missing tokens"
        assert hasattr(result, 'scan_time_ms'), "Missing scan_time_ms"
        assert hasattr(result, 'success'), "Missing success"
        assert hasattr(result, 'metadata'), "Missing metadata"

        # Test dynamic token analysis
        token_result = await scanner.scan(tokens=["0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"])
        assert isinstance(token_result, list), "Expected list from scan method"

        results["sentiment_scanner"] = {
            "scan_network": "PASS",
            "dynamic_tokens": "PASS",
            "interface_compatibility": "PASS"
        }
        print("✅ SentimentScanner interface: PASS")

    except Exception as e:
        results["sentiment_scanner"] = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(f"❌ SentimentScanner interface: FAIL - {e}")

    # Test 2: DexScreenerScanner interface
    print("\n2. Testing DexScreenerScanner Interface")
    print("-" * 40)

    try:
        from scanners.discovery.dex_screener_scanner import DexScreenerScanner

        scanner = DexScreenerScanner(config={"min_liquidity": 1000}, max_concurrent=1)
        await scanner.initialize()

        # Test scan_network method
        chain_type = MockChainType()
        result = await scanner.scan_network(chain_type)

        assert isinstance(result, ScanResult), f"Expected ScanResult, got {type(result)}"
        assert result.scanner_name == "DexScreenerScanner", f"Wrong scanner name: {result.scanner_name}"
        assert "scanner_type" in result.metadata, "Missing scanner_type in metadata"

        results["dex_screener_scanner"] = {
            "scan_network": "PASS",
            "metadata": "PASS",
            "interface_compatibility": "PASS"
        }
        print("✅ DexScreenerScanner interface: PASS")

    except Exception as e:
        results["dex_screener_scanner"] = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(f"❌ DexScreenerScanner interface: FAIL - {e}")

    # Test 3: OnChainScanner interface
    print("\n3. Testing OnChainScanner Interface")
    print("-" * 40)

    try:
        from scanners.discovery.onchain_scanner import OnChainScannerUltra

        scanner = OnChainScannerUltra(config={"min_liquidity": 1000}, max_concurrent=1)
        await scanner.initialize()

        # Test scan_network method
        chain_type = MockChainType()
        result = await scanner.scan_network(chain_type)

        assert isinstance(result, ScanResult), f"Expected ScanResult, got {type(result)}"
        assert result.scanner_name == "OnChainScannerUltra", f"Wrong scanner name: {result.scanner_name}"

        # Test dynamic chain capability checking
        supported = scanner._is_chain_supported("ethereum")
        assert supported, "Ethereum should be supported"

        not_supported = scanner._is_chain_supported("nonexistent_chain")
        assert not not_supported, "Nonexistent chain should not be supported"

        results["onchain_scanner"] = {
            "scan_network": "PASS",
            "dynamic_capability": "PASS",
            "interface_compatibility": "PASS"
        }
        print("✅ OnChainScanner interface: PASS")

    except Exception as e:
        results["onchain_scanner"] = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(f"❌ OnChainScanner interface: FAIL - {e}")

    # Test 4: Cross-scanner compatibility
    print("\n4. Testing Cross-Scanner Compatibility")
    print("-" * 40)

    try:
        # Test that all scanners can be imported and initialized
        scanners = []

        from scanners.discovery.sentiment_scanner import SentimentScanner as SS
        scanners.append(("SentimentScanner", SS))

        from scanners.discovery.dex_screener_scanner import DexScreenerScanner as DSS
        scanners.append(("DexScreenerScanner", DSS))

        from scanners.discovery.onchain_scanner import OnChainScannerUltra as OCS
        scanners.append(("OnChainScannerUltra", OCS))

        for name, scanner_class in scanners:
            # Test basic instantiation
            scanner = scanner_class(max_concurrent=1, log_level="WARNING")
            await scanner.initialize()
            await scanner.cleanup()
            print(f"✅ {name} instantiation: PASS")

        results["cross_scanner"] = {
            "import": "PASS",
            "instantiation": "PASS",
            "cleanup": "PASS"
        }
        print("✅ Cross-scanner compatibility: PASS")

    except Exception as e:
        results["cross_scanner"] = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(f"❌ Cross-scanner compatibility: FAIL - {e}")

    # Calculate overall results
    for scanner_results in [results["sentiment_scanner"], results["dex_screener_scanner"],
                           results["onchain_scanner"], results["cross_scanner"]]:
        if isinstance(scanner_results, dict):
            for test, status in scanner_results.items():
                if status == "PASS":
                    results["overall"]["passed"] += 1
                elif status in ["FAIL", "error"]:
                    results["overall"]["failed"] += 1
                results["overall"]["total"] += 1

    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)

    print(f"Total Tests: {results['overall']['total']}")
    print(f"Passed: {results['overall']['passed']}")
    print(f"Failed: {results['overall']['failed']}")
    print(".1f")

    if results['overall']['failed'] == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED - Review details above")

    return results

async def main():
    """Main test execution."""
    try:
        results = await test_scanner_interfaces()

        # Save results to file
        import json
        with open("scanner_interface_test_results.json", "w") as f:
            # Convert results to JSON-serializable format
            json_results = {}
            for key, value in results.items():
                if isinstance(value, dict):
                    json_results[key] = {}
                    for k, v in value.items():
                        if k == "traceback":
                            # Truncate traceback for readability
                            json_results[key][k] = v[:500] + "..." if len(v) > 500 else v
                        else:
                            json_results[key][k] = v
                else:
                    json_results[key] = value

            json.dump(json_results, f, indent=2)

        print("\n📄 Results saved to: scanner_interface_test_results.json")

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
