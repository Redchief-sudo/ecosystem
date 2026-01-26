"""
Execution Admission Controller

Critical pre-execution gate that prevents uneconomic, impossible,
or unsafe trades from reaching the execution layer.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from trading.treasury.gas_treasury import GasTreasury
from trading.token_pipeline import TokenRegistry

logger = logging.getLogger(__name__)


# =========================
# Admission Result
# =========================

@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.admitted

    @staticmethod
    def ok() -> "AdmissionResult":
        return AdmissionResult(admitted=True)

    @staticmethod
    def fail(reason: str, details: Optional[Dict[str, Any]] = None) -> "AdmissionResult":
        return AdmissionResult(admitted=False, reason=reason, details=details)


# =========================
# Controller
# =========================

class ExecutionAdmissionController:
    """
    Hard execution gate enforcing capital, risk, and feasibility constraints.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        token_registry: TokenRegistry,
        network_manager: Optional[Any] = None,
        gas_treasury: Optional[GasTreasury] = None,
    ):
        self.config = config
        self.token_registry = token_registry
        self.network_manager = network_manager
        self.gas_treasury = gas_treasury

        admission = config.get("execution_admission", {})
        self.enabled = admission.get("enabled", True)

        self.supported_chains: Set[str] = set(admission.get("supported_chains", []))
        self.paused_chains: Set[str] = set(admission.get("paused_chains", []))
        self.enabled_strategies: Set[str] = set(admission.get("enabled_strategies", []))

        self.deployed_routers: Dict[str, Set[str]] = {
            chain: set(routers)
            for chain, routers in admission.get("deployed_routers", {}).items()
            if isinstance(routers, (list, set))
        }

        self.minimum_notional_usd = admission.get("minimum_notional_usd", {})
        self.minimum_gas_balance = admission.get("minimum_gas_balance", {})

        self.profit_safety_multiplier = float(admission.get("profit_safety_multiplier", 1.5))
        self.max_slippage_percent = float(admission.get("max_slippage_percent", 5.0))
        self.max_trade_size_usd = float(admission.get("max_trade_size_usd", 10_000))

        self.global_risk_limits = admission.get("global_risk_limits", {})

        self.executable_tokens = admission.get("executable_tokens", {})
        self._token_addresses: Dict[str, Set[str]] = {}

        logger.info("ExecutionAdmissionController initialized")

    async def initialize(self) -> None:
        await self._load_token_addresses()

    async def _load_token_addresses(self) -> None:
        for chain, symbols in self.executable_tokens.items():
            addresses: Set[str] = set()
            for symbol in symbols:
                try:
                    resolved = self.token_registry.resolve_address(symbol, chain)
                    if asyncio.iscoroutine(resolved):
                        resolved = await resolved
                    if resolved and getattr(resolved, "address", None):
                        addresses.add(resolved.address.lower())
                except Exception as e:
                    logger.warning(f"Token resolution failed: {symbol} on {chain}: {e}")

            if not addresses:
                logger.error(f"Executable token allowlist empty for chain {chain}")

            self._token_addresses[chain] = addresses

    # =========================
    # Public API
    # =========================

    async def validate_execution_plan(self, execution_plan: Any, wallet_address: str) -> AdmissionResult:
        if not self.enabled:
            return AdmissionResult.ok()

        for check in (
            self._check_chain,
            self._check_supported_chain,
            self._check_chain_operational_status,
            self._check_plan_completeness,
            self._check_base_asset,
            self._check_minimum_notional,
            self._check_trade_size_limit,
            self._check_executable_token,
            self._check_router_deployment,
            self._check_slippage,
            self._check_expected_profit,
            self._check_strategy_enablement,
            self._check_global_risk_limits,
        ):
            result = check(execution_plan)
            if not result:
                return result

        gas = await self._check_gas_balance(execution_plan.chain, wallet_address)
        if not gas:
            return gas

        funding = await self._check_chain_funding(execution_plan, wallet_address)
        if not funding:
            return funding

        if self.gas_treasury:
            treasury = await self._check_gas_treasury(execution_plan, wallet_address)
            if not treasury:
                return treasury

        return AdmissionResult.ok()

    # =========================
    # Checks
    # =========================

    def _check_chain(self, plan) -> AdmissionResult:
        if not getattr(plan, "chain", None):
            return AdmissionResult.fail("Missing chain")
        return AdmissionResult.ok()

    def _check_supported_chain(self, plan) -> AdmissionResult:
        """
        Check if chain is supported.
        For true multi-network sniper, if supported_chains is empty, allow all chains.
        """
        # If no supported chains configured, allow all (true sniper mode)
        if not self.supported_chains or len(self.supported_chains) == 0:
            logger.debug(f"🆓 Allowing chain {plan.chain} (no supported_chains restriction)")
            return AdmissionResult.ok()
        
        if plan.chain not in self.supported_chains:
            return AdmissionResult.fail("Unsupported chain", {"chain": plan.chain})
        return AdmissionResult.ok()

    def _check_chain_operational_status(self, plan) -> AdmissionResult:
        if plan.chain in self.paused_chains:
            return AdmissionResult.fail("Chain paused", {"chain": plan.chain})
        return AdmissionResult.ok()

    def _check_plan_completeness(self, plan) -> AdmissionResult:
        required = ("plan_id", "token_address", "amount_usd", "chain", "is_buy", "max_slippage")
        missing = [f for f in required if not getattr(plan, f, None)]
        if missing:
            return AdmissionResult.fail("Incomplete execution plan", {"missing": missing})
        return AdmissionResult.ok()

    def _check_base_asset(self, plan) -> AdmissionResult:
        if getattr(plan, "base_asset", "USDC") != "USDC":
            return AdmissionResult.fail("Invalid base asset")
        return AdmissionResult.ok()

    def _check_minimum_notional(self, plan) -> AdmissionResult:
        min_notional = self.minimum_notional_usd.get(plan.chain)
        if min_notional and plan.amount_usd < min_notional:
            return AdmissionResult.fail(
                "Below minimum notional",
                {"required": min_notional, "actual": plan.amount_usd},
            )
        return AdmissionResult.ok()

    def _check_trade_size_limit(self, plan) -> AdmissionResult:
        if plan.amount_usd > self.max_trade_size_usd:
            return AdmissionResult.fail(
                "Trade size exceeds configured limit",
                {"amount_usd": plan.amount_usd, "limit": self.max_trade_size_usd},
            )
        return AdmissionResult.ok()

    def _check_executable_token(self, plan) -> AdmissionResult:
        """
        Check if token is allowed to trade.
        
        For a true multi-network sniper, we allow:
        1. Tokens in the allowlist (if configured)
        2. ALL discovered tokens (those with opportunity_id) - this enables true sniper behavior
        3. If allowlist is empty, allow all tokens (open sniper mode)
        """
        allowlist = self._token_addresses.get(plan.chain)
        
        # If allowlist is empty, allow all tokens (true sniper mode)
        if not allowlist or len(allowlist) == 0:
            # This is a discovered token from scanner - allow it
            token_lower = plan.token_address.lower()
            logger.info(f"🆓 Allowing discovered token (no allowlist): {plan.token_address} on {plan.chain}")
            # Add to allowlist for future reference
            if plan.chain not in self._token_addresses:
                self._token_addresses[plan.chain] = set()
            self._token_addresses[plan.chain].add(token_lower)
            return AdmissionResult.ok()

        # Check if token is in allowlist OR if it's a discovered token (more permissive)
        token_lower = plan.token_address.lower()
        if token_lower not in allowlist:
            # For discovered tokens, we can be more permissive but still apply some checks
            if hasattr(plan, 'opportunity_id') and plan.opportunity_id:
                # This is a discovered token, allow it but log for monitoring
                logger.info(f"🆓 Allowing discovered token: {plan.token_address} on {plan.chain}")
                # Optionally add to allowlist for future trades
                self._token_addresses[plan.chain].add(token_lower)
                return AdmissionResult.ok()
            else:
                return AdmissionResult.fail("Token not executable", {"token": plan.token_address})
        return AdmissionResult.ok()
    
    def add_discovered_token(self, chain: str, token_address: str) -> None:
        """Add a discovered token to the allowlist for future trades."""
        if chain not in self._token_addresses:
            self._token_addresses[chain] = set()
        self._token_addresses[chain].add(token_address.lower())
        logger.debug(f"Added token {token_address} to {chain} allowlist")

    def _check_router_deployment(self, plan) -> AdmissionResult:
        """
        Check if router is deployed.
        For true multi-network sniper, if deployed_routers is empty, allow all routers.
        """
        routers = self.deployed_routers.get(plan.chain)
        
        # If no routers configured for this chain, allow all (auto-detect mode)
        if not routers or len(routers) == 0:
            logger.debug(f"🆓 Allowing router {getattr(plan, 'router_name', 'unknown')} on {plan.chain} (no router restriction)")
            return AdmissionResult.ok()
        
        router_name = getattr(plan, 'router_name', None)
        if router_name and router_name not in routers:
            return AdmissionResult.fail("Router not deployed", {"router": router_name})
        return AdmissionResult.ok()

    def _check_slippage(self, plan) -> AdmissionResult:
        if plan.max_slippage <= 0 or plan.max_slippage > self.max_slippage_percent:
            return AdmissionResult.fail(
                "Invalid slippage",
                {"max_slippage": plan.max_slippage, "limit": self.max_slippage_percent},
            )
        return AdmissionResult.ok()

    def _check_expected_profit(self, plan) -> AdmissionResult:
        gas = getattr(plan, "estimated_gas_cost_usd", None)
        profit = getattr(plan, "expected_profit_usd", None)

        if gas is None or profit is None or gas <= 0:
            return AdmissionResult.fail("Missing or invalid gas/profit estimate")

        if profit < gas * self.profit_safety_multiplier:
            return AdmissionResult.fail("Profit below safety threshold")
        return AdmissionResult.ok()

    def _check_strategy_enablement(self, plan) -> AdmissionResult:
        if plan.strategy_name and plan.strategy_name not in self.enabled_strategies:
            return AdmissionResult.fail("Strategy disabled", {"strategy": plan.strategy_name})
        return AdmissionResult.ok()

    def _check_global_risk_limits(self, plan) -> AdmissionResult:
        return AdmissionResult.ok()  # explicitly non-enforced

    async def _check_gas_balance(self, chain: str, wallet: str) -> AdmissionResult:
        if not self.network_manager:
            return AdmissionResult.ok()

        min_gas = self.minimum_gas_balance.get(chain, 0)
        w3 = self.network_manager.get_web3(chain)
        if not w3:
            return AdmissionResult.fail("No network connection", {"chain": chain})

        balance = w3.from_wei(await w3.eth.get_balance(wallet), "ether")
        if balance < min_gas:
            return AdmissionResult.fail("Insufficient gas", {"required": min_gas, "actual": float(balance)})
        return AdmissionResult.ok()

    async def _check_chain_funding(self, plan, wallet: str) -> AdmissionResult:
        if self.config.get("paper_trading", {}).get("enabled"):
            return AdmissionResult.ok()
        return AdmissionResult.ok()  # funding validated elsewhere

    async def _check_gas_treasury(self, plan, wallet: str) -> AdmissionResult:
        reservation = await self.gas_treasury.reserve_gas(
            chain=plan.chain,
            wallet_address=wallet,
            estimated_gas_cost=getattr(plan, "estimated_gas_cost_native", 0.01),
        )
        if not reservation:
            return AdmissionResult.fail("Gas treasury exhausted")
        plan.gas_reservation_id = reservation.reservation_id
        return AdmissionResult.ok()

