"""
Chain Constants Module

Provides chain metadata and safe lookup utilities.

This module is intentionally immutable and safe for production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping, Optional, TypedDict
from types import MappingProxyType


class ChainInfo(TypedDict):
    chain_id: int
    name: str
    is_testnet: bool


@dataclass(frozen=True)
class ChainMetadata:
    chain_id: int
    name: str
    is_testnet: bool


class ChainConstants:
    # Immutable chain definitions
    _NETWORKS: Final[Mapping[str, ChainInfo]] = MappingProxyType({
        # Mainnets (25)
        "ethereum": {"chain_id": 1, "name": "Ethereum", "is_testnet": False},
        "bsc": {"chain_id": 56, "name": "Binance Smart Chain", "is_testnet": False},
        "polygon": {"chain_id": 137, "name": "Polygon", "is_testnet": False},
        "arbitrum": {"chain_id": 42161, "name": "Arbitrum One", "is_testnet": False},
        "optimism": {"chain_id": 10, "name": "Optimism", "is_testnet": False},
        "avalanche": {"chain_id": 43114, "name": "Avalanche C-Chain", "is_testnet": False},
        "fantom": {"chain_id": 250, "name": "Fantom Opera", "is_testnet": False},
        "base": {"chain_id": 8453, "name": "Base", "is_testnet": False},
        "blast": {"chain_id": 81457, "name": "Blast", "is_testnet": False},
        "cronos": {"chain_id": 25, "name": "Cronos", "is_testnet": False},
        "gnosis": {"chain_id": 100, "name": "Gnosis Chain", "is_testnet": False},
        "celo": {"chain_id": 42220, "name": "Celo", "is_testnet": False},
        "moonbeam": {"chain_id": 1284, "name": "Moonbeam", "is_testnet": False},
        "moonriver": {"chain_id": 1285, "name": "Moonriver", "is_testnet": False},
        "aurora": {"chain_id": 1313161554, "name": "Aurora", "is_testnet": False},
        "harmony": {"chain_id": 1666600000, "name": "Harmony One", "is_testnet": False},
        "fuse": {"chain_id": 122, "name": "Fuse", "is_testnet": False},
        "metis": {"chain_id": 1088, "name": "Metis Andromeda", "is_testnet": False},
        "boba": {"chain_id": 288, "name": "Boba Network", "is_testnet": False},
        "kava": {"chain_id": 2222, "name": "Kava EVM", "is_testnet": False},
        "zksync": {"chain_id": 324, "name": "zkSync Era", "is_testnet": False},
        "scroll": {"chain_id": 534352, "name": "Scroll", "is_testnet": False},
        "linea": {"chain_id": 59144, "name": "Linea", "is_testnet": False},
        "mantle": {"chain_id": 5000, "name": "Mantle", "is_testnet": False},
        "polygon_zkevm": {"chain_id": 1101, "name": "Polygon zkEVM", "is_testnet": False},
        "canto": {"chain_id": 7700, "name": "Canto", "is_testnet": False},
        "evmos": {"chain_id": 9001, "name": "Evmos", "is_testnet": False},
        "arbitrum_nova": {"chain_id": 42170, "name": "Arbitrum Nova", "is_testnet": False},
        "astar": {"chain_id": 592, "name": "Astar", "is_testnet": False},
        "iotex": {"chain_id": 4689, "name": "IoTeX", "is_testnet": False},
        "kcc": {"chain_id": 321, "name": "KCC", "is_testnet": False},
        "theta": {"chain_id": 361, "name": "Theta Network", "is_testnet": False},
        "okc": {"chain_id": 66, "name": "OKX Chain", "is_testnet": False},
        "heco": {"chain_id": 128, "name": "Huobi ECO Chain", "is_testnet": False},
        "oasis_emerald": {"chain_id": 42262, "name": "Oasis Emerald", "is_testnet": False},
        "telos": {"chain_id": 40, "name": "Telos EVM", "is_testnet": False},
        # Additional chains from logs
        "klaytn": {"chain_id": 8217, "name": "Klaytn", "is_testnet": False},
        "oasis": {"chain_id": 43187, "name": "Oasis", "is_testnet": False},
        "syscoin": {"chain_id": 57, "name": "Syscoin", "is_testnet": False},
        "velas": {"chain_id": 106, "name": "Velas", "is_testnet": False},
        "thundercore": {"chain_id": 18, "name": "ThunderCore", "is_testnet": False},
        "palm": {"chain_id": 11297106, "name": "Palm", "is_testnet": False},
        "manta": {"chain_id": 169, "name": "Manta", "is_testnet": False},
        "polygonzkevm": {"chain_id": 1101, "name": "Polygon zkEVM", "is_testnet": False},
        "opbnb": {"chain_id": 197, "name": "opBNB", "is_testnet": False},
        "goerli": {"chain_id": 5, "name": "Goerli", "is_testnet": True},
        "sepolia": {"chain_id": 11155111, "name": "Sepolia", "is_testnet": True},
        "bsc_testnet": {"chain_id": 97, "name": "BSC Testnet", "is_testnet": True},
        "mumbai": {"chain_id": 80001, "name": "Mumbai", "is_testnet": True},
        "arbitrum_goerli": {"chain_id": 421613, "name": "Arbitrum Goerli", "is_testnet": True},
        "optimism_goerli": {"chain_id": 420, "name": "Optimism Goerli", "is_testnet": True},
        "avalanche_fuji": {"chain_id": 43113, "name": "Avalanche Fuji", "is_testnet": True},
        "fantom_testnet": {"chain_id": 4002, "name": "Fantom Testnet", "is_testnet": True},
        "base_goerli": {"chain_id": 84531, "name": "Base Goerli", "is_testnet": True},
        "scroll_sepolia": {"chain_id": 534351, "name": "Scroll Sepolia", "is_testnet": True},
    })

    @classmethod
    def _get_chain_id_to_name(cls) -> Mapping[int, str]:
        """Get reverse mapping of chain_id to name."""
        return MappingProxyType(
            {info["chain_id"]: name for name, info in cls._NETWORKS.items()}
        )

    @classmethod
    def get_chain_info(cls, chain: str) -> Optional[ChainMetadata]:
        chain_lower = chain.lower()
        info = cls._NETWORKS.get(chain_lower)
        if not info:
            return None
        return ChainMetadata(**info)

    @classmethod
    def get_chain_id(cls, chain: str) -> Optional[int]:
        info = cls.get_chain_info(chain)
        return info.chain_id if info else None

    @classmethod
    def get_chain_name(cls, chain: str) -> Optional[str]:
        info = cls.get_chain_info(chain)
        return info.name if info else None

    @classmethod
    def get_chain_by_id(cls, chain_id: int) -> Optional[str]:
        return cls._get_chain_id_to_name().get(chain_id)


# Convenience function for backward compatibility
def get_chain_id(chain: str) -> Optional[int]:
    """Get chain ID by chain name."""
    return ChainConstants.get_chain_id(chain)

