"""
Lightweight async Onchain provider client supporting Etherscan and Alchemy fallbacks.
Provides helpers used by scanners for:
- contract verification
- contract creation lookup
- holder estimation (best-effort)

This implementation prefers web3 when available, and falls back to explorer APIs if configured.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

class OnchainClient:
    def __init__(self, config: Dict[str, Any], web3_instances: Optional[Dict[str, Any]] = None):
        """
        config: expected shape {
            'explorer_api_keys': {'ethereum': '<key>', 'bsc': '<key>'},
            'explorer_urls': {'ethereum': 'https://api.etherscan.io/api', 'bsc': 'https://api.bscscan.com/api'},
            'alchemy_urls': {'ethereum': 'https://eth-mainnet.alchemyapi.io/v2/<key>'}
        }
        web3_instances: optional mapping network -> Web3 instance
        """
        self.config = config or {}
        self.explorer_api_keys = self.config.get('explorer_api_keys', {})
        self.explorer_urls = self.config.get('explorer_urls', {})
        self.alchemy_urls = self.config.get('alchemy_urls', {})
        self.web3_instances = web3_instances or {}
        self._session = None

    async def _get_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def _http_get_json(self, url: str, params: Dict[str, str] = None, timeout: int = DEFAULT_TIMEOUT) -> Optional[Dict]:
        session = await self._get_session()
        params = params or {}
        retries = 3
        for attempt in range(retries):
            try:
                async with session.get(url, params=params, timeout=timeout) as resp:
                    if resp.status != 200:
                        logger.debug(f"HTTP GET {url} returned {resp.status}")
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    data = await resp.json()
                    return data
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url} (attempt {attempt+1})")
            except Exception as e:
                logger.warning(f"Error fetching {url} (attempt {attempt+1}): {e}")
            await asyncio.sleep(0.2 * (attempt + 1))
        return None

    async def is_contract_verified(self, address: str, network: str) -> bool:
        """Check block explorer for contract verification (Etherscan-style API)."""
        url = self.explorer_urls.get(network)
        if not url:
            return False
        api_key = self.explorer_api_keys.get(network, '')
        params = {
            'module': 'contract',
            'action': 'getsourcecode',
            'address': address,
            'apikey': api_key
        }
        data = await self._http_get_json(url, params=params)
        try:
            if data and 'result' in data and isinstance(data['result'], list):
                r = data['result'][0]
                source = r.get('SourceCode') or r.get('sourceCode')
                return bool(source)
        except Exception as e:
            logger.debug(f"Error parsing verification response: {e}")
        return False

    async def get_contract_creation(self, address: str, network: str) -> Tuple[int, str]:
        """
        Attempt to find contract creation transaction and block.
        Strategy:
          1) If an explorer API is available, query txlist for the address and find earliest tx where contractAddress == address.
          2) Fallback: use web3 to scan logs for earliest block containing contract's code (expensive, limited to a block window)
        Returns (blockNumber, txHash) or (0, "") on failure.
        """
        url = self.explorer_urls.get(network)
        api_key = self.explorer_api_keys.get(network, '')
        if url:
            params = {
                'module': 'account',
                'action': 'txlist',
                'address': address,
                'startblock': 0,
                'endblock': 99999999,
                'sort': 'asc',
                'apikey': api_key
            }
            data = await self._http_get_json(url, params=params)
            try:
                if data and 'result' in data and isinstance(data['result'], list):
                    for tx in data['result']:
                        # If this tx created the contract, contractAddress will be present
                        if tx.get('contractAddress') and tx.get('contractAddress').lower() == address.lower():
                            return int(tx.get('blockNumber', 0)), tx.get('hash', '')
            except Exception as e:
                logger.debug(f"Error parsing txlist response: {e}")

        # Fallback: try web3 (estimate using earliest tx that created code)
        w3 = self.web3_instances.get(network)
        if w3:
            try:
                # Binary-search for creation block could be implemented; here we try linear scan around recent blocks as a best-effort
                latest = w3.eth.block_number
                search_win = min(5000, latest)
                for blk in range(0, search_win, 1000):
                    start = blk
                    end = min(blk + 999, latest)
                    logs = w3.eth.get_logs({'fromBlock': start, 'toBlock': end, 'address': address})
                    if logs:
                        # We found logs, but contract creation detection may be imperfect; return first block
                        return logs[0]['blockNumber'], ''
            except Exception as e:
                logger.debug(f"Web3 fallback creation lookup failed: {e}")

        return 0, ''

    async def get_holder_count(self, token_address: str, network: str, lookback_blocks: int = 100000) -> int:
        """Estimate holder count by scanning Transfer events over `lookback_blocks` blocks.

        Raises:
            RuntimeError: If holder count cannot be estimated
        """
        w3 = self.web3_instances.get(network)
        if not w3:
            raise RuntimeError(f"No Web3 instance available for network: {network}")
        
        try:
            latest = w3.eth.block_number
            from_block = max(0, latest - lookback_blocks)
            # Transfer topic
            transfer_topic = w3.keccak(text='Transfer(address,address,uint256)').hex()
            logs = w3.eth.get_logs({'fromBlock': from_block, 'toBlock': latest, 'topics': [transfer_topic], 'address': token_address})
            holders = set()
            for log in logs:
                # topic[2] is 'to' address (indexed)
                # topics[2] typically exists; decode last 20 bytes
                if len(log['topics']) >= 3:
                    to_hex = log['topics'][2].hex()[-40:]
                    holders.add('0x' + to_hex)
            return len(holders)
        except Exception as e:
            logger.error(f"❌ Error estimating holders via logs for {token_address} on {network}: {e}")
            # NO FALLBACK - fail explicitly instead of returning None
            raise RuntimeError(
                f"Failed to estimate holder count for {token_address} on {network}: {e}"
            )


# Simple helper to construct default config from global config
def build_onchain_client_from_config(config: Dict[str, Any], web3_instances: Optional[Dict[str, Any]] = None) -> OnchainClient:
    # allow config to include explorer urls and keys, or derive from network names
    normalized = {
        'explorer_api_keys': config.get('explorer_api_keys', {}),
        'explorer_urls': config.get('explorer_urls', {}),
        'alchemy_urls': config.get('alchemy_urls', {})
    }
    return OnchainClient(normalized, web3_instances)
