"""
Rotating Network Cycle Manager
==============================

Cycles through 40 networks in groups of 8 with 35-second holds to avoid rate limits.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NetworkCycle:
    """Represents a network cycle configuration."""
    cycle_number: int
    networks: List[str]
    start_time: float
    end_time: float
    is_active: bool = False

class RotatingNetworkCycleManager:
    """
    Manages rotating network cycles to avoid rate limits.
    
    Cycles through 40 networks in groups of 8:
    - 5 cycles total
    - 8 networks per cycle
    - 35-second hold between cycles
    - Continuous rotation
    """
    
    def __init__(self, cycle_duration: int = 35, networks_per_cycle: int = 8):
        self.cycle_duration = cycle_duration
        self.networks_per_cycle = networks_per_cycle
        self.current_cycle_index = 0
        self.cycles: List[NetworkCycle] = []
        self.is_running = False
        self.rotation_task: Optional[asyncio.Task] = None
        
        # Initialize network cycles
        self._initialize_network_cycles()
        
    def _initialize_network_cycles(self):
        """Initialize the 5 network cycles with 8 networks each."""
        from trading.token_pipeline.token_registry import TokenRegistry
        
        registry = TokenRegistry()
        all_networks = list(registry.get_supported_chains())
        
        # Ensure we have exactly 40 networks
        if len(all_networks) < 40:
            logger.warning(f"Only {len(all_networks)} networks available, expected 40")
        
        # Take first 40 networks or all available if less
        networks_to_cycle = all_networks[:40]
        
        # Create 5 cycles with 8 networks each
        for i in range(5):
            start_idx = i * self.networks_per_cycle
            end_idx = start_idx + self.networks_per_cycle
            cycle_networks = networks_to_cycle[start_idx:end_idx]
            
            cycle = NetworkCycle(
                cycle_number=i + 1,
                networks=cycle_networks,
                start_time=0,
                end_time=0
            )
            self.cycles.append(cycle)
        
        logger.info(f"Initialized {len(self.cycles)} network cycles with {self.networks_per_cycle} networks each")
        for i, cycle in enumerate(self.cycles):
            logger.info(f"Cycle {cycle.cycle_number}: {cycle.networks}")
    
    async def start_rotation(self):
        """Start the rotating network cycle."""
        if self.is_running:
            logger.warning("Network rotation already running")
            return
        
        self.is_running = True
        self.rotation_task = asyncio.create_task(self._rotation_loop())
        logger.info("Started rotating network cycle manager")
    
    async def stop_rotation(self):
        """Stop the rotating network cycle."""
        self.is_running = False
        if self.rotation_task:
            self.rotation_task.cancel()
            try:
                await self.rotation_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped rotating network cycle manager")
    
    async def _rotation_loop(self):
        """Main rotation loop."""
        while self.is_running:
            try:
                # Activate current cycle
                await self._activate_cycle(self.current_cycle_index)
                
                # Wait for cycle duration
                await asyncio.sleep(self.cycle_duration)
                
                # Deactivate current cycle
                self._deactivate_cycle(self.current_cycle_index)
                
                # Move to next cycle
                self.current_cycle_index = (self.current_cycle_index + 1) % len(self.cycles)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rotation loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _activate_cycle(self, cycle_index: int):
        """Activate a specific network cycle."""
        cycle = self.cycles[cycle_index]
        cycle.is_active = True
        cycle.start_time = time.time()
        cycle.end_time = cycle.start_time + self.cycle_duration
        
        logger.info(f"🔄 Activating Cycle {cycle.cycle_number}: {cycle.networks}")
        logger.info(f"⏰ Cycle active for {self.cycle_duration} seconds (until {time.ctime(cycle.end_time)})")
        
        # Notify other components about active networks
        await self._notify_cycle_activation(cycle)
    
    def _deactivate_cycle(self, cycle_index: int):
        """Deactivate a specific network cycle."""
        cycle = self.cycles[cycle_index]
        cycle.is_active = False
        
        logger.info(f"⏹️ Deactivating Cycle {cycle.cycle_number}: {cycle.networks}")
    
    async def _notify_cycle_activation(self, cycle: NetworkCycle):
        """Notify other components about the active cycle."""
        # This can be extended to notify scanners, rate limiters, etc.
        # For now, just log the activation
        pass
    
    def get_active_networks(self) -> List[str]:
        """Get currently active networks."""
        for cycle in self.cycles:
            if cycle.is_active:
                return cycle.networks.copy()
        return []
    
    def get_current_cycle_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the current cycle."""
        if not self.cycles:
            return None
        
        cycle = self.cycles[self.current_cycle_index]
        return {
            "cycle_number": cycle.cycle_number,
            "networks": cycle.networks,
            "is_active": cycle.is_active,
            "start_time": cycle.start_time,
            "end_time": cycle.end_time,
            "remaining_time": max(0, cycle.end_time - time.time()) if cycle.is_active else 0
        }
    
    def get_all_cycles_info(self) -> List[Dict[str, Any]]:
        """Get information about all cycles."""
        return [
            {
                "cycle_number": cycle.cycle_number,
                "networks": cycle.networks,
                "is_active": cycle.is_active,
                "start_time": cycle.start_time,
                "end_time": cycle.end_time
            }
            for cycle in self.cycles
        ]
    
    def get_next_cycle_networks(self) -> List[str]:
        """Get networks for the next cycle."""
        next_index = (self.current_cycle_index + 1) % len(self.cycles)
        return self.cycles[next_index].networks.copy()
    
    def is_network_active(self, network: str) -> bool:
        """Check if a specific network is currently active."""
        active_networks = self.get_active_networks()
        return network in active_networks


# Global instance for easy access
network_cycle_manager = RotatingNetworkCycleManager()


async def start_network_rotation():
    """Start the global network rotation."""
    await network_cycle_manager.start_rotation()


async def stop_network_rotation():
    """Stop the global network rotation."""
    await network_cycle_manager.stop_rotation()


def get_active_networks():
    """Get currently active networks from global manager."""
    return network_cycle_manager.get_active_networks()


def is_network_active(network: str) -> bool:
    """Check if a network is currently active from global manager."""
    return network_cycle_manager.is_network_active(network)
