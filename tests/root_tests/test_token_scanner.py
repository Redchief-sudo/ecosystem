#!/usr/bin/env python3
"""Test script for TokenScanner functionality."""

import asyncio
import logging
from typing import Dict, List, Any
from web3 import Web3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('test_scanner')

async def test_token_scanner():
    """Test the TokenScanner with both discovery and specific token analysis."""
    from scanners.discovery.token_scanner import TokenScanner
    from web3 import Web3
    
    # Mock web3 connections (in a real scenario, these would be actual connections)
    web3_connections = {
        'ethereum': Web3(),
        'bsc': Web3(),
    }
    
    # Initialize the scanner
    scanner = TokenScanner(
        web3_connections=web3_connections,
        config={
            'cache_enabled': True,
            'max_concurrent': 10
        }
    )
    
    try:
        # Test 1: Discover top tokens on Ethereum
        print("\n" + "="*80)
        print("TEST 1: DISCOVER TOP TOKENS ON ETHEREUM")
        print("="*80)
        tokens = await scanner.scan(
            'ethereum',
            max_tokens=5,  # Limit to 5 tokens for testing
            min_market_cap=1_000_000,
            min_volume_24h=100_000
        )
        
        print(f"\nDiscovered {len(tokens)} tokens on Ethereum:")
        for i, token in enumerate(tokens, 1):
            print(f"{i}. {token.get('symbol')} - {token.get('name')}")
            print(f"   Price: ${token.get('price', {}).get('usd', 'N/A'):,.4f}")
            print(f"   Market Cap: ${token.get('market_data', {}).get('market_cap', {}).get('usd', 0):,.0f}")
            print(f"   24h Volume: ${token.get('market_data', {}).get('total_volume', {}).get('usd', 0):,.0f}")
            print(f"   Price Change (24h): {token.get('market_data', {}).get('price_change_percentage_24h', 0):.2f}%")
            print()
        
        # Test 2: Analyze a specific token (USDC on Ethereum)
        print("\n" + "="*80)
        print("TEST 2: ANALYZE SPECIFIC TOKEN (USDC ON ETHEREUM)")
        print("="*80)
        usdc = await scanner.scan(
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'ethereum'
        )
        
        if usdc and len(usdc) > 0:
            token = usdc[0]
            print(f"\nToken Analysis for {token.get('symbol')} - {token.get('name')}:")
            print(f"Address: {token.get('address')}")
            print(f"Chain: {token.get('chain')}")
            print(f"Decimals: {token.get('decimals')}")
            print(f"Price: ${token.get('price', {}).get('usd', 'N/A'):,.4f}")
            print(f"Market Cap: ${token.get('market_data', {}).get('market_cap', {}).get('usd', 0):,.0f}")
            print(f"24h Volume: ${token.get('market_data', {}).get('total_volume', {}).get('usd', 0):,.0f}")
            print(f"Price Change (24h): {token.get('market_data', {}).get('price_change_percentage_24h', 0):.2f}%")
            
            # Show additional token data if available
            if 'contract_data' in token:
                print("\nContract Data:")
                for key, value in token['contract_data'].items():
                    print(f"  {key}: {value}")
        
        # Print metrics
        print("\n" + "="*80)
        print("SCANNER METRICS")
        print("="*80)
        metrics = scanner.get_metrics()
        for key, value in metrics.items():
            if key != 'start_time':
                print(f"{key}: {value}")
    
    finally:
        # Clean up
        await scanner.close()

if __name__ == "__main__":
    asyncio.run(test_token_scanner())
