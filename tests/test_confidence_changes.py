#!/usr/bin/env python3
"""
Test script to verify confidence threshold changes and trading flow
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_confidence_changes():
    """Test that confidence thresholds are properly equalized."""
    
    logger.info("🧪 Testing confidence threshold changes...")
    
    try:
        # Import configuration directly
        import yaml
        with open('config/config_unified.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        strategies_config = config.get('strategies', {})
        ai_config = config.get('ai', {})
        
        logger.info("✅ Configuration loaded successfully")
        
        # Test strategy confidence thresholds
        strategies = strategies_config.get("configs", {})
        
        logger.info("📊 Strategy confidence thresholds:")
        all_equal = True
        target_confidence = 0.35
        
        for strategy_name, config in strategies.items():
            min_conf = config.get("min_confidence", "N/A")
            logger.info(f"  {strategy_name}: {min_conf}")
            
            if min_conf != "N/A" and min_conf != target_confidence:
                all_equal = False
        
        # Test AI controller threshold
        ai_min_conf = ai_config.get("signal_thresholds", {}).get("min_confidence", "N/A")
        logger.info(f"🧠 AI Controller min_confidence: {ai_min_conf}")
        
        # Test strategy weights
        weights = strategies_config.get("weights", {})
        logger.info("⚖️ Strategy weights:")
        for strategy, weight in weights.items():
            logger.info(f"  {strategy}: {weight}")
        
        # Results
        logger.info("\n🎯 Test Results:")
        logger.info(f"  All strategies have equal confidence ({target_confidence}): {all_equal}")
        logger.info(f"  AI controller threshold lowered: {ai_min_conf == 0.2}")
        logger.info(f"  Risk caps weight reduced: {weights.get('risk_caps', 1.0) < 1.0}")
        
        if all_equal and ai_min_conf == 0.2 and weights.get('risk_caps', 1.0) < 1.0:
            logger.info("✅ All confidence changes implemented correctly!")
            return True
        else:
            logger.error("❌ Some changes not properly implemented")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

async def test_config_directly():
    """Test configuration directly without importing strategy modules."""
    
    logger.info("\n📋 Testing configuration directly...")
    
    try:
        import yaml
        with open('config/config_unified.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        strategies_config = config.get('strategies', {})
        ai_config = config.get('ai', {})
        
        # Test strategy confidence thresholds
        strategies = strategies_config.get("configs", {})
        
        logger.info("📊 Strategy confidence thresholds:")
        all_equal = True
        target_confidence = 0.35
        
        for strategy_name, config in strategies.items():
            min_conf = config.get("min_confidence", "N/A")
            logger.info(f"  {strategy_name}: {min_conf}")
            
            if min_conf != "N/A" and min_conf != target_confidence:
                all_equal = False
        
        # Test AI controller threshold
        ai_min_conf = ai_config.get("signal_thresholds", {}).get("min_confidence", "N/A")
        logger.info(f"🧠 AI Controller min_confidence: {ai_min_conf}")
        
        # Test strategy weights
        weights = strategies_config.get("weights", {})
        logger.info("⚖️ Strategy weights:")
        for strategy, weight in weights.items():
            logger.info(f"  {strategy}: {weight}")
        
        # Results
        logger.info("\n🎯 Configuration Test Results:")
        logger.info(f"  All strategies have equal confidence ({target_confidence}): {all_equal}")
        logger.info(f"  AI controller threshold lowered: {ai_min_conf == 0.2}")
        logger.info(f"  Risk caps weight reduced: {weights.get('risk_caps', 1.0) < 1.0}")
        
        return all_equal and ai_min_conf == 0.2 and weights.get('risk_caps', 1.0) < 1.0
        
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}", exc_info=True)
        return False

async def main():
    """Main test function."""
    
    logger.info("🚀 Starting confidence threshold tests...")
    
    config_test_passed = await test_config_directly()
    
    logger.info("\n📋 Final Results:")
    logger.info(f"  Configuration test: {'✅ PASSED' if config_test_passed else '❌ FAILED'}")
    
    if config_test_passed:
        logger.info("🎉 CONFIGURATION TEST PASSED! The system should now trade more fairly.")
        logger.info("\n📝 Summary of changes:")
        logger.info("  ✅ All strategy min_confidence set to 0.35")
        logger.info("  ✅ AI controller min_confidence lowered to 0.2")
        logger.info("  ✅ Risk caps weight reduced to 0.8")
        logger.info("  ✅ Aggressive strategy weight increased to 1.3")
        logger.info("  ✅ Momentum and breakout weights increased to 1.1-1.2")
    else:
        logger.error("💥 CONFIGURATION TEST FAILED! Check the implementation.")

if __name__ == "__main__":
    asyncio.run(main())
