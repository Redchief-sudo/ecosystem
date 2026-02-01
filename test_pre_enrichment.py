#!/usr/bin/env python3
"""
Quick test to verify pre-enrichment provides data for strategy evaluation.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent))

from core.models import TradeOpportunity, TokenInfo, MarketData, AssetClass
from ai.elite_async_ai_controller import EliteAsyncAIController


def test_pre_enrichment():
    """Test that pre-enrichment provides sensible defaults for strategies."""
    print("\n" + "=" * 60)
    print("Testing Pre-Enrichment")
    print("=" * 60)
    
    # Create AI controller
    controller = EliteAsyncAIController(config={})
    
    # Create minimal opportunity
    token = TokenInfo(
        symbol="TEST",
        address="0x1234567890123456789012345678901234567890",
        chain_id=1,
        decimals=18,
        asset_class=AssetClass.CRYPTO,
    )
    
    market = MarketData(
        price=Decimal("100.0"),
        volume_24h=Decimal("1000000"),
        liquidity=Decimal("5000000"),
        timestamp=datetime.now(timezone.utc),
    )
    
    opportunity = TradeOpportunity(
        token=token,
        market_data=market,
        scanner_id="test",
        scanner_version="1.0",
        opportunity_id="test:0x1234567890123456789012345678901234567890",
        chain="ethereum",
        token_address="0x1234567890123456789012345678901234567890",
        confidence=0.5,
        volatility=0.0,
        metadata={},
    )
    
    print(f"\nBefore pre-enrichment:")
    print(f"  Metadata keys: {list(opportunity.metadata.keys())}")
    print(f"  Metadata empty: {len(opportunity.metadata) == 0}")
    
    # Apply pre-enrichment
    controller._pre_enrich_opportunity(opportunity)
    
    print(f"\nAfter pre-enrichment:")
    metadata = opportunity.metadata
    print(f"  Metadata keys: {len(metadata)} fields")
    
    # Check for required fields
    required_fields = [
        "rsi", "macd", "volatility", "price_change_24h",
        "volume_change_24h", "liquidity_score", "market_cap"
    ]
    
    all_present = all(field in metadata for field in required_fields)
    print(f"  All required fields present: {all_present}")
    
    if all_present:
        print(f"\n✅ Pre-enrichment successful!")
        print(f"  RSI: {metadata['rsi']}")
        print(f"  MACD: {metadata['macd']}")
        print(f"  Volatility: {metadata['volatility']}")
        print(f"  Market Cap: ${metadata['market_cap']:,.0f}")
        print(f"  Liquidity Score: {metadata['liquidity_score']:.2f}")
        print(f"\nStrategies can now evaluate this opportunity!")
        return True
    else:
        missing = [f for f in required_fields if f not in metadata]
        print(f"❌ Missing fields: {missing}")
        return False


if __name__ == "__main__":
    success = test_pre_enrichment()
    sys.exit(0 if success else 1)
