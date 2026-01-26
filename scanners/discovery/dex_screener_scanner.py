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
from networks.chain_constants import get_chain_id
from config.network_config import NetworkConfig

logger = logging.getLogger(__name__)

class DexScreenerScanner(ScannerBase):
    """
    Elite DexScreener Scanner for discovering high-potential tokens.
    Uses DexScreener API to find trending tokens with advanced filtering.
    """

    # Chain-specific decimals lookup
    CHAIN_DEFAULT_DECIMALS = {
        'ethereum': 18,
        'bsc': 18,
        'polygon': 18,
        'arbitrum': 18,
        'optimism': 18,
        'avalanche': 18,
        'fantom': 18,
        'base': 18,
        'celo': 18,
        'cronos': 18
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None, ai=None, memory=None, **kwargs):
        super().__init__(config, **kwargs)
        self.name = "DexScreenerScanner"
        self.api_base_url = "https://api.dexscreener.com/latest"
        self.session = None
        
        # Initialize AI controller
        self._ai_controller = ai or kwargs.get('ai_controller') or kwargs.get('elite_ai_controller')
        
        # Initialize memory for token persistence
        self.memory = memory or kwargs.get('memory')
        self._memory_is_async = hasattr(self.memory, 'add_token') and asyncio.iscoroutinefunction(
            getattr(self.memory, 'add_token', None)
        ) if self.memory else False
        
        self.scan_count = 0
        self.running = False

        # Default configuration
        self.config.setdefault('min_liquidity', 10000.0)
        self.config.setdefault('min_volume', 5000.0)
        self.config.setdefault('ai_score_threshold', 0.6)
        self.config.setdefault('max_age_hours', 24)
        self.config.setdefault('max_tokens_per_scan', 50)
        self.config.setdefault('scan_mode', 'ultra')
        
        # Scanner-specific timeout (longer for discovery scanners)
        self.config.setdefault('timeout_seconds', 120.0)  # 2 minutes for DexScreener
        
        # Advanced rate limiting
        self.config.setdefault('rate_limit_delay', 0.5)
        self.config.setdefault('rate_limit_window', 60)
        self.config.setdefault('max_requests_per_window', 80)  # Conservative default
        self.config.setdefault('rate_limit_backoff_multiplier', 2.0)
        self.config.setdefault('max_rate_limit_backoff', 30)
        
        # Dynamic throttling parameters
        self.config.setdefault('dynamic_throttling', True)
        self.config.setdefault('target_response_time', 2.0)  # Target 2s response time
        self.config.setdefault('min_delay', 0.2)  # Minimum 200ms delay
        self.config.setdefault('max_delay', 3.0)  # Maximum 3s delay
        self.config.setdefault('success_rate_threshold', 0.8)  # 80% success rate threshold
        self.config.setdefault('adjustment_factor', 1.2)  # Adjustment multiplier
        
        # Dynamic throttling state
        self._dynamic_metrics = {
            'response_times': deque(maxlen=10),  # Last 10 response times
            'success_count': 0,
            'error_count': 0,
            'current_delay': self.config['rate_limit_delay'],
            'last_adjustment': time.time(),
            'adjustment_interval': 15  # Adjust every 15 seconds
        }
        
        # Token rotation state
        self._rotation_state = {
            'current_token_index': 0,
            'last_rotation': time.time(),
            'rotation_interval': 60  # Rotate every scan cycle (60 seconds)
        }
        
        # Per-chain circuit breaker state - better for discovery scanners
        self._chain_circuit_breakers = defaultdict(lambda: {
            'failures': 0,
            'last_failure': 0,
            'threshold': 3,  # Open circuit after 3 failures per chain (more aggressive)
            'timeout': 300,  # Reset circuit after 5 minutes per chain
            'state': 'closed',  # 'closed' = normal, 'open' = stopped
            'last_reset': time.time()
        })
        
        # Global circuit breaker for transport-level failures only
        self._global_circuit_breaker = {
            'failures': 0,
            'last_failure': 0,
            'threshold': 10,  # Open after 10 global transport failures
            'timeout': 600,  # Reset after 10 minutes
            'state': 'closed',
            'last_reset': time.time()
        }
        
        # Volatility and filtering
        self.config.setdefault('max_volatility_1h', 50.0)
        self.config.setdefault('min_price_change_1h', 0.0)
        self.config.setdefault('dynamic_thresholds', True)  # Adapt to chain conditions
        
        # AI and scoring
        self.config.setdefault('memory_retry_attempts', 3)
        self.config.setdefault('memory_retry_delay', 0.5)
        self.config.setdefault('require_ai_score', False)
        self.config.setdefault('ai_timeout_seconds', 10.0)
        self.config.setdefault('ai_batch_delay', 0.2)
        
        # Parallel processing
        self.config.setdefault('parallel_processing', True)
        self.config.setdefault('batch_size', 10)
        self.config.setdefault('max_concurrent_batches', 3)
        self.config.setdefault('persist_batch_size', 20)
        
        # Logging
        self.config.setdefault('verbose_logging', False)
        
        # Per-chain rate limiting
        self._rate_limiters = {}  # chain -> rate limiter state
        self._global_rate_limiter = {
            'last_request': 0,
            'request_count': 0,
            'backoff_until': 0
        }
        
        # Dynamic threshold tracking
        self._chain_metrics = defaultdict(lambda: {
            'avg_liquidity': 0,
            'avg_volume': 0,
            'avg_volatility': 0,
            'sample_count': 0
        })
        
        # Log initialization
        ai_status = f"with {type(self._ai_controller).__name__}" if self._ai_controller else "without AI"
        mem_status = "async" if self._memory_is_async else "sync" if self.memory else "none"
        logger.info(f"DexScreenerScanner initialized {ai_status}, memory: {mem_status}")

    async def initialize(self) -> None:
        """Initialize the scanner with HTTP session."""
        try:
            import aiohttp
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={'User-Agent': 'EliteScanner/2.0'}
            )
            self.running = True
            logger.info("✅ Initialized Elite DexScreener Scanner v2")
        except ImportError:
            logger.error("❌ aiohttp not available, scanner cannot function")
            self.running = False

    async def cleanup(self) -> None:
        """Clean up HTTP session."""
        self.running = False
        if self.session and not self.session.closed:
            try:
                await self.session.close()
                await asyncio.sleep(0.1)  # Brief pause to ensure cleanup
                logger.debug("✅ DexScreener HTTP session closed")
            except Exception as e:
                logger.warning(f"Error closing DexScreener session: {e}")
        self.session = None

    async def scan(self, chain: str = "ethereum") -> List[Dict]:
        """
        Scan for tokens on the specified chain using DexScreener API.

        Args:
            chain: Blockchain network to scan

        Returns:
            List of token data dictionaries
        """
        if not hasattr(self, 'session') or self.session is None:
            logger.error("DexScreener scanner not initialized - cannot scan")
            return []
            
        start_time = time.time()
        self.last_scan_time = datetime.now(timezone.utc)
        self.scan_count += 1

        try:
            log_level = logger.info if self.config['verbose_logging'] else logger.debug
            log_level(f"🚀 Scan #{self.scan_count} on {chain} (mode: {self.config['scan_mode']})")

            # Fetch tokens from DexScreener
            raw_tokens = await self._fetch_tokens_from_dexscreener(chain)

            if not raw_tokens:
                logger.info(f"No tokens found for chain {chain} - this is normal for discovery")
                self._record_success(0.1, chain)  # Record as success with minimal response time
                return []

            # Process tokens with concurrent batching
            processed_tokens = await self._process_tokens(raw_tokens, chain)

            if not processed_tokens:
                logger.warning(f"No tokens passed initial processing for {chain}")
                return []

            # Update dynamic thresholds if enabled
            if self.config['dynamic_thresholds']:
                self._update_chain_metrics(chain, processed_tokens)

            # Apply AI scoring with timeout protection
            if self._ai_controller is not None:
                processed_tokens = await self._apply_ai_scoring(processed_tokens)
            elif self.config['require_ai_score']:
                logger.warning("AI scoring required but unavailable - returning empty results")
                return []

            # Filter by thresholds (dynamic or static)
            elite_tokens = self._filter_elite_tokens(processed_tokens, chain)

            # Persist to memory with batch optimization
            scanned_tokens = await self._persist_tokens(elite_tokens)

            scan_time = time.time() - start_time
            logger.info(
                f"✅ Scan complete: {len(raw_tokens)} raw → {len(processed_tokens)} processed → "
                f"{len(elite_tokens)} elite → {len(scanned_tokens)} persisted ({scan_time:.2f}s)"
            )

            return scanned_tokens

        except asyncio.CancelledError:
            # Cancellation is NOT a failure - propagate without recording
            logger.debug(f"Scan cancelled for {chain} - propagating")
            raise
        except asyncio.TimeoutError:
            # Timeout is NOT a scanner failure - it's orchestration timeout
            logger.info(f"⏱️ Scan timeout for {chain} (non-failure)")
            return []
        except Exception as e:
            logger.error(f"❌ Scan failed for {chain}: {e}", exc_info=True)
            return []

    def _get_rate_limiter(self, chain: str) -> Dict:
        """Get or create per-chain rate limiter."""
        if chain not in self._rate_limiters:
            self._rate_limiters[chain] = {
                'last_request': 0,
                'request_count': 0,
                'backoff_until': 0,
                'backoff_duration': self.config['rate_limit_delay']
            }
        return self._rate_limiters[chain]

    async def _rate_limit(self, chain: str = None) -> None:
        """Smart per-chain and global rate limiting with exponential backoff."""
        current_time = time.time()
        
        # Global rate limiting
        global_limiter = self._global_rate_limiter
        
        # Check global backoff
        if current_time < global_limiter['backoff_until']:
            wait_time = global_limiter['backoff_until'] - current_time
            if self.config['verbose_logging']:
                logger.debug(f"⏸️ Global backoff active, waiting {wait_time:.1f}s")
            try:
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                logger.debug("Rate limit sleep cancelled (global backoff) - propagating")
                raise
            current_time = time.time()
        
        # Reset global window if expired
        if current_time - global_limiter['last_request'] > self.config['rate_limit_window']:
            global_limiter['request_count'] = 0
        
        # Check global rate limit
        if global_limiter['request_count'] >= self.config['max_requests_per_window']:
            wait_time = self.config['rate_limit_window'] - (current_time - global_limiter['last_request'])
            if wait_time > 0:
                logger.debug(f"⏸️ Global rate limit reached, waiting {wait_time:.1f}s")
                try:
                    await asyncio.sleep(wait_time)
                except asyncio.CancelledError:
                    logger.debug("Rate limit sleep cancelled (global rate limit) - propagating")
                    raise
                global_limiter['request_count'] = 0
        
        # Per-chain rate limiting
        if chain:
            chain_limiter = self._get_rate_limiter(chain)
            
            # Check chain backoff
            if current_time < chain_limiter['backoff_until']:
                wait_time = chain_limiter['backoff_until'] - current_time
                try:
                    await asyncio.sleep(wait_time)
                except asyncio.CancelledError:
                    logger.debug(f"Rate limit sleep cancelled ({chain} backoff) - propagating")
                    raise
            
            # Ensure minimum delay between requests
            if chain_limiter['last_request'] > 0:
                elapsed = current_time - chain_limiter['last_request']
                if elapsed < chain_limiter['backoff_duration']:
                    try:
                        await asyncio.sleep(chain_limiter['backoff_duration'] - elapsed)
                    except asyncio.CancelledError:
                        logger.debug(f"Rate limit sleep cancelled ({chain} delay) - propagating")
                    raise
            
            chain_limiter['last_request'] = time.time()
            chain_limiter['request_count'] += 1
        
        global_limiter['last_request'] = time.time()
        global_limiter['request_count'] += 1

    async def _handle_rate_limit_error(self, chain: str, retry_after: int = None) -> None:
        """Handle 429 rate limit error with exponential backoff."""
        chain_limiter = self._get_rate_limiter(chain)
        global_limiter = self._global_rate_limiter
        
        # Use server's retry-after if provided, otherwise use exponential backoff
        if retry_after:
            backoff_duration = min(retry_after, self.config['max_rate_limit_backoff'])
        else:
            backoff_duration = min(
                chain_limiter['backoff_duration'] * self.config['rate_limit_backoff_multiplier'],
                self.config['max_rate_limit_backoff']
            )
        
        chain_limiter['backoff_duration'] = backoff_duration
        chain_limiter['backoff_until'] = time.time() + backoff_duration
        global_limiter['backoff_until'] = time.time() + backoff_duration
        
        logger.warning(f"🚫 Rate limit hit for {chain}, backing off {backoff_duration:.1f}s")
        await asyncio.sleep(backoff_duration)

    def _get_current_search_token(self, chain: str) -> str:
        """Get the current search token based on rotation schedule."""
        # Define all possible search tokens for rotation
        if chain == 'ethereum':
            all_tokens = ['WETH', 'USDC', 'USDT']
        elif chain == 'bsc':
            all_tokens = ['WBNB', 'USDC', 'USDT']
        elif chain == 'polygon':
            all_tokens = ['WMATIC', 'USDC', 'USDT']
        elif chain == 'arbitrum':
            all_tokens = ['WETH', 'USDC', 'USDT']
        elif chain == 'optimism':
            all_tokens = ['WETH', 'USDC', 'USDT']
        elif chain == 'avalanche':
            all_tokens = ['WAVAX', 'USDC', 'USDT']
        elif chain == 'base':
            all_tokens = ['WETH', 'USDC', 'USDT']
        elif chain == 'fantom':
            all_tokens = ['WFTM', 'USDC', 'USDT']
        elif chain == 'cronos':
            all_tokens = ['WCRO', 'USDC', 'USDT']
        elif chain == 'gnosis':
            all_tokens = ['WETH', 'USDC', 'USDT']
        else:
            # For other chains, use native token and stable coins
            network_config = NetworkConfig()
            chain_info = network_config.NETWORKS.get(chain, {})
            native_token = chain_info.get('native_symbol', 'ETH')
            all_tokens = [native_token, 'USDC', 'USDT']
        
        # Rotate through tokens based on current index
        current_time = time.time()
        if current_time - self._rotation_state['last_rotation'] > self._rotation_state['rotation_interval']:
            self._rotation_state['current_token_index'] = (self._rotation_state['current_token_index'] + 1) % len(all_tokens)
            self._rotation_state['last_rotation'] = current_time
            logger.info(f"🔄 Rotating to token index {self._rotation_state['current_token_index']}: {all_tokens[self._rotation_state['current_token_index']]}")
        
        return all_tokens[self._rotation_state['current_token_index']]

    def _check_circuit_breaker(self, chain: str = None) -> bool:
        """Check if circuit breaker is open (should stop requests)."""
        current_time = time.time()
        
        # Check global circuit breaker first (transport failures)
        global_cb = self._global_circuit_breaker
        if current_time - global_cb['last_failure'] > global_cb['timeout']:
            if global_cb['state'] == 'open':
                global_cb['failures'] = 0
                global_cb['state'] = 'closed'
                global_cb['last_reset'] = current_time
                logger.info(f"🔄 Global circuit breaker reset after {global_cb['timeout']}s")
        
        if global_cb['state'] == 'open':
            logger.warning(f"🚫 Global circuit breaker OPEN - skipping all chains")
            return True
        
        # Check per-chain circuit breaker if chain specified
        if chain:
            chain_cb = self._chain_circuit_breakers[chain]
            if current_time - chain_cb['last_failure'] > chain_cb['timeout']:
                if chain_cb['state'] == 'open':
                    chain_cb['failures'] = 0
                    chain_cb['state'] = 'closed'
                    chain_cb['last_reset'] = current_time
                    logger.info(f"🔄 {chain} circuit breaker reset after {chain_cb['timeout']}s")
            
            if chain_cb['state'] == 'open':
                logger.warning(f"🚫 {chain} circuit breaker OPEN - skipping chain")
                return True
        
        return False
    
    def _record_success(self, response_time: float, chain: str = None):
        """Record successful request and adjust throttling."""
        self._dynamic_metrics['success_count'] += 1
        self._dynamic_metrics['response_times'].append(response_time)
        
        # Reset per-chain circuit breaker on success
        if chain and chain in self._chain_circuit_breakers:
            chain_cb = self._chain_circuit_breakers[chain]
            if chain_cb['state'] == 'open':
                chain_cb['state'] = 'closed'
                chain_cb['failures'] = 0
                logger.info(f"✅ {chain} circuit breaker closed - requests successful")
        
        # Reset global circuit breaker on success
        if self._global_circuit_breaker['state'] == 'open':
            self._global_circuit_breaker['state'] = 'closed'
            self._global_circuit_breaker['failures'] = 0
            logger.info("✅ Global circuit breaker closed - requests successful")
        
        # Adjust delay based on response time
        self._adjust_throttling()
    
    def _record_failure(self, chain: str = None, is_transport_failure: bool = True):
        """Record failed request and potentially open circuit breaker."""
        self._dynamic_metrics['error_count'] += 1
        
        if is_transport_failure:
            # Transport failures affect global circuit breaker
            self._global_circuit_breaker['failures'] += 1
            self._global_circuit_breaker['last_failure'] = time.time()
            
            # Open global circuit breaker if threshold reached
            if self._global_circuit_breaker['failures'] >= self._global_circuit_breaker['threshold']:
                self._global_circuit_breaker['state'] = 'open'
                logger.warning(f"🚫 Global circuit breaker OPEN - {self._global_circuit_breaker['failures']} transport failures")
        
        # Record per-chain failure if chain specified
        if chain:
            chain_cb = self._chain_circuit_breakers[chain]
            chain_cb['failures'] += 1
            chain_cb['last_failure'] = time.time()
            
            # Open per-chain circuit breaker if threshold reached
            if chain_cb['failures'] >= chain_cb['threshold']:
                chain_cb['state'] = 'open'
                logger.warning(f"🚫 {chain} circuit breaker OPEN - {chain_cb['failures']} failures (timeout: {chain_cb['timeout']}s)")
        
        # Increase delay on failure
        self._dynamic_metrics['current_delay'] = min(
            self._dynamic_metrics['current_delay'] * self.config['adjustment_factor'],
            self.config['max_delay']
        )
    
    def _adjust_throttling(self):
        """Dynamically adjust request delay based on performance."""
        current_time = time.time()
        
        # Only adjust at intervals
        if current_time - self._dynamic_metrics['last_adjustment'] < self._dynamic_metrics['adjustment_interval']:
            return
        
        if len(self._dynamic_metrics['response_times']) < 3:
            return  # Not enough data
        
        avg_response_time = mean(self._dynamic_metrics['response_times'])
        total_requests = self._dynamic_metrics['success_count'] + self._dynamic_metrics['error_count']
        success_rate = self._dynamic_metrics['success_count'] / total_requests if total_requests > 0 else 0
        
        # Adjust delay based on response time
        if avg_response_time > self.config['target_response_time']:
            # Response too slow - increase delay
            new_delay = min(
                self._dynamic_metrics['current_delay'] * self.config['adjustment_factor'],
                self.config['max_delay']
            )
            logger.debug(f"🐌 Slow response ({avg_response_time:.2f}s) - increasing delay to {new_delay:.2f}s")
        elif success_rate < self.config['success_rate_threshold']:
            # Low success rate - increase delay
            new_delay = min(
                self._dynamic_metrics['current_delay'] * self.config['adjustment_factor'],
                self.config['max_delay']
            )
            logger.debug(f"📉 Low success rate ({success_rate:.2f}) - increasing delay to {new_delay:.2f}s")
        else:
            # Good performance - decrease delay
            new_delay = max(
                self._dynamic_metrics['current_delay'] / self.config['adjustment_factor'],
                self.config['min_delay']
            )
            logger.debug(f"✅ Good performance - decreasing delay to {new_delay:.2f}s")
        
        self._dynamic_metrics['current_delay'] = new_delay
        self._dynamic_metrics['last_adjustment'] = current_time

    async def _fetch_tokens_from_dexscreener(self, chain: str) -> List[Dict]:
        """Fetch token data from DexScreener token profiles API instead of hardcoded tokens."""
        if not self.session:
            logger.error("No HTTP session available")
            return []

        try:
            # Check circuit breaker first
            if self._check_circuit_breaker(chain):
                logger.warning(f"🚫 Circuit breaker OPEN - skipping {chain}")
                return []
            
            # Use NetworkConfig for chain information
            network_config = NetworkConfig()
            chain_info = network_config.NETWORKS.get(chain)
            
            if not chain_info:
                logger.warning(f"Chain {chain} not found in NetworkConfig")
                return []
            
            # Get DexScreener chain name - use proper mapping to avoid conflicts
            ds_chain_mapping = {
                'ethereum': 'ethereum',
                'bsc': 'bsc',
                'polygon': 'polygon',
                'arbitrum': 'arbitrum',
                'optimism': 'optimism',
                'base': 'base',
                'avalanche': 'avalanche',
                'fantom': 'fantom',
                'cronos': 'cronos',
                'gnosis': 'gnosis',
                'moonbeam': 'moonbeam',
                'moonriver': 'moonriver',
                'celo': 'celo',
                'metis': 'metis',
                'kava': 'kava',
                'aurora': 'aurora',
                'solana': 'solana',
                'tron': 'tron',
                'sui': 'sui',
                'aptos': 'aptos',
                'cardano': 'cardano',
                'xrpl': 'xrpl',
                'thorchain': 'thorchain',
                'stacks': 'stacks',
                'algorand': 'algorand',
                'osmosis': 'osmosis',
                'acala': 'acala',
                'tezos': 'tezos',
                'stellar': 'stellar',
                'starknet': 'starknet',
                'cosmos': 'cosmos',
                'polkadot': 'polkadot',
                'near': 'near',
                'flow': 'flow',
                'elrond': 'elrond',
                'bitcoin': 'bitcoin',
                'litecoin': 'litecoin',
                'dogecoin': 'dogecoin'
            }
            
            ds_chain = ds_chain_mapping.get(chain.lower(), chain.lower())
            
            # Fetch token profiles instead of hardcoded tokens
            logger.info(f"🔍 Fetching token profiles for {chain}")
            
            all_pairs = []
            seen_addresses = set()
            
            # Make request with circuit breaker protection
            start_time = time.time()
            try:
                await self._rate_limit(chain)
                
                # Use improved discovery strategy with multiple approaches
                chain_pairs = await self._fetch_with_discovery_strategy(chain, ds_chain)
                
                if chain_pairs:
                    logger.info(f"📊 Found {len(chain_pairs)} pairs for {chain}")
                
                logger.info(f"📊 Fetched {len(chain_pairs)} unique pairs for {chain} using discovery strategy")
                
                return chain_pairs
                    
            except asyncio.CancelledError:
                # Cancellation is NOT a failure - propagate without recording
                logger.debug(f"Discovery cancelled for {chain} - propagating")
                raise
            except asyncio.TimeoutError:
                # Timeout is NOT a scanner failure - it's orchestration timeout
                logger.info(f"⏱️ Discovery timeout for {chain} (non-failure)")
                return []
            except Exception as e:
                self._record_failure(chain, is_transport_failure=True)
                logger.error(f"Unexpected error fetching token profiles: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching tokens from DexScreener: {e}")
            return []

    async def _process_single_token(self, pair: Dict, requested_chain: str) -> Optional[Dict]:
        """Process a single token pair into standardized format using NetworkConfig."""
        try:
            # CRITICAL FIX: Extract the actual chain from DexScreener data, not the requested chain
            dex_chain_id = pair.get('chainId')
            if not dex_chain_id:
                logger.debug(f"Pair missing chainId: {pair.get('pairAddress', 'unknown')}")
                return None

            # Normalize the DexScreener chain ID to our internal chain name
            from networks.chain_normalizer import chain_normalizer
            actual_chain = chain_normalizer.normalize_chain_identifier(dex_chain_id)

            # If the actual chain doesn't match the requested chain, skip this pair
            # This prevents cross-chain fan-out where one BSC pair gets replicated to multiple chains
            if actual_chain != requested_chain:
                logger.debug(f"Skipping cross-chain token: requested={requested_chain}, actual={actual_chain}, pair={pair.get('pairAddress', 'unknown')}")
                return None

            base_token = pair.get('baseToken', {})

            # Validate required fields
            if not base_token.get('address') or not base_token.get('symbol'):
                return None

            # Calculate metrics
            liquidity = pair.get('liquidity', {}).get('usd', 0.0)
            volume_24h = pair.get('volume', {}).get('h24', 0.0)

            # Early filter
            if liquidity < self.config['min_liquidity'] or volume_24h < self.config['min_volume']:
                return None

            # Get price changes
            price_changes = pair.get('priceChange', {})
            price_change_5m = price_changes.get('m5', 0.0)
            price_change_1h = price_changes.get('h1', 0.0)
            price_change_24h = price_changes.get('h24', 0.0)
            price_change_7d = price_changes.get('d7', 0.0)

            # Calculate technical indicators
            volatility = self._calculate_volatility(price_change_5m, price_change_1h, price_change_24h)
            momentum = self._calculate_momentum(price_change_5m, price_change_1h)
            strength = self._calculate_strength(volume_24h, liquidity)

            # Calculate zscore if we have price history
            zscore = self._calculate_zscore([price_change_5m, price_change_1h, price_change_24h])

            # Smart decimals detection
            decimals = base_token.get('decimals')
            if decimals is None or decimals == 0:
                decimals = self.CHAIN_DEFAULT_DECIMALS.get(actual_chain, 18)

            # Consistent timestamp handling (ISO format)
            current_time = datetime.now(timezone.utc)
            pair_created = pair.get('pairCreatedAt')

            # Convert millisecond timestamp to ISO if available
            if pair_created:
                try:
                    first_seen = datetime.fromtimestamp(pair_created / 1000, tz=timezone.utc).isoformat()
                except:
                    first_seen = current_time.isoformat()
            else:
                first_seen = current_time.isoformat()

            token_data = {
                'address': base_token['address'].lower(),
                'symbol': base_token.get('symbol', ''),
                'name': base_token.get('name', ''),
                'chain': actual_chain,  # Use the actual chain from DexScreener data
                'chain_id': chain_info.get('chain_id') if chain_info else get_chain_id(actual_chain),
                'chain_name': actual_chain,
                'decimals': decimals,
                'price': pair.get('priceUsd', None),
                'volume_24h': volume_24h,
                'liquidity_usd': liquidity,
                'price_change_5m': price_change_5m,
                'price_change_1h': price_change_1h,
                'price_change_24h': price_change_24h,
                'price_change_7d': price_change_7d,
                'market_cap': pair.get('marketCap', 0.0),
                'pair_address': pair.get('pairAddress', ''),
                'exchange': pair.get('dexId', ''),
                'dex_id': pair.get('dexId', ''),
                'source': 'dexscreener',

                # Technical indicators
                'zscore': zscore,
                'strength': strength,
                'momentum': momentum,
                'volatility': volatility,

                # AI scores (populated later)
                'ai_score': 0.0,
                'confidence': 0.0,
                'risk_score': 0.0,

                # Metadata
                'holders': pair.get('holders', None),
                'has_traded': volume_24h > 0,
                'is_blacklisted': False,
                'metadata': {
                    'dexscreener_pair': pair.get('pairAddress', ''),
                    'dex_id': pair.get('dexId', ''),
                    'source': 'dexscreener',
                    'quote_token': pair.get('quoteToken', {}).get('symbol', ''),
                    'fdv': pair.get('fdv', 0.0),
                    'price_native': pair.get('priceNative', None)
                },

                # Consistent ISO timestamps
                'first_seen': first_seen,
                'created_at': current_time.isoformat(),
                'updated_at': current_time.isoformat()
            }

            return token_data

        except Exception as e:
            if self.config['verbose_logging']:
                logger.debug(f"Error processing pair: {e}")
            return None

    def _calculate_volatility(self, price_5m: float, price_1h: float, price_24h: float) -> float:
        """Calculate volatility score with outlier handling."""
        try:
            changes = [abs(x) for x in [price_5m, price_1h, price_24h] if x is not None]
            if len(changes) < 2:
                return 0.0
            return stdev(changes) if len(changes) > 1 else abs(changes[0])
        except:
            return 0.0

    def _calculate_momentum(self, price_5m: float, price_1h: float) -> float:
        """Calculate momentum with acceleration component."""
        try:
            if price_5m is None or price_1h is None:
                return 0.0
            # Weighted momentum with acceleration (5m trend vs 1h trend)
            acceleration = (price_5m - (price_1h / 12)) if price_1h != 0 else price_5m
            momentum = (price_5m * 0.7) + (acceleration * 0.3)
            return max(-100.0, min(100.0, momentum))
        except:
            return 0.0

    def _calculate_strength(self, volume: float, liquidity: float) -> float:
        """Calculate strength with volume/liquidity ratio."""
        try:
            if liquidity <= 0:
                return 0.0
            ratio = volume / liquidity
            # Logarithmic scaling for better distribution
            return min(100.0, (ratio ** 0.5) * 50.0)
        except:
            return 0.0

    def _calculate_zscore(self, price_changes: List[float]) -> float:
        """Calculate z-score from price changes."""
        try:
            valid_changes = [x for x in price_changes if x is not None]
            if len(valid_changes) < 2:
                return 0.0
            avg = mean(valid_changes)
            std = stdev(valid_changes)
            if std == 0:
                return 0.0
            # Z-score of most recent change
            return (valid_changes[-1] - avg) / std
        except:
            return 0.0

    async def _process_tokens(self, raw_pairs: List[Dict], chain: str) -> List[Dict]:
        """Process tokens with true concurrent batch processing."""
        pairs_to_process = raw_pairs[:self.config['max_tokens_per_scan']]
        
        if not self.config['parallel_processing']:
            # Sequential fallback
            processed = []
            for pair in pairs_to_process:
                result = await self._process_single_token(pair, chain)
                if result:
                    processed.append(result)
            return processed
        
        # Concurrent batch processing
        processed = []
        batch_size = self.config['batch_size']
        max_concurrent = self.config['max_concurrent_batches']
        
        # Create all batches
        batches = [
            pairs_to_process[i:i + batch_size]
            for i in range(0, len(pairs_to_process), batch_size)
        ]
        
        # Process batches with controlled concurrency
        for i in range(0, len(batches), max_concurrent):
            concurrent_batches = batches[i:i + max_concurrent]
            
            batch_tasks = []
            for batch in concurrent_batches:
                tasks = [self._process_single_token(pair, chain) for pair in batch]
                batch_tasks.append(asyncio.gather(*tasks, return_exceptions=True))
            
            # Wait for concurrent batches
            batch_results = await asyncio.gather(*batch_tasks)
            
            # Flatten and filter results
            for batch_result in batch_results:
                for result in batch_result:
                    if isinstance(result, Exception):
                        if self.config['verbose_logging']:
                            logger.debug(f"Processing error: {result}")
                    elif result is not None:
                        processed.append(result)

        logger.info(f"📊 Processed {len(processed)}/{len(pairs_to_process)} tokens")
        return processed

    async def _score_single_token(self, token: Dict) -> float:
        """Score a single token with timeout protection."""
        try:
            score_task = self._ai_controller.score_token(token)
            return await asyncio.wait_for(score_task, timeout=self.config['ai_timeout_seconds'])
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ AI scoring timeout for {token.get('symbol', 'unknown')}")
            return 0.0
        except Exception as e:
            if self.config['verbose_logging']:
                logger.debug(f"AI scoring failed for {token.get('symbol')}: {e}")
            return 0.0

    async def _apply_ai_scoring(self, tokens: List[Dict]) -> List[Dict]:
        """Apply AI scoring with concurrent batches and timeout protection."""
        if not self._ai_controller:
            return tokens
        
        if not hasattr(self._ai_controller, 'score_token'):
            logger.warning(f"AI controller missing score_token method")
            return tokens

        try:
            scored_tokens = []
            batch_size = self.config['batch_size']
            
            # Process in batches
            for i in range(0, len(tokens), batch_size):
                batch = tokens[i:i + batch_size]
                tasks = [self._score_single_token(token) for token in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for token, result in zip(batch, results):
                    if isinstance(result, Exception):
                        token['ai_score'] = 0.0
                    else:
                        token['ai_score'] = result if result is not None else 0.0
                    scored_tokens.append(token)
                
                # Delay between batches to avoid overwhelming AI
                if i + batch_size < len(tokens):
                    await asyncio.sleep(self.config['ai_batch_delay'])

            scored_count = sum(1 for t in scored_tokens if t.get('ai_score', 0) > 0)
            logger.info(f"✅ AI scored {scored_count}/{len(scored_tokens)} tokens")
            return scored_tokens

        except Exception as e:
            logger.error(f"⚠️ AI scoring failed: {e}", exc_info=True)
            return tokens

    def _update_chain_metrics(self, chain: str, tokens: List[Dict]) -> None:
        """Update running averages for dynamic thresholds."""
        if not tokens:
            return
        
        metrics = self._chain_metrics[chain]
        new_sample_count = len(tokens)
        old_weight = metrics['sample_count'] / (metrics['sample_count'] + new_sample_count)
        new_weight = new_sample_count / (metrics['sample_count'] + new_sample_count)
        
        # Update running averages
        metrics['avg_liquidity'] = (
            metrics['avg_liquidity'] * old_weight +
            mean([t.get('liquidity_usd', 0) for t in tokens]) * new_weight
        )
        metrics['avg_volume'] = (
            metrics['avg_volume'] * old_weight +
            mean([t.get('volume_24h', 0) for t in tokens]) * new_weight
        )
        metrics['avg_volatility'] = (
            metrics['avg_volatility'] * old_weight +
            mean([t.get('volatility', 0) for t in tokens]) * new_weight
        )
        metrics['sample_count'] += new_sample_count

    def _get_dynamic_thresholds(self, chain: str) -> Dict[str, float]:
        """Get dynamic thresholds based on chain metrics."""
        if not self.config['dynamic_thresholds'] or chain not in self._chain_metrics:
            return {
                'min_liquidity': self.config['min_liquidity'],
                'min_volume': self.config['min_volume'],
                'max_volatility': self.config['max_volatility_1h']
            }
        
        metrics = self._chain_metrics[chain]
        
        # Adaptive thresholds (50% of average)
        return {
            'min_liquidity': max(self.config['min_liquidity'], metrics['avg_liquidity'] * 0.5),
            'min_volume': max(self.config['min_volume'], metrics['avg_volume'] * 0.5),
            'max_volatility': max(self.config['max_volatility_1h'], metrics['avg_volatility'] * 2.0)
        }

    def _filter_elite_tokens(self, tokens: List[Dict], chain: str = None) -> List[Dict]:
        """Filter tokens with dynamic thresholds and comprehensive stats."""
        elite_tokens = []
        filter_stats = defaultdict(int)
        
        # Get thresholds (dynamic or static)
        thresholds = self._get_dynamic_thresholds(chain) if chain else {
            'min_liquidity': self.config['min_liquidity'],
            'min_volume': self.config['min_volume'],
            'max_volatility': self.config['max_volatility_1h']
        }

        for token in tokens:
            try:
                # Liquidity check
                if token.get('liquidity_usd', 0) < thresholds['min_liquidity']:
                    filter_stats['low_liquidity'] += 1
                    continue
                
                # Volume check
                if token.get('volume_24h', 0) < thresholds['min_volume']:
                    filter_stats['low_volume'] += 1
                    continue
                
                # AI score check
                ai_score = token.get('ai_score', 0)
                if self.config['require_ai_score'] and ai_score == 0:
                    filter_stats['missing_ai_score'] += 1
                    continue
                
                if ai_score > 0 and ai_score < self.config['ai_score_threshold']:
                    filter_stats['low_ai_score'] += 1
                    continue

                # Volatility check
                price_change_1h = abs(token.get('price_change_1h', 0))
                if price_change_1h > thresholds['max_volatility']:
                    filter_stats['extreme_volatility'] += 1
                    continue
                
                # Minimum movement check
                if self.config['min_price_change_1h'] > 0:
                    if price_change_1h < self.config['min_price_change_1h']:
                        filter_stats['insufficient_movement'] += 1
                        continue

                elite_tokens.append(token)

            except Exception as e:
                filter_stats['errors'] += 1
                if self.config['verbose_logging']:
                    logger.debug(f"Error filtering {token.get('address', 'unknown')}: {e}")
                continue

        # Efficient logging
        logger.info(f"⭐ {len(elite_tokens)} elite from {len(tokens)} candidates")
        if self.config['verbose_logging'] and filter_stats:
            for reason, count in sorted(filter_stats.items(), key=lambda x: -x[1])[:5]:
                logger.info(f"   {count} filtered: {reason.replace('_', ' ')}")
            
        return elite_tokens

    async def _persist_single_token(self, token_dict: Dict) -> bool:
        """Persist a single token with retry logic."""
        for attempt in range(self.config['memory_retry_attempts']):
            try:
                if self._memory_is_async:
                    success = await self.memory.add_token(token_dict)
                else:
                    success = self.memory.add_token(token_dict)
                
                if success:
                    return True
                    
            except Exception as e:
                if attempt < self.config['memory_retry_attempts'] - 1:
                    await asyncio.sleep(self.config['memory_retry_delay'])
                else:
                    if self.config['verbose_logging']:
                        logger.debug(f"Persist failed for {token_dict.get('symbol')}: {e}")
        
        return False

    async def _persist_tokens(self, elite_tokens: List[Dict]) -> List[Dict]:
        """Persist tokens with batch optimization."""
        scanned_tokens = []
        failed_tokens = []

        # Convert all tokens first
        for token_data in elite_tokens:
            try:
                scanned_token = ScannedToken.from_dict(token_data)
                scanned_tokens.append(scanned_token.to_dict())
            except Exception as e:
                logger.warning(f"Conversion failed for {token_data.get('address', 'unknown')}: {e}")
                continue

        # Persist to memory if available
        if not self.memory or not hasattr(self.memory, 'add_token'):
            return scanned_tokens
        
        persisted_count = 0
        
        if self.config['parallel_processing']:
            # Batch persistence
            batch_size = self.config['persist_batch_size']
            
            for i in range(0, len(scanned_tokens), batch_size):
                batch = scanned_tokens[i:i + batch_size]
                tasks = [self._persist_single_token(token) for token in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for token, success in zip(batch, results):
                    if success is True:
                        persisted_count += 1
                    else:
                        failed_tokens.append(token.get('symbol', 'unknown'))
        else:
            # Sequential persistence
            for token in scanned_tokens:
                if await self._persist_single_token(token):
                    persisted_count += 1
                else:
                    failed_tokens.append(token.get('symbol', 'unknown'))

        logger.info(f"💾 Persisted {persisted_count}/{len(scanned_tokens)} tokens")
        
        if failed_tokens:
            shown = failed_tokens[:10]
            remaining = len(failed_tokens) - len(shown)
            failed_str = ', '.join(shown)
            if remaining > 0:
                failed_str += f" (+{remaining} more)"
            logger.warning(f"Failed to persist: {failed_str}")
        
        return scanned_tokens

    def get_scan_summary(self) -> Dict[str, Any]:
        """Get comprehensive scanner summary."""
        summary = super().get_scan_summary()
        
        # Calculate total requests across all chains
        total_requests = sum(
            limiter['request_count']
            for limiter in self._rate_limiters.values()
        ) + self._global_rate_limiter['request_count']
        
        summary.update({
            'api_endpoint': self.api_base_url,
            'scan_mode': self.config.get('scan_mode', 'ultra'),
            'thresholds': {
                'min_liquidity': self.config.get('min_liquidity'),
                'min_volume': self.config.get('min_volume'),
                'max_volatility_1h': self.config.get('max_volatility_1h'),
                'ai_threshold': self.config.get('ai_score_threshold'),
                'dynamic': self.config.get('dynamic_thresholds', False)
            },
            'performance': {
                'parallel_processing': self.config.get('parallel_processing'),
                'batch_size': self.config.get('batch_size'),
                'max_concurrent_batches': self.config.get('max_concurrent_batches')
            },
            'stats': {
                'total_scans': self.scan_count,
                'total_requests': total_requests,
                'chains_scanned': len(self._rate_limiters),
                'avg_chain_metrics': {
                    chain: {
                        'samples': metrics['sample_count'],
                        'avg_liquidity': round(metrics['avg_liquidity'], 2),
                        'avg_volume': round(metrics['avg_volume'], 2)
                    }
                    for chain, metrics in self._chain_metrics.items()
                    if metrics['sample_count'] > 0
                }
            }
        })
        return summary

    async def _fetch_with_discovery_strategy(self, chain: str, ds_chain: str) -> List[Dict]:
        """
        Improved discovery strategy using multiple DexScreener approaches.
        Tries different methods to find tokens on the specified chain.
        """
        start_time = time.time()
        all_pairs = []
        seen_addresses = set()
        
        # Strategy 1: Token Profiles API (trending tokens)
        try:
            await self._rate_limit(chain)
            url = f"{self.api_base_url}/token-profiles/latest/v1"
            
            async with self.session.get(url, timeout=10.0) as response:
                if response.status == 200:
                    data = await response.json()
                    profiles = data.get('profiles', [])
                    
                    for profile in profiles[:20]:  # Limit to first 20 profiles
                        if profile.get('chainId') == ds_chain:
                            token_address = profile.get('tokenAddress')
                            if token_address:
                                pairs = await self._get_token_pairs(token_address, ds_chain, seen_addresses)
                                all_pairs.extend(pairs)
                                
                else:
                    logger.debug(f"Token profiles API status {response.status}")
                    
        except Exception as e:
            logger.debug(f"Token profiles strategy failed: {e}")
        
        # Strategy 2: Direct chain search using popular tokens (fallback)
        if len(all_pairs) < 5:  # Only try if we didn't find enough tokens
            try:
                search_tokens = self._get_popular_search_tokens(chain)
                for token_symbol in search_tokens[:3]:  # Try up to 3 tokens
                    await self._rate_limit(chain)
                    
                    search_url = f"{self.api_base_url}/dex/search"
                    params = {'q': token_symbol}
                    
                    async with self.session.get(search_url, params=params, timeout=5.0) as response:
                        if response.status == 200:
                            data = await response.json()
                            pairs = data.get('pairs', [])
                            
                            for pair in pairs:
                                if pair.get('chainId') == ds_chain:
                                    pair_addr = pair.get('pairAddress')
                                    if pair_addr and pair_addr not in seen_addresses:
                                        seen_addresses.add(pair_addr)
                                        all_pairs.append(pair)
                                        if len(all_pairs) >= 10:  # Limit total results
                                            break
                        if len(all_pairs) >= 10:
                            break
                            
            except Exception as e:
                logger.debug(f"Direct search strategy failed: {e}")
        
        # Strategy 3: Trending pairs (last resort for major chains)
        if len(all_pairs) < 3 and chain in ['ethereum', 'bsc', 'base', 'polygon']:
            try:
                await self._rate_limit(chain)
                trending_url = f"{self.api_base_url}/dex/trending/{ds_chain}"
                
                async with self.session.get(trending_url, timeout=5.0) as response:
                    if response.status == 200:
                        data = await response.json()
                        pairs = data.get('pairs', [])
                        
                        for pair in pairs[:5]:  # Take first 5 trending pairs
                            pair_addr = pair.get('pairAddress')
                            if pair_addr and pair_addr not in seen_addresses:
                                seen_addresses.add(pair_addr)
                                all_pairs.append(pair)
                                
            except Exception as e:
                logger.debug(f"Trending strategy failed: {e}")
        
        # Record success if we found any pairs
        response_time = time.time() - start_time
        if all_pairs:
            self._record_success(response_time, chain)
        else:
            # Empty result is not a failure for discovery
            self._record_success(response_time, chain)
            
        return all_pairs
    
    def _get_popular_search_tokens(self, chain: str) -> List[str]:
        """Get popular tokens to search for on specific chains."""
        chain_tokens = {
            'ethereum': ['WETH', 'USDC', 'USDT', 'SHIB', 'PEPE'],
            'bsc': ['WBNB', 'USDC', 'USDT', 'CAKE', 'BABYDOGE'],
            'polygon': ['WMATIC', 'USDC', 'USDT', 'POLY', 'QI'],
            'arbitrum': ['WETH', 'USDC', 'USDT', 'ARB', 'GMX'],
            'optimism': ['WETH', 'USDC', 'USDT', 'OP', 'VEL'],
            'base': ['WETH', 'USDC', 'USDT', 'BASE', 'DEGEN'],
            'avalanche': ['WAVAX', 'USDC', 'USDT', 'JOE', 'PNG'],
            'fantom': ['WFTM', 'USDC', 'USDT', 'BOO', 'SPOOKY'],
            'blast': ['WETH', 'USDC', 'USDT', 'BLAST', 'PYRO'],
            'cronos': ['WCRO', 'USDC', 'USDT', 'CRO', 'VVS']
        }
        return chain_tokens.get(chain, ['ETH', 'USDC', 'USDT'])
    
    async def _get_token_pairs(self, token_address: str, ds_chain: str, seen_addresses: set) -> List[Dict]:
        """Get pairs for a specific token address."""
        try:
            await self._rate_limit("global")  # Use global rate limiting
            
            pairs_url = f"{self.api_base_url}/dex/search"
            params = {'q': token_address}
            
            async with self.session.get(pairs_url, params=params, timeout=5.0) as response:
                if response.status == 200:
                    pairs_data = await response.json()
                    pairs = pairs_data.get('pairs', [])
                    
                    token_pairs = []
                    for pair in pairs:
                        if pair.get('chainId') == ds_chain:
                            pair_addr = pair.get('pairAddress')
                            if pair_addr and pair_addr not in seen_addresses:
                                seen_addresses.add(pair_addr)
                                token_pairs.append(pair)
                                break  # Only need one pair per token
                    
                    return token_pairs
                else:
                    return []
                    
        except Exception as e:
            logger.debug(f"Failed to get pairs for {token_address}: {e}")
            return []
