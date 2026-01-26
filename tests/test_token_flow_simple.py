#!/usr/bin/env python3
"""
Simple test script to check token normalization and queue flow
"""

import asyncio
import logging
import os
import sys

# Add the project root to Python path
sys.path.insert(0, '/home/damien/ecosystem')

# Configure logging to see all diagnostic messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

async def test_token_normalization():
    """Test token normalization and queue flow without network dependencies"""
    try:
        # Import here to avoid path issues
        from trading.trade_engine import TradingEngine
        
        print("🔍 Testing token normalization and queue flow...")
        
        # Create a minimal config
        config = {
            "scanning": {
                "interval": 10,
                "batch_size": 10,
                "max_concurrent": 5
            },
            "trading": {
                "risk_reward_ratio": 2.0,
                "expected_duration_hours": 24.0,
                "underwater_threshold_pct": 20.0
            },
            "risk": {
                "max_drawdown_pct": 15.0,
                "max_position_age_hours": 72
            },
            "ai": {
                "ai_score_threshold": 0.4,
                "min_liquidity_usd": 100,
                "min_volume_usd": 100
            },
            "circuit_breaker": {
                "failure_threshold": 5,
                "timeout_seconds": 60
            }
        }
        
        # Create mock scan director that returns sample tokens
        class MockScanDirector:
            async def scan_all(self):
                # Return sample tokens that scanners would typically produce
                return [
                    {
                        "symbol": "ETH",
                        "token_address": "0x1234567890123456789012345678901234567890",
                        "chain": "ethereum",
                        "price": 2500.0,
                        "volume_24h": 1000000.0,
                        "liquidity_usd": 500000.0,
                        "market_cap": 300000000.0,
                        "volatility": 0.05,
                        "confidence": 0.8
                    },
                    {
                        "symbol": "BTC",
                        "token_address": "0x0987654321098765432109876543210987654321",
                        "chain": "ethereum",
                        "price": 45000.0,
                        "volume_24h": 2000000.0,
                        "liquidity_usd": 1000000.0,
                        "market_cap": 800000000.0,
                        "volatility": 0.04,
                        "confidence": 0.9
                    },
                    {
                        "symbol": "INVALID",
                        "token_address": "",  # Missing address - should be filtered out
                        "chain": "ethereum",
                        "price": 0.0,  # Invalid price - should be filtered out
                        "volume_24h": 100.0,
                        "liquidity_usd": 50.0,
                        "market_cap": 1000.0,
                        "volatility": 0.1,
                        "confidence": 0.3
                    }
                ]
        
        # Create mock components for testing
        class MockEliteAI:
            def __init__(self):
                self.strategies = {"test_strategy": {"name": "Test Strategy"}}
                self.current_regime = "SIDEWAYS"
                self.active_positions = {}
            
            async def get_portfolio_value(self):
                return 100000.0
            
            async def recommend_strategy(self, opportunity):
                # Always return a recommendation for testing
                class MockRecommendation:
                    def __init__(self):
                        self.recommended_strategy_id = "test_strategy"
                        self.recommended_strategy_name = "Test Strategy"
                        self.position_size = 100.0
                        self.confidence = 0.8
                        self.expected_risk = 0.5
                        self.key_factors = ["Test factor"]
                
                return MockRecommendation()
        
        class MockTradeExecutor:
            async def execute(self, plan):
                class MockResult:
                    def __init__(self):
                        self.success = True
                        self.transaction_hash = "0x123"
                        self.executed_price = plan.target_price
                        self.executed_amount = plan.amount
                        self.gas_used = 0.001
                        self.slippage = 0.01
                        self.execution_time_ms = 1000.0
                return MockResult()
        
        class MockTradeOptimizer:
            async def create_execution_plan(self, **kwargs):
                class MockPlan:
                    def __init__(self, **kwargs):
                        self.token_address = kwargs.get('token_address')
                        self.chain = kwargs.get('chain')
                        self.amount = kwargs.get('amount')
                        self.is_buy = kwargs.get('is_buy')
                        self.target_price = kwargs.get('target_price')
                        self.max_slippage = kwargs.get('max_slippage')
                        self.gas_strategy = "normal"
                        self.retry_strategy = {"max_attempts": 3}
                        self.timeout_ms = 30000
                        self.strategy_id = "test_strategy"
                        self.strategy_name = "Test Strategy"
                        self.decision_id = "test_decision"
                return MockPlan(**kwargs)
        
        # Create trading engine
        trading_engine = TradingEngine(
            scan_director=MockScanDirector(),
            elite_ai_controller=MockEliteAI(),
            trade_executor=MockTradeExecutor(),
            trade_optimizer=MockTradeOptimizer(),
            config=config
        )
        
        print("✅ Trading engine created successfully")
        
        # Initialize the engine properly (this sets up ingestion pipeline)
        print("🔄 Initializing trading engine...")
        await trading_engine.start()
        
        # Stop the engine immediately after initialization to prevent background tasks
        # We'll manually run the cycle for testing
        trading_engine.is_running = False
        await asyncio.sleep(0.1)  # Let background tasks finish
        
        print("✅ Trading engine initialized")
        
        # Run a single cycle to test token flow
        print("🔄 Running single trading cycle...")
        await trading_engine._run_cycle()
        
        print("✅ Single cycle completed")
        
        # Check queue status
        queue_size = trading_engine.evaluation_queue.qsize()
        print(f"📊 Evaluation queue size: {queue_size}")
        
        registry_size = len(trading_engine.opportunity_registry)
        print(f"📊 Opportunity registry size: {registry_size}")
        
        if trading_engine.ingestion_pipeline:
            metrics = trading_engine.ingestion_pipeline.get_metrics()
            print(f"📊 Ingestion pipeline metrics: {metrics}")
        
        # Test decision processor by processing queued items
        print("🔄 Testing decision processor...")
        for i in range(queue_size):
            try:
                opportunity = await asyncio.wait_for(
                    trading_engine.evaluation_queue.get(),
                    timeout=1.0
                )
                print(f"📊 Retrieved opportunity: {opportunity.token_symbol}")
                
                # Get decision
                decision = await trading_engine._request_elite_decision(opportunity)
                print(f"📊 Decision: {decision.outcome.value} - {decision.reasoning}")
                
            except asyncio.TimeoutError:
                print("📊 Queue empty")
                break
        
        print("✅ Token flow test completed successfully")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_token_normalization())
