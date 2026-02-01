from .chain_capabilities import (
    get_chain_capabilities,
    supports_filters,
    supports_mempool,
    supports_websocket,
    get_recommended_rpcs,
    get_limitations
)

from .chain_constants import ChainConstants, get_chain_id
from .chain_execution_policy import ChainExecutionPolicy, chain_execution_policy
from .chain_normalizer import ChainNormalizer, chain_normalizer
from .cross_chain_mapper import CrossChainAddressMapper
from .network_verifier import NetworkVerifier
from .universal_network_manager import UniversalNetworkManager

# Alias for tests expecting NetworkManager
NetworkManager = UniversalNetworkManager

# New multi-chain components
from .multi_chain_models import (
    ChainType,
    AddressType,
    TokenIdentity,
    TokenCandidate,
    get_chain_type,
    detect_address_type,
    CHAIN_TYPE_MAPPING
)

from .chain_normalizers import (
    AddressNormalizer,
    EVMNormalizer,
    SolanaNormalizer,
    AptosNormalizer,
    SuiNormalizer,
    CosmosNormalizer,
    BitcoinNormalizer,
    normalize_address,
    validate_address,
    detect_and_normalize_address
)

from .address_validator import AddressValidator, address_validator

__all__ = [
    'get_chain_capabilities',
    'supports_filters',
    'supports_mempool',
    'supports_websocket',
    'get_recommended_rpcs',
    'get_limitations',
    'ChainConstants',
    'get_chain_id',
    'ChainExecutionPolicy',
    'chain_execution_policy',
    'ChainNormalizer',
    'chain_normalizer',
    'CrossChainAddressMapper',
    'NetworkVerifier',
    'UniversalNetworkManager',
    'NetworkManager',
    # New multi-chain exports
    'ChainType',
    'AddressType',
    'TokenIdentity',
    'TokenCandidate',
    'get_chain_type',
    'detect_address_type',
    'CHAIN_TYPE_MAPPING',
    'AddressNormalizer',
    'EVMNormalizer',
    'SolanaNormalizer',
    'AptosNormalizer',
    'SuiNormalizer',
    'CosmosNormalizer',
    'BitcoinNormalizer',
    'normalize_address',
    'validate_address',
    'detect_and_normalize_address',
    'AddressValidator',
    'address_validator'
]
