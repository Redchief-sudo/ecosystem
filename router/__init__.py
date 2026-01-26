"""
Router Package
---------------
Handles all router-related functionality for trading system.
Automatically initializes token registries for all supported chains.
"""

from threading import RLock
from typing import Dict
from pathlib import Path

from core.models import TokenMetadata
from .hybrid_router_manager import HybridRouterManager
from trading.token_pipeline.token_registry import TokenRegistry
from .api.health import get_health

class RouterInitializer:
    """
    Initializes routing with full multi-chain token registries.
    """
    def __init__(self, token_registry: TokenRegistry):
        self.token_registry = token_registry
        self._registries: Dict[str, Dict[str, TokenMetadata]] = {}
        self._registry_lock = RLock()
        self._initialize_registries()

    def _initialize_registries(self):
        """Populate registries for all chains in the token registry"""
        with self._registry_lock:
            for chain in self.token_registry.get_supported_chains():
                # Initialize empty dict if not already present
                if chain not in self._registries:
                    self._registries[chain] = {}

                # Copy tokens from TokenRegistry into local routing registries
                for symbol, metadata in self.token_registry._registries.get(chain, {}).items():
                    self._registries[chain][symbol] = metadata

    def get_registry_for_chain(self, chain: str) -> Dict[str, TokenMetadata]:
        """Get token registry for a specific chain"""
        return self._registries.get(chain, {})


# Initialize the routing layer automatically
token_registry = TokenRegistry()  # Or pass an existing instance if already initialized
router_initializer = RouterInitializer(token_registry)
HybridRouterManager._registries = router_initializer._registries  # Inject into HybridRouterManager

__all__ = ['HybridRouterManager', 'router_initializer', 'get_health']

