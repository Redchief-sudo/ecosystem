#!/usr/bin/env python3
"""
RPC Ping Test - Comprehensive RPC Performance and Reliability Tester

This script tests all configured RPC endpoints for:
- Response time
- Success rate
- Block number latency
- Gas price accuracy
- Connection stability

Usage:
    python scripts/rpc_ping_test.py [--chain CHAIN] [--iterations N] [--timeout SECONDS]
"""
import asyncio
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse

import aiohttp
from web3 import AsyncWeb3
from web3.providers.async_rpc import AsyncHTTPProvider

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.logging import get_logger
from config.config_loader import load_yaml_config

logger = get_logger('rpc_ping_test')

@dataclass
class RPCTestResult:
    """Results from testing a single RPC endpoint"""
    url: str
    chain: str
    success_count: int = 0
    total_tests: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    block_number: Optional[int] = None
    gas_price: Optional[int] = None
    errors: List[str] = None
    is_reliable: bool = False
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_tests == 0:
            return 0.0
        return (self.success_count / self.total_tests) * 100
    
    def calculate_reliability_score(self) -> float:
        """
        Calculate a reliability score (0-100) based on:
        - Success rate (40% weight)
        - Response time consistency (30% weight)
        - Average response time (30% weight)
        """
        if self.total_tests == 0:
            return 0.0
        
        # Success rate component
        success_score = self.success_rate
        
        # Response time consistency (lower variance = higher score)
        if self.success_count > 1:
            variance = (self.max_response_time - self.min_response_time) / self.avg_response_time
            consistency_score = max(0, 100 - (variance * 50))  # Penalize high variance
        else:
            consistency_score = 50  # Neutral score for single test
        
        # Response time component (faster = higher score)
        # Scale: <1s = 100, 1-2s = 80, 2-5s = 60, 5-10s = 40, >10s = 20
        if self.avg_response_time < 1.0:
            speed_score = 100
        elif self.avg_response_time < 2.0:
            speed_score = 80
        elif self.avg_response_time < 5.0:
            speed_score = 60
        elif self.avg_response_time < 10.0:
            speed_score = 40
        else:
            speed_score = 20
        
        # Weighted average
        reliability_score = (success_score * 0.4 + consistency_score * 0.3 + speed_score * 0.3)
        return min(100, max(0, reliability_score))

class RPCPingTester:
    """Comprehensive RPC testing utility"""
    
    def __init__(self, config_path: str = None, timeout: int = 15):
        """
        Initialize the RPC tester
        
        Args:
            config_path: Path to config file (default: config/config_unified.yaml)
            timeout: Request timeout in seconds
        """
        self.config_path = config_path or "config/config_unified.yaml"
        self.timeout = timeout
        self.config = None
        self.results: Dict[str, List[RPCTestResult]] = {}
        
    async def load_config(self):
        """Load configuration from file"""
        try:
            self.config = load_yaml_config(self.config_path)
            logger.info(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def get_rpc_endpoints(self) -> Dict[str, List[str]]:
        """
        Extract all RPC endpoints from config
        
        Returns:
            Dict mapping chain names to list of RPC URLs
        """
        if not self.config:
            raise ValueError("Config not loaded")
        
        endpoints = {}
        networks = self.config.get('networks', {})
        
        for chain_name, chain_config in networks.items():
            if not isinstance(chain_config, dict):
                continue
                
            # Skip disabled networks
            if not chain_config.get('enabled', True):
                logger.debug(f"Skipping disabled network: {chain_name}")
                continue
            
            chain_endpoints = []
            
            # Primary RPC
            rpc_url = chain_config.get('rpc') or chain_config.get('rpc_url')
            if rpc_url:
                # Substitute API keys
                rpc_url = self._substitute_api_keys(rpc_url)
                if rpc_url:
                    chain_endpoints.append(rpc_url)
            
            # Fallback RPCs
            fallback_rpcs = chain_config.get('fallback_rpcs', [])
            for fallback in fallback_rpcs:
                fallback_url = self._substitute_api_keys(fallback)
                if fallback_url:
                    chain_endpoints.append(fallback_url)
            
            if chain_endpoints:
                endpoints[chain_name] = chain_endpoints
                logger.debug(f"Found {len(chain_endpoints)} RPC endpoints for {chain_name}")
        
        return endpoints
    
    def _substitute_api_keys(self, rpc_url: str) -> str:
        """Substitute API keys in RPC URLs"""
        import os
        import re
        
        # Handle ${api_keys.provider} pattern
        api_key_pattern = re.compile(r'\$\{api_keys\.(\w+)\}')
        
        def replace_api_key(match):
            provider = match.group(1)
            api_key = self.config.get('api_keys', {}).get(provider)
            if api_key and not api_key.startswith('your_'):
                return api_key
            return match.group(0)
        
        rpc_url = api_key_pattern.sub(replace_api_key, rpc_url)
        
        # Handle environment variables
        if '${' in rpc_url:
            def replace_var(match):
                var = match.group(1).strip()
                if ':-' in var:
                    var, default = var.split(':-', 1)
                    return os.getenv(var, default)
                return os.getenv(var, '')
            
            rpc_url = re.sub(r'\${([^}]+)}', replace_var, rpc_url)
        else:
            rpc_url = os.path.expandvars(rpc_url)
        
        return rpc_url.strip('"\'')
    
    async def test_rpc_endpoint(self, chain: str, url: str, iterations: int = 5) -> RPCTestResult:
        """
        Test a single RPC endpoint multiple times
        
        Args:
            chain: Chain name
            url: RPC URL
            iterations: Number of test iterations
            
        Returns:
            RPCTestResult with performance metrics
        """
        result = RPCTestResult(url=url, chain=chain, total_tests=iterations)
        response_times = []
        
        # Create Web3 instance
        try:
            provider = AsyncHTTPProvider(url, request_kwargs={'timeout': self.timeout})
            w3 = AsyncWeb3(provider)
        except Exception as e:
            result.errors.append(f"Failed to create Web3 instance: {e}")
            return result
        
        logger.info(f"Testing {chain} RPC: {url}")
        
        for i in range(iterations):
            start_time = time.time()
            try:
                # Test basic connectivity and get block number
                block_number = await asyncio.wait_for(
                    w3.eth.block_number,
                    timeout=self.timeout
                )
                
                # Test gas price
                gas_price = await asyncio.wait_for(
                    w3.eth.gas_price,
                    timeout=self.timeout
                )
                
                response_time = time.time() - start_time
                response_times.append(response_time)
                
                result.success_count += 1
                result.block_number = block_number
                result.gas_price = gas_price
                
                logger.debug(f"  Test {i+1}/{iterations}: {response_time:.3f}s, block {block_number}")
                
            except asyncio.TimeoutError:
                error = f"Timeout after {self.timeout}s"
                result.errors.append(error)
                logger.debug(f"  Test {i+1}/{iterations}: {error}")
                
            except Exception as e:
                error = str(e)
                result.errors.append(error)
                logger.debug(f"  Test {i+1}/{iterations}: {error}")
        
        # Calculate statistics
        if response_times:
            result.avg_response_time = sum(response_times) / len(response_times)
            result.min_response_time = min(response_times)
            result.max_response_time = max(response_times)
        
        # Determine reliability
        result.is_reliable = (
            result.success_rate >= 80 and  # At least 80% success rate
            result.avg_response_time <= 5.0  # Average response time under 5 seconds
        )
        
        # Close Web3 connection
        try:
            await w3.provider.session.close()
        except:
            pass
        
        return result
    
    async def test_all_endpoints(self, chains: List[str] = None, iterations: int = 5):
        """
        Test all RPC endpoints
        
        Args:
            chains: List of chains to test (None = all)
            iterations: Number of test iterations per endpoint
        """
        await self.load_config()
        endpoints = self.get_rpc_endpoints()
        
        if chains:
            endpoints = {k: v for k, v in endpoints.items() if k in chains}
        
        if not endpoints:
            logger.error("No RPC endpoints found to test")
            return
        
        logger.info(f"Testing {len(endpoints)} chains with {iterations} iterations each")
        
        # Create test tasks
        tasks = []
        for chain, urls in endpoints.items():
            for url in urls:
                tasks.append(self.test_rpc_endpoint(chain, url, iterations))
        
        # Run tests in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Organize results by chain
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Test failed with exception: {result}")
                continue
                
            if result.chain not in self.results:
                self.results[result.chain] = []
            self.results[result.chain].append(result)
    
    def print_results(self):
        """Print formatted test results"""
        print("\n" + "="*80)
        print("RPC PING TEST RESULTS")
        print("="*80)
        
        for chain, results in sorted(self.results.items()):
            print(f"\n📡 {chain.upper()}")
            print("-" * 60)
            
            # Sort by reliability score
            sorted_results = sorted(results, key=lambda r: r.calculate_reliability_score(), reverse=True)
            
            for i, result in enumerate(sorted_results, 1):
                status = "✅ RELIABLE" if result.is_reliable else "⚠️ UNRELIABLE"
                score = result.calculate_reliability_score()
                
                print(f"{i}. {status} (Score: {score:.1f}/100)")
                print(f"   URL: {result.url}")
                print(f"   Success Rate: {result.success_rate:.1f}% ({result.success_count}/{result.total_tests})")
                print(f"   Response Time: {result.avg_response_time:.3f}s (min: {result.min_response_time:.3f}s, max: {result.max_response_time:.3f}s)")
                
                if result.block_number:
                    try:
                        # Handle AttributeDict from Web3 errors
                        if hasattr(result.block_number, 'get') and result.block_number.get('error'):
                            print(f"   Latest Block: RPC Error (non-EVM chain)")
                        else:
                            print(f"   Latest Block: {result.block_number}")
                    except:
                        print(f"   Latest Block: {result.block_number}")
                        
                if result.gas_price:
                    try:
                        # Handle AttributeDict from Web3 errors
                        if hasattr(result.gas_price, 'get') and result.gas_price.get('error'):
                            print(f"   Gas Price: RPC Error (non-EVM chain)")
                        else:
                            print(f"   Gas Price: {result.gas_price:,} wei")
                    except (ValueError, TypeError):
                        print(f"   Gas Price: {result.gas_price}")
                
                if result.errors:
                    # Show unique errors (max 3)
                    unique_errors = list(set(result.errors))[:3]
                    print(f"   Errors: {', '.join(unique_errors)}")
                    if len(set(result.errors)) > 3:
                        print(f"   ... and {len(set(result.errors)) - 3} more")
                print()
    
    def get_recommendations(self) -> Dict[str, str]:
        """
        Get the best RPC endpoint for each chain
        
        Returns:
            Dict mapping chain names to recommended RPC URLs
        """
        recommendations = {}
        
        for chain, results in self.results.items():
            # Filter to reliable endpoints only
            reliable_results = [r for r in results if r.is_reliable]
            
            if reliable_results:
                # Choose the one with highest reliability score
                best = max(reliable_results, key=lambda r: r.calculate_reliability_score())
                recommendations[chain] = best.url
            elif results:
                # If none are reliable, choose the one with highest success rate
                best = max(results, key=lambda r: (r.success_rate, -r.avg_response_time))
                recommendations[chain] = best.url
        
        return recommendations
    
    def save_results(self, filename: str = "rpc_test_results.json"):
        """Save test results to JSON file"""
        data = {
            'timestamp': time.time(),
            'test_timeout': self.timeout,
            'results': {}
        }
        
        for chain, results in self.results.items():
            data['results'][chain] = []
            for result in results:
                result_dict = asdict(result)
                result_dict['reliability_score'] = result.calculate_reliability_score()
                
                # Convert non-serializable objects
                if result.block_number and hasattr(result.block_number, 'get'):
                    result_dict['block_number'] = str(result.block_number)
                if result.gas_price and hasattr(result.gas_price, 'get'):
                    result_dict['gas_price'] = str(result.gas_price)
                
                data['results'][chain].append(result_dict)
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Results saved to {filename}")
    
    def generate_config_recommendations(self) -> str:
        """Generate recommended configuration updates"""
        recommendations = self.get_recommendations()
        
        output = ["# Recommended RPC Configuration Updates"]
        output.append("# Based on automated reliability testing")
        output.append("")
        
        for chain, url in recommendations.items():
            output.append(f"# {chain.upper()} - Best performing RPC")
            output.append(f"networks.{chain}.rpc: {url}")
            output.append("")
        
        return "\n".join(output)

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test RPC endpoint performance and reliability")
    parser.add_argument("--chain", help="Test specific chain only (comma-separated for multiple)")
    parser.add_argument("--iterations", type=int, default=5, help="Number of test iterations per endpoint")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--recommendations", action="store_true", help="Show configuration recommendations")
    
    args = parser.parse_args()
    
    # Parse chains
    chains = None
    if args.chain:
        chains = [c.strip() for c in args.chain.split(",")]
    
    # Run tests
    tester = RPCPingTester(config_path=args.config, timeout=args.timeout)
    await tester.test_all_endpoints(chains=chains, iterations=args.iterations)
    
    # Show results
    tester.print_results()
    
    # Show recommendations
    if args.recommendations:
        print("\n" + "="*80)
        print("CONFIGURATION RECOMMENDATIONS")
        print("="*80)
        print(tester.generate_config_recommendations())
    
    # Save results
    if args.save:
        tester.save_results()

if __name__ == "__main__":
    asyncio.run(main())
