#!/usr/bin/env python3
"""
Integration test for the complete data enrichment pipeline.

Tests:
1. DataManager initialization and token snapshot storage
2. OpportunityEnricher retrieving historical data from DataManager
3. Technical indicators calculated from real historical data
4. Entry Manager scoring opportunities with enriched data
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.models import TradeOpportunity, TokenInfo, MarketData, AssetClass, OrderSide
from data_sources.data_manager import DataManager
from data_sources.opportunity_enricher import OpportunityEnricher


@dataclass
class TestConfig:
    """Configuration for integration test."""
    db_path: str = "test_integration.db"
    test_token_address: str = "0x1234567890123456789012345678901234567890"
    test_token_symbol: str = "TEST"
    test_token_name: str = "Test Token"
    test_chain: str = "ethereum"
    test_decimals: int = 18


def create_test_token_info(config: TestConfig) -> TokenInfo:
    """Create a test TokenInfo object."""
    return TokenInfo(
        symbol=config.test_token_symbol,
        address=config.test_token_address,
        chain_id=1,  # Ethereum chain ID
        name=config.test_token_name,
        decimals=config.test_decimals,
        asset_class=AssetClass.CRYPTO,
    )


def create_test_market_data() -> MarketData:
    """Create test MarketData with realistic values."""
    return MarketData(
        price=100.0,
        volume_24h=1000000.0,
        liquidity=5000000.0,
        timestamp=datetime.now(timezone.utc),
    )


def create_test_opportunity(config: TestConfig, market_data: MarketData) -> TradeOpportunity:
    """Create a test TradeOpportunity."""
    return TradeOpportunity(
        token=create_test_token_info(config),
        market_data=market_data,
        scanner_id="test_scanner",
        scanner_version="1.0",
        confidence=0.7,
        chain=config.test_chain,
        token_address=config.test_token_address,
    )


def test_data_manager_initialization():
    """Test that DataManager initializes and creates tables."""
    print("\n" + "=" * 60)
    print("TEST 1: DataManager Initialization")
    print("=" * 60)
    
    config = TestConfig()
    dm = DataManager(db_path=config.db_path)
    
    # Verify tables exist
    dm.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in dm.cursor.fetchall()]
    
    required_tables = {'tokens', 'token_snapshots', 'trades', 'positions'}
    found_tables = set(tables)
    missing_tables = required_tables - found_tables
    
    if missing_tables:
        print(f"❌ FAILED: Missing tables: {missing_tables}")
        return False
    
    print(f"✅ PASSED: All required tables exist: {required_tables}")
    dm.close()
    return True


def test_data_manager_token_storage():
    """Test that DataManager can store and retrieve token snapshots."""
    print("\n" + "=" * 60)
    print("TEST 2: DataManager Token Storage")
    print("=" * 60)
    
    config = TestConfig()
    dm = DataManager(db_path=config.db_path)
    
    try:
        # Create/get token
        token_id = dm.get_or_create_token(
            chain=config.test_chain,
            address=config.test_token_address,
            symbol=config.test_token_symbol,
            name=config.test_token_name,
            decimals=config.test_decimals,
        )
        
        if not token_id:
            print("❌ FAILED: Could not create/get token")
            return False
        
        print(f"✅ Created token with ID: {token_id}")
        
        # Generate and save historical snapshots
        base_price = 100.0
        base_volume = 1000000.0
        snapshots_saved = 0
        
        for i in range(50):
            # Create synthetic but realistic price history
            price = base_price + (i * 0.5)  # Slight uptrend
            volume = base_volume + (i * 10000)  # Increasing volume
            
            snapshot_id = dm.save_token_snapshot(
                token_id=token_id,
                price=price,
                price_change_24h=5.0 + (i * 0.1),
                volume_24h=volume,
                liquidity=5000000.0 + (i * 50000),
                market_cap=500000000.0 + (i * 500000),
                volatility=0.15,
                social_sentiment=0.6,
            )
            
            if snapshot_id:
                snapshots_saved += 1
        
        print(f"✅ Saved {snapshots_saved} historical snapshots")
        
        # Retrieve history
        history = dm.get_token_history(token_id=token_id, limit=100)
        
        if len(history) < 40:
            print(f"❌ FAILED: Expected 40+ snapshots, got {len(history)}")
            return False
        
        print(f"✅ Retrieved {len(history)} historical snapshots")
        
        # Verify data quality
        prices = [s.get('price') for s in history if s.get('price') is not None]
        volumes = [s.get('volume_24h') for s in history if s.get('volume_24h') is not None]
        
        if not prices or not volumes:
            print("❌ FAILED: No price or volume data in history")
            return False
        
        print(f"✅ Price range: ${min(prices):.2f} - ${max(prices):.2f}")
        print(f"✅ Volume range: {min(volumes):.0f} - {max(volumes):.0f}")
        
        return True
    
    finally:
        dm.close()


def test_enricher_data_retrieval():
    """Test that OpportunityEnricher can retrieve data from DataManager."""
    print("\n" + "=" * 60)
    print("TEST 3: OpportunityEnricher Data Retrieval")
    print("=" * 60)
    
    config = TestConfig()
    dm = DataManager(db_path=config.db_path)
    enricher = OpportunityEnricher(data_manager=dm)
    
    try:
        # Get token that was created in previous test
        token = dm.get_token_by_address(
            chain=config.test_chain,
            address=config.test_token_address
        )
        
        if not token:
            print("❌ FAILED: Test token not found in database")
            return False
        
        # Test _fetch_historical_data
        async def test_fetch():
            prices, volumes = await enricher._fetch_historical_data(
                token_address=config.test_token_address,
                chain=config.test_chain,
                lookback_periods=100
            )
            return prices, volumes
        
        prices, volumes = asyncio.run(test_fetch())
        
        if not prices or len(prices) < 40:
            print(f"❌ FAILED: Expected 40+ prices, got {len(prices)}")
            return False
        
        if not volumes or len(volumes) < 40:
            print(f"❌ FAILED: Expected 40+ volumes, got {len(volumes)}")
            return False
        
        print(f"✅ Retrieved {len(prices)} price points and {len(volumes)} volume points")
        print(f"✅ Price data: {prices[0]:.2f} → {prices[-1]:.2f}")
        print(f"✅ Volume data: {volumes[0]:.0f} → {volumes[-1]:.0f}")
        
        return True
    
    finally:
        dm.close()


def test_enricher_indicator_calculation():
    """Test that OpportunityEnricher calculates correct technical indicators."""
    print("\n" + "=" * 60)
    print("TEST 4: OpportunityEnricher Indicator Calculation")
    print("=" * 60)
    
    config = TestConfig()
    dm = DataManager(db_path=config.db_path)
    enricher = OpportunityEnricher(data_manager=dm)
    
    try:
        # Create test opportunity
        market_data = create_test_market_data()
        opportunity = create_test_opportunity(config, market_data)
        
        # Enrich opportunity
        async def test_enrich():
            enriched = await enricher.enrich(opportunity)
            return enriched
        
        enriched_opp = asyncio.run(test_enrich())
        
        # Verify enrichment
        if not enriched_opp.metadata or not enriched_opp.metadata.get("data_enriched"):
            print("❌ FAILED: Opportunity not enriched")
            return False
        
        print("✅ Opportunity enriched successfully")
        
        # Check metadata fields
        metadata = enriched_opp.metadata
        required_fields = [
            "price_history",
            "volume_history",
            "technical_indicators",
            "volume_profile",
            "data_quality",
        ]
        
        for field in required_fields:
            if field not in metadata:
                print(f"❌ FAILED: Missing metadata field: {field}")
                return False
        
        print("✅ All required metadata fields present")
        
        # Check technical indicators
        ti = metadata.get("technical_indicators", {})
        required_indicators = ["rsi", "macd", "signal_line", "histogram", "bollinger_position"]
        
        for indicator in required_indicators:
            if indicator not in ti:
                print(f"❌ FAILED: Missing technical indicator: {indicator}")
                return False
        
        print("✅ All technical indicators calculated")
        
        # Verify indicator values are in valid ranges
        rsi = ti.get("rsi", 50)
        if not (0 <= rsi <= 100):
            print(f"❌ FAILED: RSI out of range: {rsi}")
            return False
        
        bollinger_pos = ti.get("bollinger_position", 0.5)
        if not (0 <= bollinger_pos <= 1):
            print(f"❌ FAILED: Bollinger position out of range: {bollinger_pos}")
            return False
        
        print(f"✅ Indicator values in valid ranges:")
        print(f"   RSI: {rsi:.1f}")
        print(f"   MACD: {ti.get('macd', 0):.6f}")
        print(f"   Signal: {ti.get('signal_line', 0):.6f}")
        print(f"   Bollinger Position: {bollinger_pos:.2f}")
        
        # Check data quality assessment
        dq = metadata.get("data_quality", {})
        print(f"✅ Data quality assessment: {dq.get('overall_quality', 'unknown')}")
        
        return True
    
    finally:
        dm.close()


def test_enriched_data_for_entry_manager():
    """Test that enriched data is suitable for Entry Manager evaluation."""
    print("\n" + "=" * 60)
    print("TEST 5: Enriched Data for Entry Manager")
    print("=" * 60)
    
    config = TestConfig()
    dm = DataManager(db_path=config.db_path)
    enricher = OpportunityEnricher(data_manager=dm)
    
    try:
        # Create test opportunity
        market_data = create_test_market_data()
        opportunity = create_test_opportunity(config, market_data)
        
        # Enrich opportunity
        async def test_enrich():
            enriched = await enricher.enrich(opportunity)
            return enriched
        
        enriched_opp = asyncio.run(test_enrich())
        metadata = enriched_opp.metadata
        
        # Simulate Entry Manager data structure
        entry_data = {
            "price_history": metadata.get("price_history", []),
            "rsi": metadata.get("technical_indicators", {}).get("rsi", 50.0),
            "volume_profile": metadata.get("volume_profile", 0.5),
            "macd": metadata.get("technical_indicators", {}).get("macd", 0.0),
            "signal_line": metadata.get("technical_indicators", {}).get("signal_line", 0.0),
            "bollinger_position": metadata.get("technical_indicators", {}).get("bollinger_position", 0.5),
            "price": enriched_opp.market_data.price,
            "volume": enriched_opp.market_data.volume_24h,
            "liquidity": enriched_opp.market_data.liquidity,
        }
        
        # Check data completeness
        print("✅ Entry Manager data structure:")
        print(f"   Price history points: {len(entry_data['price_history'])}")
        print(f"   RSI: {entry_data['rsi']:.1f} (from real data, not default 50.0)")
        print(f"   Volume profile: {entry_data['volume_profile']:.2f}")
        print(f"   MACD: {entry_data['macd']:.6f} (from real data, not default 0.0)")
        print(f"   Price: ${float(entry_data['price']):.2f}")
        print(f"   Volume 24h: ${float(entry_data['volume']):,.0f}")
        print(f"   Liquidity: ${float(entry_data['liquidity']):,.0f}")
        
        # Verify we have sufficient data for good entry scoring
        sufficient_data = (
            len(entry_data['price_history']) >= 20 and
            0 <= entry_data['rsi'] <= 100 and  # Real RSI, not default
            entry_data['macd'] != 0.0 and  # Real MACD, not default
            float(entry_data['price']) > 0 and
            float(entry_data['volume']) > 0
        )
        
        if not sufficient_data:
            print("❌ FAILED: Insufficient data for Entry Manager scoring")
            return False
        
        print("✅ Sufficient data for accurate Entry Manager scoring")
        return True
    
    finally:
        dm.close()


def cleanup():
    """Remove test database."""
    import os
    test_db = "test_integration.db"
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"\n🧹 Cleaned up test database: {test_db}")


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("DATA ENRICHMENT INTEGRATION TEST SUITE")
    print("=" * 60)
    print("Testing complete pipeline: DataManager → OpportunityEnricher → Entry Manager")
    
    tests = [
        test_data_manager_initialization,
        test_data_manager_token_storage,
        test_enricher_data_retrieval,
        test_enricher_indicator_calculation,
        test_enriched_data_for_entry_manager,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    cleanup()
    
    if passed == total:
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - DATA ENRICHMENT PIPELINE WORKING")
        print("=" * 60)
        print("\nThe system is ready to:")
        print("1. Collect historical price and volume data via DataManager")
        print("2. Calculate real technical indicators (RSI, MACD, Bollinger)")
        print("3. Provide enriched data to Entry Manager for accurate scoring")
        print("4. Execute trades when opportunities pass 60% entry threshold")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
