"""
Multi-Chain Token Models
========================

Chain-aware token models that support EVM, Solana, Aptos, Sui, and other networks.
This replaces the EVM-centric approach with a truly multi-network architecture.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class ChainType(Enum):
    """Supported chain families."""
    EVM = "evm"
    SOLANA = "solana"
    APTOS = "aptos"
    SUI = "sui"
    COSMOS = "cosmos"
    BITCOIN = "bitcoin"


class AddressType(Enum):
    """Address formats by chain family."""
    EVM = "evm"           # 0x + 40 hex chars
    SOLANA = "solana"     # base58, 32-44 chars
    APTOS = "aptos"       # 0x + 64 hex chars
    SUI = "sui"           # 0x + 64 hex chars
    COSMOS = "cosmos"     # bech32 format
    BITCOIN = "bitcoin"   # base58, 26-35 chars


@dataclass(frozen=True)
class TokenIdentity:
    """
    Chain-aware token identifier that supports multiple networks.
    
    This replaces the EVM-centric approach with proper multi-network support.
    """
    chain: str                    # e.g., "ethereum", "solana", "aptos-mainnet"
    address: str                  # raw address from source
    address_type: AddressType     # normalized address type
    chain_type: ChainType         # chain family
    token_id: Optional[str] = None # for chains like Solana/Move that use token IDs
    
    def __post_init__(self):
        """Validate the token identity."""
        if not self.chain:
            raise ValueError("Chain cannot be empty")
        if not self.address:
            raise ValueError("Address cannot be empty")
        if not self.address_type:
            raise ValueError("Address type cannot be empty")
        if not self.chain_type:
            raise ValueError("Chain type cannot be empty")
    
    def get_dedup_key(self) -> str:
        """
        Generate a deduplication key that's chain-type aware.
        
        Format: chain_type:address_type:normalized_address:token_id
        """
        normalized_addr = self.normalize_address()
        token_id_part = f":{self.token_id}" if self.token_id else ""
        return f"{self.chain_type.value}:{self.address_type.value}:{normalized_addr}{token_id_part}"
    
    def normalize_address(self) -> str:
        """Normalize address based on its type."""
        if self.address_type == AddressType.EVM:
            return self.address.lower()
        elif self.address_type == AddressType.SOLANA:
            # Solana addresses are case-sensitive, return as-is
            return self.address
        elif self.address_type in (AddressType.APTOS, AddressType.SUI):
            return self.address.lower()
        else:
            # For other chains, return as-is for now
            return self.address
    
    def __hash__(self) -> int:
        """Hash based on dedup key for efficient storage."""
        return hash(self.get_dedup_key())
    
    def __eq__(self, other) -> bool:
        """Compare based on dedup key."""
        if not isinstance(other, TokenIdentity):
            return False
        return self.get_dedup_key() == other.get_dedup_key()


@dataclass
class TokenCandidate:
    """
    Multi-network token candidate that supports all chain types.
    
    This replaces the EVM-centric TokenCandidate with proper multi-network support.
    """
    # Core identity
    chain: str
    chain_type: ChainType
    address: str
    address_type: AddressType
    symbol: str
    name: str
    
    # Optional token ID for chains that use it
    token_id: Optional[str] = None
    
    # Market data (network-agnostic)
    price_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    
    # Chain-specific metadata
    decimals: Optional[int] = None
    pair_address: Optional[str] = None  # EVM-specific
    pool_id: Optional[str] = None       # Solana-specific
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Discovery metadata
    source: str = ""
    discovered_at: Optional[str] = None
    confidence: float = 0.0
    
    # Validation flags
    is_valid: bool = True
    validation_errors: list = field(default_factory=list)
    
    def __post_init__(self):
        """Validate the token candidate."""
        if not self.chain:
            self.validation_errors.append("Chain cannot be empty")
            self.is_valid = False
        
        if not self.address:
            self.validation_errors.append("Address cannot be empty")
            self.is_valid = False
        
        if not self.symbol:
            self.validation_errors.append("Symbol cannot be empty")
            self.is_valid = False
    
    def get_identity(self) -> TokenIdentity:
        """Get the token identity for deduplication."""
        return TokenIdentity(
            chain=self.chain,
            address=self.address,
            address_type=self.address_type,
            chain_type=self.chain_type,
            token_id=self.token_id
        )
    
    def is_evm(self) -> bool:
        """Check if this is an EVM token."""
        return self.chain_type == ChainType.EVM
    
    def is_solana(self) -> bool:
        """Check if this is a Solana token."""
        return self.chain_type == ChainType.SOLANA
    
    def is_aptos(self) -> bool:
        """Check if this is an Aptos token."""
        return self.chain_type == ChainType.APTOS
    
    def is_sui(self) -> bool:
        """Check if this is a Sui token."""
        return self.chain_type == ChainType.SUI
    
    def get_network_specific_data(self) -> Dict[str, Any]:
        """Get network-specific data for strategies and executors."""
        if self.is_evm():
            return {
                "pair_address": self.pair_address,
                "decimals": self.decimals or 18,
                "gas_estimated": False,
            }
        elif self.is_solana():
            return {
                "pool_id": self.pool_id,
                "decimals": self.decimals or 9,
                "token_account": None,  # To be filled by Solana-specific logic
            }
        elif self.is_aptos():
            return {
                "decimals": self.decimals or 8,
                "resource_address": self.address,
            }
        elif self.is_sui():
            return {
                "decimals": self.decimals or 9,
                "object_id": self.address,
            }
        else:
            return {}
    
    def get_dedup_key(self) -> str:
        """Get deduplication key."""
        return self.get_identity().get_dedup_key()


# Chain type mapping for common chains
CHAIN_TYPE_MAPPING = {
    # EVM chains
    "ethereum": ChainType.EVM,
    "bsc": ChainType.EVM,
    "polygon": ChainType.EVM,
    "arbitrum": ChainType.EVM,
    "optimism": ChainType.EVM,
    "base": ChainType.EVM,
    "blast": ChainType.EVM,
    "avalanche": ChainType.EVM,
    "fantom": ChainType.EVM,
    "cronos": ChainType.EVM,
    "gnosis": ChainType.EVM,
    "celo": ChainType.EVM,
    
    # Non-EVM chains
    "solana": ChainType.SOLANA,
    "aptos-mainnet": ChainType.APTOS,
    "aptos-testnet": ChainType.APTOS,
    "sui-mainnet": ChainType.SUI,
    "sui-testnet": ChainType.SUI,
    "cosmos-hub": ChainType.COSMOS,
    "osmosis": ChainType.COSMOS,
    "bitcoin": ChainType.BITCOIN,
}


def get_chain_type(chain: str) -> ChainType:
    """Get chain type for a given chain name."""
    return CHAIN_TYPE_MAPPING.get(chain.lower(), ChainType.EVM)  # Default to EVM for unknown


def detect_address_type(address: str) -> AddressType:
    """
    Detect address type from format.
    
    This is a fallback - ideally, chain type should be determined first.
    """
    import re
    
    if not address:
        return AddressType.EVM  # Default
    
    # EVM: 0x + 40 hex chars
    if re.match(r"^0x[a-fA-F0-9]{40}$", address):
        return AddressType.EVM
    
    # Solana: base58, 32-44 chars
    if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", address):
        return AddressType.SOLANA
    
    # Aptos/Sui: 0x + 64 hex chars
    if re.match(r"^0x[a-fA-F0-9]{64}$", address):
        return AddressType.APTOS  # Could also be Sui, need chain context
    
    # Bitcoin: base58, 26-35 chars, starts with 1, 3, or bc1
    if (re.match(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$", address) or
        re.match(r"^bc1[a-z0-9]{39,59}$", address)):
        return AddressType.BITCOIN
    
    # Default to EVM for unknown formats
    return AddressType.EVM


__all__ = [
    "ChainType",
    "AddressType", 
    "TokenIdentity",
    "TokenCandidate",
    "get_chain_type",
    "detect_address_type",
    "CHAIN_TYPE_MAPPING",
]
