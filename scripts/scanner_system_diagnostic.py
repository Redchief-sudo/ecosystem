#!/usr/bin/env python3
"""
Scanner System Test - Comprehensive testing of scanner functionality
Tests all connected networks with different scanner types
"""
import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, List
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bootstrap.logging import get_logger
from config.config_loader import load_yaml_config
from networks.universal_network_manager import UniversalNetworkManager
from scanners.scan_director import ScanDirector
from utils.memory import MemoryManager

logger = get_logger('scanner_test')

class ScannerSystemTester:
    """Comprehensive scanner system tester"""
    
    def __init__(self, config_path: str = None):
        """Initialize scanner tester"""
        self.config_path = config_path or "config/config_unified.yaml"
        self.config = None
        self.network_manager = None
        self.scan_director = None
        self.memory_manager = None
        
    async def initialize(self):
        """Initialize all components"""
        try:
            # Load configuration
            self.config = load_yaml_config(self.config_path)
            logger.info("✅ Configuration loaded")
            
            # Initialize network manager
            self.network_manager = UniversalNetworkManager(self.config)
            await self.network_manager.initialize()
            logger.info(f"✅ Network manager initialized with {len(self.network_manager.get_connected_chains())} networks")
            
            # Initialize memory manager
            self.memory_manager = MemoryManager(self.config)
            logger.info("✅ Memory manager initialized")
            
            # Initialize scan director
            self.scan_director = ScanDirector(
                network_manager=self.network_manager,
                memory=self.memory_manager,
                config=self.config
            )
            logger.info(f"✅ Scan director initialized with {len(self.scan_director.enabled_networks)} enabled networks")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize scanner system: {e}")
            return False
    
    async def test_network_connectivity(self) -> Dict[str, bool]:
        """Test connectivity for all networks"""
        logger.info("🔍 Testing network connectivity...")
        
        results = {}
        connected_chains = self.network_manager.get_connected_chains()
        
        for chain in connected_chains:
            try:
                client = self.network_manager.get_client(chain)
                if client and client.is_connected:
                    # Try to get latest block
                    block = await client.get_latest_block()
                    results[chain] = True
                    logger.debug(f"✅ {chain}: Block {block}")
                else:
                    results[chain] = False
                    logger.warning(f"❌ {chain}: Client not connected")
            except Exception as e:
                results[chain] = False
                logger.error(f"❌ {chain}: Error - {e}")
        
        success_count = sum(results.values())
        logger.info(f"📊 Network connectivity: {success_count}/{len(results)} networks working")
        
        return results
    
    async def test_scanner_initialization(self) -> Dict[str, bool]:
        """Test scanner initialization"""
        logger.info("🔍 Testing scanner initialization...")
        
        results = {}
        scanners = self.scan_director.scanners
        
        for scanner_name, scanner in scanners.items():
            try:
                # Check if scanner has required methods
                has_scan = hasattr(scanner, 'scan')
                has_scan_network = hasattr(scanner, 'scan_network')
                
                results[scanner_name] = has_scan or has_scan_network
                status = "✅" if results[scanner_name] else "❌"
                logger.debug(f"{status} {scanner_name}: scan={has_scan}, scan_network={has_scan_network}")
                
            except Exception as e:
                results[scanner_name] = False
                logger.error(f"❌ {scanner_name}: Error - {e}")
        
        success_count = sum(results.values())
        logger.info(f"📊 Scanner initialization: {success_count}/{len(results)} scanners working")
        
        return results
    
    async def test_single_network_scan(self, chain: str, scanner_name: str) -> Dict:
        """Test scanning a single network with a single scanner"""
        try:
            scanner = self.scan_director.scanners.get(scanner_name)
            if not scanner:
                return {"success": False, "error": "Scanner not found"}
            
            # Check scanner capabilities
            if hasattr(scanner, 'scan_network'):
                result = await asyncio.wait_for(
                    scanner.scan_network(chain),
                    timeout=30.0
                )
            elif hasattr(scanner, 'scan'):
                # Try the scan method
                result = await asyncio.wait_for(
                    scanner.scan(chain),
                    timeout=30.0
                )
            else:
                return {"success": False, "error": "Scanner has no scan method"}
            
            return {
                "success": True,
                "result": result,
                "chain": chain,
                "scanner": scanner_name
            }
            
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout", "chain": chain, "scanner": scanner_name}
        except Exception as e:
            return {"success": False, "error": str(e), "chain": chain, "scanner": scanner_name}
    
    async def test_scanner_functionality(self, max_networks: int = 5, max_scanners: int = 3) -> Dict[str, Dict]:
        """Test scanner functionality on sample networks"""
        logger.info(f"🔍 Testing scanner functionality (max {max_networks} networks, {max_scanners} scanners)...")
        
        results = {}
        connected_chains = list(self.network_manager.get_connected_chains())
        scanners = list(self.scan_director.scanners.keys())
        
        # Limit test scope to avoid timeouts
        test_chains = connected_chains[:max_networks]
        test_scanners = scanners[:max_scanners]
        
        logger.info(f"Testing chains: {test_chains}")
        logger.info(f"Testing scanners: {test_scanners}")
        
        for chain in test_chains:
            for scanner_name in test_scanners:
                test_key = f"{chain}_{scanner_name}"
                logger.debug(f"Testing {test_key}...")
                
                result = await self.test_single_network_scan(chain, scanner_name)
                results[test_key] = result
                
                if result["success"]:
                    logger.debug(f"✅ {test_key}: Success")
                else:
                    logger.warning(f"❌ {test_key}: {result.get('error', 'Unknown error')}")
        
        # Count successes
        total_tests = len(results)
        successful_tests = sum(1 for r in results.values() if r["success"])
        
        logger.info(f"📊 Scanner functionality: {successful_tests}/{total_tests} tests successful")
        
        return results
    
    async def test_memory_integration(self) -> bool:
        """Test memory manager integration"""
        try:
            # Test memory manager basic functionality
            stats = self.memory_manager.get_memory_stats()
            logger.info(f"✅ Memory manager working: {stats}")
            return True
        except Exception as e:
            logger.error(f"❌ Memory manager error: {e}")
            return False
    
    async def run_comprehensive_test(self, max_networks: int = 3, max_scanners: int = 2):
        """Run comprehensive scanner system test"""
        logger.info("🚀 Starting comprehensive scanner system test...")
        
        # Test 1: Network connectivity
        network_results = await self.test_network_connectivity()
        
        # Test 2: Scanner initialization
        scanner_results = await self.test_scanner_initialization()
        
        # Test 3: Scanner functionality
        functionality_results = await self.test_scanner_functionality(max_networks, max_scanners)
        
        # Test 4: Memory integration
        memory_result = await self.test_memory_integration()
        
        # Generate summary
        logger.info("\n" + "="*80)
        logger.info("📊 SCANNER SYSTEM TEST RESULTS")
        logger.info("="*80)
        
        # Network connectivity summary
        network_success = sum(network_results.values())
        logger.info(f"🌐 Network Connectivity: {network_success}/{len(network_results)} ({network_success/len(network_results)*100:.1f}%)")
        
        # Scanner initialization summary
        scanner_success = sum(scanner_results.values())
        logger.info(f"🔍 Scanner Initialization: {scanner_success}/{len(scanner_results)} ({scanner_success/len(scanner_results)*100:.1f}%)")
        
        # Functionality summary
        func_success = sum(1 for r in functionality_results.values() if r["success"])
        logger.info(f"⚡ Scanner Functionality: {func_success}/{len(functionality_results)} ({func_success/len(functionality_results)*100:.1f}%)")
        
        # Memory integration
        memory_status = "✅" if memory_result else "❌"
        logger.info(f"💾 Memory Integration: {memory_status}")
        
        # Overall assessment
        total_tests = len(network_results) + len(scanner_results) + len(functionality_results) + 1
        total_success = network_success + scanner_success + func_success + (1 if memory_result else 0)
        
        logger.info(f"\n🎯 Overall Success Rate: {total_success}/{total_tests} ({total_success/total_tests*100:.1f}%)")
        
        if total_success / total_tests >= 0.8:
            logger.info("🎉 Scanner system is READY for production!")
        else:
            logger.warning("⚠️ Scanner system needs attention before production use")
        
        logger.info("="*80)
        
        return {
            "network_connectivity": network_results,
            "scanner_initialization": scanner_results,
            "scanner_functionality": functionality_results,
            "memory_integration": memory_result,
            "overall_success_rate": total_success / total_tests
        }
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.network_manager:
                await self.network_manager.shutdown()
            logger.info("✅ Cleanup complete")
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test scanner system functionality")
    parser.add_argument("--max-networks", type=int, default=3, help="Maximum networks to test")
    parser.add_argument("--max-scanners", type=int, default=2, help="Maximum scanners to test")
    parser.add_argument("--config", help="Path to config file")
    
    args = parser.parse_args()
    
    tester = ScannerSystemTester(config_path=args.config)
    
    try:
        # Initialize
        if not await tester.initialize():
            sys.exit(1)
        
        # Run comprehensive test
        await tester.run_comprehensive_test(args.max_networks, args.max_scanners)
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
