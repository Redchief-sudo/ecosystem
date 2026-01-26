"""
Tests for the EliteAsyncAIController class.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from ai.elite_async_ai_controller import (EliteAsyncAIController, MarketRegime,
                                          StrategyType, TokenMetrics,
                                          TradeOpportunity)
from ai.score_engine import EnhancedScoreEngine


@pytest.fixture
def mock_config():
    """Return a mock configuration."""
    return {
        'ai': {
            'min_confidence': 0.55,
            'scoring': {
                'weights': {
                    'liquidity': 0.3,
                    'volatility': 0.2,
                    'volume': 0.2,
                    'momentum': 0.15,
                    'sentiment': 0.1,
                    'market_cap': 0.05
                }
            }
        }
    }

@pytest.fixture
def mock_score_engine():
    """Return a mock score engine."""
    engine = MagicMock(spec=EnhancedScoreEngine)
    engine.score_opportunities.return_value = [{
        'symbol': 'TEST',
        'score': 0.75,
        'liquidity': 1000000,
        'volatility': 0.2,
        'price': 1.0,
        'score_components': {
            'liquidity': 0.9,
            'volatility': 0.8,
            'volume': 0.7,
            'momentum': 0.6
        }
    }]
    return engine

@pytest.fixture
async def ai_controller(mock_config, mock_score_engine):
    """Return an EliteAsyncAIController instance for testing."""
    # Configure the mock score engine
    mock_score_engine.calculate_score.return_value = {
        'composite_score': 0.75,
        'liquidity_score': 0.8,
        'sentiment_score': 0.7,
        'technical_score': 0.8,
        'risk_score': 0.3
    }
    
    # Create and return the controller
    controller = EliteAsyncAIController(
        config=mock_config, 
        score_engine=mock_score_engine,
        token_scoring_service=MagicMock()
    )
    
    # Patch the analyze_market_context method for testing
    async def mock_analyze(*args, **kwargs):
        return {
            'confidence': 0.8,
            'market_regime': MarketRegime.BULL_TRENDING,
            'scores': {},
            'features': {},
            'risk_metrics': {}
        }
    
    controller.analyze_market_context = mock_analyze
    return controller

@pytest.mark.asyncio
async def test_evaluate_opportunity(ai_controller):
    """Test evaluating a trading opportunity."""
    # Create a test opportunity
    opportunity = TradeOpportunity(
        opportunity_id="test_opp_1",
        token_symbol='BTC/USDT',
        opportunity_type='technical',
        current_price=Decimal('50000.0'),
        target_price=Decimal('55000.0'),
        stop_loss=Decimal('48000.0'),
        potential_profit=Decimal('5000.0'),
        potential_loss=Decimal('2000.0'),
        risk_reward_ratio=2.5,
        confidence=0.8,
        volatility=0.02,
        volume_24h=Decimal('1000.0'),
        liquidity=Decimal('5000000.0'),
        market_regime=MarketRegime.BULL_TRENDING,
        required_capital=Decimal('1000.0'),
        estimated_execution_time_ms=100.0,
        max_slippage=0.001,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        urgency=0.8,
        technical_indicators={
            'rsi': 60.0,
            'macd': 2.5,
            'bb_upper': 51000.0,
            'bb_lower': 49000.0
        },
        market_sentiment=0.7
    )
    
    # Mock portfolio state
    portfolio = {
        'total_balance': Decimal('10000.0'),
        'available_balance': Decimal('5000.0'),
        'positions': {}
    }
    
    # Evaluate the opportunity
    recommendation = await ai_controller.evaluate_opportunity(opportunity, portfolio)
    
    # Verify the recommendation
    assert recommendation is not None
    assert hasattr(recommendation, 'recommended_strategy_id')
    assert hasattr(recommendation, 'confidence')
    assert hasattr(recommendation, 'expected_profit')
    assert hasattr(recommendation, 'expected_risk')
    assert hasattr(recommendation, 'selection_method')
    assert hasattr(recommendation, 'market_regime')
    
    # Verify the recommendation has valid values
    assert recommendation.confidence >= 0.0
    assert recommendation.confidence <= 1.0
    assert recommendation.expected_profit >= Decimal('0')
    assert recommendation.expected_risk >= 0.0

@pytest.mark.asyncio
async def test_create_decision(ai_controller):
    """Test creating a trading decision."""
    # Create a test token metrics
    token_metrics = TokenMetrics(
        symbol='ETH',
        address='0x123...',
        price=Decimal('3000.0'),
        volume_24h=Decimal('1000000.0'),
        liquidity=Decimal('5000000.0')
    )
    
    # Create a test opportunity
    opportunity = TradeOpportunity(
        opportunity_id="test_opp_2",
        token_symbol='ETH',
        opportunity_type='technical',
        current_price=Decimal('3000.0'),
        target_price=Decimal('3500.0'),
        stop_loss=Decimal('2800.0'),
        potential_profit=Decimal('500.0'),
        potential_loss=Decimal('200.0'),
        risk_reward_ratio=2.5,
        confidence=0.75,
        volatility=0.025,
        volume_24h=Decimal('1000000.0'),
        liquidity=Decimal('5000000.0'),
        market_regime=MarketRegime.BULL_TRENDING,
        required_capital=Decimal('1000.0'),
        estimated_execution_time_ms=100.0,
        max_slippage=0.001,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        urgency=0.8,
        technical_indicators={
            'rsi': 65.0,
            'macd': 1.5,
            'bb_upper': 3200.0,
            'bb_lower': 2800.0
        },
        market_sentiment=0.7
    )
    
    # Create a recommendation
    recommendation = StrategyRecommendation(
        opportunity_id=opportunity.opportunity_id,
        recommended_strategy_id='momentum_1h',
        recommended_strategy_name='1H Momentum',
        confidence=0.75,
        expected_profit=Decimal('500.0'),
        expected_risk=Decimal('200.0'),
        market_regime=MarketRegime.BULL_TRENDING,
        position_size=Decimal('0.1'),
        key_factors=['rsi', 'macd', 'volume']
    )
    
    # Create the decision
    position = await ai_controller._create_position(
        token_metrics=token_metrics,
        opportunity=opportunity,
        recommendation=recommendation
    )
    
    # Verify the position
    assert position is not None
    assert position.symbol == 'ETH'
    assert position.amount > Decimal('0')
    assert position.entry_price > Decimal('0')
    assert position.stop_loss > Decimal('0')
    assert position.take_profit > Decimal('0')
    assert position.status == 'OPEN'

@pytest.mark.asyncio
async def test_track_decision(ai_controller):
    """Test tracking a decision in history."""
    # Clear history
    ai_controller.decision_history = []
    
    # Create and track a decision
    decision = StrategyRecommendation(
        opportunity_id="test_opp_1",
        recommended_strategy_id='momentum_1h',
        recommended_strategy_name='1H Momentum',
        confidence=0.75,
        expected_profit=Decimal('500.0'),
        expected_risk=Decimal('200.0'),
        market_regime=MarketRegime.BULL_TRENDING,
        position_size=Decimal('0.1'),
        key_factors=['rsi', 'macd', 'volume']
    )
    
    # Create and track a test position
    position = ActivePosition(
        position_id='test_position_1',
        strategy_id=decision.recommended_strategy_id,
        opportunity_id=decision.opportunity_id,
        symbol='TEST',
        entry_price=Decimal('1.0'),
        amount=Decimal('100.0'),
        stop_loss=Decimal('0.9'),
        take_profit=Decimal('1.2')
    )
    
    # Track the position
    await ai_controller.track_position(position)
    
    # Verify the position was tracked
    tracked_position = await ai_controller.get_position('test_position_1')
    assert tracked_position is not None
    assert tracked_position.symbol == 'TEST'
    assert tracked_position.status == 'OPEN'
    
    # Test history size limit
    for i in range(ai_controller.max_history + 10):
        new_position = ActivePosition(
            position_id=f'test_position_{i+2}',
            strategy_id=decision.recommended_strategy_id,
            opportunity_id=f'opp_{i+2}',
            symbol=f'SYMBOL{i}',
            entry_price=Decimal('1.0'),
            amount=Decimal('100.0'),
            stop_loss=Decimal('0.9'),
            take_profit=Decimal('1.2')
        )
        await ai_controller.track_position(new_position)
    
    # Verify history size is limited to max_history
    positions = await ai_controller.get_all_positions()
    assert len(positions) <= ai_controller.max_history
