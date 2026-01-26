"""
Token analysis using real-time blockchain and market data
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict, deque
from statistics import stdev, mean

import aiohttp
from ..base_scanner import ScannerBase
from ..scanned_token import ScannedToken
from config.network_config import NetworkConfig

logger = logging.getLogger(__name__)

class TokenAnalyzer(ScannerBase):
    """Analyzes tokens using multiple data sources"""
    
    def __init__(self, config: Optional[Dict] = None, **kwargs):
        super().__init__(config or {}, **kwargs)
        self.name = "TokenAnalyzer"
        self.dexscreener_base = "https://api.dexscreener.com/latest"
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        
        # Scanner-specific timeout (shorter for fast scanner)
        self.config.setdefault('timeout_seconds', 30.0)  # 30 seconds for TokenAnalyzer
        
        # Token rotation state (same as DexScreener)
        self._rotation_state = {
            'current_token_index': 0,
            'last_rotation': time.time(),
            'rotation_interval': 60  # Rotate every scan cycle (60 seconds)
        }
        
        # Common tokens for rotation (same as DexScreener)
        self._all_tokens = {
            'ethereum': ['WETH', 'USDC', 'USDT'],
            'bsc': ['WBNB', 'USDC', 'USDT'],
            'polygon': ['WMATIC', 'USDC', 'USDT'],
            'arbitrum': ['WETH', 'USDC', 'USDT'],
            'optimism': ['WETH', 'USDC', 'USDT'],
            'avalanche': ['WAVAX', 'USDC', 'USDT'],
            'base': ['WETH', 'USDC', 'USDT'],
            'fantom': ['WFTM', 'USDC', 'USDT'],
            'cronos': ['WCRO', 'USDC', 'USDT'],
            'gnosis': ['WETH', 'USDC', 'USDT']
        }
    
    def _get_current_search_token(self, chain: str) -> str:
        """Get current search token based on rotation (same as DexScreener)."""
        all_tokens = self._all_tokens.get(chain, ['ETH'])
        
        # Rotate through tokens based on current index
        current_time = time.time()
        if current_time - self._rotation_state['last_rotation'] > self._rotation_state['rotation_interval']:
            self._rotation_state['current_token_index'] = (self._rotation_state['current_token_index'] + 1) % len(all_tokens)
            self._rotation_state['last_rotation'] = current_time
            logger.info(f"🔄 TokenAnalyzer rotating to token index {self._rotation_state['current_token_index']}: {all_tokens[self._rotation_state['current_token_index']]}")
        
        return all_tokens[self._rotation_state['current_token_index']]
    
    async def scan(self, chain: str = "ethereum") -> List[Dict]:
        """
        Scan for analyzed tokens on specified chain using token rotation.
        
        Args:
            chain: Blockchain network to scan
            
        Returns:
            List of raw token data dictionaries
        """
        try:
            # Get current search token based on rotation (ONLY ONE TOKEN PER CYCLE!)
            search_term = self._get_current_search_token(chain)
            logger.info(f"🔍 TokenAnalyzer searching {chain} with token: {search_term}")
            
            # Get trending tokens for the current search token (reduced to 3 for less API load)
            trending_addresses = await self.get_trending_tokens(chain, limit=3)
            
            results = []
            for address in trending_addresses:
                try:
                    analyzed_token = await self.analyze_token(address, chain)
                    if analyzed_token:
                        results.append(analyzed_token)  # Already a raw dict
                except Exception as e:
                    logger.warning(f"Failed to analyze token {address}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"TokenAnalyzer scan failed: {e}")
            return []
    
    async def analyze_token(self, token_address: str, network: str) -> Optional[Dict]:
        """
        Analyze token and return raw data dictionary (no scoring or modification).
        Only uses DexScreener API to avoid CoinGecko timeouts.
        
        Args:
            token_address: Token contract address
            network: Network name (e.g., 'ethereum', 'bsc')
        
        Returns:
            Raw token data dictionary or None if analysis fails
        """
        try:
            # Only fetch from DexScreener (skip CoinGecko to avoid timeouts)
            dex_data = await self._get_dexscreener_data(token_address)
            # Skip CoinGecko and onchain data for now
            gecko_data = {}
            onchain_data = {}
            
            if not dex_data:
                logger.warning(f"No DEX data found for {token_address}")
                return None
            
            # Get the best pair from DEX data
            pairs = dex_data.get('pairs', [])
            if not pairs:
                logger.warning(f"No pair data found for {token_address}")
                return None
                
            best_pair = pairs[0]  # Use first pair as best
            
            # Extract raw token data
            base_token = best_pair.get('baseToken', {})
            quote_token = best_pair.get('quoteToken', {})
            
            # Get basic metrics
            price = float(best_pair.get('priceUsd', 0))
            volume_24h = float(best_pair.get('volume', {}).get('h24', 0))
            liquidity = float(best_pair.get('liquidity', {}).get('usd', 0))
            
            # Get price changes
            price_changes = best_pair.get('priceChange', {})
            price_change_5m = float(price_changes.get('m5', 0))
            price_change_1h = float(price_changes.get('h1', 0))
            price_change_24h = float(price_changes.get('h24', 0))
            price_change_7d = float(price_changes.get('d7', 0))
            
            # Extract actual chain from DexScreener data to prevent conflicts
            actual_chain_id = best_pair.get('chainId', network)
            
            # Normalize chain ID to chain name
            from networks.chain_normalizer import chain_normalizer
            actual_chain = chain_normalizer.normalize_chain_identifier(actual_chain_id)
            
            # Return raw data dictionary (no scoring, no confidence)
            return {
                'address': base_token.get('address', token_address),
                'symbol': base_token.get('symbol', 'UNKNOWN'),
                'name': base_token.get('name', 'Unknown Token'),
                'decimals': int(base_token.get('decimals', 18)),
                'price': price,
                'price_change_5m': price_change_5m,
                'price_change_1h': price_change_1h,
                'price_change_24h': price_change_24h,
                'price_change_7d': price_change_7d,
                'volume_24h': volume_24h,
                'liquidity_usd': liquidity,
                'chain_id': self._get_chain_id(actual_chain),
                'chain': actual_chain,  # Use actual chain from DexScreener
                'chain_name': actual_chain,
                'exchange': best_pair.get('dexId', 'unknown'),
                'pair_address': best_pair.get('pairAddress', ''),
                'quote_token': quote_token.get('symbol', ''),
                'quote_address': quote_token.get('address', ''),
                'metadata': {
                    'dex_data': best_pair,
                    'gecko_data': gecko_data,
                    'onchain_data': onchain_data,
                    'analysis_source': 'TokenAnalyzer',
                    'analysis_time': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Token analysis failed for {token_address}: {e}")
            return None
    
    def _get_chain_id(self, network: str) -> int:
        """Convert network name to chain ID."""
        chain_mapping = {
            'ethereum': 1,
            'bsc': 56,
            'polygon': 137,
            'arbitrum': 42161,
            'optimism': 10,
            'avalanche': 43114,
            'base': 8453,
            'fantom': 250,
            'cronos': 100,
            'moonbeam': 1284,
            'celo': 42220,
            'metis': 1088,
            'kava': 2222,
            'aurora': 1313161554,
            'harmony': 1666600000,
            'klaytn': 8217,
            'oasis': 42262,
            'fuse': 122,
            'evmos': 9001,
            'boba': 288,
            'moonriver': 235,
            'telos': 40,
            'thundercore': 19,
            'palm': 11297108109,
            'scroll': 534352,
            'manta': 169,
            'mantle': 5000,
            'polygonzkevm': 1101,
            'opbnb': 204,
            'blast': 81457,
            'linea': 59144,
            'syscoin': 560350,
            'velas': 128,
            'zksync': 324,
            'gnosis': 100,
            'arbitrumnova': 42170,
            'soneium': 1946  # Add Soneium chain support
        }
        return chain_mapping.get(network.lower(), 1)
    
    def _is_valid_address_for_chain(self, address: str, chain: str) -> bool:
        """
        Validate address format for different blockchain networks.
        
        Args:
            address: Token address to validate
            chain: Chain identifier (chainId or chain name)
            
        Returns:
            True if address is valid for the chain, False otherwise
        """
        if not address:
            return False
        
        # EVM chains (Ethereum, BSC, Polygon, Arbitrum, etc.)
        evm_chains = {
            'ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 'avalanche',
            'base', 'fantom', 'cronos', 'gnosis', 'moonbeam', 'celo', 'metis',
            'kava', 'aurora', 'harmony', 'klaytn', 'oasis', 'fuse', 'evmos',
            'boba', 'moonriver', 'telos', 'thundercore', 'palm', 'scroll',
            'manta', 'mantle', 'polygonzkevm', 'opbnb', 'blast', 'linea',
            'syscoin', 'velas', 'zksync', 'arbitrumnova', 'soneium',
            '1', '56', '137', '42161', '10', '43114', '8453', '250',
            '100', '1284', '42220', '1088', '2222', '1313161554',
            '1666600000', '8217', '42262', '122', '9001', '288',
            '235', '40', '19', '11297108109', '534352', '169',
            '5000', '1101', '204', '81457', '59144', '560350',
            '128', '324', '42170', '1946'
        }
        
        # Solana
        solana_chains = {'solana', 'sol'}
        
        # Aptos
        aptos_chains = {'aptos', 'apt'}
        
        # Tron
        tron_chains = {'tron', 'trx'}
        
        # Check chain type and validate accordingly
        chain_lower = chain.lower()
        
        if chain_lower in evm_chains:
            # EVM address validation
            return (address.startswith('0x') and 
                   len(address) == 42 and 
                   all(c in '0123456789abcdefABCDEF' for c in address[2:]) and
                   address != '0x0000000000000000000000000000000000000000')
        
        elif chain_lower in solana_chains:
            # Solana address validation (Base58 format, typically 44 chars)
            try:
                import base58
                decoded = base58.b58decode(address)
                return len(decoded) == 32  # 32 bytes for Solana addresses
            except:
                # Fallback: Basic length check for Solana addresses
                return len(address) >= 32 and len(address) <= 44
        
        elif chain_lower in aptos_chains:
            # Aptos address validation (resource format with 0x prefix)
            if address.startswith('0x') and '::' in address:
                parts = address.split('::')
                hex_part = parts[0]
                return (len(hex_part) == 66 and 
                       all(c in '0123456789abcdefABCDEF' for c in hex_part[2:]) and
                       len(parts) >= 3)
            else:
                return False
        
        elif chain_lower in tron_chains:
            # Tron address validation (starts with 'T', exactly 34 chars, base58)
            return (address.startswith('T') and 
                   len(address) == 34 and 
                   all(c.isalnum() for c in address))
        
        else:
            # Unknown chain - be permissive but log warning
            if chain.lower() not in ['soneium']:  # Only warn for truly unknown chains
                logger.warning(f"Unknown chain '{chain}' - accepting address {address}")
            return len(address) > 0
    
    async def _get_dexscreener_data(self, token_address: str) -> Optional[Dict]:
        """Fetch data from DEXScreener API with improved timeout handling."""
        try:
            url = f"{self.dexscreener_base}/dex/tokens/{token_address}"
            
            # Use shorter timeout and better error handling
            timeout = aiohttp.ClientTimeout(total=5.0, connect=2.0)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        logger.debug(f"Token {token_address} not found on DexScreener")
                        return None
                    elif response.status == 429:
                        logger.warning(f"Rate limited on DexScreener for {token_address}")
                        await asyncio.sleep(1.0)  # Brief pause on rate limit
                        return None
                    else:
                        logger.debug(f"DexScreener API status {response.status} for {token_address}")
                        return None
        except asyncio.TimeoutError:
            logger.warning(f"DexScreener timeout for {token_address}")
            return None
        except Exception as e:
            logger.error(f"DexScreener API error: {e}")
            return None
    
    async def _get_coingecko_data(self, token_address: str, network: str) -> Dict:
        """Fetch data from CoinGecko API"""
        try:
            platform = NetworkConfig.COINGECKO_PLATFORMS.get(network, 'ethereum')
            url = f"{self.coingecko_base}/coins/{platform}/contract/{token_address}"
            
            headers = {}
            if self.api_keys.get('coingecko_api_key'):
                headers['x-cg-demo-api-key'] = self.api_keys['coingecko_api_key']
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'verified': data.get('verified', False),
                            'description': data.get('description', {}).get('en', ''),
                            'links': data.get('links', {}),
                            'community_score': data.get('community_score', 0)
                        }
        except Exception as e:
            logger.debug(f"CoinGecko API error: {e}")
        
        return {}
    
    async def _get_onchain_metrics(self, token_address: str, network: str) -> Dict:
        """
        Get on-chain metrics
        Note: This would integrate with block explorer APIs in production
        """
        # Placeholder for on-chain metrics
        return {
            'holders': 0,
            'total_supply': 0,
            'security_score': 0.5
        }
    
    def _select_best_pair(self, pairs: List[Dict]) -> Optional[Dict]:
        """Select the best trading pair from available pairs"""
        if not pairs:
            return None
        
        # Filter for pairs with sufficient liquidity and volume
        valid_pairs = [
            pair for pair in pairs
            if float(pair.get('liquidity', {}).get('usd', 0)) > 10000
            and float(pair.get('volume', {}).get('h24', 0)) > 5000
        ]
        
        if not valid_pairs:
            return pairs[0]  # Return first pair if none meet criteria
        
        # Select pair with highest volume
        return max(valid_pairs, key=lambda p: float(p.get('volume', {}).get('h24', 0)))
    
    async def get_trending_tokens(self, network: str, limit: int = 10) -> List[str]:
        """Get trending tokens for a specific network using current search token."""
        try:
            # Use current search token from rotation instead of chain-based search
            search_term = self._get_current_search_token(network)
            chain_id = NetworkConfig.DEXSCREENER_CHAINS.get(network, 'bsc')
            url = f"{self.dexscreener_base}/dex/search?q={search_term}"
            
            # Use shorter timeout for better reliability
            timeout = aiohttp.ClientTimeout(total=5.0, connect=2.0)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        
                        # Filter for active pairs
                        recent_pairs = [
                            p for p in pairs 
                            if float(p.get('volume', {}).get('h24', 0)) > 10000
                            and float(p.get('liquidity', {}).get('usd', 0)) > 25000
                        ]
                        
                        # Extract unique token addresses with validation
                        tokens = []
                        for p in recent_pairs[:limit]:
                            token_addr = p.get('baseToken', {}).get('address')
                            token_symbol = p.get('baseToken', {}).get('symbol', 'UNKNOWN')
                            token_chain = p.get('chainId', 'unknown')
                            
                            # Multi-chain address validation
                            if self._is_valid_address_for_chain(token_addr, token_chain):
                                tokens.append(token_addr)
                                logger.debug(f"✅ Valid {token_chain} token: {token_symbol} - {token_addr}")
                            else:
                                logger.debug(f"❌ Invalid {token_chain} token: {token_symbol} - {token_addr}")
                        
                        return tokens
                    elif response.status == 429:
                        logger.warning(f"Rate limited on trending tokens for {network}")
                        await asyncio.sleep(1.0)
                        return []
                    else:
                        logger.debug(f"Trending tokens API status {response.status} for {network}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching trending tokens: {e}")
        
        return []
