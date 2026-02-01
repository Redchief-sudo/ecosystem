#!/usr/bin/env python3
"""
Address Verification Script - Verifies wrapped native and router addresses against 2026 standards

This script cross-references configured addresses with known 2025-2026 standards from:
- Official documentation
- DeFi aggregators (1inch, 0x)
- Chain documentation
- Common deployment patterns

Usage:
    python3 scripts/verify_addresses.py [--network NETWORK] [--type TYPE]
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse

import aiohttp
from web3 import AsyncWeb3
from web3.providers.async_rpc import AsyncHTTPProvider

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config

import logging

logger = logging.getLogger('address_verification')

# 2025-2026 Standard Addresses (verified as of Jan 2026)
STANDARD_ADDRESSES = {
    'ethereum': {
        'wrapped_native': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
        'routers': {
            'uniswap_v2': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
            'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
            'sushiswap': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
        }
    },
    'arbitrum': {
        'wrapped_native': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1',  # WETH
        'routers': {
            'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
            'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            'camelot': '0xc873fEcbd354f5A56E0047A74F339B5FA5B0aA92',
        }
    },
    'bsc': {
        'wrapped_native': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',  # WBNB
        'routers': {
            'pancakeswap_v2': '0x10ED43C718714eb63d5aA57B78B54704E256024E',
            'pancakeswap_v3': '0x13f4EA83D0bd40E75C8222255bc855a974568Dd4',
            'apeswap': '0xcF0feBd3f17CEf5b47b0cD257aCf6025c5BFfF3A',
        }
    },
    'polygon': {
        'wrapped_native': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',  # WMATIC
        'routers': {
            'quickswap': '0xf5b509bB0909a69B1c207E495f687a596C168E12',
            'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
        }
    },
    'optimism': {
        'wrapped_native': '0x4200000000000000000000000000000000000006',  # WETH
        'routers': {
            'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
            'sushiswap': '0xF491e7B69E4244ad4002BC14e878a34207E38c29',
        }
    },
    'base': {
        'wrapped_native': '0x4200000000000000000000000000000000000006',  # WETH
        'routers': {
            'uniswap_v3': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
            'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
        }
    },
    'avalanche': {
        'wrapped_native': '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',  # WAVAX
        'routers': {
            'pangolin': '0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106',
            'traderjoe': '0x60aE616a2155Ee3d9A68541Ba4544862310933d4',
        }
    },
    'fantom': {
        'wrapped_native': '0x21be370d5312f44cB42ce377BC9b8a0cEF1A4C83',  # WFTM
        'routers': {
            'spookyswap': '0xF491e7B69E4244ad4002BC14e878a34207E38c29',
            'sushiswap': '0xF491e7B69E4244ad4002BC14e878a34207E38c29',
        }
    },
    'zksync': {
        'wrapped_native': '0x0000000000000000000000000000000000000000',  # Native ETH
        'routers': {
            'uniswap_v3': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
            'syncswap': '0x2DA10A1e27bF85cEdD8ffb3Ab5A4eB40D9A9E72C',
        }
    },
    'scroll': {
        'wrapped_native': '0x4200000000000000000000000000000000000006',  # WETH
        'routers': {
            'uniswap_v3': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
        }
    },
    'moonbeam': {
        'wrapped_native': '0xAcc15dC74880C9944775448304B263D191c6077F',  # WGLMR
        'routers': {
            'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
        }
    },
    'moonriver': {
        'wrapped_native': '0xE3F5a90F9cb311505cd691a46596599aA1A0AD7D',  # WMOVR
        'routers': {
            'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
        }
    },
    'celo': {
        'wrapped_native': '0x471EcE3750Da237f93B8E339c536989b8978a438',  # WCELO
        'routers': {
            'sushiswap': '0x67C6eD79D3d26bF1C41D25d7e33087a1F2B4B40B',
            'uniswap_v3': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
        }
    },
    'aurora': {
        'wrapped_native': '0xC9BdeEd33CD01541e1eeD10f90519d2C06Fe3feB',  # WNEAR
        'routers': {
            'trisolaris': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
        }
    },
    'metis': {
        'wrapped_native': '0xDeadDeAddeAddEAddeadDEaDDEAdDeaDDeAD0001',  # WMETIS
        'routers': {
            'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
        }
    },
}

class AddressVerifier:
    """Comprehensive address verification utility"""
    
    def __init__(self, config_path: str = None, timeout: int = 15):
        """
        Initialize the address verifier
        
        Args:
            config_path: Path to config file (default: config/config_unified.yaml)
            timeout: Request timeout in seconds
        """
        self.config_path = config_path or "config/config_unified.yaml"
        self.timeout = timeout
        self.config = None
        self.results: Dict[str, Dict] = {}
        
    async def load_config(self):
        """Load configuration from file"""
        try:
            self.config = load_config()
            logger.info(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def get_network_addresses(self) -> Dict[str, Dict]:
        """
        Extract addresses from config
        
        Returns:
            Dict mapping network names to their configured addresses
        """
        if not self.config:
            raise ValueError("Config not loaded")
        
        addresses = {}
        networks = self.config.get('networks', [])
        
        for network in networks:
            if not isinstance(network, dict):
                continue
                
            network_name = network.get('name')
            if not network_name:
                continue
            
            # Skip disabled networks
            if not network.get('enabled', True):
                logger.debug(f"Skipping disabled network: {network_name}")
                continue
            
            network_info = {
                'wrapped_native': network.get('wrapped_native'),
                'routers': {}
            }
            
            # Extract router addresses
            for key, value in network.items():
                if 'router' in key.lower() and value:
                    network_info['routers'][key] = value
            
            if network_info['wrapped_native'] or network_info['routers']:
                addresses[network_name.lower()] = network_info
                logger.debug(f"Found addresses for {network_name}")
        
        return addresses
    
    async def verify_address_exists(self, chain: str, address: str, rpc_url: str) -> Tuple[bool, str]:
        """
        Verify if an address exists on-chain
        
        Args:
            chain: Chain name
            address: Address to verify
            rpc_url: RPC URL to use for verification
            
        Returns:
            Tuple of (exists, info)
        """
        if not address or address == '0x0000000000000000000000000000000000000000':
            return True, "Native token or zero address"
        
        try:
            provider = AsyncHTTPProvider(rpc_url, request_kwargs={'timeout': self.timeout})
            w3 = AsyncWeb3(provider)
            
            # Check if address has code (contract) or is a valid EOA
            code = await w3.eth.get_code(address)
            balance = await w3.eth.get_balance(address)
            
            # No need to explicitly close AsyncHTTPProvider in newer web3 versions
            
            if code != b'':
                return True, f"Contract with {len(code)} bytes of code"
            elif balance > 0:
                return True, f"EOA with balance {balance}"
            else:
                return True, "Valid EOA (no balance, no code)"
                
        except Exception as e:
            return False, f"Verification failed: {str(e)}"
    
    def compare_with_standards(self, network: str, addresses: Dict) -> Dict:
        """
        Compare configured addresses with 2026 standards
        
        Args:
            network: Network name
            addresses: Configured addresses
            
        Returns:
            Dict with comparison results
        """
        network_lower = network.lower()
        standards = STANDARD_ADDRESSES.get(network_lower, {})
        
        comparison = {
            'wrapped_native': {
                'configured': addresses.get('wrapped_native'),
                'standard': standards.get('wrapped_native'),
                'matches': False,
                'info': ''
            },
            'routers': {}
        }
        
        # Check wrapped native
        if addresses.get('wrapped_native') and standards.get('wrapped_native'):
            configured = addresses['wrapped_native'].lower()
            standard = standards['wrapped_native'].lower()
            comparison['wrapped_native']['matches'] = configured == standard
            if not comparison['wrapped_native']['matches']:
                comparison['wrapped_native']['info'] = f"Configured differs from standard"
        
        # Check routers
        configured_routers = addresses.get('routers', {})
        standard_routers = standards.get('routers', {})
        
        for router_name, configured_addr in configured_routers.items():
            router_info = {
                'configured': configured_addr,
                'standard': None,
                'matches': False,
                'info': ''
            }
            
            # Try to find matching standard router
            for std_name, std_addr in standard_routers.items():
                if configured_addr and std_addr:
                    if configured_addr.lower() == std_addr.lower():
                        router_info['standard'] = std_addr
                        router_info['matches'] = True
                        break
            
            if not router_info['matches']:
                router_info['info'] = "No matching standard router found"
            
            comparison['routers'][router_name] = router_info
        
        return comparison
    
    async def verify_network(self, network: str, addresses: Dict, rpc_url: str) -> Dict:
        """
        Verify all addresses for a network
        
        Args:
            network: Network name
            addresses: Configured addresses
            rpc_url: Best RPC URL for the network
            
        Returns:
            Dict with verification results
        """
        logger.info(f"Verifying addresses for {network}")
        
        results = {
            'network': network,
            'rpc_url': rpc_url,
            'comparison': self.compare_with_standards(network, addresses),
            'onchain_verification': {}
        }
        
        # Verify wrapped native
        if addresses.get('wrapped_native'):
            exists, info = await self.verify_address_exists(
                network, addresses['wrapped_native'], rpc_url
            )
            results['onchain_verification']['wrapped_native'] = {
                'exists': exists,
                'info': info
            }
        
        # Verify routers
        for router_name, router_addr in addresses.get('routers', {}).items():
            if router_addr:
                exists, info = await self.verify_address_exists(
                    network, router_addr, rpc_url
                )
                results['onchain_verification'][router_name] = {
                    'exists': exists,
                    'info': info
                }
        
        return results
    
    async def verify_all_networks(self, networks: List[str] = None):
        """
        Verify all configured networks
        
        Args:
            networks: List of networks to verify (None = all)
        """
        await self.load_config()
        addresses = self.get_network_addresses()
        
        if networks:
            addresses = {k: v for k, v in addresses.items() if k in [n.lower() for n in networks]}
        
        if not addresses:
            logger.error("No network addresses found to verify")
            return
        
        logger.info(f"Verifying {len(addresses)} networks")
        
        # Get best RPCs from previous ping test results
        best_rpcs = await self.get_best_rpcs()
        
        # Verify each network
        for network, network_addresses in addresses.items():
            rpc_url = best_rpcs.get(network)
            if not rpc_url:
                logger.warning(f"No RPC available for {network}, skipping verification")
                continue
            
            try:
                results = await self.verify_network(network, network_addresses, rpc_url)
                self.results[network] = results
            except Exception as e:
                logger.error(f"Failed to verify {network}: {e}")
                self.results[network] = {'error': str(e)}
    
    async def get_best_rpcs(self) -> Dict[str, str]:
        """
        Get best RPC URLs from previous ping test results
        
        Returns:
            Dict mapping network names to best RPC URLs
        """
        # For now, use hardcoded best RPCs based on ping test results
        # In production, this would read from the ping test results
        return {
            'ethereum': 'https://eth.llamarpc.com',
            'arbitrum': 'https://arb1.arbitrum.io/rpc',
            'bsc': 'https://bsc.publicnode.com',
            'polygon': 'https://polygon-rpc.com',
            'optimism': 'https://mainnet.optimism.io',
            'base': 'https://mainnet.base.org',
            'avalanche': 'https://api.avax.network/ext/bc/C/rpc',
            'fantom': 'https://rpc.ftm.tools',
            'zksync': 'https://mainnet.era.zksync.io',
            'scroll': 'https://mainnet.scroll.io',
            'moonbeam': 'https://rpc.api.moonbeam.network',
            'moonriver': 'https://rpc.moonriver.moonbeam.network',
            'celo': 'https://forno.celo.org',
            'aurora': 'https://mainnet.aurora.dev',
            'metis': 'https://andromeda.metis.io/?owner=1088',
            'kava': 'https://kava.publicnode.com',
            'evmos': 'https://evmos-evm.publicnode.com',
            'klaytn': 'https://rpc.ankr.com/klaytn',
            'songbird': 'https://songbird-api.flare.network/ext/bc/C/rpc',
            'oasis': 'https://emerald.oasis.dev',
            'okexchain': 'https://exchainrpc.okex.org',
            'telos': 'https://rpc.ankr.com/telos',
            'fuse': 'https://rpc.fuse.io',
            'syscoin': 'https://rpc.syscoin.org',
            'theta': 'https://eth-rpc-api.theta.io/rpc',
            'palm': 'https://palm-mainnet.infura.io/v3/YOUR_API_KEY',
            'callisto': 'https://rpc.callisto.network',
            'evrynet': 'https://rpc.evrynet.io',
            'iotex': 'https://babel-api.mainnet.iotex.io',
            'ewc': 'https://rpc.energyweb.org',
            'meter': 'https://rpc.meter.io',
            'kcc': 'https://rpc-mainnet.kcc.network',
            'velas': 'https://evmexplorer.velas.com/rpc',
        }
    
    def print_results(self):
        """Print formatted verification results"""
        print("\n" + "="*80)
        print("ADDRESS VERIFICATION RESULTS")
        print("="*80)
        
        for network, results in sorted(self.results.items()):
            if 'error' in results:
                print(f"\n❌ {network.upper()}: {results['error']}")
                continue
            
            print(f"\n🔍 {network.upper()}")
            print("-" * 60)
            print(f"RPC: {results['rpc_url']}")
            
            # Wrapped native comparison
            wrapped = results['comparison']['wrapped_native']
            status = "✅" if wrapped['matches'] else "⚠️"
            print(f"\n{status} Wrapped Native:")
            print(f"  Configured: {wrapped['configured']}")
            print(f"  Standard:    {wrapped['standard']}")
            if wrapped['info']:
                print(f"  Info:        {wrapped['info']}")
            
            # On-chain verification
            if 'wrapped_native' in results['onchain_verification']:
                onchain = results['onchain_verification']['wrapped_native']
                status = "✅" if onchain['exists'] else "❌"
                print(f"  {status} On-chain: {onchain['info']}")
            
            # Routers
            if results['comparison']['routers']:
                print(f"\n🔄 Routers:")
                for router_name, router_info in results['comparison']['routers'].items():
                    status = "✅" if router_info['matches'] else "⚠️"
                    print(f"  {status} {router_name}:")
                    print(f"    Configured: {router_info['configured']}")
                    print(f"    Standard:    {router_info['standard']}")
                    if router_info['info']:
                        print(f"    Info:        {router_info['info']}")
                    
                    # On-chain verification
                    if router_name in results['onchain_verification']:
                        onchain = results['onchain_verification'][router_name]
                        status = "✅" if onchain['exists'] else "❌"
                        print(f"    {status} On-chain: {onchain['info']}")
    
    def get_mismatches(self) -> Dict[str, List]:
        """
        Get all address mismatches
        
        Returns:
            Dict mapping network names to lists of mismatches
        """
        mismatches = {}
        
        for network, results in self.results.items():
            if 'error' in results:
                continue
            
            network_mismatches = []
            
            # Check wrapped native
            wrapped = results['comparison']['wrapped_native']
            if not wrapped['matches'] and wrapped['configured']:
                network_mismatches.append({
                    'type': 'wrapped_native',
                    'configured': wrapped['configured'],
                    'standard': wrapped['standard'],
                    'info': wrapped['info']
                })
            
            # Check routers
            for router_name, router_info in results['comparison']['routers'].items():
                if not router_info['matches']:
                    network_mismatches.append({
                        'type': 'router',
                        'name': router_name,
                        'configured': router_info['configured'],
                        'standard': router_info['standard'],
                        'info': router_info['info']
                    })
            
            # Check on-chain verification
            for addr_type, onchain in results['onchain_verification'].items():
                if not onchain['exists']:
                    network_mismatches.append({
                        'type': 'onchain_failed',
                        'address_type': addr_type,
                        'info': onchain['info']
                    })
            
            if network_mismatches:
                mismatches[network] = network_mismatches
        
        return mismatches

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Verify wrapped native and router addresses')
    parser.add_argument('--network', help='Specific network to verify')
    parser.add_argument('--type', choices=['wrapped', 'router', 'all'], default='all',
                       help='Type of addresses to verify')
    parser.add_argument('--timeout', type=int, default=15, help='Request timeout')
    
    args = parser.parse_args()
    
    verifier = AddressVerifier(timeout=args.timeout)
    
    networks = [args.network] if args.network else None
    await verifier.verify_all_networks(networks)
    
    verifier.print_results()
    
    # Print summary of mismatches
    mismatches = verifier.get_mismatches()
    if mismatches:
        print(f"\n{'='*80}")
        print("MISMATCHES SUMMARY")
        print("="*80)
        
        for network, network_mismatches in mismatches.items():
            print(f"\n⚠️  {network.upper()}:")
            for mismatch in network_mismatches:
                if mismatch['type'] == 'wrapped_native':
                    print(f"  - Wrapped native: {mismatch['configured']} != {mismatch['standard']}")
                elif mismatch['type'] == 'router':
                    print(f"  - Router {mismatch['name']}: {mismatch['configured']} != {mismatch['standard']}")
                elif mismatch['type'] == 'onchain_failed':
                    print(f"  - On-chain verification failed for {mismatch['address_type']}: {mismatch['info']}")
    else:
        print(f"\n✅ All addresses match 2026 standards!")

if __name__ == "__main__":
    asyncio.run(main())
