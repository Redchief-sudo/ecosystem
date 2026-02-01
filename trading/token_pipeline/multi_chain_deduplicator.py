"""
Multi-Chain Token Deduplicator
===============================

Chain-aware deduplication that supports EVM, Solana, Aptos, Sui, and other networks.
This replaces the EVM-centric deduplication with proper multi-network support.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set

from networks.multi_chain_models import TokenIdentity, TokenCandidate, ChainType, AddressType
from networks.chain_normalizers import MultiChainNormalizer
from networks.chain_normalizer import chain_normalizer

logger = logging.getLogger(__name__)


class MultiChainTokenDeduplicator:
    """
    Advanced multi-chain token deduplication system.
    
    Prevents:
    - Duplicate opportunities from multiple scanners
    - Cross-chain token duplication
    - Address format conflicts between networks
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self.seen_identities: Set[TokenIdentity] = set()
        self.token_sources: Dict[TokenIdentity, Set[str]] = {}
        self.token_timestamps: Dict[TokenIdentity, float] = {}
        self.duplicate_count = 0
        self.unique_count = 0
        self.ttl_seconds = ttl_seconds
        self.last_cleanup = time.time()
        
        # Per-chain type statistics
        self.chain_type_stats = {
            chain_type: {"unique": 0, "duplicates": 0} 
            for chain_type in ChainType
        }
    
    def is_duplicate(self, identity: TokenIdentity) -> bool:
        """
        Fast duplicate check using TokenIdentity.
        
        Args:
            identity: TokenIdentity to check
            
        Returns:
            True if token is a duplicate, False otherwise
        """
        if identity in self.seen_identities:
            self.duplicate_count += 1
            self.chain_type_stats[identity.chain_type]["duplicates"] += 1
            return True
        
        self.seen_identities.add(identity)
        self.token_timestamps[identity] = time.time()
        self.unique_count += 1
        self.chain_type_stats[identity.chain_type]["unique"] += 1
        return False
    
    def add_tokens(self, tokens: List[Dict[str, Any]], scanner_name: str) -> List[TokenCandidate]:
        """
        Add tokens from a scanner, returning only unique tokens.
        
        Args:
            tokens: List of token dictionaries from scanner
            scanner_name: Name of scanner for tracking
            
        Returns:
            List of unique TokenCandidate objects
        """
        unique_candidates: List[TokenCandidate] = []
        malformed_count = 0
        
        self._cleanup_expired_tokens()
        
        for token in tokens:
            try:
                candidate = self._convert_to_candidate(token, scanner_name)
                if not candidate:
                    malformed_count += 1
                    continue
                
                identity = candidate.get_identity()
                
                if self.is_duplicate(identity):
                    self.token_sources.setdefault(identity, set()).add(scanner_name)
                    logger.debug(
                        f"Duplicate token found: {identity.chain}:{identity.address} "
                        f"({identity.chain_type.value}) from {scanner_name}"
                    )
                    continue
                
                self.token_sources.setdefault(identity, set()).add(scanner_name)
                unique_candidates.append(candidate)
                
                logger.info(
                    f"Successfully processed token: {candidate.symbol} on {candidate.chain} "
                    f"({candidate.chain_type.value})"
                )
                
            except Exception as e:
                malformed_count += 1
                logger.warning(f"Skipping malformed token from {scanner_name}: {e}")
                logger.debug(f"Malformed token data: {token}")
                continue
        
        logger.info(
            f"Scanner {scanner_name}: {len(unique_candidates)} unique, "
            f"{self.duplicate_count} duplicates, {malformed_count} malformed"
        )
        
        return unique_candidates
    
    def _convert_to_candidate(self, token: Dict[str, Any], scanner_name: str) -> Optional[TokenCandidate]:
        """
        Convert raw token data to TokenCandidate with proper chain type detection.
        """
        try:
            # Extract basic fields
            raw_chain = self._extract_chain(token)
            address = self._extract_address(token)
            symbol = self._extract_symbol(token)
            name = self._extract_name(token, symbol)
            
            if not raw_chain or not address or not symbol:
                raise ValueError(f"Missing required fields: chain={raw_chain}, address={address}, symbol={symbol}")
            
            # Normalize chain name first
            try:
                normalized_chain = chain_normalizer.normalize_chain_identifier(raw_chain)
            except Exception as e:
                logger.warning(f"Chain normalization failed for '{raw_chain}': {e}")
                return None
            
            # Detect and normalize address format
            try:
                normalized_addr, chain_type, address_type = MultiChainNormalizer.detect_and_normalize(
                    address, normalized_chain
                )
            except ValueError as e:
                logger.warning(f"Address normalization failed: {e}")
                return None
            
            # Extract market data
            price_usd = self._safe_float(token, ["priceUsd", "price_usd", "price"])
            liquidity_usd = self._safe_float(token, ["liquidity", "liquidity_usd", "liquidityUsd"])
            volume_24h = self._safe_float(token, ["volume", "volume_24h", "volume24h"])
            market_cap = self._safe_float(token, ["market_cap", "marketCap"])
            
            # Extract chain-specific data
            decimals = token.get("decimals")
            pair_address = token.get("pair_address") or token.get("dexscreener_pair")
            pool_id = token.get("pool_id") or token.get("amm_id")
            token_id = token.get("token_id")
            
            # Create TokenCandidate
            candidate = TokenCandidate(
                chain=normalized_chain,
                chain_type=chain_type,
                address=normalized_addr,
                address_type=address_type,
                symbol=symbol,
                name=name,
                token_id=token_id,
                price_usd=price_usd,
                liquidity_usd=liquidity_usd,
                volume_24h=volume_24h,
                market_cap=market_cap,
                decimals=decimals,
                pair_address=pair_address,
                pool_id=pool_id,
                source=scanner_name,
                confidence=token.get("confidence", 0.5),
                metadata=token.get("metadata", {})
            )
            
            return candidate
            
        except Exception as e:
            logger.error(f"Failed to convert token to candidate: {e}")
            return None
    
    def _extract_chain(self, token: Dict[str, Any]) -> str:
        """Extract chain from token with fallbacks."""
        chain_fields = ["chain", "chain_name", "network", "blockchain", "chainId", "chain_id"]
        
        for field in chain_fields:
            if field in token and token[field]:
                return str(token[field]).strip()
        
        # Try to infer from metadata
        if "metadata" in token and isinstance(token["metadata"], dict):
            metadata = token["metadata"]
            for field in ["chain", "network"]:
                if field in metadata and metadata[field]:
                    return str(metadata[field]).strip()
        
        return ""
    
    def _extract_address(self, token: Dict[str, Any]) -> str:
        """Extract address from token with fallbacks."""
        address_fields = ["address", "contractAddress", "token_address", "contract"]
        
        for field in address_fields:
            if field in token and token[field]:
                return str(token[field]).strip()
        
        # Try nested fields
        for nested in ["baseToken", "quoteToken"]:
            if nested in token and isinstance(token[nested], dict):
                addr = token[nested].get("address")
                if addr:
                    return str(addr).strip()
        
        return ""
    
    def _extract_symbol(self, token: Dict[str, Any]) -> str:
        """Extract symbol from token with fallbacks."""
        symbol_fields = ["symbol", "token_symbol", "baseToken.symbol", "quoteToken.symbol"]
        
        for field in symbol_fields:
            if field in token and token[field]:
                return str(token[field]).strip()
        
        # Try nested fields
        for nested in ["baseToken", "quoteToken"]:
            if nested in token and isinstance(token[nested], dict):
                symbol = token[nested].get("symbol")
                if symbol:
                    return str(symbol).strip()
        
        return ""
    
    def _extract_name(self, token: Dict[str, Any], symbol: str) -> str:
        """Extract name from token with fallbacks."""
        name_fields = ["name", "token_name", "baseToken.name", "quoteToken.name"]
        
        for field in name_fields:
            if field in token and token[field]:
                return str(token[field]).strip()
        
        # Try nested fields
        for nested in ["baseToken", "quoteToken"]:
            if nested in token and isinstance(token[nested], dict):
                name = token[nested].get("name")
                if name:
                    return str(name).strip()
        
        # Fallback to symbol
        return symbol
    
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
                    continue
        return default
    
    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get comprehensive deduplication statistics."""
        total_seen = self.unique_count + self.duplicate_count
        return {
            "total_seen": total_seen,
            "unique_tokens": self.unique_count,
            "duplicate_tokens": self.duplicate_count,
            "duplicate_rate": self.duplicate_count / max(total_seen, 1),
            "tokens_with_multiple_sources": len(
                [sources for sources in self.token_sources.values() if len(sources) > 1]
            ),
            "chain_type_breakdown": self.chain_type_stats,
            "most_duplicated_tokens": self._get_most_duplicated(),
        }
    
    def _get_most_duplicated(self) -> List[Dict[str, Any]]:
        """Get tokens found by multiple scanners."""
        multi_source_tokens = []
        
        for token_id, sources in self.token_sources.items():
            if len(sources) > 1:
                multi_source_tokens.append({
                    "chain": token_id.chain,
                    "address": token_id.address,
                    "chain_type": token_id.chain_type.value,
                    "address_type": token_id.address_type.value,
                    "sources": list(sources),
                    "source_count": len(sources),
                })
        
        return sorted(multi_source_tokens, key=lambda x: x["source_count"], reverse=True)
    
    def _cleanup_expired_tokens(self):
        """Remove tokens older than TTL to prevent unbounded memory growth."""
        current_time = time.time()
        if current_time - self.last_cleanup < 300:  # Cleanup every 5 minutes
            return
        
        expired_tokens = [
            tid for tid, ts in self.token_timestamps.items() 
            if current_time - ts > self.ttl_seconds
        ]
        
        for token_id in expired_tokens:
            self.seen_identities.discard(token_id)
            self.token_timestamps.pop(token_id, None)
            self.token_sources.pop(token_id, None)
        
        if expired_tokens:
            logger.debug(f"Cleaned up {len(expired_tokens)} expired tokens from deduplicator")
        
        self.last_cleanup = current_time
    
    def clear(self):
        """Clear all seen tokens for fresh scan."""
        self.seen_identities.clear()
        self.token_sources.clear()
        self.token_timestamps.clear()
        self.duplicate_count = 0
        self.unique_count = 0
        
        # Reset chain type stats
        for chain_type in self.chain_type_stats:
            self.chain_type_stats[chain_type] = {"unique": 0, "duplicates": 0}
        
        logger.info("Multi-chain token deduplicator cleared")


# Global deduplicator instance
multi_chain_deduplicator = MultiChainTokenDeduplicator(ttl_seconds=60)


__all__ = [
    "MultiChainTokenDeduplicator",
    "multi_chain_deduplicator",
]
