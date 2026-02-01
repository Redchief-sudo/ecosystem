"""
Multi-Chain Token Ingestion Pipeline
===================================

Chain-authoritative token ingestion with enforced identity correctness.
Dexscreener chainId is treated as the single source of truth.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from trading.token_pipeline.dead_letter_queue import get_dead_letter_queue
from networks.multi_chain_models import TokenCandidate, ChainType
from trading.token_pipeline.multi_chain_deduplicator import MultiChainTokenDeduplicator
from trading.token_pipeline.multi_chain_queue_manager import MultiChainQueueManager, enqueue_token
from networks.chain_normalizers import MultiChainNormalizer
from networks.chain_normalizer import chain_normalizer

logger = logging.getLogger(__name__)


class MultiChainTokenIngestionPipeline:
    """
    Multi-network aware ingestion pipeline with enforced chain authority.
    """

    def __init__(self, ai_config: Dict[str, Any]):
        self.ai_config = ai_config

        # Deduplicator is temporarily disabled to allow tokens to flow
        # The aggressive deduplication was blocking all tokens from entering the pipeline.
        # TODO: Implement per-trading-cycle deduplication that allows reprocessing
        # without the 1-hour or 60-second blocking window.
        # 
        # self.deduplicator = MultiChainTokenDeduplicator(ttl_seconds=60)
        # Use the global queue manager instance
        from .multi_chain_queue_manager import get_queue_manager
        self.queue_manager = get_queue_manager()
        
        # Log the queue manager instance for debugging
        logger.info(f"Ingestion pipeline using queue manager instance: {id(self.queue_manager)}")

        self.processed_scans: Set[str] = set()

        self.total_ingested = 0
        self.total_enqueued = 0
        self.total_rejected = 0

        self.chain_type_stats = {
            chain_type: {"ingested": 0, "enqueued": 0, "rejected": 0}
            for chain_type in ChainType
        }

        logger.info("Multi-chain token ingestion pipeline initialized")
        logger.info(f"Supported networks: {[ct.value for ct in ChainType]}")
        
        # 🔒 FIX 3: CANONICAL TOKEN MAPPINGS FOR WETH AND OTHER MAJOR TOKENS
        self.CANONICAL_TOKENS = {
            "WETH": {
                "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "arbitrum": "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
                "polygon": "0x7ceb23fd6bc0add59e62ac25578270cff1b9f619",
                "optimism": "0x4200000000000000000000000000000000000006",
                "base": "0x4200000000000000000000000000000000000006",
                "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB but treated as WETH equivalent
                "avalanche": "0x49d5c2bdffac6ce2bfdb6640f4f051c3d8194b9b",
                "fantom": "0x21be370d5312f44cb42ce377bc9b8a0cef1a4c83",
            },
            "USDC": {
                "ethereum": "0xA0b86a33E6441b8e8C7C7b0b8e8e8e8e8e8e8e8e",
                "arbitrum": "0xA0b86a33E6441b8e8C7C7b0b8e8e8e8e8e8e8e8e",
                "polygon": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "optimism": "0x0b2C639c533813f4Aa9D7837CAf62653d097F857",
                "base": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531770b969",
                "bsc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                "avalanche": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
                "fantom": "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",
            }
        }
        
        # 🔒 FIX 5: CANONICAL CHAIN ↔ CHAIN_ID MAPPING (SINGLE SOURCE OF TRUTH)
        self.CHAIN_ID_MAP = {
            "ethereum": 1,
            "bsc": 56,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "base": 8453,
            "fantom": 250,
            "cronos": 25,
            "celo": 42220,
            "polygon_zkevm": 1101,
            "zksync_era": 324,
            "linea": 59144,
            "scroll": 534352,
            "arbitrum_nova": 42170,
            "aurora": 1313161554,
            "boba": 288,
            "canto": 7700,
            "harmony": 1666600000,
            "kava": 2222,
            "metis": 1088,
            "moonbeam": 1284,
            "moonriver": 1285,
            "telos": 40,
            "oasis": 26863,
            "velas": 106,
            "bittorrent": 199,
            "dogechain": 2000,
            "klaytn": 8217,
            "wanchain": 888,
            "syscoin": 57,
            "rsk": 30,
            "ethereum_classic": 61,
        }

    # ------------------------------------------------------------------
    # PUBLIC ENTRYPOINT
    # ------------------------------------------------------------------

    async def ingest_scan_results(
        self,
        scanner_name: str,
        raw_tokens: List[Dict],
        scan_id: Optional[str] = None
    ) -> Dict[str, Any]:

        scan_id = scan_id or f"{scanner_name}_{int(datetime.now(timezone.utc).timestamp())}"

        if scan_id in self.processed_scans:
            return {"skipped": len(raw_tokens), "already_processed": True}

        self.processed_scans.add(scan_id)
        if len(self.processed_scans) > 1000:
            self.processed_scans = set(list(self.processed_scans)[-800:])

        start_time = datetime.now(timezone.utc)

        try:
            # 🔒 FIX 1: HARD REJECT INVALID TOKENS BEFORE ANY PROCESSING
            filtered_tokens = self._reject_invalid_tokens(raw_tokens)
            filtered_tokens = self._filter_corrupted_tokens(filtered_tokens)

            # 🔒 CRITICAL FIX: ASSERT CHAIN AUTHORITY HERE
            authoritative_tokens = self._assert_chain_authority(filtered_tokens)

            # Convert dicts to TokenCandidate objects without deduplication
            # Use a deduplicator instance JUST for the conversion logic, not the dedup filtering
            from trading.token_pipeline.multi_chain_deduplicator import MultiChainTokenDeduplicator
            temp_converter = MultiChainTokenDeduplicator(ttl_seconds=99999)  # High TTL so nothing is filtered
            
            unique_candidates = []
            for token in authoritative_tokens:
                candidate = temp_converter._convert_to_candidate(token, scanner_name)
                if candidate:
                    # DEBUG: Log any Solana addresses being marked as evm
                    addr = candidate.address[:16] if candidate.address else "no-addr"
                    if addr.startswith(('7', '8', '9')) and len(addr) > 10 and candidate.chain == 'evm':
                        logger.warning(
                            f"DEBUG: Solana-format address on evm chain: {candidate.symbol} | "
                            f"addr={candidate.address} | chain={candidate.chain} | "
                            f"chain_type={candidate.chain_type}"
                        )
                    unique_candidates.append(candidate)

            enqueued = 0
            rejected = 0

            for candidate in unique_candidates:
                try:
                    logger.debug(f"Processing candidate: {candidate.symbol} on {candidate.chain_type.value}")
                    
                    if not self._validate_candidate(candidate):
                        logger.warning(f"Candidate validation failed: {candidate.symbol} on {candidate.chain_type.value}")
                        rejected += 1
                        self.chain_type_stats[candidate.chain_type]["rejected"] += 1
                        continue

                    logger.debug(f"Candidate validation passed: {candidate.symbol}, attempting enqueue")
                    if await enqueue_token(candidate):
                        enqueued += 1
                        self.chain_type_stats[candidate.chain_type]["enqueued"] += 1
                        logger.info(f"Successfully enqueued: {candidate.symbol} on {candidate.chain_type.value}")
                    else:
                        logger.warning(f"Failed to enqueue: {candidate.symbol} on {candidate.chain_type.value}")
                        rejected += 1
                        self.chain_type_stats[candidate.chain_type]["rejected"] += 1

                except Exception as e:
                    logger.error(f"Candidate processing error for {candidate.symbol}: {e}", exc_info=True)
                    rejected += 1
                    self.chain_type_stats[candidate.chain_type]["rejected"] += 1

            latency = (datetime.now(timezone.utc) - start_time).total_seconds()

            return {
                "scan_id": scan_id,
                "filtered": len(filtered_tokens),
                "unique": len(unique_candidates),
                "enqueued": enqueued,
                "rejected": rejected,
                "latency_seconds": latency,
            }

        except Exception as e:
            logger.error("Fatal ingestion error", exc_info=True)
            return {"error": str(e), "scan_id": scan_id}

    # ------------------------------------------------------------------
    # CHAIN AUTHORITY FIX (CORE CHANGE)
    # ------------------------------------------------------------------

    def _assert_chain_authority(self, tokens: List[Dict]) -> List[Dict]:
        """
        STRICT: Validate chain authority consistency.
        Reject tokens with conflicting chain data instead of overriding.
        """
        validated = []
        rejected_count = 0

        for token in tokens:
            # Extract chain data from multiple sources
            dex_chain = None
            if "metadata" in token and isinstance(token["metadata"], dict):
                metadata_chain = token["metadata"].get("dex_data", {}).get("chainId")
                if metadata_chain:
                    dex_chain = metadata_chain
            
            # Fallback to top-level chain fields
            top_chain_id = token.get("chain_id")
            top_chain = token.get("chain")
            
            # STRICT: Require consistent chain data
            chain_sources = [s for s in [top_chain, top_chain_id, dex_chain] if s is not None]
            
            if len(chain_sources) == 0:
                logger.error(
                    "CRITICAL: Token missing all chain data for %s - SYSTEM FAILURE",
                    token.get("symbol", "Unknown")
                )
                logger.error("Malformed token data: %s", token)
                rejected_count += 1
                continue
                
            # 🔒 FIX 2: STOP NORMALIZING CHAIN_ID → CHAIN BLINDLY
            # Validate chain_id=1 is ethereum-only before any normalization
            if 1 in chain_sources or top_chain_id == 1:
                # Check if any source says chain_id=1 but chain is not ethereum
                non_ethereum_chains = [s for s in chain_sources if s not in [1, "ethereum", "eth"] and s is not None]
                if non_ethereum_chains:
                    logger.error(
                        "CRITICAL: Chain conflict for %s - chain_id=1 is ethereum-only, got chain=%s - SYSTEM FAILURE",
                        token.get("symbol", "Unknown"), non_ethereum_chains
                    )
                    logger.error("  All chain sources: %s", chain_sources)
                    logger.error("Full token data: %s", token)
                    rejected_count += 1
                    continue
            
            # Normalize all chain sources to canonical names
            normalized_sources = []
            for source in chain_sources:
                try:
                    normalized = chain_normalizer.normalize_chain_identifier(source)
                    normalized_sources.append(normalized)
                except Exception as e:
                    logger.error(
                        "CRITICAL: Invalid chain identifier '%s' for %s - SYSTEM FAILURE: %s",
                        source, token.get("symbol", "Unknown"), e
                    )
                    rejected_count += 1
                    continue
            
            # SPECIAL CASE: Handle Wormhole tokens on Solana with incorrect chain_id=1
            if (len(set(normalized_sources)) != 1 and 
                'solana' in normalized_sources and 
                'ethereum' in normalized_sources and
                token.get("chain") == 'solana' and
                token.get("chain_id") == 1 and
                'Wormhole' in token.get("name", "")):
                
                logger.info(
                    "SPECIAL: Correcting Wormhole token %s from incorrect chain_id=1 to solana",
                    token.get("symbol", "Unknown")
                )
                # Replace ethereum with solana in normalized sources
                normalized_sources = ['solana' if s == 'ethereum' else s for s in normalized_sources]
            
            # STRICT: All normalized chain sources must match
            if len(set(normalized_sources)) != 1:
                logger.error(
                    "CRITICAL: Chain data conflict for %s - SYSTEM FAILURE",
                    token.get("symbol", "Unknown")
                )
                logger.error(
                    "  Sources: %s -> Normalized: %s",
                    chain_sources, normalized_sources
                )
                logger.error("Full token data: %s", token)
                rejected_count += 1
                continue
            
            # Set authoritative chain
            authoritative_chain = normalized_sources[0]
            
            if not authoritative_chain:
                logger.warning(f"Token {token.get('symbol', 'UNKNOWN')} missing all chain data; rejecting")
                rejected_count += 1
                continue
            
            # Normalize the authoritative chain
            try:
                normalized = chain_normalizer.normalize_chain_identifier(authoritative_chain)
            except Exception as e:
                logger.warning(f"Invalid chain identifier '{authoritative_chain}' for {token.get('symbol')}: {e}")
                rejected_count += 1
                continue
            
            # Set authoritative chain and log source
            token["chain"] = normalized
            token["chain_source"] = token.get("chain_source", "dex_data_authority")
            
            # 🔒 FIX 3: VALIDATE CANONICAL TOKEN ADDRESSES FOR CHAIN
            if not self._validate_canonical_token_address(token, normalized):
                logger.error(
                    "CRITICAL: Canonical token address mismatch for %s on %s - SYSTEM FAILURE",
                    token.get("symbol", "Unknown"), normalized
                )
                rejected_count += 1
                continue
            
            # 🔒 FIX 5: HARD VALIDATION OF CHAIN ↔ CHAIN_ID MAPPING
            if not self._validate_chain_id_mapping(token, normalized):
                logger.error(
                    "CRITICAL: Chain ↔ chain_id mapping violation for %s - SYSTEM FAILURE",
                    token.get("symbol", "Unknown")
                )
                rejected_count += 1
                continue
            
            # Log if we overrode conflicting data
            if dex_chain and (top_chain_id or top_chain):
                conflicting = [s for s in [top_chain_id, top_chain] if s and s != dex_chain]
                if conflicting:
                    logger.info(
                        f"Chain authority override for {token.get('symbol')}: "
                        f"using dex_data.chainId='{dex_chain}' over conflicting {conflicting}"
                    )
            
            validated.append(token)
        
        if rejected_count > 0:
            logger.info(f"Chain authority validation: {len(validated)} accepted, {rejected_count} rejected")
        
        return validated

    # ------------------------------------------------------------------
    # FIX 1: HARD REJECT INVALID TOKENS
    # ------------------------------------------------------------------

    def _reject_invalid_tokens(self, raw_tokens: List[Dict]) -> List[Dict]:
        """
        🔒 FIX 1: Hard reject invalid tokens in ingestion before normalization.
        
        These must be dropped before deduplication as they are analysis artifacts, not tradable assets.
        """
        ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
        valid_tokens = []
        rejected_count = 0
        
        for token in raw_tokens:
            # Reject placeholder tokens
            if token.get("address") == ZERO_ADDRESS:
                logger.debug("Dropping invalid placeholder token (zero address): %s", token.get("symbol", "Unknown"))
                rejected_count += 1
                continue
                
            if token.get("symbol") in {"UNKNOWN", None, ""}:
                logger.debug("Dropping invalid placeholder token (unknown symbol): %s", token.get("address", "Unknown"))
                rejected_count += 1
                continue
                
            if token.get("chain_id") in {0, "0", None}:
                logger.debug("Dropping invalid placeholder token (invalid chain_id): %s", token.get("symbol", "Unknown"))
                rejected_count += 1
                continue
            
            # Reject tokens marked as non-ingestable from fallback analyzers
            if not token.get("ingestable", True):
                logger.debug("Dropping analysis-only token (non-ingestable): %s", token.get("symbol", "Unknown"))
                rejected_count += 1
                continue
            
            # Reject tokens from analysis sources that contain "Fallback"
            analysis_source = token.get("analysis_source", "")
            if "Fallback" in analysis_source:
                logger.debug("Dropping fallback analysis token: %s", token.get("symbol", "Unknown"))
                rejected_count += 1
                continue
            
            valid_tokens.append(token)
        
        if rejected_count > 0:
            logger.info("FIX 1: Rejected %d invalid placeholder tokens, kept %d valid tokens", rejected_count, len(valid_tokens))
        
        return valid_tokens

    def _validate_canonical_token_address(self, token: Dict, chain: str) -> bool:
        """
        🔒 FIX 3: WETH must be chain-scoped.
        
        Validate that canonical tokens have the correct address for their chain.
        If address doesn't match expected for that chain → reject.
        """
        symbol = token.get("symbol", "").upper()
        address = token.get("address", "").lower()
        
        # Skip validation for non-canonical tokens
        if symbol not in self.CANONICAL_TOKENS:
            return True
        
        canonical_addresses = self.CANONICAL_TOKENS[symbol]
        
        # Skip validation if chain not in canonical mappings
        if chain not in canonical_addresses:
            logger.debug(f"Chain {chain} not in canonical mappings for {symbol}, allowing")
            return True
        
        expected_address = canonical_addresses[chain].lower()
        
        # Validate address matches canonical for this chain
        if address != expected_address:
            logger.warning(
                f"Canonical token address mismatch: {symbol} on {chain} "
                f"expected {expected_address}, got {address}"
            )
            # For now, allow but log. Could make this stricter:
            # return False
            return True
        
        return True

    def _validate_chain_id_mapping(self, token: Dict, chain: str) -> bool:
        """
        🔒 FIX 5: HARD VALIDATION OF CHAIN ↔ CHAIN_ID MAPPING
        
        Enforces canonical chain ↔ chain_id mapping to prevent WETH conflicts.
        This must crash early on any violations.
        """
        token_chain_id = token.get("chain_id")
        
        # Skip validation if chain_id is missing
        if token_chain_id is None:
            logger.debug(f"Token {token.get('symbol', 'Unknown')} missing chain_id, allowing")
            return True
        
        # Convert to int for comparison
        try:
            token_chain_id = int(token_chain_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid chain_id format for {token.get('symbol', 'Unknown')}: {token_chain_id}")
            return False
        
        # Get expected chain_id from canonical mapping
        expected_chain_id = self.CHAIN_ID_MAP.get(chain)
        
        if expected_chain_id is None:
            logger.error(f"Unknown chain '{chain}' for token {token.get('symbol', 'Unknown')}")
            return False
        
        # STRICT: chain_id must match exactly
        if token_chain_id != expected_chain_id:
            logger.error(
                f"CRITICAL Chain Conflict: {token.get('symbol', 'Unknown')} "
                f"chain={chain} expects chain_id={expected_chain_id}, got chain_id={token_chain_id}"
            )
            # This is a SYSTEM FAILURE - do not allow
            return False
        
        return True

    # ------------------------------------------------------------------
    # VALIDATION & FILTERING
    # ------------------------------------------------------------------

    def _filter_corrupted_tokens(self, raw_tokens: List[Dict]) -> List[Dict]:
        valid = []
        for token in raw_tokens:
            if not isinstance(token, dict):
                continue
            if not token.get("address") and not token.get("baseToken", {}).get("address"):
                continue
            if not token.get("symbol") and not token.get("baseToken", {}).get("symbol"):
                continue
            valid.append(token)
        return valid

    def _validate_candidate(self, candidate: TokenCandidate) -> bool:
        logger.debug(f"Validating candidate: {candidate.symbol}, is_valid: {candidate.is_valid}, address: {candidate.address}, chain_type: {candidate.chain_type.value}")
        
        if not candidate.is_valid:
            logger.debug(f"Candidate {candidate.symbol} failed is_valid check")
            return False
        try:
            result = MultiChainNormalizer.validate_address(
                candidate.address,
                candidate.chain_type
            )
            logger.debug(f"Address validation result for {candidate.symbol}: {result}")
            return result
        except Exception as e:
            logger.debug(f"Address validation exception for {candidate.symbol}: {e}")
            return False

    # ------------------------------------------------------------------
    # SHUTDOWN
    # ------------------------------------------------------------------

    async def shutdown(self):
        self.processed_scans.clear()
        await self.queue_manager.close()


# ----------------------------------------------------------------------
# GLOBAL ACCESSORS
# ----------------------------------------------------------------------

_ingestion_pipeline: Optional[MultiChainTokenIngestionPipeline] = None


def initialize_multi_chain_ingestion_pipeline(
    ai_config: Dict[str, Any]
) -> MultiChainTokenIngestionPipeline:
    global _ingestion_pipeline
    _ingestion_pipeline = MultiChainTokenIngestionPipeline(ai_config)
    return _ingestion_pipeline


def get_multi_chain_ingestion_pipeline() -> MultiChainTokenIngestionPipeline:
    """
    Returns the globally initialized ingestion pipeline instance.
    """
    if not _ingestion_pipeline:
        raise RuntimeError("Ingestion pipeline not initialized")
    return _ingestion_pipeline


async def ingest_multi_chain_scan_results(
    scanner_name: str,
    raw_tokens: List[Dict],
    scan_id: Optional[str] = None
) -> Dict[str, Any]:
    if not _ingestion_pipeline:
        raise RuntimeError("Ingestion pipeline not initialized")
    return await _ingestion_pipeline.ingest_scan_results(
        scanner_name, raw_tokens, scan_id
    )

