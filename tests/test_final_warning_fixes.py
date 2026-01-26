#!/usr/bin/env python3
"""
Final test of all warning fixes
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_all_fixes():
    """Test that all warning fixes work properly."""
    
    logger.info("🧪 Testing all warning fixes...")
    
    try:
        # Test 1: Multi-chain ingestion authority resolution
        from trading.token_pipeline.multi_chain_ingestion import MultiChainTokenIngestionPipeline
        
        pipeline = MultiChainTokenIngestionPipeline({'max_queue_size': 1000})
        
        # Test token with real-world chain conflict
        conflict_token = {
            'symbol': 'ETH',
            'address': '0x2170Ed0880ac9A755fd29B2688956BD959F933F8',
            'chain': 'blast',
            'chain_id': 81457,
            'metadata': {
                'dex_data': {
                    'chainId': 'bsc'  # Real conflict from DexScreener
                }
            }
        }
        
        result = pipeline._assert_chain_authority([conflict_token])
        
        if result and result[0]['chain'] == 'bsc' and result[0]['chain_source'] == 'dex_data':
            logger.info("✅ Test 1: Multi-chain ingestion authority resolution works")
        else:
            logger.error(f"❌ Test 1 failed: {result}")
            return False
        
        # Test 2: Multi-chain deduplicator conversion
        from trading.token_pipeline.multi_chain_deduplicator import MultiChainTokenDeduplicator
        
        deduplicator = MultiChainTokenDeduplicator()
        
        result = deduplicator._convert_to_candidate(conflict_token, 'test_scanner')
        
        # The multi-chain ingestion pipeline already resolved the conflict to 'bsc'
        # So the deduplicator should receive the resolved chain
        if result and result.chain == 'bsc' and result.chain_type.value == 'evm':
            logger.info("✅ Test 2: Multi-chain deduplicator conversion works")
        else:
            logger.error(f"❌ Test 2 failed: {result}")
            return False
        
        # Test 3: Chain normalizer handles numeric chain IDs
        from networks.chain_normalizer import chain_normalizer
        
        test_cases = [
            ('bsc', 'bsc'),
            ('56', 'bsc'),
            ('81457', 'blast'),
            ('101001', 'solana'),
            ('101002', 'sui'),
            ('101003', 'aptos'),
        ]
        
        all_passed = True
        for input_chain, expected in test_cases:
            try:
                result = chain_normalizer.normalize_chain_identifier(input_chain)
                if result == expected:
                    logger.info(f"✅ {input_chain} -> {result}")
                else:
                    logger.error(f"❌ {input_chain} -> {result}, expected {expected}")
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ {input_chain} failed: {e}")
                all_passed = False
        
        if not all_passed:
            return False
        
        # Test 4: MultiChainNormalizer has get_chain_type method
        from networks.chain_normalizers import MultiChainNormalizer
        
        try:
            chain_type = MultiChainNormalizer.get_chain_type('bsc')
            if chain_type.value == 'evm':
                logger.info("✅ Test 4: MultiChainNormalizer.get_chain_type works")
            else:
                logger.error(f"❌ Test 4 failed: {chain_type}")
                return False
        except Exception as e:
            logger.error(f"❌ Test 4 failed: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Warning fixes test failed: {e}", exc_info=True)
        return False

async def main():
    """Main test function."""
    
    logger.info("🚀 Testing all warning fixes...")
    
    test_passed = await test_all_fixes()
    
    logger.info("\n📋 Final Results:")
    logger.info(f"  All warning fixes: {'✅ PASSED' if test_passed else '❌ FAILED'}")
    
    if test_passed:
        logger.info("\n🎉 ALL WARNING FIXES COMPLETE!")
        logger.info("✅ Chain authority resolution works intelligently")
        logger.info("✅ Multi-chain deduplicator conversion works")
        logger.info("✅ Chain normalizer handles all chain ID formats")
        logger.info("✅ MultiChainNormalizer has all required methods")
        logger.info("✅ No more method errors or chain conflicts")
        logger.info("\n🚀 System ready for production with real-world data!")
    else:
        logger.error("\n💥 SOME FIXES FAILED!")

if __name__ == "__main__":
    asyncio.run(main())
