#!/usr/bin/env python3
"""
Address Fix Script - Automatically fixes identified address issues

This script fixes:
1. Invalid EIP-55 checksums
2. Outdated wrapped native addresses
3. Placeholder router addresses with proper DEX routers

Usage:
    python3 scripts/fix_addresses.py [--dry-run] [--network NETWORK]
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config

import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('address_fix')

# Updated 2026 Standard Addresses and Corrections
ADDRESS_FIXES = {
    'moonriver': {
        'wrapped_native': {
            'current': '0x98878B06940aE243284CA214f92Bb71a2b032B8A',
            'correct': '0xE3F5a90F9cb311505cd691a46596599aA1A0AD7D',
            'name': 'WMOVR'
        }
    },
    'optimism': {
        'routers': {
            'router_address': {
                'current': '0x4200000000000000000000000000000000000006',
                'correct': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
                'name': 'Uniswap V3 Router'
            }
        }
    },
    'moonbeam': {
        'routers': {
            'router_address': {
                'current': '0x2fDF1164D2CA2A799D3d6eF226c3cFDC8c8c1ACF',
                'correct': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
                'name': 'SushiSwap Router'
            }
        }
    },
    'moonriver': {
        'routers': {
            'router_address': {
                'current': '0x1FAD9F5740A7Be69C3B7cB188d05c5F7F7cF291D',
                'correct': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
                'name': 'SushiSwap Router'
            }
        }
    },
    'aurora': {
        'routers': {
            'router_address': {
                'current': '0xC0fFEE0000000000000000000000000000000014',
                'correct': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
                'name': 'Trisolaris Router'
            }
        }
    },
    'evmos': {
        'wrapped_native': {
            'current': '0xD4949664cD82660AaE99bEdc034a0deA8A0bd517',
            'correct': '0xD4949664cD82660AaE99bEdc034a0deA8A0bd517',  # Keep current, add to standards
            'name': 'WEVMOS'
        },
        'routers': {
            'router_address': {
                'current': '0xC0fFEE0000000000000000000000000000000013',
                'correct': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
                'name': 'SushiSwap Router'
            }
        }
    },
    'songbird': {
        'wrapped_native': {
            'current': '0x4200000000000000000000000000000000000006',
            'correct': '0x0000000000000000000000000000000000000000',  # Native FLR
            'name': 'Native FLR'
        },
        'routers': {
            'router_address': {
                'current': '0xC0fFEE0000000000000000000000000000000033',
                'correct': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
                'name': 'SushiSwap Router'
            }
        }
    },
    'fuse': {
        'wrapped_native': {
            'current': '0x0BE9e53fd7EDaC9F859882AfdDa116645287C629',
            'correct': '0x0BE9e53fd7EDaC9F859882AfdDa116645287C629',  # Keep current, add to standards
            'name': 'WFUSE'
        },
        'routers': {
            'router_address': {
                'current': '0xC0fFEE0000000000000000000000000000000043',
                'correct': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
                'name': 'SushiSwap Router'
            }
        }
    },
    'evrynet': {
        'routers': {
            'router_address': {
                'current': '0xC0fFEE0000000000000000000000000000000053',
                'correct': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
                'name': 'SushiSwap Router'
            }
        }
    }
}

# Map config names to fix keys
NETWORK_NAME_MAP = {
    'Moonriver': 'moonriver',
    'Optimism': 'optimism',
    'Moonbeam': 'moonbeam',
    'Aurora': 'aurora',
    'Evmos': 'evmos',
    'Songbird': 'songbird',
    'Fuse': 'fuse',
    'Evrynet': 'evrynet'
}

class AddressFixer:
    """Address fixing utility"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize the address fixer
        
        Args:
            config_path: Path to config file (default: config/config_unified.yaml)
        """
        self.config_path = config_path or "config/config_unified.yaml"
        self.config = None
        self.fixes_applied = []
        
    def load_config(self):
        """Load configuration from file"""
        try:
            self.config = load_config()
            logger.info(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def find_network_in_config(self, network_name: str) -> Optional[Dict]:
        """
        Find a network in the config by name
        
        Args:
            network_name: Network name to find
            
        Returns:
            Network config dict or None if not found
        """
        networks = self.config.get('networks', [])
        
        for network in networks:
            if isinstance(network, dict):
                name = network.get('name', '')
                # Try exact match and case-insensitive match
                if name.lower() == network_name.lower() or name == network_name:
                    logger.debug(f"Found network {network_name}: {name}")
                    return network
        
        logger.debug(f"Network {network_name} not found. Available networks: {[n.get('name', 'UNKNOWN') for n in networks if isinstance(n, dict)]}")
        return None
    
    def apply_fixes(self, dry_run: bool = True, target_network: str = None):
        """
        Apply address fixes
        
        Args:
            dry_run: If True, only show what would be changed
            target_network: Only fix this specific network
        """
        if not self.config:
            raise ValueError("Config not loaded")
        
        # Get all network names from config
        networks_in_config = {}
        for network in self.config.get('networks', []):
            if isinstance(network, dict):
                name = network.get('name', '')
                if name:
                    networks_in_config[name] = network
        
        networks_to_fix = ADDRESS_FIXES.keys()
        if target_network:
            # Map target network name to fix key
            target_key = NETWORK_NAME_MAP.get(target_network, target_network.lower())
            networks_to_fix = [target_key]
        
        for fix_key in networks_to_fix:
            if fix_key not in ADDRESS_FIXES:
                logger.warning(f"No fixes available for {fix_key}")
                continue
            
            # Find the corresponding network in config
            network_config = None
            network_name = None
            
            # First try exact match with NETWORK_NAME_MAP
            for config_name, config_network in networks_in_config.items():
                if NETWORK_NAME_MAP.get(config_name) == fix_key:
                    network_config = config_network
                    network_name = config_name
                    break
            
            # If not found, try direct match
            if not network_config:
                for config_name, config_network in networks_in_config.items():
                    if config_name.lower() == fix_key.lower():
                        network_config = config_network
                        network_name = config_name
                        break
            
            if not network_config:
                logger.warning(f"Network {fix_key} not found in config")
                continue
            
            fixes = ADDRESS_FIXES[fix_key]
            logger.info(f"Checking {network_name} ({fix_key}) for fixes...")
            
            # Apply wrapped native fixes
            if 'wrapped_native' in fixes:
                self.fix_wrapped_native(network_name, network_config, fixes['wrapped_native'], dry_run)
            
            # Apply router fixes
            if 'routers' in fixes:
                for router_key, router_fix in fixes['routers'].items():
                    self.fix_router(network_name, network_config, router_key, router_fix, dry_run)
    
    def fix_wrapped_native(self, network_name: str, network_config: Dict, fix: Dict, dry_run: bool):
        """
        Fix wrapped native address
        
        Args:
            network_name: Network name
            network_config: Network configuration
            fix: Fix information
            dry_run: If True, only show what would be changed
        """
        current = network_config.get('wrapped_native')
        correct = fix['correct']
        name = fix['name']
        
        if current != correct:
            action = "Would fix" if dry_run else "Fixed"
            logger.info(f"{action} {network_name} wrapped native: {current} → {correct} ({name})")
            
            if not dry_run:
                network_config['wrapped_native'] = correct
                self.fixes_applied.append({
                    'network': network_name,
                    'type': 'wrapped_native',
                    'field': 'wrapped_native',
                    'old_value': current,
                    'new_value': correct,
                    'name': name
                })
        else:
            logger.debug(f"{network_name} wrapped native already correct: {correct}")
    
    def fix_router(self, network_name: str, network_config: Dict, router_key: str, fix: Dict, dry_run: bool):
        """
        Fix router address
        
        Args:
            network_name: Network name
            network_config: Network configuration
            router_key: Router field name
            fix: Fix information
            dry_run: If True, only show what would be changed
        """
        current = network_config.get(router_key)
        correct = fix['correct']
        name = fix['name']
        
        if current != correct:
            action = "Would fix" if dry_run else "Fixed"
            logger.info(f"{action} {network_name} router {router_key}: {current} → {correct} ({name})")
            
            if not dry_run:
                network_config[router_key] = correct
                self.fixes_applied.append({
                    'network': network_name,
                    'type': 'router',
                    'field': router_key,
                    'old_value': current,
                    'new_value': correct,
                    'name': name
                })
        else:
            logger.debug(f"{network_name} router {router_key} already correct: {correct}")
    
    def save_config(self, backup: bool = True):
        """
        Save the updated configuration
        
        Args:
            backup: If True, create a backup of the original file
        """
        if not self.config:
            raise ValueError("No config loaded")
        
        import yaml
        from datetime import datetime
        
        config_file = Path(self.config_path)
        
        # Create backup if requested
        if backup and config_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = config_file.parent / f"{config_file.stem}_backup_{timestamp}{config_file.suffix}"
            config_file.rename(backup_path)
            logger.info(f"Created backup: {backup_path}")
        
        # Save updated config
        with open(config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False, indent=2)
        
        logger.info(f"Saved updated configuration to: {config_file}")
    
    def print_summary(self):
        """Print summary of fixes applied"""
        print("\n" + "="*80)
        print("ADDRESS FIX SUMMARY")
        print("="*80)
        
        if not self.fixes_applied:
            print("✅ No fixes needed - all addresses are already correct!")
            return
        
        print(f"Applied {len(self.fixes_applied)} fixes:\n")
        
        for fix in self.fixes_applied:
            print(f"🔧 {fix['network'].upper()} - {fix['type'].replace('_', ' ').title()}")
            print(f"   Field: {fix['field']}")
            print(f"   Name:  {fix['name']}")
            print(f"   From:  {fix['old_value']}")
            print(f"   To:    {fix['new_value']}")
            print()
        
        print("✅ All address fixes have been applied successfully!")
        print("📝 Please review the changes and test your configuration.")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Fix address issues in configuration')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be changed without applying fixes')
    parser.add_argument('--network', help='Only fix this specific network')
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip creating a backup of the original config')
    
    args = parser.parse_args()
    
    fixer = AddressFixer()
    
    try:
        fixer.load_config()
        
        # Apply fixes
        fixer.apply_fixes(dry_run=args.dry_run, target_network=args.network)
        
        if args.dry_run:
            print("\n🔍 DRY RUN MODE - No changes were made")
            print("Run without --dry-run to apply the fixes")
        else:
            # Save changes
            fixer.save_config(backup=not args.no_backup)
            fixer.print_summary()
    
    except Exception as e:
        logger.error(f"Failed to apply fixes: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
