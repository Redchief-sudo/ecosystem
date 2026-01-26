"""
Chain Client Factory - Creates appropriate clients for different blockchain types

This module provides a factory pattern to create the right type of client
for each blockchain network, eliminating the need for fallbacks by using
the correct protocol from the start.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import aiohttp
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    try:
        from web3.middleware.geth_poa import geth_poa_middleware
    except ImportError:
        geth_poa_middleware = None  # If middleware not available

try:
    from web3.middleware import async_geth_poa_middleware
except ImportError:
    try:
        from web3.middleware.geth_poa import async_geth_poa_middleware
    except ImportError:
        async_geth_poa_middleware = None  # If middleware not available

from networks.chain_type_detector import ChainTypeDetector, ChainInfo

logger = logging.getLogger("chain_client_factory")


@dataclass
class ChainClient:
    """Universal chain client wrapper"""
    chain_name: str
    chain_type: str
    client: Any
    chain_info: ChainInfo
    is_connected: bool = False
    last_block: Optional[Union[int, str]] = None
    native_token: Optional[str] = None

    async def disconnect(self):
        """Clean up connections"""
        if hasattr(self.client, "disconnect"):
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting {self.chain_name}: {e}")
        elif hasattr(self.client, "close"):
            try:
                await self.client.close()
            except Exception as e:
                logger.warning(f"Error closing {self.chain_name}: {e}")


class BaseChainClient(ABC):
    """Abstract base class for chain-specific clients"""

    def __init__(self, chain_name: str, rpc_url: str, chain_info: ChainInfo, timeout: int = 15):
        self.chain_name = chain_name
        self.rpc_url = rpc_url
        self.chain_info = chain_info
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.client: Optional[Any] = None

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the chain and verify connectivity"""
        pass

    @abstractmethod
    async def get_latest_block(self) -> Union[int, str]:
        """Get the latest block number or identifier"""
        pass

    @abstractmethod
    async def get_native_token_price(self) -> Optional[str]:
        """Get native token price or gas price"""
        pass

    @abstractmethod
    async def disconnect(self):
        """Clean up connections"""
        pass


class EVMChainClient(BaseChainClient):
    """Client for EVM-compatible chains"""

    async def connect(self) -> bool:
        """Connect to EVM chain using Web3"""
        try:
            provider = AsyncHTTPProvider(self.rpc_url)
            self.client = AsyncWeb3(provider)

            poa_chains = {
                "bsc",
                "bnb_smart_chain",
                "polygon",
                "avalanche",
                "fantom",
                "cronos",
                "moonriver",
                "moonbeam",
                "celo",
                "aurora",
                "near_aurora",
                "boba",
                "metis",
                "kava",
                "canto",
                "gnosis",
                "dogechain",
                "base",
                "optimism",
                "arbitrum",
                "linea",
                "scroll",
                "zksync",
                "mantle",
                "blast",
            }

            if self.chain_name.lower() in poa_chains and async_geth_poa_middleware is not None:
                self.client.middleware_onion.inject(async_geth_poa_middleware, layer=0)

            chain_id = await asyncio.wait_for(self.client.eth.chain_id, timeout=self.timeout)
            logger.info(f"Connected to {self.chain_name} (chain_id={chain_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to {self.chain_name}: {e}")
            await self.disconnect()
            return False

    async def get_latest_block(self) -> int:
        if not self.client:
            raise RuntimeError("Client not connected")

        try:
            return await asyncio.wait_for(self.client.eth.block_number, timeout=self.timeout)
        except Exception as e:
            logger.error(f"Failed to get block number for {self.chain_name}: {e}")
            raise

    async def get_native_token_price(self) -> Optional[str]:
        if not self.client:
            return None

        try:
            gas_price = await asyncio.wait_for(self.client.eth.gas_price, timeout=self.timeout)
            return str(gas_price)
        except Exception:
            return None

    async def disconnect(self):
        if not self.client:
            return

        try:
            provider = getattr(self.client, "provider", None)
            if provider is not None:
                session = getattr(provider, "session", None)
                if session is not None:
                    await session.close()
        except Exception:
            pass

        self.client = None


class BitcoinLikeClient(BaseChainClient):
    """Client for Bitcoin-like chains (BTC, LTC, DOGE, etc.)"""

    async def connect(self) -> bool:
        try:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
            api_url = self.rpc_url.rstrip("/") + "/blocks/tip/height"

            async with self.session.get(api_url) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} from {self.chain_name}")
                    return False

                block_height = await response.text()
                if block_height.isdigit():
                    logger.info(f"Connected to {self.chain_name} (Bitcoin-like)")
                    return True

                logger.error(f"Invalid response from {self.chain_name}: {block_height}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to {self.chain_name}: {e}")
            await self.disconnect()
            return False

    async def get_latest_block(self) -> int:
        if not self.session:
            raise RuntimeError("Client not connected")

        api_url = self.rpc_url.rstrip("/") + "/blocks/tip/height"

        async with self.session.get(api_url) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")

            block_height = await response.text()
            return int(block_height) if block_height.isdigit() else 0

    async def get_native_token_price(self) -> Optional[str]:
        return None

    async def disconnect(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None


class SolanaClient(BaseChainClient):
    """Client for Solana blockchain"""

    async def connect(self) -> bool:
        try:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

            payload = {"jsonrpc": "2.0", "method": "getSlot", "params": [], "id": 1}
            async with self.session.post(self.rpc_url, json=payload) as response:
                if response.status != 200:
                    logger.error(f"HTTP {response.status} from {self.chain_name}")
                    return False

                result = await response.json()
                if "result" in result:
                    logger.info(f"Connected to {self.chain_name} (Solana)")
                    return True

                logger.error(f"Invalid response from {self.chain_name}: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to {self.chain_name}: {e}")
            await self.disconnect()
            return False

    async def get_latest_block(self) -> int:
        if not self.session:
            raise RuntimeError("Client not connected")

        payload = {"jsonrpc": "2.0", "method": "getSlot", "params": [], "id": 1}
        async with self.session.post(self.rpc_url, json=payload) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
            result = await response.json()
            return int(result.get("result", 0))

    async def get_native_token_price(self) -> Optional[str]:
        """
        Solana does not expose gas price in the same way as EVM.
        This method returns recent fee calculation if available.
        """
        if not self.session:
            return None

        try:
            payload = {"jsonrpc": "2.0", "method": "getRecentBlockhash", "params": [], "id": 1}
            async with self.session.post(self.rpc_url, json=payload) as response:
                if response.status != 200:
                    return None

                result = await response.json()
                blockhash = result.get("result", {}).get("context", {}).get("slot")
                return str(blockhash) if blockhash else None

        except Exception:
            return None

    async def disconnect(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None


class GenericHTTPClient(BaseChainClient):
    """Generic HTTP client for other blockchain types"""

    async def connect(self) -> bool:
        try:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))

            payload = {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}
            async with self.session.post(self.rpc_url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Connected to {self.chain_name} ({self.chain_info.chain_type})")
                    return True

                if response.status in {400, 401, 403}:
                    logger.warning(f"Reachable but auth/error for {self.chain_name}: HTTP {response.status}")
                    return True

                logger.error(f"HTTP {response.status} from {self.chain_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to {self.chain_name}: {e}")
            await self.disconnect()
            return False

    async def get_latest_block(self) -> str:
        return "connected"

    async def get_native_token_price(self) -> Optional[str]:
        return None

    async def disconnect(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None


class ChainClientFactory:
    """Factory for creating appropriate chain clients"""

    @staticmethod
    def create_client(chain_name: str, rpc_url: str, timeout: int = 15) -> BaseChainClient:
        chain_info = ChainTypeDetector.get_chain_info(chain_name)

        if chain_info.chain_type == "evm":
            return EVMChainClient(chain_name, rpc_url, chain_info, timeout)
        elif chain_info.chain_type == "bitcoin":
            return BitcoinLikeClient(chain_name, rpc_url, chain_info, timeout)
        elif chain_info.chain_type == "solana":
            return SolanaClient(chain_name, rpc_url, chain_info, timeout)
        else:
            return GenericHTTPClient(chain_name, rpc_url, chain_info, timeout)

    @staticmethod
    async def create_and_connect_client(chain_name: str, rpc_url: str, timeout: int = 15) -> Optional[ChainClient]:
        client = ChainClientFactory.create_client(chain_name, rpc_url, timeout)

        if not await client.connect():
            return None

        try:
            latest_block = await client.get_latest_block()
            native_price = await client.get_native_token_price()

            return ChainClient(
                chain_name=chain_name,
                chain_type=client.chain_info.chain_type,
                client=client,
                chain_info=client.chain_info,
                is_connected=True,
                last_block=latest_block,
                native_token=native_price,
            )
        except Exception as e:
            logger.error(f"Failed to retrieve chain info for {chain_name}: {e}")
            await client.disconnect()
            return None

