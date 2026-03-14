#!/usr/bin/env python3
"""
Test pre-enrichment to verify it adds necessary fields for strategies.
"""
import sys
sys.path.insert(0, "/home/damien/ecosystem")

from core.models import TradeOpportunity, TokenInfo, MarketData, AssetClass
from ai.elite_async_ai_controller import EliteAsyncAIController

def test_pre_enrichment():
    """Test if pre-enrichment adds required fields"""
    
    # Create a minimal opportunity
    token = TokenInfo(
        address="EPjFWaJLqPxcxLj6CqxtPgMrF5PLnEqqqz6Q8vdoKaKP",  # Valid Solana address
        symbol="TEST",
        chain_id="solana",
        decimals=6,
        asset_class=AssetClass.CRYPTO
    )
    
    market_data = MarketData(
        price=100.0,
        volume_24h=1000000.0,
        liquidity=5000000.0,
        timestamp="2026-01-27T14:00:00Z"
    )
    
    opportunity = TradeOpportunity(
        opportunity_id="test_opp_1",
        token=token,
        chain="solana",
        market_data=market_data,
        metadata={}
    )
    
    print(f"Before pre-enrichment:")
    print(f"  Metadata keys: {list(opportunity.metadata.keys())}")
    print(f"  Metadata size: {len(opportunity.metadata)}")
    
    # Create AI controller (minimal)
    class FakeTracker:
        def __init__(self):
            self.current_regime = "neutral"
    
    controller = FakeTracker()
    
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
            print(f"  ✅ {field}: {opportunity.metadata[field]}")
        else:
            print(f"  ❌ {field}: MISSING")
            missing.append(field)
    
    if missing:
        print(f"\n❌ Missing {len(missing)} fields: {missing}")
        return False
    else:
        print(f"\n✅ All required fields present!")
        return True

if __name__ == "__main__":
    success = test_pre_enrichment()
    sys.exit(0 if success else 1)
