#!/usr/bin/env python3
"""
Direct test of pre-enrichment method in isolation.
"""
import sys
sys.path.insert(0, "/home/damien/ecosystem")

# Mock the TradeOpportunity class to avoid validation issues
class MockMarketData:
    def __init__(self):
        self.price = 100.0
        self.volume_24h = 1000000.0
        self.liquidity = 5000000.0

class MockToken:
    def __init__(self):
        self.symbol = "TEST"

class MockOpportunity:
    def __init__(self):
        self.token = MockToken()
        self.market_data = MockMarketData()
        self.metadata = {}

def test_pre_enrichment():
    """Test if pre-enrichment adds required fields"""
    from ai.elite_async_ai_controller import EliteAsyncAIController
    
    # Create mock opportunity
    opportunity = MockOpportunity()
    
    print(f"Before pre-enrichment:")
    print(f"  Metadata keys: {list(opportunity.metadata.keys())}")
    print(f"  Metadata size: {len(opportunity.metadata)}")
    
    # Create minimal AI controller
    class FakeController:
        current_regime = "neutral"
    
    controller = FakeController()
    
    # Apply pre-enrichment
    EliteAsyncAIController._pre_enrich_opportunity(controller, opportunity)
    
    print(f"\nAfter pre-enrichment:")
    print(f"  Metadata keys: {list(opportunity.metadata.keys())}")
    print(f"  Metadata size: {len(opportunity.metadata)}")
    
    # Check required fields
    required_fields = [
        "rsi", "macd", "macd_signal", "volatility",
        "price_change_1h", "price_change_24h", "price_change_7d",
        "market_cap", "liquidity_score", "rugpull_risk",
    ]
    
    print(f"\nRequired fields check:")
    missing = []
    for field in required_fields:
        if field in opportunity.metadata:
            val = opportunity.metadata[field]
            print(f"  ✅ {field}: {val}")
        else:
            print(f"  ❌ {field}: MISSING")
            missing.append(field)
    
    if missing:
        print(f"\n❌ Missing {len(missing)} fields: {missing}")
        return False
    else:
        print(f"\n✅ All {len(opportunity.metadata)} pre-enrichment fields present!")
        return True

if __name__ == "__main__":
    success = test_pre_enrichment()
    sys.exit(0 if success else 1)
