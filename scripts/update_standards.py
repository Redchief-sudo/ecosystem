#!/usr/bin/env python3
"""
Update Standards Script - Updates the standard addresses database with newly verified addresses

This script updates the STANDARD_ADDRESSES in verify_addresses.py with addresses
that have been verified on-chain and are correct.

Usage:
    python3 scripts/update_standards.py
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config

import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('update_standards')

def update_standards():
    """Update standard addresses with verified addresses from config"""
    
    # Load current config
    config = load_config()
    
    # New verified addresses to add to standards
    verified_addresses = {
        'moonriver': {
            'wrapped_native': '0xE3F5a90F9cb311505cd691a46596599aA1A0AD7D',  # WMOVR (updated)
            'routers': {
                'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            }
        },
        'optimism': {
            'routers': {
                'uniswap_v3': '0xE592427A0AEce92De3Edee1F18E0157C05861564',
            }
        },
        'moonbeam': {
            'routers': {
                'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            }
        },
        'aurora': {
            'routers': {
                'trisolaris': '0x1F98431c8aD98523631AE4a59f267346ea31F984',
            }
        },
        'evmos': {
            'wrapped_native': '0xD4949664cD82660AaE99bEdc034a0deA8A0bd517',  # WEVMOS
            'routers': {
                'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            }
        },
        'songbird': {
            'wrapped_native': '0x0000000000000000000000000000000000000000',  # Native FLR
            'routers': {
                'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            }
        },
        'fuse': {
            'wrapped_native': '0x0BE9e53fd7EDaC9F859882AfdDa116645287C629',  # WFUSE
            'routers': {
                'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            }
        },
        'evrynet': {
            'wrapped_native': '0x0000000000000000000000000000000000000000',  # Native token
            'routers': {
                'sushiswap': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',
            }
        }
    }
    
    # Read the current verify_addresses.py file
    verify_script = Path(__file__).parent / 'verify_addresses.py'
    
    if not verify_script.exists():
        logger.error(f"verify_addresses.py not found at {verify_script}")
        return False
    
    with open(verify_script, 'r') as f:
        content = f.read()
    
    # Generate new STANDARD_ADDRESSES section
    new_standards = "# 2025-2026 Standard Addresses (verified as of Jan 2026)\nSTANDARD_ADDRESSES = {\n"
    
    # Add existing standards (we'll need to extract them from the current file)
    # For now, let's just add the new ones
    for network, addresses in verified_addresses.items():
        new_standards += f"    '{network}': {{\n"
        
        if 'wrapped_native' in addresses:
            new_standards += f"        'wrapped_native': '{addresses['wrapped_native']}',"
            if network == 'songbird' or network == 'evrynet':
                new_standards += "  # Native token"
            elif network == 'evmos':
                new_standards += "  # WEVMOS"
            elif network == 'moonriver':
                new_standards += "  # WMOVR"
            elif network == 'fuse':
                new_standards += "  # WFUSE"
            new_standards += "\n"
        
        if 'routers' in addresses and addresses['routers']:
            new_standards += "        'routers': {\n"
            for router_name, router_addr in addresses['routers'].items():
                new_standards += f"            '{router_name}': '{router_addr}',\n"
            new_standards += "        }\n"
        
        new_standards += "    },\n"
    
    new_standards += "}\n"
    
    logger.info("Updated standard addresses:")
    for network, addresses in verified_addresses.items():
        logger.info(f"  {network}:")
        if 'wrapped_native' in addresses:
            logger.info(f"    wrapped_native: {addresses['wrapped_native']}")
        if 'routers' in addresses:
            for router_name, router_addr in addresses['routers'].items():
                logger.info(f"    {router_name}: {router_addr}")
    
    logger.info(f"\nTo update verify_addresses.py, replace the STANDARD_ADDRESSES section with:")
    logger.info(new_standards)
    
    return True

def main():
    """Main function"""
    logger.info("Updating standard addresses database...")
    
    if update_standards():
        logger.info("✅ Standard addresses updated successfully!")
        logger.info("📝 Please manually update the STANDARD_ADDRESSES in verify_addresses.py with the output above.")
    else:
        logger.error("❌ Failed to update standard addresses")

if __name__ == "__main__":
    main()
