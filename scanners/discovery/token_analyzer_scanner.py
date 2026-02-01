"""
Scanner Wrapper for TokenAnalyzer v2.1
Integrates the new TokenAnalyzer with the ScanDirector system
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from scanners.base_scanner import ScannerBase
from scanners.discovery.token_analyzer import (
    TokenAnalyzer, 
    AnalyzerConfig,
    MetricsCollector,
    CacheManager,
    InMemoryCacheBackend
)
from web3 import Web3

logger = logging.getLogger(__name__)


# Default RPC endpoints for fallback when network_manager is unavailable
DEFAULT_RPC_ENDPOINTS = {
    'ethereum': 'https://eth.llamarpc.com',
    'bsc': 'https://bsc.publicnode.com',
    'polygon': 'https://polygon.publicnode.com',
    'arbitrum': 'https://arbitrum.publicnode.com',
    'optimism': 'https://optimism.publicnode.com',
    'avalanche': 'https://avalanche.publicnode.com',
    'fantom': 'https://rpc2.fantom.network/',
    'base': 'https://mainnet.base.org',
    'zksync_era': 'https://mainnet.era.zksync.io',
    'scroll': 'https://rpc.scroll.io',
}


class TokenAnalyzerScanner(ScannerBase):
    """
    Scanner wrapper for the new TokenAnalyzer v2.1
    Makes it compatible with ScanDirector system
    """
    
    # Lower default min_market_cap for better token discovery
    DEFAULT_MIN_MARKET_CAP = 100000  # $100k (lowered from $1M)
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, network_manager=None, **kwargs):
        super().__init__(config, **kwargs)
        self.name = "TokenAnalyzerScanner"
        self.network_manager = network_manager
        self.analyzer: Optional[TokenAnalyzer] = None
        self.web3_connections: Dict[str, Web3] = {}
        self._using_fallback_rpc = False
        
        # Configuration
        self.max_tokens_per_scan = self.config.get('max_tokens_per_scan', 10)
        self.min_market_cap = self.config.get('min_market_cap', self.DEFAULT_MIN_MARKET_CAP)
        self.supported_chains = self.config.get('supported_chains', [
            'ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 
            'avalanche', 'fantom', 'base', 'zksync_era', 'scroll'
        ])
        
        logger.info(f"TokenAnalyzerScanner initialized with chains: {self.supported_chains}")
        logger.info(f"Min market cap threshold: ${self.min_market_cap:,.0f}")
    
    async def initialize(self) -> None:
        """Initialize TokenAnalyzer and Web3 connections"""
        await super().initialize()
        
        # Try to use network_manager if available
        if self.network_manager:
            await self._initialize_with_network_manager()
        else:
            # Use fallback RPC endpoints
            await self._initialize_with_fallback_rpc()
        
        if not self.web3_connections:
            logger.error("No Web3 connections established - TokenAnalyzerScanner will return empty results")
        else:
            logger.info(f"TokenAnalyzerScanner initialized with {len(self.web3_connections)} chains")
    
    async def _initialize_with_network_manager(self) -> None:
        """Initialize using network_manager"""
        for chain_name in self.supported_chains:
            try:
                web3_client = None

                # Preferred API: network_manager.get_web3(chain) (returns Web3 or stub)
                if hasattr(self.network_manager, 'get_web3'):
                    try:
                        web3_client = self.network_manager.get_web3(chain_name)
                    except Exception:
                        web3_client = None

                # Secondary API: network_manager.get_client(chain) -> ChainClient with .client
                if web3_client is None and hasattr(self.network_manager, 'get_client'):
                    try:
                        client = self.network_manager.get_client(chain_name)
                        if client and hasattr(client, 'client'):
                            web3_client = client.client
                    except Exception:
                        web3_client = None

                # Backwards-compatible: get_network() or NETWORKS mapping with rpc attr
                if web3_client is None:
                    if hasattr(self.network_manager, 'get_network'):
                        try:
                            network = self.network_manager.get_network(chain_name)
                            if network and hasattr(network, 'rpc'):
                                web3_client = Web3(Web3.HTTPProvider(network.rpc))
                        except Exception:
                            web3_client = None
                    elif hasattr(self.network_manager, 'NETWORKS'):
                        try:
                            network = self.network_manager.NETWORKS.get(chain_name)
                            if network and hasattr(network, 'rpc'):
                                web3_client = Web3(Web3.HTTPProvider(network.rpc))
                        except Exception:
                            web3_client = None

                if web3_client:
                    self.web3_connections[chain_name] = web3_client
                    logger.info(f"Connected to {chain_name} via network_manager")
                else:
                    logger.warning(f"Could not obtain Web3 for {chain_name} from network_manager")

            except Exception as e:
                logger.warning(f"Failed to connect to {chain_name} via network_manager: {e}")
                # Will try fallback RPC below
    
    async def _initialize_with_fallback_rpc(self) -> None:
        """Initialize using default RPC endpoints (fallback)"""
        logger.warning("No network_manager available, using default RPC endpoints")
        self._using_fallback_rpc = True
        
        for chain_name in self.supported_chains:
            if chain_name in DEFAULT_RPC_ENDPOINTS:
                try:
                    rpc_url = DEFAULT_RPC_ENDPOINTS[chain_name]
                    web3 = Web3(Web3.HTTPProvider(rpc_url))
                    if web3.is_connected():
                        self.web3_connections[chain_name] = web3
                        logger.info(f"Connected to {chain_name} via fallback RPC")
                    else:
                        logger.warning(f"Failed to connect to {chain_name} via fallback RPC")
                except Exception as e:
                    logger.warning(f"Failed to connect to {chain_name}: {e}")
        
        if not self.web3_connections:
            logger.error("No Web3 connections available via fallback RPCs either")
    
    async def scan(self, chain: str = None, **kwargs) -> List[Dict]:
        """
        Scan tokens using TokenAnalyzer
        
        Args:
            chain: Specific chain to scan, or None for all chains
            **kwargs: Additional scan parameters
            
        Returns:
            List of token data dictionaries
        """
        # Return empty list if no Web3 connections
        if not self.web3_connections:
            logger.warning("No Web3 connections available - returning empty results")
            return []
        
        # Default tokens to analyze (can be configured)
        default_tokens = [
            # Ethereum
            ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "ethereum"),  # USDC
            ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "ethereum"),  # USDT
            ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "ethereum"),  # WETH
            
            # BSC
            ("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "bsc"),  # USDC
            ("0x55d398326f99059fF775485246999027B3197955", "bsc"),  # USDT
            ("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", "bsc"),  # WBNB
            
            # Polygon
            ("0x2791Bca1f2de4661ed88A30C99A7a9449Aa84174", "polygon"),  # USDC
            ("0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0", "polygon"),  # MATIC
        ]
        
        # Filter by chain if specified
        if chain:
            tokens_to_scan = [(addr, ch) for addr, ch in default_tokens if ch == chain]
        else:
            tokens_to_scan = default_tokens
        
        # Limit number of tokens per scan
        tokens_to_scan = tokens_to_scan[:self.max_tokens_per_scan]
        
        logger.info(f"TokenAnalyzer scanning {len(tokens_to_scan)} tokens on chain: {chain or 'all'}")
        
        try:
            # Check if TokenAnalyzer is available
            if self.analyzer:
                # Use full TokenAnalyzer
                return await self._scan_with_analyzer(tokens_to_scan)
            else:
                # Use simple Web3-based scanning
                return await self._scan_simple(tokens_to_scan)
            
        except Exception as e:
            logger.error(f"TokenAnalyzer scan failed: {e}", exc_info=True)
            return []
    
    async def _scan_with_analyzer(self, tokens_to_scan: List[tuple]) -> List[Dict]:
        """Scan using full TokenAnalyzer"""
        results = []
        async for token_info in self.analyzer.analyze_batch_stream(tokens_to_scan):
            token_dict = {
                'address': token_info.address,
                'symbol': token_info.symbol,
                'name': token_info.name,
                'chain': token_info.chain,
                'chain_id': token_info.chain_id,
                'decimals': token_info.decimals,
                'price_usd': token_info.price_data.current_price_usd,
                'volume_24h': token_info.price_data.volume_24h_usd,
                'market_cap': token_info.price_data.market_cap_usd,
                'liquidity_usd': token_info.price_data.liquidity_usd,
                'verified': token_info.metadata.verified,
                'data_quality_score': token_info.metadata.data_quality_score,
                'analysis_time': token_info.metadata.analysis_time.isoformat(),
                'analysis_duration_ms': token_info.metadata.analysis_duration_ms,
                'source': 'token_analyzer_v2.1',
                'scanner_name': self.name,
            }
            
            # Apply market cap filter
            if token_info.price_data.market_cap_usd >= self.min_market_cap:
                results.append(token_dict)
            else:
                logger.debug(f"Filtered token {token_info.symbol} - market cap too low: ${token_info.price_data.market_cap_usd:,.0f}")
        
        logger.info(f"TokenAnalyzer scan completed: {len(results)} tokens found")
        return results
    
    async def _scan_simple(self, tokens_to_scan: List[tuple]) -> List[Dict]:
        """Simple scanning using just Web3 (fallback when TokenAnalyzer unavailable)"""
        results = []
        
        for token_address, chain in tokens_to_scan:
            if chain not in self.web3_connections:
                continue
            
            try:
                web3 = self.web3_connections[chain]
                checksum_addr = web3.to_checksum_address(token_address)
                
                # Get basic token info from contract
                contract = web3.eth.contract(
                    address=checksum_addr,
                    abi=[
                        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
                        {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
                        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
                    ]
                )
                
                symbol = await asyncio.to_thread(contract.functions.symbol().call)
                name = await asyncio.to_thread(contract.functions.name().call)
                decimals = await asyncio.to_thread(contract.functions.decimals().call)
                
                token_dict = {
                    'address': token_address,
                    'symbol': symbol,
                    'name': name,
                    'chain': chain,
                    'chain_id': 0,
                    'decimals': decimals,
                    'price_usd': 0.0,
                    'volume_24h': 0.0,
                    'market_cap': 0.0,
                    'liquidity_usd': 0.0,
                    'verified': False,
                    'data_quality_score': 0.3,  # Low quality (simple scan)
                    'analysis_time': datetime.now(timezone.utc).isoformat(),
                    'analysis_duration_ms': 0,
                    'source': 'token_analyzer_simple',
                    'scanner_name': self.name,
                    'metadata': {
                        'scan_mode': 'simple_web3',
                        'using_fallback_rpc': self._using_fallback_rpc,
                    }
                }
                
                results.append(token_dict)
                logger.debug(f"Found token via simple scan: {symbol} on {chain}")
                
            except Exception as e:
                logger.debug(f"Failed to scan {token_address} on {chain}: {e}")
                continue
        
        logger.info(f"TokenAnalyzer simple scan completed: {len(results)} tokens found")
        return results
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        if self.analyzer:
            await self.analyzer.close()
        
        # Close Web3 connections
        for chain, web3 in self.web3_connections.items():
            try:
                if hasattr(web3, 'provider') and hasattr(web3.provider, 'session'):
                    # aiohttp-based provider
                    if hasattr(web3.provider.session, 'close'):
                        await web3.provider.session.close()
            except Exception:
                pass  # Best effort cleanup
        
        await super().cleanup()
        logger.info("TokenAnalyzerScanner cleanup completed")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get analyzer metrics"""
        if self.analyzer:
            return self.analyzer.get_metrics()
        return {
            'mode': 'simple' if not self.analyzer else 'full',
            'chains_connected': len(self.web3_connections),
            'using_fallback_rpc': self._using_fallback_rpc,
        }
