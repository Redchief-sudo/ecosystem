#!/usr/bin/env python3
"""
Test script to check strategy weighing and detect bias toward momentum
"""

import asyncio
import logging
import os
import sys

# Add the project root to Python path
sys.path.insert(0, '/home/damien/ecosystem')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

async def test_strategy_weighing():
    """Test if all strategies are being weighed fairly"""
    try:
        from datetime import datetime, timedelta, timezone
        from decimal import Decimal

        from ai.elite_ai_controller import (EliteAsyncAIController,
                                            MarketRegime, TradeOpportunity)
        
        print("🔍 Testing strategy weighing for bias...")
        
        # Create AI controller with default config
        config = {
            'primary_method': 'ensemble',
            'ucb_confidence': 2.0,
            'thompson_beta_prior': (1.0, 1.0),
            'ensemble_size': 5,
            'min_strategy_weight': 0.05,
            'rebalance_interval': 100,
            'min_trades_for_inclusion': 20,
            'min_win_rate': 0.55,
            'min_sharpe_ratio': 0.5,
            'max_drawdown': 0.3
        }
        
        ai_controller = EliteAsyncAIController(config=config, total_capital=Decimal('100000'))
        await ai_controller.initialize()
        
        print(f"✅ AI Controller initialized with {len(ai_controller.strategies)} strategies")
        
        # List all strategies and their types
        print("\n📊 Available Strategies:")
        for strategy_id, perf in ai_controller.strategies.items():
            print(f"  - {strategy_id}: {perf.strategy_name} (Type: {perf.strategy_type})")
            print(f"    Current Weight: {perf.current_weight:.2%}")
            print(f"    Recent Performance: {perf.recent_performance:.3f}")
            print(f"    Win Rate: {perf.win_rate:.2%}")
            print(f"    Sharpe Ratio: {perf.sharpe_ratio:.2f}")
            print()
        
        # Create test opportunity
        opportunity = TradeOpportunity(
            opportunity_id="test:0x123:spot",
            token_symbol="TEST",
            token_address="0x1234567890123456789012345678901234567890",
            chain_id="ethereum",
            opportunity_type="spot",
            current_price=Decimal("100.0"),
            target_price=Decimal("110.0"),
            stop_loss=Decimal("95.0"),
            potential_profit=Decimal("10.0"),
            potential_loss=Decimal("5.0"),
            risk_reward_ratio=2.0,
            confidence=0.8,
            volatility=0.05,
            volume_24h=Decimal("1000000"),
            liquidity=Decimal("500000"),
            market_regime=MarketRegime.SIDEWAYS,
            required_capital=Decimal("1000"),
            estimated_execution_time_ms=200,
            max_slippage=0.01,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            urgency=0.7,
        )
        
        print("🔄 Testing strategy selection with test opportunity...")
        
        # Test multiple selections to see distribution
        selection_counts = {}
        strategy_weights = {}
        
        for i in range(50):  # Run 50 test selections
            recommendation = await ai_controller.select_strategy(opportunity)
            
            strategy_id = recommendation.recommended_strategy_id
            if strategy_id != "SKIP":
                selection_counts[strategy_id] = selection_counts.get(strategy_id, 0) + 1
                strategy_weights[strategy_id] = strategy_weights.get(strategy_id, 0) + recommendation.confidence
            
            print(f"  Selection {i+1}: {strategy_id} (Confidence: {recommendation.confidence:.2%})")
        
        print("\n📈 Strategy Selection Distribution:")
        total_selections = sum(selection_counts.values())
        
        for strategy_id, count in sorted(selection_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_selections) * 100
            avg_confidence = strategy_weights[strategy_id] / count
            strategy_type = ai_controller.strategies[strategy_id].strategy_type
            print(f"  - {strategy_id}: {count}/50 ({percentage:.1f}%) - Type: {strategy_type.value} - Avg Confidence: {avg_confidence:.2%}")
        
        # Check for momentum bias
        momentum_selections = 0
        momentum_strategies = []
        
        for strategy_id, count in selection_counts.items():
            strategy_type = ai_controller.strategies[strategy_id].strategy_type
            if strategy_type.value == "momentum":
                momentum_selections += count
                momentum_strategies.append((strategy_id, count))
        
        momentum_percentage = (momentum_selections / total_selections) * 100 if total_selections > 0 else 0
        
        print(f"\n⚖️  Momentum Strategy Analysis:")
        print(f"  - Total Momentum Selections: {momentum_selections}/50 ({momentum_percentage:.1f}%)")
        print(f"  - Momentum Strategies: {len(momentum_strategies)}")
        for strategy_id, count in momentum_strategies:
            print(f"    - {strategy_id}: {count} selections")
        
        # Determine if there's bias
        if momentum_percentage > 60:
            print(f"⚠️  POTENTIAL BIAS DETECTED: Momentum strategies selected {momentum_percentage:.1f}% of the time (>60%)")
        elif momentum_percentage < 20:
            print(f"⚠️  POTENTIAL ANTI-BIAS: Momentum strategies selected only {momentum_percentage:.1f}% of the time (<20%)")
        else:
            print(f"✅ NO SIGNIFICANT BIAS: Momentum strategies selected {momentum_percentage:.1f}% of the time (reasonable range)")
        
        # Check ensemble weights
        print(f"\n🔄 Current Strategy Weights:")
        for strategy_id, perf in sorted(ai_controller.strategies.items(), key=lambda x: x[1].current_weight, reverse=True):
            print(f"  - {strategy_id}: {perf.current_weight:.2%} (Type: {perf.strategy_type.value})")
        
        print("✅ Strategy weighing test completed")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_strategy_weighing())
