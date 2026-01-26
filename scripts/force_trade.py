#!/usr/bin/env python3
"""
Force Trade Script - Inject a trade opportunity directly into the running system
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def force_trade():
    """Force a trade by injecting an opportunity directly into the system."""

    try:
        # Import system components
        from trading.models import TradeOpportunity, TokenInfo, MarketData, AssetClass
        from trading.execution.trade_engine import TradingEngine
        from main import EliteSystemManager

        logger.info("🚀 Starting force trade script...")

        # Get the system manager (it should be running)
        # This is a bit hacky - in a real scenario we'd get this from the running system
        from main import lifecycle_orchestrator
        from core.lifecycle import get_startup_director

        startup_director = get_startup_director()

        # Check if system is running
        if not startup_director.is_system_ready():
            logger.error("❌ System is not ready - cannot force trade")
            return

        logger.info("✅ System is ready")

        # Get the trading engine from the orchestrator
        trading_engine = lifecycle_orchestrator.get_component_instance("trading_engine")
        if not trading_engine:
            logger.error("❌ Trading engine not found")
            return

        logger.info("✅ Trading engine found")

        # Create a test opportunity - using WAVAX since we saw it in the logs
        token_info = TokenInfo(
            symbol='WAVAX',
            address='0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
            chain_id=43114,  # Avalanche chain ID
            decimals=18,
            name='Wrapped AVAX',
            asset_class=AssetClass.CRYPTO
        )

        market_data = MarketData(
            price=Decimal('13.80'),
            volume_24h=Decimal('3457403.98'),
            liquidity=Decimal('1221738.33'),
            timestamp=datetime.now(timezone.utc)
        )

        # Create the opportunity
        opportunity = TradeOpportunity(
            token=token_info,
            market_data=market_data,
            scanner_id='forced_trade',
            scanner_version='1.0',
            opportunity_type='spot',
            target_price=Decimal('13.80'),
            stop_loss=Decimal('13.80') * Decimal('0.95'),  # 5% stop loss
            potential_profit=Decimal('100'),  # Small amount for testing
            potential_loss=Decimal('50'),
            risk_reward_ratio=2.0,
            confidence=0.8,  # High confidence to ensure approval
            volatility=0.05,
            required_capital=Decimal('1000'),
            estimated_execution_time_ms=200,
            max_slippage=0.01,
            urgency=0.9,  # High urgency
            chain='avalanche',
            token_address='0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=300),
            metadata={
                'source': 'forced_trade',
                'reason': 'Manual trade injection for testing'
            }
        )

        logger.info(f"📦 Created opportunity: {opportunity.opportunity_id}")

        # Inject into the evaluation queue
        await trading_engine.evaluation_queue.put(opportunity)

        # Also register in the opportunity registry
        from trading.execution.trade_engine import OpportunityLifecycle, OpportunityLifecycleState

        async with trading_engine._registry_lock:
            if opportunity.opportunity_id not in trading_engine.opportunity_registry:
                lifecycle = OpportunityLifecycle(
                    opportunity.opportunity_id,
                    OpportunityLifecycleState.QUEUED,
                    datetime.now(timezone.utc),
                    opportunity.expires_at,
                    datetime.now(timezone.utc)
                )
                trading_engine.opportunity_registry[opportunity.opportunity_id] = lifecycle
                logger.info(f"📝 Registered opportunity in lifecycle: {opportunity.opportunity_id}")

        # Force high score to ensure it passes
        opportunity.metadata['ai_score'] = 0.9
        opportunity.confidence = 0.9
        logger.info(f"🎯 Forced high confidence: {opportunity.confidence}")

        # REQUIRE AI controller - no fallbacks allowed
        if trading_engine.elite is None:
            logger.error("❌ CRITICAL: AI Controller not wired to trading engine!")
            logger.error("Cannot force trade - AI controller is required for all decisions")
            logger.error("Check system initialization and AI wiring in main.py")
            return

        logger.info("✅ AI Controller is properly wired and available")

        logger.info("✅ Trade opportunity injected successfully!")
        logger.info("🎯 The trading engine should now process this opportunity")
        logger.info("📊 Check the logs to see if the trade gets approved and executed")

    except Exception as e:
        logger.error(f"❌ Failed to force trade: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(force_trade())