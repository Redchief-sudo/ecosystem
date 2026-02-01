import asyncio
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.elite_async_ai_controller import (EliteAsyncAIController, MarketRegime,
                                          SelectionMethod, StrategyType)
from trading.models import (AssetClass, DecisionOutcome, MarketData, OrderSide,
                            OrderType, StrategyDecision, TimeInForce,
                            TokenInfo, TradeOpportunity)
from trading.execution.trade_engine import TradingEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class MockTradeExecutor:
    async def execute_trade(self, *args, **kwargs):
        return {"status": "success", "order_id": "MOCK_ORDER_123"}

class MockScanDirector:
    async def scan_markets(self):
        # Generate test tokens
        return [
            {
                "symbol": f"GOOD_{i}",
                "price": 10.0 + i,
                "volume_24h": 1000000 * (i + 1),
                "liquidity": 500000 * (i + 1),
                "token_address": f"0x{'a' * 40}",
                "chain_id": 1
            } for i in range(5)
        ] + [
            {
                "symbol": f"BAD_{i}",
                "price": 1.0,
                "volume_24h": 1000,
                "liquidity": 500,
                "token_address": f"0x{'b' * 40}",
                "chain_id": 1
            } for i in range(3)
        ]

async def create_test_ai_controller():
    """Create a test instance of EliteAsyncAIController with test configurations."""
    test_config = {
        "primary_method": SelectionMethod.ENSEMBLE,
        "exploration_rate": 0.1,
        "ensemble_size": 3,
        "min_strategy_weight": 0.1,
        "rebalance_interval": 100,
        "min_trades_for_inclusion": 5,
        "min_win_rate": 0.5,
        "min_sharpe_ratio": 0.3,
        "max_drawdown": 0.5,
        "max_strategies_per_trade": 1,
        "position_sizing_method": "kelly",
        "max_position_size_pct": 0.1,
        "regime_detection_window": 20,
        "performance_decay_factor": 0.9,
        "health_check_interval": 10,
        "auto_disable_poor_strategies": True,
        "quarantine_threshold_drawdown": 0.5
    }
    
    # Initialize controller with test config
    controller = EliteAsyncAIController(
        config=test_config,
        total_capital=Decimal('10000.0')
    )
    
    # Register test strategies
    test_strategies = [
        ("test_momentum", "Test Momentum Strategy", StrategyType.MOMENTUM),
        ("test_reversion", "Test Mean Reversion", StrategyType.MEAN_REVERSION),
        ("test_breakout", "Test Breakout", StrategyType.BREAKOUT)
    ]
    
    for strat_id, name, strat_type in test_strategies:
        await controller.register_strategy_async(
            strategy_id=strat_id,
            strategy_name=name,
            strategy_type=strat_type
        )
        
        # Add some performance metrics
        if hasattr(controller, 'strategy_history') and strat_id in controller.strategy_history:
            # Add some sample trade results
            for _ in range(5):
                profit = Decimal('100') + Decimal(str(random.uniform(-20, 50)))
                controller.strategy_history[strat_id].append(profit)
    
    return controller

async def test_decision_flow():
    """Test the complete decision flow using the real EliteAsyncAIController."""
    print("\n=== Starting Decision Flow Test ===\n")
    
    try:
        # Create and initialize test AI controller
        print("Initializing EliteAsyncAIController...")
        ai_controller = await create_test_ai_controller()
        
        # Initialize the controller if not already done
        if not hasattr(ai_controller, '_initialized') or not ai_controller._initialized:
            print("Initializing controller...")
            await ai_controller.async_initialize()
        
        # Create test opportunities
        print("\n=== Generating Test Opportunities ===")
        test_opportunities = []
        current_time = datetime.now(timezone.utc)
        
        for i in range(3):
            symbol = f"TEST_{i}"
            price = Decimal('100.0') + (Decimal('10.0') * i)
            
            # Create token info
            token = TokenInfo(
                symbol=symbol,
                address=f"0x{'a' * 40}",
                chain_id=1,
                name=f"Test Token {i}",
                asset_class=AssetClass.CRYPTO
            )
            
            # Create market data
            market_data = MarketData(
                price=price,
                volume_24h=Decimal('1000000') * (i + 1),
                liquidity=Decimal('500000') * (i + 1)
            )
            
            # Create metadata with technical indicators and other fields
            metadata = {
                "opportunity_type": "test",
                "target_price": float(price * Decimal('1.1')),  # 10% target
                "stop_loss": float(price * Decimal('0.95')),    # 5% stop loss
                "potential_profit": float(price * Decimal('0.1')),  # 10% profit potential
                "potential_loss": float(price * Decimal('0.05')),   # 5% risk
                "risk_reward_ratio": 2.0,  # 2:1 reward/risk
                "confidence": float(0.7 + (i * 0.1)),
                "volatility": float(0.05 + (i * 0.02)),
                "market_regime": "bull_trending",
                "required_capital": 1000.0,
                "estimated_execution_time_ms": 50.0,
                "max_slippage": 0.001,
                "urgency": 0.7,
                "detected_at": current_time.isoformat(),
                "technical_indicators": {
                    "rsi": 60.0 - (i * 5.0),  # Vary RSI
                    "macd": 0.01 * (i + 1),
                    "bb_width": 0.1 - (i * 0.02)
                },
                "market_sentiment": 0.6 + (i * 0.1)  # Vary sentiment
            }
            
            # Create the opportunity with the correct structure
            opportunity = TradeOpportunity(
                token=token,
                market_data=market_data,
                scanner_id="test_scanner",
                scanner_version="1.0",
                metadata=metadata,
                expires_at=current_time + timedelta(minutes=5)
            )
            test_opportunities.append(opportunity)
        
        # Test decision making
        print("\n=== Testing AI Decisions ===")
        for i, opportunity in enumerate(test_opportunities):
            print(f"\n--- Testing Opportunity {i+1} ---")
            print(f"Symbol: {opportunity.token.symbol}")
            print(f"Price: ${opportunity.market_data.price}")
            print(f"Volume (24h): ${opportunity.market_data.volume_24h:,.2f}")
            print(f"Expires at: {opportunity.expires_at}")
            print(f"Type: {opportunity.metadata.get('opportunity_type', 'N/A')}")
            print(f"Confidence: {opportunity.metadata.get('confidence', 0):.1%}")
            print(f"Market Regime: {opportunity.metadata.get('market_regime', 'N/A')}")
            
            # Get strategy recommendation
            print("\nGetting strategy recommendation...")
            try:
                # Use canonical TradeOpportunity directly
                recommendation = await ai_controller.select_strategy(opportunity)
                
                # Basic assertions
                assert recommendation is not None, "Recommendation should not be None"
                assert recommendation.confidence > 0, "Confidence should be positive"
                assert recommendation.recommended_strategy_name, "Strategy name should not be empty"
                assert recommendation.selection_method in SelectionMethod, "Invalid selection method"
                
                # Log detailed decision info
                print("\n=== Recommendation ===")
                print(f"Strategy: {recommendation.recommended_strategy_name}")
                print(f"Confidence: {recommendation.confidence:.1%}")
                print(f"Position Size: ${recommendation.position_size:,.2f}")
                print(f"Selection Method: {recommendation.selection_method.value}")
                
                # Log ensemble weights if available
                if recommendation.ensemble_strategies:
                    print("\nEnsemble Weights:")
                    for strategy_id, weight in recommendation.ensemble_strategies:
                        print(f"  - {strategy_id}: {weight:.1%}")
                    
                    # Verify weights sum to ~1.0 (allowing for floating point errors)
                    total_weight = sum(w for _, w in recommendation.ensemble_strategies)
                    assert abs(1.0 - total_weight) < 1e-6, f"Weights should sum to 1.0, got {total_weight}"
                
                print(f"\nKey Factors: {', '.join(recommendation.key_factors) if recommendation.key_factors else 'None'}")
                
                if recommendation.ensemble_strategies:
                    print("\nEnsemble Strategies:")
                    for strat, weight in recommendation.ensemble_strategies:
                        print(f"  - {strat}: {weight:.1%}")
                
                # Simulate trade execution
                if recommendation.recommended_strategy_id != "skip":
                    print("\nSimulating trade execution...")
                    # In a real test, you would execute the trade here
                    print("Trade executed successfully!")
                
            except Exception as e:
                print(f"Error getting recommendation: {str(e)}")
                import traceback
                traceback.print_exc()
        
        print("\n=== Test Completed Successfully ===")
        
    except Exception as e:
        print(f"\n!!! Test Failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if 'ai_controller' in locals() and hasattr(ai_controller, 'shutdown'):
            print("\nCleaning up resources...")
            await ai_controller.shutdown()
            print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(test_decision_flow())
