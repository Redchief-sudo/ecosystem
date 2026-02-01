"""
Elite Production-Grade Multi-Chain Sentiment Token Scanner
Enhanced version with improved error handling, validation, and monitoring
Version: 2.1
"""

import asyncio
import logging
import re
import yaml
import os
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal
import json
import aiohttp
from web3 import Web3
from web3.exceptions import Web3Exception, ContractLogicError
import anthropic
from enum import Enum
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from functools import lru_cache
import time
import psutil
import threading

# Configure rotating file handler with configurable verbosity
handler = RotatingFileHandler('scanner.log', maxBytes=10*1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class Sentiment(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataQuality(Enum):
    """Track data source quality"""
    REAL = "real"
    SIMULATED = "simulated"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class AnalysisValidity(Enum):
    """IMPROVEMENT #1: Explicit validity contract for downstream consumers"""
    VALID = "valid"
    DEGRADED = "degraded"
    INVALID = "invalid"


@dataclass
class NetworkConfig:
    chain_id: int
    name: str
    rpc: str
    ws: Optional[str]
    explorer: str
    native_token: str
    wrapped_native: str
    block_time: float
    routers: Dict[str, str]
    fallback_rpcs: List[str]
    enabled: bool = True


@dataclass
class TokenMetrics:
    address: str
    symbol: str
    name: str
    network: str
    price_usd: float
    price_native: float
    liquidity_usd: float
    volume_24h: float
    price_change_1h: float
    price_change_24h: float
    price_change_7d: float
    holders: int
    market_cap: Optional[float]
    decimals: int
    total_supply: int
    data_quality: DataQuality = DataQuality.REAL
    valid: bool = True  # IMPROVEMENT #3: Explicit validity flag
    failure_reason: Optional[str] = None  # IMPROVEMENT #3: Why invalid
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AIInsight:
    """IMPROVEMENT #2: Separate AI output from scoring logic"""
    sentiment_label: str  # AI's opinion
    key_factors: List[str]  # AI's reasoning
    rationale: str  # AI's summary
    confidence: str  # AI's confidence
    raw_score: Optional[int] = None  # AI's raw score (for reference only)


@dataclass
class SentimentAnalysis:
    token_address: str
    symbol: str
    network: str
    overall_score: int  # IMPROVEMENT #2: Calculated by code, not AI
    sentiment: Sentiment
    confidence: str
    risk_level: RiskLevel  # IMPROVEMENT #2: Calculated by code
    key_factors: List[str]
    technical_signals: List[str]
    recommendation: str
    summary: str
    social_score: Optional[int]
    rugpull_risk: float
    honeypot_risk: float
    whale_concentration: float
    data_quality: DataQuality = DataQuality.REAL
    validity: AnalysisValidity = AnalysisValidity.VALID  # IMPROVEMENT #1
    ai_powered: bool = True
    ai_insight: Optional[AIInsight] = None  # IMPROVEMENT #2: Preserve AI output
    timestamp: datetime = field(default_factory=datetime.now)


class RPCHealthMonitor:
    """NEW: Monitor RPC health with parallel checks"""
    
    def __init__(self):
        self.health_status: Dict[str, bool] = {}
        self.last_check: Dict[str, datetime] = {}
        self.check_interval = timedelta(minutes=5)
    
    async def check_rpc_health(self, rpc_url: str, timeout: int = 5) -> bool:
        """Quick health check for RPC endpoint"""
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': timeout}))
            await asyncio.wait_for(
                asyncio.to_thread(w3.eth.block_number),
                timeout=timeout
            )
            self.health_status[rpc_url] = True
            self.last_check[rpc_url] = datetime.now()
            return True
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"RPC health check failed for {rpc_url}: {e}")
            self.health_status[rpc_url] = False
            self.last_check[rpc_url] = datetime.now()
            return False
    
    async def check_all_rpcs(self, rpcs: List[str]) -> Dict[str, bool]:
        """Parallel health check for all RPCs"""
        tasks = [self.check_rpc_health(rpc) for rpc in rpcs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            rpc: result if isinstance(result, bool) else False
            for rpc, result in zip(rpcs, results)
        }
    
    def is_healthy(self, rpc_url: str) -> bool:
        """Check if RPC is considered healthy"""
        if rpc_url not in self.health_status:
            return True  # Assume healthy if never checked
        
        # Re-check if too old
        if rpc_url in self.last_check:
            if datetime.now() - self.last_check[rpc_url] > self.check_interval:
                return True  # Allow retry
        
        return self.health_status.get(rpc_url, True)


class RPCManager:
    """Enhanced RPC manager with parallel initialization and health monitoring"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rpc_failures: Dict[str, int] = defaultdict(int)
        self.rpc_blacklist: Dict[str, datetime] = {}
        self.base_blacklist_duration = timedelta(minutes=5)
        self.health_monitor = RPCHealthMonitor()  # NEW
    
    def _get_blacklist_duration(self, rpc_url: str) -> timedelta:
        """Dynamic backoff: longer blacklist for repeated failures"""
        failure_count = self.rpc_failures.get(rpc_url, 0)
        multiplier = min(failure_count // 3, 4)
        return self.base_blacklist_duration * (2 ** multiplier)
    
    async def get_web3_with_fallback(
        self, 
        primary_rpc: str, 
        fallback_rpcs: List[str],
        network_name: str
    ) -> Optional[Web3]:
        """Try primary RPC then fallbacks with health-aware selection"""
        all_rpcs = [primary_rpc] + fallback_rpcs
        
        # Filter by health status
        healthy_rpcs = [rpc for rpc in all_rpcs if self.health_monitor.is_healthy(rpc)]
        if not healthy_rpcs:
            logger.warning(f"No healthy RPCs available for {network_name}, trying all")
            healthy_rpcs = all_rpcs
        
        for rpc_url in healthy_rpcs:
            if rpc_url in self.rpc_blacklist:
                duration = self._get_blacklist_duration(rpc_url)
                if datetime.now() - self.rpc_blacklist[rpc_url] < duration:
                    logger.debug(f"Skipping blacklisted RPC: {rpc_url}")
                    continue
                else:
                    del self.rpc_blacklist[rpc_url]
                    logger.info(f"RPC {rpc_url} removed from blacklist")
            
            for attempt in range(self.max_retries):
                try:
                    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
                    # Use asyncio.wait_for for timeout protection
                    block_number = await asyncio.wait_for(
                        asyncio.to_thread(w3.eth.block_number),
                        timeout=10
                    )
                    logger.debug(f"Connected to {network_name} via {rpc_url} (block: {block_number})")
                    self.rpc_failures[rpc_url] = 0
                    await self.health_monitor.check_rpc_health(rpc_url)
                    return w3
                except asyncio.TimeoutError:
                    logger.warning(f"RPC {rpc_url} timeout (attempt {attempt + 1}/{self.max_retries})")
                    self.rpc_failures[rpc_url] += 1
                except Exception as e:
                    error_type = type(e).__name__
                    logger.warning(f"RPC {rpc_url} attempt {attempt + 1}/{self.max_retries} failed: {error_type}: {e}")
                    self.rpc_failures[rpc_url] += 1
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
            
            if self.rpc_failures[rpc_url] >= self.max_retries:
                duration = self._get_blacklist_duration(rpc_url)
                self.rpc_blacklist[rpc_url] = datetime.now()
                logger.error(f"Blacklisted RPC {rpc_url} for {duration.total_seconds()}s")
        
        logger.critical(f"All RPCs failed for {network_name}")
        return None
    
    async def call_with_retry(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        timeout: int = 15,
        **kwargs
    ) -> Any:
        """Execute Web3 call with retry, timeout, and detailed error differentiation"""
        retries = max_retries or self.max_retries
        last_error = None
        
        for attempt in range(retries):
            try:
                # Wrap in timeout for safety
                return await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Call timeout after {timeout}s")
                logger.warning(f"Call timeout (attempt {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
            except ContractLogicError as e:
                logger.error(f"Contract logic error (no retry): {e}")
                raise
            except Web3Exception as e:
                last_error = e
                logger.debug(f"Web3 call attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
            except Exception as e:
                last_error = e
                logger.warning(f"Unexpected error (attempt {attempt + 1}/{retries}): {type(e).__name__}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        raise last_error or Exception("Max retries exceeded")


class MarketDataCache:
    """Enhanced cache with statistics"""
    
    def __init__(self, ttl_seconds: int = 30):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return data
            else:
                del self.cache[key]
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any):
        self.cache[key] = (value, time.time())
    
    def clear(self):
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'size': len(self.cache)
        }


class NetworkManager:
    """Enhanced network manager with parallel initialization"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.networks: Dict[str, NetworkConfig] = {}
        self.web3_instances: Dict[str, Web3] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.rpc_manager = RPCManager()
        
        if config_path and Path(config_path).exists():
            self._load_config_from_file(config_path)
        else:
            self._load_default_config()
    
    def _load_config_from_file(self, config_path: str):
        """Load network config from YAML with validation"""
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            networks_data = config_data.get('networks', {})
            for network_name, network_info in networks_data.items():
                if not network_info.get('enabled', True):
                    continue
                
                # Validate required fields
                required = ['chain_id', 'name', 'rpc', 'explorer', 'native_token', 'wrapped_native', 'block_time']
                missing = [f for f in required if f not in network_info]
                if missing:
                    logger.error(f"Network {network_name} missing fields: {missing}")
                    continue
                
                self.networks[network_name] = NetworkConfig(
                    chain_id=network_info['chain_id'],
                    name=network_info['name'],
                    rpc=network_info['rpc'],
                    ws=network_info.get('ws'),
                    explorer=network_info['explorer'],
                    native_token=network_info['native_token'],
                    wrapped_native=network_info['wrapped_native'],
                    block_time=network_info['block_time'],
                    routers=network_info.get('routers', {}),
                    fallback_rpcs=network_info.get('fallback_rpcs', []),
                    enabled=network_info.get('enabled', True)
                )
            logger.info(f"Loaded {len(self.networks)} networks from {config_path}")
        except Exception as e:
            logger.error(f"Error loading config: {e}", exc_info=True)
            self._load_default_config()
    
    def _load_default_config(self):
        """Default network configurations"""
        self.networks = {
            'ethereum': NetworkConfig(
                chain_id=1, name='Ethereum Mainnet',
                rpc='https://eth-mainnet.g.alchemy.com/v2/demo',
                ws='wss://eth-mainnet.g.alchemy.com/v2/demo',
                explorer='https://etherscan.io', native_token='ETH',
                wrapped_native='0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                block_time=12, routers={'uniswap_v2': '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'},
                fallback_rpcs=['https://1rpc.io/eth', 'https://eth.llamarpc.com', 'https://ethereum.publicnode.com']
            ),
            'bsc': NetworkConfig(
                chain_id=56, name='BSC',
                rpc='https://bsc.publicnode.com', ws=None,
                explorer='https://bscscan.com', native_token='BNB',
                wrapped_native='0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',
                block_time=3, routers={'pancakeswap': '0x10ED43C718714eb63d5aA57B78B54704E256024E'},
                fallback_rpcs=['https://1rpc.io/bnb', 'https://bsc.llamarpc.com']
            ),
        }
    
    async def initialize(self) -> None:
        """Initialize Web3 connections in parallel with health checks"""
        logger.info("Initializing scanner with parallel network connections...")
        self.session = aiohttp.ClientSession()
        
        # Parallel health checks first
        all_rpcs = []
        for config in self.networks.values():
            all_rpcs.extend([config.rpc] + config.fallback_rpcs)
        
        logger.info(f"Running health checks on {len(all_rpcs)} RPC endpoints...")
        await self.rpc_manager.health_monitor.check_all_rpcs(all_rpcs)
        
        # Parallel network initialization
        tasks = [self._init_network(n, c) for n, c in self.networks.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success = sum(1 for r in results if r is True)
        failed = len(results) - success
        logger.info(f"✓ Initialized {success}/{len(self.networks)} networks ({failed} failed)")
    
    async def _init_network(self, network_name: str, config: NetworkConfig) -> bool:
        try:
            w3 = await self.rpc_manager.get_web3_with_fallback(
                config.rpc, config.fallback_rpcs, network_name
            )
            if w3:
                self.web3_instances[network_name] = w3
                logger.info(f"✓ {config.name} ready")
                return True
            logger.error(f"✗ {config.name} failed")
            return False
        except Exception as e:
            logger.error(f"Error initializing {network_name}: {e}", exc_info=True)
            return False
    
    async def close(self) -> None:
        if self.session:
            await self.session.close()
    
    def get_web3(self, network: str) -> Optional[Web3]:
        return self.web3_instances.get(network)
    
    def get_config(self, network: str) -> Optional[NetworkConfig]:
        return self.networks.get(network)
    
    def get_all_networks(self) -> List[str]:
        return list(self.networks.keys())


class MarketDataProvider:
    """Enhanced market data with better error handling and data quality tracking"""
    
    CHAIN_MAP = {
        'ethereum': 'ethereum', 'bsc': 'bsc', 'polygon': 'polygon',
        'arbitrum': 'arbitrum', 'base': 'base', 'avalanche': 'avalanche',
        'optimism': 'optimism', 'fantom': 'fantom', 'cronos': 'cronos'
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.dexscreener_api = "https://api.dexscreener.com/latest/dex"
        self.cache = MarketDataCache(ttl_seconds=30)
    
    async def get_token_price_data(self, token_address: str, network: str) -> Tuple[Optional[Dict], DataQuality]:
        """Fetch from DexScreener with data quality tracking"""
        cache_key = f"{network}:{token_address}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for {token_address}")
            return cached, DataQuality.REAL
        
        chain_id = self.CHAIN_MAP.get(network)
        if not chain_id:
            logger.warning(f"Network {network} not supported by DexScreener (supported: {list(self.CHAIN_MAP.keys())})")
            return None, DataQuality.UNKNOWN
        
        try:
            url = f"{self.dexscreener_api}/tokens/{token_address}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    if pairs:
                        best = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                        
                        # Validate data completeness
                        has_price = best.get('priceUsd') is not None
                        has_liquidity = best.get('liquidity', {}).get('usd') is not None
                        has_volume = best.get('volume', {}).get('h24') is not None
                        
                        quality = DataQuality.REAL if (has_price and has_liquidity and has_volume) else DataQuality.PARTIAL
                        
                        result = {
                            'price_usd': float(best.get('priceUsd', 0)),
                            'price_native': float(best.get('priceNative', 0)),
                            'liquidity_usd': float(best.get('liquidity', {}).get('usd', 0) or 0),
                            'volume_24h': float(best.get('volume', {}).get('h24', 0) or 0),
                            'price_change_24h': float(best.get('priceChange', {}).get('h24', 0) or 0),
                        }
                        self.cache.set(cache_key, result)
                        
                        if quality == DataQuality.PARTIAL:
                            logger.warning(f"Partial data for {token_address}: missing some fields")
                        
                        return result, quality
                    else:
                        logger.warning(f"No trading pairs found for {token_address}")
                        return None, DataQuality.UNKNOWN
                else:
                    logger.warning(f"DexScreener returned status {resp.status} for {token_address}")
                    return None, DataQuality.UNKNOWN
        except asyncio.TimeoutError:
            logger.warning(f"DexScreener timeout for {token_address}")
            return None, DataQuality.UNKNOWN
        except Exception as e:
            logger.error(f"DexScreener error for {token_address}: {type(e).__name__}: {e}")
            return None, DataQuality.UNKNOWN
    
    async def get_holder_count(self, token_address: str, network: str, api_key: Optional[str] = None) -> Tuple[Optional[int], DataQuality]:
        """Get holder count with data quality tracking"""
        explorer_apis = {
            'ethereum': 'https://api.etherscan.io/api',
            'bsc': 'https://api.bscscan.com/api',
            'polygon': 'https://api.polygonscan.com/api',
        }
        
        api_url = explorer_apis.get(network)
        if not api_url:
            logger.debug(f"No explorer API for {network} (supported: {list(explorer_apis.keys())})")
            return None, DataQuality.UNKNOWN
        
        if not api_key:
            logger.debug(f"No API key provided for {network} explorer")
            return None, DataQuality.UNKNOWN
        
        try:
            params = {
                'module': 'token',
                'action': 'tokenholderlist',
                'contractaddress': token_address,
                'apikey': api_key
            }
            async with self.session.get(api_url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('status') == '1':
                        holder_count = len(data.get('result', []))
                        return holder_count, DataQuality.REAL
                    else:
                        logger.debug(f"Explorer API returned error: {data.get('message', 'unknown')}")
                        return None, DataQuality.UNKNOWN
                else:
                    logger.warning(f"Explorer API status {resp.status}")
                    return None, DataQuality.UNKNOWN
        except asyncio.TimeoutError:
            logger.debug(f"Holder count timeout for {token_address}")
            return None, DataQuality.UNKNOWN
        except Exception as e:
            logger.debug(f"Holder count error: {e}")
            return None, DataQuality.UNKNOWN


class TokenAnalyzer:
    """Enhanced token analyzer with clear data quality tracking"""
    
    ERC20_ABI = json.loads('[{"constant":true,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},{"constant":true,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},{"constant":true,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')
    
    def __init__(
        self,
        network_manager: NetworkManager,
        market_data: MarketDataProvider,
        rpc_manager: RPCManager,
        explorer_api_key: Optional[str] = None
    ):
        self.network_manager = network_manager
        self.market_data = market_data
        self.rpc_manager = rpc_manager
        self.explorer_api_key = explorer_api_key
    
    async def get_token_info(self, token_address: str, network: str) -> Optional[Dict]:
        """Get token metadata with retry and timeout"""
        w3 = self.network_manager.get_web3(network)
        if not w3:
            logger.error(f"No Web3 instance for {network}")
            return None
        
        try:
            addr = w3.to_checksum_address(token_address)
            contract = w3.eth.contract(address=addr, abi=self.ERC20_ABI)
            
            name = await self.rpc_manager.call_with_retry(contract.functions.name().call, timeout=10)
            symbol = await self.rpc_manager.call_with_retry(contract.functions.symbol().call, timeout=10)
            decimals = await self.rpc_manager.call_with_retry(contract.functions.decimals().call, timeout=10)
            supply = await self.rpc_manager.call_with_retry(contract.functions.totalSupply().call, timeout=10)
            
            info = {
                'address': addr, 'name': name, 'symbol': symbol,
                'decimals': decimals, 'total_supply': supply
            }
            logger.debug(f"Token info: {symbol} ({name})")
            return info
        except ContractLogicError as e:
            logger.error(f"Contract error for {token_address}: {e}")
            return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout getting token info for {token_address}")
            return None
        except Exception as e:
            logger.error(f"Token info error for {token_address}: {type(e).__name__}: {e}", exc_info=True)
            return None
    
    async def calculate_metrics(self, token_address: str, network: str) -> Optional[TokenMetrics]:
        """IMPROVEMENT #3: Return invalid metrics instead of simulated data"""
        token_info = await self.get_token_info(token_address, network)
        if not token_info:
            return None
        
        # Get market data with quality info
        market_data, market_quality = await self.market_data.get_token_price_data(token_address, network)
        
        # Get holder count with quality info
        holder_count, holder_quality = await self.market_data.get_holder_count(
            token_address, network, self.explorer_api_key
        )
        
        # IMPROVEMENT #3: NO SIMULATED DATA - return invalid metrics instead
        if market_data is None:
            logger.error(f"⚠ No market data for {token_info['symbol']} - marking as INVALID")
            return TokenMetrics(
                address=token_address,
                symbol=token_info['symbol'],
                name=token_info['name'],
                network=network,
                price_usd=0.0,
                price_native=0.0,
                liquidity_usd=0.0,
                volume_24h=0.0,
                price_change_1h=0.0,
                price_change_24h=0.0,
                price_change_7d=0.0,
                holders=0,
                market_cap=None,
                decimals=token_info['decimals'],
                total_supply=token_info['total_supply'],
                data_quality=DataQuality.UNKNOWN,
                valid=False,
                failure_reason="market_data_unavailable"
            )
        
        # Determine overall data quality
        data_quality = market_quality
        
        # Use real holder count if available, otherwise mark as partial
        if holder_count is not None:
            holders = holder_count
            logger.debug(f"Real holder count: {holders}")
        else:
            # IMPROVEMENT #3: Don't estimate - mark as partial instead
            holders = 0
            logger.warning(f"⚠ No holder data for {token_info['symbol']} - marking as PARTIAL")
            if data_quality == DataQuality.REAL:
                data_quality = DataQuality.PARTIAL
        
        return TokenMetrics(
            address=token_address,
            symbol=token_info['symbol'],
            name=token_info['name'],
            network=network,
            price_usd=market_data['price_usd'],
            price_native=market_data['price_native'],
            liquidity_usd=market_data['liquidity_usd'],
            volume_24h=market_data['volume_24h'],
            price_change_1h=0.0,
            price_change_24h=market_data['price_change_24h'],
            price_change_7d=0.0,
            holders=holders,
            market_cap=market_data['price_usd'] * token_info['total_supply'] / (10 ** token_info['decimals']) if market_data['price_usd'] > 0 else None,
            decimals=token_info['decimals'],
            total_supply=token_info['total_supply'],
            data_quality=data_quality,
            valid=True,
            failure_reason=None
        )


class BaseSentimentEngine:
    """IMPROVEMENT #7: Abstract provider interface for multi-model support"""
    
    async def analyze_token(self, metrics: TokenMetrics) -> SentimentAnalysis:
        """Analyze token and return sentiment analysis"""
        raise NotImplementedError
    
    async def extract_insight(self, metrics: TokenMetrics) -> Optional[AIInsight]:
        """IMPROVEMENT #2: Extract AI insight only (no scoring)"""
        raise NotImplementedError


class SentimentEngine(BaseSentimentEngine):
    """IMPROVEMENT #2 & #7: AI extracts insight, code calculates scores"""
    
    def __init__(self, api_key: Optional[str] = None):
        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
        else:
            self.client = None
            logger.warning("⚠ No Anthropic API key provided - using heuristic analysis only")
        
        # IMPROVEMENT #6: Track AI performance metrics
        self.ai_stats = {
            'ai_calls': 0,
            'fallback_count': 0,
            'parse_failures': 0,
            'timeout_count': 0
        }
    
    async def analyze_token(self, metrics: TokenMetrics) -> SentimentAnalysis:
        """IMPROVEMENT #1 & #3: Check validity, short-circuit invalid metrics"""
        # IMPROVEMENT #3: Reject invalid metrics immediately
        if not metrics.valid:
            logger.error(f"Cannot analyze invalid metrics for {metrics.symbol}: {metrics.failure_reason}")
            return self._create_invalid_analysis(metrics, metrics.failure_reason)
        
        # Calculate risk metrics (code-based, deterministic)
        rugpull = self._calc_rugpull(metrics)
        honeypot = self._calc_honeypot(metrics)
        whale = self._calc_whale(metrics)
        
        # IMPROVEMENT #2: Extract AI insight (sentiment only, not scores)
        ai_insight = None
        ai_powered = False
        if self.client:
            ai_insight = await self.extract_insight(metrics)
            if ai_insight:
                ai_powered = True
            else:
                logger.warning(f"AI insight failed for {metrics.symbol}, using heuristic")
                self.ai_stats['fallback_count'] += 1
        
        # IMPROVEMENT #2: Code calculates score, risk, recommendation (not AI)
        score, risk = self._calculate_score_and_risk(metrics, rugpull, honeypot, whale)
        sentiment = self._map_sentiment(ai_insight.sentiment_label if ai_insight else None, score)
        recommendation = self._map_recommendation(score, risk)
        
        # Build technical signals
        ratio = metrics.volume_24h / max(metrics.liquidity_usd, 1)
        technical_signals = [
            f"Volume/Liquidity: {ratio:.2%}",
            f"Market cap: ${metrics.market_cap:,.0f}" if metrics.market_cap else "Market cap: N/A",
            f"Data quality: {metrics.data_quality.value}"
        ]
        
        # IMPROVEMENT #1: Determine validity
        validity = self._determine_validity(metrics, ai_powered)
        confidence = self._adjust_confidence(ai_insight.confidence if ai_insight else "medium", metrics.data_quality, validity)
        
        # Build key factors (code + AI insights)
        key_factors = [
            f"24h change: {metrics.price_change_24h:+.2f}%",
            f"Liquidity: ${metrics.liquidity_usd:,.0f}",
            f"Holders: {metrics.holders:,}" if metrics.holders > 0 else "Holders: unknown",
            f"Volume/Liquidity: {ratio:.2%}"
        ]
        
        if ai_insight and ai_insight.key_factors:
            key_factors.extend(ai_insight.key_factors[:2])  # Add top 2 AI insights
        
        summary = ai_insight.rationale if ai_insight else self._generate_summary(metrics, sentiment, risk)
        
        return SentimentAnalysis(
            token_address=metrics.address,
            symbol=metrics.symbol,
            network=metrics.network,
            overall_score=score,
            sentiment=sentiment,
            confidence=confidence,
            risk_level=risk,
            key_factors=key_factors,
            technical_signals=technical_signals,
            recommendation=recommendation,
            summary=summary,
            social_score=score,  # Social score mirrors overall for now
            rugpull_risk=rugpull,
            honeypot_risk=honeypot,
            whale_concentration=whale,
            data_quality=metrics.data_quality,
            validity=validity,
            ai_powered=ai_powered,
            ai_insight=ai_insight
        )
    
    def _create_invalid_analysis(self, metrics: TokenMetrics, reason: str) -> SentimentAnalysis:
        """Create analysis for invalid metrics"""
        return SentimentAnalysis(
            token_address=metrics.address,
            symbol=metrics.symbol,
            network=metrics.network,
            overall_score=0,
            sentiment=Sentiment.NEUTRAL,
            confidence="none",
            risk_level=RiskLevel.CRITICAL,
            key_factors=[f"Analysis failed: {reason}"],
            technical_signals=["Invalid metrics"],
            recommendation="no_action",
            summary=f"Cannot analyze {metrics.symbol}: {reason}",
            social_score=None,
            rugpull_risk=1.0,
            honeypot_risk=1.0,
            whale_concentration=1.0,
            data_quality=metrics.data_quality,
            validity=AnalysisValidity.INVALID,
            ai_powered=False,
            ai_insight=None
        )
    
    def _determine_validity(self, metrics: TokenMetrics, ai_powered: bool) -> AnalysisValidity:
        """IMPROVEMENT #1: Explicit validity determination"""
        if not metrics.valid or metrics.data_quality == DataQuality.UNKNOWN:
            return AnalysisValidity.INVALID
        elif metrics.data_quality in (DataQuality.SIMULATED, DataQuality.PARTIAL):
            return AnalysisValidity.DEGRADED
        else:
            return AnalysisValidity.VALID
    
    def _adjust_confidence(self, base_confidence: str, data_quality: DataQuality, validity: AnalysisValidity) -> str:
        """Adjust confidence based on validity"""
        if validity == AnalysisValidity.INVALID:
            return "none"
        elif validity == AnalysisValidity.DEGRADED:
            return "low"
        elif data_quality == DataQuality.PARTIAL:
            return "medium" if base_confidence == "high" else base_confidence
        return base_confidence
    
    def _calculate_score_and_risk(
        self,
        m: TokenMetrics,
        rugpull: float,
        honeypot: float,
        whale: float
    ) -> Tuple[int, RiskLevel]:
        """IMPROVEMENT #2: Code-based scoring (deterministic, auditable)"""
        score = 50  # Neutral baseline
        
        # Price momentum
        if m.price_change_24h > 20: score += 25
        elif m.price_change_24h > 10: score += 15
        elif m.price_change_24h < -20: score -= 25
        elif m.price_change_24h < -10: score -= 15
        
        # Liquidity scoring
        if m.liquidity_usd > 1000000: score += 20
        elif m.liquidity_usd > 500000: score += 15
        elif m.liquidity_usd > 100000: score += 5
        elif m.liquidity_usd < 50000: score -= 20
        
        # Volume/Liquidity ratio
        ratio = m.volume_24h / max(m.liquidity_usd, 1)
        if ratio > 1.0: score += 15
        elif ratio > 0.5: score += 10
        elif ratio < 0.01: score -= 10
        
        # Holder count
        if m.holders > 10000: score += 10
        elif m.holders > 5000: score += 5
        elif m.holders > 0 and m.holders < 100: score -= 15
        elif m.holders > 0 and m.holders < 500: score -= 10
        
        score = max(0, min(100, score))
        
        # Determine risk (code-based)
        risk = RiskLevel.MEDIUM
        if rugpull > 0.7 or honeypot > 0.7 or whale > 0.8:
            risk = RiskLevel.CRITICAL
        elif m.liquidity_usd > 1000000 and m.holders > 5000 and rugpull < 0.3:
            risk = RiskLevel.LOW
        elif rugpull > 0.5 or honeypot > 0.5 or m.liquidity_usd < 50000:
            risk = RiskLevel.HIGH
        
        return score, risk
    
    def _map_sentiment(self, ai_sentiment: Optional[str], score: int) -> Sentiment:
        """Map AI sentiment or score to sentiment enum"""
        if ai_sentiment:
            sentiment_map = {
                'bullish': Sentiment.BULLISH,
                'bearish': Sentiment.BEARISH,
                'neutral': Sentiment.NEUTRAL
            }
            return sentiment_map.get(ai_sentiment.lower(), Sentiment.NEUTRAL)
        
        # Fallback to score-based
        if score > 60:
            return Sentiment.BULLISH
        elif score < 40:
            return Sentiment.BEARISH
        return Sentiment.NEUTRAL
    
    def _map_recommendation(self, score: int, risk: RiskLevel) -> str:
        """IMPROVEMENT #5: Neutral signal language (no BUY/SELL)"""
        if risk == RiskLevel.CRITICAL:
            return "avoid"
        elif score > 75 and risk == RiskLevel.LOW:
            return "positive_bias"
        elif score > 60:
            return "lean_positive"
        elif score < 25:
            return "negative_bias"
        elif score < 40:
            return "lean_negative"
        else:
            return "neutral"
    
    def _generate_summary(self, m: TokenMetrics, sentiment: Sentiment, risk: RiskLevel) -> str:
        """Generate summary without AI"""
        return f"{m.symbol} shows {sentiment.value} sentiment with {risk.value} risk profile (deterministic analysis)"
    
    async def extract_insight(self, metrics: TokenMetrics) -> Optional[AIInsight]:
        """IMPROVEMENT #2: AI extracts sentiment/rationale only (no scoring)"""
        self.ai_stats['ai_calls'] += 1
        
        prompt = f"""Analyze cryptocurrency token sentiment. Respond with ONLY JSON:

Token: {metrics.name} ({metrics.symbol}) on {metrics.network}
Price: ${metrics.price_usd:.6f}
24h Change: {metrics.price_change_24h:+.2f}%
Liquidity: ${metrics.liquidity_usd:,.0f}
Volume 24h: ${metrics.volume_24h:,.0f}
Holders: {metrics.holders:,}

Return ONLY this JSON (no markdown, no explanation):
{{"sentiment":"<bullish|neutral|bearish>","confidence":"<high|medium|low>","key_factors":["factor1","factor2"],"rationale":"<1 sentence summary>"}}"""
        
        try:
            message = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.messages.create,
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,  # Reduced - we need less
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=20  # Tighter timeout
            )
            
            text = message.content[0].text.strip()
            
            # Multi-strategy JSON extraction
            parsed = self._parse_json_response(text)
            
            if parsed and self._validate_insight(parsed):
                return AIInsight(
                    sentiment_label=parsed['sentiment'],
                    key_factors=parsed.get('key_factors', []),
                    rationale=parsed.get('rationale', ''),
                    confidence=parsed.get('confidence', 'medium')
                )
            else:
                logger.warning(f"AI insight validation failed for {metrics.symbol}")
                self.ai_stats['parse_failures'] += 1
                return None
            
        except asyncio.TimeoutError:
            logger.error(f"AI insight timeout for {metrics.symbol}")
            self.ai_stats['timeout_count'] += 1
            return None
        except Exception as e:
            logger.error(f"AI insight error for {metrics.symbol}: {type(e).__name__}: {e}")
            self.ai_stats['parse_failures'] += 1
            return None
    
    def _parse_json_response(self, text: str) -> Optional[Dict]:
        """Parse JSON with multiple strategies"""
        # Strategy 1: Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract first {...}
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Remove markdown
        cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _validate_insight(self, response: Dict) -> bool:
        """Validate AI insight structure"""
        required = ['sentiment', 'confidence', 'rationale']
        if not all(f in response for f in required):
            return False
        
        if response['sentiment'] not in ['bullish', 'neutral', 'bearish']:
            return False
        if response['confidence'] not in ['high', 'medium', 'low']:
            return False
        
        return True
    
    def get_ai_stats(self) -> Dict[str, Any]:
        """IMPROVEMENT #6: Expose AI performance metrics"""
        total_calls = self.ai_stats['ai_calls']
        if total_calls == 0:
            return {
                'ai_calls': 0,
                'fallback_rate': '0%',
                'parse_failure_rate': '0%',
                'timeout_rate': '0%'
            }

        return {
            'ai_calls': total_calls,
            'fallback_rate': f"{(self.ai_stats['fallback_count'] / total_calls * 100):.1f}%",
            'parse_failure_rate': f"{(self.ai_stats['parse_failures'] / total_calls * 100):.1f}%",
            'timeout_rate': f"{(self.ai_stats['timeout_count'] / total_calls * 100):.1f}%"
        }

    def _calc_rugpull(self, m: TokenMetrics) -> float:
        """Enhanced rugpull calculation"""
        r = 0.0
        if m.liquidity_usd < 50000: r += 0.3
        elif m.liquidity_usd < 100000: r += 0.15
        if m.holders < 100: r += 0.4
        elif m.holders < 500: r += 0.2
        if abs(m.price_change_24h) > 50: r += 0.3
        elif abs(m.price_change_24h) > 30: r += 0.2

        # Adjust for data quality
        if m.data_quality == DataQuality.SIMULATED:
            r = min(r + 0.2, 1.0)  # Increase risk for simulated data

        return min(r, 1.0)

    def _calc_honeypot(self, m: TokenMetrics) -> float:
        """Enhanced honeypot detection"""
        r = 0.0
        ratio = m.volume_24h / max(m.liquidity_usd, 1)
        if ratio < 0.01: r += 0.5
        if m.price_change_24h > 100: r += 0.3

        # Very low holder count is suspicious
        if m.holders < 50: r += 0.3

        return min(r, 1.0)

    def _calc_whale(self, m: TokenMetrics) -> float:
        """Enhanced whale concentration estimation"""
        if m.holders < 50: return 0.9
        elif m.holders < 100: return 0.8
        elif m.holders < 500: return 0.6
        elif m.holders < 1000: return 0.4
        elif m.holders < 5000: return 0.2
        return 0.1
    
    async def _get_ai_analysis(self, m: TokenMetrics) -> Optional[Dict]:
        """AI analysis with improved JSON extraction and validation"""
        data_quality_note = ""
        if m.data_quality == DataQuality.SIMULATED:
            data_quality_note = "\n⚠ WARNING: Market data is simulated/estimated."
        elif m.data_quality == DataQuality.PARTIAL:
            data_quality_note = "\n⚠ NOTE: Some market data fields are missing."
        
        prompt = f"""Analyze cryptocurrency token. Respond with ONLY a single-line minified JSON object, no markdown, no explanation.

Token: {m.name} ({m.symbol}) on {m.network}
Price: ${m.price_usd:.6f}
24h Change: {m.price_change_24h:+.2f}%
Liquidity: ${m.liquidity_usd:,.0f}
Volume 24h: ${m.volume_24h:,.0f}
Holders: {m.holders:,}{data_quality_note}

{{"overall_score":<0-100>,"sentiment":"<bullish|neutral|bearish>","confidence":"<high|medium|low>","risk_level":"<low|medium|high|critical>","key_factors":["factor1","factor2","factor3"],"technical_signals":["signal1","signal2"],"recommendation":"<strong_buy|buy|hold|sell|strong_sell>","summary":"<brief analysis>","social_score":<0-100>}}"""
        
        try:
            message = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.messages.create,
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=30
            )
            
            text = message.content[0].text.strip()
            
            # Multi-strategy JSON extraction
            parsed = None
            
            # Strategy 1: Direct parse
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
            
            # Strategy 2: Extract first {...}
            if not parsed:
                match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass
            
            # Strategy 3: Remove markdown
            if not parsed:
                cleaned = re.sub(r'```json\s*|\s*```', '', text).strip()
                try:
                    parsed = json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
            
            # Validate parsed result
            if parsed and self._validate_ai_response(parsed):
                return parsed
            else:
                logger.warning(f"AI response validation failed for {m.symbol}")
                return None
            
        except asyncio.TimeoutError:
            logger.error(f"AI analysis timeout for {m.symbol}")
            return None
        except Exception as e:
            logger.error(f"AI analysis error for {m.symbol}: {type(e).__name__}: {e}", exc_info=True)
            return None
    
    def _validate_ai_response(self, response: Dict) -> bool:
        """Validate AI response has required fields and correct types"""
        required_fields = {
            'overall_score': int,
            'sentiment': str,
            'confidence': str,
            'risk_level': str,
            'key_factors': list,
            'technical_signals': list,
            'recommendation': str,
            'summary': str
        }
        
        for field, expected_type in required_fields.items():
            if field not in response:
                logger.debug(f"Missing field: {field}")
                return False
            if not isinstance(response[field], expected_type):
                logger.debug(f"Invalid type for {field}: {type(response[field])}")
                return False
        
        # Validate enum values
        if response['sentiment'] not in ['bullish', 'neutral', 'bearish']:
            return False
        if response['risk_level'] not in ['low', 'medium', 'high', 'critical']:
            return False
        if not 0 <= response['overall_score'] <= 100:
            return False
        
        return True
    
    def _get_basic_analysis(self, m: TokenMetrics) -> Dict:
        """Enhanced heuristic fallback analysis"""
        score, sent, risk = 50, "neutral", "medium"
        
        # Price momentum
        if m.price_change_24h > 20: score += 25; sent = "bullish"
        elif m.price_change_24h > 10: score += 15; sent = "bullish"
        elif m.price_change_24h < -20: score -= 25; sent = "bearish"
        elif m.price_change_24h < -10: score -= 15; sent = "bearish"
        
        # Liquidity scoring
        if m.liquidity_usd > 1000000: score += 20; risk = "low"
        elif m.liquidity_usd > 500000: score += 15; risk = "low"
        elif m.liquidity_usd > 100000: score += 5
        elif m.liquidity_usd < 50000: score -= 20; risk = "high"
        
        # Volume/Liquidity ratio
        ratio = m.volume_24h / max(m.liquidity_usd, 1)
        if ratio > 1.0: score += 15  # High activity
        elif ratio > 0.5: score += 10
        elif ratio < 0.01: risk = "high"; score -= 10
        
        # Holder count
        if m.holders > 10000: score += 10
        elif m.holders > 5000: score += 5
        elif m.holders < 100: risk = "critical"; score -= 15
        elif m.holders < 500: risk = "high"; score -= 10
        
        # Adjust for data quality
        if m.data_quality == DataQuality.SIMULATED:
            risk = "high" if risk == "medium" else risk
            risk = "critical" if risk == "low" else risk
        
        score = max(0, min(100, score))
        
        return {
            'overall_score': score,
            'sentiment': sent,
            'confidence': 'medium',
            'risk_level': risk,
            'key_factors': [
                f"24h change: {m.price_change_24h:+.2f}%",
                f"Liquidity: ${m.liquidity_usd:,.0f}",
                f"Holders: {m.holders:,}",
                f"Volume/Liquidity: {ratio:.2%}"
            ],
            'technical_signals': [
                f"Market cap: ${m.market_cap:,.0f}" if m.market_cap else "Market cap: N/A",
                f"Data quality: {m.data_quality.value}"
            ],
            'recommendation': 'hold' if 40 <= score <= 60 else 'buy' if score > 60 else 'sell',
            'summary': f"{m.symbol} shows {sent} sentiment with {risk} risk profile (heuristic analysis)",
            'social_score': score
        }


class AlertManager:
    """Enhanced alert manager with rate limiting"""
    
    def __init__(self):
        self.webhook_url: Optional[str] = None
        self.alert_history: List[Tuple[str, float]] = []  # (alert_key, timestamp)
        self.rate_limit_window = 60  # seconds
        self.max_alerts_per_window = 10
    
    def set_webhook(self, url: str):
        """Set webhook with validation"""
        valid_prefixes = (
            'https://discord.com/api/webhooks/',
            'https://hooks.slack.com/',
            'https://discordapp.com/api/webhooks/'
        )
        if not url.startswith(valid_prefixes):
            logger.warning(f"⚠ Webhook URL may not be valid. Expected Discord or Slack webhook.")
        self.webhook_url = url
        logger.info(f"✓ Webhook configured: {url[:50]}...")
    
    def _should_rate_limit(self, alert_key: str) -> bool:
        """Check if alert should be rate limited"""
        now = time.time()
        
        # Clean old entries
        self.alert_history = [(k, t) for k, t in self.alert_history if now - t < self.rate_limit_window]
        
        # Check rate limit
        recent_alerts = len(self.alert_history)
        if recent_alerts >= self.max_alerts_per_window:
            logger.warning(f"⚠ Rate limit hit: {recent_alerts} alerts in {self.rate_limit_window}s")
            return True
        
        # Check duplicate alert
        duplicate_count = sum(1 for k, t in self.alert_history if k == alert_key and now - t < 300)
        if duplicate_count >= 3:
            logger.debug(f"Suppressing duplicate alert: {alert_key}")
            return True
        
        return False
    
    async def send_alert(
        self,
        title: str,
        msg: str,
        severity: str = "info",
        analysis: Optional[SentimentAnalysis] = None
    ):
        """IMPROVEMENT #5: Compliance-safe neutral signal language"""
        log_map = {
            'critical': logger.critical,
            'warning': logger.warning,
            'info': logger.info
        }
        log_map.get(severity, logger.info)(f"{title}: {msg}")
        
        if self.webhook_url and analysis:
            alert_key = f"{analysis.token_address}:{severity}"
            
            # Rate limit check
            if self._should_rate_limit(alert_key):
                return
            
            try:
                async with aiohttp.ClientSession() as sess:
                    color = {
                        'critical': 16711680,  # Red
                        'warning': 16776960,   # Yellow
                        'info': 65280          # Green
                    }.get(severity, 8421504)
                    
                    # Add data quality and validity indicators
                    quality_emoji = {
                        DataQuality.REAL: "✅",
                        DataQuality.PARTIAL: "⚠️",
                        DataQuality.SIMULATED: "🔶",
                        DataQuality.UNKNOWN: "❓"
                    }.get(analysis.data_quality, "")
                    
                    validity_emoji = {
                        AnalysisValidity.VALID: "✅",
                        AnalysisValidity.DEGRADED: "⚠️",
                        AnalysisValidity.INVALID: "❌"
                    }.get(analysis.validity, "")
                    
                    # IMPROVEMENT #5: Neutral signal language (no BUY/SELL)
                    recommendation_display = {
                        'positive_bias': 'Positive Bias',
                        'lean_positive': 'Lean Positive',
                        'neutral': 'Neutral',
                        'lean_negative': 'Lean Negative',
                        'negative_bias': 'Negative Bias',
                        'avoid': 'Structural Risk - Avoid',
                        'no_action': 'No Action'
                    }.get(analysis.recommendation, analysis.recommendation.upper())
                    
                    fields = [
                        {"name": "Sentiment", "value": analysis.sentiment.value.upper(), "inline": True},
                        {"name": "Score", "value": f"{analysis.overall_score}/100", "inline": True},
                        {"name": "Risk", "value": analysis.risk_level.value.upper(), "inline": True},
                        {"name": "Structural Risk", "value": f"{analysis.rugpull_risk:.1%}", "inline": True},
                        {"name": "Signal", "value": recommendation_display, "inline": True},
                        {"name": "Validity", "value": f"{validity_emoji} {analysis.validity.value}", "inline": True}
                    ]
                    
                    if not analysis.ai_powered:
                        fields.append({"name": "Analysis Type", "value": "🔧 Deterministic (AI unavailable)", "inline": False})
                    
                    payload = {
                        "content": f"**{title}**\n{msg}",
                        "embeds": [{
                            "title": f"{analysis.symbol} on {analysis.network}",
                            "description": analysis.summary,
                            "color": color,
                            "fields": fields,
                            "timestamp": datetime.utcnow().isoformat()
                        }]
                    }
                    
                    async with sess.post(self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status != 204:
                            logger.warning(f"Webhook returned status {resp.status}")
                        else:
                            logger.debug("✓ Alert sent")
                            self.alert_history.append((alert_key, time.time()))
            except asyncio.TimeoutError:
                logger.error("Webhook timeout")
            except Exception as e:
                logger.error(f"Webhook failed: {type(e).__name__}: {e}")


class MonitoringTask:
    """IMPROVEMENT #4: Complete stateful alert gating (no spam anywhere)"""
    
    def __init__(
        self,
        scanner: 'SentimentScanner',
        token_address: str,
        network: str,
        interval: int,
        thresholds: Dict
    ):
        self.scanner = scanner
        self.token_address = token_address
        self.network = network
        self.interval = interval
        self.thresholds = thresholds
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.error_count = 0
        self.max_errors = 5
        
        # IMPROVEMENT #4: Complete state tracking for ALL alert types
        self.last_alert_state = {
            "risk": None,          # Critical risk state
            "signal": None,        # Positive/negative bias state
            "validity": None,      # Validity state
            "last_score": None     # For sentiment shift detection
        }
    
    async def start(self):
        """Start monitoring task"""
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info(f"✓ Started monitoring {self.token_address} on {self.network}")
    
    async def stop(self):
        """Stop monitoring task"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info(f"✓ Stopped monitoring {self.token_address}")
    
    async def _monitor_loop(self):
        """IMPROVEMENT #4: Fully state-gated monitoring loop"""
        
        try:
            while self.running:
                try:
                    analysis = await asyncio.wait_for(
                        self.scanner.scan_token(self.token_address, self.network),
                        timeout=60
                    )
                    
                    if analysis:
                        self.error_count = 0
                        
                        # IMPROVEMENT #1: Alert on validity changes
                        if analysis.validity == AnalysisValidity.INVALID:
                            if self.last_alert_state["validity"] != "invalid":
                                await self.scanner.alert_manager.send_alert(
                                    "❌ ANALYSIS INVALID",
                                    f"Cannot analyze {analysis.symbol}: invalid metrics",
                                    severity='critical',
                                    analysis=analysis
                                )
                                self.last_alert_state["validity"] = "invalid"
                        elif analysis.validity == AnalysisValidity.DEGRADED:
                            if self.last_alert_state["validity"] != "degraded":
                                await self.scanner.alert_manager.send_alert(
                                    "⚠️ DEGRADED DATA QUALITY",
                                    f"Partial data for {analysis.symbol}",
                                    severity='warning',
                                    analysis=analysis
                                )
                                self.last_alert_state["validity"] = "degraded"
                        else:
                            self.last_alert_state["validity"] = "valid"
                        
                        # Skip further alerts if invalid
                        if analysis.validity == AnalysisValidity.INVALID:
                            await asyncio.sleep(self.interval)
                            continue
                        
                        # IMPROVEMENT #4: State-gated critical risk
                        if self.thresholds.get('critical_risk'):
                            if analysis.risk_level == RiskLevel.CRITICAL and self.last_alert_state["risk"] != "critical":
                                await self.scanner.alert_manager.send_alert(
                                    "🚨 CRITICAL RISK DETECTED",
                                    f"High structural risk for {analysis.symbol}",
                                    severity='critical',
                                    analysis=analysis
                                )
                                self.last_alert_state["risk"] = "critical"
                            elif analysis.risk_level != RiskLevel.CRITICAL:
                                self.last_alert_state["risk"] = None
                        
                        # IMPROVEMENT #4 & #5: State-gated signals with neutral language
                        signal = None
                        if self.thresholds.get('high_score') and analysis.overall_score > self.thresholds['high_score']:
                            signal = "positive"
                        elif self.thresholds.get('low_score') and analysis.overall_score < self.thresholds['low_score']:
                            signal = "negative"
                        
                        if signal and self.last_alert_state["signal"] != signal:
                            if signal == "positive":
                                await self.scanner.alert_manager.send_alert(
                                    "📈 POSITIVE BIAS DETECTED",
                                    f"Strong positive indicators for {analysis.symbol}",
                                    severity='info',
                                    analysis=analysis
                                )
                            else:
                                await self.scanner.alert_manager.send_alert(
                                    "📉 NEGATIVE BIAS DETECTED",
                                    f"Strong negative indicators for {analysis.symbol}",
                                    severity='warning',
                                    analysis=analysis
                                )
                            self.last_alert_state["signal"] = signal
                        elif not signal:
                            self.last_alert_state["signal"] = None
                        
                        # IMPROVEMENT #2: Configurable sentiment shift threshold
                        if self.thresholds.get('sentiment_shift') and self.last_alert_state["last_score"] is not None:
                            delta = self.thresholds.get('sentiment_shift_delta', 20)
                            score_change = abs(analysis.overall_score - self.last_alert_state["last_score"])
                            if score_change > delta:
                                await self.scanner.alert_manager.send_alert(
                                    "⚡ SENTIMENT SHIFT",
                                    f"{analysis.symbol} score changed by {score_change} points",
                                    severity='warning',
                                    analysis=analysis
                                )
                        
                        self.last_alert_state["last_score"] = analysis.overall_score
                    else:
                        self.error_count += 1
                        logger.warning(f"Scan returned None for {self.token_address} (error {self.error_count}/{self.max_errors})")
                    
                    await asyncio.sleep(self.interval)
                    
                except asyncio.CancelledError:
                    logger.info(f"Monitoring cancelled for {self.token_address}")
                    break
                except asyncio.TimeoutError:
                    self.error_count += 1
                    logger.error(f"Monitor timeout for {self.token_address} (error {self.error_count}/{self.max_errors})")
                    if self.error_count >= self.max_errors:
                        logger.critical(f"Max errors reached for {self.token_address}, stopping monitor")
                        break
                    await asyncio.sleep(self.interval)
                except Exception as e:
                    self.error_count += 1
                    logger.error(f"Monitor error for {self.token_address}: {e} (error {self.error_count}/{self.max_errors})", exc_info=True)
                    if self.error_count >= self.max_errors:
                        logger.critical(f"Max errors reached for {self.token_address}, stopping monitor")
                        break
                    await asyncio.sleep(self.interval)
        finally:
            self.running = False


class SentimentScanner:
    """Enhanced main orchestrator with better diagnostics"""

    REQUIRED_CONFIG_KEYS = [
        'max_concurrent', 'log_level'
    ]

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        config_path: Optional[str] = None,
        explorer_api_key: Optional[str] = None,
        max_concurrent: int = 10,
        log_level: str = "INFO",
        config: Optional[Dict] = None  # 🔒 FIX: Accept config parameter for constructor normalization
    ):
        # 🔒 FIX: Handle config parameter from ScanDirector
        if config:
            max_concurrent = config.get('max_concurrent', max_concurrent)
            log_level = config.get('log_level', log_level)
            # Extract other possible config params
            anthropic_api_key = config.get('anthropic_api_key', anthropic_api_key)
            config_path = config.get('config_path', config_path)
            explorer_api_key = config.get('explorer_api_key', explorer_api_key)
        
        # ✅ IMMEDIATE FIX: Add startup configuration validation
        config = {
            'max_concurrent': max_concurrent,
            'log_level': log_level
        }

        missing_keys = [key for key in self.REQUIRED_CONFIG_KEYS if key not in config or config[key] is None]
        if missing_keys:
            raise ValueError(f"SentimentScanner missing required config keys: {missing_keys}")

        if config['max_concurrent'] <= 0:
            raise ValueError(f"max_concurrent must be > 0, got {config['max_concurrent']}")

        # Set log level
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # Load API keys from environment if not provided
        self.anthropic_key = anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')
        self.explorer_key = explorer_api_key or os.getenv('EXPLORER_API_KEY')

        # Warn about missing keys
        if not self.anthropic_key:
            logger.warning("⚠ ANTHROPIC_API_KEY not set - AI analysis will be unavailable")
        if not self.explorer_key:
            logger.warning("⚠ EXPLORER_API_KEY not set - real holder counts will be unavailable")

        self.network_manager = NetworkManager(config_path)
        self.rpc_manager = RPCManager()
        self.market_data: Optional[MarketDataProvider] = None
        self.token_analyzer: Optional[TokenAnalyzer] = None

        # FIX #6: Use base interface for sentiment engine
        self.sentiment_engine: BaseSentimentEngine = SentimentEngine(self.anthropic_key)

        self.alert_manager = AlertManager()
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Monitoring tasks
        self.monitoring_tasks: Dict[str, MonitoringTask] = {}

        # IMPROVEMENT #1 & #3: Track graded success metrics
        self.scan_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.degraded_count = 0  # Partial/simulated data
        self.invalid_count = 0  # Invalid metrics (no market data)

        # ✅ IMMEDIATE FIX: Add memory usage monitoring
        # TODO: Implement MemoryMonitor class
        # self.memory_monitor = MemoryMonitor()
        # self.memory_monitor.start()
    
    async def initialize(self) -> None:
        """Initialize scanner components"""
        logger.info("="*80)
        logger.info("Elite Sentiment Scanner v2.1 - Initializing...")
        logger.info("="*80)
        
        await self.network_manager.initialize()
        
        if self.network_manager.session:
            self.market_data = MarketDataProvider(self.network_manager.session)
            self.token_analyzer = TokenAnalyzer(
                self.network_manager,
                self.market_data,
                self.rpc_manager,
                self.explorer_key
            )
        
        logger.info("="*80)
        logger.info("✓ Scanner ready for operation")
        logger.info("="*80)
    
    async def scan_token(
        self,
        token_address: str,
        network: str = 'ethereum'
    ) -> Optional[SentimentAnalysis]:
        """Scan single token with FIX #4: timeout outside semaphore (Python 3.11+ compatible)"""
        self.scan_count += 1

        # ✅ IMMEDIATE FIX: Global error boundary
        try:
            # FIX #4: Timeout wraps the entire operation, not nested inside semaphore
            # Note: asyncio.timeout() requires Python 3.11+
            # For Python <3.11, use: async with asyncio.wait_for(..., timeout=90)
            async with asyncio.timeout(90):
                async with self.semaphore:
                    logger.info(f"[{self.scan_count}] Scanning {token_address} on {network}")

                    metrics = await self.token_analyzer.calculate_metrics(token_address, network)

                    if not metrics:
                        logger.error(f"✗ Failed to get metrics for {token_address}")
                        self.failure_count += 1
                        return None

                    analysis = await self.sentiment_engine.analyze_token(metrics)

                    self.success_count += 1

                    # IMPROVEMENT #1 & #3: Track validity levels
                    if analysis.validity == AnalysisValidity.INVALID:
                        self.invalid_count += 1
                    elif analysis.validity == AnalysisValidity.DEGRADED:
                        self.degraded_count += 1

                    # Enhanced logging with data quality
                    quality_indicator = {
                        DataQuality.REAL: "✅",
                        DataQuality.PARTIAL: "⚠️",
                        DataQuality.SIMULATED: "🔶",
                        DataQuality.UNKNOWN: "❓"
                    }.get(analysis.data_quality, "")

                    ai_indicator = "🤖" if analysis.ai_powered else "🔧"

                    logger.info(
                        f"✓ {analysis.symbol}: {analysis.sentiment.value.upper()} "
                        f"(Score: {analysis.overall_score}/100, Risk: {analysis.risk_level.value.upper()}) "
                        f"{quality_indicator}{ai_indicator}"
                    )

                    return analysis

        except asyncio.TimeoutError:
            logger.error(f"✗ Timeout scanning {token_address}")
            self.failure_count += 1
            return None
        except Exception as e:
            # ✅ IMMEDIATE FIX: Global error boundary - catch all exceptions
            logger.error(f"✗ CRITICAL: Scan error for {token_address}: {type(e).__name__}: {e}", exc_info=True)
            self.failure_count += 1
            # Return None instead of crashing the entire scanner
            return None
    
    async def scan(self, chain: str = None, **kwargs) -> List[Dict]:
        """
        Scan method compatible with ScanDirector
        Returns empty list as sentiment scanner doesn't produce token candidates
        """
        logger.info(f"SentimentScanner scan called for chain: {chain}")
        return []
    
    async def protected_scan(self, chain: str = None, **kwargs) -> List[Dict]:
        """
        Protected scan method with circuit breaker compatibility
        """
        try:
            return await self.scan(chain, **kwargs)
        except Exception as e:
            logger.error(f"SentimentScanner protected_scan failed: {e}")
            return []
    
    async def scan_multiple(
        self,
        tokens: List[Tuple[str, str]]
    ) -> List[SentimentAnalysis]:
        """Batch scan with detailed per-token logging"""
        logger.info(f"Starting batch scan of {len(tokens)} tokens")
        start_time = time.time()
        
        tasks = [self.scan_token(addr, net) for addr, net in tokens]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = [r for r in results if isinstance(r, SentimentAnalysis)]
        failed = len(results) - len(successful)
        elapsed = time.time() - start_time
        
        # Log failures with details
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                addr, net = tokens[i]
                logger.error(f"Token {addr} on {net} failed: {result}")
        
        logger.info(
            f"Batch scan complete: {len(successful)} successful, {failed} failed "
            f"({elapsed:.2f}s, {len(tokens)/elapsed:.2f} tokens/sec)"
        )
        
        return successful
    
    async def start_monitoring(
        self,
        token_address: str,
        network: str,
        interval: int = 60,
        alert_thresholds: Optional[Dict] = None
    ) -> str:
        """Start monitoring token with per-token thresholds"""
        task_id = f"{network}:{token_address}"
        
        if task_id in self.monitoring_tasks:
            logger.warning(f"Already monitoring {token_address} on {network}")
            return task_id
        
        thresholds = alert_thresholds or {
            'critical_risk': True,
            'high_score': 75,  # Alert on score > 75
            'low_score': 25,   # Alert on score < 25
            'sentiment_shift': True,  # Alert on large sentiment changes
            'sentiment_shift_delta': 20  # FIX #2: Configurable threshold (no hardcode)
        }
        
        task = MonitoringTask(self, token_address, network, interval, thresholds)
        await task.start()
        self.monitoring_tasks[task_id] = task
        
        return task_id
    
    async def stop_monitoring(self, task_id: str):
        """Stop specific monitoring task"""
        if task_id in self.monitoring_tasks:
            await self.monitoring_tasks[task_id].stop()
            del self.monitoring_tasks[task_id]
            logger.info(f"✓ Stopped monitoring: {task_id}")
        else:
            logger.warning(f"Task not found: {task_id}")
    
    async def stop_all_monitoring(self):
        """Stop all monitoring tasks"""
        if not self.monitoring_tasks:
            logger.info("No active monitoring tasks")
            return
        
        logger.info(f"Stopping {len(self.monitoring_tasks)} monitoring tasks")
        tasks = [task.stop() for task in self.monitoring_tasks.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.monitoring_tasks.clear()
        logger.info("✓ All monitoring tasks stopped")
    
    def get_monitoring_status(self) -> Dict[str, Dict]:
        """Get detailed status of all monitoring tasks"""
        return {
            task_id: {
                'running': task.running,
                'interval': task.interval,
                'error_count': task.error_count,
                'token': task.token_address,
                'network': task.network
            }
            for task_id, task in self.monitoring_tasks.items()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """IMPROVEMENT #6: Include AI evaluation metrics"""
        cache_stats = self.market_data.cache.get_stats() if self.market_data else {}
        ai_stats = self.sentiment_engine.get_ai_stats() if hasattr(self.sentiment_engine, 'get_ai_stats') else {}
        
        return {
            'total_scans': self.scan_count,
            'successful_scans': self.success_count,
            'failed_scans': self.failure_count,
            'degraded_scans': self.degraded_count,
            'invalid_scans': self.invalid_count,  # NEW
            'success_rate': f"{(self.success_count / max(self.scan_count, 1) * 100):.1f}%",
            'data_quality_rate': f"{((self.success_count - self.degraded_count) / max(self.success_count, 1) * 100):.1f}%",
            'active_monitors': len(self.monitoring_tasks),
            'cache_stats': cache_stats,
            'ai_stats': ai_stats  # IMPROVEMENT #6
        }
    
    async def cleanup(self):
        """Cleanup all resources"""
        logger.info("="*80)
        logger.info("Shutting down scanner...")
        logger.info("="*80)

        await self.stop_all_monitoring()
        await self.network_manager.close()

        # ✅ IMMEDIATE FIX: Stop memory monitor
        if hasattr(self, 'memory_monitor'):
            self.memory_monitor.stop()

        # Print final statistics
        stats = self.get_statistics()
        logger.info("Final Statistics:")
        for key, value in stats.items():
            if key not in ['cache_stats', 'ai_stats']:
                logger.info(f"  {key}: {value}")

        # Print memory stats
        if hasattr(self, 'memory_monitor'):
            mem_stats = self.memory_monitor.get_memory_stats()
            logger.info("Final Memory Stats:")
            logger.info(f"  RSS: {mem_stats['rss_mb']:.1f} MB")
            logger.info(f"  VMS: {mem_stats['vms_mb']:.1f} MB")

        logger.info("="*80)
        logger.info("✓ Cleanup complete")
        logger.info("="*80)
    
    def export_analysis(
        self,
        analysis: SentimentAnalysis,
        format: str = 'json'
    ) -> str:
        """Export analysis in various formats"""
        data = asdict(analysis)
        
        # Convert enums and datetime
        data['sentiment'] = data['sentiment'].value if isinstance(data['sentiment'], Enum) else data['sentiment']
        data['risk_level'] = data['risk_level'].value if isinstance(data['risk_level'], Enum) else data['risk_level']
        data['data_quality'] = data['data_quality'].value if isinstance(data['data_quality'], Enum) else data['data_quality']
        data['validity'] = data['validity'].value if isinstance(data['validity'], Enum) else data['validity']
        data['timestamp'] = data['timestamp'].isoformat()
        
        # Handle AIInsight nested object
        if data.get('ai_insight'):
            data['ai_insight'] = asdict(data['ai_insight']) if hasattr(data['ai_insight'], '__dict__') else data['ai_insight']
        
        if format == 'json':
            return json.dumps(data, indent=2)
        elif format == 'csv':
            import csv
            import io
            # Flatten lists for CSV
            data['key_factors'] = '; '.join(data['key_factors'])
            data['technical_signals'] = '; '.join(data['technical_signals'])
            # Flatten ai_insight
            if data.get('ai_insight'):
                data.pop('ai_insight')  # Too complex for CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
            return output.getvalue()
        else:
            return str(data)
    
    async def batch_export(
        self,
        analyses: List[SentimentAnalysis],
        filename: str,
        format: str = 'json'
    ):
        """Export batch results to file with error handling"""
        try:
            if format == 'json':
                data = [json.loads(self.export_analysis(a, 'json')) for a in analyses]
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)
            
            elif format == 'csv':
                import csv
                if analyses:
                    data_list = []
                    for a in analyses:
                        data = json.loads(self.export_analysis(a, 'json'))
                        # Flatten lists
                        data['key_factors'] = '; '.join(a.key_factors) if isinstance(a.key_factors, list) else str(a.key_factors)
                        data['technical_signals'] = '; '.join(a.technical_signals) if isinstance(a.technical_signals, list) else str(a.technical_signals)
                        data_list.append(data)
                    
                    with open(filename, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=data_list[0].keys())
                        writer.writeheader()
                        writer.writerows(data_list)
            
            logger.info(f"✓ Exported {len(analyses)} analyses to {filename}")
        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)


async def main():
    """Comprehensive example usage with all improvements"""
    
    # Initialize scanner with API keys from environment
    scanner = SentimentScanner(
        anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
        explorer_api_key=os.getenv('EXPLORER_API_KEY'),
        config_path='networks.yaml',  # Optional: custom network config
        max_concurrent=5,
        log_level='INFO'  # Can be DEBUG, INFO, WARNING, ERROR
    )
    
    await scanner.initialize()
    
    # Configure webhook alerts (optional)
    webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if webhook:
        scanner.alert_manager.set_webhook(webhook)
    
    try:
        print("\n" + "="*80)
        print("ENHANCED MULTI-CHAIN SENTIMENT SCANNER v2.1 - PRODUCTION DEMO")
        print("="*80)
        
        # Example 1: Single token scan with data quality tracking
        print("\n[1] SINGLE TOKEN SCAN WITH DATA QUALITY")
        print("-" * 80)
        
        analysis = await scanner.scan_token(
            token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            network="ethereum"
        )
        
        if analysis:
            print(f"\nToken: {analysis.symbol} ({analysis.network})")
            print(f"Validity: {analysis.validity.value.upper()} ✓" if analysis.validity == AnalysisValidity.VALID else f"Validity: {analysis.validity.value.upper()} ⚠️")
            print(f"Sentiment: {analysis.sentiment.value.upper()}")
            print(f"Overall Score: {analysis.overall_score}/100")
            print(f"Confidence: {analysis.confidence.upper()}")
            print(f"Risk Level: {analysis.risk_level.value.upper()}")
            print(f"Structural Risk: {analysis.rugpull_risk:.1%}")
            print(f"Honeypot Risk: {analysis.honeypot_risk:.1%}")
            print(f"Whale Concentration: {analysis.whale_concentration:.1%}")
            print(f"Signal: {analysis.recommendation.upper()}")
            print(f"Data Quality: {analysis.data_quality.value.upper()} {'🤖' if analysis.ai_powered else '🔧'}")
            print(f"\nSummary: {analysis.summary}")
            print(f"\nKey Factors:")
            for factor in analysis.key_factors:
                print(f"  • {factor}")
            print(f"\nTechnical Signals:")
            for signal in analysis.technical_signals:
                print(f"  • {signal}")
            
            if analysis.ai_insight:
                print(f"\nAI Insight:")
                print(f"  Sentiment: {analysis.ai_insight.sentiment_label}")
                print(f"  Confidence: {analysis.ai_insight.confidence}")
                print(f"  Rationale: {analysis.ai_insight.rationale}")
        
        # Example 2: Multi-chain batch scan with error tracking
        print("\n" + "="*80)
        print("[2] MULTI-CHAIN BATCH SCAN")
        print("-" * 80)
        
        tokens = [
            ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "ethereum"),  # WETH
            ("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", "bsc"),  # WBNB
        ]
        
        results = await scanner.scan_multiple(tokens)
        
        print(f"\n{'Symbol':<10} {'Network':<12} {'Validity':<10} {'Sentiment':<10} {'Score':<8} {'Risk':<10} {'Signal':<15}")
        print("-" * 95)
        for a in results:
            validity_icon = "✓" if a.validity == AnalysisValidity.VALID else "⚠" if a.validity == AnalysisValidity.DEGRADED else "✗"
            print(f"{a.symbol:<10} {a.network:<12} {validity_icon} {a.validity.value:<8} {a.sentiment.value:<10} {a.overall_score:>3}/100  "
                  f"{a.risk_level.value:<10} {a.recommendation:<15}")
        
        # Export results
        await scanner.batch_export(results, "scan_results_v2.json", format="json")
        await scanner.batch_export(results, "scan_results_v2.csv", format="csv")
        print("\n✓ Results exported to scan_results_v2.json and scan_results_v2.csv")
        
        # Example 3: Enhanced monitoring with per-token thresholds
        print("\n" + "="*80)
        print("[3] CONTINUOUS MONITORING WITH CUSTOM THRESHOLDS")
        print("-" * 80)
        
        # Start monitoring with custom thresholds
        task1 = await scanner.start_monitoring(
            token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            network="ethereum",
            interval=300,  # 5 minutes
            alert_thresholds={
                'critical_risk': True,
                'high_score': 75,  # Alert on score > 75 (POSITIVE SENTIMENT)
                'low_score': 25,   # Alert on score < 25 (NEGATIVE SENTIMENT)
                'sentiment_shift': True,  # Alert on large sentiment changes
                'sentiment_shift_delta': 20  # FIX #2: Configurable (not hardcoded)
            }
        )
        
        print(f"✓ Started monitoring: {task1}")
        
        # Check monitoring status
        status = scanner.get_monitoring_status()
        print(f"\nActive monitoring tasks: {len(status)}")
        for task_id, task_info in status.items():
            print(f"  • {task_id}")
            print(f"    Running: {task_info['running']}")
            print(f"    Interval: {task_info['interval']}s")
            print(f"    Errors: {task_info['error_count']}")
        
        # Get scanner statistics
        print("\n" + "="*80)
        print("[4] SCANNER STATISTICS & AI EVALUATION")
        print("-" * 80)
        stats = scanner.get_statistics()
        for key, value in stats.items():
            if key == 'ai_stats':
                print("\nAI Performance Metrics:")
                for ai_key, ai_value in value.items():
                    print(f"  {ai_key}: {ai_value}")
            elif key != 'cache_stats':
                print(f"{key}: {value}")
        
        if 'cache_stats' in stats:
            print("\nCache Performance:")
            for key, value in stats['cache_stats'].items():
                print(f"  {key}: {value}")
        
        # Run for 30 seconds as demo
        print("\n" + "="*80)
        print("Monitoring for 30 seconds (press Ctrl+C to stop)...")
        print("="*80)
        await asyncio.sleep(30)
        
        # Stop monitoring
        await scanner.stop_monitoring(task1)
        print(f"\n✓ Stopped monitoring: {task1}")
        
        # Final statistics
        print("\n" + "="*80)
        print("FINAL STATISTICS")
        print("-" * 80)
        final_stats = scanner.get_statistics()
        for key, value in final_stats.items():
            if key != 'cache_stats':
                print(f"{key}: {value}")
        
    except KeyboardInterrupt:
        print("\n\nShutdown requested...")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    finally:
        await scanner.cleanup()
        print("\n✓ Scanner shutdown complete")


if __name__ == "__main__":
    # Run the enhanced scanner
    asyncio.run(main())
