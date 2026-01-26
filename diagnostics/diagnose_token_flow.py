#!/usr/bin/env python3
"""
Diagnostic script to trace token flow and identify why tokens aren't reaching trading
"""

import asyncio
import logging
import os
import sys

# Add the project root to Python path
sys.path.insert(0, '/home/damien/ecosystem')

# Configure logging to see all diagnostic messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

async def diagnose_token_flow():
    """Diagnose why tokens aren't making it to trading"""
    try:
        from datetime import datetime, timedelta, timezone
        from decimal import Decimal

        from ai.elite_ai_controller import (EliteAsyncAIController,
                                            MarketRegime, TradeOpportunity)
        from trading.trade_engine import TradingEngine
        
        print("🔍 Diagnosing token flow from 206 tokens...")
        
        # Create a realistic config
        config = {
            "scanning": {
                "interval": 5,
                "batch_size": 50,
                "max_concurrent": 10
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
        
        # Create mock scan director that returns 206 tokens
        class MockScanDirector:
            def __init__(self):
                self.tokens = self._generate_206_tokens()
            
            def _generate_206_tokens(self):
                """Generate 206 realistic tokens with varying quality"""
                tokens = []
                base_symbols = ["ETH", "BTC", "ADA", "DOT", "LINK", "UNI", "AAVE", "SUSHI", "COMP", "MKR"]
                
                for i in range(206):
                    # Vary the quality of tokens
                    if i < 50:  # High quality tokens
                        price = 1000 + (i * 10)
                        volume = 1000000 + (i * 10000)
                        liquidity = 500000 + (i * 5000)
                        confidence = 0.7 + (i * 0.006)
                    elif i < 150:  # Medium quality tokens
                        price = 100 + (i * 2)
                        volume = 100000 + (i * 1000)
                        liquidity = 50000 + (i * 500)
                        confidence = 0.4 + (i * 0.002)
                    else:  # Low quality tokens
                        price = 0.01 + (i * 0.001)
                        volume = 1000 + (i * 10)
                        liquidity = 500 + (i * 5)
                        confidence = 0.1 + (i * 0.001)
                    
                    # Some tokens have missing/invalid data
                    if i % 20 == 0:  # 5% have missing address
                        token_address = ""
                    elif i % 25 == 0:  # 4% have zero price
                        price = 0.0
                    else:
                        token_address = f"0x{i:040x}"
                    
                    symbol = f"{base_symbols[i % len(base_symbols)]}{i}"
                    
                    tokens.append({
                        "symbol": symbol,
                        "token_address": token_address,
                        "chain": "ethereum",
                        "price": price,
                        "volume_24h": volume,
                        "liquidity_usd": liquidity,
                        "market_cap": volume * 10,
                        "volatility": 0.05 + (i * 0.0001),
                        "confidence": confidence
                    })
                
                return tokens
            
            async def scan_all(self):
                print(f"📊 MockScanDirector: Returning {len(self.tokens)} tokens")
                return self.tokens
        
        # Create mock AI controller
        class MockEliteAI:
            def __init__(self):
                self.strategies = {"test_strategy": {"name": "Test Strategy"}}
                self.current_regime = MarketRegime.SIDEWAYS
                self.active_positions = {}
                self.decision_count = 0
            
            async def get_portfolio_value(self):
                return 100000.0
            
            async def recommend_strategy(self, opportunity):
                self.decision_count += 1
                
                # Log every 10th decision to track progress
                if self.decision_count % 10 == 0:
                    print(f"🧠 AI Decision #{self.decision_count}: {opportunity.token_symbol}")
                
                # Simulate realistic decision making
                confidence = opportunity.confidence
                
                # Reject low confidence opportunities
                if confidence < 0.5:
                    class MockRecommendation:
                        def __init__(self):
                            self.recommended_strategy_id = "SKIP"
                            self.recommended_strategy_name = "Skip"
                            self.position_size = 0
                            self.confidence = confidence
                            self.expected_risk = 1.0
                            self.key_factors = [f"Low confidence: {confidence:.2f}"]
                    return MockRecommendation()
                
                # Approve high confidence opportunities
                class MockRecommendation:
                    def __init__(self):
                        self.recommended_strategy_id = "test_strategy"
                        self.recommended_strategy_name = "Test Strategy"
                        self.position_size = 100.0
                        self.confidence = confidence
                        self.expected_risk = 0.5
                        self.key_factors = [f"Good confidence: {confidence:.2f}"]
                
                return MockRecommendation()
        
        class MockTradeExecutor:
            def __init__(self):
                self.execution_count = 0
            
            async def execute(self, plan):
                self.execution_count += 1
                print(f"⚡ EXECUTION #{self.execution_count}: {plan.token_address[:10]}... Amount: ${plan.amount}")
                
                class MockResult:
                    def __init__(self):
                        self.success = True
                        self.transaction_hash = f"0x{self.execution_count:040x}"
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
        
        # Create components
        scan_director = MockScanDirector()
        elite_ai = MockEliteAI()
        trade_executor = MockTradeExecutor()
        trade_optimizer = MockTradeOptimizer()
        
        print("✅ Components created")
        
        # Create trading engine
        trading_engine = TradingEngine(
            scan_director=scan_director,
            elite_ai_controller=elite_ai,
            trade_executor=trade_executor,
            trade_optimizer=trade_optimizer,
            config=config
        )
        
        print("✅ Trading engine created")
        
        # Initialize the engine
        print("🔄 Initializing trading engine...")
        await trading_engine.start()
        
        # Stop background tasks to focus on single cycle
        trading_engine.is_running = False
        await asyncio.sleep(0.1)
        
        print("✅ Trading engine initialized")
        
        # Run a single cycle and track each step
        print("\n" + "="*80)
        print("🔄 RUNNING SINGLE TRADING CYCLE WITH 206 TOKENS")
        print("="*80)
        
        await trading_engine._run_cycle()
        
        print("\n" + "="*80)
        print("📊 CYCLE RESULTS ANALYSIS")
        print("="*80)
        
        # Analyze results at each stage
        print(f"🔍 STEP 1 - SCAN: {len(scan_director.tokens)} tokens found")
        
        # Check normalization results
        tokens = trading_engine._flatten_scan_results(scan_director.tokens)
        print(f"🔍 STEP 2 - FLATTEN: {len(tokens)} tokens flattened")
        
        # Check opportunity registry
        registry_size = len(trading_engine.opportunity_registry)
        print(f"🔍 STEP 3 - REGISTRY: {registry_size} opportunities in registry")
        
        # Check queue sizes
        eval_queue_size = trading_engine.evaluation_queue.qsize()
        opt_queue_size = trading_engine.optimization_queue.qsize()
        exec_queue_size = trading_engine.execution_queue.qsize()
        
        print(f"🔍 STEP 4 - QUEUES:")
        print(f"   Evaluation Queue: {eval_queue_size}")
        print(f"   Optimization Queue: {opt_queue_size}")
        print(f"   Execution Queue: {exec_queue_size}")
        
        # Process queued items to see where they get stuck
        print(f"\n🔄 Processing {eval_queue_size} items from evaluation queue...")
        
        decisions_made = 0
        approvals = 0
        rejections = 0
        
        for i in range(eval_queue_size):
            try:
                opportunity = await asyncio.wait_for(
                    trading_engine.evaluation_queue.get(),
                    timeout=1.0
                )
                decisions_made += 1
                
                decision = await trading_engine._request_elite_decision(opportunity)
                
                if decision.outcome.value == "approved":
                    approvals += 1
                    print(f"✅ APPROVED: {opportunity.token_symbol} (Confidence: {decision.confidence:.2%})")
                else:
                    rejections += 1
                    print(f"📊 Decision: {decision.outcome.value} - {decision.reasoning}")
                
            except asyncio.TimeoutError:
                break
            except Exception as e:
                print(f"❌ ERROR processing opportunity: {e}")
        
        print(f"\n📊 DECISION SUMMARY:")
        print(f"   Total Decisions: {decisions_made}")
        print(f"   Approved: {approvals}")
        print(f"   Rejected: {rejections}")
        print(f"   Approval Rate: {(approvals/decisions_made*100):.1f}%" if decisions_made > 0 else "   Approval Rate: N/A")
        
        # Check execution results
        print(f"\n⚡ EXECUTION RESULTS: {trade_executor.execution_count} trades executed")
        
        # Check ingestion pipeline metrics
        if trading_engine.ingestion_pipeline:
            metrics = trading_engine.ingestion_pipeline.get_metrics()
            print(f"\n📊 INGESTION PIPELINE METRICS:")
            print(f"   Total Ingested: {metrics['total_ingested']}")
            print(f"   Total Enqueued: {metrics['total_enqueued']}")
            print(f"   Total Rejected: {metrics['total_rejected']}")
            print(f"   Acceptance Rate: {metrics['acceptance_rate']:.1%}")
        
        print("\n✅ Token flow diagnosis completed")
        
    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(diagnose_token_flow())
