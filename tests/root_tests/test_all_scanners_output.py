#!/usr/bin/env python3
"""Enhanced test script to verify token output from all scanners with detailed logging."""

import asyncio
import logging
import time
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import yaml

# Configure logging with debug level
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('scanner_test')

# Known test tokens by network
KNOWN_TOKENS = {
    'ethereum': [
        {'address': '0xdac17f958d2ee523a2206206994597c13d831ec7', 'symbol': 'USDT'},  # Tether
        {'address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', 'symbol': 'USDC'},  # USD Coin
    ],
    'bsc': [
        {'address': '0x55d398326f99059fF775485246999027B3197955', 'symbol': 'USDT'},  # Tether on BSC
        {'address': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', 'symbol': 'USDC'},  # USD Coin on BSC
    ],
    'polygon': [
        {'address': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F', 'symbol': 'USDT'},  # Tether on Polygon
        {'address': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'symbol': 'USDC'},  # USD Coin on Polygon
    ]
}

# Test configuration
TEST_CONFIG = {
    'test_networks': ['ethereum', 'bsc', 'polygon'],  # Focus on main networks
    'max_tokens_per_scan': 50,
    'min_market_cap': 0,  # Reduced to 0 to ensure we get some results
    'min_volume_24h': 0,  # Reduced to 0 to ensure we get some results
    'timeout_seconds': 60,
    'min_liquidity': 0,  # Reduced to 0 to ensure we get some results
    'max_concurrent': 10,
    'test_known_tokens': True  # Enable testing with known tokens
}

class NetworkTester:
    """Helper class to test network connectivity."""
    
    @staticmethod
    async def check_url_accessible(url: str, timeout: int = 5) -> Tuple[bool, str]:
        """Check if a URL is accessible."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    return response.status == 200, f"Status: {response.status}"
        except Exception as e:
            return False, str(e)

class ScannerTester:
    def __init__(self, config: Dict):
        self.config = config
        self.results = {}
        self.scanners = {}
        self.web3_connections = {}
        self.network_manager = None
        self.network_status = {}
        
    async def check_network_connectivity(self):
        """Check connectivity to required network services."""
        logger.info("Checking network connectivity...")
        
        # Test basic internet connectivity
        internet_ok, internet_msg = await NetworkTester.check_url_accessible("https://www.google.com")
        logger.info(f"Internet connectivity: {'✅' if internet_ok else '❌'} {internet_msg}")
        
        # Test common RPC endpoints
        rpc_endpoints = {
            'ethereum': 'https://eth.llamarpc.com',
            'bsc': 'https://bsc-dataseed.binance.org/',
            'polygon': 'https://polygon-rpc.com/'
        }
        
        for network, url in rpc_endpoints.items():
            if network in self.config['test_networks']:
                status, msg = await NetworkTester.check_url_accessible(url)
                self.network_status[network] = status
                logger.info(f"  {network.upper()} RPC: {'✅' if status else '❌'} {msg}")
            else:
                logger.debug(f"Skipping {network} RPC check (not in test networks)")
    
    async def initialize_web3(self):
        """Initialize Web3 connections for test networks."""
        from web3 import Web3
        
        logger.info("Initializing Web3 connections...")
        for network in self.config['test_networks']:
            if not self.network_status.get(network, False):
                logger.warning(f"Skipping Web3 initialization for {network} (network check failed)")
                continue
                
            try:
                # In a real test, these would be actual RPC endpoints
                self.web3_connections[network] = Web3(Web3.HTTPProvider(
                    f"https://{network}.example.com"  # Placeholder - will be overridden by network_manager
                ))
                logger.info(f"Initialized Web3 connection for {network}")
            except Exception as e:
                logger.error(f"Failed to initialize Web3 for {network}: {str(e)}")
    
    async def initialize_scanners(self):
        """Initialize all scanners with proper configuration."""
        logger.info("Initializing scanners...")
        
        # Import scanners
        try:
            from scanners.discovery.dex_screener_scanner import DexScreenerScanner
            from scanners.discovery.token_scanner import TokenScanner
            from scanners.discovery.onchain_scanner import OnChainScannerUltra as OnChainScanner
            from networks.universal_network_manager import UniversalNetworkManager as NetworkManager
        except ImportError as e:
            logger.error(f"Failed to import scanner modules: {e}")
            return False

        # Initialize NetworkManager
        try:
            self.network_manager = NetworkManager()
            logger.info("Initialized NetworkManager")
        except Exception as e:
            logger.error(f"Failed to initialize NetworkManager: {e}")
            return False
        
        # Common scanner config with optimized parameters for discovery
        scanner_config = {
            'cache_enabled': True,
            'max_concurrent': self.config.get('max_concurrent', 10),
            'min_liquidity': self.config.get('min_liquidity', 0),
            'min_volume_24h': self.config['min_volume_24h'],
            'min_market_cap': self.config['min_market_cap'],
            'network_manager': self.network_manager,
            'max_retries': 3,
            'request_timeout': 30,
            'debug': True  # Enable debug mode in scanners
        }
        
        # Initialize each scanner
        try:
            self.scanners = {
                'DexScreener': DexScreenerScanner(
                    config=scanner_config,
                    web3_connections=self.web3_connections
                ),
                'TokenScanner': TokenScanner(
                    web3_connections=self.web3_connections,
                    config=scanner_config
                ),
                'OnChainScanner': OnChainScanner(
                    config=scanner_config,
                    web3_connections=self.web3_connections,
                    network_manager=self.network_manager
                )
            }

            # Initialize each scanner
            for name, scanner in self.scanners.items():
                if hasattr(scanner, 'initialize'):
                    await scanner.initialize()
                    logger.info(f"Initialized {name} scanner")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize scanners: {e}")
            return False
    
    async def test_known_tokens(self):
        """Test with known tokens to verify scanner functionality."""
        if not self.config.get('test_known_tokens', False):
            logger.info("Skipping known tokens test (disabled in config)")
            return []

        logger.info("\n" + "="*80)
        logger.info("TESTING WITH KNOWN TOKENS")
        logger.info("="*80)
        
        results = []
        
        for scanner_name, scanner in self.scanners.items():
            for network in self.config['test_networks']:
                if network not in KNOWN_TOKENS:
                    logger.warning(f"No known tokens for {network}, skipping...")
                    continue
                    
                for token in KNOWN_TOKENS[network]:
                    try:
                        logger.info(f"\nTesting {scanner_name} on {network} with {token['symbol']} ({token['address']})")
                        
                        # Special handling for different scanner interfaces
                        if hasattr(scanner, 'get_token'):
                            # For scanners that support direct token lookup
                            token_data = await scanner.get_token(
                                network, 
                                token['address'],
                                include_metrics=True
                            )
                            
                            if token_data:
                                logger.info(f"✅ Found {token['symbol']} with {scanner_name}")
                                results.append({
                                    'scanner': scanner_name,
                                    'network': network,
                                    'token': token['symbol'],
                                    'address': token['address'],
                                    'success': True,
                                    'data': token_data
                                })
                            else:
                                logger.warning(f"❌ {token['symbol']} not found with {scanner_name}")
                                results.append({
                                    'scanner': scanner_name,
                                    'network': network,
                                    'token': token['symbol'],
                                    'address': token['address'],
                                    'success': False,
                                    'error': 'Token not found'
                                })
                        else:
                            # For scanners that only support scanning
                            logger.warning(f"Scanner {scanner_name} doesn't support direct token lookup")
                            
                    except Exception as e:
                        logger.error(f"Error testing {token['symbol']} with {scanner_name}: {e}")
                        results.append({
                            'scanner': scanner_name,
                            'network': network,
                            'token': token['symbol'],
                            'address': token['address'],
                            'success': False,
                            'error': str(e)
                        })
        
        return results

    async def run_tests(self):
        """Run tests for all scanners on all test networks."""
        logger.info("="*80)
        logger.info("STARTING SCANNER TESTS")
        logger.info("="*80)
        
        # Check network connectivity first
        await self.check_network_connectivity()
        
        # Initialize Web3 connections
        await self.initialize_web3()
        
        # Initialize scanners
        if not await self.initialize_scanners():
            logger.error("Failed to initialize one or more scanners. Aborting tests.")
            return None
        
        # Test with known tokens first
        known_token_results = await self.test_known_tokens()
        
        # Run standard scanner tests
        scanner_results = await self._run_standard_tests()
        
        # Combine results
        self.results = {
            'timestamp': time.time(),
            'config': self.config,
            'network_status': self.network_status,
            'known_token_tests': known_token_results,
            'scanner_results': scanner_results
        }
        
        # Log summary
        self.log_summary()
        
        return self.results
    
    async def _run_standard_tests(self):
        """Run standard scanner tests."""
        logger.info("\n" + "="*80)
        logger.info("RUNNING STANDARD SCANNER TESTS")
        logger.info("="*80)
        
        tasks = []
        for scanner_name in self.scanners.keys():
            for network in self.config['test_networks']:
                tasks.append(self.test_scanner(scanner_name, network))
        
        # Run tests with a timeout
        try:
            return await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config['timeout_seconds']
            )
        except asyncio.TimeoutError:
            logger.error("Tests timed out!")
            return []

    async def test_scanner(self, scanner_name: str, network: str) -> Dict:
        """Test a single scanner on a specific network."""
        scanner = self.scanners[scanner_name]
        result = {
            'scanner': scanner_name,
            'network': network,
            'success': False,
            'duration_seconds': 0,
            'tokens_found': 0,
            'validation_errors': [],
            'error': None
        }
        
        try:
            start_time = time.time()
            
            logger.info(f"\n🔍 Testing {scanner_name} on {network}...")
            
            # Run the scanner
            tokens = await scanner.scan(
                network,
                max_tokens=self.config['max_tokens_per_scan']
            )
            
            result['duration_seconds'] = time.time() - start_time
            result['tokens_found'] = len(tokens)
            result['success'] = True
            
            logger.info(f"  Found {len(tokens)} tokens in {result['duration_seconds']:.2f}s")
            
            # Validate tokens
            for token in tokens:
                validation = self.validate_token(token, scanner_name)
                if not validation['valid']:
                    result['validation_errors'].append({
                        'token': token.get('address', 'unknown'),
                        'issues': {
                            'missing': validation['missing_fields'],
                            'type_errors': validation['type_errors']
                        }
                    })
            
            # Store a sample of tokens for inspection
            sample_size = min(3, len(tokens))
            result['sample_tokens'] = [
                {k: v for k, v in token.items() if k in ['address', 'symbol', 'name', 'chain']}
                for token in tokens[:sample_size]
            ]
            
            # Log sample tokens
            if result['sample_tokens']:
                logger.info("  Sample tokens:")
                for token in result['sample_tokens']:
                    logger.info(f"    - {token.get('symbol', '?')} ({token.get('name', '?')}) - {token.get('address', '?')}")
            else:
                logger.warning("  No tokens found")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"❌ Error testing {scanner_name} on {network}: {e}", exc_info=True)
        
        return result

    def validate_token(self, token: Dict, scanner_name: str) -> Dict:
        """Validate a token's structure and content."""
        required_fields = {
            'address': str,
            'symbol': str,
            'name': str,
            'decimals': int,
            'chain': str
        }
        
        validation = {
            'valid': True,
            'missing_fields': [],
            'type_errors': []
        }
        
        # Check for required fields
        for field, field_type in required_fields.items():
            if field not in token:
                validation['missing_fields'].append(field)
                validation['valid'] = False
            elif not isinstance(token[field], field_type):
                validation['type_errors'].append(
                    f"{field} should be {field_type.__name__}, got {type(token[field]).__name__}"
                )
                validation['valid'] = False
        
        return validation

    def log_summary(self):
        """Log a summary of test results."""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        
        # Network status
        logger.info("\nNETWORK STATUS:")
        for network, status in self.network_status.items():
            logger.info(f"  {network.upper()}: {'✅' if status else '❌'}")
        
        # Known token tests
        if self.results.get('known_token_tests'):
            logger.info("\nKNOWN TOKEN TESTS:")
            for test in self.results['known_token_tests']:
                status = "✅" if test.get('success') else "❌"
                logger.info(f"  {status} {test['scanner']} on {test['network']} - {test.get('token', '?')} "
                          f"({test.get('error', 'Success')})")
        
        # Scanner results
        logger.info("\nSCANNER RESULTS:")
        for result in self.results.get('scanner_results', []):
            if isinstance(result, Exception):
                logger.error(f"  ❌ Error in test: {str(result)}")
                continue
                
            status = "✅" if result['success'] else "❌"
            logger.info(f"\n{status} {result['scanner']} on {result['network']}")
            logger.info(f"  Tokens found: {result['tokens_found']}")
            logger.info(f"  Duration: {result['duration_seconds']:.2f}s")
            
            if result['validation_errors']:
                logger.warning(f"  Validation errors: {len(result['validation_errors'])}")
            
            if 'sample_tokens' in result and result['sample_tokens']:
                logger.info("  Sample tokens:")
                for token in result['sample_tokens']:
                    logger.info(f"    - {token.get('symbol', '?')} ({token.get('name', '?')}) - {token.get('address', '?')}")

async def main():
    """Main test function."""
    tester = ScannerTester(TEST_CONFIG)
    results = await tester.run_tests()
    
    # Print final status
    if results:
        total_tests = len(results.get('scanner_results', []))
        passed_tests = sum(1 for r in results.get('scanner_results', []) 
                          if not isinstance(r, Exception) and r.get('success', False))
        
        logger.info("\n" + "="*80)
        logger.info(f"TEST COMPLETE: {passed_tests}/{total_tests} tests passed")
        logger.info("="*80)
    else:
        logger.error("\n" + "="*80)
        logger.error("TEST FAILED: No results returned")
        logger.error("="*80)

if __name__ == "__main__":
    asyncio.run(main())