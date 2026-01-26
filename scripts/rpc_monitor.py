#!/usr/bin/env python3
"""
RPC Health Monitor - Simple monitoring for RPC endpoints

This script provides a quick health check of configured RPC endpoints.
Can be used for:
- Periodic monitoring (cron job)
- Pre-trading validation
- Troubleshooting RPC issues

Usage:
    python scripts/rpc_monitor.py [--chain CHAIN] [--quick]
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.logging import get_logger
from config.config_loader import load_yaml_config
from networks.chain_type_detector import ChainTypeDetector

logger = get_logger('rpc_monitor')

class RPCMonitor:
    """Simple RPC health monitoring utility"""
    
    def __init__(self, config_path: str = None, timeout: int = 10):
        """Initialize RPC monitor"""
        self.config_path = config_path or "config/config_unified.yaml"
        self.timeout = timeout
        self.config = None
    
    async def load_config(self):
        """Load configuration"""
        try:
            self.config = load_yaml_config(self.config_path)
            logger.info(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def get_primary_rpcs(self) -> Dict[str, str]:
        """Get primary RPC URLs for each enabled network"""
        if not self.config:
            raise ValueError("Config not loaded")
        
        rpcs = {}
        networks = self.config.get('networks', {})
        
        for chain_name, chain_config in networks.items():
            if not isinstance(chain_config, dict):
                continue
                
            # Skip disabled networks
            if not chain_config.get('enabled', True):
                continue
            
            # Get primary RPC
            rpc_url = chain_config.get('rpc') or chain_config.get('rpc_url')
            if rpc_url:
                # Substitute API keys
                rpc_url = self._substitute_api_keys(rpc_url)
                if rpc_url:
                    rpcs[chain_name] = rpc_url
        
        return rpcs
    
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
    
    async def test_rpc(self, chain: str, url: str) -> Tuple[str, bool, float, str]:
        """
        Test a single RPC endpoint
        
        Returns:
            Tuple of (url, success, response_time, error_message)
        """
        try:
            import aiohttp
            from web3 import AsyncWeb3
            from web3.providers.async_rpc import AsyncHTTPProvider
            
            # Get chain info to determine testing approach
            chain_info = ChainTypeDetector.get_chain_info(chain)
            
            # For non-EVM chains, use simple HTTP request instead of Web3
            if not chain_info.supports_eth_calls:
                start_time = time.time()
                
                # Test basic HTTP connectivity
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    try:
                        # Try a simple POST request to test connectivity
                        payload = {"jsonrpc": "2.0", "method": "test", "params": [], "id": 1}
                        async with session.post(url, json=payload) as response:
                            if response.status in [200, 404, 405]:  # Any of these mean the server is reachable
                                response_time = time.time() - start_time
                                return url, True, response_time, f"HTTP {response.status} - {chain_info.chain_type} chain"
                            else:
                                response_time = time.time() - start_time
                                return url, False, response_time, f"HTTP {response.status}"
                    except Exception as e:
                        response_time = time.time() - start_time
                        return url, False, response_time, f"HTTP Error: {str(e)}"
            
            # For EVM chains, use Web3
            provider = AsyncHTTPProvider(url, request_kwargs={'timeout': self.timeout})
            w3 = AsyncWeb3(provider)
            
            start_time = time.time()
            
            # Test basic connectivity
            block_number = await asyncio.wait_for(
                w3.eth.block_number,
                timeout=self.timeout
            )
            
            response_time = time.time() - start_time
            
            # Clean up
            try:
                await w3.provider.session.close()
            except:
                pass
            
            return url, True, response_time, f"Block: {block_number}"
            
        except asyncio.TimeoutError:
            return url, False, 0.0, f"Timeout after {self.timeout}s"
        except Exception as e:
            return url, False, 0.0, str(e)
    
    async def check_all_rpcs(self, chains: List[str] = None) -> Dict[str, Tuple[str, bool, float, str]]:
        """
        Check all RPC endpoints
        
        Args:
            chains: List of chains to check (None = all)
            
        Returns:
            Dict mapping chain names to test results
        """
        await self.load_config()
        rpcs = self.get_primary_rpcs()
        
        if chains:
            rpcs = {k: v for k, v in rpcs.items() if k in chains}
        
        if not rpcs:
            logger.error("No RPC endpoints found to check")
            return {}
        
        logger.info(f"Checking {len(rpcs)} RPC endpoints...")
        
        # Create test tasks
        tasks = []
        for chain, url in rpcs.items():
            tasks.append(self.test_rpc(chain, url))
        
        # Run tests in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Organize results
        final_results = {}
        for i, result in enumerate(results):
            chain = list(rpcs.keys())[i]
            if isinstance(result, Exception):
                final_results[chain] = ("", False, 0.0, str(result))
            else:
                final_results[chain] = result
        
        return final_results
    
    def print_results(self, results: Dict[str, Tuple[str, bool, float, str]], quick: bool = False):
        """Print formatted results"""
        if quick:
            # Quick summary - just status
            print("RPC Health Status:")
            for chain, (url, success, response_time, error) in results.items():
                status = "✅ OK" if success else "❌ FAIL"
                print(f"  {chain:12} {status}")
        else:
            # Detailed results
            print("\n" + "="*60)
            print("RPC HEALTH MONITOR RESULTS")
            print("="*60)
            
            # Sort by success then by response time
            sorted_results = sorted(
                results.items(), 
                key=lambda x: (not x[1][1], x[1][2])
            )
            
            for chain, (url, success, response_time, details) in sorted_results:
                if success:
                    print(f"✅ {chain.upper():12} {response_time:.3f}s - {details}")
                else:
                    print(f"❌ {chain.upper():12} FAILED - {details}")
            
            # Summary
            total = len(results)
            healthy = sum(1 for _, (url, success, _, _) in results.items() if success)
            unhealthy = total - healthy
            
            print(f"\n📊 Summary: {healthy}/{total} healthy, {unhealthy} unhealthy")
            
            if unhealthy > 0:
                print("\n⚠️  Unhealthy RPCs detected. Consider:")
                print("   - Checking network connectivity")
                print("   - Verifying API keys are valid")
                print("   - Trying alternative RPC endpoints")
                print("   - Running: python scripts/rpc_ping_test.py --recommendations")

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Monitor RPC endpoint health")
    parser.add_argument("--chain", help="Check specific chain only (comma-separated for multiple)")
    parser.add_argument("--quick", action="store_true", help="Show quick summary only")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--config", help="Path to config file")
    
    args = parser.parse_args()
    
    # Parse chains
    chains = None
    if args.chain:
        chains = [c.strip() for c in args.chain.split(",")]
    
    # Run health check
    monitor = RPCMonitor(config_path=args.config, timeout=args.timeout)
    results = await monitor.check_all_rpcs(chains=chains)
    
    # Show results
    monitor.print_results(results, quick=args.quick)
    
    # Exit with error code if any RPCs are unhealthy
    unhealthy = sum(1 for _, (url, success, _, _) in results.items() if not success)
    if unhealthy > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
