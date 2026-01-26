#!/usr/bin/env python3
"""
Test strict token ingestion fixes - no more permissive logic
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_chain_normalizer():
    """Test strict chain normalization."""
    
    logger.info("🧪 Testing strict chain normalization...")
    
    try:
        from networks.chain_normalizer import chain_normalizer
        
        # Test cases
        test_cases = [
            ("bsc", "bsc"),           # String chain ID
            ("56", "bsc"),            # Numeric chain ID  
            ("ethereum", "ethereum"), # String name
            ("1", "ethereum"),        # Numeric ID
            ("blast", "blast"),       # Blast chain
            ("81457", "blast"),       # Blast numeric ID
            ("invalid", "unknown"),   # Invalid chain
        ]
        
        all_passed = True
        for input_chain, expected in test_cases:
            result = chain_normalizer.normalize_chain_identifier(input_chain)
            if result != expected:
                logger.error(f"❌ Chain normalization failed: {input_chain} -> {result}, expected {expected}")
                all_passed = False
            else:
                logger.info(f"✅ {input_chain} -> {result}")
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Chain normalizer test failed: {e}", exc_info=True)
        return False

async def test_address_normalization():
    """Test strict address normalization."""
    
    logger.info("\n🧪 Testing strict address normalization...")
    
    try:
        from networks.chain_normalizers import MultiChainNormalizer
        from networks.multi_chain_models import ChainType
        
        # Valid EVM address on EVM chain
        try:
            result = MultiChainNormalizer.detect_and_normalize(
                "0x1234567890123456789012345678901234567890", 
                "ethereum"
            )
            logger.info(f"✅ Valid EVM address: {result[0]} ({result[1].value})")
        except Exception as e:
            logger.error(f"❌ Valid EVM address failed: {e}")
            return False
        
        # Invalid: Solana address on EVM chain (should reject)
        try:
            result = MultiChainNormalizer.detect_and_normalize(
                "7vfCXTUXx5WdVfa9XqFzDEwMVGQn9hJGKzFmLNMQKv8", 
                "ethereum"
            )
            logger.error(f"❌ Solana address on EVM chain should have been rejected but got: {result}")
            return False
        except ValueError as e:
            logger.info(f"✅ Correctly rejected Solana address on EVM: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Address normalization test failed: {e}", exc_info=True)
        return False

async def test_chain_authority():
    """Test strict chain authority validation."""
    
    logger.info("\n🧪 Testing strict chain authority validation...")
    
    try:
        from trading.token_pipeline.multi_chain_ingestion import MultiChainTokenIngestionPipeline
        
        pipeline = MultiChainTokenIngestionPipeline({"max_queue_size": 1000})
        
        # Test case 1: Consistent chain data (should pass)
        consistent_token = {
            "symbol": "ETH",
            "address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "chain": "bsc",
            "chainId": "bsc",
            "metadata": {
                "dex_data": {
                    "chainId": "bsc"
                }
            }
        }
        
        result = pipeline._assert_chain_authority([consistent_token])
        if len(result) == 1:
            logger.info("✅ Consistent chain data accepted")
        else:
            logger.error(f"❌ Consistent chain data rejected: {result}")
            return False
        
        # Test case 2: Conflicting chain data (should be rejected)
        conflicting_token = {
            "symbol": "ETH", 
            "address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "chain": "ethereum",
            "chainId": "bsc",  # Conflict!
            "metadata": {
                "dex_data": {
                    "chainId": "bsc"
                }
            }
        }
        
        result = pipeline._assert_chain_authority([conflicting_token])
        if len(result) == 0:
            logger.info("✅ Conflicting chain data correctly rejected")
        else:
            logger.error(f"❌ Conflicting chain data should have been rejected: {result}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Chain authority test failed: {e}", exc_info=True)
        return False

async def test_token_deduplicator():
    """Test strict token deduplication."""
    
    logger.info("\n🧪 Testing strict token deduplication...")
    
    try:
        from trading.token_pipeline.token_deduplicator import TokenDeduplicator
        
        deduplicator = TokenDeduplicator()
        
        # Test case: Token with chain mismatch (should be rejected)
        mismatched_token = {
            "symbol": "ETH",
            "address": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "chain": "ethereum",  # Top level says ethereum
            "metadata": {
                "dex_data": {
                    "chainId": "bsc",  # But dex data says bsc
                    "pairAddress": "0x62Fcb3C1794FB95BD8B1A97f6Ad5D8a7e4943a1e"
                }
            }
        }
        
        result = deduplicator.add_tokens([mismatched_token], "test_scanner")
        
        # Should be empty due to chain mismatch rejection
        if len(result) == 0:
            logger.info("✅ Chain mismatched token correctly rejected by deduplicator")
            return True
        else:
            logger.error(f"❌ Chain mismatched token should have been rejected: {len(result)} tokens returned")
            return False
        
    except Exception as e:
        logger.error(f"❌ Token deduplicator test failed: {e}", exc_info=True)
        return False

async def main():
    """Main test function."""
    
    logger.info("🚀 Testing STRICT token ingestion fixes...")
    
    test1_passed = await test_chain_normalizer()
    test2_passed = await test_address_normalization() 
    test3_passed = await test_chain_authority()
    test4_passed = await test_token_deduplicator()
    
    logger.info("\n📋 Final Results:")
    logger.info(f"  Chain normalizer: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    logger.info(f"  Address normalization: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    logger.info(f"  Chain authority: {'✅ PASSED' if test3_passed else '❌ FAILED'}")
    logger.info(f"  Token deduplicator: {'✅ PASSED' if test4_passed else '❌ FAILED'}")
    
    all_passed = test1_passed and test2_passed and test3_passed and test4_passed
    
    if all_passed:
        logger.info("\n🎉 ALL STRICT FIXES PASSED!")
        logger.info("✅ No more permissive fallback logic")
        logger.info("✅ Chain conflicts are rejected instead of overridden")
        logger.info("✅ Address format mismatches are rejected")
        logger.info("✅ System now enforces data integrity")
    else:
        logger.error("\n💥 SOME TESTS FAILED! Fix the remaining issues.")

if __name__ == "__main__":
    asyncio.run(main())
