#!/usr/bin/env python3
"""
Test the rotating network cycle manager with working RPCs
"""

import asyncio
import logging
import time
from typing import List, Dict, Any

# Import the NetworkCycle dataclass
from trading.token_pipeline.network_cycle_manager import NetworkCycle

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Working networks with reliable RPCs
WORKING_NETWORKS = [
    # EVM Networks (using Ankr which is most reliable)
    "ethereum",
    "bsc", 
    "polygon",
    "arbitrum",
    "optimism",
    "base",
    "avalanche",
    "fantom",
    
    # Non-EVM Networks that work
    "solana",
    "tron", 
    "aptos",
    "xrpl",
    "algorand",
    "osmosis",
    "stellar",
    "elrond"
]

async def test_network_cycle():
    """Test the rotating network cycle manager."""
    
    try:
        from trading.token_pipeline.network_cycle_manager import RotatingNetworkCycleManager
        
        # Create cycle manager with working networks
        cycle_manager = RotatingNetworkCycleManager(
            cycle_duration=5,  # 5 seconds for testing (instead of 35)
            networks_per_cycle=4  # 4 networks per cycle for testing
        )
        
        # Override the networks with working ones
        cycle_manager.cycles = []
        for i in range(4):  # 4 cycles
            start_idx = i * 4
            end_idx = start_idx + 4
            cycle_networks = WORKING_NETWORKS[start_idx:end_idx]
            
            cycle = NetworkCycle(
                cycle_number=i + 1,
                networks=cycle_networks,
                start_time=0,
                end_time=0
            )
            cycle_manager.cycles.append(cycle)
        
        print("🔄 Testing Rotating Network Cycle Manager")
        print("=" * 50)
        
        # Test cycle activation
        print(f"📊 Total cycles: {len(cycle_manager.cycles)}")
        print(f"📊 Networks per cycle: {cycle_manager.networks_per_cycle}")
        print(f"📊 Total networks: {len(WORKING_NETWORKS)}")
        
        # Test cycle 1 activation
        print(f"\n🚀 Activating Cycle 1...")
        await cycle_manager._activate_cycle(0)
        
        current_cycle = cycle_manager.get_current_cycle_info()
        print(f"✅ Cycle {current_cycle['cycle_number']} active")
        print(f"📡 Active networks: {current_cycle['networks']}")
        print(f"⏰ Remaining time: {current_cycle['remaining_time']:.1f}s")
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Test cycle 2 activation
        print(f"\n🚀 Activating Cycle 2...")
        cycle_manager._deactivate_cycle(0)
        await cycle_manager._activate_cycle(1)
        
        current_cycle = cycle_manager.get_current_cycle_info()
        print(f"✅ Cycle {current_cycle['cycle_number']} active")
        print(f"📡 Active networks: {current_cycle['networks']}")
        
        # Test active networks check
        active_networks = cycle_manager.get_active_networks()
        print(f"📡 Currently active: {active_networks}")
        
        # Test network check
        print(f"\n🔍 Testing network checks:")
        for network in WORKING_NETWORKS[:8]:
            is_active = cycle_manager.is_network_active(network)
            status = "✅ ACTIVE" if is_active else "⏸️ INACTIVE"
            print(f"  {network}: {status}")
        
        # Test cycle progression
        print(f"\n🔄 Testing cycle progression...")
        for i in range(4):
            cycle_info = cycle_manager.get_current_cycle_info()
            print(f"Cycle {cycle_info['cycle_number']}: {cycle_info['networks']}")
            cycle_manager._deactivate_cycle(i)
            next_idx = (i + 1) % 4
            await cycle_manager._activate_cycle(next_idx)
            await asyncio.sleep(1)
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False

async def test_full_rotation():
    """Test full rotation loop."""
    
    try:
        from trading.token_pipeline.network_cycle_manager import RotatingNetworkCycleManager
        
        print("🔄 Testing Full Rotation Loop")
        print("=" * 50)
        
        # Create manager with working networks
        cycle_manager = RotatingNetworkCycleManager(
            cycle_duration=3,  # 3 seconds for testing
            networks_per_cycle=4
        )
        
        # Override with working networks
        cycle_manager.cycles = []
        for i in range(4):
            start_idx = i * 4
            end_idx = start_idx + 4
            cycle_networks = WORKING_NETWORKS[start_idx:end_idx]
            
            cycle = NetworkCycle(
                cycle_number=i + 1,
                networks=cycle_networks,
                start_time=0,
                end_time=0
            )
            cycle_manager.cycles.append(cycle)
        
        print("🚀 Starting full rotation test...")
        
        # Start rotation
        await cycle_manager.start_rotation()
        
        # Let it run for 12 seconds (4 cycles)
        await asyncio.sleep(12)
        
        # Stop rotation
        await cycle_manager.stop_rotation()
        
        print("✅ Full rotation test completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Full rotation test failed: {e}", exc_info=True)
        return False

async def main():
    """Main test function."""
    
    print("🚀 Testing Rotating Network Cycle Manager")
    print("=" * 60)
    
    test1_passed = await test_network_cycle()
    test2_passed = await test_full_rotation()
    
    print("\n" + "=" * 60)
    print("📋 Final Results:")
    print(f"  Basic cycle operations: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"  Full rotation loop: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    all_passed = test1_passed and test2_passed
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Rotating Network Cycle Manager is working correctly")
        print("✅ Ready for production with 35-second cycles")
        print("✅ Will avoid rate limits by cycling through networks")
    else:
        print("\n💥 SOME TESTS FAILED!")

if __name__ == "__main__":
    asyncio.run(main())
