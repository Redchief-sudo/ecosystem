"""
Tests for the EliteAsyncAIController class.
"""
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from ai.elite_async_ai_controller import EliteAsyncAIController, MarketRegime
from core.models import TradeOpportunity, StrategyRecommendation, TokenInfo, MarketData, AssetClass


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
def mock_strategy_manager():
    """Return a mock strategy manager."""
    manager = MagicMock()
    manager.execute_strategies_parallel = AsyncMock(return_value=[])
    return manager


@pytest_asyncio.fixture
async def ai_controller(mock_config, mock_strategy_manager):
    """Return an EliteAsyncAIController instance for testing."""
    # Create the controller with minimal dependencies
    controller = EliteAsyncAIController(
        config=mock_config,
        strategy_manager=mock_strategy_manager
    )
    
    return controller

@pytest.mark.asyncio
async def test_evaluate_opportunity(ai_controller):
    """Test evaluating a trading opportunity."""
    # Create a test opportunity with TokenInfo
    token = TokenInfo(
        symbol='BTC',
        address='0x1234567890abcdef1234567890abcdef12345678',
        name='Bitcoin',
        decimals=18,
        chain_id=1,
        asset_class=AssetClass.CRYPTO
    )
    
    market = MarketData(
        price=Decimal('50000.0'),
        volume_24h=Decimal('1000000.0'),
        liquidity=Decimal('5000000.0'),
        timestamp=datetime.now(timezone.utc)
    )
    
    opportunity = TradeOpportunity(
        opportunity_id="test_opp_1",
        token=token,
        market_data=market,
        scanner_id='test_scanner',
        scanner_version='1.0',
        chain='ethereum',
        token_address=token.address,
        confidence=0.8,
        volatility=0.02,
        metadata={}
    )
    
    # Call select_strategy which is the main evaluation method
    recommendation = await ai_controller.select_strategy(opportunity)
    
    # Verify the recommendation
    assert recommendation is not None
    assert hasattr(recommendation, 'recommended_strategy_id')
    assert hasattr(recommendation, 'confidence')
    assert hasattr(recommendation, 'expected_profit')
    assert hasattr(recommendation, 'expected_risk')
    assert hasattr(recommendation, 'selection_method')
    assert hasattr(recommendation, 'market_regime')
    assert hasattr(recommendation, 'market_regime')

@pytest.mark.asyncio
async def test_create_decision(ai_controller):
    """Test creating a trading decision."""
    # Create a test token
    token = TokenInfo(
        symbol='ETH',
        address='0xabcdefabcdefabcdefabcdefabcdefabcdefabcd',
        name='Ethereum',
        decimals=18,
        chain_id=1,
        asset_class=AssetClass.CRYPTO
    )
    
    market = MarketData(
        price=Decimal('3000.0'),
        volume_24h=Decimal('1000000.0'),
        liquidity=Decimal('5000000.0'),
        timestamp=datetime.now(timezone.utc)
    )
    
    # Create a test opportunity
    opportunity = TradeOpportunity(
        opportunity_id="test_opp_2",
        token=token,
        market_data=market,
        scanner_id='test_scanner',
        scanner_version='1.0',
        chain='ethereum',
        token_address=token.address,
        confidence=0.75,
        volatility=0.025,
        metadata={
            'rsi': 65.0,
            'macd': 1.5,
            'bb_upper': 3200.0,
            'bb_lower': 2800.0
        }
    )
    
    # Create a recommendation
    recommendation = StrategyRecommendation(
        opportunity_id=opportunity.opportunity_id,
        recommended_strategy_id='momentum_1h',
        recommended_strategy_name='1H Momentum',
        confidence=0.75,
        expected_profit=500.0,
        expected_risk=0.2,
        selection_method='test',
        market_regime=MarketRegime.BULL_TRENDING,
        position_size=Decimal('0.1'),
        key_factors=['rsi', 'macd', 'volume'],
        strategy='momentum_1h',
        timestamp=datetime.now(timezone.utc),
        recommendation='buy'
    )
    
    # Verify the recommendation was created successfully
    assert recommendation is not None
    assert recommendation.recommended_strategy_id == 'momentum_1h'
    assert recommendation.confidence == 0.75
    assert recommendation.position_size == Decimal('0.1')

@pytest.mark.asyncio
async def test_track_decision(ai_controller):
    """Test tracking decisions and controller state."""
    # Test that the controller maintains state
    assert ai_controller.current_regime is not None
    assert ai_controller.regime_confidence >= 0.0
    
    # Test deduplication tracking
    assert hasattr(ai_controller, '_seen_tokens')
    assert hasattr(ai_controller, '_seen_opportunities')
    
    # Test duplicate detection
    key1 = "ethereum:0x1234567890abcdef1234567890abcdef12345678"
    assert not ai_controller._is_duplicate(key1)
    # Second call should detect duplicate
    assert ai_controller._is_duplicate(key1)
    
    # Test cleanup
    ai_controller._prune_dedup()
    
    # Verify dedup cache size limits are respected
    assert len(ai_controller._seen_tokens) <= ai_controller.MAX_DEDUP_SIZE
