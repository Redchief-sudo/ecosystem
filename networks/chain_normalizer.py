"""
Chain Name Normalization
=======================

Centralized chain name normalization and ID resolution
to ensure consistent chain identification across the system.
"""

import logging
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)


class ChainNormalizer:
    """
    Normalizes chain names from various sources to canonical names
    and provides bidirectional chain ID resolution.
    """

    # ------------------------------------------------------------------
    # Canonical Name → Chain ID (Base mapping)
    # ------------------------------------------------------------------
    CHAIN_ID_MAPPINGS: Dict[int, str] = {
        1: 'ethereum',
        56: 'bsc',
        137: 'polygon',
        42161: 'arbitrum',
        10: 'optimism',
        8453: 'base',
        81457: 'blast',  # Added missing Blast chain mapping
        43114: 'avalanche',
        324: 'zksync_era',
        1101: 'polygon_zkevm',
        59144: 'linea',
        42170: 'arbitrum_nova',
        1313161554: 'aurora',
        288: 'boba',
        7700: 'canto',
        42220: 'celo',
        25: 'cronos',
        250: 'fantom',
        100: 'cronos',  # Override: tokens with chain_id=100 are cronos, not gnosis
        1666600000: 'harmony',
        2222: 'kava',
        5000: 'mantle',
        1088: 'metis',
        1284: 'moonbeam',
        1285: 'moonriver',
        534352: 'scroll',
        592: 'astar',
        9001: 'evmos',
        122: 'fuse',
        128: 'heco',
        4689: 'iotex',
        321: 'kcc',
        66: 'okc',
        42262: 'oasis_emerald',
        40: 'telos',
        361: 'theta',
        1946: 'soneium',  # Soneium chain
        
        # Non-EVM Networks (unique chain IDs > 100000)
        101001: 'solana',
        101002: 'sui',
        101003: 'aptos',
        101004: 'cardano',
        101005: 'xrpl',
        101006: 'thorchain',
        101007: 'stacks',
        101008: 'algorand',
        101009: 'osmosis',
        101010: 'tezos',
        101011: 'stellar',
        101012: 'starknet',

        # Testnets
        5: 'goerli',
        11155111: 'sepolia',
        97: 'bsc_testnet',
        80001: 'mumbai',
        421613: 'arbitrum_goerli',
        420: 'optimism_goerli',
        43113: 'avalanche_fuji',
        4002: 'fantom_testnet',
        84531: 'base_goerli',
        10200: 'chiado',
        44787: 'celo_alfajores',
        1287: 'moonbase_alpha',
        1313161555: 'aurora_testnet',
        1666700000: 'harmony_testnet',
        599: 'metis_goerli',
        28: 'boba_rinkeby',
        280: 'zksync_goerli',
        534351: 'scroll_sepolia',
        59140: 'linea_goerli',
        5001: 'mantle_testnet',
        1442: 'polygon_zkevm_testnet',
    }

    # ------------------------------------------------------------------
    # Name / Alias → Canonical Name
    # ------------------------------------------------------------------
    CHAIN_MAPPINGS: Dict[str, str] = {
        # Ethereum
        'eth': 'ethereum',
        'mainnet': 'ethereum',
        'ethereum': 'ethereum',
        'eth_mainnet': 'ethereum',
        'hyperevm': 'ethereum',

        # BSC
        'bsc': 'bsc',
        'binance_smart_chain': 'bsc',
        'bnb_chain': 'bsc',
        'binance': 'bsc',
        'bsc_mainnet': 'bsc',
        'bnb_smart_chain': 'bsc',

        # Polygon
        'polygon': 'polygon',
        'matic': 'polygon',
        'polygon_mainnet': 'polygon',
        'polygon_pos': 'polygon',

        # Arbitrum
        'arbitrum': 'arbitrum',
        'arbitrum_one': 'arbitrum',
        'arbitrum_mainnet': 'arbitrum',
        'arb1': 'arbitrum',

        # Optimism
        'optimism': 'optimism',
        'op_mainnet': 'optimism',
        'optimism_mainnet': 'optimism',

        # Base
        'base': 'base',
        'base_mainnet': 'base',

        # Blast
        'blast': 'blast',
        'blast_mainnet': 'blast',

        # Avalanche
        'avalanche': 'avalanche',
        'avax': 'avalanche',
        'avalanche_c_chain': 'avalanche',
        'avalanche_mainnet': 'avalanche',

        # zkSync Era
        'zksync': 'zksync_era',
        'zksync_era': 'zksync_era',
        'zksync_mainnet': 'zksync_era',

        # Polygon zkEVM
        'polygon_zkevm': 'polygon_zkevm',
        'zkevm': 'polygon_zkevm',
        'polygon_zkevm_mainnet': 'polygon_zkevm',

        # Linea
        'linea': 'linea',
        'linea_mainnet': 'linea',
        'consensys_linea': 'linea',

        # Arbitrum Nova
        'arbitrum_nova': 'arbitrum_nova',
        'nova': 'arbitrum_nova',

        # Aurora
        'aurora': 'aurora',
        'aurora_mainnet': 'aurora',
        'near_aurora': 'aurora',

        # Bitcoin
        'bitcoin': 'bitcoin',
        
        # Non-EVM Networks
        'solana': 'solana',
        'aptos': 'aptos',
        'sui': 'sui',
        'cosmos': 'cosmos',
        'osmosis': 'cosmos',
        'cardano': 'cardano',
        'polkadot': 'polkadot',
        'avalanche': 'avalanche',
        'near': 'near',
        'tron': 'tron',
        'stellar': 'stellar',
        'algorand': 'algorand',
        'tezos': 'tezos',
        'hedera': 'hedera',
        'flow': 'flow',
        'elrond': 'elrond',
        'canto_mainnet': 'canto',

        # Celo
        'celo': 'celo',
        'celo_mainnet': 'celo',
        'celo_network': 'celo',

        # Cronos
        'cronos': 'cronos',
        'cro': 'cronos',
        'crypto_com_chain': 'cronos',

        # Soneium
        'soneium': 'soneium',
        'soneium_mainnet': 'soneium',

        # Fantom
        'fantom': 'fantom',
        'ftm': 'fantom',
        'fantom_opera': 'fantom',

        # Gnosis Chain
        'gnosis': 'gnosis',
        'gnosis_chain': 'gnosis',
        'xdai': 'gnosis',
        'gnosis_mainnet': 'gnosis',

        # Harmony
        'harmony': 'harmony',
        'harmony_one': 'harmony',
        'harmony_mainnet': 'harmony',

        # Kava
        'kava': 'kava',
        'kava_evm': 'kava',
        'kava_mainnet': 'kava',

        # Mantle
        'mantle': 'mantle',
        'mantle_mainnet': 'mantle',

        # Metis
        'metis': 'metis',
        'metis_andromeda': 'metis',
        'metis_mainnet': 'metis',

        # Moonbeam
        'moonbeam': 'moonbeam',
        'moonbeam_mainnet': 'moonbeam',

        # Moonriver
        'moonriver': 'moonriver',
        'moonriver_mainnet': 'moonriver',

        # Scroll
        'scroll': 'scroll',
        'scroll_mainnet': 'scroll',

        # Astar
        'astar': 'astar',
        'astar_network': 'astar',
        'astar_mainnet': 'astar',

        # Evmos
        'evmos': 'evmos',
        'evmos_mainnet': 'evmos',

        # Fuse
        'fuse': 'fuse',
        'fuse_network': 'fuse',
        'fuse_mainnet': 'fuse',

        # HECO
        'heco': 'heco',
        'huobi_eco_chain': 'heco',
        'heco_mainnet': 'heco',

        # IoTeX
        'iotex': 'iotex',
        'iotex_mainnet': 'iotex',

        # KCC
        'kcc': 'kcc',
        'kucoin_community_chain': 'kcc',
        'kcc_mainnet': 'kcc',

        # OKX Chain
        'okc': 'okc',
        'okx_chain': 'okc',
        'okex_chain': 'okc',
        'okx_mainnet': 'okc',

        # Oasis Emerald
        'oasis_emerald': 'oasis_emerald',
        'oasis': 'oasis_emerald',
        'emerald': 'oasis_emerald',

        # Telos
        'telos': 'telos',
        'telos_evm': 'telos',
        'telos_mainnet': 'telos',

        # Theta
        'theta': 'theta',
        'theta_network': 'theta',
        'theta_mainnet': 'theta',
        
        # Non-EVM Networks (missing from TokenRegistry)
        'solana': 'solana',
        'aptos': 'aptos',
        'sui': 'sui',
        'cosmos': 'cosmos',
        'osmosis': 'cosmos',
        'cardano': 'cardano',
        'polkadot': 'polkadot',
        'near': 'near',
        'tron': 'tron',
        'stellar': 'stellar',
        'algorand': 'algorand',
        'tezos': 'tezos',
        'hedera': 'hedera',
        'flow': 'flow',
        'elrond': 'elrond',
        
        # TokenRegistry Networks (missing aliases)
        'acala': 'acala',
        'stacks': 'stacks',
        'starknet': 'starknet',
        'thorchain': 'thorchain',
        'ton': 'ton',
        'xrpl': 'xrpl',
        'bnb_smart_chain': 'bsc',
        'near_aurora': 'aurora'
    }

    # ------------------------------------------------------------------
    # Reverse lookup: canonical name → chain id
    # ------------------------------------------------------------------
    CHAIN_NAME_TO_ID: Dict[str, int] = {
        name: chain_id for chain_id, name in CHAIN_ID_MAPPINGS.items()
    }

    @staticmethod
    def normalize_chain_name(chain: str) -> str:
        if not chain:
            return 'unknown'

        normalized = str(chain).lower().strip()
        canonical = ChainNormalizer.CHAIN_MAPPINGS.get(normalized, normalized)

        if canonical != normalized:
            logger.debug(f"Normalized chain name: {chain} → {canonical}")

        return canonical

    @staticmethod
    def chain_id_to_name(chain_id: int) -> str:
        try:
            return ChainNormalizer.CHAIN_ID_MAPPINGS.get(int(chain_id), 'unknown')
        except (ValueError, TypeError):
            return 'unknown'

    @staticmethod
    def normalize_chain_identifier(chain_input: Union[str, int]) -> str:
        if chain_input is None:
            return 'unknown'

        # Handle numeric chain IDs first
        try:
            chain_id = int(chain_input)
            name = ChainNormalizer.chain_id_to_name(chain_id)
            if name != 'unknown':
                return name
        except (ValueError, TypeError):
            pass

        # Handle string chain IDs (like 'bsc', 'ethereum')
        chain_str = str(chain_input).lower().strip()
        
        # Direct mapping for common string chain IDs
        string_to_id = {
            'bsc': 56,
            'ethereum': 1,
            'eth': 1,
            'polygon': 137,
            'matic': 137,
            'arbitrum': 42161,
            'arb': 42161,
            'optimism': 10,
            'op': 10,
            'base': 8453,
            'blast': 81457,
            'avalanche': 43114,
            'avax': 43114,
            'fantom': 250,
            'ftm': 250,
            'cronos': 25,
            'cro': 25,
            'linea': 59144,
            'scroll': 534352,
            'mantle': 5000,
            'zksync': 324,
            
            # Non-EVM networks (unique chain IDs > 100000)
            'solana': 101001,
            'sui': 101002,
            'aptos': 101003,
            'cardano': 101004,
            'xrpl': 101005,
            'thorchain': 101006,
            'stacks': 101007,
            'algorand': 101008,
            'osmosis': 101009,
            'tezos': 101010,
            'stellar': 101011,
            'starknet': 101012,
        }
        
        if chain_str in string_to_id:
            return ChainNormalizer.chain_id_to_name(string_to_id[chain_str])
        
        # Fallback to name normalization
        return ChainNormalizer.normalize_chain_name(chain_str)


def get_chain_id(chain_name: str) -> int:
    """
    Resolve canonical chain name to numeric chain ID.

    Used by execution / routing layers.
    """
    if not chain_name:
        raise ValueError("Chain name is empty")

    canonical = ChainNormalizer.normalize_chain_name(chain_name)

    if canonical not in ChainNormalizer.CHAIN_NAME_TO_ID:
        raise ValueError(f"Unknown or unsupported chain: {chain_name}")

    return ChainNormalizer.CHAIN_NAME_TO_ID[canonical]


# Global normalizer instance
chain_normalizer = ChainNormalizer()


__all__ = [
    "ChainNormalizer",
    "chain_normalizer",
    "get_chain_id",
]

