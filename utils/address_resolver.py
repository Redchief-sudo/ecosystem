"""
Token Address Resolver - Auto-resolve token addresses via API lookup.
"""

import asyncio
import logging
from typing import Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)

# API endpoints for token resolution
TOKEN_APIS = {
    "coingecko": "https://api.coingecko.com/api/v3",
    "coinmarketcap": "https://api.coinmarketcap.com/v1",
    "1inch": "https://api.1inch.dev/swap/v5.2",
    "moralis": "https://api.moralis.io/v1"
}

class TokenAddressResolver:
    """Resolves token addresses using multiple API sources."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.session = None
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    async def _get_session(self):
        """Get or create HTTP session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self.session
    
    async def resolve_by_symbol(self, symbol: str, chain: str = "ethereum") -> Optional[str]:
        """
        Resolve token address by symbol using multiple APIs.
        """
        cache_key = f"{chain}:{symbol}"
        
        # Check cache first
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if asyncio.get_event_loop().time() - cached["timestamp"] < self.cache_ttl:
                return cached["address"]
        
        # Try CoinGecko first
        address = await self._resolve_from_coingecko(symbol, chain)
        if address:
            address = self._correct_address(address, chain)
            self.cache[cache_key] = {
                "address": address,
                "timestamp": asyncio.get_event_loop().time()
            }
            return address
        
        # Try CoinMarketCap
        address = await self._resolve_from_coinmarketcap(symbol, chain)
        if address:
            address = self._correct_address(address, chain)
            self.cache[cache_key] = {
                "address": address,
                "timestamp": asyncio.get_event_loop().time()
            }
            return address
        
        logger.warning(f"Could not resolve address for {symbol} on {chain}")
        return None
    
    def _correct_address(self, address: str, chain: str) -> Optional[str]:
        """Correct address based on known invalid addresses."""
        if address in self.invalid_address_map:
            correction = self.invalid_address_map[address]
            if isinstance(correction, dict) and chain in correction:
                return correction[chain]
            elif correction is None:
                return None
        return address
    
    async def _resolve_from_coingecko(self, symbol: str, chain: str) -> Optional[str]:
        """Resolve from CoinGecko API."""
        try:
            session = await self._get_session()
            url = f"{TOKEN_APIS['coingecko']}/coins/{symbol.lower()}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Get platform-specific address
                    platforms = data.get("platforms", {})
                    if chain.lower() in platforms:
                        return platforms[chain.lower()]["contract_address"]
                    
                    # Default to Ethereum
                    return data.get("contract_address", "")
        
        except Exception as e:
            logger.debug(f"CoinGecko lookup failed for {symbol}: {e}")
            return None
    
    async def _resolve_from_coinmarketcap(self, symbol: str, chain: str) -> Optional[str]:
        """Resolve from CoinMarketCap API."""
        try:
            session = await self._get_session()
            url = f"{TOKEN_APIS['coinmarketcap']}/cryptocurrency/map"
            
            params = {
                "symbol": symbol,
                "aux": "platform,contract_address"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Find the token in the data
                    for crypto in data.get("data", []):
                        if crypto.get("symbol", "").upper() == symbol.upper():
                            platform_data = crypto.get("platform", {})
                            if chain.lower() in platform_data:
                                return platform_data[chain.lower()]["contract_address"]
        
        except Exception as e:
            logger.debug(f"CoinMarketCap lookup failed for {symbol}: {e}")
            return None
    
    async def validate_token_addresses(self, tokens: list) -> list:
        """
        Validate and correct token addresses in a list of token data.
        """
        corrected_tokens = []
        
        for token in tokens:
            if isinstance(token, dict):
                address = token.get("address", "")
                chain = token.get("chain", "ethereum")
                
                # Check if address needs correction
                if not self._is_valid_address(address, chain):
                    # Try to resolve by symbol
                    symbol = token.get("symbol", "")
                    if symbol:
                        corrected_address = await self.resolve_by_symbol(symbol, chain)
                        if corrected_address and corrected_address != address:
                            token["address"] = corrected_address
                            logger.info(f"✅ Corrected address for {symbol}: {address} → {corrected_address}")
                            corrected_tokens.append(token)
                        else:
                            logger.warning(f"Could not resolve address for {symbol}")
                else:
                    corrected_tokens.append(token)
        
        return corrected_tokens
    
    def _is_valid_address(self, address: str, chain: str) -> bool:
        """Check if address format is valid for the given chain."""
        if not address:
            return False
        
        # EVM chains
        if chain in ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "avalanche", "base", "fantom", "cronos", "gnosis", "linea", "aurora", "harmony", "kava", "moonbeam", "moonriver", "celo", "zksync_era", "scroll", "mantle", "blast", "mode", "sei", "arbitrum_nova", "taiko", "canto", "boba", "fuse", "polygon_zkevm"]:
            return address.startswith("0x") and len(address) == 42
        
        # Solana
        if chain == "solana":
            return len(address) in [43, 44]
        
        # TRON
        if chain == "tron":
            return address.startswith("T") and len(address) == 34
        
        return False
    
    async def close(self):
        """Close the resolver session."""
        if self.session:
            await self.session.close()
            self.session = None
