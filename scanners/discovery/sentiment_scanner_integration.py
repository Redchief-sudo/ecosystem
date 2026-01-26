"""
Sentiment Scanner - ScannerBase Integration
============================================
Integration layer that wraps the SentimentScanner class to work with the existing
ScanDirector and ScannerBase infrastructure.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_scanner import ScannerBase

# Import the core sentiment scanner components
from .sentiment_scanner import (
    SentimentScanner as CoreSentimentScanner,
    SentimentAnalysis,
    Sentiment,
    RiskLevel,
    DataQuality,
)

logger = logging.getLogger('scanner.sentiment')


class SentimentScannerIntegration(ScannerBase):
    """
    Sentiment Scanner integration for ScanDirector.

    This class wraps the core SentimentScanner to work with the existing
    ScannerBase infrastructure used by ScanDirector.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the Sentiment Scanner integration.

        Args:
            config: Configuration dictionary with scanner settings
            **kwargs: Additional keyword arguments (network_manager, memory, ai, etc.)
        """
        super().__init__(config)

        # Extract integration-specific config
        self._integration_config = config or {}

        # Get external dependencies from kwargs
        self.network_manager = kwargs.get('network_manager')
        self.memory = kwargs.get('memory')
        self.ai = kwargs.get('ai')

        # Scanner-specific configuration
        self.min_liquidity_usd = float(self._integration_config.get('min_liquidity_usd', 10000))
        self.min_volume_24h_usd = float(self._integration_config.get('min_volume_24h_usd', 5000))
        self.min_ai_score = float(self._integration_config.get('min_ai_score', 0.6))
        self.max_tokens_per_scan = int(self._integration_config.get('max_tokens_per_scan', 50))
        self.supported_chains = self._integration_config.get('chains', [
            'ethereum', 'bsc', 'polygon', 'arbitrum', 'optimism', 'base', 'avalanche'
        ])

        # Initialize the core scanner
        self._core_scanner: Optional[CoreSentimentScanner] = None
        self._initialized = False

        logger.info(f"SentimentScannerIntegration initialized with {len(self.supported_chains)} chains")
    
    async def initialize(self) -> None:
        """Initialize the core sentiment scanner."""
        if self._initialized:
            logger.debug("SentimentScannerIntegration already initialized")
            return
        
        try:
            # Get API keys from environment or config
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            explorer_key = os.getenv('EXPLORER_API_KEY')
            
            # Create core scanner
            self._core_scanner = CoreSentimentScanner(
                anthropic_api_key=anthropic_key,
                explorer_api_key=explorer_key,
                max_concurrent=5,
                log_level='INFO'
            )
            
            # Initialize core scanner
            await self._core_scanner.initialize()
            
            self._initialized = True
            logger.info("✓ SentimentScannerIntegration initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SentimentScannerIntegration: {e}", exc_info=True)
            raise
    
    async def cleanup(self) -> None:
        """Cleanup scanner resources."""
        if self._core_scanner:
            await self._core_scanner.cleanup()
            self._core_scanner = None
        
        self._initialized = False
        logger.info("SentimentScannerIntegration cleanup complete")
    
    async def scan(self, *args, **kwargs) -> List[Dict]:
        """
        Main scan method for ScanDirector integration.
        
        Can be called as:
        - scan() - scans all configured chains
        - scan('ethereum') - scans specific chain
        - scan(chain='ethereum') - scans specific chain
        """
        # Determine target chain
        chain = None
        if args and isinstance(args[0], str):
            chain = args[0]
        elif 'chain' in kwargs:
            chain = kwargs['chain']
        
        if chain:
            return await self.scan_network(chain)
        else:
            # Scan all supported chains
            results = []
            for supported_chain in self.supported_chains:
                try:
                    chain_results = await self.scan_network(supported_chain)
                    results.extend(chain_results)
                except Exception as e:
                    logger.error(f"Error scanning chain {supported_chain}: {e}")
            return results
    
    async def scan_network(self, chain: str) -> List[Dict]:
        """
        Scan tokens on a specific chain for sentiment analysis.
        
        Args:
            chain: Chain identifier (e.g., 'ethereum', 'bsc')
            
        Returns:
            List of token dictionaries with sentiment analysis
        """
        if not self._initialized or not self._core_scanner:
            await self.initialize()
        
        # Check if chain is supported
        if chain.lower() not in [c.lower() for c in self.supported_chains]:
            logger.debug(f"Chain {chain} not supported by SentimentScanner")
            return []
        
        logger.info(f"Scanning {chain} for sentiment analysis...")
        
        # Get tokens from memory or use default tokens
        tokens_to_scan = await self._get_tokens_for_chain(chain)
        
        if not tokens_to_scan:
            logger.info(f"No tokens available for sentiment scan on {chain}")
            return []
        
        # Limit tokens per scan
        tokens_to_scan = tokens_to_scan[:self.max_tokens_per_scan]
        
        # Scan tokens
        results = []
        for token_info in tokens_to_scan:
            try:
                token_address = token_info.get('address')
                if not token_address:
                    continue
                
                # Scan the token
                if self._core_scanner:
                    analysis = await self._core_scanner.scan_token(token_address, chain)
                else:
                    logger.error(f"Core scanner not initialized for token {token_address}")
                    continue
                
                if analysis:
                    # Convert to dict format expected by ScanDirector
                    token_dict = self._analysis_to_dict(analysis, chain)
                    results.append(token_dict)
                    
                    # Log significant results
                    if analysis.overall_score > 80 or analysis.risk_level == RiskLevel.CRITICAL:
                        logger.info(f"⚠️ {analysis.symbol}: Score={analysis.overall_score}, Risk={analysis.risk_level.value}")
                        
            except Exception as e:
                logger.error(f"Error scanning token {token_info.get('symbol', 'unknown')}: {e}")
                continue
        
        logger.info(f"Sentiment scan complete for {chain}: {len(results)} tokens analyzed")
        return results
    
    async def _get_tokens_for_chain(self, chain: str) -> List[Dict]:
        """
        Get tokens to scan for a specific chain.
        
        Uses memory if available, otherwise falls back to default tokens.
        """
        # Try to get tokens from memory
        if self.memory:
            try:
                if hasattr(self.memory, 'get_all_tokens'):
                    all_tokens = self.memory.get_all_tokens() or []
                    
                    # Filter by chain and apply filters
                    chain_tokens = []
                    for token in all_tokens:
                        token_chain = getattr(token, 'chain', None) or token.get('chain') if isinstance(token, dict) else 'unknown'
                        if token_chain == chain:
                            # Apply basic filters
                            liquidity = float(getattr(token, 'liquidity_usd', 0) or token.get('liquidity_usd', 0) if isinstance(token, dict) else 0)
                            volume = float(getattr(token, 'volume_24h', 0) or token.get('volume_24h', 0) if isinstance(token, dict) else 0)
                            
                            if liquidity >= self.min_liquidity_usd and volume >= self.min_volume_24h_usd:
                                chain_tokens.append({
                                    'address': getattr(token, 'address', None) or token.get('address') if isinstance(token, dict) else None,
                                    'symbol': getattr(token, 'symbol', None) or token.get('symbol') if isinstance(token, dict) else 'UNKNOWN',
                                    'name': getattr(token, 'name', None) or token.get('name') if isinstance(token, dict) else 'Unknown Token',
                                })
                    
                    if chain_tokens:
                        return chain_tokens
                        
            except Exception as e:
                logger.debug(f"Error getting tokens from memory: {e}")
        
        # Fallback: Return default tokens for known chains
        return self._get_default_tokens_for_chain(chain)
    
    def _get_default_tokens_for_chain(self, chain: str) -> List[Dict]:
        """Get default tokens for major chains."""
        default_tokens = {
            'ethereum': [
                {'address': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', 'symbol': 'WETH', 'name': 'Wrapped Ether'},
                {'address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 'symbol': 'USDC', 'name': 'USD Coin'},
                {'address': '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', 'symbol': 'UNI', 'name': 'Uniswap'},
            ],
            'bsc': [
                {'address': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', 'symbol': 'WBNB', 'name': 'Wrapped BNB'},
                {'address': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d3', 'symbol': 'USDC', 'name': 'USD Coin'},
                {'address': '0x10ED43C718714eb63d5aA57B78B54704E256024E', 'symbol': 'CAKE', 'name': 'PancakeSwap'},
            ],
            'polygon': [
                {'address': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270', 'symbol': 'WMATIC', 'name': 'Wrapped Matic'},
                {'address': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', 'symbol': 'USDC', 'name': 'USD Coin'},
            ],
            'arbitrum': [
                {'address': '0x82aF49447D8a07e3bd95BD0d56f35241523fBab1', 'symbol': 'WETH', 'name': 'Wrapped Ether'},
                {'address': '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8', 'symbol': 'USDC', 'name': 'USD Coin'},
            ],
            'optimism': [
                {'address': '0x4200000000000000000000000000000000000006', 'symbol': 'WETH', 'name': 'Wrapped Ether'},
                {'address': '0x7F5c764cBc14f9669B88837ca1490cCa17c31607', 'symbol': 'USDC', 'name': 'USD Coin'},
            ],
            'base': [
                {'address': '0x4200000000000000000000000000000000000006', 'symbol': 'WETH', 'name': 'Wrapped Ether'},
                {'address': '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913', 'symbol': 'USDC', 'name': 'USD Coin'},
            ],
            'avalanche': [
                {'address': '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7', 'symbol': 'WAVAX', 'name': 'Wrapped AVAX'},
                {'address': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E', 'symbol': 'USDC', 'name': 'USD Coin'},
            ],
        }
        
        return default_tokens.get(chain.lower(), [])
    
    def _analysis_to_dict(self, analysis: SentimentAnalysis, chain: str) -> Dict[str, Any]:
        """
        Convert SentimentAnalysis to dictionary format.
        
        Args:
            analysis: SentimentAnalysis object
            chain: Chain identifier
            
        Returns:
            Dictionary with token data and sentiment analysis
        """
        return {
            'address': analysis.token_address,
            'symbol': analysis.symbol,
            'name': f"{analysis.symbol} Sentiment Analysis",
            'decimals': 18,
            
            # Market data (from analysis)
            'price': analysis.overall_score / 100.0,  # Use score as proxy
            'price_change_24h': 0.0,
            'volume_24h': 0.0,
            'liquidity_usd': 0.0,
            
            # AI/Scoring data
            'ai_score': analysis.overall_score / 100.0,
            'confidence': analysis.confidence,
            'risk_score': {
                'rugpull': analysis.rugpull_risk,
                'honeypot': analysis.honeypot_risk,
                'whale': analysis.whale_concentration,
            },
            
            # Sentiment data
            'sentiment': {
                'overall_score': analysis.overall_score,
                'sentiment': analysis.sentiment.value,
                'confidence': analysis.confidence,
                'risk_level': analysis.risk_level.value,
                'recommendation': analysis.recommendation,
                'summary': analysis.summary,
                'key_factors': analysis.key_factors,
                'technical_signals': analysis.technical_signals,
            },
            
            # Metadata
            'chain': chain,
            'chain_id': self._get_chain_id(chain),
            'data_quality': analysis.data_quality.value,
            'ai_powered': analysis.ai_powered,
            
            # Timestamps
            'first_seen': datetime.now(timezone.utc).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            
            # Scanner metadata
            'metadata': {
                'scanner_type': 'sentiment_scanner',
                'scanned_at': datetime.now(timezone.utc).isoformat(),
                'version': '2.1',
            }
        }
    
    def _get_chain_id(self, chain: str) -> int:
        """Get chain ID from chain name."""
        chain_ids = {
            'ethereum': 1,
            'bsc': 56,
            'polygon': 137,
            'arbitrum': 42161,
            'optimism': 10,
            'base': 8453,
            'avalanche': 43114,
            'fantom': 250,
            'cronos': 25,
            'moonbeam': 1284,
            'celo': 42220,
        }
        return chain_ids.get(chain.lower(), 0)
    
    def get_scan_summary(self) -> Dict[str, Any]:
        """Get scan summary for monitoring."""
        base_summary = super().get_scan_summary()
        
        if self._core_scanner:
            stats = self._core_scanner.get_statistics()
            base_summary.update({
                'core_stats': stats,
                'supported_chains': self.supported_chains,
                'config': {
                    'min_liquidity_usd': self.min_liquidity_usd,
                    'min_volume_24h_usd': self.min_volume_24h_usd,
                    'min_ai_score': self.min_ai_score,
                    'max_tokens_per_scan': self.max_tokens_per_scan,
                }
            })
        
        return base_summary


# Export classes
__all__ = ['SentimentScannerIntegration']

