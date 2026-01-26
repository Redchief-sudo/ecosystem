"""
Chain Execution Policy Manager
==============================

Centralized execution policy management to prevent execution
on unsupported or non-executable chains.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set

from networks.chain_normalizer import chain_normalizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionProfile:
    """Execution profile for a chain."""
    chain: str
    is_evm_compatible: bool
    supported_routers: List[str]
    requires_permit: bool
    gas_model: str
    execution_enabled: bool = True


class ChainExecutionPolicy:
    """
    Manages execution policies for different chains.

    Prevents:
    - Execution on unsupported chains
    - Gas model mismatches
    - Router incompatibilities
    - Permit requirement failures
    """

    # Chains with known execution support
    EXECUTABLE_EVM_CHAINS: Set[str] = {
        'ethereum', 'bsc', 'bnb_smart_chain', 'polygon', 'arbitrum', 'optimism',
        'base', 'avalanche', 'fantom', 'cronos', 'celo', 'gnosis', 'linea',
        'polygon_zkevm', 'moonriver', 'moonbeam', 'scroll', 'zksync', 'zksync_era',
        'mantle', 'blast', 'mode', 'acala', 'telos', 'step', 'rangers', 'astar',
        'songbird', 'evmos', 'okc', 'kava', 'canto', 'boba', 'aurora',
        'near_aurora', 'metis', 'harmony', 'godwoken', 'kcc', 'theta',
        'heco', 'oasis_emerald', 'telos', 'iotex', 'kava'
    }

    # Chains requiring special handling (non-EVM)
    SPECIAL_HANDLING_CHAINS: Dict[str, Dict[str, object]] = {
        'solana': {
            'evm_compatible': False,
            'reason': 'Non-EVM architecture',
            'alternative': 'Use Solana-specific scanners'
        },
        'osmosis': {
            'evm_compatible': False,
            'reason': 'Cosmos SDK architecture',
            'alternative': 'Use cosmos-specific scanners'
        },
        'tron': {
            'evm_compatible': False,
            'reason': 'TRON Virtual Machine architecture',
            'alternative': 'Use TRON-specific scanners'
        },
        'ton': {
            'evm_compatible': False,
            'reason': 'TON Virtual Machine architecture',
            'alternative': 'Use TON-specific scanners'
        },
        'cardano': {
            'evm_compatible': False,
            'reason': 'Cardano Plutus architecture',
            'alternative': 'Use Cardano-specific scanners'
        },
        'xrpl': {
            'evm_compatible': False,
            'reason': 'XRPL ledger architecture',
            'alternative': 'Use XRPL-specific scanners'
        },
        'aptos': {
            'evm_compatible': False,
            'reason': 'Aptos Move architecture',
            'alternative': 'Use Aptos-specific scanners'
        },
        'sui': {
            'evm_compatible': False,
            'reason': 'Sui Move architecture',
            'alternative': 'Use Sui-specific scanners'
        },
        'stacks': {
            'evm_compatible': False,
            'reason': 'Clarity smart contracts',
            'alternative': 'Use Stacks-specific scanners'
        },
        'algorand': {
            'evm_compatible': False,
            'reason': 'Algorand ASA architecture',
            'alternative': 'Use Algorand-specific scanners'
        },
        'tezos': {
            'evm_compatible': False,
            'reason': 'Tezos Michelson architecture',
            'alternative': 'Use Tezos-specific scanners'
        },
        'stellar': {
            'evm_compatible': False,
            'reason': 'Stellar Soroban architecture',
            'alternative': 'Use Stellar-specific scanners'
        },
        'starknet': {
            'evm_compatible': False,
            'reason': 'StarkNet Cairo architecture',
            'alternative': 'Use StarkNet-specific scanners'
        }
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.disabled_chains: Set[str] = set(self.config.get('disabled_chains', []))
        self.execution_profiles: Dict[str, ExecutionProfile] = self._build_execution_profiles()

    def _build_execution_profiles(self) -> Dict[str, ExecutionProfile]:
        """Build execution profiles for all supported chains."""
        profiles: Dict[str, ExecutionProfile] = {}

        evm_chains = {
            'ethereum': ExecutionProfile('ethereum', True, ['uniswap_v2', 'uniswap_v3'], False, 'eth', True),
            'bsc': ExecutionProfile('bsc', True, ['pancakeswap_v2', 'pancakeswap_v3'], False, 'bnb', True),
            'bnb_smart_chain': ExecutionProfile('bnb_smart_chain', True, ['pancakeswap_v2', 'pancakeswap_v3'], False, 'bnb', True),
            'polygon': ExecutionProfile('polygon', True, ['quickswap', 'sushiswap'], False, 'matic', True),
            'arbitrum': ExecutionProfile('arbitrum', True, ['uniswap_v3', 'sushiswap'], False, 'eth', True),
            'optimism': ExecutionProfile('optimism', True, ['uniswap_v3'], False, 'eth', True),
            'base': ExecutionProfile('base', True, ['uniswap_v3'], False, 'eth', True),
            'avalanche': ExecutionProfile('avalanche', True, ['traderjoe'], False, 'avax', True),
            'fantom': ExecutionProfile('fantom', True, ['spookyswap', 'sushiswap'], False, 'ftm', True),
            'cronos': ExecutionProfile('cronos', True, ['vvs', 'sushiswap'], False, 'cro', True),
            'gnosis': ExecutionProfile('gnosis', True, ['honeyswap', 'sushiswap'], False, 'xdai', True),
            'linea': ExecutionProfile('linea', True, ['uniswap_v3'], False, 'eth', True),
            'polygon_zkevm': ExecutionProfile('polygon_zkevm', True, ['uniswap_v3'], False, 'eth', True),
            'moonriver': ExecutionProfile('moonriver', True, ['sushiswap'], False, 'movr', True),
            'moonbeam': ExecutionProfile('moonbeam', True, ['sushiswap'], False, 'glmr', True),
            'scroll': ExecutionProfile('scroll', True, ['uniswap_v3'], False, 'eth', True),
            'zksync': ExecutionProfile('zksync', True, ['uniswap_v3'], False, 'eth', True),
            'zksync_era': ExecutionProfile('zksync_era', True, ['uniswap_v3'], False, 'eth', True),
            'mantle': ExecutionProfile('mantle', True, ['uniswap_v3'], False, 'mnt', True),
            'blast': ExecutionProfile('blast', True, ['uniswap_v3'], False, 'eth', True),
            'mode': ExecutionProfile('mode', True, ['uniswap_v3'], False, 'eth', True),
            'acala': ExecutionProfile('acala', True, ['uniswap_v2'], False, 'aca', True),
            'telos': ExecutionProfile('telos', True, ['uniswap_v2'], False, 'tlos', True),
            'step': ExecutionProfile('step', True, ['uniswap_v2'], False, 'step', True),
            'rangers': ExecutionProfile('rangers', True, ['uniswap_v2'], False, 'rpg', True),
            'astar': ExecutionProfile('astar', True, ['arthswap'], False, 'astr', True),
            'songbird': ExecutionProfile('songbird', True, ['uniswap_v2'], False, 'sgb', True),
            'evmos': ExecutionProfile('evmos', True, ['uniswap_v2'], False, 'evmos', True),
            'kava': ExecutionProfile('kava', True, ['uniswap_v2'], False, 'kava', True),
            'canto': ExecutionProfile('canto', True, ['uniswap_v2'], False, 'canto', True),
            'boba': ExecutionProfile('boba', True, ['uniswap_v2'], False, 'eth', True),
            'aurora': ExecutionProfile('aurora', True, ['uniswap_v2'], False, 'eth', True),
            'near_aurora': ExecutionProfile('near_aurora', True, ['uniswap_v2'], False, 'eth', True),
            'metis': ExecutionProfile('metis', True, ['uniswap_v2'], False, 'metis', True),
            'harmony': ExecutionProfile('harmony', True, ['uniswap_v2'], False, 'one', True),
            'godwoken': ExecutionProfile('godwoken', True, ['uniswap_v2'], False, 'eth', True),
            'okc': ExecutionProfile('okc', True, ['uniswap_v2'], False, 'okt', True),
            'kcc': ExecutionProfile('kcc', True, ['uniswap_v2'], False, 'kcs', True),
            'theta': ExecutionProfile('theta', True, ['uniswap_v2'], False, 'theta', True),
            'heco': ExecutionProfile('heco', True, ['uniswap_v2'], False, 'ht', True),
            'oasis_emerald': ExecutionProfile('oasis_emerald', True, ['uniswap_v2'], False, 'rose', True),
            'iotex': ExecutionProfile('iotex', True, ['uniswap_v2'], False, 'iotx', True),
        }

        profiles.update(evm_chains)

        # Add special handling chains
        for chain, special_config in self.SPECIAL_HANDLING_CHAINS.items():
            profiles[chain] = ExecutionProfile(
                chain=chain,
                is_evm_compatible=bool(special_config['evm_compatible']),
                supported_routers=[],
                requires_permit=False,
                gas_model='native',
                execution_enabled=False
            )

        return profiles

    def is_chain_executable(self, chain: str) -> Tuple[bool, str]:
        """
        Check if a chain can be executed.

        Args:
            chain: Chain name to check

        Returns:
            Tuple of (is_executable, reason)
        """
        normalized_chain = chain_normalizer.normalize_chain_name(chain)

        if normalized_chain in self.disabled_chains:
            return False, f"Chain {normalized_chain} is explicitly disabled"

        profile = self.execution_profiles.get(normalized_chain)
        if profile is None:
            return False, f"Chain {normalized_chain} is not supported for execution"

        if not profile.execution_enabled:
            return False, f"Chain {normalized_chain} execution is disabled"

        if not profile.is_evm_compatible:
            return False, f"Chain {normalized_chain} is not EVM compatible: {self.SPECIAL_HANDLING_CHAINS.get(normalized_chain, {}).get('reason', 'unknown')}"

        return True, "Chain is executable"

    def get_execution_profile(self, chain: str) -> Optional[ExecutionProfile]:
        """Get execution profile for a chain."""
        normalized_chain = chain_normalizer.normalize_chain_name(chain)
        return self.execution_profiles.get(normalized_chain)

    def filter_executable_chains(self, chains: List[str]) -> List[str]:
        """
        Filter list of chains to only executable ones.

        Args:
            chains: List of chain names

        Returns:
            List of executable chain names
        """
        executable_chains = []

        for chain in chains:
            is_executable, reason = self.is_chain_executable(chain)
            if is_executable:
                executable_chains.append(chain_normalizer.normalize_chain_name(chain))
            else:
                logger.warning(f"Filtering out non-executable chain {chain}: {reason}")

        logger.info(
            "Execution policy: %d/%d chains passed execution filter",
            len(executable_chains),
            len(chains)
        )
        return executable_chains

    def should_disable_chain_early(self, chain: str, scanner_type: str) -> Tuple[bool, str]:
        """
        Determine if a chain should be disabled early for specific scanner types.

        Args:
            chain: Chain name
            scanner_type: Type of scanner (ultra, onchain, etc.)

        Returns:
            Tuple of (should_disable, reason)
        """
        normalized_chain = chain_normalizer.normalize_chain_name(chain)

        long_tail_chains = {
            'harmony', 'moonriver', 'celo', 'aurora', 'rootstock',
            'kava', 'canto', 'boba', 'metis', 'evmos'
        }

        if scanner_type == 'ultra' and normalized_chain in long_tail_chains:
            return True, f"Chain {normalized_chain} has poor DexScreener coverage for ultra scanning"

        non_evm_chains = set(self.SPECIAL_HANDLING_CHAINS.keys())

        if scanner_type in ['ultra', 'onchain'] and normalized_chain in non_evm_chains:
            return True, f"Chain {normalized_chain} is non-EVM, incompatible with {scanner_type} scanner"

        return False, ""

    def disable_chain(self, chain: str) -> None:
        """Disable a chain at runtime."""
        normalized_chain = chain_normalizer.normalize_chain_name(chain)
        self.disabled_chains.add(normalized_chain)

    def enable_chain(self, chain: str) -> None:
        """Enable a chain at runtime."""
        normalized_chain = chain_normalizer.normalize_chain_name(chain)
        self.disabled_chains.discard(normalized_chain)

    def set_chain_execution_enabled(self, chain: str, enabled: bool) -> None:
        """Enable or disable execution on a specific chain profile."""
        normalized_chain = chain_normalizer.normalize_chain_name(chain)
        profile = self.execution_profiles.get(normalized_chain)
        if profile is None:
            raise ValueError(f"Chain {normalized_chain} not found in execution profiles")

        self.execution_profiles[normalized_chain] = ExecutionProfile(
            chain=profile.chain,
            is_evm_compatible=profile.is_evm_compatible,
            supported_routers=profile.supported_routers,
            requires_permit=profile.requires_permit,
            gas_model=profile.gas_model,
            execution_enabled=enabled
        )


# Global policy manager instance
chain_execution_policy = ChainExecutionPolicy()

