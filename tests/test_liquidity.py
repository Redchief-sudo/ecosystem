#!/usr/bin/env python3
import asyncio

from config import get_config
from network import NetworkManager
from scanners.dex_screener_scanner import DexScreenerScanner


async def test():
    config = get_config()._config
    network_manager = NetworkManager(config)
    
    # Create DexScreener scanner
    scanner_config = config.get('scanners', {}).get('dex_screener', {})
    scanner = DexScreenerScanner(
        network_manager=network_manager,
        config=scanner_config,
        memory=None
    )
    
    # Test API call directly
    try:
        async with scanner.api_client as client:
            data = await client.get('search', params={'q': 'ETH', 'limit': 5})
            if data and 'pairs' in data:
                pairs = data['pairs']
                ethereum_pairs = [p for p in pairs if p.get('chainId') == 'ethereum']
                print(f'Ethereum pairs: {len(ethereum_pairs)}')
                
                # Test _process_v2_pair method directly
                for i, pair in enumerate(ethereum_pairs):
                    token_dict = scanner._process_v2_pair(pair, 'ethereum')
                    print(f'Pair {i+1} processed:')
                    print(f'  Symbol: {token_dict.get("symbol", "N/A")}')
                    print(f'  Liquidity: ${token_dict.get("liquidity", 0):,.2f}')
                    print(f'  Volume: ${token_dict.get("volume_24h", 0):,.2f}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(test())
