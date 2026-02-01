"""
Production-Grade Token Analyzer v2.1 FINAL
==========================================

Final production implementation with all technical refinements:

✅ Error categorization for smart metrics/alerts
✅ Simplified code checks
✅ Dynamic backoff with Retry-After headers
✅ Cache key versioning for schema changes
✅ Per-provider metrics (latency, success/failure)
✅ Async streaming for large batches
✅ Strict protocol enforcement
✅ Connection pool optimization
✅ Enhanced observability
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Protocol, AsyncIterator
from dataclasses import dataclass, field as dc_field
from enum import Enum
import hashlib
import json
from collections import defaultdict
import time

import aiohttp
from web3 import Web3
from web3.exceptions import Web3Exception
from pydantic import BaseModel, Field, validator
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

try:
    from network_manager import NetworkManager, network_manager
except ImportError:
    # Fallback for when network_manager.py is not available
    NetworkManager = None
    network_manager = None

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Constants & Configuration
# ============================================================================

# Cache schema version for invalidation
CACHE_SCHEMA_VERSION = "v2.1"

ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

COINGECKO_PLATFORMS = {
    "ethereum": "ethereum",
    "bsc": "binance-smart-chain",
    "polygon": "polygon-pos",
    "avalanche": "avalanche",
    "fantom": "fantom",
    "base": "base",
    "arbitrum": "arbitrum-one",
    "optimism": "optimistic-ethereum",
    "cronos": "cronos",
    "zksync": "zksync",
    "linea": "linea",
}


# ============================================================================
# Error Classification (Technical Review Item #2)
# ============================================================================

class ErrorCategory(str, Enum):
    """Categorized errors for smart metrics"""
    ONCHAIN_FAILURE = "onchain_failure"
    COINGECKO_FAILURE = "coingecko_failure"
    NETWORK_FAILURE = "network_failure"
    VALIDATION_FAILURE = "validation_failure"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class CategorizedError:
    """Structured error with category"""
    category: ErrorCategory
    message: str
    timestamp: datetime = dc_field(default_factory=lambda: datetime.now(timezone.utc))
    provider: Optional[str] = None
    field: Optional[str] = None


# ============================================================================
# Enhanced Metrics Tracking (Technical Review Item #5)
# ============================================================================

@dataclass
class ProviderMetrics:
    """Per-provider performance metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    _latency_history: List[float] = dc_field(default_factory=list, repr=False)
    
    def record_request(self, latency_ms: float, success: bool):
        """Record a request"""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        self.total_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        
        # Keep last 1000 samples for percentile calculation
        self._latency_history.append(latency_ms)
        if len(self._latency_history) > 1000:
            self._latency_history.pop(0)
        
        # Update percentiles
        if self._latency_history:
            sorted_latencies = sorted(self._latency_history)
            self.latency_p50 = sorted_latencies[len(sorted_latencies) // 2]
            self.latency_p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            self.latency_p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
    
    @property
    def avg_latency_ms(self) -> float:
        """Average latency"""
        return self.total_latency_ms / self.total_requests if self.total_requests > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """Success rate percentage"""
        return (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0


class MetricsCollector:
    """Centralized metrics collection"""
    
    def __init__(self):
        self.providers: Dict[str, ProviderMetrics] = defaultdict(ProviderMetrics)
        self.errors_by_category: Dict[ErrorCategory, int] = defaultdict(int)
        self.total_requests = 0
        self.cache_hits = 0
        self.successful_analyses = 0
        self.failed_analyses = 0
    
    def record_error(self, error: CategorizedError):
        """Record categorized error"""
        self.errors_by_category[error.category] += 1
        if error.provider:
            self.providers[error.provider].failed_requests += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0.0,
            "successful_analyses": self.successful_analyses,
            "failed_analyses": self.failed_analyses,
            "success_rate": (self.successful_analyses / self.total_requests * 100) if self.total_requests > 0 else 0.0,
            "providers": {
                name: {
                    "requests": m.total_requests,
                    "success_rate": m.success_rate,
                    "avg_latency_ms": m.avg_latency_ms,
                    "p50_latency_ms": m.latency_p50,
                    "p95_latency_ms": m.latency_p95,
                    "p99_latency_ms": m.latency_p99,
                }
                for name, m in self.providers.items()
            },
            "errors_by_category": {
                cat.value: count
                for cat, count in self.errors_by_category.items()
            }
        }


# ============================================================================
# Data Models
# ============================================================================

class TokenMetadata(BaseModel):
    """Enhanced metadata with categorized errors"""
    analysis_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_duration_ms: float = 0.0
    analysis_source: str = "TokenAnalyzer"
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = CACHE_SCHEMA_VERSION
    
    verified: bool = False
    onchain_verified: bool = False
    coingecko_verified: bool = False
    data_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    cache_hit: bool = False
    cache_ttl_seconds: Optional[int] = None
    source_timestamp: Optional[datetime] = None
    
    # Enhanced error tracking
    errors: List[str] = Field(default_factory=list)
    categorized_errors: List[Dict[str, Any]] = Field(default_factory=list)
    field_errors: Dict[str, str] = Field(default_factory=dict)
    
    # Provider metrics
    provider_latencies: Dict[str, float] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PriceData(BaseModel):
    """Token price and market metrics"""
    current_price_usd: float = 0.0
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    volume_24h_usd: float = 0.0
    market_cap_usd: float = 0.0
    fully_diluted_valuation: float = 0.0
    liquidity_usd: float = 0.0
    last_updated: Optional[datetime] = None

    @validator('current_price_usd', 'volume_24h_usd', 'market_cap_usd', 'liquidity_usd')
    def validate_positive(cls, v):
        return max(0.0, v)


class TokenInfo(BaseModel):
    """Complete token information"""
    address: str
    chain: str
    chain_id: int
    
    symbol: str = "UNKNOWN"
    name: str = "Unknown Token"
    decimals: int = 18
    total_supply: Optional[int] = None
    
    price_data: PriceData = Field(default_factory=PriceData)
    
    primary_exchange: Optional[str] = None
    pair_address: Optional[str] = None
    quote_token: str = "USD"
    
    metadata: TokenMetadata = Field(default_factory=TokenMetadata)
    
    raw_onchain_data: Dict[str, Any] = Field(default_factory=dict)
    raw_coingecko_data: Dict[str, Any] = Field(default_factory=dict)

    @validator('address')
    def validate_address(cls, v):
        if not v or not Web3.is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")
        return Web3.to_checksum_address(v)
    
    @validator('symbol')
    def normalize_symbol(cls, v):
        return v.upper().strip() if v else "UNKNOWN"
    
    @validator('name')
    def normalize_name(cls, v):
        return v.strip() if v else "Unknown Token"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Circuit Breaker
# ============================================================================

@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking"""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "CLOSED"
    failure_threshold: int = 5
    timeout_seconds: int = 60


class CircuitBreaker:
    """Circuit breaker pattern"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.state = CircuitBreakerState(
            failure_threshold=failure_threshold,
            timeout_seconds=timeout
        )
        self.success_count = 0
    
    async def call(self, func, *args, **kwargs):
        """Execute with circuit breaker"""
        if self.state.state == "OPEN":
            if self.state.last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self.state.last_failure_time).total_seconds()
                if elapsed >= self.state.timeout_seconds:
                    self.state.state = "HALF_OPEN"
                    logger.info("Circuit breaker HALF_OPEN")
                else:
                    raise Exception(f"Circuit breaker OPEN - {self.state.timeout_seconds - elapsed:.0f}s remaining")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        if self.state.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= 3:
                self.state.state = "CLOSED"
                self.state.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker CLOSED")
        else:
            self.state.failure_count = max(0, self.state.failure_count - 1)
    
    def _on_failure(self):
        self.state.failure_count += 1
        self.state.last_failure_time = datetime.now(timezone.utc)
        
        if self.state.failure_count >= self.state.failure_threshold:
            self.state.state = "OPEN"
            logger.error(f"Circuit breaker OPEN after {self.state.failure_count} failures")


# ============================================================================
# Cache Backend
# ============================================================================

class CacheBackend(Protocol):
    """Cache backend protocol"""
    
    async def get(self, key: str) -> Optional[Any]: ...
    async def set(self, key: str, value: Any, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...
    def get_stats(self) -> Dict[str, int]: ...


class InMemoryCacheBackend:
    """In-memory cache implementation"""
    
    def __init__(self):
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, expiry = self._cache[key]
            if datetime.now(timezone.utc) < expiry:
                self._hits += 1
                return value
            else:
                del self._cache[key]
        
        self._misses += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: int) -> None:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        self._cache[key] = (value, expiry)
    
    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)
    
    def get_stats(self) -> Dict[str, int]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "size": len(self._cache)
        }


class CacheManager:
    """Cache manager with schema versioning"""
    
    def __init__(self, backend: Optional[CacheBackend] = None, default_ttl: int = 300):
        self.backend = backend or InMemoryCacheBackend()
        self.default_ttl = default_ttl
    
    def _generate_key(self, *args) -> str:
        """Generate cache key with schema version (Technical Review Item #4)"""
        # Include schema version to invalidate on changes
        key_parts = [CACHE_SCHEMA_VERSION] + [str(arg).lower().strip() for arg in args]
        key_str = ":".join(key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def get(self, *args) -> Optional[Any]:
        key = self._generate_key(*args)
        return await self.backend.get(key)
    
    async def set(self, value: Any, *args, ttl: Optional[int] = None) -> None:
        key = self._generate_key(*args)
        ttl = ttl or self.default_ttl
        await self.backend.set(key, value, ttl)
        
        # Log cache TTL for observability (Technical Review suggestion)
        logger.debug(f"Cached with TTL: {ttl}s", extra={'cache_key': key[:16]})
    
    async def delete(self, *args) -> None:
        key = self._generate_key(*args)
        await self.backend.delete(key)
    
    def get_stats(self) -> Dict[str, int]:
        return self.backend.get_stats()


# ============================================================================
# Rate Limiter Backend
# ============================================================================

class RateLimiterBackend(Protocol):
    """Rate limiter backend protocol"""
    
    async def acquire(self, key: str, rate: int, per: int) -> bool: ...


class LocalRateLimiter:
    """Local rate limiter"""
    
    def __init__(self):
        self._buckets: Dict[str, tuple[float, datetime]] = {}
    
    async def acquire(self, key: str, rate: int, per: int) -> bool:
        current = datetime.now(timezone.utc)
        
        if key in self._buckets:
            allowance, last_check = self._buckets[key]
        else:
            allowance = rate
            last_check = current
        
        time_passed = (current - last_check).total_seconds()
        allowance += time_passed * (rate / per)
        allowance = min(allowance, rate)
        
        if allowance >= 1.0:
            allowance -= 1.0
            self._buckets[key] = (allowance, current)
            return True
        else:
            sleep_time = (1.0 - allowance) * (per / rate)
            await asyncio.sleep(sleep_time)
            self._buckets[key] = (0.0, datetime.now(timezone.utc))
            return True


class RateLimiter:
    """Rate limiter with backend support"""
    
    def __init__(self, rate: int = 50, per: int = 60, backend: Optional[RateLimiterBackend] = None):
        self.rate = rate
        self.per = per
        self.backend = backend or LocalRateLimiter()
    
    async def acquire(self, key: str = "default") -> None:
        await self.backend.acquire(key, self.rate, self.per)


# ============================================================================
# Provider Protocol (Technical Review Item #8)
# ============================================================================

class DataProvider(Protocol):
    """Strict data provider protocol"""
    
    async def fetch_token_data(
        self,
        contract_address: str,
        chain: str,
        correlation_id: str
    ) -> Optional[Dict[str, Any]]: ...
    
    async def close(self) -> None: ...


# ============================================================================
# CoinGecko Provider with Retry-After (Technical Review Item #3)
# ============================================================================

class CoinGeckoProvider:
    """CoinGecko provider with dynamic backoff"""
    
    def __init__(
        self,
        base_url: str = "https://api.coingecko.com/api/v3",
        api_key: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None,
        timeout: int = 10,
        metrics_collector: Optional[MetricsCollector] = None
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.rate_limiter = rate_limiter or RateLimiter(rate=50, per=60)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        self.metrics = metrics_collector or MetricsCollector()
        self._session: Optional[aiohttp.ClientSession] = None
        
        if api_key:
            self.base_url = "https://pro-api.coingecko.com/api/v3"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get session with optimized connection pooling (Technical Review Item #7)"""
        if self._session is None or self._session.closed:
            # Optimized connector for connection pooling
            connector = aiohttp.TCPConnector(
                limit=100,  # Max connections
                limit_per_host=30,
                ttl_dns_cache=300
            )
            
            headers = {}
            if self.api_key:
                headers['x-cg-pro-api-key'] = self.api_key
            
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=headers,
                connector=connector
            )
        return self._session
    
    async def close(self) -> None:
        """Close session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _fetch(self, url: str, correlation_id: str) -> Optional[Dict]:
        """Fetch with dynamic backoff from Retry-After header"""
        start_time = time.time()
        success = False
        
        try:
            async def _do_fetch():
                await self.rate_limiter.acquire("coingecko")
                
                session = await self._get_session()
                async with session.get(url) as response:
                    if response.status == 404:
                        return None
                    
                    if response.status == 429:
                        # Use Retry-After header for dynamic backoff
                        retry_after = response.headers.get('Retry-After', '60')
                        try:
                            wait_seconds = int(retry_after)
                        except ValueError:
                            wait_seconds = 60
                        
                        logger.warning(
                            f"Rate limited - waiting {wait_seconds}s",
                            extra={'correlation_id': correlation_id}
                        )
                        
                        # Record rate limit error
                        self.metrics.record_error(CategorizedError(
                            category=ErrorCategory.RATE_LIMIT,
                            message=f"Rate limited, Retry-After: {wait_seconds}",
                            provider="coingecko"
                        ))
                        
                        await asyncio.sleep(wait_seconds)
                        raise aiohttp.ClientError("Rate limit - retry scheduled")
                    
                    response.raise_for_status()
                    return await response.json()
            
            result = await self.circuit_breaker.call(_do_fetch)
            success = True
            return result
            
        except Exception as e:
            # Categorize error
            if "timeout" in str(e).lower():
                category = ErrorCategory.TIMEOUT
            elif "circuit breaker" in str(e).lower():
                category = ErrorCategory.CIRCUIT_BREAKER
            else:
                category = ErrorCategory.COINGECKO_FAILURE
            
            self.metrics.record_error(CategorizedError(
                category=category,
                message=str(e),
                provider="coingecko"
            ))
            
            logger.error(
                f"CoinGecko fetch failed: {e}",
                extra={'correlation_id': correlation_id, 'category': category.value}
            )
            raise
        
        finally:
            # Record metrics
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.providers["coingecko"].record_request(latency_ms, success)
    
    async def fetch_token_data(
        self,
        contract_address: str,
        chain: str,
        correlation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch token data"""
        platform = COINGECKO_PLATFORMS.get(chain)
        if not platform:
            return None
        
        url = f"{self.base_url}/coins/{platform}/contract/{contract_address.lower()}"
        
        try:
            data = await self._fetch(url, correlation_id)
            if data:
                logger.info(
                    f"CoinGecko data fetched",
                    extra={'correlation_id': correlation_id, 'chain': chain}
                )
            return data
        except Exception:
            return None


# ============================================================================
# On-Chain Provider with Simplified Code Check (Technical Review Item #1)
# ============================================================================

class OnChainProvider:
    """On-chain provider with optimized checks"""
    
    def __init__(
        self,
        web3_connections: Dict[str, Web3],
        metrics_collector: Optional[MetricsCollector] = None
    ):
        self.web3_connections = web3_connections
        self.metrics = metrics_collector or MetricsCollector()
    
    def get_web3(self, chain: str) -> Optional[Web3]:
        return self.web3_connections.get(chain)
    
    async def fetch_token_data(
        self,
        contract_address: str,
        chain: str,
        correlation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch on-chain data with metrics"""
        start_time = time.time()
        success = False
        
        try:
            w3 = self.get_web3(chain)
            if not w3:
                self.metrics.record_error(CategorizedError(
                    category=ErrorCategory.NETWORK_FAILURE,
                    message=f"No Web3 connection for {chain}",
                    provider="onchain"
                ))
                return None
            
            # Simplified code check (Technical Review suggestion)
            code = await asyncio.to_thread(
                w3.eth.get_code,
                Web3.to_checksum_address(contract_address)
            )
            
            if not code or code.hex() == '0x':
                logger.warning(
                    f"No contract code",
                    extra={'correlation_id': correlation_id, 'chain': chain}
                )
                return None
            
            contract = w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=ERC20_ABI
            )
            
            result = {
                "contract_verified": True,
                "field_errors": {}
            }
            
            # Fetch fields with individual error tracking
            for field_name, func in [
                ("name", contract.functions.name),
                ("symbol", contract.functions.symbol),
                ("decimals", contract.functions.decimals),
                ("total_supply", contract.functions.totalSupply)
            ]:
                try:
                    result[field_name] = await asyncio.to_thread(func().call)
                except Exception as e:
                    result["field_errors"][field_name] = str(e)
                    result[field_name] = None if field_name == "total_supply" else (18 if field_name == "decimals" else "Unknown")
                    
                    # Record field-level error
                    self.metrics.record_error(CategorizedError(
                        category=ErrorCategory.ONCHAIN_FAILURE,
                        message=str(e),
                        provider="onchain",
                        field=field_name
                    ))
            
            success = True
            return result
            
        except Exception as e:
            self.metrics.record_error(CategorizedError(
                category=ErrorCategory.ONCHAIN_FAILURE,
                message=str(e),
                provider="onchain"
            ))
            
            logger.error(
                f"On-chain fetch failed: {e}",
                extra={'correlation_id': correlation_id},
                exc_info=True
            )
            return None
        
        finally:
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.providers["onchain"].record_request(latency_ms, success)
    
    async def close(self) -> None:
        """Cleanup (for protocol compliance)"""
        pass


# ============================================================================
# Analyzer Configuration
# ============================================================================

@dataclass
class AnalyzerConfig:
    """Analyzer configuration"""
    weight_onchain: float = 0.4
    weight_coingecko: float = 0.6
    cache_enabled: bool = True
    cache_ttl_high_quality: int = 600
    cache_ttl_low_quality: int = 60
    max_concurrent: int = 10
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60


# ============================================================================
# Token Analyzer v2.1 FINAL
# ============================================================================

class TokenAnalyzer:
    """Production-grade token analyzer v2.1"""
    
    def __init__(
        self,
        web3_connections: Dict[str, Web3],
        coingecko_provider: Optional[CoinGeckoProvider] = None,
        cache_manager: Optional[CacheManager] = None,
        config: Optional[AnalyzerConfig] = None,
        network_manager: Optional[NetworkManager] = None,
        metrics_collector: Optional[MetricsCollector] = None
    ):
        self.web3_connections = web3_connections
        self.config = config or AnalyzerConfig()
        self.network_manager = network_manager or globals().get('network_manager')
        self.metrics = metrics_collector or MetricsCollector()
        
        # Providers
        self.coingecko = coingecko_provider or CoinGeckoProvider(metrics_collector=self.metrics)
        self.onchain = OnChainProvider(web3_connections, metrics_collector=self.metrics)
        
        # Cache
        self.cache = cache_manager if self.config.cache_enabled else None
        
        logger.info("TokenAnalyzer v2.1 initialized")
    
    async def analyze_token(
        self,
        contract_address: str,
        chain: str,
        force_refresh: bool = False,
        correlation_id: Optional[str] = None
    ) -> TokenInfo:
        """Analyze token with enhanced metrics"""
        start_time = time.time()
        correlation_id = correlation_id or str(uuid.uuid4())
        
        self.metrics.total_requests += 1
        
        # Normalize address
        try:
            address = Web3.to_checksum_address(contract_address)
        except Exception as e:
            self.metrics.record_error(CategorizedError(
                category=ErrorCategory.VALIDATION_FAILURE,
                message=str(e)
            ))
            raise ValueError(f"Invalid address: {contract_address}")
        
        chain_id = self.network_manager.get_chain_id(chain) or 0
        
        # Check cache
        if not force_refresh and self.cache:
            cached = await self.cache.get("token", address, chain)
            if cached:
                self.metrics.cache_hits += 1
                token_info = TokenInfo(**cached)
                token_info.metadata.cache_hit = True
                token_info.metadata.correlation_id = correlation_id
                return token_info
        
        # Initialize token
        token_info = TokenInfo(address=address, chain=chain, chain_id=chain_id)
        token_info.metadata.correlation_id = correlation_id
        
        categorized_errors = []
        field_errors = {}
        data_quality = 0.0
        provider_latencies = {}
        
        # Fetch on-chain
        onchain_start = time.time()
        onchain_data = await self.onchain.fetch_token_data(address, chain, correlation_id)
        provider_latencies["onchain"] = (time.time() - onchain_start) * 1000
        
        if onchain_data:
            token_info.symbol = onchain_data.get("symbol", "UNKNOWN")
            token_info.name = onchain_data.get("name", "Unknown Token")
            token_info.decimals = onchain_data.get("decimals", 18)
            token_info.total_supply = onchain_data.get("total_supply")
            token_info.raw_onchain_data = onchain_data
            token_info.metadata.onchain_verified = True
            
            if onchain_data.get("field_errors"):
                field_errors.update(onchain_data["field_errors"])
            
            data_quality += self.config.weight_onchain
        else:
            categorized_errors.append({
                "category": ErrorCategory.ONCHAIN_FAILURE.value,
                "message": "Failed to fetch on-chain data"
            })
        
        # Fetch CoinGecko
        gecko_start = time.time()
        try:
            gecko_data = await self.coingecko.fetch_token_data(address, chain, correlation_id)
            provider_latencies["coingecko"] = (time.time() - gecko_start) * 1000
            
            if gecko_data:
                token_info = self._merge_coingecko_data(token_info, gecko_data)
                token_info.metadata.coingecko_verified = True
                data_quality += self.config.weight_coingecko
            else:
                categorized_errors.append({
                    "category": ErrorCategory.COINGECKO_FAILURE.value,
                    "message": "Token not found on CoinGecko"
                })
        except Exception as e:
            provider_latencies["coingecko"] = (time.time() - gecko_start) * 1000
            categorized_errors.append({
                "category": ErrorCategory.COINGECKO_FAILURE.value,
                "message": str(e)
            })
        
        # Update metadata
        duration = (time.time() - start_time) * 1000
        
        ttl = (
            self.config.cache_ttl_high_quality
            if data_quality >= 0.8
            else self.config.cache_ttl_low_quality
        )
        
        token_info.metadata.verified = (
            token_info.metadata.onchain_verified or
            token_info.metadata.coingecko_verified
        )
        token_info.metadata.data_quality_score = min(data_quality, 1.0)
        token_info.metadata.categorized_errors = categorized_errors
        token_info.metadata.field_errors = field_errors
        token_info.metadata.analysis_duration_ms = duration
        token_info.metadata.provider_latencies = provider_latencies
        token_info.metadata.cache_ttl_seconds = ttl
        token_info.metadata.source_timestamp = datetime.now(timezone.utc)
        
        # Cache
        if self.cache and data_quality > 0:
            await self.cache.set(token_info.dict(), "token", address, chain, ttl=ttl)
        
        # Update metrics
        if data_quality > 0:
            self.metrics.successful_analyses += 1
        else:
            self.metrics.failed_analyses += 1
        
        logger.info(
            f"Analysis complete: {token_info.symbol}",
            extra={
                'correlation_id': correlation_id,
                'quality': data_quality,
                'duration_ms': duration
            }
        )
        
        return token_info
    
    def _merge_coingecko_data(self, token_info: TokenInfo, gecko_data: Dict) -> TokenInfo:
        """Merge CoinGecko data immutably"""
        updated = token_info.copy(deep=True)
        
        if updated.symbol == "UNKNOWN":
            updated.symbol = gecko_data.get("symbol", "UNKNOWN").upper()
        if updated.name == "Unknown Token":
            updated.name = gecko_data.get("name", "Unknown Token")
        
        market_data = gecko_data.get("market_data", {})
        
        updated.price_data.current_price_usd = market_data.get("current_price", {}).get("usd", 0.0)
        updated.price_data.price_change_24h = market_data.get("price_change_percentage_24h", 0.0)
        updated.price_data.price_change_7d = market_data.get("price_change_percentage_7d", 0.0)
        updated.price_data.volume_24h_usd = market_data.get("total_volume", {}).get("usd", 0.0)
        updated.price_data.market_cap_usd = market_data.get("market_cap", {}).get("usd", 0.0)
        updated.price_data.fully_diluted_valuation = market_data.get("fully_diluted_valuation", {}).get("usd", 0.0)
        
        # Deduplicate tickers
        tickers = gecko_data.get("tickers", [])
        seen_pairs = set()
        total_liquidity = 0.0
        
        for ticker in tickers:
            pair_key = f"{ticker.get('market', {}).get('name')}:{ticker.get('base')}:{ticker.get('target')}"
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                total_liquidity += ticker.get("converted_volume", {}).get("usd", 0.0)
        
        updated.price_data.liquidity_usd = total_liquidity
        updated.price_data.last_updated = datetime.now(timezone.utc)
        
        if tickers:
            primary = tickers[0]
            updated.primary_exchange = primary.get("market", {}).get("name")
            updated.quote_token = primary.get("target", "USD")
        
        updated.raw_coingecko_data = {
            "market_data": market_data,
            "tickers_count": len(tickers),
            "unique_pairs": len(seen_pairs),
            "coingecko_id": gecko_data.get("id")
        }
        
        return updated
    
    async def analyze_batch_stream(
        self,
        tokens: List[tuple[str, str]],
        max_concurrent: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> AsyncIterator[TokenInfo]:
        """
        Stream results as they complete (Technical Review Item #6)
        
        Yields results as soon as available instead of waiting for all
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        max_concurrent = max_concurrent or self.config.max_concurrent
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_semaphore(addr: str, chain: str, index: int):
            async with semaphore:
                child_id = f"{correlation_id}-{index}"
                try:
                    return await self.analyze_token(addr, chain, correlation_id=child_id)
                except Exception as e:
                    logger.error(f"Batch item {index} failed: {e}", extra={'correlation_id': child_id})
                    chain_id = self.network_manager.get_chain_id(chain) or 0
                    token = TokenInfo(address=addr, chain=chain, chain_id=chain_id)
                    token.metadata.categorized_errors.append({
                        "category": ErrorCategory.VALIDATION_FAILURE.value,
                        "message": str(e)
                    })
                    token.metadata.correlation_id = child_id
                    return token
        
        # Create tasks
        tasks = [
            asyncio.create_task(analyze_with_semaphore(addr, chain, i))
            for i, (addr, chain) in enumerate(tokens)
        ]
        
        # Yield as completed
        for coro in asyncio.as_completed(tasks):
            result = await coro
            yield result
    
    async def analyze_batch(
        self,
        tokens: List[tuple[str, str]],
        max_concurrent: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> List[TokenInfo]:
        """Analyze batch (collect all results)"""
        results = []
        async for token in self.analyze_batch_stream(tokens, max_concurrent, correlation_id):
            results.append(token)
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics"""
        return self.metrics.get_summary()
    
    async def close(self) -> None:
        """Cleanup"""
        await self.coingecko.close()
        await self.onchain.close()
        logger.info("TokenAnalyzer closed")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# ============================================================================
# Example
# ============================================================================

async def main():
    """Example usage"""
    from web3 import Web3
    
    # Setup
    web3_connections = {}
    for network_name in ["ethereum", "bsc", "polygon"]:
        network = network_manager.get_network(network_name)
        if network:
            web3_connections[network_name] = Web3(Web3.HTTPProvider(network.rpc))
    
    config = AnalyzerConfig()
    
    async with TokenAnalyzer(web3_connections=web3_connections, config=config) as analyzer:
        # Single analysis
        print("\n" + "="*80)
        print("SINGLE TOKEN ANALYSIS")
        print("="*80)
        
        usdc = await analyzer.analyze_token(
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "ethereum"
        )
        
        print(f"Token: {usdc.name} ({usdc.symbol})")
        print(f"Price: ${usdc.price_data.current_price_usd:,.4f}")
        print(f"Quality: {usdc.metadata.data_quality_score:.1%}")
        print(f"Duration: {usdc.metadata.analysis_duration_ms:.0f}ms")
        print(f"Provider Latencies: {usdc.metadata.provider_latencies}")
        print(f"Cache TTL: {usdc.metadata.cache_ttl_seconds}s")
        
        # Streaming batch
        print("\n" + "="*80)
        print("STREAMING BATCH ANALYSIS")
        print("="*80)
        
        tokens = [
            ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "ethereum"),
            ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "ethereum"),
            ("0x2170Ed0880ac9A755fd29B2688956BD959F933F8", "bsc"),
        ]
        
        async for token in analyzer.analyze_batch_stream(tokens):
            print(f"✓ {token.symbol}: ${token.price_data.current_price_usd:,.2f}")
        
        # Metrics
        print("\n" + "="*80)
        print("COMPREHENSIVE METRICS")
        print("="*80)
        
        metrics = analyzer.get_metrics()
        print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
