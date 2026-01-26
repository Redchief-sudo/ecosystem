"""
Chain-Specific Address Normalizers
==================================

Normalizes and validates addresses for different chain families.
This replaces the EVM-centric validation with proper multi-network support.
"""

import re
import logging
from typing import Optional, Tuple

from .multi_chain_models import ChainType, AddressType

logger = logging.getLogger(__name__)


class ChainNormalizer:
    """Base class for chain-specific address normalizers."""
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize address according to chain rules."""
        raise NotImplementedError
    
    @staticmethod
    def validate(address: str) -> bool:
        """Validate address format."""
        raise NotImplementedError
    
    @staticmethod
    def get_address_type() -> AddressType:
        """Get the address type this normalizer handles."""
        raise NotImplementedError


class EVMNormalizer(ChainNormalizer):
    """Normalizer for EVM chains (Ethereum, BSC, Polygon, etc.)."""
    
    EVM_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize EVM address to lowercase."""
        if not EVMNormalizer.validate(address):
            raise ValueError(f"Invalid EVM address format: {address}")
        return address.lower()
    
    @staticmethod
    def validate(address: str) -> bool:
        """Validate EVM address format."""
        if not address or not isinstance(address, str):
            return False
        return bool(EVMNormalizer.EVM_ADDRESS_PATTERN.match(address.strip()))
    
    @staticmethod
    def get_address_type() -> AddressType:
        return AddressType.EVM


class SolanaNormalizer(ChainNormalizer):
    """Normalizer for Solana addresses."""
    
    SOLANA_ADDRESS_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize Solana address (case-sensitive, return as-is)."""
        if not SolanaNormalizer.validate(address):
            raise ValueError(f"Invalid Solana address format: {address}")
        return address.strip()  # Solana addresses are case-sensitive
    
    @staticmethod
    def validate(address: str) -> bool:
        """Validate Solana address format."""
        if not address or not isinstance(address, str):
            return False
        return bool(SolanaNormalizer.SOLANA_ADDRESS_PATTERN.match(address.strip()))
    
    @staticmethod
    def get_address_type() -> AddressType:
        return AddressType.SOLANA


class AptosNormalizer(ChainNormalizer):
    """Normalizer for Aptos addresses."""
    
    APTOS_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize Aptos address to lowercase."""
        if not AptosNormalizer.validate(address):
            raise ValueError(f"Invalid Aptos address format: {address}")
        return address.lower()
    
    @staticmethod
    def validate(address: str) -> bool:
        """Validate Aptos address format."""
        if not address or not isinstance(address, str):
            return False
        return bool(AptosNormalizer.APTOS_ADDRESS_PATTERN.match(address.strip()))
    
    @staticmethod
    def get_address_type() -> AddressType:
        return AddressType.APTOS


class SuiNormalizer(ChainNormalizer):
    """Normalizer for Sui addresses."""
    
    SUI_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize Sui address to lowercase."""
        if not SuiNormalizer.validate(address):
            raise ValueError(f"Invalid Sui address format: {address}")
        return address.lower()
    
    @staticmethod
    def validate(address: str) -> bool:
        """Validate Sui address format."""
        if not address or not isinstance(address, str):
            return False
        return bool(SuiNormalizer.SUI_ADDRESS_PATTERN.match(address.strip()))
    
    @staticmethod
    def get_address_type() -> AddressType:
        return AddressType.SUI


class CosmosNormalizer(ChainNormalizer):
    """Normalizer for Cosmos SDK chains."""
    
    # Basic bech32 pattern (simplified - full validation is complex)
    BECH32_PATTERN = re.compile(r"^[a-z]{1,10}1[ac-hj-np-z02-9]{39,59}$")
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize Cosmos address (case-sensitive)."""
        if not CosmosNormalizer.validate(address):
            raise ValueError(f"Invalid Cosmos address format: {address}")
        return address.strip().lower()  # Bech32 is case-insensitive in practice
    
    @staticmethod
    def validate(address: str) -> bool:
        """Validate Cosmos address format."""
        if not address or not isinstance(address, str):
            return False
        return bool(CosmosNormalizer.BECH32_PATTERN.match(address.strip()))
    
    @staticmethod
    def get_address_type() -> AddressType:
        return AddressType.COSMOS


class BitcoinNormalizer(ChainNormalizer):
    """Normalizer for Bitcoin addresses."""
    
    # Legacy addresses (base58)
    LEGACY_PATTERN = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")
    # SegWit addresses (bech32)
    SEGWIT_PATTERN = re.compile(r"^bc1[a-z0-9]{39,59}$")
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize Bitcoin address."""
        if not BitcoinNormalizer.validate(address):
            raise ValueError(f"Invalid Bitcoin address format: {address}")
        return address.strip()
    
    @staticmethod
    def validate(address: str) -> bool:
        """Validate Bitcoin address format."""
        if not address or not isinstance(address, str):
            return False
        addr = address.strip()
        return (bool(BitcoinNormalizer.LEGACY_PATTERN.match(addr)) or 
                bool(BitcoinNormalizer.SEGWIT_PATTERN.match(addr)))
    
    @staticmethod
    def get_address_type() -> AddressType:
        return AddressType.BITCOIN


class MultiChainNormalizer:
    """
    Factory that provides the appropriate normalizer for each chain type.
    This is the main entry point for address normalization.
    """
    
    _normalizers = {
        ChainType.EVM: EVMNormalizer(),
        ChainType.SOLANA: SolanaNormalizer(),
        ChainType.APTOS: AptosNormalizer(),
        ChainType.SUI: SuiNormalizer(),
        ChainType.COSMOS: CosmosNormalizer(),
        ChainType.BITCOIN: BitcoinNormalizer(),
    }
    
    @classmethod
    def get_normalizer(cls, chain_type: ChainType) -> ChainNormalizer:
        """Get the appropriate normalizer for a chain type."""
        normalizer = cls._normalizers.get(chain_type)
        if not normalizer:
            raise ValueError(f"No normalizer available for chain type: {chain_type}")
        return normalizer
    
    @classmethod
    def get_chain_type(cls, chain: str) -> ChainType:
        """Get chain type from chain name."""
        # Map chain names to chain types
        chain_type_mapping = {
            # EVM chains
            'ethereum': ChainType.EVM, 'eth': ChainType.EVM, 'mainnet': ChainType.EVM,
            'bsc': ChainType.EVM, 'binance_smart_chain': ChainType.EVM, 'bnb_chain': ChainType.EVM,
            'polygon': ChainType.EVM, 'matic': ChainType.EVM, 'polygon_pos': ChainType.EVM,
            'arbitrum': ChainType.EVM, 'arb': ChainType.EVM, 'arbitrum_one': ChainType.EVM,
            'optimism': ChainType.EVM, 'op': ChainType.EVM, 'optimism_mainnet': ChainType.EVM,
            'base': ChainType.EVM, 'base_mainnet': ChainType.EVM,
            'blast': ChainType.EVM, 'blast_mainnet': ChainType.EVM,
            'avalanche': ChainType.EVM, 'avax': ChainType.EVM, 'avalanche_c_chain': ChainType.EVM,
            'fantom': ChainType.EVM, 'ftm': ChainType.EVM, 'fantom_opera': ChainType.EVM,
            'cronos': ChainType.EVM, 'cro': ChainType.EVM, 'cronos_mainnet': ChainType.EVM,
            'celo': ChainType.EVM, 'celo_mainnet': ChainType.EVM,
            'gnosis': ChainType.EVM, 'xdai': ChainType.EVM, 'gnosis_chain': ChainType.EVM,
            'linea': ChainType.EVM, 'linea_mainnet': ChainType.EVM,
            'scroll': ChainType.EVM, 'scroll_mainnet': ChainType.EVM,
            'mantle': ChainType.EVM, 'mantle_mainnet': ChainType.EVM,
            'zksync': ChainType.EVM, 'zksync_era': ChainType.EVM,
            
            # Non-EVM chains
            'solana': ChainType.SOLANA,
            'aptos': ChainType.APTOS,
            'sui': ChainType.SUI,
            'cosmos': ChainType.COSMOS,
            'osmosis': ChainType.COSMOS,
            'cardano': ChainType.BITCOIN,
            'polkadot': ChainType.BITCOIN,
            'near': ChainType.BITCOIN,
            'tron': ChainType.BITCOIN,
            'stellar': ChainType.BITCOIN,
            'algorand': ChainType.BITCOIN,
            'tezos': ChainType.BITCOIN,
            'hedera': ChainType.BITCOIN,
            'flow': ChainType.BITCOIN,
            'elrond': ChainType.BITCOIN,
            'acala': ChainType.COSMOS,
            'stacks': ChainType.BITCOIN,
            'starknet': ChainType.EVM,
            'thorchain': ChainType.COSMOS,
            'ton': ChainType.BITCOIN,
            'xrpl': ChainType.BITCOIN,
            'bitcoin': ChainType.BITCOIN,
        }
        
        normalized = chain.lower().strip()
        return chain_type_mapping.get(normalized, ChainType.EVM)  # Default to EVM
    
    @classmethod
    def normalize_address(cls, address: str, chain_type: ChainType) -> str:
        """Normalize address using the appropriate normalizer."""
        normalizer = cls.get_normalizer(chain_type)
        return normalizer.normalize(address)
    
    @classmethod
    def validate_address(cls, address: str, chain_type: ChainType) -> bool:
        """Validate address using the appropriate normalizer."""
        try:
            normalizer = cls.get_normalizer(chain_type)
            return normalizer.validate(address)
        except ValueError:
            return False
    
    @classmethod
    def detect_and_normalize(cls, address: str, chain: str) -> Tuple[str, ChainType, AddressType]:
        """
        STRICT: Detect chain type and normalize address without fallbacks.
        Reject mismatched address formats instead of trying to fix them.
        """
        if not address or not chain:
            raise ValueError("Address and chain are required")
        
        # Get expected chain type from chain name
        try:
            chain_type = cls.get_chain_type(chain)
        except ValueError:
            raise ValueError(f"Unsupported chain: {chain}")
        
        # Validate address format matches expected chain type
        if not cls.validate_address(address, chain_type):
            detected_address_type = detect_address_type(address)
            
            # STRICT: Reject instead of trying to fix
            raise ValueError(
                f"Address format mismatch for chain {chain}. "
                f"Expected {chain_type.value} format, detected {detected_address_type.value}. "
                f"Address: {address[:10]}..."
            )
        
        # Normalize address for the correct chain type
        normalizer = cls.get_normalizer(chain_type)
        normalized = normalizer.normalize(address)
        return normalized, chain_type, normalizer.get_address_type()


# Convenience functions
def normalize_address(address: str, chain_type: ChainType) -> str:
    """Normalize address for the given chain type."""
    return MultiChainNormalizer.normalize_address(address, chain_type)


def validate_address(address: str, chain_type: ChainType) -> bool:
    """Validate address for the given chain type."""
    return MultiChainNormalizer.validate_address(address, chain_type)


def detect_and_normalize_address(address: str, chain: str) -> Tuple[str, ChainType, AddressType]:
    """Detect chain type and normalize address."""
    return MultiChainNormalizer.detect_and_normalize(address, chain)


__all__ = [
    "ChainNormalizer",
    "EVMNormalizer",
    "SolanaNormalizer", 
    "AptosNormalizer",
    "SuiNormalizer",
    "CosmosNormalizer",
    "BitcoinNormalizer",
    "MultiChainNormalizer",
    "normalize_address",
    "validate_address",
    "detect_and_normalize_address",
]
