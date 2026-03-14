#!/usr/bin/env python3
"""Test script for all scanner outputs."""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from web3 import Web3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('test_scanners')

class ScannerTester:
    """Test all scanner components and their outputs."""
    
    def __init__(self):
        self.scanners = {}
        self.results = {}
        self.start_time = datetime.utcnow()
        self.web3_connections = {}
        self.network_manager = None
        
    async def initialize_scanners(self):
        """Initialize all scanner instances."""
        from scanners.scan_director import ScanDirector
        from scanners.discovery.token_scanner import TokenScanner
        from scanners.discovery.dex_screener_scanner import DexScreenerScanner
        from scanners.discovery.onchain_scanner import OnChainScannerUltra
        from scanners.discovery.mempool_scanner import MempoolScannerUltra
        
        # Initialize NetworkManager
        from networks.universal_network_manager import UniversalNetworkManager
        self.network_manager = UniversalNetworkManager()
        await self.network_manager.initialize()
        
        # Initialize Web3 connections for different chains
        chains = ['ethereum', 'bsc', 'polygon', 'avalanche', 'arbitrum']
        for chain in chains:
            try:
                # In a real scenario, you'd use actual RPC endpoints here
                self.web3_connections[chain] = Web3()
            except Exception as e:
                logger.warning(f"Failed to initialize Web3 for {chain}: {e}")
        
        # Initialize individual scanners
        scanner_config = {
            'cache_enabled': True,
            'max_concurrent': 10,
            'min_market_cap': 1_000_000,
            'min_volume_24h': 100_000
        }
        
        web3_connections = self.web3_connections
        
        try:
            # Token Scanner
            self.scanners['token_scanner'] = TokenScanner(
                web3_connections=web3_connections,
                config=scanner_config,
                network_manager=self.network_manager
            )
            
            # DexScreener Scanner
            self.scanners['dex_screener'] = DexScreenerScanner(
                web3_connections=web3_connections,
                config=scanner_config,
                network_manager=self.network_manager
            )
            
            # OnChain Scanner
            self.scanners['onchain_scanner'] = OnChainScannerUltra(
                web3_connections=web3_connections,
                config=scanner_config,
                network_manager=self.network_manager
            )
            
            # Mempool Scanner
            self.scanners['mempool_scanner'] = MempoolScannerUltra(
                web3_connections=web3_connections,
                config=scanner_config,
                network_manager=self.network_manager
            )
            
            # Initialize ScanDirector
            self.scan_director = ScanDirector(
                config={
                    'max_concurrent': 5,
                    'scanner_timeout': 30,
                    'execution_mode': 'PARALLEL',
                    'aggregation_strategy': 'DEDUPE_BY_ADDRESS'
                },
                network_manager=self.network_manager
            )
            
            # Register all scanners
            for name, scanner in self.scanners.items():
                self.scan_director.register_scanner(
                    scanner=scanner,
                    priority=10,  # Medium priority
                    enabled=True,
                    chains=['ethereum', 'bsc', 'polygon', 'avalanche', 'arbitrum']
                )
                logger.info(f"Registered scanner: {name}")
                
            # Initialize the director
            await self.scan_director.initialize()
            
            logger.info(f"Initialized {len(self.scanners)} scanners")
            
        except Exception as e:
            logger.error(f"Failed to initialize scanners: {e}", exc_info=True)
            raise
    
    async def test_token_scanner(self):
        """Test the token scanner."""
        scanner = self.scanners['token_scanner']
        results = {}
        
        # Test 1: Discover top tokens on Ethereum
        results['discover_ethereum'] = await scanner.scan(
            'ethereum',
            max_tokens=3
        )
        
        # Test 2: Analyze specific token (USDC on Ethereum)
        results['analyze_usdc'] = await scanner.scan(
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'ethereum'
        )
        
        # Get metrics
        results['metrics'] = scanner.get_metrics()
        
        return results
    
    async def test_dex_screener(self):
        """Test the DexScreener scanner."""
        scanner = self.scanners['dex_screener']
        results = {}
        
        # Test 1: Get pairs for a token (WETH on Ethereum)
        results['get_pairs'] = await scanner.get_pairs(
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
            'ethereum'
        )
        
        # Test 2: Get token info
        results['get_token'] = await scanner.get_token(
            '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
            'ethereum'
        )
        
        # Get metrics
        results['metrics'] = scanner.get_metrics()
        
        return results
    
    async def test_onchain_scanner(self):
        """Test the OnChain scanner."""
        scanner = self.scanners['onchain_scanner']
        results = {}
        
        # Test 1: Get token info
        results['get_token_info'] = await scanner.get_token_info(
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USDC
            'ethereum'
        )
        
        # Test 2: Get token holders
        results['get_holders'] = await scanner.get_top_holders(
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USDC
            'ethereum',
            limit=3
        )
        
        # Get metrics
        results['metrics'] = scanner.get_metrics()
        
        return results
    
    async def test_mempool_scanner(self):
        """Test the Mempool scanner."""
        scanner = self.scanners['mempool_scanner']
        results = {}
        
        # Test 1: Get pending transactions
        results['pending_txs'] = await scanner.get_pending_transactions(
            'ethereum',
            limit=3
        )
        
        # Test 2: Get gas prices
        results['gas_prices'] = await scanner.get_gas_prices('ethereum')
        
        # Get metrics
        results['metrics'] = scanner.get_metrics()
        
        return results
    
    async def test_scan_director(self):
        """Test the ScanDirector with all scanners."""
        results = {}
        
        # Test 1: Scan all chains with all scanners
        scan_results = await self.scan_director.scan_all(
            chains=['ethereum'],
            max_tokens=2
        )
        
        # Format results
        for chain, scanner_results in scan_results.items():
            results[chain] = {}
            for scanner_name, data in scanner_results.items():
                if isinstance(data, list):
                    results[chain][scanner_name] = f"Found {len(data)} items"
                elif isinstance(data, dict):
                    results[chain][scanner_name] = f"Result with {len(data)} fields"
                else:
                    results[chain][scanner_name] = str(data)
        
        # Get metrics
        results['metrics'] = self.scan_director.get_metrics()
        
        return results
    
    async def run_tests(self):
        """Run all tests and collect results."""
        try:
            logger.info("Starting scanner tests...")
            
            # Initialize all scanners
            await self.initialize_scanners()
            
            # Run individual scanner tests
            self.results['token_scanner'] = await self.test_token_scanner()
            self.results['dex_screener'] = await self.test_dex_screener()
            self.results['onchain_scanner'] = await self.test_onchain_scanner()
            self.results['mempool_scanner'] = await self.test_mempool_scanner()
            
            # Test ScanDirector integration
            self.results['scan_director'] = await self.test_scan_director()
            
            # Calculate test duration
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            logger.info(f"All tests completed in {duration:.2f} seconds")
            
            # Print summary
            self.print_summary()
            
            return self.results
            
        except Exception as e:
            logger.error(f"Test failed: {e}", exc_info=True)
            raise
        finally:
            # Clean up
            await self.cleanup()
    
    def print_summary(self):
        """Print a summary of the test results."""
        print("\n" + "="*80)
        print("SCANNER TEST SUMMARY")
        print("="*80)
        
        for scanner_name, result in self.results.items():
            print(f"\n{scanner_name.upper()}:")
            if 'metrics' in result:
                metrics = result.pop('metrics', {})
                print(f"  Metrics: {json.dumps(metrics, indent=2, default=str)}")
            
            for test_name, test_result in result.items():
                if isinstance(test_result, (list, dict)):
                    print(f"  {test_name}: {len(test_result)} items")
                else:
                    print(f"  {test_name}: {test_result}")
    
    async def cleanup(self):
        """Clean up resources."""
        # Close all scanners
        for name, scanner in self.scanners.items():
            try:
                if hasattr(scanner, 'close'):
                    await scanner.close()
                logger.info(f"Closed scanner: {name}")
            except Exception as e:
                logger.error(f"Error closing scanner {name}: {e}")
                
        # Close network manager
        if self.network_manager:
            try:
                if hasattr(self.network_manager, 'close'):
                    await self.network_manager.close()
                    logger.info("Closed NetworkManager")
            except Exception as e:
                logger.error(f"Error closing NetworkManager: {e}")

async def main():
    """Run the scanner tests."""
    tester = ScannerTester()
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(main())
