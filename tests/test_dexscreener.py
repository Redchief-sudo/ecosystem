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
    
    # Get raw tokens from _scan_v2
    raw_tokens = await scanner._scan_v2('ethereum')
    print(f'Raw tokens: {len(raw_tokens)}')
    
    # Check what filters are being applied
    print(f'Filters: {scanner.filters}')
    
    # Test each token against filters
    for i, token in enumerate(raw_tokens):
        passes = scanner._passes_filters(token, 'ethereum')
        print(f'Token {i+1}: {token.get("symbol", "N/A")} - Passes filter: {passes}')
        if not passes:
            print(f'  Liquidity: ${token.get("liquidity", 0):,.2f}')
            print(f'  Volume: ${token.get("volume_24h", 0):,.2f}')
            print(f'  Min liquidity filter: {scanner.filters.get("min_liquidity", 0)}')
            print(f'  Min volume filter: {scanner.filters.get("min_volume", 0)}')

if __name__ == "__main__":
    asyncio.run(test())
