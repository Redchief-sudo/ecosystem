"""
Mempool Scanner Manager
-----------------------
Simple integration wrapper for the MempoolScannerUltra.
Provides ecosystem-compatible interface while preserving advanced functionality.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .mempool_scanner import MempoolScannerUltra

logger = logging.getLogger(__name__)


class MempoolManager:
    """
    Simple manager for the MempoolScannerUltra.
    Provides start/stop control and basic ecosystem integration.
    """
    
    def __init__(self, config: Optional[Dict] = None, **kwargs):
        """Initialize mempool manager with configuration."""
        self.config = config or {}
        self.scanner = None
        self.running = False
        self.chains = self.config.get('chains', ['ethereum'])
        
        # Network configuration for scanner
        self.network_config = {}
        for chain in self.chains:
            self.network_config[chain] = {
                'rpc_url': self.config.get('rpc_urls', {}).get(chain),
                'enabled': True
            }
    
    async def initialize(self) -> bool:
        """Initialize the mempool scanner."""
        try:
            logger.info("Initializing Mempool Manager...")
            
            # Create scanner instance
            self.scanner = MempoolScannerUltra(
                config=self.config,
                network_config=self.network_config
            )
            
            self.running = False
            logger.info("Mempool Manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Mempool Manager: {e}")
            return False
    
    async def start(self) -> None:
        """Start mempool monitoring."""
        if not self.scanner:
            await self.initialize()
        
        if self.running:
            logger.warning("Mempool scanner already running")
            return
        
        try:
            logger.info(f"Starting mempool scanner on chains: {self.chains}")
            await self.scanner.start(self.chains)
            self.running = True
            logger.info("Mempool scanner started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start mempool scanner: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop mempool monitoring."""
        if not self.running:
            return
        
        try:
            logger.info("Stopping mempool scanner...")
            await self.scanner.stop()
            self.running = False
            logger.info("Mempool scanner stopped")
            
        except Exception as e:
            logger.error(f"Error stopping mempool scanner: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current status of mempool scanner."""
        status = {
            'running': self.running,
            'chains': self.chains,
            'scanner_initialized': self.scanner is not None
        }
        
        if self.scanner:
            # Get basic metrics from scanner
            status.update({
                'pending_txs': len(getattr(self.scanner, 'pending_txs', {})),
                'mev_opportunities': len(getattr(self.scanner, 'mev_opportunities', [])),
                'arbitrage_opportunities': len(getattr(self.scanner, 'arbitrage_opportunities', []))
            })
        
        return status
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self.running:
            await self.stop()
        
        self.scanner = None
        logger.info("Mempool Manager cleanup complete")


# Singleton instance for global access
_mempool_manager: Optional[MempoolManager] = None


def get_mempool_manager(config: Optional[Dict] = None) -> MempoolManager:
    """Get or create the global mempool manager instance."""
    global _mempool_manager
    if _mempool_manager is None:
        _mempool_manager = MempoolManager(config)
    return _mempool_manager


async def start_mempool_scanner(config: Optional[Dict] = None) -> None:
    """Convenience function to start mempool scanner."""
    manager = get_mempool_manager(config)
    await manager.start()


async def stop_mempool_scanner() -> None:
    """Convenience function to stop mempool scanner."""
    manager = get_mempool_manager()
    await manager.stop()
