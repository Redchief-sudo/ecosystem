#!/usr/bin/env python3
"""
Test script to verify OpportunityEnricher works correctly.
This validates that the enricher can calculate technical indicators properly.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.rsi_calculator import RSICalculator
from utils.macd_calculator import MACDCalculator
from data_sources.opportunity_enricher import OpportunityEnricher


def test_rsi_calculator():
    """Test RSI calculation."""
    print("Testing RSI Calculator...")
    
    # Create sample price data (uptrend then downtrend)
    prices = [100.0]
    for i in range(14):
        prices.append(prices[-1] + 0.5)  # Uptrend
    for i in range(10):
        prices.append(prices[-1] - 0.3)  # Slight downtrend
    
    calculator = RSICalculator(period=14)
    rsi_values = []
    
    for price in prices:
        rsi = calculator.add_price(price)
        if rsi is not None:
            rsi_values.append(rsi)
    
    if rsi_values:
        final_rsi = rsi_values[-1]
        print(f"  ✅ RSI calculated: {final_rsi:.2f}")
        assert 0 <= final_rsi <= 100, f"RSI out of range: {final_rsi}"
        print(f"  Final RSI value: {final_rsi:.2f} (should be >70 for uptrend)")
    else:
        print(f"  ❌ No RSI values calculated")
        return False
    
    return True


def test_macd_calculator():
    """Test MACD calculation."""
    print("\nTesting MACD Calculator...")
    
    # Create sample price data (strong uptrend)
    prices = [100.0]
    for i in range(60):
        prices.append(prices[-1] + 0.3)  # Strong uptrend
    
    calculator = MACDCalculator()
    macd_values = []
    
    for price in prices:
        macd, signal, histogram = calculator.add_price(price)
        if macd is not None:
            macd_values.append((macd, signal, histogram))
    
    if macd_values:
        final_macd, final_signal, final_histogram = macd_values[-1]
        print(f"  ✅ MACD calculated:")
        print(f"     MACD: {final_macd:.6f}")
        print(f"     Signal: {final_signal:.6f}")
        print(f"     Histogram: {final_histogram:.6f}")
        print(f"  In uptrend, histogram should be positive: {final_histogram > 0}")
    else:
        print(f"  ❌ No MACD values calculated")
        return False
    
    return True


def test_bollinger_bands():
    """Test Bollinger Bands calculation."""
    print("\nTesting Bollinger Bands...")
    
    enricher = OpportunityEnricher()
    
    # Create price data oscillating around 100
    prices = [100.0 + (i % 2 * 2 - 1) for i in range(30)]
    
    bb = enricher._calculate_bollinger_bands(prices)
    
    if bb.get("upper"):
        print(f"  ✅ Bollinger Bands calculated:")
        print(f"     Upper: {bb['upper']:.2f}")
        print(f"     Middle: {bb['middle']:.2f}")
        print(f"     Lower: {bb['lower']:.2f}")
        print(f"     Position: {bb['position']:.2f}")
        assert 0 <= bb['position'] <= 1, f"Position out of range: {bb['position']}"
    else:
        print(f"  ❌ Bollinger Bands failed")
        return False
    
    return True


def test_volume_profile():
    """Test volume profile calculation."""
    print("\nTesting Volume Profile...")
    
    enricher = OpportunityEnricher()
    
    # Create volume data showing increasing trend
    volumes = [1000000.0 + (i * 10000) for i in range(20)]
    
    profile = enricher._calculate_volume_profile(volumes)
    
    print(f"  ✅ Volume profile calculated: {profile:.2f}")
    assert 0 <= profile <= 1, f"Profile out of range: {profile}"
    print(f"  Volume trending up, profile should be >0.5: {profile > 0.5}")
    
    return True


def test_enricher_data_quality():
    """Test data quality assessment."""
    print("\nTesting Data Quality Assessment...")
    
    enricher = OpportunityEnricher()
    
    # Test with excellent data
    prices = list(range(100, 200))  # 100 data points
    volumes = [1000000 + i * 1000 for i in range(100)]
    
    quality = enricher._assess_data_quality(prices, volumes)
    
    print(f"  ✅ Data quality assessment:")
    print(f"     Price points: {quality['price_points']}")
    print(f"     Volume points: {quality['volume_points']}")
    print(f"     Overall quality: {quality['overall_quality']}")
    print(f"     Sufficient for RSI: {quality['sufficient_for_rsi']}")
    print(f"     Sufficient for MACD: {quality['sufficient_for_macd']}")
    print(f"     Sufficient for Bollinger: {quality['sufficient_for_bollinger']}")
    
    assert quality['overall_quality'] == 'excellent', "Should be excellent with 100 points"
    assert quality['sufficient_for_rsi'], "Should be sufficient for RSI"
    assert quality['sufficient_for_macd'], "Should be sufficient for MACD"
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("OpportunityEnricher Test Suite")
    print("=" * 60)
    
    tests = [
        test_rsi_calculator,
        test_macd_calculator,
        test_bollinger_bands,
        test_volume_profile,
        test_enricher_data_quality,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"  ❌ Test failed with error: {e}")
            results.append((test.__name__, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! Enricher is working correctly.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    exit(main())
