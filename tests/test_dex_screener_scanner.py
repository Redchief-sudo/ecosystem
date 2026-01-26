import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from scanners.dex_screener_scanner import DexScreenerScanner
from trading.token_pipeline import TokenMetadata, validate_token_data
from config import is_network_supported, get_evm_networks

@pytest.fixture
def scanner():
    return DexScreenerScanner()

@pytest.mark.asyncio
async def test_scan_network_success(scanner):
    """Test successful network scan."""
    with patch('aiohttp.ClientSession.get') as mock_get:
        # Mock successful API response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'pairs': [{
                'baseToken': {
                    'address': '0x1234567890123456789012345678901234567890',
                    'symbol': 'TEST',
                    'name': 'Test Token',
                    'decimals': 18
                },
                'quoteToken': {
                    'symbol': 'WETH'
                },
                'pairAddress': '0xpair12345678901234567890123456789012345678',
                'dexId': 'test-dex',
                'priceUsd': '1.0',
                'liquidity': {'usd': '10000.0'},
                'volume': {'h24': '5000.0'},
                'priceChange': {
                    'm5': '0.5',
                    'h1': '2.0',
                    'h24': '5.0',
                    'd7': '10.0'
                },
                'marketCap': '100000.0'
            }]
        }
        mock_get.return_value.__aenter__.return_value = mock_response

        # Mock memory
        scanner.memory = AsyncMock()
        scanner.memory.add_token.return_value = True

        # Initialize and scan
        await scanner.initialize()
        tokens = await scanner.scan_network('ethereum')

        # Verify results
        assert len(tokens) == 1
        assert tokens[0]['symbol'] == 'TEST'
        assert tokens[0]['chain'] == 'ethereum'
        assert tokens[0]['liquidity_usd'] == 10000.0

@pytest.mark.asyncio
async def test_scan_unsupported_network(scanner):
    """Test scanning unsupported network."""
    tokens = await scanner.scan_network('unsupported-chain')
    assert tokens == []

def test_token_validation():
    """Test token validation logic."""
    # Valid token
    token = TokenMetadata(
        address='0x1234567890123456789012345678901234567890',
        symbol='TEST',
        name='Test Token',
        decimals=18,
        chain='ethereum'
    )
    assert token.symbol == 'TEST'
    
    # Invalid address
    with pytest.raises(ValueError):
        TokenMetadata(
            address='invalid',
            symbol='TEST',
            name='Test Token',
            decimals=18,
            chain='ethereum'
        )
    
    # Test validate_token_data function
    valid_data = {
        'address': '0x1234567890123456789012345678901234567890',
        'symbol': 'TEST',
        'name': 'Test Token',
        'decimals': 18,
        'chain': 'ethereum'
    }
    is_valid, message = validate_token_data(valid_data)
    assert is_valid == True
    
    # Missing required field
    invalid_data = {
        'symbol': 'TEST',
        'name': 'Test Token',
        'decimals': 18,
        'chain': 'ethereum'
    }
    is_valid, message = validate_token_data(invalid_data)
    assert is_valid == False
    assert 'Missing required fields' in message

def test_network_config():
    """Test network configuration."""
    # Test supported networks
    assert is_network_supported('ethereum') == True
    assert is_network_supported('bsc') == True
    assert is_network_supported('unsupported') == False
    
    # Test EVM networks list
    evm_networks = get_evm_networks()
    assert 'ethereum' in evm_networks
    assert 'bsc' in evm_networks
    assert 'solana' not in evm_networks  # Non-EVM

@pytest.mark.asyncio
async def test_rate_limiting(scanner):
    """Test rate limiting logic."""
    # Initialize rate limits for test
    scanner._rate_limits = {
        'ethereum': {
            'max_requests': 2,
            'window_seconds': 1,
            'requests': [],
            'backoff_until': 0,
            'consecutive_errors': 0
        }
    }

    # First two requests should pass
    await scanner._rate_limit('ethereum')
    await scanner._rate_limit('ethereum')

    # Third request should be rate limited
    with patch('asyncio.sleep') as mock_sleep:
        await scanner._rate_limit('ethereum')
        assert mock_sleep.called

def test_required_fields_present():
    """Test that all required fields are present in token data."""
    from scanners.scanned_token import ScannedToken
    
    # Create a token with all required fields
    token_data = {
        'address': '0x1234567890123456789012345678901234567890',
        'symbol': 'TEST',
        'name': 'Test Token',
        'decimals': 18,
        'chain': 'ethereum',
        'chain_id': 1,
        'chain_name': 'ethereum',
        'price': 1.0,
        'volume_24h': 5000.0,
        'liquidity_usd': 10000.0,
        'price_change_5m': 0.5,
        'price_change_1h': 2.0,
        'price_change_24h': 5.0,
        'price_change_7d': 10.0,
        'market_cap': 100000.0,
        'pair_address': '0xpair12345678901234567890123456789012345678',
        'exchange': 'test-dex',
        'zscore': 0.0,
        'strength': 50.0,
        'momentum': 50.0,
        'volatility': 50.0,
        'ai_score': 0.0,
        'confidence': 0.0,
        'risk_score': 0.0,
        'holders': 1000,
        'has_traded': True,
        'is_blacklisted': False,
        'metadata': {},
        'first_seen': datetime.now(timezone.utc).timestamp() * 1000,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Verify all required fields are present
    required_fields = [
        'address', 'symbol', 'name', 'decimals', 'chain',
        'chain_id', 'chain_name', 'price', 'volume_24h', 'liquidity_usd',
        'price_change_5m', 'price_change_1h', 'price_change_24h', 'price_change_7d',
        'market_cap', 'pair_address', 'exchange', 'zscore', 'strength',
        'momentum', 'volatility', 'ai_score', 'confidence', 'risk_score',
        'holders', 'has_traded', 'is_blacklisted', 'metadata',
        'first_seen', 'created_at', 'updated_at'
    ]
    
    for field in required_fields:
        assert field in token_data, f"Missing required field: {field}"
    
    # Test ScannedToken creation
    scanned_token = ScannedToken.from_dict(token_data)
    assert scanned_token.address == token_data['address']
    assert scanned_token.symbol == token_data['symbol']
    assert scanned_token.name == token_data['name']
    assert scanned_token.decimals == token_data['decimals']
    assert scanned_token.chain_name == token_data['chain_name']

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
