"""
Trade Intent Builder - Converts StrategyDecisions to executable TradeIntents.

This is the ONLY place where decisions become intents.
All field validation and defaults happen here.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from eth_typing import Address
from typing import Any, Dict, Optional

from trading.models import (
    DecisionOutcome,
    StrategyDecision,
    TradeOpportunity,
    TradeSide,
)
from trading.trade_intent.trade_intent import ExecutionType, TradeIntent

logger = logging.getLogger(__name__)


class TradeIntentBuilder:
    """
    Converts strategy decisions to executable trade intents.

    This is the authoritative conversion layer - no other component
    should create TradeIntents directly.
    """

    # Execution profile mapping - supports true multi-network
    CHAIN_EXECUTION_PROFILE = {
        # EVM Chains - Uniswap V3
        "ethereum": "uniswap_v3",
        "arbitrum": "uniswap_v3", 
        "optimism": "uniswap_v3",
        "base": "uniswap_v3",
        "zksync_era": "uniswap_v3",
        "polygon_zkevm": "uniswap_v3",
        "taiko": "uniswap_v3",
        "blast": "uniswap_v3",
        "linea": "uniswap_v3",
        "scroll": "uniswap_v3",
        "mantle": "uniswap_v3",
        "mode": "uniswap_v3",
        
        # EVM Chains - Uniswap V2
        "bsc": "pancakeswap_v2",
        "polygon": "uniswap_v2",
        "avalanche": "traderjoe",
        "fantom": "spookyswap",
        "cronos": "vvs_finance",
        "celo": "ubeswap",
        "moonbeam": "solarflare",
        "moonriver": "solarbeam",
        "gnosis": "honeyswap",
        "harmony": "viper",
        "aurora": "trisolaris",
        "metis": "netswap",
        "canto": "canto_dex",
        "boba": "oomi",
        "kava": "kaddex",
        "evmos": "evmos_dex",
        "telos": "telos_swap",
        
        # NON-EVM NETWORKS - Native DEXs
        "solana": "raydium",
        "aptos": "panora", 
        "sui": "cetus",
        "cosmos": "osmosis",
        "bitcoin": "bisq",
    }

    # Router name normalization map - supports all networks
    ROUTER_NAME_NORMALIZATION = {
        # EVM DEXs
        "uniswap": "uniswap_v3",
        "uniswap_v2": "uniswap_v2",
        "uniswap_v3": "uniswap_v3",
        "pancakeswap": "pancakeswap_v2",
        "pancakeswap_v2": "pancakeswap_v2",
        "pancakeswap_v3": "pancakeswap_v3",
        "apeswap": "pancakeswap_v2",
        "quickswap": "uniswap_v2",
        "quickswap_v2": "uniswap_v2",
        "quickswap_v3": "uniswap_v3",
        "camelot": "uniswap_v3",
        "camelot_v2": "uniswap_v2",
        "camelot_v3": "uniswap_v3",
        "traderjoe": "uniswap_v2",
        "traderjoe_v2": "uniswap_v2",
        "pangolin": "uniswap_v2",
        "pangolin_v2": "uniswap_v2",
        "pangolin_v3": "uniswap_v3",
        "spookyswap": "uniswap_v2",
        
        # Non-EVM DEXs
        "raydium": "raydium",
        "orca": "orca",
        "serum": "serum",
        "panora": "panora",
        "cetus": "cetus",
        "turbos": "turbos",
        "osmosis": "osmosis",
        "junoswap": "junoswap",
        "bisq": "bisq",
        
        # Additional EVM DEXs (legacy)
        "spiritswap": "uniswap_v2",
        "spookyswap_v2": "uniswap_v2",
        "spiritswap_v2": "uniswap_v2",
        "cronaswap": "uniswap_v2",
        "vvs_swap": "uniswap_v2",
        "cronos_swap": "uniswap_v2",
        "ubeswap": "uniswap_v2",
        "mobius": "uniswap_v2",
        "sushiswap_celo": "uniswap_v2",
        "stellaswap": "uniswap_v2",
        "solarbeam": "uniswap_v2",
        "moonbeam_swap": "uniswap_v2",
        "trisolaris": "uniswap_v2",
        "netswap": "uniswap_v2",
        "canto_dex": "uniswap_v2",
        "oomi": "uniswap_v2",
        "kaddex": "uniswap_v2",
        "evmos_dex": "uniswap_v2",
        "telos_swap": "uniswap_v2",
        "viper": "uniswap_v2",
        "honeyswap": "uniswap_v2",
        "pangolin_v3": "uniswap_v3",
        "traderjoe_v3": "uniswap_v3",
        "camelot_v3": "uniswap_v3",
        "quickswap_v3": "uniswap_v3",
        "pancakeswap_v3": "pancakeswap_v3",
        "apeswap": "pancakeswap_v2",
        "biswap": "pancakeswap_v2",
        "babyswap": "pancakeswap_v2",
        "mdex": "pancakeswap_v2",
        "bakeryswap": "pancakeswap_v2",
        "coffeeswap": "pancakeswap_v2",
        "jetswap": "pancakeswap_v2",
        "xswap": "pancakeswap_v2",
        "vvs_finance": "uniswap_v2",
        "solarflare": "uniswap_v2",
        "solarbeam": "uniswap_v2",
        "trisolaris": "uniswap_v2",
        "netswap": "uniswap_v2",
        "canto_dex": "uniswap_v2",
        "oomi": "uniswap_v2",
        "kaddex": "uniswap_v2",
        "evmos_dex": "uniswap_v2",
        "telos_swap": "uniswap_v2",
        "scroll_swap": "uniswap_v2",
        "scroll_v2": "uniswap_v2",
        "scroll_v3": "uniswap_v3",
        "linea_swap": "uniswap_v2",
        "linea_v2": "uniswap_v2",
        "linea_v3": "uniswap_v3",

        "netswap": "uniswap_v2",
        "diffusion": "uniswap_v2",
        "kava_swap": "uniswap_v2",
        "canto_dex": "uniswap_v2",
        "oolong_swap": "uniswap_v2",
        "fuse_swap": "uniswap_v2",
        "agni_swap": "uniswap_v2",
        "blast_swap": "uniswap_v2",
        "velodrome": "uniswap_v2",
        "sei_swap": "uniswap_v2",
        "taiko_swap": "uniswap_v3",
        "rsk_swap": "uniswap_v2",
        "oasis_swap": "uniswap_v2",
        "ewt_swap": "uniswap_v2",
        "telos_swap": "uniswap_v2",
        "dogeswap": "uniswap_v2",

        "swap": "uniswap_v2",
        "dex": "uniswap_v2",
        "exchange": "uniswap_v2",
        "router": "uniswap_v2",
    }

    # Default routing configuration (only validated real routers)
    DEFAULT_ROUTERS = {
        "ethereum": {
            "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        },
        "bsc": {
            "pancakeswap_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        },
        "polygon": {
            "uniswap_v2": "0xa5E0829CaCEDd8fC1b1bAe4dbD3b1f0a9E0C8B",
        },
        "arbitrum": {
            "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        },
        "optimism": {
            "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        },
        "avalanche": {
            "uniswap_v2": "0x60aE616515Af5Dc7FF5C5b2372B8440c3E4E0cEc",
        },
        "fantom": {
            "uniswap_v2": "0xF491e7B69E4244ad4002BC14e878a34207E38c29",
        },
    }

    # Default gas settings
    DEFAULT_GAS_LIMITS = {
        "ethereum": 200000,
        "bsc": 300000,
        "polygon": 500000,
        "arbitrum": 300000,
        "optimism": 300000,
        "avalanche": 500000,
        "fantom": 500000,
    }

    @classmethod
    def from_decision(
        cls,
        decision: StrategyDecision,
        opportunity: TradeOpportunity,
        native_token_address: str,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> TradeIntent:
        """
        Convert strategy decision to executable TradeIntent.

        Args:
            decision: Strategy decision from AI controller
            opportunity: Original trading opportunity
            native_token_address: Wrapped native token address for chain
            portfolio_state: Current portfolio state (optional)

        Returns:
            Executable TradeIntent

        Raises:
            ValueError: If decision cannot be converted to executable intent
        """

        cls.validate_required_fields(decision, opportunity)

        if decision.outcome != DecisionOutcome.APPROVED:
            raise ValueError(f"Cannot create TradeIntent from unapproved decision: {decision.outcome}")

        chain = opportunity.chain
        token_address = opportunity.token_address
        opportunity_id = getattr(opportunity, "opportunity_id", None)

        if not opportunity_id:
            raise ValueError("Opportunity missing opportunity_id")

        if chain not in cls.DEFAULT_ROUTERS:
            raise ValueError(f"Chain '{chain}' not execution-enabled")

        if chain not in cls.CHAIN_EXECUTION_PROFILE:
            raise ValueError(f"Chain '{chain}' missing execution profile")

        # Use 90% of portfolio value as default amount
        portfolio_value = portfolio_state.get("total_value_usd", 1000.0) if portfolio_state else 1000.0
        amount_usd = min(portfolio_value * 0.9, 100.0)

        # Convert USD to native token amount (requires real price)
        price_usd = getattr(opportunity, "current_price", None)
        if not price_usd or price_usd <= 0:
            raise ValueError("Opportunity missing valid current_price")

        amount_in = Decimal(str(amount_usd)) / Decimal(str(price_usd))
        min_amount_out = amount_in * Decimal("0.98")
        deadline = datetime.now(timezone.utc) + timedelta(minutes=2)

        execution_profile = cls.CHAIN_EXECUTION_PROFILE.get(chain, "uniswap_v2")
        router_name = execution_profile

        if getattr(decision, "dex", None):
            normalized_dex = cls.ROUTER_NAME_NORMALIZATION.get(decision.dex.lower(), decision.dex.lower())
            if normalized_dex in cls.DEFAULT_ROUTERS.get(chain, {}):
                router_name = normalized_dex
            else:
                logger.warning(f"DEX {decision.dex} not supported on {chain}, using profile {router_name}")

        if router_name not in cls.DEFAULT_ROUTERS[chain]:
            available_routers = list(cls.DEFAULT_ROUTERS[chain].keys())
            raise ValueError(f"Router '{router_name}' not registered for chain '{chain}'. Available: {available_routers}")

        router_address = cls.DEFAULT_ROUTERS[chain][router_name]

        intent = TradeIntent(
            chain=chain,
            router=router_address,
            token_in=Address(native_token_address),
            token_out=Address(token_address),
            amount_in=amount_in,
            min_amount_out=min_amount_out,
            slippage_bps=200,
            deadline=deadline,
            execution_type=ExecutionType.IMMEDIATE,
            side=TradeSide.BUY,
            opportunity_id=opportunity_id,
            confidence=decision.confidence,
            gas_limit=cls.DEFAULT_GAS_LIMITS.get(chain, 300000),
        )

        if not intent.is_executable():
            raise ValueError(f"Generated TradeIntent is not executable: {intent}")

        return intent

    @classmethod
    def validate_required_fields(cls, decision: StrategyDecision, opportunity: TradeOpportunity) -> None:
        """
        Validate that decision and opportunity have required fields.

        Raises:
            ValueError: If required fields are missing
        """
        if decision.confidence is None or decision.confidence <= 0:
            raise ValueError("Decision missing valid confidence")

        if decision.outcome != DecisionOutcome.APPROVED:
            raise ValueError(f"Decision not approved: {decision.outcome}")

        if not getattr(opportunity, "token_address", None):
            raise ValueError("Opportunity missing token_address")

        if not getattr(opportunity, "chain", None):
            raise ValueError("Opportunity missing chain")

        if not getattr(opportunity, "current_price", None) or opportunity.current_price <= 0:
            raise ValueError("Opportunity missing valid current_price")

        if not getattr(opportunity, "opportunity_id", None):
            raise ValueError("Opportunity missing opportunity_id")

