import asyncio
import json
import logging
import time
import traceback
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

import aiohttp
from eth_typing import ChecksumAddress
from web3 import Web3
from web3.contract import Contract

from scanners.scanned_token import ScannedToken

T = TypeVar("T")

logger = logging.getLogger(__name__)

# --------------------------------------------
# RATE LIMIT DECORATOR
# --------------------------------------------
def rate_limited(max_per_second: float):
    min_interval = 1.0 / float(max_per_second)
    last_called = [0.0]

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_called[0] = time.time()
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            last_called[0] = time.time()
            return await func(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


# --------------------------------------------
# ERROR HANDLER (SAFE, TRACEBACK-PROOF)
# --------------------------------------------
def handle_errors(default=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"[ScannerError] {func.__name__} failed: {e}")
                logger.debug("[ScannerError] Traceback:\n%s", traceback.format_exc())
                return default

        return wrapper

    return decorator


# --------------------------------------------
# WEB3 UTILITIES
# --------------------------------------------
def get_web3_provider(rpc_url: str) -> Optional[Web3]:
    try:
        web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
        return web3 if web3.is_connected() else None
    except Exception as e:
        logger.error(f"Failed to connect to Web3 provider: {e}")
        return None


def get_token_contract_abi() -> List[Dict[str, Any]]:
    return [
        {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
        {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    ]


# --------------------------------------------
# TOKEN HELPERS
# --------------------------------------------
async def fetch_token_metadata(web3: Web3, token_address: str) -> Dict[str, Any]:
    try:
        if not Web3.is_address(token_address):
            logger.warning(f"Invalid EVM address: {token_address}")
            return {"name": "Unknown", "symbol": "UNKNOWN", "decimals": 18}

        contract = web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=get_token_contract_abi())

        # Run all calls concurrently
        name, symbol, decimals = await asyncio.gather(
            contract.functions.name().call(),
            contract.functions.symbol().call(),
            contract.functions.decimals().call(),
        )

        return {"name": name, "symbol": symbol, "decimals": decimals}

    except Exception as e:
        logger.error(f"Token metadata fetch failed ({token_address}): {e}")
        return {"name": "Unknown", "symbol": "UNKNOWN", "decimals": 18}


def normalize_token_amount(amount: int, decimals: int) -> float:
    return amount / (10 ** decimals)


# --------------------------------------------
# LIGHTWEIGHT API CLIENT
# --------------------------------------------
class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def get(self, endpoint: str, params=None, timeout: int = 30):
        if not self.session:
            raise RuntimeError("APIClient session not initialized")

        url = f"{self.base_url}/{endpoint}"
        try:
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except asyncio.TimeoutError:
            logger.warning(f"API timeout: {url}")
        except Exception as e:
            logger.debug(f"API request failed: {e}")
        return None


# --------------------------------------------
# GENERIC JSON FETCHER
# --------------------------------------------
async def fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"HTTP {resp.status} for {url}")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching {url}")
    except Exception as e:
        logger.warning(f"Fetch failed for {url}: {e}")
    return None


# --------------------------------------------
# RAW SCAN OUTPUT DECORATOR (NO NORMALIZATION)
# --------------------------------------------
def raw_scan_output(default_decimals: int = 18, auto_fetch: bool = True, web3: Optional[Web3] = None):
    """
    Decorator to ensure raw output of scanner.scan() methods.
    - Ensures addresses are checksummed
    - Fills missing metadata (optionally via Web3)
    - Returns raw ScannedToken objects without scoring or normalization
    
    SCANNERS MUST ONLY:
    - Discover tokens
    - Collect raw market data
    - Perform basic data validation
    
    SCANNERS MUST NOT:
    - Score tokens
    - Normalize data beyond basic validation
    - Filter based on AI scores
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> List[ScannedToken]:
            raw_tokens = await func(*args, **kwargs)
            raw_scanned_tokens: List[ScannedToken] = []

            for t in raw_tokens:
                # Support both dict and ScannedToken input
                if isinstance(t, ScannedToken):
                    raw_scanned_tokens.append(t)
                    continue

                # Handle dict input - convert to ScannedToken without scoring
                if isinstance(t, dict):
                    addr = t.get('address') or t.get('token_address')
                    if not addr:
                        logger.warning("Skipping token without address")
                        continue

                    # Basic validation only - no scoring
                    chain = kwargs.get('chain', 'ethereum')
                    addr = Web3.to_checksum_address(addr) if web3 else addr

                    # Get basic metadata (no scoring)
                    name = t.get('name')
                    symbol = t.get('symbol')
                    decimals = t.get('decimals', default_decimals)

                    # Auto-fetch missing metadata if requested
                    if auto_fetch and web3 and (not name or not symbol or not decimals):
                        metadata = await fetch_token_metadata(web3, addr)
                        name = name or metadata.get("name", "Unknown")
                        symbol = symbol or metadata.get("symbol", "UNKNOWN")
                        decimals = decimals or metadata.get("decimals", default_decimals)

                    raw_scanned_tokens.append(ScannedToken(address=addr, name=name, symbol=symbol, decimals=decimals, chain=chain))

            return raw_scanned_tokens

        return wrapper

    return decorator
