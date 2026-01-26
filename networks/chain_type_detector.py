"""
Chain Type Detector - Identifies chain types for appropriate RPC handling

This module helps determine whether a chain uses EVM-compatible RPC methods
or requires special handling for non-EVM chains.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set

import logging

logger = logging.getLogger(__name__)


class ChainType(Enum):
    EVM = "evm"
    BITCOIN = "bitcoin"
    SOLANA = "solana"
    TRON = "tron"
    COSMOS = "cosmos"
    SPECIAL = "special"
    OTHER = "other"


@dataclass(frozen=True)
class ChainInfo:
    """Information about a blockchain network"""
    chain_type: ChainType
    supports_gas_price: bool
    supports_block_number: bool
    supports_eth_calls: bool
    native_token_symbol: str
    special_methods: Dict[str, str]


class ChainTypeDetector:
    """Detects chain types and capabilities"""

    # EVM-compatible chains
    EVM_CHAINS: Set[str] = frozenset({
        "ethereum", "bsc", "polygon", "arbitrum", "base", "optimism",
        "avalanche", "fantom", "gnosis", "celo", "moonbeam", "moonriver",
        "aurora", "harmony", "cronos", "kava", "metis", "canto",
        "dogechain", "boba", "linea", "scroll", "zksync_era", "mantle",
        "blast", "acala", "polygon_zkevm", "base_goerli", "arbitrum_goerli",
        "optimism_goerli", "sepolia", "mumbai", "fuji", "bsc_testnet"
    })

    # Native token per chain
    EVM_NATIVE_TOKENS: Dict[str, str] = {
        "ethereum": "ETH",
        "bsc": "BNB",
        "polygon": "MATIC",
        "arbitrum": "ETH",
        "base": "ETH",
        "optimism": "ETH",
        "avalanche": "AVAX",
        "fantom": "FTM",
        "gnosis": "xDAI",
        "celo": "CELO",
        "moonbeam": "GLMR",
        "moonriver": "MOVR",
        "aurora": "AURORA",
        "harmony": "ONE",
        "cronos": "CRO",
        "kava": "KAVA",
        "metis": "METIS",
        "canto": "CANTO",
        "dogechain": "DOGE",
        "boba": "BOBA",
        "linea": "ETH",
        "scroll": "ETH",
        "zksync_era": "ETH",
        "mantle": "BIT",
        "blast": "BLAST",
        "acala": "ACA",
        "polygon_zkevm": "ETH",
        "base_goerli": "ETH",
        "arbitrum_goerli": "ETH",
        "optimism_goerli": "ETH",
        "sepolia": "ETH",
        "mumbai": "MATIC",
        "fuji": "AVAX",
        "bsc_testnet": "BNB"
    }

    # Bitcoin-like chains (UTXO model)
    BITCOIN_CHAINS: Set[str] = frozenset({
        "bitcoin", "bitcoin_cash", "bitcoin_sv", "litecoin", "dogecoin"
    })

    # Solana ecosystem
    SOLANA_CHAINS: Set[str] = frozenset({
        "solana", "solana_devnet", "solana_testnet"
    })

    # TRON ecosystem
    TRON_CHAINS: Set[str] = frozenset({
        "tron", "tron_testnet"
    })

    # Cosmos SDK chains
    COSMOS_CHAINS: Set[str] = frozenset({
        "cosmos", "osmosis", "juno", "terra", "secret", "fetch_ai",
        "kava", "band_protocol", "iris_network", "akash"
    })

    # Other specialized chains
    SPECIAL_CHAINS: Dict[str, ChainInfo] = {
        "stellar": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="XLM",
            special_methods={
                "getLatestLedger": "Get latest ledger number",
                "getFeeStats": "Get fee statistics",
            },
        ),
        "ripple": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="XRP",
            special_methods={
                "ledger": "Get current ledger",
                "fee": "Get fee information",
            },
        ),
        "cardano": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="ADA",
            special_methods={
                "getBlock": "Get block information",
                "getEpoch": "Get current epoch",
            },
        ),
        "hedera": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="HBAR",
            special_methods={
                "getLatestBlock": "Get latest block",
                "getExchangeRate": "Get exchange rate",
            },
        ),
        "aptos": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="APT",
            special_methods={
                "getLatestBlock": "Get latest block",
                "getGasPrice": "Get gas price estimate",
            },
        ),
        "sui": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="SUI",
            special_methods={
                "getLatestBlock": "Get latest block",
                "getReferenceGasPrice": "Get reference gas price",
            },
        ),
        "near": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="NEAR",
            special_methods={
                "latestBlock": "Get latest block",
                "gasPrice": "Get gas price",
            },
        ),
        "toncoin": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="TON",
            special_methods={
                "getMasterchainInfo": "Get masterchain info",
                "estimateFee": "Estimate transaction fee",
            },
        ),
        "tezos": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="XTZ",
            special_methods={
                "getBlock": "Get block information",
                "getConstants": "Get chain constants",
            },
        ),
        "algorand": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="ALGO",
            special_methods={
                "getBlock": "Get block information",
                "getSuggestedParams": "Get suggested transaction params",
            },
        ),
        "stacks": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="STX",
            special_methods={
                "getBlockInfo": "Get block information",
                "getFeeEstimate": "Get fee estimate",
            },
        ),
        "thorchain": ChainInfo(
            chain_type=ChainType.SPECIAL,
            supports_gas_price=False,
            supports_block_number=True,
            supports_eth_calls=False,
            native_token_symbol="RUNE",
            special_methods={
                "getLatestBlock": "Get latest block",
                "getNetwork": "Get network information",
            },
        ),
    }

    # Cache for ChainInfo objects
    _cache: Dict[str, ChainInfo] = {}

    @classmethod
    def _normalize(cls, chain_name: str) -> str:
        return chain_name.strip().lower()

    @classmethod
    def get_chain_info(cls, chain_name: str) -> ChainInfo:
        """
        Get chain information for a given chain name.

        Args:
            chain_name: Name of the blockchain network

        Returns:
            ChainInfo object with chain capabilities
        """
        chain_lower = cls._normalize(chain_name)

        if chain_lower in cls._cache:
            return cls._cache[chain_lower]

        # Check special chains first
        if chain_lower in cls.SPECIAL_CHAINS:
            cls._cache[chain_lower] = cls.SPECIAL_CHAINS[chain_lower]
            return cls._cache[chain_lower]

        # Check EVM chains
        if chain_lower in cls.EVM_CHAINS:
            native = cls.EVM_NATIVE_TOKENS.get(chain_lower, "ETH")
            info = ChainInfo(
                chain_type=ChainType.EVM,
                supports_gas_price=True,
                supports_block_number=True,
                supports_eth_calls=True,
                native_token_symbol=native,
                special_methods={
                    "eth_blockNumber": "Get latest block number",
                    "eth_gasPrice": "Get current gas price",
                    "eth_getBalance": "Get account balance",
                },
            )
            cls._cache[chain_lower] = info
            return info

        # Check Bitcoin-like chains
        if chain_lower in cls.BITCOIN_CHAINS:
            info = ChainInfo(
                chain_type=ChainType.BITCOIN,
                supports_gas_price=False,
                supports_block_number=True,
                supports_eth_calls=False,
                native_token_symbol="BTC",
                special_methods={
                    "getblockcount": "Get block count",
                    "getnetworkinfo": "Get network information",
                },
            )
            cls._cache[chain_lower] = info
            return info

        # Check Solana chains
        if chain_lower in cls.SOLANA_CHAINS:
            info = ChainInfo(
                chain_type=ChainType.SOLANA,
                supports_gas_price=False,
                supports_block_number=True,
                supports_eth_calls=False,
                native_token_symbol="SOL",
                special_methods={
                    "getSlot": "Get current slot",
                    "getFeeForMessage": "Get fee for message",
                },
            )
            cls._cache[chain_lower] = info
            return info

        # Check TRON chains
        if chain_lower in cls.TRON_CHAINS:
            info = ChainInfo(
                chain_type=ChainType.TRON,
                supports_gas_price=False,
                supports_block_number=True,
                supports_eth_calls=False,
                native_token_symbol="TRX",
                special_methods={
                    "getLatestBlock": "Get latest block",
                    "getBandwidthPrice": "Get bandwidth price",
                },
            )
            cls._cache[chain_lower] = info
            return info

        # Check Cosmos chains
        if chain_lower in cls.COSMOS_CHAINS:
            info = ChainInfo(
                chain_type=ChainType.COSMOS,
                supports_gas_price=False,
                supports_block_number=True,
                supports_eth_calls=False,
                native_token_symbol="ATOM",
                special_methods={
                    "abci_info": "Get ABCI info",
                    "block": "Get latest block",
                },
            )
            cls._cache[chain_lower] = info
            return info

        # Default to unknown/other
        logger.warning("Unknown chain requested: %s", chain_name)
        info = ChainInfo(
            chain_type=ChainType.OTHER,
            supports_gas_price=False,
            supports_block_number=False,
            supports_eth_calls=False,
            native_token_symbol="UNKNOWN",
            special_methods={},
        )
        cls._cache[chain_lower] = info
        return info

    @classmethod
    def is_evm_chain(cls, chain_name: str) -> bool:
        """Check if chain is EVM-compatible"""
        return cls.get_chain_info(chain_name).chain_type == ChainType.EVM

    @classmethod
    def supports_evm_methods(cls, chain_name: str) -> bool:
        """Check if chain supports standard EVM RPC methods"""
        return cls.get_chain_info(chain_name).supports_eth_calls

    @classmethod
    def get_supported_chains_by_type(cls) -> Dict[str, List[str]]:
        """Get all supported chains grouped by type"""
        return {
            "evm": sorted(list(cls.EVM_CHAINS)),
            "bitcoin": sorted(list(cls.BITCOIN_CHAINS)),
            "solana": sorted(list(cls.SOLANA_CHAINS)),
            "tron": sorted(list(cls.TRON_CHAINS)),
            "cosmos": sorted(list(cls.COSMOS_CHAINS)),
            "special": sorted(list(cls.SPECIAL_CHAINS.keys())),
            "other": ["unknown"],
        }

