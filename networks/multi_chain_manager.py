"""
Multi-Chain Network Manager
--------------------------
Manages connections to multiple blockchain networks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from web3 import HTTPProvider, Web3

try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    try:
        from web3.middleware.geth_poa import geth_poa_middleware
    except ImportError:
        geth_poa_middleware = None  # If middleware not available


logger = logging.getLogger(__name__)


@dataclass
class ChainConfig:
    chain_id: int
    rpc: str
    router_v2: Optional[str] = None
    native_wrapped: Optional[str] = None
    fallback_rpcs: List[str] = None


class MultiChainManager:
    """
    Manages connections to multiple blockchain networks with automatic failover.
    """

    def __init__(self, config: Dict[str, Any], private_key: str = ""):
        self.config = config
        self.private_key = private_key
        self.clients: Dict[str, Web3] = {}
        self.chain_configs: Dict[str, ChainConfig] = {}
        self._initialize_chain_configs()

    def _initialize_chain_configs(self) -> None:
        """Initialize chain configurations from the config file."""
        networks = self.config.get("networks", {}) or {}

        for chain, chain_config in networks.items():
            chain_lower = chain.lower()
            self.chain_configs[chain_lower] = ChainConfig(
                chain_id=chain_config.get("chain_id"),
                rpc=chain_config.get("rpc"),
                router_v2=chain_config.get("router_v2"),
                native_wrapped=chain_config.get("native_wrapped"),
                fallback_rpcs=chain_config.get("fallback_rpcs", []),
            )
            logger.info("Loaded configuration for %s", chain_lower)

    async def initialize(self) -> None:
        """Initialize all chain connections."""
        tasks = [self._initialize_chain(chain) for chain in self.chain_configs]
        await asyncio.gather(*tasks, return_exceptions=True)

        for chain in self.chain_configs:
            status = "Connected" if chain in self.clients else "Failed"
            logger.info("%s %s: %s", "✅" if chain in self.clients else "❌", chain.upper(), status)

    async def _initialize_chain(self, chain: str) -> None:
        """Initialize connection to a specific chain."""
        chain = chain.lower()
        config = self.chain_configs.get(chain)

        if not config:
            logger.warning("Configuration for chain %s not found", chain)
            return

        if not config.rpc:
            logger.warning("No RPC URL configured for chain %s", chain)
            return

        # Try primary RPC first
        primary = await asyncio.to_thread(self._create_web3, config.rpc, chain, config.chain_id)
        if primary:
            self.clients[chain] = primary
            logger.info("✅ Connected to %s at %s", chain.upper(), config.rpc)
            return

        # Try fallbacks
        if config.fallback_rpcs:
            await self._try_fallback_rpcs(chain, config)

    async def _try_fallback_rpcs(self, chain: str, config: ChainConfig) -> None:
        """Try connecting to fallback RPCs for a chain, selecting the fastest working one."""
        tasks = [asyncio.to_thread(self._create_web3_with_latency, rpc, chain, config.chain_id) for rpc in config.fallback_rpcs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        working: List[Tuple[Web3, int, str]] = []
        for r in results:
            if isinstance(r, tuple):
                web3, latency_ms, rpc_url = r
                working.append((web3, latency_ms, rpc_url))

        if not working:
            logger.error("❌ All RPCs failed for chain %s", chain)
            return

        # Select best by latency
        best = min(working, key=lambda x: x[1])
        self.clients[chain] = best[0]
        logger.info("✅ Connected to %s via fallback RPC (latency=%dms) %s", chain.upper(), best[1], best[2])

    def _create_web3(self, rpc_url: str, chain: str, expected_chain_id: int) -> Optional[Web3]:
        """Create and validate Web3 instance synchronously."""
        try:
            web3 = Web3(HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))

            if chain in ["bsc", "polygon", "avalanche", "arbitrum_nova"] and geth_poa_middleware:
                web3.middleware_onion.inject(geth_poa_middleware, layer=0)

            chain_id = web3.eth.chain_id
            if chain_id != expected_chain_id:
                raise ValueError(f"Chain ID mismatch: expected {expected_chain_id}, got {chain_id}")

            return web3
        except Exception as e:
            logger.warning("Failed to connect to %s RPC at %s: %s", chain, rpc_url, str(e))
            return None

    def _create_web3_with_latency(self, rpc_url: str, chain: str, expected_chain_id: int) -> Optional[Tuple[Web3, int, str]]:
        """Create Web3 instance and return latency if successful."""
        start = asyncio.get_event_loop().time()
        web3 = self._create_web3(rpc_url, chain, expected_chain_id)
        if not web3:
            return None

        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)
        return web3, latency_ms, rpc_url

    def get_web3(self, chain: str) -> Optional[Web3]:
        """Get a Web3 instance for the specified chain."""
        return self.clients.get(chain.lower())

    async def is_chain_available(self, chain: str) -> bool:
        """Check if a chain is available."""
        chain = chain.lower()
        w3 = self.clients.get(chain)
        if not w3:
            return False

        try:
            await asyncio.to_thread(lambda: w3.eth.chain_id)
            return True
        except Exception as e:
            logger.warning("Chain %s is not responding: %s", chain, str(e))
            return False

    async def refresh_health(self) -> None:
        """Refresh health status for all chains (reconnect if needed)."""
        tasks = [self._health_check_chain(chain) for chain in self.chain_configs]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _health_check_chain(self, chain: str) -> None:
        """Health check for a chain; reconnect if necessary."""
        if await self.is_chain_available(chain):
            return

        logger.warning("Chain %s not available, attempting reconnect...", chain)
        await self._initialize_chain(chain)

    async def close(self) -> None:
        """Close all connections."""
        self.clients.clear()
        logger.info("Closed all network connections")

