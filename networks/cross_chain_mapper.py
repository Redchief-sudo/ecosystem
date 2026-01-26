#!/usr/bin/env python3
"""
Cross-chain address mapping utilities.
Maps non-EVM addresses to their EVM equivalents when available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set
from threading import Lock

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None

logger = logging.getLogger(__name__)


class ChainType(Enum):
    EVM = "evm"
    SOLANA = "solana"
    OSMOSIS = "osmosis"
    IBC = "ibc"
    TRON = "tron"
    COSMOS = "cosmos"
    OTHER = "other"


@dataclass
class AddressMapping:
    """Maps a token across different chains."""
    symbol: str
    name: str
    evm_address: Optional[str] = None
    solana_address: Optional[str] = None
    osmosis_address: Optional[str] = None
    ibc_address: Optional[str] = None
    tron_address: Optional[str] = None
    cosmos_address: Optional[str] = None

    def __post_init__(self):
        """Normalize EVM addresses to checksum format if possible."""
        if self.evm_address:
            self.evm_address = self.evm_address.strip()
            if WEB3_AVAILABLE:
                self.evm_address = Web3.to_checksum_address(self.evm_address)

    def get_address_for_chain(self, chain: str) -> Optional[str]:
        """Get the appropriate address for a given chain."""
        chain_lower = chain.strip().lower()

        if chain_lower in EVM_CHAIN_ALIASES:
            return self.evm_address
        elif chain_lower == "solana":
            return self.solana_address
        elif chain_lower == "osmosis":
            return self.osmosis_address
        elif chain_lower.startswith("ibc"):
            return self.ibc_address
        elif chain_lower == "tron":
            return self.tron_address
        elif chain_lower in {"cosmos", "injective", "juno"}:
            return self.cosmos_address
        return None

    def get_evm_equivalent(self, current_address: str, current_chain: str) -> Optional[str]:
        """
        Get the EVM address for a token given its address on another chain.

        Returns EVM address only if the provided address matches the mapping.
        """
        current_address = (current_address or "").strip()
        chain_lower = (current_chain or "").strip().lower()

        if chain_lower in EVM_CHAIN_ALIASES:
            return current_address if current_address.startswith("0x") and len(current_address) == 42 else None

        if chain_lower == "solana" and self.solana_address == current_address:
            return self.evm_address
        if chain_lower == "osmosis" and self.osmosis_address == current_address:
            return self.evm_address
        if chain_lower.startswith("ibc") and self.ibc_address == current_address:
            return self.evm_address
        if chain_lower == "tron" and self.tron_address == current_address:
            return self.evm_address
        if chain_lower in {"cosmos", "injective", "juno"} and self.cosmos_address == current_address:
            return self.evm_address

        return None


# EVM aliases for chain detection
EVM_CHAIN_ALIASES: Set[str] = {
    "ethereum", "bsc", "polygon", "arbitrum", "avalanche", "fantom",
    "optimism", "base", "gnosis", "celo", "moonbeam", "moonriver",
    "aurora", "harmony", "cronos", "kava", "metis", "canto", "boba",
    "linea", "scroll", "zksync_era", "mantle", "polygon_zkevm",
    "arbitrum_nova", "okc", "kcc"
}


class CrossChainAddressMapper:
    """Manages cross-chain address mappings."""

    def __init__(self, silent_warnings: bool = False):
        self.mappings: Dict[str, AddressMapping] = {}
        self.silent_warnings = silent_warnings
        self._logged_missing_tokens: Set[str] = set()
        self._lock = Lock()
        self._initialize_common_mappings()

    def _initialize_common_mappings(self):
        """Initialize common token mappings."""
        common_tokens = [
            AddressMapping(
                symbol="USDT",
                name="Tether USD",
                evm_address="0xdAC17F958D2ee523a2206206994597C13D831ec7",
                solana_address="Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
                tron_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
            ),
            AddressMapping(
                symbol="USDC",
                name="USD Coin",
                evm_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                solana_address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            ),
            AddressMapping(
                symbol="ETH",
                name="Ethereum",
                evm_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                solana_address="So11111111111111111111111111111111111111112"
            ),
            AddressMapping(
                symbol="BTC",
                name="Bitcoin",
                evm_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                solana_address="9n4nbM75f5Ui33ZbPYXn59EwKSgE2Ck4LrtQh8LeMva"
            ),
            AddressMapping(
                symbol="DAI",
                name="Dai Stablecoin",
                evm_address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                solana_address="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
            ),
            AddressMapping(
                symbol="LINK",
                name="Chainlink",
                evm_address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
                solana_address="CzAjYN8i6TqTeJz9FwJTPZRrSuhmz7mqUgG4biVts9V"
            ),
            AddressMapping(
                symbol="WBTC",
                name="Wrapped Bitcoin",
                evm_address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                solana_address="9n4nbM75f5Ui33ZbPYXn59EwKSgE2Ck4LrtQh8LeMva"
            ),
        ]

        for mapping in common_tokens:
            self.add_mapping(mapping)

    def add_mapping(self, mapping: AddressMapping):
        """Add a new address mapping."""
        with self._lock:
            self.mappings[mapping.symbol.upper()] = mapping

    def get_evm_address(self, symbol: str, current_address: str, current_chain: str) -> Optional[str]:
        """Get the EVM address for a token."""
        symbol_upper = symbol.upper()

        if symbol_upper not in self.mappings:
            if not self.silent_warnings and symbol_upper not in self._logged_missing_tokens:
                logger.warning("No mapping found for token: %s", symbol)
                self._logged_missing_tokens.add(symbol_upper)
            return None

        mapping = self.mappings[symbol_upper]
        evm_address = mapping.get_evm_equivalent(current_address, current_chain)

        if evm_address:
            logger.info("Found EVM address for %s: %s", symbol, evm_address)
        else:
            if not self.silent_warnings:
                logger.warning("No EVM address found for %s on %s", symbol, current_chain)

        return evm_address

    def get_evm_from_any_address(self, address: str) -> Optional[str]:
        """Find EVM equivalent from any non-EVM address."""
        address = (address or "").strip()
        for mapping in self.mappings.values():
            if address in {
                mapping.solana_address,
                mapping.osmosis_address,
                mapping.ibc_address,
                mapping.tron_address,
                mapping.cosmos_address,
            }:
                return mapping.evm_address
        return None

    def map_address_to_evm(self, address: str, chain: str, symbol: str = None) -> Optional[str]:
        """Map any address to its EVM equivalent."""
        address = (address or "").strip()
        chain_lower = (chain or "").strip().lower()

        # If it's already an EVM address, return it
        if address.startswith("0x") and len(address) == 42:
            return address

        # If we have a symbol, try to find mapping
        if symbol:
            return self.get_evm_address(symbol, address, chain_lower)

        # Try to find by address matching
        for mapping in self.mappings.values():
            evm_address = mapping.get_evm_equivalent(address, chain_lower)
            if evm_address:
                return evm_address

        if not self.silent_warnings:
            logger.warning("No EVM mapping found for address %s on %s", address, chain)
        return None

    def is_supported_token(self, symbol: str) -> bool:
        """Check if a token is supported for cross-chain mapping."""
        return symbol.upper() in self.mappings

    def get_all_mappings(self) -> List[AddressMapping]:
        """Get all address mappings."""
        return list(self.mappings.values())


# Global instance
address_mapper = CrossChainAddressMapper()


def get_evm_address(address: str, chain: str, symbol: str = None) -> Optional[str]:
    """
    Convenience function to get EVM address for any token.

    Args:
        address: Current token address (can be non-EVM)
        chain: Current chain name
        symbol: Token symbol (optional, helps with mapping)

    Returns:
        EVM-compatible address or None if not found
    """
    return address_mapper.map_address_to_evm(address, chain, symbol)

