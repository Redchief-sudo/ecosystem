"""
Token Deduplication Utility
===========================

Centralized token deduplication to prevent duplicate opportunities
and reduce CPU drag from repeated processing.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

from networks.chain_normalizer import chain_normalizer
from networks.address_validator import address_validator

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@dataclass(frozen=True)
class TokenIdentifier:
    """Unique identifier for tokens to prevent duplicates."""
    canonical_chain: str
    dex: str
    pair_address: str

    def __hash__(self) -> int:
        """Use tuple-based hashing for efficiency."""
        return hash((self.canonical_chain.lower(), self.dex.lower(), self.pair_address.lower()))

    def __eq__(self, other) -> bool:
        """Compare token identifiers."""
        if not isinstance(other, TokenIdentifier):
            return False
        return (
            self.canonical_chain.lower() == other.canonical_chain.lower()
            and self.dex.lower() == other.dex.lower()
            and self.pair_address.lower() == other.pair_address.lower()
        )


class TokenDeduplicator:
    """
    Advanced token deduplication system.

    Prevents:
    - Duplicate opportunities from multiple scanners
    - Registry fallback loops
    - Cross-chain token duplication
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.seen_tokens: Set[TokenIdentifier] = set()
        self.token_sources: Dict[TokenIdentifier, Set[str]] = {}
        self.token_timestamps: Dict[TokenIdentifier, float] = {}
        self.duplicate_count = 0
        self.unique_count = 0
        self.ttl_seconds = ttl_seconds
        self.last_cleanup = time.time()
        self.seen_by_market: Set[str] = set()
        self.chain_mismatches = 0

    def _get_canonical_chain(self, token: Dict[str, Any]) -> str:
        """
        Extract canonical chain from authoritative DEX data.
        
        DexScreener metadata is the source of truth for where a token actually trades.
        Top-level chain fields may contain classification noise.
        """
        if "metadata" in token and isinstance(token["metadata"], dict):
            metadata = token["metadata"]
            if "dex_data" in metadata and isinstance(metadata["dex_data"], dict):
                dex_data = metadata["dex_data"]
                if "chainId" in dex_data and dex_data["chainId"]:
                    canonical = str(dex_data["chainId"]).strip().lower()
                    normalized = chain_normalizer.normalize_chain_identifier(canonical)
                    logger.debug("Canonical chain from dex_data.chainId: '%s' -> '%s'", canonical, normalized)
                    return normalized
        
        fallback_chain = self._extract_chain(token)
        logger.debug("No dex_data.chainId found, using fallback chain: '%s'", fallback_chain)
        return fallback_chain

    def _get_dex_id(self, token: Dict[str, Any]) -> str:
        """Extract DEX identifier from token metadata."""
        if "metadata" in token and isinstance(token["metadata"], dict):
            metadata = token["metadata"]
            if "dex_data" in metadata and isinstance(metadata["dex_data"], dict):
                dex_data = metadata["dex_data"]
                if "dexId" in dex_data and dex_data["dexId"]:
                    return str(dex_data["dexId"]).strip().lower()
        
        if "exchange" in token and token["exchange"]:
            return str(token["exchange"]).strip().lower()
        
        return "unknown"

    def _get_pair_address(self, token: Dict[str, Any]) -> Optional[str]:
        """Extract pair address from token data."""
        if "metadata" in token and isinstance(token["metadata"], dict):
            metadata = token["metadata"]
            if "dex_data" in metadata and isinstance(metadata["dex_data"], dict):
                dex_data = metadata["dex_data"]
                if "pairAddress" in dex_data and dex_data["pairAddress"]:
                    return str(dex_data["pairAddress"]).strip().lower()
        
        if "pair_address" in token and token["pair_address"]:
            return str(token["pair_address"]).strip().lower()
        
        if "dexscreener_pair" in token and token["dexscreener_pair"]:
            return str(token["dexscreener_pair"]).strip().lower()
        
        return None

    def _detect_chain_mismatch(self, token: Dict[str, Any], canonical_chain: str) -> bool:
        """
        STRICT: Detect chain field inconsistencies and reject invalid tokens.
        Returns True if token should be rejected.
        """
        top_level_chain = self._extract_chain(token)
        
        if not top_level_chain:
            logger.error(
                "CRITICAL: Token missing chain data for %s - SYSTEM FAILURE",
                token.get("symbol", "Unknown")
            )
            logger.error("Malformed token data: %s", token)
            return True  # Signal to reject this token
        
        if top_level_chain.lower() != canonical_chain.lower():
            logger.error(
                "CRITICAL: Chain data inconsistency for %s - SYSTEM FAILURE",
                token.get("symbol", "Unknown")
            )
            logger.error(
                "  Token chain: '%s' != Canonical chain: '%s'",
                top_level_chain,
                canonical_chain
            )
            logger.error("Full token data: %s", token)
            return True  # Signal to reject this token
        
        return False  # No mismatch, accept token

    def is_duplicate(self, canonical_chain: str, dex: str, pair_address: str) -> bool:
        """
        Fast duplicate check using canonical_chain + dex + pair_address key.

        Args:
            canonical_chain: Authoritative chain from dex_data
            dex: DEX identifier
            pair_address: Trading pair address

        Returns:
            True if market is a duplicate, False otherwise
        """
        key = f"{canonical_chain}:{dex}:{pair_address}"
        if key in self.seen_by_market:
            return True
        self.seen_by_market.add(key)
        return False

    def add_tokens(self, tokens: List[Dict[str, Any]], scanner_name: str) -> List[Dict[str, Any]]:
        """
        Add tokens from a scanner, returning only unique tokens.

        Args:
            tokens: List of token dictionaries from scanner
            scanner_name: Name of scanner for tracking

        Returns:
            List of unique tokens (duplicates removed)
        """
        unique_tokens: List[Dict[str, Any]] = []
        malformed_count = 0

        self._cleanup_expired_tokens()

        for token in tokens:
            try:
                canonical_chain = self._get_canonical_chain(token)
                dex = self._get_dex_id(token)
                pair_address = self._get_pair_address(token)

                if not canonical_chain or canonical_chain == "unknown":
                    malformed_count += 1
                    logger.warning(
                        "TOKEN INVARIANT VIOLATION: Token missing canonical chain - chain='%s'",
                        canonical_chain,
                    )
                    logger.debug("Malformed token emitted by scanner '%s': %s", scanner_name, token)
                    continue

                if not pair_address:
                    malformed_count += 1
                    logger.warning(
                        "TOKEN INVARIANT VIOLATION: Token missing pair address for %s",
                        token.get("symbol", "Unknown")
                    )
                    logger.debug("Malformed token emitted by scanner '%s': %s", scanner_name, token)
                    continue

                # STRICT: Check for chain mismatch and reject if found
                if self._detect_chain_mismatch(token, canonical_chain):
                    malformed_count += 1
                    continue

                # Update token with authoritative chain to resolve conflicts
                token["chain"] = canonical_chain
                token["chain_source"] = "dex_data_authority"

                token_id = TokenIdentifier(
                    canonical_chain=canonical_chain,
                    dex=dex,
                    pair_address=pair_address
                )

                if self.is_duplicate(canonical_chain, dex, pair_address):
                    self.duplicate_count += 1
                    self.token_sources.setdefault(token_id, set()).add(scanner_name)
                    logger.debug(
                        "Duplicate market found: %s:%s:%s from %s",
                        canonical_chain,
                        dex,
                        pair_address,
                        scanner_name
                    )
                    continue

                self.seen_tokens.add(token_id)
                self.token_timestamps[token_id] = time.time()
                self.unique_count += 1
                self.token_sources.setdefault(token_id, set()).add(scanner_name)

                token["canonical_chain"] = canonical_chain
                token["source_scanner"] = scanner_name
                token["discovery_method"] = "deduplicated"

                unique_tokens.append(token)
                logger.info(
                    "Successfully processed token: %s on %s (dex: %s, pair: %s)",
                    token.get("symbol", "Unknown"),
                    canonical_chain,
                    dex,
                    pair_address[:10]
                )

            except ValueError as e:
                malformed_count += 1
                logger.warning("Skipping malformed token from %s: %s", scanner_name, e)
                logger.debug("Malformed token data: %s", token)
                continue
            except Exception as e:
                malformed_count += 1
                logger.warning("Unexpected error processing token from %s: %s", scanner_name, e)
                logger.debug("Token data: %s", token)
                continue

        logger.info(
            "Scanner %s: %d unique, %d duplicates, %d malformed, %d chain mismatches",
            scanner_name,
            len(unique_tokens),
            self.duplicate_count,
            malformed_count,
            self.chain_mismatches,
        )
        return unique_tokens

    def _is_malformed(self, token: Dict[str, Any]) -> bool:
        """Check if token appears malformed based on missing critical fields."""
        address_fields = ["address", "token_address", "contract_address", "contract"]
        symbol_fields = ["symbol", "token_symbol", "baseToken.symbol", "quoteToken.symbol"]

        has_address = any(field in token and token[field] for field in address_fields)
        has_symbol = any(field in token and token[field] for field in symbol_fields)

        return not (has_address and has_symbol)

    def _extract_chain(self, token: Dict[str, Any]) -> str:
        """Extract chain from token with normalization."""
        available_fields = list(token.keys())
        logger.debug("Token fields available: %s", available_fields)
        logger.debug("Full token data: %s", token)

        chain_fields = ["chain", "chain_name", "network", "blockchain", "chainId", "chain_id"]

        for field in chain_fields:
            if field in token:
                field_value = token[field]
                logger.debug("Found field '%s' with value: '%s' (type: %s)", field, field_value, type(field_value))
                if field_value:
                    chain = str(field_value).strip()
                    if chain and chain != "0":
                        normalized = chain_normalizer.normalize_chain_identifier(chain)
                        logger.debug("Extracted and normalized chain: '%s' -> '%s'", chain, normalized)
                        return normalized

        if "pair_address" in token and token["pair_address"]:
            if "metadata" in token and isinstance(token["metadata"], dict):
                metadata = token["metadata"]
                if "pair_url" in metadata:
                    url = metadata["pair_url"]
                    if "/" in url:
                        chain_from_url = url.split("/")[3] if len(url.split("/")) > 3 else None
                        if chain_from_url and chain_from_url.strip():
                            normalized = chain_normalizer.normalize_chain_name(chain_from_url)
                            logger.debug("Inferred chain from URL: '%s' -> '%s'", chain_from_url, normalized)
                            return normalized

        error_msg = (
            "CRITICAL ERROR: Cannot extract chain from token. "
            f"Available fields: {available_fields}. Token data: {token}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    def _extract_address(self, token: Dict[str, Any]) -> str:
        """Extract address from token with normalization."""
        available_fields = list(token.keys())
        logger.debug("Address extraction - Token fields available: %s", available_fields)

        address_fields = ["address", "contractAddress", "token_address", "contract"]

        for field in address_fields:
            if field in token:
                field_value = token[field]
                logger.debug("Found address field '%s' with value: '%s' (type: %s)", field, field_value, type(field_value))
                if field_value:
                    address = str(field_value).strip()
                    if address.startswith("0x"):
                        normalized = address.lower()
                        logger.debug("Extracted and normalized address: '%s' -> '%s'", address, normalized)
                        return normalized
                    return address.lower()

        error_msg = (
            "CRITICAL ERROR: Cannot extract address from token. "
            f"Available fields: {available_fields}. Token data: {token}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    def _normalize_chain_name(self, chain: str) -> str:
        """Normalize chain names to prevent duplicates."""
        return chain_normalizer.normalize_chain_name(chain)

    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        total_seen = self.unique_count + self.duplicate_count
        return {
            "total_seen": total_seen,
            "unique_tokens": self.unique_count,
            "duplicate_tokens": self.duplicate_count,
            "duplicate_rate": self.duplicate_count / max(total_seen, 1),
            "tokens_with_multiple_sources": len(
                [sources for sources in self.token_sources.values() if len(sources) > 1]
            ),
            "most_duplicated_tokens": self._get_most_duplicated(),
        }

    def _get_most_duplicated(self) -> List[Dict[str, Any]]:
        """Get markets found by multiple scanners."""
        multi_source_tokens = []

        for token_id, sources in self.token_sources.items():
            if len(sources) > 1:
                multi_source_tokens.append(
                    {
                        "canonical_chain": token_id.canonical_chain,
                        "dex": token_id.dex,
                        "pair_address": token_id.pair_address,
                        "sources": list(sources),
                        "source_count": len(sources),
                    }
                )

        return sorted(multi_source_tokens, key=lambda x: x["source_count"], reverse=True)

    def _cleanup_expired_tokens(self):
        """Remove tokens older than TTL to prevent unbounded memory growth."""
        current_time = time.time()
        if current_time - self.last_cleanup < 300:
            return

        expired_tokens = [tid for tid, ts in self.token_timestamps.items() if current_time - ts > self.ttl_seconds]

        for token_id in expired_tokens:
            self.seen_tokens.discard(token_id)
            self.token_timestamps.pop(token_id, None)
            self.token_sources.pop(token_id, None)

        if expired_tokens:
            logger.debug("Cleaned up %d expired tokens from deduplicator", len(expired_tokens))

        self.last_cleanup = current_time

    def clear(self):
        """Clear all seen tokens for fresh scan."""
        self.seen_tokens.clear()
        self.token_sources.clear()
        self.token_timestamps.clear()
        self.seen_by_market.clear()
        self.duplicate_count = 0
        self.unique_count = 0
        self.chain_mismatches = 0
        logger.info("Token deduplicator cleared")


# Global deduplicator instance
token_deduplicator = TokenDeduplicator()

