#!/usr/bin/env python3
"""
Integration test to verify OpportunityEnricher works with the trading loop.
This simulates what happens when an opportunity comes in and needs enrichment.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.models import TradeOpportunity, TokenInfo, MarketData
from data_sources.opportunity_enricher import OpportunityEnricher


async def test_enrichment_flow():
    """Test the full enrichment flow."""
    print("=" * 60)
    print("Testing Opportunity Enrichment Flow")
    print("=" * 60)
    
    # Create a mock opportunity with minimal data (what scanner provides)
    token_info = TokenInfo(
        address="0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
        symbol="DAI",
        name="Dai Stablecoin",
        chain_id=1,  # Ethereum
        decimals=18
    )
    
    market_data = MarketData(
        price=1.001,
        volume_24h=500000000,
        liquidity=100000000,
        market_cap=5000000000,
        price_change_24h=0.1
    )
    
    opportunity = TradeOpportunity(
        token=token_info,
        market_data=market_data,
        chain="ethereum",
        token_address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
        source="test",
        confidence_score=0.5,
        entry_signal="stable_entry"
    )
    
    print(f"\nOriginal opportunity:")
    print(f"  Token: {opportunity.token.symbol}")
    print(f"  Price: ${opportunity.market_data.price}")
    print(f"  Volume 24h: ${opportunity.market_data.volume_24h:,.0f}")
    print(f"  Metadata before enrichment: {opportunity.metadata}")
    
    # Create enricher (without data_manager)
    enricher = OpportunityEnricher(data_manager=None)
    
    # Enrich the opportunity
    enriched = await enricher.enrich(opportunity)
    
    print(f"\nEnriched opportunity:")
    print(f"  Data enriched: {enriched.metadata.get('data_enriched', False)}")
    print(f"  Technical indicators:")
    indicators = enriched.metadata.get('technical_indicators', {})
    print(f"    RSI: {indicators.get('rsi', 'N/A')}")
    print(f"    MACD: {indicators.get('macd', 'N/A')}")
    print(f"    Signal: {indicators.get('signal_line', 'N/A')}")
    print(f"    Bollinger Position: {indicators.get('bollinger_position', 'N/A')}")
    print(f"  Volume profile: {enriched.metadata.get('volume_profile', 'N/A')}")
    print(f"  Data quality: {enriched.metadata.get('data_quality', {}).get('overall_quality', 'N/A')}")
    
    # Verify all expected fields are present
    expected_fields = [
        'data_enriched',
        'technical_indicators',
        'volume_profile',
        'data_quality',
        'enriched_at'
    ]
    
    all_present = all(field in enriched.metadata for field in expected_fields)
    
    print(f"\n{'✅' if all_present else '❌'} All expected fields present: {all_present}")
    
    # Check that technical indicators have expected keys
    expected_indicators = ['rsi', 'macd', 'signal_line', 'histogram', 'bollinger_position']
    indicators_dict = enriched.metadata.get('technical_indicators', {})
    indicators_present = all(key in indicators_dict for key in expected_indicators)
    
    print(f"{'✅' if indicators_present else '❌'} All expected indicators present: {indicators_present}")
    
    return all_present and indicators_present


async def main():
    """Run integration test."""
    try:
        result = await test_enrichment_flow()
        
        print("\n" + "=" * 60)
        if result:
            print("✅ Integration test PASSED")
            print("Enricher is ready for production use!")
            return 0
        else:
            print("❌ Integration test FAILED")
            return 1
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
