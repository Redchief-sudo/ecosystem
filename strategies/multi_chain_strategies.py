"""
Network-Specific Strategy Adapters
===================================

Strategy adapters that handle the unique characteristics of each network type.
This replaces the one-size-fits-all approach with network-specific logic.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from trading.token_pipeline.token_candidate import TokenCandidate
from networks.multi_chain_models import ChainType

logger = logging.getLogger(__name__)


@dataclass
class StrategyDecision:
    """Network-agnostic strategy decision."""
    should_trade: bool
    confidence: float
    direction: str  # "buy", "sell", "hold"
    position_size: float  # 0.0 to 1.0
    expected_return: float
    risk_score: float  # 0.0 to 1.0 (higher = riskier)
    metadata: Dict[str, Any]
    network_specific: Dict[str, Any]  # Network-specific data for executor


class BaseNetworkStrategy(ABC):
    """Base class for network-specific strategies."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.chain_type = self.get_supported_chain_type()

    @abstractmethod
    def get_supported_chain_type(self) -> ChainType:
        """Return the chain type this strategy supports."""
        pass

    @abstractmethod
    async def evaluate(
        self, candidate: TokenCandidate, market_data: Dict[str, Any]
    ) -> StrategyDecision:
        pass

    @abstractmethod
    def validate_candidate(self, candidate: TokenCandidate) -> bool:
        pass

    def get_min_liquidity(self) -> float:
        """Get minimum liquidity requirement for this network."""
        return float(self.config.get("min_liquidity_usd", 1000.0))

    def get_min_volume(self) -> float:
        """Get minimum volume requirement for this network."""
        return float(self.config.get("min_volume_24h", 500.0))

    def _clamp01(self, value: float) -> float:
        """Clamp value between 0 and 1."""
        return max(0.0, min(1.0, float(value)))


class EVMStrategy(BaseNetworkStrategy):
    """Strategy adapter for EVM chains (Ethereum, BSC, Polygon, etc.)."""

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.EVM

    def validate_candidate(self, candidate: TokenCandidate) -> bool:
        if candidate.chain_type != ChainType.EVM:
            return False

        if not candidate.pair_address:
            logger.debug(f"EVM candidate {candidate.symbol} missing pair_address")
            return False

        if candidate.liquidity_usd and candidate.liquidity_usd < self.get_min_liquidity():
            return False

        if candidate.volume_24h and candidate.volume_24h < self.get_min_volume():
            return False

        return True

    async def evaluate(self, candidate: TokenCandidate, market_data: Dict[str, Any]) -> StrategyDecision:
        liquidity_score = self._calculate_liquidity_score(candidate)
        volume_score = self._calculate_volume_score(candidate)
        price_action_score = self._calculate_price_action_score(market_data)

        combined_score = (
            liquidity_score * 0.4 +
            volume_score * 0.3 +
            price_action_score * 0.3
        )

        confidence = self._clamp01(combined_score)
        should_trade = confidence > 0.60

        if should_trade:
            price_change = float(market_data.get("price_change_24h", 0.0))
            direction = "buy" if price_change >= 0 else "sell"
            position_size = min(0.10, confidence * 0.20)
            expected_return = 0.05 + (confidence * 0.10)
            risk_score = max(0.10, 1.0 - confidence)
        else:
            direction = "hold"
            position_size = 0.0
            expected_return = 0.0
            risk_score = 0.0

        return StrategyDecision(
            should_trade=should_trade,
            confidence=confidence,
            direction=direction,
            position_size=position_size,
            expected_return=expected_return,
            risk_score=risk_score,
            metadata={
                "liquidity_score": liquidity_score,
                "volume_score": volume_score,
                "price_action_score": price_action_score,
                "combined_score": combined_score,
            },
            network_specific={
                "pair_address": candidate.pair_address,
                "gas_estimate": self._estimate_gas(candidate),
                "dex_type": self._detect_dex_type(candidate),
            },
        )

    def _calculate_liquidity_score(self, candidate: TokenCandidate) -> float:
        if not candidate.liquidity_usd:
            return 0.0
        import math
        return min(1.0, math.log10(max(candidate.liquidity_usd, 1)) / 6.0)

    def _calculate_volume_score(self, candidate: TokenCandidate) -> float:
        if not candidate.volume_24h:
            return 0.0
        import math
        return min(1.0, math.log10(max(candidate.volume_24h, 1)) / 5.0)

    def _calculate_price_action_score(self, market_data: Dict[str, Any]) -> float:
        price_change = float(market_data.get("price_change_24h", 0.0))
        if abs(price_change) < 0.01:
            return 0.1
        if abs(price_change) > 0.5:
            return 0.2
        return min(1.0, abs(price_change) * 2)

    def _estimate_gas(self, candidate: TokenCandidate) -> Dict[str, Any]:
        return {
            "gas_limit": 200000,
            "gas_price_gwei": 20,
            "estimated_cost_eth": 0.004,
        }

    def _detect_dex_type(self, candidate: TokenCandidate) -> str:
        if not candidate.pair_address:
            return "unknown"

        pair_addr = candidate.pair_address.lower()
        if pair_addr.startswith("0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc"):
            return "uniswap_v2"
        if pair_addr.startswith("0x1f98431c8ad98523631ae4a59f267346ea31f984"):
            return "uniswap_v3"

        if isinstance(candidate.metadata, dict) and "dex" in candidate.metadata:
            if "pancake" in str(candidate.metadata.get("dex", "")).lower():
                return "pancakeswap"

        return "unknown"


class SolanaStrategy(BaseNetworkStrategy):
    """Strategy adapter for Solana."""

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.SOLANA

    def validate_candidate(self, candidate: TokenCandidate) -> bool:
        if candidate.chain_type != ChainType.SOLANA:
            return False

        if not getattr(candidate, "pool_id", None):
            logger.debug(f"Solana candidate {candidate.symbol} missing pool_id")
            return False

        if candidate.liquidity_usd and candidate.liquidity_usd < self.get_min_liquidity():
            return False

        return True

    async def evaluate(self, candidate: TokenCandidate, market_data: Dict[str, Any]) -> StrategyDecision:
        liquidity_score = self._calculate_solana_liquidity_score(candidate)
        volume_score = self._calculate_solana_volume_score(candidate)
        holder_score = self._calculate_holder_score(market_data)

        combined_score = (
            liquidity_score * 0.5 +
            volume_score * 0.3 +
            holder_score * 0.2
        )

        confidence = self._clamp01(combined_score)
        should_trade = confidence > 0.65

        if should_trade:
            price_change = float(market_data.get("price_change_24h", 0.0))
            direction = "buy" if price_change >= 0 else "sell"
            position_size = min(0.08, confidence * 0.15)
            expected_return = 0.08 + (confidence * 0.12)
            risk_score = max(0.15, 1.0 - confidence)
        else:
            direction = "hold"
            position_size = 0.0
            expected_return = 0.0
            risk_score = 0.0

        return StrategyDecision(
            should_trade=should_trade,
            confidence=confidence,
            direction=direction,
            position_size=position_size,
            expected_return=expected_return,
            risk_score=risk_score,
            metadata={
                "liquidity_score": liquidity_score,
                "volume_score": volume_score,
                "holder_score": holder_score,
                "combined_score": combined_score,
            },
            network_specific={
                "pool_id": candidate.pool_id,
                "estimated_sol_fee": self._estimate_solana_fees(),
                "program_id": self._detect_program_id(candidate),
            },
        )

    def _calculate_solana_liquidity_score(self, candidate: TokenCandidate) -> float:
        if not candidate.liquidity_usd:
            return 0.0
        import math
        return min(1.0, math.log10(max(candidate.liquidity_usd, 1)) / 5.5)

    def _calculate_solana_volume_score(self, candidate: TokenCandidate) -> float:
        if not candidate.volume_24h:
            return 0.0
        import math
        return min(1.0, math.log10(max(candidate.volume_24h, 1)) / 4.5)

    def _calculate_holder_score(self, market_data: Dict[str, Any]) -> float:
        holder_count = int(market_data.get("holder_count", 0))
        if holder_count < 10:
            return 0.1
        if holder_count > 10000:
            return 0.9
        import math
        return min(1.0, math.log10(holder_count) / 4.0)

    def _estimate_solana_fees(self) -> Dict[str, Any]:
        return {
            "lamports_per_signature": 5000,
            "estimated_lamports": 25000,
            "estimated_sol": 0.000025,
        }

    def _detect_program_id(self, candidate: TokenCandidate) -> str:
        if isinstance(candidate.metadata, dict):
            return candidate.metadata.get("program_id", "unknown")
        return "unknown"


class AptosStrategy(BaseNetworkStrategy):
    """Strategy adapter for Aptos."""

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.APTOS

    def validate_candidate(self, candidate: TokenCandidate) -> bool:
        return candidate.chain_type == ChainType.APTOS

    async def evaluate(self, candidate: TokenCandidate, market_data: Dict[str, Any]) -> StrategyDecision:
        return StrategyDecision(
            should_trade=False,
            confidence=0.0,
            direction="hold",
            position_size=0.0,
            expected_return=0.0,
            risk_score=0.0,
            metadata={"note": "Aptos strategy not implemented"},
            network_specific={"resource_address": candidate.address},
        )


class SuiStrategy(BaseNetworkStrategy):
    """Strategy adapter for Sui."""

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.SUI

    def validate_candidate(self, candidate: TokenCandidate) -> bool:
        return candidate.chain_type == ChainType.SUI

    async def evaluate(self, candidate: TokenCandidate, market_data: Dict[str, Any]) -> StrategyDecision:
        return StrategyDecision(
            should_trade=False,
            confidence=0.0,
            direction="hold",
            position_size=0.0,
            expected_return=0.0,
            risk_score=0.0,
            metadata={"note": "Sui strategy not implemented"},
            network_specific={"object_id": candidate.address},
        )


class MultiChainStrategyManager:
    """
    Manages network-specific strategies and routes tokens to appropriate adapters.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.strategies: Dict[ChainType, BaseNetworkStrategy] = {}
        self._initialize_strategies()

    def _initialize_strategies(self):
        strategy_configs = self.config.get("strategies", {})

        if strategy_configs.get("evm", {}).get("enabled", True):
            self.strategies[ChainType.EVM] = EVMStrategy(strategy_configs.get("evm", {}))

        if strategy_configs.get("solana", {}).get("enabled", True):
            self.strategies[ChainType.SOLANA] = SolanaStrategy(strategy_configs.get("solana", {}))

        if strategy_configs.get("aptos", {}).get("enabled", False):
            self.strategies[ChainType.APTOS] = AptosStrategy(strategy_configs.get("aptos", {}))

        if strategy_configs.get("sui", {}).get("enabled", False):
            self.strategies[ChainType.SUI] = SuiStrategy(strategy_configs.get("sui", {}))

        logger.info(f"Initialized strategies for: {[ct.value for ct in self.strategies.keys()]}")

    async def evaluate_token(
        self, candidate: TokenCandidate, market_data: Dict[str, Any]
    ) -> Optional[StrategyDecision]:

        strategy = self.strategies.get(candidate.chain_type)
        if not strategy:
            logger.warning(f"No strategy available for chain type: {candidate.chain_type.value}")
            return None

        if not strategy.validate_candidate(candidate):
            logger.debug(f"Candidate {candidate.symbol} failed validation for {candidate.chain_type.value}")
            return None

        try:
            return await strategy.evaluate(candidate, market_data)
        except Exception as e:
            logger.error(f"Strategy evaluation failed for {candidate.symbol}: {e}")
            return None

    def get_supported_chain_types(self) -> List[ChainType]:
        return list(self.strategies.keys())


# Global strategy manager instance
_strategy_manager: Optional[MultiChainStrategyManager] = None


def get_multi_chain_strategy_manager() -> Optional[MultiChainStrategyManager]:
    return _strategy_manager


def initialize_multi_chain_strategy_manager(config: Dict[str, Any]) -> MultiChainStrategyManager:
    global _strategy_manager
    _strategy_manager = MultiChainStrategyManager(config)
    return _strategy_manager


__all__ = [
    "BaseNetworkStrategy",
    "EVMStrategy",
    "SolanaStrategy",
    "AptosStrategy",
    "SuiStrategy",
    "MultiChainStrategyManager",
    "StrategyDecision",
    "get_multi_chain_strategy_manager",
    "initialize_multi_chain_strategy_manager",
]

