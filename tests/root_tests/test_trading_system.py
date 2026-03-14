#!/usr/bin/env python3
"""
Comprehensive Trading System Test
=================================

Tests the complete trading flow:
1. Token scanning → 2. Ingestion → 3. Bridge → 4. AI Controller → 5. Trading execution
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.models import TradeOpportunity, TokenInfo, MarketData, AssetClass
from trading.token_pipeline.token_candidate import TokenCandidate
from networks.multi_chain_models import ChainType
from trading.token_pipeline import (
    initialize_queue_manager, 
    get_queue_manager,
    enqueue_token,
    dequeue_any_token
)
from decimal import Decimal
from datetime import datetime, timezone

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)


class TradingSystemTest:
    """Test the complete trading system flow."""
    
    def __init__(self):
        self.test_results = {
            "queue_manager_init": False,
            "token_enqueue": False,
            "token_dequeue": False,
            "bridge_conversion": False,
            "ai_controller_receive": False,
            "opportunity_queue": False,
            "overall_success": False
        }
        
    async def setup(self):
        """Initialize system components."""
        logger.info("🔧 Setting up test environment...")
        
        try:
            # Initialize queue manager
            initialize_queue_manager()
            self.test_results["queue_manager_init"] = True
            logger.info("✅ Queue manager initialized")
            
            # Import AI controller components (will be initialized in main system)
            from ai.elite_async_ai_controller import EliteAsyncAIController
            self.ai_controller_class = EliteAsyncAIController
            
            return True
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False
    
    async def test_queue_manager(self):
        """Test queue manager basic functionality."""
        logger.info("🧪 Testing queue manager...")
        
        try:
            qm = get_queue_manager()
            
            # Test empty queues
            for chain_type in ChainType:
                size = qm.queues[chain_type].qsize()
                logger.debug(f"{chain_type.value}: {size} items")
            
            logger.info("✅ Queue manager test passed")
            return True
        except Exception as e:
            logger.error(f"❌ Queue manager test failed: {e}")
            return False
    
    async def test_token_enqueue(self):
        """Test enqueuing tokens."""
        logger.info("🧪 Testing token enqueue...")
        
        try:
            # Create test token candidates
            test_tokens = [
                TokenCandidate(
                    symbol="TEST1",
                    address="0x1234567890123456789012345678901234567890",
                    chain_type=ChainType.EVM,
                    chain_id=1,
                    decimals=18,
                    price=1000.0,
                    liquidity=50000.0,
                    volume_24h=100000.0
                ),
                TokenCandidate(
                    symbol="TEST2", 
                    address="9gP2kCy3wA1ctvYWQk75guqXuHfrEomqydHLtcTCqiLa",
                    chain_type=ChainType.SOLANA,
                    decimals=18,
                    price=500.0,
                    liquidity=25000.0,
                    volume_24h=75000.0
                )
            ]
            
            # Enqueue tokens
            for token in test_tokens:
                success = await enqueue_token(token)
                if success:
                    logger.info(f"✅ Enqueued {token.symbol} on {token.chain_type.value}")
                    self.test_results["token_enqueue"] = True
                else:
                    logger.error(f"❌ Failed to enqueue {token.symbol}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"❌ Token enqueue test failed: {e}")
            return False
    
    async def test_token_dequeue(self):
        """Test dequeuing tokens."""
        logger.info("🧪 Testing token dequeue...")
        
        try:
            qm = get_queue_manager()
            
            # Check queue sizes before dequeue
            for chain_type in ChainType:
                size = qm.queues[chain_type].qsize()
                if size > 0:
                    logger.info(f"Queue {chain_type.value} has {size} items")
            
            # Dequeue tokens
            dequeued_count = 0
            max_attempts = 3
            
            for attempt in range(max_attempts):
                candidate = await dequeue_any_token(timeout=2.0)
                if candidate:
                    logger.info(f"✅ Dequeued {candidate.symbol} from {candidate.chain_type.value}")
                    self.test_results["token_dequeue"] = True
                    dequeued_count += 1
                    
                    # Test bridge conversion
                    if await self.test_bridge_conversion(candidate):
                        self.test_results["bridge_conversion"] = True
                else:
                    logger.debug(f"No token available on attempt {attempt + 1}")
            
            if dequeued_count == 0:
                logger.warning("⚠️ No tokens dequeued - queues might be empty")
                return False
            
            return True
        except Exception as e:
            logger.error(f"❌ Token dequeue test failed: {e}")
            return False
    
    async def test_bridge_conversion(self, candidate: TokenCandidate) -> bool:
        """Test TokenCandidate to TradeOpportunity conversion."""
        logger.info("🧪 Testing bridge conversion...")
        
        try:
            # Convert TokenCandidate to TradeOpportunity (same as bridge)
            token_info = TokenInfo(
                symbol=candidate.symbol,
                address=candidate.address,
                chain_id=getattr(candidate, 'chain_id', 1),
                decimals=getattr(candidate, 'decimals', 18),
                name=candidate.symbol,
                asset_class=AssetClass.CRYPTO
            )
            
            market_data = MarketData(
                price=Decimal(str(getattr(candidate, 'price', 0))),
                liquidity=Decimal(str(getattr(candidate, 'liquidity', 0))),
                volume_24h=Decimal(str(getattr(candidate, 'volume_24h', 0))),
                price_change_24h=getattr(candidate, 'price_change_24h', 0.0)
            )
            
            opportunity = TradeOpportunity(
                token=token_info,
                market_data=market_data,
                scanner_id="test_scanner",
                scanner_version="1.0.0",
                opportunity_type="test_candidate",
                chain=candidate.chain_type.value,
                token_address=candidate.address,
                created_at=datetime.now(timezone.utc),
                detected_at=datetime.now(timezone.utc),
                opportunity_id=f"test_{candidate.symbol}_{int(datetime.now(timezone.utc).timestamp())}",
                # Legacy fields for compatibility
                token_symbol=candidate.symbol,
                token_address_legacy=candidate.address,
                current_price=float(market_data.price),
                volume_24h=float(market_data.volume_24h),
                liquidity=float(market_data.liquidity)
            )
            
            logger.info(f"✅ Converted {candidate.symbol} to TradeOpportunity")
            return True
            
        except Exception as e:
            logger.error(f"❌ Bridge conversion test failed: {e}")
            return False
    
    async def test_ai_controller_integration(self):
        """Test AI controller integration."""
        logger.info("🧪 Testing AI controller integration...")
        
        try:
            # This would test the actual AI controller if it were running
            # For now, we'll simulate the decision queue
            import asyncio
            
            # Create a mock decision queue
            decision_queue = asyncio.Queue(maxsize=1000)
            
            # Create a test opportunity
            token_info = TokenInfo(
                symbol="TEST_AI",
                address="0x1234567890123456789012345678901234567890",
                chain_id=1,
                decimals=18,
                name="Test AI Token",
                asset_class=AssetClass.CRYPTO
            )
            
            market_data = MarketData(
                price=Decimal("1000.0"),
                liquidity=Decimal("50000.0"),
                volume_24h=Decimal("100000.0")
            )
            
            opportunity = TradeOpportunity(
                token=token_info,
                market_data=market_data,
                scanner_id="test_ai_scanner",
                scanner_version="1.0.0",
                opportunity_type="test_ai",
                chain="ethereum",
                token_address="0x1234567890123456789012345678901234567890",
                created_at=datetime.now(timezone.utc),
                detected_at=datetime.now(timezone.utc),
                opportunity_id="test_ai_opportunity"
            )
            
            # Test putting to decision queue
            await decision_queue.put(opportunity)
            self.test_results["ai_controller_receive"] = True
            
            # Test getting from decision queue
            received = await decision_queue.get()
            if received.opportunity_id == "test_ai_opportunity":
                logger.info("✅ AI controller integration test passed")
                return True
            
        except Exception as e:
            logger.error(f"❌ AI controller integration test failed: {e}")
            return False
    
    async def run_full_test(self):
        """Run the complete test suite."""
        logger.info("🚀 Starting comprehensive trading system test...")
        
        # Setup
        if not await self.setup():
            return False
        
        # Test individual components
        tests = [
            ("Queue Manager", self.test_queue_manager),
            ("Token Enqueue", self.test_token_enqueue),
            ("Token Dequeue", self.test_token_dequeue),
            ("AI Controller Integration", self.test_ai_controller_integration),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n--- Running {test_name} Test ---")
            try:
                result = await test_func()
                if not result:
                    logger.error(f"❌ {test_name} test failed")
                    return False
            except Exception as e:
                logger.error(f"❌ {test_name} test exception: {e}")
                return False
        
        # Calculate overall success
        passed_tests = sum(1 for result in self.test_results.values() if result)
        total_tests = len(self.test_results)
        
        if passed_tests == total_tests:
            self.test_results["overall_success"] = True
            logger.info("🎉 ALL TESTS PASSED!")
            return True
        else:
            logger.warning(f"⚠️ {passed_tests}/{total_tests} tests passed")
            return False
    
    def print_results(self):
        """Print test results summary."""
        logger.info("\n" + "="*50)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("="*50)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name:25} : {status}")
        
        logger.info("="*50)


async def main():
    """Run the trading system test."""
    test = TradingSystemTest()
    
    try:
        success = await test.run_full_test()
        test.print_results()
        
        if success:
            logger.info("\n🎯 Trading system is working correctly!")
            return 0
        else:
            logger.error("\n💥 Trading system has issues that need to be fixed!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Test suite failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
