"""
Address Validation Module
=========================

Strict address validation by chain type to prevent invalid token addresses.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AddressValidator:
    """
    Validates token addresses based on chain type.
    
    EVM chains require 0x-prefixed 40 hex characters.
    Solana requires base58 length 32-44 characters.
    """
    
    # EVM address pattern: 0x + 40 hex characters
    EVM_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
    
    # Solana address pattern: base58 characters, length 32-44
    SOLANA_ADDRESS_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
    
    # EVM chain list
    EVM_CHAINS = {
        "ethereum", "bsc", "arbitrum", "optimism", "base", "blast",
        "polygon", "avalanche", "fantom", "cronos", "gnosis", "celo",
        "moonbeam", "moonriver", "aurora", "harmony", "fuse", "metis",
        "boba", "kava", "zksync_era", "scroll", "linea", "mantle",
        "polygon_zkevm", "canto", "evmos", "arbitrum_nova", "astar",
        "iotex", "kcc", "theta", "okc", "heco", "oasis_emerald", "telos",
        # Additional chains from logs
        "zksync", "klaytn", "oasis", "syscoin", "velas", "thundercore",
        "palm", "manta", "polygonzkevm", "opbnb"
    }
    
    @staticmethod
    def validate_token_address(chain: str, address: str) -> bool:
        """
        Validate token address format based on chain type.
        
        Args:
            chain: Chain name (normalized)
            address: Token address string
            
        Returns:
            True if address format is valid for the chain, False otherwise
        """
        if not chain or not address:
            return False
            
        chain_lower = chain.lower()
        address_clean = address.strip()
        
        # EVM chains require 0x-prefixed hex addresses
        if chain_lower in AddressValidator.EVM_CHAINS:
            is_valid = bool(AddressValidator.EVM_ADDRESS_PATTERN.match(address_clean))
            if not is_valid:
                logger.warning(
                    "Invalid EVM address format for chain %s: %s", 
                    chain, address_clean
                )
            return is_valid
        
        # Solana requires base58 format
        elif chain_lower == "solana":
            is_valid = bool(AddressValidator.SOLANA_ADDRESS_PATTERN.match(address_clean))
            if not is_valid:
                logger.warning(
                    "Invalid Solana address format: %s", 
                    address_clean
                )
            return is_valid
        
        # Unknown chain - be permissive but log warning
        else:
            logger.warning(
                "Unknown chain %s for address validation, accepting address: %s",
                chain, address_clean
            )
            return True
    
    @staticmethod
    def is_evm_address(address: str) -> bool:
        """Check if address matches EVM format."""
        return bool(AddressValidator.EVM_ADDRESS_PATTERN.match(address.strip()))
    
    @staticmethod
    def is_solana_address(address: str) -> bool:
        """Check if address matches Solana format."""
        return bool(AddressValidator.SOLANA_ADDRESS_PATTERN.match(address.strip()))


# Global validator instance
address_validator = AddressValidator()


__all__ = [
    "AddressValidator",
    "address_validator",
]
