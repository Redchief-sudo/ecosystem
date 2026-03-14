"""
End-to-End Paper Trading Test
Tests the complete flow from token discovery to paper trade execution.
"""

import asyncio
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_paper_trading_flow():
    """Test complete paper trading flow"""
    
    logger.info("="*80)
    logger.info("PAPER TRADING END-TO-END TEST")
    logger.info("="*80)
    
    # Import required components
    from config import load_config
    from trading.token_pipeline.token_candidate import TokenCandidate
    from ai.elite_async_ai_controller import EliteAsyncAIController
    from strategies.elite_strategy_manager import EliteStrategyManager
    from strategies.strategy_factory import create_strategies_from_config
    from strategies import registry
    from ai.neural_brain import NeuralBrain
    from trading.execution.trade_engine import TradingEngine
    from trading.execution.trade_executor import HybridTradeExecutor
    from networks.universal_network_manager import UniversalNetworkManager
    from router.hybrid_router_manager import HybridRouterManager
    from datetime import datetime, timezone
    
    # Load config
    config = load_config()
    logger.info(f"✅ Config loaded - Mode: {config.get('mode')}")
    
    # Initialize components
    network_manager = UniversalNetworkManager(config)
    router_manager = HybridRouterManager(network_manager=network_manager, config=config)
    
    # Create strategies
    strategies = create_strategies_from_config(config, registry)
    strategy_manager = EliteStrategyManager(strategies)
    
    # Create AI components
    neural_brain = NeuralBrain(config.get("neural_brain", {}))
    decision_queue = asyncio.Queue(maxsize=1000)
    opportunity_queue = asyncio.Queue(maxsize=1000)
    
    ai_controller = EliteAsyncAIController(
        config=config.get("ai", {}),
        strategy_manager=strategy_manager,
        neural_brain=neural_brain,
        decision_queue=decision_queue,
        opportunity_queue=opportunity_queue,
        data_manager=None
    )
    
    # Initialize AI
    await ai_controller.async_initialize()
    logger.info("✅ AI Controller initialized")
    
    # Create executor
    trade_executor = HybridTradeExecutor(
        config=config,
        network_manager=network_manager,
        hybrid_router_manager=router_manager
    )
    logger.info(f"✅ Trade Executor initialized in {trade_executor.trading_mode.upper()} mode")
    
    # Create trading engine
    trading_engine = TradingEngine(
        config=config,
        ai=ai_controller,
        executor=trade_executor
    )
    await trading_engine.start()
    logger.info("✅ Trading Engine started")
    
    # Create test token candidate
    test_candidate = TokenCandidate(
        address="0x1234567890123456789012345678901234567890",
        symbol="TEST",
        name="Test Token",
        decimals=18,
        chain="ethereum",
        source="test",
        discovered_at=datetime.now(timezone.utc),
        price_usd=1.50,
        volume_24h=100000.0,
        liquidity_usd=50000.0,
        confidence=0.85,
        metadata={
            "price_change_24h": 5.2,
            "volume_change_24h": 15.3,
            "market_cap": 1000000,
        }
    )
    
    logger.info("="*80)
    logger.info("TEST TOKEN CANDIDATE")
    logger.info(f"Symbol: {test_candidate.symbol}")
    logger.info(f"Chain: {test_candidate.chain}")
    logger.info(f"Price: ${test_candidate.price_usd}")
    logger.info(f"Confidence: {test_candidate.confidence}")
    logger.info("="*80)
    
    # Put candidate into decision queue
    await decision_queue.put(test_candidate)
    logger.info("✅ Test candidate added to decision queue")
    
    # Wait for AI to process
    logger.info("⏳ Waiting for AI to process candidate...")
    await asyncio.sleep(2)
    
    # Check if opportunity was created
    if opportunity_queue.qsize() > 0:
        opportunity = await opportunity_queue.get()
        logger.info("="*80)
        logger.info("✅ OPPORTUNITY CREATED")
        logger.info(f"Token: {opportunity.token.symbol}")
        logger.info(f"Chain: {opportunity.chain}")
        logger.info(f"Strategy: {opportunity.metadata.get('strategy_recommendation', {}).get('recommended_strategy_id')}")
        logger.info("="*80)
        
        # Process opportunity through trading engine
        logger.info("⏳ Processing opportunity through trading engine...")
        result = await trading_engine.process_opportunity(opportunity)
        
        logger.info("="*80)
        logger.info("EXECUTION RESULT")
        logger.info(f"Success: {result.get('success')}")
        if result.get('success'):
            logger.info(f"Order ID: {result.get('order_id')}")
            logger.info(f"Executed Amount: {result.get('executed_amount')}")
            logger.info(f"Executed Price: ${result.get('executed_price')}")
            logger.info(f"TX Hash: {result.get('transaction_hash')}")
            logger.info("✅ PAPER TRADE EXECUTED SUCCESSFULLY!")
        else:
            logger.info(f"Rejection Stage: {result.get('rejection_stage')}")
            logger.info(f"Rejection Reason: {result.get('rejection_reason')}")
        logger.info("="*80)
        
        return result.get('success')
    else:
        logger.error("❌ No opportunity created - AI may have rejected the candidate")
        return False
    
    # Cleanup
    await ai_controller.shutdown()
    await trading_engine.stop()


if __name__ == "__main__":
    success = asyncio.run(test_paper_trading_flow())
    if success:
        print("\n" + "="*80)
        print("✅ END-TO-END TEST PASSED - System is executing paper trades!")
        print("="*80)
        exit(0)
    else:
        print("\n" + "="*80)
        print("❌ END-TO-END TEST FAILED - Check logs for details")
        print("="*80)
        exit(1)
