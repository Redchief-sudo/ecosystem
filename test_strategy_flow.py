#!/usr/bin/env python3
"""
Minimal test to see if strategies generate signals with pre-enriched data.
"""
import asyncio
import logging
import sys
sys.path.insert(0, "/home/damien/ecosystem")

from core.models import TradeOpportunity, TokenInfo, MarketData, AssetClass
from strategies.elite_strategy_manager import EliteStrategyManager
from ai.elite_async_ai_controller import EliteAsyncAIController

logging.basicConfig(level=logging.DEBUG, format='%(name)s | %(message)s')
logger = logging.getLogger(__name__)

async def test_strategy_execution():
    """Test if strategies generate signals"""
    
    # Create strategy manager
    from config.config_validator import ConfigValidator
    validator = ConfigValidator()
    config = validator.load_and_validate_config("/home/damien/ecosystem/config/config_unified.yaml")
    
    # Build strategies from config and registry
    from strategies import registry
    from strategies.strategy_factory import create_strategies_from_config

    strategies = create_strategies_from_config(config, registry)
    strategy_manager = EliteStrategyManager(strategies)
    
    # Create a simple market data dict (like what pre-enrichment would create)
    market_data = {
        "price": 100.0,
        "volume_24h": 1000000,
        "liquidity": 5000000,
        "symbol": "TEST",
        "chain": "solana",
        # Pre-enriched fields
        "rsi": 50.0,
        "macd": 0.0,
        "macd_signal": 0.0,
        "volatility": 0.15,
        "price_change_1h": 0.0,
        "price_change_24h": 0.0,
        "price_change_7d": 0.0,
        "market_cap": 50000000,
        "liquidity_score": 1.0,
        "rugpull_risk": 0.2,
    }
    
    logger.info(f"Testing strategy execution with market_data keys: {list(market_data.keys())}")
    logger.info(f"Market data: {market_data}")
    
    # Execute strategies
    results = await strategy_manager.execute_strategies_parallel(market_data)
    
    logger.info(f"\n=== STRATEGY RESULTS ===")
    logger.info(f"Total strategies executed: {len(results)}")
    
    for r in results:
        logger.info(f"\nStrategy: {r.strategy_id}")
        logger.info(f"  Success: {r.success}")
        logger.info(f"  Signal: {r.signal}")
        if r.error:
            logger.info(f"  Error: {r.error}")
    
    valid = [r for r in results if r.success and r.signal]
    logger.info(f"\n=== SUMMARY ===")
    logger.info(f"Valid signals: {len(valid)} out of {len(results)}")
    
    if not valid:
        logger.error("NO VALID SIGNALS GENERATED - STRATEGIES ARE NOT WORKING")
    else:
        logger.info("✅ Strategies generated signals!")

if __name__ == "__main__":
    asyncio.run(test_strategy_execution())
