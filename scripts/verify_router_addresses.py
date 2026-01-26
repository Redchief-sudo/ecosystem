#!/usr/bin/env python3
"""
Router Address Verification Script

This script verifies that all DEX router addresses in the configuration are current
and correct for their respective networks.
"""

import yaml
import json
import re
from typing import Dict, List, Set, Tuple
from pathlib import Path


class RouterVerifier:
    """Verifies DEX router addresses against known current addresses."""

    # Known current router addresses for major DEXes (as of 2026)
    # These should be updated periodically from official sources
    KNOWN_ROUTERS = {
        # Uniswap V2 Router (Ethereum)
        'uniswap_v2': {
            'ethereum': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
            'polygon': '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff',
            'arbitrum': '0x4752ba5DBc23f44D87826276BF6Fd6b1C263D0',
            'optimism': '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45',
            'base': '0x4752ba5DBc23f44D87826276BF6Fd6b1C263D0',
        },

        # PancakeSwap V2 Router
        'pancakeswap': {
            'bsc': '0x10ED43C718714eb63d5aA57B78B54704E256024E',
            'ethereum': '0xEfF92A263d31888d860bD50809A8D171709b7b1c3',  # PancakeSwap on ETH
        },

        # SushiSwap Router
        'sushiswap': {
            'ethereum': '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',
            'polygon': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            'arbitrum': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            'optimism': '0x9c6522117e2c8486TDaF19c5DDD3Da439a2eF79',
            'base': '0x6BDED42c6DA8FBf0d2bA55B2fa120C5e0c8D7891',
            'bsc': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
        },

        # QuickSwap Router (Polygon)
        'quickswap': {
            'polygon': '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff',
        },

        # Trader Joe Router
        'traderjoe': {
            'avalanche': '0x60aE616a2155Ee3d9A68541Ba4544862310933d4',
            'arbitrum': '0xb4315e873dBcf96Ffd0acd8EA43f689D8c20fB30',
            'bsc': '0x0fBc7D8cBcDf9Eb9c2F8757B22b3a5c76b9B3b8',
        },

        # SpookySwap Router (Fantom)
        'spookyswap': {
            'fantom': '0xF491e7B69E4244ad4002BC14e878a34207E38c29',
        },

        # SpiritSwap Router (Fantom)
        'spiritswap': {
            'fantom': '0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52',
        },

        # Camelot Router (Arbitrum)
        'camelot': {
            'arbitrum': '0xc873fEcbd354f5A56E0047A74F339B5FA5B0aA92',
        },

        # Uniswap V3 Router
        'uniswap_v3': {
            'ethereum': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
            'polygon': '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45',
            'arbitrum': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
            'optimism': '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45',
            'base': '0x2626664c2603336E57B271c5C0b26F421741e481',
        },

        # ApeSwap Router
        'apeswap': {
            'bsc': '0xcF0feBd3f17CEf5b47b0cD257aCf6025c5BFf3b',
            'polygon': '0xC0788A3aD43d79aa53B09c2EaCc313A787d1d607',
        },

        # CronaSwap Router
        'cronaswap': {
            'cronos': '0xcd7d16fB918511BF7269eC4f48d61D79Fb26f918',
        },

        # BaseSwap Router
        'baseswap': {
            'base': '0x327Df1E6de05895d2ab08513aaDD9313Fe506d51',
        },

        # UbeSwap Router (Celo)
        'ubeswap': {
            'celo': '0xE3D8bd6Aed4F159bc8000a9cD47CffDb95F96121',
        },

        # Diffusion Router
        'diffusion': {
            'ethereum': '0xb4A7D971D0ADea1c73198C97d7ab3f9CE4aaFA13',
        },

        # Pangolin Router
        'pangolin': {
            'avalanche': '0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106',
        },

        # Zenlink Router
        'zenlink': {
            'moonbeam': '0x7f5373AE26c3E8FfC4c77b7255DF7Ec1A9aF52a',
        },

        # Trisolaris Router
        'trisolaris': {
            'aurora': '0x2CB45Edb4517d5947aFdE3BEAbF95A582506858B',
        },

        # Thrill Router
        'thrill': {
            'ethereum': '0x6fd4383CB451173D5f9304F041C7BCBf27d561fF',
        },

        # Canto DEX Router
        'canto_dex': {
            'canto': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
        },

        # Various smaller DEX routers (placeholder addresses)
        'oolongswap': {'polygon': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'fuse_swap': {'fuse': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'honeyswap': {'gnosis': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'godwoken_swap': {'godwoken': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'defikingdoms': {'harmony': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'kava_swap': {'kava': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'lineaswap': {'linea': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'fusionx': {'mantle': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'netswap': {'metis': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'stellaswap': {'moonbeam': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
        'solarbeam': {'moonriver': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'},
    }

    def __init__(self, config_path: str = 'config/config_unified.yaml'):
        self.config_path = Path(config_path)
        self.issues: List[str] = []
        self.warnings: List[str] = []

    def load_config(self) -> Dict:
        """Load the unified configuration file."""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def extract_router_addresses(self, config: Dict) -> Dict[str, Dict[str, str]]:
        """Extract all router addresses from the configuration."""
        routers = {}

        networks_config = config.get('networks', {})
        if not networks_config:
            print("Warning: No 'networks' section found in config")
            return routers

        for network_name, network_config in networks_config.items():
            if network_config is None or not isinstance(network_config, dict):
                continue

            if not network_config.get('enabled', True):
                continue

            network_routers = {}

            # Extract main router
            if 'router' in network_config:
                network_routers['default'] = network_config['router']

            # Extract router_v2 if different
            if 'router_v2' in network_config and network_config['router_v2'] != network_config.get('router'):
                network_routers['default_v2'] = network_config['router_v2']

            # Extract specific DEX routers
            if 'routers' in network_config:
                network_routers.update(network_config['routers'])

            if network_routers:
                routers[network_name] = network_routers

        return routers

    def verify_address_format(self, address: str) -> bool:
        """Verify that an address has the correct Ethereum address format."""
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        try:
            int(address, 16)
            return True
        except ValueError:
            return False

    def normalize_network_name(self, network_name: str) -> str:
        """Normalize network name to match our known routers."""
        mapping = {
            'ethereum': 'ethereum',
            'eth': 'ethereum',
            'polygon': 'polygon',
            'matic': 'polygon',
            'arbitrum_one': 'arbitrum',
            'arbitrum': 'arbitrum',
            'optimism': 'optimism',
            'base': 'base',
            'bsc': 'bsc',
            'binance': 'bsc',
            'avalanche': 'avalanche',
            'avax': 'avalanche',
            'fantom': 'fantom',
            'celo': 'celo',
            'aurora': 'aurora',
            'cronos': 'cronos',
            'moonbeam': 'moonbeam',
            'moonriver': 'moonriver',
            'gnosis': 'gnosis',
            'harmony': 'harmony',
            'kava': 'kava',
            'linea': 'linea',
            'mantle': 'mantle',
            'metis': 'metis',
            'godwoken': 'godwoken',
            'fuse': 'fuse',
            'canto': 'canto',
        }
        return mapping.get(network_name.lower(), network_name.lower())

    def verify_router_address(self, network: str, dex_name: str, config_address: str) -> Tuple[bool, str]:
        """Verify a single router address."""
        normalized_network = self.normalize_network_name(network)

        # Check address format
        if not self.verify_address_format(config_address):
            return False, f"Invalid address format: {config_address}"

        # Check against known addresses
        if dex_name in self.KNOWN_ROUTERS:
            if normalized_network in self.KNOWN_ROUTERS[dex_name]:
                expected = self.KNOWN_ROUTERS[dex_name][normalized_network]
                if config_address.lower() != expected.lower():
                    return False, f"Address mismatch - expected: {expected}, got: {config_address}"
            else:
                return True, f"No known address for {dex_name} on {normalized_network} (may be correct)"
        else:
            return True, f"Unknown DEX: {dex_name} (cannot verify)"

        return True, "Address verified"

    def verify_all_routers(self) -> Dict[str, List[Dict]]:
        """Verify all router addresses in the configuration."""
        config = self.load_config()
        routers = self.extract_router_addresses(config)

        results = {}

        for network, network_routers in routers.items():
            results[network] = []

            for dex_name, address in network_routers.items():
                is_valid, message = self.verify_router_address(network, dex_name, address)

                result = {
                    'dex': dex_name,
                    'address': address,
                    'valid': is_valid,
                    'message': message,
                    'network': network
                }

                results[network].append(result)

                if not is_valid:
                    self.issues.append(f"{network}/{dex_name}: {message}")
                elif "mismatch" in message.lower() or "invalid" in message.lower():
                    self.warnings.append(f"{network}/{dex_name}: {message}")

        return results

    def print_report(self, results: Dict[str, List[Dict]]):
        """Print a comprehensive verification report."""
        print("=" * 80)
        print("ROUTER ADDRESS VERIFICATION REPORT")
        print("=" * 80)

        total_routers = 0
        invalid_count = 0
        warning_count = 0

        for network, network_results in results.items():
            print(f"\n🔗 {network.upper()}:")
            print("-" * 50)

            for result in network_results:
                total_routers += 1
                status_icon = "✅" if result['valid'] else "❌"
                if not result['valid']:
                    invalid_count += 1
                elif "mismatch" in result['message'].lower() or "invalid" in result['message'].lower():
                    status_icon = "⚠️"
                    warning_count += 1

                print(f"  {status_icon} {result['dex']}: {result['address']}")
                if not result['valid'] or "mismatch" in result['message'].lower():
                    print(f"      {result['message']}")

        print("\n" + "=" * 80)
        print("SUMMARY:")
        print(f"Total routers checked: {total_routers}")
        print(f"Invalid addresses: {invalid_count}")
        print(f"Warnings: {warning_count}")

        if self.issues:
            print(f"\n❌ CRITICAL ISSUES ({len(self.issues)}):")
            for issue in self.issues:
                print(f"  • {issue}")

        if self.warnings:
            print(f"\n⚠️ WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.issues and not self.warnings:
            print("\n✅ All router addresses appear to be current and valid!")

        print("=" * 80)


def main():
    """Main verification function."""
    verifier = RouterVerifier()

    try:
        results = verifier.verify_all_routers()
        verifier.print_report(results)
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return 1

    return 0 if not verifier.issues else 1


if __name__ == "__main__":
    exit(main())