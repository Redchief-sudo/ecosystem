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

        self.deduplicator = MultiChainTokenDeduplicator()
        self.queue_manager = MultiChainQueueManager(
            max_queue_size=ai_config.get("max_queue_size", 1000)
        )

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
            filtered_tokens = self._filter_corrupted_tokens(raw_tokens)

            # 🔒 CRITICAL FIX: ASSERT CHAIN AUTHORITY HERE
            authoritative_tokens = self._assert_chain_authority(filtered_tokens)

            unique_candidates = self.deduplicator.add_tokens(
                authoritative_tokens,
                scanner_name
            )

            enqueued = 0
            rejected = 0

            for candidate in unique_candidates:
                try:
                    if not self._validate_candidate(candidate):
                        rejected += 1
                        self.chain_type_stats[candidate.chain_type]["rejected"] += 1
                        continue

                    if await enqueue_token(candidate):
                        enqueued += 1
                        self.chain_type_stats[candidate.chain_type]["enqueued"] += 1
                    else:
                        rejected += 1
                        self.chain_type_stats[candidate.chain_type]["rejected"] += 1

                except Exception as e:
                    rejected += 1
                    self.chain_type_stats[candidate.chain_type]["rejected"] += 1
                    logger.error(f"Candidate processing error: {e}", exc_info=True)

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
            
            # STRICT: All normalized chain sources must match
            if len(set(normalized_sources)) != 1:
                logger.error(
                    "CRITICAL: Chain data conflict for %s - SYSTEM FAILURE",
                    token.get("symbol", "Unknown")")
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
            token["chain_source"] = source_type
            
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
        if not candidate.is_valid:
            return False
        try:
            return MultiChainNormalizer.validate_address(
                candidate.address,
                candidate.chain_type
            )
        except Exception:
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

