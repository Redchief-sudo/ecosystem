"""
CoinMarketLive Scanner
---------------------
Production-grade CoinMarketCap data source providing market data and trading signals.
Live data feed for trading decisions rather than scanning for tokens.
"""
import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import numpy as np
import redis.asyncio as redis
from scipy import stats
from tenacity import (before_sleep_log, retry, retry_if_exception_type,
                      stop_after_attempt, wait_exponential)

from ..data_source import (DataSourceBase, DataSourceStatus,
                           DataSourceType, MarketData, TradingSignal)
from utils.http_session_manager import get_http_session

logger = logging.getLogger(__name__)

class ScannerStatus(Enum):
    """Scanner operational status."""
    IDLE = "idle"
    SCANNING = "scanning"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    HEALTHY = "healthy"

class CacheStrategy(Enum):
    """Cache invalidation strategies."""
    TTL = "ttl"  # Time to live
    LRU = "lru"  # Least recently used
    ADAPTIVE = "adaptive"  # Dynamic based on data volatility

@dataclass
class TokenMetrics:
    """Comprehensive token metrics."""
    symbol: str
    address: str
    price: float
    market_cap: float
    volume_24h: float
    liquidity_usd: float
    
    # Price changes
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    
    # Technical indicators
    rsi: float = 50.0
    macd: float = 0.0
    bollinger_position: float = 0.5  # 0-1, position within bands
    volume_profile: float = 1.0  # Current volume vs average
    
    # Advanced metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    beta: float = 1.0
    alpha: float = 0.0
    
    # Risk scores
    liquidity_score: float = 0.0
    volatility_score: float = 0.0
    momentum_score: float = 0.0
    quality_score: float = 0.0
    composite_score: float = 0.0
    
    # Metadata
    rank: int = 0
    age_days: int = 0
    holders: int = 0
    social_score: float = 0.0
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'address': self.address,
            'price': self.price,
            'market_cap': self.market_cap,
            'volume_24h': self.volume_24h,
            'liquidity_usd': self.liquidity_usd,
            'price_change_5m': self.price_change_5m,
            'price_change_1h': self.price_change_1h,
            'price_change_24h': self.price_change_24h,
            'price_change_7d': self.price_change_7d,
            'rsi': self.rsi,
            'macd': self.macd,
            'bollinger_position': self.bollinger_position,
            'sharpe_ratio': self.sharpe_ratio,
            'liquidity_score': self.liquidity_score,
            'momentum_score': self.momentum_score,
            'composite_score': self.composite_score,
            'rank': self.rank,
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class ScanResult:
    """Results from a scan operation."""
    tokens: List[TokenMetrics]
    scan_duration: float
    tokens_analyzed: int
    errors: List[str]
    cache_hits: int
    api_calls: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class AdaptiveRateLimiter:
    """Intelligent rate limiter that adapts to API responses."""
    
    def __init__(self, initial_delay: float = 0.5, max_delay: float = 10.0):
        self.delay = initial_delay
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.last_request = 0
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        """Wait before making next request."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            
            if elapsed < self.delay:
                await asyncio.sleep(self.delay - elapsed)
            
            self.last_request = time.time()
            self.request_count += 1
    
    def report_success(self):
        """Report successful request."""
        self.success_count += 1
        # Gradually decrease delay on success
        self.delay = max(self.initial_delay, self.delay * 0.9)
    
    def report_error(self, is_rate_limit: bool = False):
        """Report failed request."""
        self.error_count += 1
        if is_rate_limit:
            # Exponentially increase delay on rate limits
            self.delay = min(self.max_delay, self.delay * 2)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            'current_delay': self.delay,
            'total_requests': self.request_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': self.success_count / max(1, self.request_count)
        }

class IntelligentCache:
    """Advanced caching system with multiple strategies."""
    
    def __init__(self, 
                 strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
                 default_ttl: int = 300,
                 max_size: int = 10000,
                 redis_client: Optional[redis.Redis] = None):
        self.strategy = strategy
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.redis = redis_client
        
        # In-memory cache
        self._cache: Dict[str, Tuple[Any, float, int]] = {}  # key -> (data, timestamp, access_count)
        self._access_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._volatility_scores: Dict[str, float] = {}
        
    def _calculate_adaptive_ttl(self, key: str, data: Any) -> int:
        """Calculate TTL based on data volatility."""
        volatility = self._volatility_scores.get(key, 0.5)
        
        # High volatility = shorter TTL
        if volatility > 0.7:
            return int(self.default_ttl * 0.3)
        elif volatility > 0.4:
            return int(self.default_ttl * 0.6)
        else:
            return self.default_ttl
    
    def _update_volatility(self, key: str, new_data: Any):
        """Update volatility score based on data changes."""
        if key not in self._cache:
            self._volatility_scores[key] = 0.5
            return
        
        old_data, _, _ = self._cache[key]
        
        # Calculate change magnitude (simplified for dict data)
        if isinstance(new_data, dict) and isinstance(old_data, dict):
            price_change = abs(new_data.get('price', 0) - old_data.get('price', 0))
            if old_data.get('price', 0) > 0:
                change_pct = price_change / old_data['price']
                # Update volatility with exponential smoothing
                old_vol = self._volatility_scores.get(key, 0.5)
                self._volatility_scores[key] = 0.7 * old_vol + 0.3 * change_pct
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        # Try in-memory first
        if key in self._cache:
            data, timestamp, access_count = self._cache[key]
            
            # Check if expired
            ttl = self._calculate_adaptive_ttl(key, data) if self.strategy == CacheStrategy.ADAPTIVE else self.default_ttl
            if time.time() - timestamp < ttl:
                self._cache[key] = (data, timestamp, access_count + 1)
                self._access_times[key].append(time.time())
                return data
            else:
                del self._cache[key]
        
        # Try Redis if available
        if self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.debug(f"Redis get error: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache."""
        # Update volatility
        if self.strategy == CacheStrategy.ADAPTIVE:
            self._update_volatility(key, value)
        
        # Store in memory
        if len(self._cache) >= self.max_size and self.strategy == CacheStrategy.LRU:
            # Evict least recently used
            lru_key = min(self._access_times.items(), key=lambda x: x[1][-1] if x[1] else 0)[0]
            del self._cache[lru_key]
            del self._access_times[lru_key]
        
        self._cache[key] = (value, time.time(), 0)
        
        # Store in Redis if available
        if self.redis:
            try:
                actual_ttl = ttl or (self._calculate_adaptive_ttl(key, value) if self.strategy == CacheStrategy.ADAPTIVE else self.default_ttl)
                await self.redis.setex(key, actual_ttl, json.dumps(value))
            except Exception as e:
                logger.debug(f"Redis set error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'strategy': self.strategy.value,
            'avg_volatility': np.mean(list(self._volatility_scores.values())) if self._volatility_scores else 0
        }

class TechnicalAnalyzer:
    """Advanced technical analysis engine."""
    
    @staticmethod
    def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)
    
    @staticmethod
    def calculate_macd(prices: np.ndarray,
                       fast: int = 12,
                       slow: int = 26,
                       signal: int = 9) -> Tuple[float, float, float]:
        """Calculate MACD indicator."""
        if len(prices) < slow:
            return 0.0, 0.0, 0.0

        # Calculate MACD line series for signal line
        macd_series = []
        for i in range(len(prices)):
            if i >= slow - 1:  # Start when we have enough data for slow EMA
                fast_ema = TechnicalAnalyzer._ema(prices[:i+1], fast)
                slow_ema = TechnicalAnalyzer._ema(prices[:i+1], slow)
                macd_series.append(fast_ema - slow_ema)

        if not macd_series:
            return 0.0, 0.0, 0.0

        macd_line = macd_series[-1]  # Current MACD value

        if len(macd_series) >= signal:
            signal_line = TechnicalAnalyzer._ema(np.array(macd_series), signal)
        else:
            signal_line = macd_line

        histogram = macd_line - signal_line

        return float(macd_line), float(signal_line), float(histogram)
    
    @staticmethod
    def _ema(prices: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return float(np.mean(prices))
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        
        return float(ema)
    
    @staticmethod
    def calculate_bollinger_bands(prices: np.ndarray, 
                                  period: int = 20, 
                                  std_dev: float = 2.0) -> Tuple[float, float, float, float]:
        """Calculate Bollinger Bands and position."""
        if len(prices) < period:
            current_price = prices[-1]
            return current_price, current_price, current_price, 0.5
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        
        # Calculate position within bands (0 = lower, 1 = upper)
        current_price = prices[-1]
        if upper != lower:
            position = (current_price - lower) / (upper - lower)
            position = max(0, min(1, position))
        else:
            position = 0.5
        
        return float(upper), float(sma), float(lower), float(position)
    
    @staticmethod
    def calculate_sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 365)
        if np.std(returns) == 0:
            return 0.0
        
        return float(np.mean(excess_returns) / np.std(returns) * np.sqrt(365))
    
    @staticmethod
    def calculate_sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / 365)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0.0
        
        return float(np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(365))
    
    @staticmethod
    def calculate_max_drawdown(prices: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        if len(prices) < 2:
            return 0.0
        
        peak = prices[0]
        max_dd = 0.0
        
        for price in prices:
            if price > peak:
                peak = price
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd
        
        return float(max_dd)
    
    @staticmethod
    def calculate_beta(asset_returns: np.ndarray, market_returns: np.ndarray) -> float:
        """Calculate beta relative to market."""
        if len(asset_returns) < 2 or len(market_returns) < 2:
            return 1.0
        
        covariance = np.cov(asset_returns, market_returns)[0][1]
        market_variance = np.var(market_returns)
        
        if market_variance == 0:
            return 1.0
        
        return float(covariance / market_variance)

class CoinMarketLiveScanner(DataSourceBase):
    """
    Production-grade CoinMarketCap data source providing market data and trading signals.

    Features:
    - Adaptive rate limiting
    - Multi-level caching (memory + Redis)
    - Advanced technical analysis
    - Real-time market data
    - Trading signal generation
    - Comprehensive error handling
    - Performance monitoring
    - WebSocket support (optional)
    """

    BASE_URL = "https://pro-api.coinmarketcap.com/v1"

    def __init__(self, config: Dict[str, Any], **kwargs):
        # Initialize DataSourceBase first
        super().__init__(config)

        self.data_source_type = DataSourceType.MARKET_DATA
        self.api_key = config.get('api_key')

        if not self.api_key:
            raise ValueError("CoinMarketCap API key required")

        # Initialize components
        self.rate_limiter = AdaptiveRateLimiter(
            initial_delay=config.get('rate_limit_delay', 0.5),
            max_delay=config.get('max_rate_delay', 10.0)
        )

        self.cache = IntelligentCache(
            strategy=CacheStrategy[config.get('cache_strategy', 'ADAPTIVE')],
            default_ttl=config.get('cache_ttl', 300),
            max_size=config.get('cache_size', 10000)
        )

        # Market data tracking
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.signal_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.tracked_tokens: Set[str] = set()

        # Performance tracking
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_api_calls': 0,
            'cache_hits': 0,
            'avg_response_time': 0.0,
            'errors': deque(maxlen=100)
        }

        logger.info("✅ CoinMarketLive Scanner initialized")
        logger.info(f"   Cache: {self.cache.strategy.value}, TTL: {self.cache.default_ttl}s")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def initialize(self):
        """Initialize data source resources."""
        self._status = DataSourceStatus.HEALTHY
        logger.info("CoinMarketLive Scanner initialized")

    async def cleanup(self):
        """Cleanup data source resources."""
        self._status = DataSourceStatus.IDLE
        logger.info("CoinMarketLive Scanner stopped")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def _make_request(self, 
                           url: str, 
                           params: Optional[Dict] = None,
                           bypass_cache: bool = False) -> Dict:
        """Make API request with retry logic and caching."""
        # Get shared session from centralized manager
        session = await get_http_session()
        
        # Generate cache key
        cache_key = hashlib.md5(f"{url}{json.dumps(params, sort_keys=True)}".encode()).hexdigest()
        
        # Check cache
        if not bypass_cache:
            cached = await self.cache.get(cache_key)
            if cached:
                self.metrics['cache_hits'] += 1
                return cached
        
        # Rate limiting
        await self.rate_limiter.acquire()
        
        headers = {
            "X-CMC_PRO_API_KEY": self.api_key,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate"
        }
        
        try:
            async with session.get(url, headers=headers, params=params) as response:
                self.metrics['total_api_calls'] += 1
                
                if response.status == 429:
                    self._status = ScannerStatus.RATE_LIMITED
                    self.rate_limiter.report_error(is_rate_limit=True)
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=429,
                        message="Rate limited"
                    )
                
                response.raise_for_status()
                data = await response.json()
                
                # Cache successful response
                await self.cache.set(cache_key, data)
                self.rate_limiter.report_success()
                self._status = ScannerStatus.HEALTHY
                
                return data
                
        except aiohttp.ClientError as e:
            self._status = ScannerStatus.ERROR
            self.rate_limiter.report_error()
            self.metrics['errors'].append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e),
                'url': url
            })
            logger.error(f"API request failed: {e}")
            raise
    
    async def fetch_market_data(self, symbols: List[str]) -> Dict[str, MarketData]:
        """
        Fetch current market data for given symbols.

        Args:
            symbols: List of trading symbols (e.g., ['BTC', 'ETH'])

        Returns:
            Dict mapping symbols to MarketData objects
        """
        try:
            self.metrics['total_requests'] += 1
            start_time = time.time()

            # Convert symbols to uppercase for API
            api_symbols = [s.upper() for s in symbols]

            # Fetch quotes from CoinMarketCap
            url = f"{self.BASE_URL}/cryptocurrency/quotes/latest"
            params = {
                'symbol': ','.join(api_symbols),
                'convert': 'USD'
            }

            response = await self._make_request(url, params)

            if not response or 'data' not in response:
                self.metrics['failed_requests'] += 1
                return {}

            market_data = {}
            for symbol in symbols:
                symbol_upper = symbol.upper()
                if symbol_upper in response['data']:
                    item = response['data'][symbol_upper]
                    quote = item.get('quote', {}).get('USD', {})

                    # Update price history
                    price = float(quote.get('price', 0))
                    if symbol_upper not in self.price_history:
                        self.price_history[symbol_upper] = deque(maxlen=100)
                    self.price_history[symbol_upper].append(price)

                    market_data[symbol] = MarketData(
                        symbol=symbol,
                        price=price,
                        volume_24h=float(quote.get('volume_24h', 0)),
                        market_cap=float(quote.get('market_cap', 0)),
                        price_change_24h=float(quote.get('percent_change_24h', 0))
                    )

            self.metrics['successful_requests'] += 1
            self.metrics['avg_response_time'] = (
                self.metrics['avg_response_time'] * (self.metrics['successful_requests'] - 1) +
                (time.time() - start_time)
            ) / self.metrics['successful_requests']

            self.last_update_time = datetime.now(timezone.utc)
            self.update_count += 1

            return market_data

        except Exception as e:
            self.metrics['failed_requests'] += 1
            self.metrics['errors'].append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e),
                'symbols': symbols
            })
            logger.error(f"Error fetching market data for {symbols}: {e}")
            return {}

    async def fetch_trading_signals(self, symbols: List[str]) -> Dict[str, TradingSignal]:
        """
        Generate trading signals based on market data analysis.

        Args:
            symbols: List of trading symbols to analyze

        Returns:
            Dict mapping symbols to TradingSignal objects
        """
        try:
            # Fetch current market data
            market_data = await self.fetch_market_data(symbols)

            signals = {}
            for symbol in symbols:
                if symbol not in market_data:
                    continue

                data = market_data[symbol]

                # Simple signal generation based on price change
                # In production, this would use more sophisticated analysis
                if data.price_change_24h > 5.0:
                    signal_type = "BUY"
                    confidence = min(data.price_change_24h / 10.0, 1.0)  # Scale confidence
                elif data.price_change_24h < -5.0:
                    signal_type = "SELL"
                    confidence = min(abs(data.price_change_24h) / 10.0, 1.0)
                else:
                    signal_type = "HOLD"
                    confidence = 0.5

                signals[symbol] = TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence=confidence,
                    price_target=data.price,  # Use price_target instead of price
                    timestamp=datetime.now(timezone.utc)
                )

            return signals

        except Exception as e:
            logger.error(f"Error generating trading signals for {symbols}: {e}")
            return {}
    
    async def _process_token(self, 
                            raw_token: Dict[str, Any],
                            min_volume: float) -> Optional[TokenMetrics]:
        """Process individual token with full analysis."""
        try:
            quote = raw_token.get('quote', {}).get('USD', {})
            
            # Volume filter
            volume_24h = float(quote.get('volume_24h', 0))
            if volume_24h < min_volume:
                return None
            
            # Extract basic data
            symbol = raw_token['symbol']
            platform = raw_token.get('platform', {}) or {}
            address = platform.get('token_address', '').lower() if isinstance(platform, dict) else ''
            
            # Update price history
            price = float(quote.get('price', 0))
            if symbol:
                self.price_history[symbol].append(price)
                self.tracked_tokens.add(symbol)
            
            # Calculate technical indicators
            prices = np.array(list(self.price_history[symbol]))
            
            if len(prices) >= 2:
                returns = np.diff(prices) / prices[:-1]
                
                rsi = TechnicalAnalyzer.calculate_rsi(prices)
                macd, signal, histogram = TechnicalAnalyzer.calculate_macd(prices)
                upper, middle, lower, bb_position = TechnicalAnalyzer.calculate_bollinger_bands(prices)
                sharpe = TechnicalAnalyzer.calculate_sharpe_ratio(returns)
                sortino = TechnicalAnalyzer.calculate_sortino_ratio(returns)
                max_dd = TechnicalAnalyzer.calculate_max_drawdown(prices)
            else:
                rsi = 50.0
                macd = signal = histogram = 0.0
                bb_position = 0.5
                sharpe = sortino = 0.0
                max_dd = 0.0
            
            # Calculate scores
            liquidity_score = self._calculate_liquidity_score(volume_24h, quote.get('market_cap', 0))
            volatility_score = self._calculate_volatility_score(quote)
            momentum_score = self._calculate_momentum_score(quote, rsi, macd)
            quality_score = self._calculate_quality_score(raw_token, quote)
            
            # Create token metrics
            metrics = TokenMetrics(
                symbol=symbol,
                address=address,
                price=price,
                market_cap=float(quote.get('market_cap', 0)),
                volume_24h=volume_24h,
                liquidity_usd=volume_24h * 0.1,  # Estimate
                price_change_1h=float(quote.get('percent_change_1h', 0)),
                price_change_24h=float(quote.get('percent_change_24h', 0)),
                price_change_7d=float(quote.get('percent_change_7d', 0)),
                rsi=rsi,
                macd=histogram,
                bollinger_position=bb_position,
                volume_profile=float(volume_24h / max(1, np.mean([v for v in self.price_history[symbol] if v > 0]) if len(self.price_history[symbol]) > 0 else 1)),
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                max_drawdown=max_dd,
                liquidity_score=liquidity_score,
                volatility_score=volatility_score,
                momentum_score=momentum_score,
                quality_score=quality_score,
                rank=raw_token.get('cmc_rank', 0)
            )
            
            return metrics
            
        except Exception as e:
            logger.debug(f"Error processing token {raw_token.get('symbol')}: {e}")
            return None
    
    def _calculate_liquidity_score(self, volume: float, market_cap: float) -> float:
        """Calculate liquidity score (0-1)."""
        if market_cap == 0:
            return 0.0
        
        # Volume to market cap ratio
        ratio = volume / market_cap
        
        # Ideal ratio is around 0.1-0.3
        if ratio >= 0.1:
            score = min(1.0, ratio / 0.3)
        else:
            score = ratio / 0.1
        
        return float(score)
    
    def _calculate_volatility_score(self, quote: Dict) -> float:
        """Calculate volatility score (0-1, lower is better)."""
        changes = [
            abs(quote.get('percent_change_1h', 0)),
            abs(quote.get('percent_change_24h', 0)) / 24,
            abs(quote.get('percent_change_7d', 0)) / 168
        ]
        
        avg_volatility = np.mean(changes)
        
        # Normalize: 0-5% = good (0.8-1.0), 5-20% = medium (0.3-0.8), >20% = high (0-0.3)
        if avg_volatility <= 5:
            score = 0.8 + (5 - avg_volatility) / 25
        elif avg_volatility <= 20:
            score = 0.3 + (20 - avg_volatility) / 50
        else:
            score = max(0.0, 0.3 - (avg_volatility - 20) / 100)
        
        return float(score)
    
    def _calculate_momentum_score(self, quote: Dict, rsi: float, macd: float) -> float:
        """Calculate momentum score (0-1)."""
        # Price momentum
        price_momentum = (
            quote.get('percent_change_1h', 0) * 0.2 +
            quote.get('percent_change_24h', 0) * 0.5 +
            quote.get('percent_change_7d', 0) * 0.3
        ) / 100
        
        # RSI momentum (optimal around 50-70)
        if 50 <= rsi <= 70:
            rsi_score = 0.5 + (rsi - 50) / 40
        elif rsi > 70:
            rsi_score = 1.0 - (rsi - 70) / 60  # Overbought penalty
        else:
            rsi_score = rsi / 100
        
        # MACD momentum
        macd_score = 0.5 + np.tanh(macd / 10) * 0.5
        
        # Combine scores
        momentum = (price_momentum * 0.4 + rsi_score * 0.3 + macd_score * 0.3)
        return float(max(0, min(1, momentum)))
    
    def _calculate_quality_score(self, token: Dict, quote: Dict) -> float:
        """Calculate overall quality score."""
        score = 0.0
        
        # Rank score (top 100 = 1.0, decreasing)
        rank = token.get('cmc_rank', 1000)
        rank_score = max(0, 1 - (rank / 1000))
        score += rank_score * 0.3
        
        # Market cap score
        mcap = quote.get('market_cap', 0)
        if mcap > 1e9:  # >$1B
            mcap_score = 1.0
        elif mcap > 1e8:  # >$100M
            mcap_score = 0.8
        elif mcap > 1e7:  # >$10M
            mcap_score = 0.6
        else:
            mcap_score = 0.4
        score += mcap_score * 0.3
        
        # Volume score
        volume = quote.get('volume_24h', 0)
        if volume > 1e7:  # >$10M
            volume_score = 1.0
        elif volume > 1e6:  # >$1M
            volume_score = 0.7
        else:
            volume_score = 0.4
        score += volume_score * 0.2
        
        # Age/stability score (if available)
        date_added = token.get('date_added')
        if date_added:
            try:
                added_date = datetime.fromisoformat(date_added.replace('Z', '+00:00'))
                age_days = (datetime.now(added_date.tzinfo) - added_date).days
                age_score = min(1.0, age_days / 365)  # Full score after 1 year
            except:
                age_score = 0.5
        else:
            age_score = 0.5
        score += age_score * 0.2
        
        return float(score)
    
    def _rank_tokens(self, tokens: List[TokenMetrics]) -> List[TokenMetrics]:
        """Calculate composite scores and rank tokens."""
        if not tokens:
            return tokens
        
        # Calculate composite score for each token
        for token in tokens:
            # Weighted composite score
            composite = (
                token.liquidity_score * 0.25 +
                token.momentum_score * 0.25 +
                token.quality_score * 0.25 +
                token.volatility_score * 0.15 +  # Lower vol is better
                (1 - token.max_drawdown) * 0.10  # Lower drawdown is better
            )
            token.composite_score = composite
        
        # Sort by composite score
        tokens.sort(key=lambda t: t.composite_score, reverse=True)
        
        return tokens
    
    async def scan_network(self,
                          chain: str,
                          limit: int = 50,
                          min_volume: float = 10000) -> ScanResult:
        """Scan a specific network for tokens."""
        start_time = time.time()
        logger.info(f"🔍 Scanning {chain} for tokens (limit: {limit}, min_volume: ${min_volume:,.0f})")

        try:
            # Fetch top tokens from CoinMarketCap
            url = f"{self.BASE_URL}/cryptocurrency/listings/latest"
            params = {
                'start': 1,
                'limit': limit,
                'convert': 'USD',
                'sort': 'market_cap',
                'sort_dir': 'desc'
            }

            response = await self._make_request(url, params)

            if not response or 'data' not in response:
                return ScanResult([], time.time() - start_time, 0, ["No data in response"], 0, 0)

            raw_tokens = response.get('data', [])
            tokens = []
            errors = []

            for raw_token in raw_tokens:
                try:
                    token = await self._process_token(raw_token, min_volume)
                    if token:
                        tokens.append(token)
                except Exception as e:
                    errors.append(f"Error processing {raw_token.get('symbol')}: {str(e)}")

            # Rank tokens
            tokens = self._rank_tokens(tokens)

            scan_duration = time.time() - start_time
            logger.info(f"✅ {chain} scan complete: {len(tokens)} tokens found in {scan_duration:.2f}s")

            return ScanResult(
                tokens=tokens,
                scan_duration=scan_duration,
                tokens_analyzed=len(raw_tokens),
                errors=errors,
                cache_hits=self.metrics['cache_hits'],
                api_calls=self.metrics['total_api_calls']
            )

        except Exception as e:
            scan_duration = time.time() - start_time
            logger.error(f"❌ Failed to scan {chain}: {e}")
            return ScanResult([], scan_duration, 0, [str(e)], 0, 0)

    async def scan_multi_network(self,
                                chains: List[str],
                                limit_per_chain: int = 50) -> Dict[str, ScanResult]:
        """Scan multiple networks concurrently."""
        logger.info(f"🚀 Multi-network scan starting: {', '.join(chains)}")

        tasks = [
            self.scan_network(chain, limit_per_chain)
            for chain in chains
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Package results
        scan_results = {}
        for chain, result in zip(chains, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to scan {chain}: {result}")
                scan_results[chain] = ScanResult([], 0, 0, [str(result)], 0, 0)
            else:
                scan_results[chain] = result

        return scan_results
    
    async def get_token_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for specific token."""
        url = f"{self.BASE_URL}/cryptocurrency/info"
        params = {'symbol': symbol.upper()}
        
        try:
            data = await self._make_request(url, params)
            return data.get('data', {}).get(symbol.upper())
        except Exception as e:
            logger.error(f"Error fetching details for {symbol}: {e}")
            return None
    
    async def get_real_time_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get real-time quotes for multiple tokens."""
        url = f"{self.BASE_URL}/cryptocurrency/quotes/latest"
        params = {'symbol': ','.join(s.upper() for s in symbols)}
        
        try:
            data = await self._make_request(url, params, bypass_cache=True)
            return data.get('data', {})
        except Exception as e:
            logger.error(f"Error fetching quotes: {e}")
            return {}
    
    async def stream_prices(self, 
                           symbols: List[str], 
                           interval: int = 60,
                           callback: Optional[callable] = None):
        """Stream price updates for tokens."""
        logger.info(f"📡 Starting price stream for {len(symbols)} tokens")
        
        while True:
            try:
                quotes = await self.get_real_time_quotes(symbols)
                
                for symbol, data in quotes.items():
                    quote = data.get('quote', {}).get('USD', {})
                    price = quote.get('price', 0)
                    
                    if price:
                        self.price_history[symbol].append(price)
                        
                        if callback:
                            await callback(symbol, price, quote)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Price stream error: {e}")
                await asyncio.sleep(interval * 2)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        return {
            'scanner': 'CoinMarketLiveScanner',
            'status': self._status.value if hasattr(self._status, 'value') else str(self._status),
            'uptime_seconds': time.time() - getattr(self, '_start_time', time.time()),
            'requests': {
                'total': self.metrics['total_requests'],
                'successful': self.metrics['successful_requests'],
                'failed': self.metrics['failed_requests'],
                'success_rate': self.metrics['successful_requests'] / max(1, self.metrics['total_requests'])
            },
            'api': {
                'total_calls': self.metrics['total_api_calls'],
                'cache_hits': self.metrics['cache_hits'],
                'avg_response_time': self.metrics['avg_response_time']
            },
            'rate_limiter': self.rate_limiter.get_stats(),
            'cache': self.cache.get_stats(),
            'tokens_tracked': len(self.tracked_tokens),
            'last_update': self.last_update_time.isoformat() if hasattr(self, 'last_update_time') and self.last_update_time else None,
            'update_count': self.update_count
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the scanner."""
        return {
            'status': self._status.value if hasattr(self._status, 'value') else str(self._status),
            'api_connected': self.metrics['successful_requests'] > 0,
            'cache_operational': True,
            'rate_limiter_healthy': self.rate_limiter.error_count < 10,
            'metrics': {
                'total_requests': self.metrics['total_requests'],
                'failed_requests': self.metrics['failed_requests'],
                'cache_hits': self.metrics['cache_hits'],
                'avg_response_time': self.metrics['avg_response_time']
            }
        }
