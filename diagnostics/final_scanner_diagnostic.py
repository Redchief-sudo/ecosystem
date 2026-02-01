#!/usr/bin/env python3
import sys

sys.path.append('.')
import asyncio

from config.config_loader import load_scanner_config
from scanners.scan_director import ScanDirector
from utils.memory import MemoryManager


# Mock network manager
class MockNetworkManager:
    def __init__(self):
        self.clients = {'ethereum': None, 'bsc': None, 'polygon': None}

# Mock AI controller
class MockAIController:
    async def make_decision(self, token_data):
        return {'confidence': 0.8, 'decision': 'buy'}

async def final_test():
    print('🔍 Final Comprehensive Scanner Test\n')
    
    # Setup
    config = load_scanner_config()
    network_manager = MockNetworkManager()
    memory = MemoryManager()
    ai_controller = MockAIController()
    
    # Create scan director
    director = ScanDirector(network_manager, memory, config, ai_controller=ai_controller)
    print(f'✅ Loaded {len(director.scanners)} scanners')
    
    # Initialize scanners
    await director.initialize()
    
    # Add some mock token data to memory for testing
    print('\n📝 Adding mock token data to memory...')
    import time

    from utils.memory import TokenMetadata
    
    current_time = int(time.time())
    mock_tokens = [
        TokenMetadata(
            address="0x1234567890123456789012345678901234567890",
            symbol="TEST1",
            name="Test Token 1",
            decimals=18,
            price=0.001,
            volume_24h=50000.0,
            liquidity_usd=25000.0,
            chain="ethereum",
            strength=0.7,
            zscore=1.5,
            momentum={'5m': 0.02, '1h': 0.05, '24h': 0.12}
        ),
        TokenMetadata(
            address="0x2345678901234567890123456789012345678901",
            symbol="TEST2", 
            name="Test Token 2",
            decimals=18,
            price=0.002,
            volume_24h=75000.0,
            liquidity_usd=40000.0,
            chain="ethereum",
            strength=0.8,
            zscore=2.1,
            momentum={'5m': 0.08, '1h': 0.12, '24h': 0.25}
        )
    ]
    
    for token in mock_tokens:
        memory.add_token(token)
    
    print(f'   ✅ Added {len(mock_tokens)} mock tokens to memory')
    
    # Test each scanner individually on ethereum
    print('\n📊 Testing individual scanners on Ethereum:')
    
    for i, scanner in enumerate(director.scanners, 1):
        scanner_name = scanner.__class__.__name__
        print(f'\n{i}. {scanner_name}:')
        
        try:
            # Use scan method (some have scan_network, some have scan)
            if hasattr(scanner, 'scan_network'):
                results = await scanner.scan_network('ethereum')
            else:
                results = await scanner.scan('ethereum')
            
            print(f'   ✅ Found {len(results)} tokens')
            
            if results:
                token = results[0]
                if isinstance(token, dict):
                    print(f'   📈 Sample: {token.get("symbol", "Unknown")} - Liquidity: ${token.get("liquidity_usd", 0):,.0f}')
                else:
                    print(f'   📈 Sample: {getattr(token, "symbol", "Unknown")} - Type: {type(token)}')
            
        except Exception as e:
            print(f'   ❌ Error: {e}')
    
    # Check memory after all scanners
    print(f'\n📊 Memory after all scanners:')
    memory_tokens = memory.get_recent_tokens(hours=1) or []
    print(f'   Total tokens in memory: {len(memory_tokens)}')
    
    if memory_tokens:
        eth_tokens = [t for t in memory_tokens if t.chain == 'ethereum']
        print(f'   Ethereum tokens: {len(eth_tokens)}')
    
    # Test hybrid scanner with populated memory
    print(f'\n🧪 Testing Hybrid Scanner with populated memory:')
    hybrid_scanner = next((s for s in director.scanners if 'Hybrid' in s.__class__.__name__), None)
    if hybrid_scanner:
        try:
            results = await hybrid_scanner.scan('ethereum')
            print(f'   ✅ Hybrid found {len(results)} tokens')
            if results:
                token = results[0]
                score = token.metadata.get('score', {})
                print(f'   📈 Sample: {token.symbol} - Overall Score: {score.get("overall", 0):.3f}')
        except Exception as e:
            print(f'   ❌ Hybrid error: {str(e)}')

    # Cleanup scanners
    print(f'\n🧹 Cleaning up scanners...')
    for scanner in director.scanners:
        try:
            if hasattr(scanner, 'cleanup') and callable(scanner.cleanup):
                await scanner.cleanup()
        except Exception as e:
            print(f'   ⚠️ Cleanup error for {scanner.__class__.__name__}: {e}')

if __name__ == "__main__":
    asyncio.run(final_test())
