"""
Scanner Wrapper for DexScreener Scanner
Integrates the new DexScreener scanner with the ScanDirector system
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from scanners.base_scanner import ScannerBase
from scanners.discovery.dex_screener_scanner import DexScreenerScanner as BaseDexScreenerScanner

logger = logging.getLogger(__name__)


class DexScreenerScannerWrapper(ScannerBase):
    """
    Scanner wrapper for the new DexScreener scanner
    Makes it compatible with ScanDirector system
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, network_manager=None, **kwargs):
        super().__init__(config, **kwargs)
        self.name = "DexScreenerScannerWrapper"
        self.network_manager = network_manager  # Store the network_manager
        self.dex_screener: Optional[BaseDexScreenerScanner] = None
        
        # Configuration
        self.api_url = self.config.get('api_url', 'https://api.dexscreener.com/token-profiles/latest/v1')
        self.timeout = self.config.get('timeout', 30)
        self.rate_limit = self.config.get('rate_limit', 10)
        self.min_volume_24h = self.config.get('min_volume_24h', 50000)
        self.min_liquidity = self.config.get('min_liquidity', 10000)
        self.max_age_hours = self.config.get('max_age_hours', 24)
        self.supported_chains = self.config.get('supported_chains', [
            'ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 
            'avalanche', 'fantom', 'base'
        ])
        
        logger.info(f"DexScreenerScannerWrapper initialized with chains: {self.supported_chains}")
    
    async def initialize(self) -> None:
        """Initialize DexScreener scanner"""
        await super().initialize()
        
        # Initialize the actual DexScreener scanner
        scanner_config = {
            'api_url': self.api_url,
            'timeout': self.timeout,
            'rate_limit': self.rate_limit,
            'min_volume_24h': self.min_volume_24h,
            'min_liquidity': self.min_liquidity,
            'max_age_hours': self.max_age_hours,
            'supported_chains': self.supported_chains,
            'debug': self.config.get('debug', False)
        }
        
        self.dex_screener = BaseDexScreenerScanner(
            config=scanner_config,
            ai=getattr(self, 'ai_controller', None),
            memory=getattr(self, 'memory', None)
        )
        
        # Initialize the scanner
        if hasattr(self.dex_screener, 'initialize'):
            await self.dex_screener.initialize()
        
        logger.info("DexScreenerScannerWrapper initialized successfully")
    
    async def scan(self, chain: str = None, **kwargs) -> List[Dict]:
        """
        Scan tokens using DexScreener
        
        Args:
            chain: Specific chain to scan, or None for all chains
            **kwargs: Additional scan parameters
            
        Returns:
            List of token data dictionaries
        """
        if not self.dex_screener:
            logger.error("DexScreener scanner not initialized")
            return []
        
        logger.info(f"DexScreener scanning chain: {chain or 'all'}")
        logger.debug(f"DexScreener config: min_volume_24h={self.min_volume_24h}, min_liquidity={self.min_liquidity}")
        
        try:
            # Call the DexScreener scanner with only supported parameters
            scan_kwargs = {
                'chain': chain
            }
            
            # The DexScreener scanner should return list of TokenCandidate objects
            logger.debug(f"Calling DexScreenerScanner.scan with chain={chain}")
            raw_results = await self.dex_screener.scan(**scan_kwargs)
            
            logger.info(f"DexScreener raw results: {len(raw_results)} tokens returned")
            logger.debug(f"Raw results type: {type(raw_results)}")
            if raw_results:
                logger.debug(f"First result type: {type(raw_results[0])}")
                if hasattr(raw_results[0], '__dict__'):
                    logger.debug(f"First result attributes: {raw_results[0].__dict__.keys() if hasattr(raw_results[0].__dict__, 'keys') else raw_results[0].__dict__}")
            
            # Convert results to expected format
            results = []
            for i, token_data in enumerate(raw_results):
                logger.debug(f"Processing token {i}: type={type(token_data)}")
                
                # Handle different result formats
                if isinstance(token_data, dict):
                    logger.debug(f"Token {i} is dict with keys: {token_data.keys()}")
                    # Already in dict format, just ensure required fields
                    token_dict = {
                        'address': token_data.get('address', ''),
                        'symbol': token_data.get('symbol', ''),
                        'name': token_data.get('name', ''),
                        'chain': token_data.get('chain', chain or ''),
                        'chain_id': token_data.get('chain_id', 0),
                        'decimals': token_data.get('decimals', 18),
                        'price_usd': token_data.get('price_usd', 0.0),
                        'volume_24h': token_data.get('max_volume_24h', token_data.get('volume_24h', 0.0)),
                        'market_cap': token_data.get('market_cap', 0.0),
                        'liquidity_usd': token_data.get('total_liquidity_usd', token_data.get('liquidity_usd', 0.0)),
                        'verified': token_data.get('verified', False),
                        'source': 'dex_screener_v2.1',
                        'scanner_name': self.name,
                        'scan_time': datetime.now(timezone.utc).isoformat(),
                        'raw_data': token_data
                    }
                    
                    logger.debug(f"Token {i} parsed: vol={token_dict['volume_24h']}, liq={token_dict['liquidity_usd']}")
                    
                    # Apply filters
                    if (token_dict['volume_24h'] >= self.min_volume_24h and 
                        token_dict['liquidity_usd'] >= self.min_liquidity):
                        results.append(token_dict)
                        logger.debug(f"Token {i} PASSED filters")
                    else:
                        logger.debug(f"Token {i} FILTERED OUT - vol: ${token_dict['volume_24h']:,.0f} < ${self.min_volume_24h:,.0f} or liq: ${token_dict['liquidity_usd']:,.0f} < ${self.min_liquidity:,.0f}")
                
                elif hasattr(token_data, '__dict__'):
                    # Handle object results (like TokenCandidate)
                    token_obj = token_data
                    logger.debug(f"Token {i} is object with __dict__: {token_obj.__dict__.keys() if hasattr(token_obj.__dict__, 'keys') else 'N/A'}")
                    
                    # Handle TokenCandidate-style objects with max_volume_24h and total_liquidity_usd
                    token_dict = {
                        'address': getattr(token_obj, 'address', getattr(token_obj, 'token_id', '').split(':')[-1] if ':' in getattr(token_obj, 'token_id', '') else ''),
                        'symbol': getattr(token_obj, 'symbol', ''),
                        'name': getattr(token_obj, 'name', ''),
                        'chain': getattr(token_obj, 'chain', chain or ''),
                        'chain_id': getattr(token_obj, 'chain_id', 0),
                        'decimals': getattr(token_obj, 'decimals', 18),
                        'price_usd': getattr(token_obj, 'price_usd', 0.0),
                        'volume_24h': getattr(token_obj, 'max_volume_24h', getattr(token_obj, 'volume_24h', 0.0)),
                        'market_cap': getattr(token_obj, 'market_cap', 0.0),
                        'liquidity_usd': getattr(token_obj, 'total_liquidity_usd', getattr(token_obj, 'liquidity_usd', 0.0)),
                        'verified': getattr(token_obj, 'verified', False),
                        'source': 'dex_screener_v2.1',
                        'scanner_name': self.name,
                        'scan_time': datetime.now(timezone.utc).isoformat(),
                        'raw_data': token_obj.__dict__ if hasattr(token_obj, '__dict__') else {}
                    }
                    
                    logger.debug(f"Token {i} parsed: vol={token_dict['volume_24h']}, liq={token_dict['liquidity_usd']}")
                    
                    # Apply filters
                    if (token_dict['volume_24h'] >= self.min_volume_24h and 
                        token_dict['liquidity_usd'] >= self.min_liquidity):
                        results.append(token_dict)
                        logger.debug(f"Token {i} PASSED filters")
                    else:
                        logger.debug(f"Token {i} FILTERED OUT - vol: ${token_dict['volume_24h']:,.0f} < ${self.min_volume_24h:,.0f} or liq: ${token_dict['liquidity_usd']:,.0f} < ${self.min_liquidity:,.0f}")
                else:
                    logger.warning(f"Token {i} has unknown type: {type(token_data)}")
            
            logger.info(f"DexScreener scan completed: {len(results)} tokens found out of {len(raw_results)} raw results")
            return results
            
        except Exception as e:
            logger.error(f"DexScreener scan failed: {e}", exc_info=True)
            return []
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        if self.dex_screener and hasattr(self.dex_screener, 'cleanup'):
            await self.dex_screener.cleanup()
        
        await super().cleanup()
        logger.info("DexScreenerScannerWrapper cleanup completed")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get scanner metrics"""
        if self.dex_screener and hasattr(self.dex_screener, 'get_metrics'):
            return self.dex_screener.get_metrics()
        return {}
