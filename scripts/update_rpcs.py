#!/usr/bin/env python3
"""
RPC Configuration Updater
Updates RPC URLs with the best performing endpoints based on test results

Usage:
    python scripts/update_rpcs.py [--dry-run] [--backup]
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.logging import get_logger
from config.config_loader import load_yaml_config
import yaml

logger = get_logger('rpc_updater')

# Recommended RPCs based on performance testing
RECOMMENDED_RPCS = {
    'ethereum': 'https://1rpc.io/eth',
    'bsc': 'https://bsc.llamarpc.com',
    'polygon': 'https://polygon.llamarpc.com',
    'arbitrum': 'https://arbitrum.publicnode.com',
    'base': 'https://base.publicnode.com',
    'optimism': 'https://mainnet.optimism.io',
    'avalanche': 'https://avax.publicnode.com',
    'fantom': 'https://rpc.ftm.tools',
    'gnosis': 'https://rpc.gnosischain.com',
    'solana': 'https://api.mainnet-beta.solana.com',
    'bitcoin': 'https://mempool.space/api',
}

def backup_config(config_path: Path) -> Path:
    """Create a backup of the config file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config_path.parent / f"{config_path.stem}_backup_{timestamp}{config_path.suffix}"
    
    shutil.copy2(config_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    return backup_path

def update_rpc_urls(config: dict, dry_run: bool = False) -> dict:
    """Update RPC URLs with recommended ones"""
    updated_config = config.copy()
    networks = updated_config.get('networks', {})
    updated_networks = 0
    
    for chain_name, recommended_url in RECOMMENDED_RPCS.items():
        if chain_name in networks:
            chain_config = networks[chain_name]
            if isinstance(chain_config, dict):
                current_url = chain_config.get('rpc')
                
                if current_url != recommended_url:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would update {chain_name}: {current_url} -> {recommended_url}")
                    else:
                        logger.info(f"Updating {chain_name}: {current_url} -> {recommended_url}")
                        chain_config['rpc'] = recommended_url
                        updated_networks += 1
                else:
                    logger.debug(f"{chain_name} already has recommended RPC")
            else:
                logger.warning(f"Invalid config for {chain_name}, skipping")
        else:
            logger.debug(f"Chain {chain_name} not found in config, skipping")
    
    if not dry_run and updated_networks > 0:
        logger.info(f"Updated {updated_networks} RPC URLs")
    
    return updated_config

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Update RPC URLs with recommended endpoints")
    parser.add_argument("--config", default="config/config_unified.yaml", help="Path to config file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    parser.add_argument("--backup", action="store_true", help="Create backup before updating")
    parser.add_argument("--list", action="store_true", help="List recommended RPCs")
    
    args = parser.parse_args()
    
    if args.list:
        print("Recommended RPC URLs:")
        print("=" * 40)
        for chain, url in RECOMMENDED_RPCS.items():
            print(f"{chain:12} {url}")
        return
    
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    
    try:
        # Load current config
        config = load_yaml_config(str(config_path))
        logger.info(f"Loaded config from {config_path}")
        
        # Update RPC URLs
        updated_config = update_rpc_urls(config, dry_run=args.dry_run)
        
        if args.dry_run:
            logger.info("Dry run completed - no changes made")
            return
        
        # Create backup if requested
        if args.backup:
            backup_path = backup_config(config_path)
        
        # Save updated config
        with open(config_path, 'w') as f:
            yaml.dump(updated_config, f, default_flow_style=False, sort_keys=False, indent=2)
        
        logger.info(f"Updated config saved to {config_path}")
        
        # Show summary
        networks = config.get('networks', {})
        updated_count = sum(1 for chain in RECOMMENDED_RPCS.keys() 
                           if chain in networks and networks[chain].get('rpc') != RECOMMENDED_RPCS[chain])
        
        if updated_count > 0:
            print(f"\n✅ Updated {updated_count} RPC URLs")
            print("💡 Run 'python scripts/rpc_monitor.py' to verify the changes")
        else:
            print("\nℹ️  All RPCs are already using recommended URLs")
            
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
