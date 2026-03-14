#!/usr/bin/env python3
"""
Test chain authority fixes and warning resolution
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

async def test_chain_authority_fixes():
    """Test that chain authority fixes work properly."""
    
    logger.info("🧪 Testing chain authority fixes...")
    
    try:
        from trading.token_pipeline.multi_chain_ingestion import MultiChainTokenIngestionPipeline
        
        pipeline = MultiChainTokenIngestionPipeline({'max_queue_size': 1000})
        
        # Test case 1: dex_data.chainId overrides conflicting top-level data
        conflict_token = {
            'symbol': 'ETH',
            'address': '0x2170Ed0880ac9A755fd29B2688956BD959F933F8',
            'chain': 'blast',  # Top level says blast
            'chain_id': 81457,  # chain_id says blast
            'metadata': {
                'dex_data': {
                    'chainId': 'bsc'  # But dex_data says bsc (authoritative)
                }
            }
        }
        
        result = pipeline._assert_chain_authority([conflict_token])
        
        if result and result[0]['chain'] == 'bsc' and result[0]['chain_source'] == 'dex_data':
            logger.info("✅ Test 1: dex_data authority override works")
        else:
            logger.error(f"❌ Test 1 failed: {result}")
            return False
        
        # Test case 2: chain_id used when dex_data missing
        no_dex_token = {
            'symbol': 'AVAX',
            'address': '0x1234567890123456789012345678901234567890',
            'chain': 'avalanche',
            'chain_id': 43114,
            'metadata': {}  # No dex_data
        }
        
        result = pipeline._assert_chain_authority([no_dex_token])
        
        if result and result[0]['chain'] == 'avalanche' and result[0]['chain_source'] == 'chain_id':
            logger.info("✅ Test 2: chain_id fallback works")
        else:
            logger.error(f"❌ Test 2 failed: {result}")
            return False
        
        # Test case 3: chain used when others missing
        chain_only_token = {
            'symbol': 'ETH',
            'address': '0x1234567890123456789012345678901234567890',
            'chain': 'ethereum',
            'metadata': {}  # No dex_data or chain_id
        }
        
        result = pipeline._assert_chain_authority([chain_only_token])
        
        if result and result[0]['chain'] == 'ethereum' and result[0]['chain_source'] == 'chain':
            logger.info("✅ Test 3: chain fallback works")
        else:
            logger.error(f"❌ Test 3 failed: {result}")
            return False
        
        # Test case 4: Token with no chain data gets rejected
        no_chain_token = {
            'symbol': 'UNKNOWN',
            'address': '0x1234567890123456789012345678901234567890',
            'metadata': {}  # No chain data at all
        }
        
        result = pipeline._assert_chain_authority([no_chain_token])
        
        if len(result) == 0:
            logger.info("✅ Test 4: No chain data correctly rejected")
        else:
            logger.error(f"❌ Test 4 failed: Should have been rejected")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Chain authority test failed: {e}", exc_info=True)
        return False

async def test_method_fix():
    """Test that the method call fix works."""
    
    logger.info("\n🧪 Testing method call fix...")
    
    try:
        from trading.token_pipeline.multi_chain_ingestion import MultiChainTokenIngestionPipeline
        from networks.chain_normalizer import chain_normalizer
        
        pipeline = MultiChainTokenIngestionPipeline({'max_queue_size': 1000})
        
        # Test that chain_normalizer.normalize_chain_identifier works
        test_cases = [
            ('bsc', 'bsc'),
            ('56', 'bsc'),
            ('ethereum', 'ethereum'),
            ('1', 'ethereum'),
            ('blast', 'blast'),
            ('81457', 'blast'),
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
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Method fix test failed: {e}", exc_info=True)
        return False

async def main():
    """Main test function."""
    
    logger.info("🚀 Testing chain authority and warning fixes...")
    
    test1_passed = await test_chain_authority_fixes()
    test2_passed = await test_method_fix()
    
    logger.info("\n📋 Final Results:")
    logger.info(f"  Chain authority fixes: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    logger.info(f"  Method call fixes: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    all_passed = test1_passed and test2_passed
    
    if all_passed:
        logger.info("\n🎉 ALL WARNING FIXES PASSED!")
        logger.info("✅ Chain authority resolution works intelligently")
        logger.info("✅ Method call errors fixed")
        logger.info("✅ No more false rejections due to data conflicts")
        logger.info("✅ System now handles real-world data inconsistencies")
    else:
        logger.error("\n💥 SOME FIXES FAILED!")

if __name__ == "__main__":
    asyncio.run(main())
