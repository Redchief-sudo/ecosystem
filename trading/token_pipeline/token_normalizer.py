"""
Token Normalization Adapters
-----------------------------
Convert raw scanner data to canonical TokenCandidate format.
Each scanner needs its own adapter to handle different data schemas.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from web3 import Web3

from trading.token_pipeline.token_candidate import TokenCandidate
from trading.token_pipeline.token_enricher import TokenEnricher  # NEW: Import enricher
from networks.address_validator import address_validator
from networks.chain_normalizer import chain_normalizer
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from utils.pipeline_monitor import get_pipeline_monitor
from utils.retry_handler import RetryConfig, RetryHandler
from utils.validators import FieldValidator

logger = logging.getLogger(__name__)


class TokenNormalizer:
    """Normalizes tokens from different scanners to canonical format."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.adapters = {
            "DexScreenerScanner": self.normalize_dexscreener,
            "EliteCoinMarketCapScanner": self.normalize_cmc,
            "MempoolScannerUltra": self.normalize_mempool,
            "ArbitrageMEVScanner": self.normalize_arbitrage_mev,
            "AIDiscoveryScanner": self.normalize_ai_discovery,
            "EliteHybridScanner": self.normalize_hybrid,
            "OnChainScannerUltra": self.normalize_onchain,
            "D3Scanner": self.normalize_d3,
            "trade_engine": self.normalize_trade_engine,
            "ScannedToken": self.normalize_scanned_token,
        }
        
        # Initialize token enricher for data enrichment
        enrichment_config = self.config.get('enrichment', {})
        self.enricher = TokenEnricher(enrichment_config)

        # Initialize monitoring
        self.monitor = get_pipeline_monitor()
        self.monitor.register_component("token_normalizer")

        # Initialize circuit breaker for normalization operations
        circuit_config = CircuitBreakerConfig(
            failure_threshold=10,
            timeout=60,
            success_threshold=3,
            expected_exception=Exception,
        )
        self.circuit_breaker = CircuitBreaker(circuit_config)

        # Initialize retry handler for transient failures
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=True,
        )
        self.retry_handler = RetryHandler(retry_config)

        # Per-adapter metrics
        self.adapter_metrics = {
            adapter: {
                "total_attempts": 0,
                "successful": 0,
                "failed": 0,
                "last_error": None,
                "last_success": None,
            }
            for adapter in self.adapters.keys()
        }

    def _enrich_candidate(self, candidate: TokenCandidate) -> None:
        """
        Enrich a TokenCandidate with computed data fields for strategy evaluation.
        
        This adds historical data and estimated metrics that strategies need.
        """
        # Convert candidate to dict format for enrichment
        token_data = {
            'address': candidate.address,
            'symbol': candidate.symbol,
            'name': candidate.name,
            'price': candidate.price_usd,
            'volume_24h': candidate.volume_24h,
            'liquidity': candidate.liquidity_usd,
            'market_cap': candidate.market_cap,
            'chain': candidate.chain,
            'confidence': candidate.confidence,
            # Include any existing metadata
            **(candidate.metadata or {}),
        }
        
        # Enrich the token data
        enriched_data = self.enricher.enrich(token_data)
        
        # Update candidate metadata with enriched fields
        if candidate.metadata is None:
            candidate.metadata = {}
        
        # Add enriched fields to metadata for strategy access
        candidate.metadata['enriched_data'] = {
            'price_history': enriched_data.get('price_history', []),
            'volume_history': enriched_data.get('volume_history', []),
            'holder_concentration': enriched_data.get('holder_concentration', 0.5),
            'whale_activity': enriched_data.get('whale_activity', 0.3),
            'rugpull_risk': enriched_data.get('rugpull_risk', 0.1),
            'social_score': enriched_data.get('social_score', 0.5),
            'market_regime': enriched_data.get('market_regime', 0),
            'smart_money_flow': enriched_data.get('smart_money_flow', 0.5),
            'bids': enriched_data.get('bids', []),
            'asks': enriched_data.get('asks', []),
            'volume_profile': enriched_data.get('volume_profile', 0.5),
        }
        
        logger.debug(f"Enriched {candidate.symbol} with strategy data")

    def _safe_float(self, data: Dict, field_names: List[str], default: float = 0.0) -> float:
        """Safely extract and convert a float value from multiple possible field names."""
        for field_name in field_names:
            value = data.get(field_name)
            if value is not None:
                try:
                    if isinstance(value, str):
                        return float(value) if value else default
                    elif isinstance(value, (int, float)):
                        return float(value)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid numeric value for {field_name}: {value}")
                    return default
        return default

    def _record_adapter_success(self, adapter_key: str):
        """Record successful normalization for an adapter."""
        if adapter_key in self.adapter_metrics:
            self.adapter_metrics[adapter_key]["successful"] += 1
            self.adapter_metrics[adapter_key]["last_success"] = datetime.now(timezone.utc)

    def _record_adapter_error(self, adapter_key: str, error_msg: str):
        """Record failed normalization for an adapter."""
        if adapter_key in self.adapter_metrics:
            self.adapter_metrics[adapter_key]["failed"] += 1
            self.adapter_metrics[adapter_key]["last_error"] = {
                "message": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def get_adapter_metrics(self) -> Dict[str, Any]:
        """Get per-adapter performance metrics."""
        metrics = {}
        for adapter, stats in self.adapter_metrics.items():
            total = stats["total_attempts"]
            success = stats["successful"]
            failed = stats["failed"]

            metrics[adapter] = {
                "total_attempts": total,
                "successful": success,
                "failed": failed,
                "success_rate": success / max(total, 1),
                "failure_rate": failed / max(total, 1),
                "last_success": stats["last_success"].isoformat() if stats["last_success"] else None,
                "last_error": stats["last_error"],
            }

        return metrics

    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Get circuit breaker state and metrics."""
        return self.circuit_breaker.get_state()

    def get_retry_metrics(self) -> Dict[str, Any]:
        """Get retry handler metrics."""
        return self.retry_handler.get_metrics()

    async def normalize_tokens_async(self, scanner_name: str, raw_tokens: List[Dict]) -> List[TokenCandidate]:
        """
        Async version of normalize_tokens with circuit breaker and retry protection.
        """
        return await self.retry_handler.execute_async(
            self._normalize_tokens_internal_async,
            scanner_name,
            raw_tokens,
        )

    def normalize_tokens(self, scanner_name: str, raw_tokens: List[Dict]) -> List[TokenCandidate]:
        """
        Normalize raw tokens from a scanner to TokenCandidate objects.
        Uses circuit breaker and retry protection.
        """
        return self.circuit_breaker.call(
            self._normalize_tokens_internal_sync,
            scanner_name,
            raw_tokens,
        )

    async def _normalize_tokens_internal_async(self, scanner_name: str, raw_tokens: List[Dict]) -> List[TokenCandidate]:
        """Internal async normalization logic."""
        return self._normalize_tokens_internal_sync(scanner_name, raw_tokens)

    def _normalize_tokens_internal_sync(self, scanner_name: str, raw_tokens: List[Dict]) -> List[TokenCandidate]:
        """Internal sync normalization logic."""
        normalized = []
        rejected = 0

        start_time = datetime.now(timezone.utc)

        for raw in raw_tokens:
            adapter_key = scanner_name

            try:
                if self._is_scanned_token_data(raw):
                    adapter_key = "ScannedToken"
                elif scanner_name == "trade_engine":
                    token_source = raw.get("source", "")
                    source_to_adapter = {
                        "dexscreener": "DexScreenerScanner",
                        "cmc": "EliteCoinMarketCapScanner",
                        "mempool": "MempoolScannerUltra",
                        "arbitrage_mev": "ArbitrageMEVScanner",
                        "ai_discovery": "AIDiscoveryScanner",
                        "hybrid": "EliteHybridScanner",
                        "onchain": "OnChainScannerUltra",
                        "d3": "D3Scanner",
                    }
                    adapter_key = source_to_adapter.get(token_source, "trade_engine")

                adapter = self.adapters.get(adapter_key)
                if not adapter:
                    error_msg = f"No adapter found for scanner: {scanner_name} (adapter_key: {adapter_key})"
                    logger.error(error_msg)
                    rejected += 1
                    self.monitor.record_component_error("token_normalizer", f"No adapter for {adapter_key}")
                    self._record_adapter_error(adapter_key, error_msg)
                    continue

                self.adapter_metrics[adapter_key]["total_attempts"] += 1

                candidate = adapter(raw)

                if not candidate:
                    error_msg = f"Adapter {adapter_key} returned None"
                    rejected += 1
                    logger.error(error_msg)
                    self.monitor.record_component_error("token_normalizer", "Invalid candidate")
                    self._record_adapter_error(adapter_key, error_msg)
                    continue

                if candidate.is_valid_candidate():
                    if adapter_key == "EliteCoinMarketCapScanner":
                        candidate.confidence = max(0.0, candidate.confidence - 0.2)
                        candidate.enrichment_only = True

                    # NEW: Enrich the token with computed data fields
                    self._enrich_candidate(candidate)
                    
                    normalized.append(candidate)
                    self.monitor.record_component_success("token_normalizer", 1)
                    self._record_adapter_success(adapter_key)
                else:
                    error_summary = candidate.get_validation_errors()
                    error_msg = f"Invalid candidate from {adapter_key}: {error_summary}"
                    rejected += 1
                    logger.error(error_msg)
                    self.monitor.record_component_error("token_normalizer", "Invalid candidate")
                    self._record_adapter_error(adapter_key, error_msg)

            except Exception as e:
                error_msg = f"Failed to normalize token from {scanner_name}: {e}"
                logger.error(error_msg, exc_info=True)
                logger.debug(f"Raw token data that failed: {raw}")
                rejected += 1
                self.monitor.record_component_error("token_normalizer", str(e))
                self._record_adapter_error(adapter_key, error_msg)

        logger.info(f"[INGEST] {scanner_name} normalized={len(normalized)} rejected={rejected}")

        latency = (datetime.now(timezone.utc) - start_time).total_seconds()
        self.monitor.record_component_metrics("token_normalizer", {
            "normalized_count": len(normalized),
            "rejected_count": rejected,
            "latency_seconds": latency,
        })

        return normalized

    def normalize_dexscreener(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize DexScreener token data."""
        try:
            if not raw:
                raise ValueError("Empty token data received")

            base_token = raw.get("baseToken", {})

            chain_id = raw.get("chainId", "")
            chain_name = raw.get("chain", self._chain_id_to_name(chain_id))

            if not chain_name:
                raise ValueError(f"Could not determine chain from data: chainId={chain_id}, chain={raw.get('chain')}")

            if base_token and base_token.get("address"):
                address = base_token.get("address", "").strip()
                symbol = base_token.get("symbol", "").strip()
                name = base_token.get("name", symbol).strip() or symbol
            else:
                address = raw.get("address", "").strip()
                symbol = raw.get("symbol", "").strip()
                name = raw.get("name", symbol).strip() or symbol

            if not address or not symbol:
                raise ValueError(f"Missing required token fields: address={address}, symbol={symbol}")

            if not address.startswith("0x") or len(address) != 42:
                raise ValueError(f"Invalid address format: {address}")

            import re
            if re.match(r"^[a-zA-Z0-9+/=]{20,}$", address):
                raise ValueError(f"Address appears to be base64/encoded data instead of hex: {address}")

            price_usd = self._safe_float(raw, ["priceUsd", "price_usd", "price"])
            liquidity = self._safe_float(raw, ["liquidity", "liquidity_usd", "liquidityUsd"])
            volume = self._safe_float(raw, ["volume", "volume_24h", "volume24h", "h24"])
            decimals = raw.get("decimals") or (base_token.get("decimals") if base_token else 18)

            market_cap = self._safe_float(raw, ["market_cap", "marketCap"])
            volatility = self._safe_float(raw, ["volatility"], default=0.0)
            ai_score = self._safe_float(raw, ["ai_score", "confidence"], default=0.0)
            strength = self._safe_float(raw, ["strength"], default=0.0)
            zscore = self._safe_float(raw, ["zscore"], default=0.0)

            return TokenCandidate(
                chain=chain_name,
                address=address,
                symbol=symbol,
                name=name,
                decimals=decimals,
                price_usd=price_usd,
                liquidity_usd=liquidity,
                volume_24h=volume,
                market_cap=market_cap,
                source="dexscreener",
                discovered_at=datetime.now(timezone.utc),
                confidence=0.7,
                metadata={
                    "volatility": volatility,
                    "ai_score": ai_score,
                    "strength": strength,
                    "zscore": zscore,
                },
            )

        except Exception as e:
            logger.error(f"DexScreener normalization failed: {e}", exc_info=True)
            raise

    def normalize_cmc(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize CoinMarketCap token data."""
        try:
            platform = raw.get("platform", {})
            quote = raw.get("quote", {}).get("USD", {})

            if not platform:
                raise ValueError("Missing platform data in CMC response")
            if not quote:
                raise ValueError("Missing USD quote data in CMC response")

            chain = self._cmc_platform_to_chain(platform).strip()
            address = platform.get("token_address", "").strip()
            symbol = raw.get("symbol", "").strip()

            if not chain or not address or not symbol:
                raise ValueError(f"TokenCandidate requires chain, address, and symbol. Got: chain={chain}, address={address}, symbol={symbol}")

            name = raw.get("name", symbol).strip() or symbol

            price_usd = float(quote.get("price", 0)) if quote else 0.0
            volume_24h = float(quote.get("volume_24h", 0)) if quote else 0.0
            market_cap = float(quote.get("market_cap", 0)) if quote else 0.0

            return TokenCandidate(
                chain=chain,
                address=address,
                symbol=symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=None,
                volume_24h=volume_24h,
                market_cap=market_cap,
                source="cmc",
                discovered_at=datetime.now(timezone.utc),
                confidence=0.5,
            )

        except Exception as e:
            logger.error(f"CMC normalization failed: {e}", exc_info=True)
            raise

    def normalize_mempool(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize MempoolScanner token data."""
        try:
            chain = raw.get("chain", "").strip()
            token_address = raw.get("address", raw.get("token_address", "")).strip()
            token_symbol = raw.get("symbol", raw.get("token_symbol", "")).strip()

            if not chain or not token_address or not token_symbol:
                raise ValueError(f"TokenCandidate requires chain, address, and symbol. Got: chain={chain}, address={token_address}, symbol={token_symbol}")

            name = raw.get("name", raw.get("token_name", token_symbol)).strip() or token_symbol

            price_usd = self._safe_float(raw, ["price_usd", "price"])
            liquidity = self._safe_float(raw, ["liquidity", "liquidity_usd"])
            volume_24h = self._safe_float(raw, ["volume_24h", "volume"])
            market_cap = self._safe_float(raw, ["market_cap"], default=0.0)

            return TokenCandidate(
                chain=chain,
                address=token_address,
                symbol=token_symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=liquidity,
                volume_24h=volume_24h,
                market_cap=market_cap,
                source="mempool",
                discovered_at=datetime.now(timezone.utc),
                confidence=0.8,
                metadata={
                    "original_gas_cost_eth": raw.get("gas_cost_eth", 0.0),
                    "original_profit_eth": raw.get("profit_eth", 0.0),
                },
            )

        except Exception as e:
            logger.error(f"Mempool normalization failed: {e}", exc_info=True)
            raise

    def normalize_arbitrage_mev(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize ArbitrageMEVScanner token data."""
        try:
            chain = raw.get("chain", raw.get("network", "")).strip()
            address = raw.get("address", "").strip()
            symbol = raw.get("symbol", "").strip()

            if not address and raw.get("pair"):
                pair = raw.get("pair", "")
                if "/" in pair:
                    address = f"mev_{pair.replace('/', '_').lower()}"

            if not address.startswith("mev_") and not self._is_valid_eth_address(address):
                raise ValueError(f"Invalid address format: {address}")

            if not chain or not address or not symbol:
                raise ValueError(f"TokenCandidate requires chain, address, and symbol. Got: chain={chain}, address={address}, symbol={symbol}")

            name = raw.get("name", f"MEV {symbol}").strip() or f"MEV {symbol}"

            price_usd = self._safe_float(raw, ["price_usd", "price", "estimated_profit"])
            liquidity_usd = self._safe_float(raw, ["liquidity_usd", "liquidity"])
            volume_24h = self._safe_float(raw, ["volume_24h", "volume"])
            confidence = self._safe_float(raw, ["confidence"], default=0.9)

            confidence = max(0.0, min(1.0, confidence))

            return TokenCandidate(
                chain=chain,
                address=address,
                symbol=symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                market_cap=None,
                source="arbitrage_mev",
                discovered_at=datetime.now(timezone.utc),
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"ArbitrageMEV normalization failed: {e}", exc_info=True)
            raise

    def normalize_ai_discovery(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize AIDiscoveryScanner token data."""
        try:
            chain = raw.get("chain", "").strip()
            address = raw.get("address", "").strip()
            symbol = raw.get("symbol", "").strip()

            if not chain or not address or not symbol:
                raise ValueError(f"TokenCandidate requires chain, address, and symbol. Got: chain={chain}, address={address}, symbol={symbol}")

            name = raw.get("name", symbol).strip() or symbol

            price_usd = self._safe_float(raw, ["price_usd", "price"])
            liquidity = self._safe_float(raw, ["liquidity", "liquidity_usd"])
            volume_24h = self._safe_float(raw, ["volume_24h", "volume"])

            market_cap = self._safe_float(raw, ["market_cap"], default=0.0)
            ai_score = self._safe_float(raw, ["ai_score"], default=0.5)

            return TokenCandidate(
                chain=chain,
                address=address,
                symbol=symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=liquidity,
                volume_24h=volume_24h,
                market_cap=market_cap,
                source="ai_discovery",
                discovered_at=datetime.now(timezone.utc),
                confidence=ai_score,
            )

        except Exception as e:
            logger.error(f"AI Discovery normalization failed: {e}", exc_info=True)
            raise

    def normalize_hybrid(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize EliteHybridScanner token data."""
        try:
            chain = raw.get("chain", raw.get("network", "")).strip()
            address = raw.get("address", "").strip()
            symbol = raw.get("symbol", "").strip()

            if not chain or not address or not symbol:
                raise ValueError(f"TokenCandidate requires chain, address, and symbol. Got: chain={chain}, address={address}, symbol={symbol}")

            name = raw.get("name", symbol).strip() or symbol

            price_usd = self._safe_float(raw, ["price_usd", "price"])
            liquidity_usd = self._safe_float(raw, ["liquidity_usd", "liquidity"])
            volume_24h = self._safe_float(raw, ["volume_24h", "volume"])

            return TokenCandidate(
                chain=chain,
                address=address,
                symbol=symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                market_cap=None,
                source="hybrid",
                discovered_at=datetime.now(timezone.utc),
                confidence=0.75,
            )

        except Exception as e:
            logger.error(f"Hybrid normalization failed: {e}", exc_info=True)
            raise

    def normalize_onchain(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize OnChainScannerUltra token data."""
        try:
            chain = raw.get("chain", "").strip()
            address = raw.get("address", "").strip()
            symbol = raw.get("symbol", "").strip()

            if not chain or not address or not symbol:
                raise ValueError(f"TokenCandidate requires chain, address, and symbol. Got: chain={chain}, address={address}, symbol={symbol}")

            name = raw.get("name", symbol).strip() or symbol

            price_usd = self._safe_float(raw, ["price_usd", "price"])
            liquidity_usd = self._safe_float(raw, ["liquidity_usd", "liquidity"])
            volume_24h = self._safe_float(raw, ["volume_24h", "volume"])

            return TokenCandidate(
                chain=chain,
                address=address,
                symbol=symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                market_cap=None,
                source="onchain",
                discovered_at=datetime.now(timezone.utc),
                confidence=0.85,
            )

        except Exception as e:
            logger.error(f"OnChain normalization failed: {e}", exc_info=True)
            raise

    def normalize_d3(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize D3Scanner token data."""
        try:
            chain = raw.get("chain", raw.get("network", "")).strip()
            address = raw.get("address", "").strip()
            symbol = raw.get("symbol", "").strip()
            name = raw.get("name", "").strip()

            if not chain or not address or not symbol:
                raise ValueError(f"TokenCandidate requires chain, address, and symbol. Got: chain={chain}, address={address}, symbol={symbol}")

            name = name or symbol

            price_usd = self._safe_float(raw, ["price_usd", "price"])
            liquidity_usd = self._safe_float(raw, ["liquidity_usd", "liquidity"])
            volume_24h = self._safe_float(raw, ["volume_24h"])

            return TokenCandidate(
                chain=chain,
                address=address,
                symbol=symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                market_cap=None,
                source="d3",
                discovered_at=datetime.now(timezone.utc),
                confidence=0.6,
            )

        except Exception as e:
            logger.error(f"D3 normalization failed: {e}", exc_info=True)
            raise

    def normalize_trade_engine(self, raw: Dict) -> Optional[TokenCandidate]:
        """Normalize trade_engine token data."""
        try:
            chain = raw.get("chain", raw.get("network", "")).strip()
            address = raw.get("address", raw.get("token_address", "")).strip()
            symbol = raw.get("symbol", raw.get("token_symbol", "")).strip()

            if not chain and address.startswith("mev_"):
                parts = address.split("-")
                if len(parts) >= 3:
                    chain = parts[1]
                    if chain not in [
                        "linea", "oasis", "fuse", "mantle", "evmos", "scroll",
                        "polygon", "bsc", "blast", "ethereum", "arbitrum", "optimism",
                        "base", "celo"
                    ]:
                        logger.warning(f"Unknown chain '{chain}' in MEV address: {address}")
                        chain = ""

            if not chain or not address or not symbol:
                raise ValueError(f"Trade engine token missing required fields: chain={chain}, address={address}, symbol={symbol}")

            name = raw.get("name", raw.get("token_name", symbol)).strip() or symbol
            price_usd = self._safe_float(raw, ["price", "price_usd"])
            liquidity_usd = self._safe_float(raw, ["liquidity_usd", "liquidity"])
            volume_24h = self._safe_float(raw, ["volume_24h", "volume"])
            market_cap = self._safe_float(raw, ["market_cap"])
            confidence = self._safe_float(raw, ["confidence", "ai_score"], default=0.5)
            confidence = max(0.0, min(1.0, confidence))

            return TokenCandidate(
                chain=chain,
                address=address,
                symbol=symbol,
                name=name,
                decimals=18,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                market_cap=market_cap,
                source="trade_engine",
                discovered_at=datetime.now(timezone.utc),
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"Trade engine normalization failed: {e}", exc_info=True)
            raise

    def _detect_chain_from_address(self, address: str) -> Optional[str]:
        """Detect chain based on address format."""
        if not address:
            return None
            
        address = address.strip()
        
        # Solana addresses (base58)
        if len(address) >= 32 and len(address) <= 44:
            base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
            if all(c in base58_chars for c in address):
                return "solana"
        
        # EVM addresses (0x + hex)
        if address.startswith("0x") and len(address) == 42:
            try:
                int(address[2:], 16)
                return "ethereum"  # Default EVM chain
            except ValueError:
                pass
        
        # Bitcoin-like addresses (base58 with prefix)
        if len(address) >= 26 and len(address) <= 35:
            base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
            if all(c in base58_chars for c in address):
                # Could be Bitcoin, but we'll default to unknown for now
                return None
        
        # Bech32 addresses (cosmos, etc.)
        if "1" in address and not address.startswith("0x"):
            return "cosmos"  # Generic bech32 chain
        
        return None

    def _chain_id_to_name(self, chain_id: str) -> str:
        """Convert chain ID to chain name."""
        chain_mapping = {
            "1": "ethereum",
            "56": "bsc",
            "137": "polygon",
            "42161": "arbitrum",
            "10": "optimism",
            "43114": "avalanche",
            "250": "fantom",
            "8453": "base",
            "100": "gnosis",
            "1284": "moonbeam",
            "42220": "celo",
            "1088": "metis",
            "2222": "kava",
            "1313161554": "aurora",
            "1666600000": "harmony",
            "8217": "klaytn",
            "42262": "oasis",
            "122": "fuse",
            "9001": "evmos",
            "288": "boba",
            "235": "moonriver",
            "40": "telos",
            "19": "thundercore",
            "11297108109": "palm",
            "534352": "scroll",
            "169": "manta",
            "5000": "mantle",
            "1101": "polygonzkevm",
            "204": "opbnb",
            "81457": "blast",
            "59144": "linea",
            "560350": "syscoin",
            "128": "velas",
            "324": "zksync",
            "42170": "arbitrumnova",
        }
        return chain_mapping.get(chain_id, "") or "ethereum"

    def _cmc_platform_to_chain(self, platform: Dict) -> str:
        """Convert CMC platform info to chain name."""
        if not platform:
            return "ethereum"

        token_address = platform.get("token_address", "")
        if not token_address:
            return "ethereum"

        if token_address.startswith("0x"):
            return "ethereum"

        return "ethereum"

    def _is_valid_eth_address(self, address: str) -> bool:
        """Check if address is a valid Ethereum address format."""
        if not address or not isinstance(address, str):
            return False
        try:
            return Web3.is_address(address)
        except:
            return False

    def _is_scanned_token_data(self, raw: Dict) -> bool:
        """
        Check if the raw data is in ScannedToken format.
        """
        if not isinstance(raw, dict):
            return False

        scanned_token_fields = {
            "address", "symbol", "name", "chain_id", "decimals",
            "price", "volume_24h", "liquidity_usd", "market_cap"
        }

        has_scanned_fields = any(field in raw for field in scanned_token_fields)
        has_raw_api_fields = "baseToken" in raw or "chainId" in raw

        return has_scanned_fields and not has_raw_api_fields

    def normalize_scanned_token(self, raw: Dict) -> Optional[TokenCandidate]:
        """
        Normalize ScannedToken data to TokenCandidate.
        """
        try:
            if not raw:
                raise ValueError("Empty ScannedToken data received")

            address = raw.get("address", "").strip()
            symbol = raw.get("symbol", "").strip()
            name = raw.get("name", "").strip()

            if not address or not symbol:
                raise ValueError(f"Missing required ScannedToken fields: address={address}, symbol={symbol}")

            chain_id = raw.get("chain_id", 1)
            chain_name = raw.get("chain", "")

            # Auto-detect chain based on address format if chain is unknown
            if not chain_name:
                chain_name = self._chain_id_to_name(str(chain_id))

            # HARD REJECT: If address format contradicts chain_id for EVM chains, reject immediately
            if chain_name and chain_name != "solana":
                if address_validator.is_solana_address(address):
                    logger.warning(f"Solana address detected on EVM chain (chain_id={chain_id}): {address[:10]}... - REJECTING TOKEN")
                    return None  # Hard reject Solana addresses on EVM chains
                elif not address_validator.validate_token_address(chain_name, address):
                    # If address doesn't match the declared chain, try to detect the correct chain
                    if address_validator.is_evm_address(address):
                        # Use chain_id mapping for EVM addresses
                        detected_from_id = self._chain_id_to_name(str(chain_id))
                        if detected_from_id and detected_from_id != chain_name:
                            chain_name = detected_from_id
                            logger.info(f"Corrected chain from '{chain_name}' to '{detected_from_id}' based on chain_id {chain_id}")
                    else:
                        logger.warning(f"Address format doesn't match chain {chain_name}: {address}")

            # Final fallback if still unknown
            if not chain_name or chain_name == "unknown":
                if address_validator.is_solana_address(address):
                    chain_name = "solana"
                elif address_validator.is_evm_address(address):
                    chain_name = self._chain_id_to_name(str(chain_id)) or "ethereum"
                else:
                    chain_name = "ethereum"
                    logger.warning(f"Unknown chain_id {chain_id} and could not detect from address format, defaulting to ethereum")

            decimals = raw.get("decimals", 18)

            price_usd = self._safe_float(raw, ["price"])
            liquidity_usd = self._safe_float(raw, ["liquidity_usd"])
            volume_24h = self._safe_float(raw, ["volume_24h"])
            market_cap = self._safe_float(raw, ["market_cap"])

            ai_score = self._safe_float(raw, ["ai_score", "confidence"], default=0.0)
            confidence = ai_score if ai_score <= 1 else ai_score / 100.0

            return TokenCandidate(
                chain=chain_name,
                address=address,
                symbol=symbol,
                name=name,
                decimals=decimals,
                source="scanned_token",
                discovered_at=datetime.now(timezone.utc),
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                market_cap=market_cap,
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"ScannedToken normalization failed: {e}", exc_info=True)
            self._record_adapter_error("ScannedToken", str(e))
            return None

