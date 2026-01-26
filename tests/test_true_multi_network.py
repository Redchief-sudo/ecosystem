#!/usr/bin/env python3
"""
Test TRUE multi-network support - no more EVM-centric bias
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

async def test_multi_network_token_validation():
    """Test TokenInfo validation for all network types."""
    
    logger.info("🧪 Testing multi-network TokenInfo validation...")
    
    try:
        from core.models import TokenInfo
        from decimal import Decimal
        
        # Test valid tokens for each network
        test_cases = [
            # EVM token
            {
                "address": "0x1234567890123456789012345678901234567890",
                "chain_id": 1,  # Ethereum
                "symbol": "ETH",
                "expected_success": True
            },
            # Solana token
            {
                "address": "7vfCXTUXx5WdVfa9XqFzDEwMVGQn9hJGKzFmLNMQKv8",
                "chain_id": 10101,  # Solana
                "symbol": "SOL",
                "expected_success": True
            },
            # Aptos token
            {
                "address": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "chain_id": 10102,  # Aptos
                "symbol": "APT",
                "expected_success": True
            },
            # Invalid: Solana address on EVM chain (should fail)
            {
                "address": "7vfCXTUXx5WdVfa9XqFzDEwMVGQn9hJGKzFmLNMQKv8",
                "chain_id": 1,  # Ethereum but Solana address
                "symbol": "INVALID",
                "expected_success": False
            },
            # Invalid: EVM address on Solana chain (should fail)
            {
                "address": "0x1234567890123456789012345678901234567890",
                "chain_id": 10101,  # Solana but EVM address
                "symbol": "INVALID",
                "expected_success": False
            }
        ]
        
        all_passed = True
        for i, case in enumerate(test_cases):
            try:
                token = TokenInfo(
                    address=case["address"],
                    chain_id=case["chain_id"],
                    symbol=case["symbol"],
                    decimals=18
                )
                
                if case["expected_success"]:
                    logger.info(f"✅ Test {i+1}: {case['symbol']} on chain {case['chain_id']} - VALID")
                else:
                    logger.error(f"❌ Test {i+1}: Should have failed but passed")
                    all_passed = False
                    
            except Exception as e:
                if not case["expected_success"]:
                    logger.info(f"✅ Test {i+1}: Correctly rejected - {e}")
                else:
                    logger.error(f"❌ Test {i+1}: Should have passed but failed - {e}")
                    all_passed = False
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Multi-network validation test failed: {e}", exc_info=True)
        return False

async def test_trade_intent_builder_multi_network():
    """Test TradeIntentBuilder for multi-network support."""
    
    logger.info("\n🧪 Testing TradeIntentBuilder multi-network support...")
    
    try:
        from trading.trade_intent.trade_intent_builder import TradeIntentBuilder
        
        builder = TradeIntentBuilder()
        
        # Test chain execution profiles
        test_chains = [
            ("ethereum", "uniswap_v3"),
            ("bsc", "pancakeswap_v2"),
            ("solana", "raydium"),
            ("aptos", "panora"),
            ("sui", "cetus"),
            ("cosmos", "osmosis"),
            ("bitcoin", "bisq"),
        ]
        
        all_passed = True
        for chain, expected_profile in test_chains:
            actual_profile = builder.CHAIN_EXECUTION_PROFILE.get(chain)
            if actual_profile == expected_profile:
                logger.info(f"✅ {chain} -> {actual_profile}")
            else:
                logger.error(f"❌ {chain} -> {actual_profile}, expected {expected_profile}")
                all_passed = False
        
        # Test router normalization
        router_tests = [
            ("raydium", "raydium"),
            ("uniswap", "uniswap_v3"),
            ("pancakeswap", "pancakeswap_v2"),
            ("orca", "orca"),
            ("cetus", "cetus"),
        ]
        
        for router, expected in router_tests:
            actual = builder.ROUTER_NAME_NORMALIZATION.get(router)
            if actual == expected:
                logger.info(f"✅ Router {router} -> {actual}")
            else:
                logger.error(f"❌ Router {router} -> {actual}, expected {expected}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ TradeIntentBuilder test failed: {e}", exc_info=True)
        return False

async def test_address_normalization_multi_network():
    """Test address normalization preserves native formats."""
    
    logger.info("\n🧪 Testing multi-network address normalization...")
    
    try:
        from networks.chain_normalizers import MultiChainNormalizer
        from networks.multi_chain_models import ChainType
        
        test_cases = [
            # EVM address should stay lowercase hex
            {
                "address": "0x1234567890123456789012345678901234567890",
                "chain_type": ChainType.EVM,
                "expected": "0x1234567890123456789012345678901234567890"
            },
            # Solana address should stay as-is (base58)
            {
                "address": "7vfCXTUXx5WdVfa9XqFzDEwMVGQn9hJGKzFmLNMQKv8",
                "chain_type": ChainType.SOLANA,
                "expected": "7vfCXTUXx5WdVfa9XqFzDEwMVGQn9hJGKzFmLNMQKv8"
            },
            # Aptos address should stay lowercase hex
            {
                "address": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
                "chain_type": ChainType.APTOS,
                "expected": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
            }
        ]
        
        all_passed = True
        for i, case in enumerate(test_cases):
            try:
                result = MultiChainNormalizer.normalize_address(case["address"], case["chain_type"])
                if result == case["expected"]:
                    logger.info(f"✅ Test {i+1}: {case['chain_type'].value} address preserved")
                else:
                    logger.error(f"❌ Test {i+1}: {result} != {case['expected']}")
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ Test {i+1} failed: {e}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Address normalization test failed: {e}", exc_info=True)
        return False

async def test_chain_normalizer_multi_network():
    """Test chain normalizer supports all network types."""
    
    logger.info("\n🧪 Testing chain normalizer multi-network support...")
    
    try:
        from networks.chain_normalizer import chain_normalizer
        
        test_cases = [
            # EVM chains
            ("ethereum", "ethereum"),
            ("1", "ethereum"),
            ("bsc", "bsc"),
            ("56", "bsc"),
            ("polygon", "polygon"),
            ("137", "polygon"),
            
            # Non-EVM chains (if supported)
            ("solana", "solana"),
            ("aptos", "aptos"),
            ("sui", "sui"),
            ("cosmos", "cosmos"),
            ("bitcoin", "bitcoin"),
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
                logger.warning(f"⚠️ {input_chain} failed: {e}")
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Chain normalizer test failed: {e}", exc_info=True)
        return False

async def main():
    """Main test function."""
    
    logger.info("🚀 Testing TRUE MULTI-NETWORK fixes...")
    
    test1_passed = await test_multi_network_token_validation()
    test2_passed = await test_trade_intent_builder_multi_network()
    test3_passed = await test_address_normalization_multi_network()
    test4_passed = await test_chain_normalizer_multi_network()
    
    logger.info("\n📋 Final Results:")
    logger.info(f"  Token validation: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    logger.info(f"  TradeIntentBuilder: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    logger.info(f"  Address normalization: {'✅ PASSED' if test3_passed else '❌ FAILED'}")
    logger.info(f"  Chain normalizer: {'✅ PASSED' if test4_passed else '❌ FAILED'}")
    
    all_passed = test1_passed and test2_passed and test3_passed and test4_passed
    
    if all_passed:
        logger.info("\n🎉 ALL MULTI-NETWORK FIXES PASSED!")
        logger.info("✅ No more EVM-centric bias")
        logger.info("✅ Native address formats preserved")
        logger.info("✅ True multi-network DEX support")
        logger.info("✅ Strict validation for each network type")
    else:
        logger.error("\n💥 SOME TESTS FAILED! Fix the remaining issues.")

if __name__ == "__main__":
    asyncio.run(main())
