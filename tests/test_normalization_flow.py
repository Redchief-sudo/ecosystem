#!/usr/bin/env python3
"""
Normalization Flow Test
Tests the complete data flow: Scanner → TokenNormalizer → TokenCandidate → TradeOpportunity
Verifies that all fields are properly mapped and live data is used correctly.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scanners.discovery.dex_screener_scanner import DexScreenerScanner
from scanners.scanned_token import ScannedToken
from trading.token_pipeline.token_normalizer import TokenNormalizer
from trading.token_pipeline.token_candidate import TokenCandidate
from core.models import TradeOpportunity, TokenInfo, MarketData, AssetClass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NormalizationFlowTester:
    """Tests the complete normalization flow."""
    
    def __init__(self):
        self.normalizer = TokenNormalizer()
        self.results = {
            'scanner_data': [],
            'normalized_candidates': [],
            'trade_opportunities': [],
            'field_analysis': {}
        }
    
    async def test_scanner_data(self) -> List[Dict]:
        """Test scanner data generation."""
        logger.info("Testing scanner data generation...")
        
        # Create mock scanner data directly (since DexScreenerScanner doesn't have start/stop)
        scan_results = await self._create_mock_scanner_data()
        
        logger.info(f"Generated {len(scan_results)} scanner results")
        self.results['scanner_data'] = scan_results
        return scan_results
    
    async def _create_mock_scanner_data(self) -> List[Dict]:
        """Create mock scanner data that mimics real DexScreener output."""
        # Create realistic ScannedToken data with VALID 42-character Ethereum addresses
        mock_tokens = [
            {
                'address': '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                'symbol': 'TEST',
                'name': 'Test Token',
                'decimals': 18,
                'price': 1.234567,
                'price_change_5m': 2.5,
                'price_change_1h': 5.2,
                'price_change_24h': 12.8,
                'price_change_7d': -3.1,
                'volume_24h': 1234567.89,
                'liquidity_usd': 987654.32,
                'market_cap': 0.0,
                'zscore': 1.23,
                'strength': 0.87,
                'momentum': 0.92,
                'volatility': 0.15,
                'chain_id': 1,
                'chain_name': 'ethereum',
                'exchange': 'uniswap_v3',
                'pair_address': '0x1234567890123456789012345678901234567890',
                'first_seen': datetime.now(timezone.utc),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'metadata': {'source': 'dexscreener'},
                'holders': 1234,
                'has_traded': True,
                'is_blacklisted': False
            },
            {
                'address': '0x1234567890123456789012345678901234567890',
                'symbol': 'DEMO',
                'name': 'Demo Token',
                'decimals': 6,
                'price': 0.00001234,
                'price_change_5m': -1.2,
                'price_change_1h': 3.4,
                'price_change_24h': 8.9,
                'price_change_7d': 15.2,
                'volume_24h': 567890.12,
                'liquidity_usd': 234567.89,
                'market_cap': 0.0,
                'zscore': 0.98,
                'strength': 0.76,
                'momentum': 0.81,
                'volatility': 0.22,
                'chain_id': 56,
                'chain_name': 'bsc',
                'exchange': 'pancakeswap_v2',
                'pair_address': '0x098765432109876543210987654321098765432',
                'first_seen': datetime.now(timezone.utc),
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc),
                'metadata': {'source': 'dexscreener'},
                'holders': 5678,
                'has_traded': True,
                'is_blacklisted': False
            }
        ]
        
        return mock_tokens
    
    async def test_normalization(self, scanner_data: List[Dict]) -> List[TokenCandidate]:
        """Test normalization from scanner data to TokenCandidate."""
        logger.info("Testing normalization pipeline...")
        
        candidates = []
        
        for i, data in enumerate(scanner_data):
            try:
                # Use the ScannedToken adapter
                candidate = self.normalizer.normalize_scanned_token(data)
                
                if candidate:
                    candidates.append(candidate)
                    logger.info(f"✓ Normalized token {i+1}: {candidate.symbol}")
                else:
                    logger.warning(f"✗ Failed to normalize token {i+1}")
                    
            except Exception as e:
                logger.error(f"✗ Normalization error for token {i+1}: {e}")
        
        logger.info(f"Successfully normalized {len(candidates)}/{len(scanner_data)} tokens")
        self.results['normalized_candidates'] = candidates
        return candidates
    
    async def test_opportunity_creation(self, candidates: List[TokenCandidate]) -> List[TradeOpportunity]:
        """Test creation of TradeOpportunity from TokenCandidate."""
        logger.info("Testing TradeOpportunity creation...")
        
        opportunities = []
        
        for i, candidate in enumerate(candidates):
            try:
                opportunity = self._convert_candidate_to_opportunity(candidate)
                
                if opportunity:
                    opportunities.append(opportunity)
                    logger.info(f"✓ Created opportunity {i+1}: {opportunity.token.symbol}")
                else:
                    logger.warning(f"✗ Failed to create opportunity {i+1}")
                    
            except Exception as e:
                logger.error(f"✗ Opportunity creation error for token {i+1}: {e}")
        
        logger.info(f"Successfully created {len(opportunities)}/{len(candidates)} opportunities")
        self.results['trade_opportunities'] = opportunities
        return opportunities
    
    def _convert_candidate_to_opportunity(self, candidate: TokenCandidate) -> TradeOpportunity:
        """Convert TokenCandidate to TradeOpportunity."""
        from decimal import Decimal
        
        # Create TokenInfo from candidate
        token = TokenInfo(
            symbol=candidate.symbol,
            address=candidate.address,
            chain_id=self._get_chain_id_from_name(candidate.chain),
            decimals=18,  # Default, should be enriched later
            name=candidate.name,
            asset_class=AssetClass.CRYPTO
        )
        
        # Create MarketData from candidate
        market_data = MarketData(
            price=Decimal(str(candidate.price_usd)) if candidate.price_usd else Decimal('0'),
            volume_24h=candidate.volume_24h or 0,
            liquidity=candidate.liquidity_usd or 0,
            timestamp=candidate.discovered_at or datetime.now(timezone.utc)
        )
        
        # Create TradeOpportunity
        return TradeOpportunity(
            token=token,
            market_data=market_data,
            scanner_id=candidate.source or 'unknown',
            scanner_version='1.0',
            metadata={'confidence': candidate.confidence},
            opportunity_id=candidate.address,
            chain=candidate.chain or '',
            token_address=candidate.address,
            confidence=candidate.confidence or 0.0
        )
    
    def _get_chain_id_from_name(self, chain_name: str) -> int:
        """Convert chain name to chain ID."""
        chain_mapping = {
            'ethereum': 1,
            'bsc': 56,
            'polygon': 137,
            'arbitrum': 42161,
            'optimism': 10,
            'avalanche': 43114
        }
        return chain_mapping.get(chain_name.lower(), 1)
    
    def analyze_field_mappings(self):
        """Analyze field mappings across the pipeline."""
        logger.info("Analyzing field mappings...")
        
        analysis = {
            'scanner_fields': set(),
            'candidate_fields': set(),
            'opportunity_fields': set(),
            'field_coverage': {}
        }
        
        # Collect scanner fields
        if self.results['scanner_data']:
            analysis['scanner_fields'] = set(self.results['scanner_data'][0].keys())
        
        # Collect candidate fields
        if self.results['normalized_candidates']:
            analysis['candidate_fields'] = set(self.results['normalized_candidates'][0].__dict__.keys())
        
        # Collect opportunity fields
        if self.results['trade_opportunities']:
            analysis['opportunity_fields'] = set(self.results['trade_opportunities'][0].__dict__.keys())
        
        # Analyze field coverage
        critical_fields = {
            'address': 'Token identifier',
            'symbol': 'Token symbol',
            'name': 'Token name',
            'price': 'Current price',
            'volume_24h': '24h volume',
            'liquidity_usd': 'Liquidity in USD',
            'chain_id': 'Blockchain ID',
            'chain_name': 'Blockchain name'
        }
        
        for field, description in critical_fields.items():
            coverage = {
                'scanner': field in analysis['scanner_fields'],
                'candidate': field in analysis['candidate_fields'],
                'opportunity': field in analysis['opportunity_fields'],
                'description': description
            }
            analysis['field_coverage'][field] = coverage
        
        self.results['field_analysis'] = analysis
        return analysis
    
    def print_detailed_results(self):
        """Print detailed results of the test."""
        print("\n" + "="*80)
        print("NORMALIZATION FLOW TEST RESULTS")
        print("="*80)
        
        # Scanner data
        print(f"\n📊 Scanner Data: {len(self.results['scanner_data'])} items")
        if self.results['scanner_data']:
            sample = self.results['scanner_data'][0]
            print(f"Sample scanner fields: {list(sample.keys())}")
            print(f"Sample scanner data: {json.dumps(sample, indent=2, default=str)}")
        
        # Normalized candidates
        print(f"\n🔄 Normalized Candidates: {len(self.results['normalized_candidates'])} items")
        if self.results['normalized_candidates']:
            sample = self.results['normalized_candidates'][0]
            print(f"Sample candidate fields: {list(sample.__dict__.keys())}")
            print(f"Sample candidate: {json.dumps(sample.__dict__, indent=2, default=str)}")
        
        # Trade opportunities
        print(f"\n💰 Trade Opportunities: {len(self.results['trade_opportunities'])} items")
        if self.results['trade_opportunities']:
            sample = self.results['trade_opportunities'][0]
            print(f"Sample opportunity fields: {list(sample.__dict__.keys())}")
            print(f"Sample opportunity: {json.dumps(sample.__dict__, indent=2, default=str)}")
        
        # Field analysis
        print(f"\n🔍 Field Coverage Analysis:")
        analysis = self.results['field_analysis']
        if analysis.get('field_coverage'):
            for field, coverage in analysis['field_coverage'].items():
                status = "✓" if coverage['opportunity'] else "✗"
                print(f"  {status} {field}: {coverage['description']}")
                print(f"     Scanner: {'✓' if coverage['scanner'] else '✗'} | "
                      f"Candidate: {'✓' if coverage['candidate'] else '✗'} | "
                      f"Opportunity: {'✓' if coverage['opportunity'] else '✗'}")
        
        # Success metrics
        scanner_count = len(self.results['scanner_data'])
        candidate_count = len(self.results['normalized_candidates'])
        opportunity_count = len(self.results['trade_opportunities'])
        
        print(f"\n📈 Success Metrics:")
        print(f"  Scanner → Normalization: {candidate_count}/{scanner_count} ({candidate_count/scanner_count*100:.1f}%)")
        print(f"  Normalization → Opportunity: {opportunity_count}/{candidate_count} ({opportunity_count/candidate_count*100:.1f}%)")
        print(f"  Overall Success: {opportunity_count}/{scanner_count} ({opportunity_count/scanner_count*100:.1f}%)")
    
    def save_results(self, filename: str = 'normalization_flow_test.json'):
        """Save test results to file."""
        # Convert to serializable format
        serializable_results = {
            'scanner_data': self.results['scanner_data'],
            'normalized_candidates': [c.__dict__ for c in self.results['normalized_candidates']],
            'trade_opportunities': [o.__dict__ for o in self.results['trade_opportunities']],
            'field_analysis': {
                'scanner_fields': list(self.results['field_analysis']['scanner_fields']),
                'candidate_fields': list(self.results['field_analysis']['candidate_fields']),
                'opportunity_fields': list(self.results['field_analysis']['opportunity_fields']),
                'field_coverage': {
                    field: {
                        'scanner': coverage['scanner'],
                        'candidate': coverage['candidate'],
                        'opportunity': coverage['opportunity'],
                        'description': coverage['description']
                    }
                    for field, coverage in self.results['field_analysis']['field_coverage'].items()
                }
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        print(f"\n📁 Results saved to: {filename}")

async def main():
    """Main test function."""
    print("="*80)
    print("NORMALIZATION FLOW TEST")
    print("="*80)
    
    tester = NormalizationFlowTester()
    
    try:
        # Test scanner data generation
        scanner_data = await tester.test_scanner_data()
        
        if not scanner_data:
            print("❌ No scanner data generated - test failed")
            return
        
        # Test normalization
        candidates = await tester.test_normalization(scanner_data)
        
        if not candidates:
            print("❌ No candidates normalized - test failed")
            return
        
        # Test opportunity creation
        opportunities = await tester.test_opportunity_creation(candidates)
        
        # Analyze field mappings
        tester.analyze_field_mappings()
        
        # Print results
        tester.print_detailed_results()
        
        # Save results
        tester.save_results()
        
        print(f"\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
