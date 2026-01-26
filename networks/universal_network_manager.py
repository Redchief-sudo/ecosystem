"""
Universal Network Manager - Core system fix for multi-chain support
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Set

from networks.chain_client_factory import ChainClientFactory, ChainClient
from networks.chain_type_detector import ChainTypeDetector
from utils.mev_protection import MEVProtector

logger = logging.getLogger(__name__)

class UniversalNetworkManager:
    """
    Universal network manager that handles all blockchain types correctly.
    """

    def __init__(self, config: Dict[str, Any], private_key: str = ""):
        """Initialize the universal network manager"""
        if hasattr(self, "_initialized") and self._initialized:
            logger.warning("⚠️ UniversalNetworkManager already initialized, skipping")
            return

        self.config = config
        self.private_key = private_key
        self.clients: Dict[str, ChainClient] = {}
        self.mev_protectors: Dict[str, MEVProtector] = {}
        self.chain_ids: Dict[str, int] = {}
        self.rpc_urls: Dict[str, str] = {}
        self.fallback_rpcs: Dict[str, List[str]] = {}
        self._request_timeout = 15  # seconds
        self._initialized = True
        self._async_initialized = False

        # Initialize networks from config
        networks = config.get("networks", {}) or {}

        for chain, chain_config in networks.items():
            if not isinstance(chain_config, dict):
                logger.warning(f"Invalid configuration for {chain}, expected dict")
                continue
            if not chain_config.get("enabled", True):
                logger.debug(f"Skipping disabled network: {chain}")
                continue

            rpc_url = chain_config.get("rpc") or chain_config.get("rpc_url")
            if not rpc_url:
                logger.warning(f"No RPC URL configured for {chain}")
                continue

            rpc_url = self._substitute_api_keys(rpc_url)
            if not rpc_url:
                logger.warning(f"Empty RPC URL after substitution for {chain}")
                continue

            self.rpc_urls[chain] = rpc_url
            chain_id = chain_config.get("chain_id")
            if isinstance(chain_id, int) and chain_id > 0:
                self.chain_ids[chain] = chain_id

            fallbacks = chain_config.get("fallback_rpcs", [])
            if fallbacks:
                processed = [self._substitute_api_keys(f) for f in fallbacks if f]
                if processed:
                    self.fallback_rpcs[chain] = processed

            logger.debug(f"Initialized network config for {chain}")

    def _substitute_api_keys(self, rpc_url: str) -> str:
        """Substitute API keys in RPC URLs"""
        import re

        pattern = re.compile(r"\$\{api_keys\.(\w+)\}")

        def replace_api_key(match):
            provider = match.group(1)
            key = self._get_api_key(provider)
            if key:
                return key
            return match.group(0)

        rpc_url = pattern.sub(replace_api_key, rpc_url)
        return os.path.expandvars(rpc_url).strip('"\'') if rpc_url else ""

    def _get_api_key(self, provider: str) -> Optional[str]:
        try:
            return self.config.get("api_keys", {}).get(provider)
        except Exception:
            return None

    async def initialize(self):
        """Initialize all configured networks"""
        if self._async_initialized:
            logger.warning("⚠️ UniversalNetworkManager already initialized asynchronously, skipping")
            return

        logger.info(f"Initializing {len(self.rpc_urls)} networks...")
        tasks = [self._initialize_chain(chain, rpc) for chain, rpc in self.rpc_urls.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success, failed = [], []
        for i, res in enumerate(results):
            chain = list(self.rpc_urls.keys())[i]
            if isinstance(res, Exception) or res is None:
                failed.append(chain)
            else:
                success.append(chain)

        if success:
            self._async_initialized = True
            logger.info(f"✅ Successfully initialized networks: {', '.join(success)}")
        if failed:
            logger.warning(f"⚠️ Failed to initialize networks: {', '.join(failed)}")
            if not success:
                raise RuntimeError("No networks could be initialized")

    async def _initialize_chain(self, chain: str, rpc_url: str) -> Optional[ChainClient]:
        """Initialize a single chain with appropriate client"""
        client: Optional[ChainClient] = None
        try:
            chain_info = ChainTypeDetector.get_chain_info(chain)
            client = await ChainClientFactory.create_and_connect_client(chain, rpc_url, self._request_timeout)
            if not client:
                return None

            if self.private_key and client.chain_type == "evm":
                try:
                    mev_protector = MEVProtector(client.client, self.private_key)
                    self.mev_protectors[chain] = mev_protector
                except Exception as e:
                    logger.warning(f"MEV protection failed for {chain}: {e}")

            self.clients[chain] = client
            return client
        except Exception as e:
            logger.error(f"Failed to initialize {chain}: {e}")
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            return None

    def get_client(self, chain: str) -> Optional[ChainClient]:
        return self.clients.get(chain)

    def get_web3(self, chain: str):
        """Return Web3 client for EVM chains only"""
        client = self.clients.get(chain)
        if client and client.chain_type == "evm":
            return client.client
        return None

    def is_chain_supported(self, chain: str) -> bool:
        client = self.clients.get(chain)
        return bool(client and client.is_connected)

    def get_connected_chains(self) -> Set[str]:
        return {c for c, client in self.clients.items() if client.is_connected}

    async def health_check(self) -> Dict[str, bool]:
        results = {}
        for chain, client in self.clients.items():
            try:
                await client.get_latest_block()
                results[chain] = True
            except Exception as e:
                logger.warning(f"Health check failed for {chain}: {e}")
                results[chain] = False
        return results

    async def shutdown(self):
        """Shutdown all network connections"""
        for chain, client in self.clients.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting {chain}: {e}")
        self.clients.clear()
        self.mev_protectors.clear()

    def __repr__(self):
        connected = len(self.get_connected_chains())
        total = len(self.clients)
        return f"UniversalNetworkManager(connected={connected}/{total})"

