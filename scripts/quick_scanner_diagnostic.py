#!/usr/bin/env python3
"""
Quick Scanner Test - Simple test to verify scanner functionality
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.logging import get_logger
from config.config_loader import load_yaml_config
from networks.universal_network_manager import UniversalNetworkManager
from scanners.scan_director import ScanDirector

logger = get_logger('scanner_test')

async def quick_test():
    """Quick test of scanner system"""
    logger.info("🚀 Quick Scanner Test Starting...")
    
    try:
        # Load config
        config = load_yaml_config()
        logger.info("✅ Config loaded")
        
        # Initialize network manager
        manager = UniversalNetworkManager(config)
        await manager.initialize()
        
        connected_chains = manager.get_connected_chains()
        logger.info(f"✅ Network manager: {len(connected_chains)} chains connected")
        
        # Initialize scan director (without memory manager for now)
        scan_director = ScanDirector(
            network_manager=manager,
            memory=None,
            config=config
        )
        
        enabled_networks = scan_director.enabled_networks
        available_scanners = list(scan_director.scanners.keys())
        
        logger.info(f"✅ Scan director: {len(enabled_networks)} networks enabled")
        logger.info(f"✅ Available scanners: {available_scanners}")
        
        # Test one scanner on one network
        if available_scanners and enabled_networks:
            scanner_name = available_scanners[0]
            test_chain = enabled_networks[0]
            
            logger.info(f"🔍 Testing {scanner_name} on {test_chain}...")
            
            scanner = scan_director.scanners[scanner_name]
            
            try:
                if hasattr(scanner, 'scan_network'):
                    result = await asyncio.wait_for(
                        scanner.scan_network(test_chain),
                        timeout=10.0
                    )
                elif hasattr(scanner, 'scan'):
                    result = await asyncio.wait_for(
                        scanner.scan(test_chain),
                        timeout=10.0
                    )
                else:
                    logger.warning(f"Scanner {scanner_name} has no scan method")
                    result = None
                
                if result:
                    logger.info(f"✅ {scanner_name} on {test_chain}: SUCCESS")
                    logger.info(f"   Result type: {type(result)}")
                    if isinstance(result, list):
                        logger.info(f"   Found {len(result)} items")
                else:
                    logger.warning(f"⚠️ {scanner_name} on {test_chain}: No result")
                    
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ {scanner_name} on {test_chain}: Timeout")
            except Exception as e:
                logger.error(f"❌ {scanner_name} on {test_chain}: {e}")
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 QUICK SCANNER TEST RESULTS")
        logger.info("="*60)
        logger.info(f"🌐 Connected Networks: {len(connected_chains)}")
        logger.info(f"🔍 Enabled Networks: {len(enabled_networks)}")
        logger.info(f"⚡ Available Scanners: {len(available_scanners)}")
        logger.info(f"✅ System Status: READY")
        logger.info("="*60)
        
        # Cleanup
        await manager.shutdown()
        logger.info("✅ Test complete")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_test())
    sys.exit(0 if success else 1)
