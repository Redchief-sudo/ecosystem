"""
Chain capability definitions for RPC method support across different networks.

This replaces assumptions about what chains support which Web3 methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, TypedDict
from functools import lru_cache


class ChainCapabilities(TypedDict):
    supports_filters: bool
    supports_mempool: bool
    supports_websocket: bool
    supports_onchain_scanning: bool
    recommended_rpcs: List[str]
    public_rpc_limitations: List[str]


BASE_CAPABILITIES: Dict[str, ChainCapabilities] = {
    "standard_evm": {
        "supports_filters": True,
        "supports_mempool": True,
        "supports_websocket": True,
        "supports_onchain_scanning": True,
        "recommended_rpcs": ["premium"],
        "public_rpc_limitations": ["rate_limited"],
    },
    "optimistic_rollup": {
        "supports_filters": False,
        "supports_mempool": False,
        "supports_websocket": True,
        "supports_onchain_scanning": True,
        "recommended_rpcs": ["premium"],
        "public_rpc_limitations": ["filters_disabled", "mempool_disabled"],
    },
    "zk_rollup": {
        "supports_filters": False,
        "supports_mempool": False,
        "supports_websocket": True,
        "supports_onchain_scanning": True,
        "recommended_rpcs": ["premium"],
        "public_rpc_limitations": [
            "filters_disabled",
            "mempool_disabled",
            "events_limited",
        ],
    },
    "testnet": {
        "supports_filters": True,
        "supports_mempool": True,
        "supports_websocket": True,
        "supports_onchain_scanning": True,
        "recommended_rpcs": ["public"],
        "public_rpc_limitations": ["rate_limited", "unstable"],
    },
}


def _clone_capabilities(cap: ChainCapabilities) -> ChainCapabilities:
    """Return a deep copy to prevent shared mutable state."""
    return {
        "supports_filters": cap["supports_filters"],
        "supports_mempool": cap["supports_mempool"],
        "supports_websocket": cap["supports_websocket"],
        "supports_onchain_scanning": cap["supports_onchain_scanning"],
        "recommended_rpcs": list(cap["recommended_rpcs"]),
        "public_rpc_limitations": list(cap["public_rpc_limitations"]),
    }


CHAIN_CAPABILITIES: Dict[str, ChainCapabilities] = {
    # Standard EVM chains
    "ethereum": {**_clone_capabilities(BASE_CAPABILITIES["standard_evm"]), "recommended_rpcs": ["premium", "archive"]},
    "bsc": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "polygon": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "avalanche": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "fantom": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "cronos": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "gnosis_chain": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "celo": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "moonbeam": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "moonriver": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "aurora": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "harmony": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "fuse": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "metis": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "boba": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "kava": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "canto": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "evmos": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "astar": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "iotex": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),
    "kcc": _clone_capabilities(BASE_CAPABILITIES["standard_evm"]),

    # Optimistic rollups
    "arbitrum": {**_clone_capabilities(BASE_CAPABILITIES["optimistic_rollup"]), "recommended_rpcs": ["premium", "archive"]},
    "optimism": _clone_capabilities(BASE_CAPABILITIES["optimistic_rollup"]),
    "base": _clone_capabilities(BASE_CAPABILITIES["optimistic_rollup"]),
    "arbitrum_nova": _clone_capabilities(BASE_CAPABILITIES["optimistic_rollup"]),

    # ZK rollups
    "zksync_era": _clone_capabilities(BASE_CAPABILITIES["zk_rollup"]),
    "scroll": _clone_capabilities(BASE_CAPABILITIES["zk_rollup"]),
    "linea": _clone_capabilities(BASE_CAPABILITIES["zk_rollup"]),
    "polygon_zkevm": _clone_capabilities(BASE_CAPABILITIES["zk_rollup"]),

    # Testnets
    "goerli": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "sepolia": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "bsc_testnet": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "mumbai": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "arbitrum_goerli": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "optimism_goerli": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "avalanche_fuji": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "fantom_testnet": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "base_goerli": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "chiado": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "celo_alfajores": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "moonbase_alpha": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "aurora_testnet": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "harmony_testnet": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "metis_goerli": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "boba_rinkeby": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "zksync_goerli": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "scroll_sepolia": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "linea_goerli": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "mantle_testnet": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
    "polygon_zkevm_testnet": _clone_capabilities(BASE_CAPABILITIES["testnet"]),
}


@lru_cache(maxsize=256)
def get_chain_capabilities(chain: str, raise_on_missing: bool = False) -> ChainCapabilities:
    """
    Get capabilities for a specific chain.

    Args:
        chain: The chain name or identifier (case-insensitive)
        raise_on_missing: If True, raise ValueError on unknown chain

    Returns:
        Dict containing the chain's capabilities
    """
    chain_lower = chain.lower()
    if chain_lower in CHAIN_CAPABILITIES:
        return _clone_capabilities(CHAIN_CAPABILITIES[chain_lower])

    if raise_on_missing:
        raise ValueError(f"Unsupported chain: {chain}")

    return {
        "supports_filters": False,
        "supports_mempool": False,
        "supports_websocket": False,
        "supports_onchain_scanning": False,
        "recommended_rpcs": [],
        "public_rpc_limitations": ["unsupported_chain"],
    }


def supports_filters(chain: str) -> bool:
    return get_chain_capabilities(chain).get("supports_filters", False)


def supports_mempool(chain: str) -> bool:
    return get_chain_capabilities(chain).get("supports_mempool", False)


def supports_websocket(chain: str) -> bool:
    return get_chain_capabilities(chain).get("supports_websocket", False)


def get_recommended_rpcs(chain: str) -> List[str]:
    return list(get_chain_capabilities(chain).get("recommended_rpcs", []))


def get_limitations(chain: str) -> List[str]:
    return list(get_chain_capabilities(chain).get("public_rpc_limitations", []))

