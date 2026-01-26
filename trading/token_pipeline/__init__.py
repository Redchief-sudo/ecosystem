"""
Token Pipeline Module
====================
Complete token processing pipeline for the trading system.

Handles the entire token lifecycle:
- Token ingestion from scanners
- Normalization and validation  
- Deduplication and registry management
- Candidate creation and queuing
- Dead letter queue handling
- Multi-chain support (NEW)
"""

# Legacy components (EVM-only)
from .token_candidate import TokenCandidate as LegacyTokenCandidate, create_token_candidate
from .token_deduplicator import TokenDeduplicator, TokenIdentifier
from .multi_chain_ingestion import MultiChainTokenIngestionPipeline as TokenIngestionPipeline, get_multi_chain_ingestion_pipeline as get_ingestion_pipeline, initialize_multi_chain_ingestion_pipeline as initialize_ingestion_pipeline, ingest_multi_chain_scan_results as ingest_scan_results
from .token_normalizer import TokenNormalizer
from .token_registry import TokenRegistry, AddressType as LegacyAddressType, ResolutionStatus
from .token_validator import TokenMetadata, TokenStandard, validate_token_data
from .dead_letter_queue import get_dead_letter_queue

# New multi-chain components
from .multi_chain_deduplicator import MultiChainTokenDeduplicator, multi_chain_deduplicator
from .multi_chain_ingestion import (
    MultiChainTokenIngestionPipeline,
    get_multi_chain_ingestion_pipeline,
    initialize_multi_chain_ingestion_pipeline,
    ingest_multi_chain_scan_results
)
from .multi_chain_queue_manager import (
    MultiChainQueueManager,
    get_queue_manager,
    initialize_queue_manager,
    enqueue_token,
    dequeue_token,
    dequeue_any_token
)

__all__ = [
    # Core pipeline components
    'TokenIngestionPipeline',
    'TokenNormalizer', 
    'TokenCandidate',
    
    # Token utilities
    'TokenRegistry',
    'TokenDeduplicator',
    'TokenValidator',
    
    # Data structures
    'TokenIdentifier',
    'TokenMetadata',
    'TokenStandard',
    'AddressType',
    'ResolutionStatus',
    
    # Pipeline functions
    'get_ingestion_pipeline',
    'initialize_ingestion_pipeline',
    'ingest_scan_results',
    'create_token_candidate',
    'validate_token_data',
    
    # Error handling
    'get_dead_letter_queue',
    
    # New multi-chain components
    'MultiChainTokenDeduplicator',
    'multi_chain_deduplicator',
    'MultiChainTokenIngestionPipeline',
    'get_multi_chain_ingestion_pipeline',
    'initialize_multi_chain_ingestion_pipeline',
    'ingest_multi_chain_scan_results',
    'MultiChainQueueManager',
    'get_queue_manager',
    'initialize_queue_manager',
    'enqueue_token',
    'dequeue_token',
    'dequeue_any_token',
    
    # Legacy compatibility
    'LegacyTokenCandidate',
    'LegacyAddressType',
]
