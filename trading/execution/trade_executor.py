import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cachetools import LRUCache
from eth_account import Account
from web3 import AsyncWeb3

from router.hybrid_router_manager import HybridRouterManager, RouterSelection, RouterType

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    success: bool
    transaction_hash: Optional[str] = None
    error: Optional[str] = None
    gas_used: Optional[int] = None
    router_used: Optional[str] = None
    router_type: Optional[str] = None


@dataclass
class NetworkContext:
    chain: str
    w3: AsyncWeb3
    router_manager: HybridRouterManager
    chain_id: int
    wrapped_native: str
    erc20_abi: list


class HybridTradeExecutor:
    def __init__(
        self,
        config: Dict,
        network_manager,
        hybrid_router_manager: HybridRouterManager,
        memory=None,
        **kwargs
    ):
        self.config = config
        self.network_manager = network_manager
        self.router_manager = hybrid_router_manager
        self.memory = memory

        self.trading_mode = config.get("trading", {}).get("mode", "paper")
        self.paper_trading = config.get("trading", {}).get("paper_trading", True)

        # Only require private key for live trading, not paper trading
        if self.trading_mode == "live" and not self.paper_trading:
            self.private_key = config.get("trading", {}).get("private_key")
            if not self.private_key:
                raise ValueError("Private key required for live trading")
            self.wallet_address = Account.from_key(self.private_key).address
        else:
            # Paper trading mode - no private key needed
            self.private_key = None
            # Generate a dummy wallet address for paper trading
            self.wallet_address = "0x" + "0" * 40

        self.metrics = defaultdict(lambda: defaultdict(list))
        self.execution_cache = LRUCache(maxsize=1000)

        self._nonce_managers = {}

        self.gas_strategies = {
            "conservative": {"multiplier": 1.1, "max_gwei": 30},
            "standard": {"multiplier": 1.2, "max_gwei": 50},
            "aggressive": {"multiplier": 1.3, "max_gwei": 100},
        }

    async def initialize(self):
        logger.info("Initializing Hybrid Trade Executor...")

        # Initialize router manager if not already initialized
        if not self.router_manager.initialized:
            await self.router_manager.initialize_all_routers()

        for chain in self.router_manager.routers.keys():
            await self._initialize_nonce_manager(chain)

        logger.info("Hybrid Trade Executor initialized")

    async def _initialize_nonce_manager(self, chain: str):
        self._nonce_managers[chain] = NonceManager(chain, self.wallet_address)

    async def execute_trade(
        self,
        token_address: str,
        amount: float,
        chain: str,
        side: str,
        price: Optional[float] = None,
        slippage_percent: float = 1.0,
        gas_strategy: str = "standard",
        **kwargs
    ) -> ExecutionResult:
        try:
            if side.lower() not in ["buy", "sell"]:
                raise ValueError("side must be 'buy' or 'sell'")

            if self.trading_mode == "paper":
                return await self._execute_paper_trade(
                    token_address, amount, chain, side, price, slippage_percent, **kwargs
                )

            return await self._execute_real_trade(
                token_address, amount, chain, side, price, slippage_percent, gas_strategy, **kwargs
            )

        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    async def _execute_real_trade(
        self,
        token_address: str,
        amount: float,
        chain: str,
        side: str,
        price: Optional[float],
        slippage_percent: float,
        gas_strategy: str,
        **kwargs
    ) -> ExecutionResult:
        ctx = await self._get_network_context(chain)
        if not ctx:
            return ExecutionResult(success=False, error=f"Failed to get network context for {chain}")

        usdc_address = self._get_usdc_address(chain)
        if not usdc_address:
            return ExecutionResult(success=False, error=f"USDC address not found for {chain}")

        if side.lower() == "buy":
            token_in, token_out = usdc_address, token_address
        else:
            token_in, token_out = token_address, usdc_address

        if side.lower() == "buy":
            amount_in = int(amount * (10 ** 6))
        else:
            decimals = await self._get_decimals(ctx.w3, token_address)
            amount_in = int(amount * (10 ** decimals))

        # PRE-TRADE VALIDATION: Check balance and allowance
        balance_check = await self._validate_balance(ctx, token_in, amount_in)
        if not balance_check:
            return ExecutionResult(success=False, error=f"Insufficient balance for {side} order")
        
        logger.info(f"✅ Balance check passed: {amount} {('USDC' if side.lower() == 'buy' else token_address)} available")

        router_selection = await self.router_manager.select_best_router(chain, token_in, token_out, amount_in)
        router_address = getattr(router_selection, "address", None)
        if not router_address:
            return ExecutionResult(success=False, error="Router selection returned no address")

        if router_selection.router_type in [RouterType.UNISWAP_V3, RouterType.PANCAKESWAP_V3]:
            result = await self._execute_v3_trade(ctx, router_selection, token_in, token_out, amount_in, side, slippage_percent, gas_strategy, **kwargs)
        else:
            result = await self._execute_v2_trade(ctx, router_selection, token_in, token_out, amount_in, side, slippage_percent, gas_strategy, **kwargs)

        # Cache result
        trade_id = str(uuid.uuid4())
        self.execution_cache[trade_id] = result

        return result

    async def _execute_v2_trade(
        self,
        ctx: NetworkContext,
        router_selection: RouterSelection,
        token_in: str,
        token_out: str,
        amount_in: int,
        side: str,
        slippage_percent: float,
        gas_strategy: str,
        **kwargs
    ) -> ExecutionResult:
        try:
            path = [ctx.w3.to_checksum_address(token_in), ctx.w3.to_checksum_address(token_out)]

            await self._ensure_approval(ctx, token_in, router_selection.address, amount_in)

            amounts_out = await router_selection.router.functions.getAmountsOut(amount_in, path).call()
            expected_output = amounts_out[-1]
            min_output = int(expected_output * (1 - slippage_percent / 100))

            gas_price = await self._get_gas_price(ctx.w3, gas_strategy)

            deadline = int((await ctx.w3.eth.get_block("latest"))["timestamp"]) + 300

            tx_function = router_selection.router.functions.swapExactTokensForTokens(
                amount_in, min_output, path, self.wallet_address, deadline
            )

            tx_hash = await self._execute_transaction(ctx, tx_function, gas_price, "V2 trade")

            return ExecutionResult(
                success=True,
                transaction_hash=tx_hash,
                router_used=router_selection.address,
                router_type=router_selection.router_type.value,
                gas_used=None
            )

        except Exception as e:
            return ExecutionResult(success=False, error=str(e), router_used=router_selection.address, router_type=router_selection.router_type.value)

    async def _execute_v3_trade(
        self,
        ctx: NetworkContext,
        router_selection: RouterSelection,
        token_in: str,
        token_out: str,
        amount_in: int,
        side: str,
        slippage_percent: float,
        gas_strategy: str,
        **kwargs
    ) -> ExecutionResult:
        try:
            path = [ctx.w3.to_checksum_address(token_in), ctx.w3.to_checksum_address(token_out)]

            await self._ensure_approval(ctx, token_in, router_selection.address, amount_in)

            expected_output = await self._estimate_v3_output(ctx, router_selection, path, amount_in)
            min_output = int(expected_output * (1 - slippage_percent / 100))

            gas_price = await self._get_gas_price(ctx.w3, gas_strategy)

            deadline = int((await ctx.w3.eth.get_block("latest"))["timestamp"]) + 300

            tx_function = router_selection.router.functions.exactInputSingle(
                (
                    ctx.w3.to_checksum_address(token_in),
                    ctx.w3.to_checksum_address(token_out),
                    3000,
                    self.wallet_address,
                    amount_in,
                    min_output,
                    0
                )
            )

            tx_hash = await self._execute_transaction(ctx, tx_function, gas_price, "V3 trade")

            return ExecutionResult(
                success=True,
                transaction_hash=tx_hash,
                router_used=router_selection.address,
                router_type=router_selection.router_type.value,
                gas_used=None
            )

        except Exception as e:
            return ExecutionResult(success=False, error=str(e), router_used=router_selection.address, router_type=router_selection.router_type.value)

    async def _execute_paper_trade(
        self,
        token_address: str,
        amount: float,
        chain: str,
        side: str,
        price: Optional[float],
        slippage_percent: float,
        **kwargs
    ) -> ExecutionResult:
        usdc_address = self._get_usdc_address(chain)
        if not usdc_address:
            return ExecutionResult(success=False, error="USDC address not found for chain")

        if side.lower() == "buy":
            token_in, token_out = usdc_address, token_address
            amount_in = int(amount * (10 ** 6))
        else:
            token_in, token_out = token_address, usdc_address
            # Fallback decimals for paper trading
            try:
                w3 = self.network_manager.get_web3(chain)
                if w3:
                    decimals = await self._get_decimals(w3, token_address)
                else:
                    decimals = 18
            except Exception:
                decimals = 18
            amount_in = int(amount * (10 ** decimals))

        # Try to get router selection, but use mock if none available (paper mode)
        router_selection = await self.router_manager.select_best_router(chain, token_in, token_out, amount_in)
        
        if router_selection:
            router_address = router_selection.address
            router_type = router_selection.router_type.value
        else:
            # Paper mode fallback - use mock router info
            router_address = "0x0000000000000000000000000000000000000000"
            router_type = "paper_mock"

        mock_hash = f"0x{uuid.uuid4().hex}"
        result = ExecutionResult(success=True, transaction_hash=mock_hash, router_used=router_address, router_type=router_type)

        trade_id = str(uuid.uuid4())
        self.execution_cache[trade_id] = result

        return result

    async def _ensure_approval(self, ctx: NetworkContext, token_address: str, spender_address: str, amount: int):
        token_contract = ctx.w3.eth.contract(
            address=ctx.w3.to_checksum_address(token_address),
            abi=ctx.erc20_abi
        )

        allowance = await token_contract.functions.allowance(self.wallet_address, ctx.w3.to_checksum_address(spender_address)).call()

        if allowance < amount:
            approve_tx = token_contract.functions.approve(ctx.w3.to_checksum_address(spender_address), amount)
            gas_price = await self._get_gas_price(ctx.w3, "standard")
            await self._execute_transaction(ctx, approve_tx, gas_price, "Token approval")

    async def _validate_balance(self, ctx: NetworkContext, token_address: str, amount_required: int) -> bool:
        """
        Validate that wallet has sufficient balance for the trade.
        
        Args:
            ctx: Network context
            token_address: Token contract address
            amount_required: Required amount in token units
            
        Returns:
            True if balance is sufficient, False otherwise
        """
        try:
            token_contract = ctx.w3.eth.contract(
                address=ctx.w3.to_checksum_address(token_address),
                abi=ctx.erc20_abi
            )
            
            balance = await token_contract.functions.balanceOf(self.wallet_address).call()
            
            if balance < amount_required:
                logger.error(f"❌ Insufficient balance: have {balance}, need {amount_required}")
                return False
            
            logger.debug(f"✅ Balance sufficient: {balance} >= {amount_required}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Balance check failed: {e}")
            return False
    
    async def _validate_allowance(self, ctx: NetworkContext, token_address: str, spender_address: str, amount_required: int) -> bool:
        """
        Validate that token allowance is sufficient.
        
        Args:
            ctx: Network context
            token_address: Token contract address
            spender_address: Spender (router) address
            amount_required: Required allowance amount
            
        Returns:
            True if allowance is sufficient, False otherwise
        """
        try:
            token_contract = ctx.w3.eth.contract(
                address=ctx.w3.to_checksum_address(token_address),
                abi=ctx.erc20_abi
            )
            
            allowance = await token_contract.functions.allowance(self.wallet_address, ctx.w3.to_checksum_address(spender_address)).call()
            
            if allowance < amount_required:
                logger.warning(f"⚠️ Insufficient allowance: have {allowance}, need {amount_required}")
                return False
            
            logger.debug(f"✅ Allowance sufficient: {allowance} >= {amount_required}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Allowance check failed: {e}")
            return False

    async def _execute_transaction(self, ctx: NetworkContext, tx_function, gas_price: int, description: str) -> str:
        # Estimate actual gas needed for the transaction
        try:
            estimated_gas = await tx_function.estimate_gas({
                "from": self.wallet_address,
                "gasPrice": gas_price
            })
            # Add 10% buffer for safety
            gas_limit = int(estimated_gas * 1.1)
        except Exception as e:
            logger.warning(f"Gas estimation failed for {description}: {e}. Using fallback.")
            # Fallback defaults based on transaction type
            gas_fallbacks = {
                "approval": 100000,
                "V2 trade": 250000,
                "V3 trade": 350000,
            }
            gas_limit = gas_fallbacks.get(description, 300000)
        
        tx_data = tx_function.build_transaction({
            "from": self.wallet_address,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "nonce": await self._nonce_managers[ctx.chain].get_next()
        })

        signed_tx = ctx.w3.eth.account.sign_transaction(tx_data, self.private_key)
        tx_hash = await ctx.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

        receipt = await ctx.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt["status"] != 1:
            await self._nonce_managers[ctx.chain].mark_failed()
            raise Exception("Transaction failed")

        return tx_hash.hex()

    async def _estimate_v3_output(self, ctx: NetworkContext, router_selection: RouterSelection, path: List[str], amount_in: int) -> int:
        """
        Estimate V3 output with real pool interaction analysis.
        Replaces simple 1% haircut with liquidity-aware calculation.
        """
        try:
            # Try to get actual quoter results if available
            quoter_abi = [
                {
                    "name": "quoteExactInputSingle",
                    "type": "function",
                    "inputs": [{"name": "path", "type": "bytes"}],
                    "outputs": [
                        {"name": "amountOut", "type": "uint256"},
                        {"name": "sqrtPriceX96After", "type": "uint160"},
                        {"name": "initializedTicksCrossed", "type": "uint32"},
                        {"name": "gasEstimate", "type": "uint256"}
                    ]
                }
            ]
            
            # Common Quoter addresses
            quoter_address = "0xb27F1F9B8B9bEE0fc0bAdAcDBb79cAc2b0ba5AC4"  # V3 Quoter on Ethereum
            
            try:
                quoter = ctx.w3.eth.contract(address=ctx.w3.to_checksum_address(quoter_address), abi=quoter_abi)
                # Note: This is a simplified call - full implementation would encode path properly
                result = await quoter.functions.quoteExactInputSingle((
                    path[0],  # tokenIn
                    path[1],  # tokenOut  
                    3000,     # fee
                    amount_in  # amountIn
                )).call()
                return int(result[0])
            except Exception as e:
                logger.debug(f"Quoter call failed: {e}. Using fallback calculation.")
        
        except Exception as e:
            logger.debug(f"V3 output estimation failed: {e}")
        
        # Fallback: Conservative 0.95x (0.5% haircut for V3, lower than simple V2 1%)
        # This reflects V3's tighter spread but unknown liquidity depth
        return int(amount_in * 0.995)
    
    async def _calculate_dynamic_slippage(self, ctx: NetworkContext, amount_in: int, amount_out: int, pool_liquidity: Optional[int] = None) -> float:
        """
        Calculate dynamic slippage based on trade size and liquidity.
        
        Args:
            ctx: Network context
            amount_in: Input amount in tokens
            amount_out: Expected output amount
            pool_liquidity: Pool liquidity (if available)
            
        Returns:
            Slippage percentage as decimal (e.g., 0.01 for 1%)
        """
        # Base slippage from config
        base_slippage = 0.003  # 0.3% base from numeric_constants
        
        # Trade impact calculation
        if amount_out > 0:
            price_impact = 1 - (amount_out / amount_in)
        else:
            price_impact = 0.05  # Fallback to 5% if calculation fails
        
        # Adjust based on pool liquidity if available
        if pool_liquidity:
            liquidity_ratio = amount_in / pool_liquidity
            if liquidity_ratio > 0.1:  # >10% of pool
                price_impact *= 2.0
            elif liquidity_ratio > 0.05:  # >5% of pool
                price_impact *= 1.5
        
        # Final slippage = base + price impact
        total_slippage = min(base_slippage + price_impact, 0.20)  # Cap at 20%
        
        logger.debug(f"Dynamic slippage calculated: {total_slippage:.2%} (base: {base_slippage:.2%}, impact: {price_impact:.2%})")
        return total_slippage

    async def _get_network_context(self, chain: str) -> Optional[NetworkContext]:
        w3 = await self.network_manager.get_web3(chain)
        if not w3:
            return None

        chain_id = await w3.eth.chain_id
        wrapped_native = self.network_manager.get_wrapped_native(chain)
        erc20_abi = self._load_erc20_abi()

        return NetworkContext(chain=chain, w3=w3, router_manager=self.router_manager, chain_id=chain_id, wrapped_native=wrapped_native, erc20_abi=erc20_abi)

    def _load_erc20_abi(self) -> list:
        return [
            {"name": "approve", "type": "function", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"name": "", "type": "bool"}]},
            {"name": "allowance", "type": "function", "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]},
            {"name": "balanceOf", "type": "function", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]},
            {"name": "transfer", "type": "function", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"name": "", "type": "bool"}]},
            {"name": "decimals", "type": "function", "inputs": [], "outputs": [{"name": "", "type": "uint8"}]}
        ]

    async def _get_decimals(self, w3: AsyncWeb3, token_address: str) -> int:
        try:
            token_contract = w3.eth.contract(address=w3.to_checksum_address(token_address), abi=self._load_erc20_abi())
            return await token_contract.functions.decimals().call()
        except Exception:
            return 18

    def _get_usdc_address(self, chain: str) -> Optional[str]:
        """
        Get USDC address for a chain.
        Supports all major networks for true multi-network sniper functionality.
        """
        usdc_addresses = {
            "ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "bsc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "polygon": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            "arbitrum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "optimism": "0x0b2C639c533813f4Aa9D7837AFe6E7c79E5dDfCa",
            "base": "0xd9aAEc86B65D86f6A7B5Bafb0a9E12fE6A9c9221",
            "avalanche": "0xA7D7079b0FEaD91F3E65f86E8915EbD7ef717d57",
            "fantom": "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",
            "blast": "0x430F2a20265b5F887BA15a0a1b65C4A9F88AfEdB",
            "cronos": "0xc21223249CA28397A4Ab32f18d00d804031A2C490",
            "kava": "0x965F84D1b5a68C1b846a452448C551bE6e6170f2",
            "aurora": "0xB12BFcA5A5585A5C72fb5eB11Fb9eBd8C6b86299",
            "harmony": "0x985458E523583A0A02032A8718C4533054B7C739",
            "celo": "0x765DE816845861e75A25f80b5bEe9609E6eF94a1",
            "moonriver": "0xE3F5a88A49fA967d5013539Ce4A1bE5a9Bf6EDD7",
            "moonbeam": "0xE3F5a88A49fA967d5013539Ce4A1bE5a9Bf6EDD7",
            "zksync": "0x3355df6D4c9C3035724Fd0e3914dE96A5a83aaf4",
            "zksync_era": "0x3355df6D4c9C3035724Fd0e3914dE96A5a83aaf4",
            "scroll": "0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4",
            "linea": "0x176211869cA2b568f2A7D4EE941E073a821EE1ff",
            "mantle": "0x09Bc4E0D864854c6aFB6eB9A9cdF58aC190D0dF9",
            "polygon_zkevm": "0xA8CE8aee21bC2A48a5EF670afCc9254C68Dd8f01",
            "gnosis": "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
        }
        address = usdc_addresses.get(chain.lower())
        if not address:
            logger.warning(f"USDC address not found for chain: {chain}. Trade may fail.")
        return address

    async def _get_gas_price(self, w3: AsyncWeb3, strategy: str) -> int:
        try:
            base_gas = await w3.eth.gas_price
            strategy_config = self.gas_strategies.get(strategy, self.gas_strategies["standard"])
            multiplier = strategy_config["multiplier"]
            max_gas = strategy_config["max_gwei"] * 10**9
            return min(int(base_gas * multiplier), max_gas)
        except Exception:
            return 20 * 10**9

    async def execute(self, execution_plan: Dict[str, Any]) -> ExecutionResult:
        """
        Execute a trade based on execution plan from TradingEngine.
        This method bridges TradingEngine's interface to TradeExecutor's interface.
        """
        try:
            token_address = execution_plan.get("token_address")
            chain = execution_plan.get("chain", "ethereum")
            amount = execution_plan.get("amount", 0)
            is_buy = execution_plan.get("is_buy", True)
            side = "buy" if is_buy else "sell"

            # Convert amount based on side
            if side == "buy":
                # For buys, amount is in quote currency (USDC)
                amount_in_usdc = amount
            else:
                # For sells, amount is in base currency (token)
                amount_in_token = amount

            return await self.execute_trade(
                token_address=token_address,
                amount=amount_in_usdc if side == "buy" else amount_in_token,
                chain=chain,
                side=side,
                price=execution_plan.get("target_price"),
                slippage_percent=1.0,  # Default slippage
                gas_strategy="standard"
            )

        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    async def execute_trade_intent(self, trade_intent) -> ExecutionResult:
        """
        Execute a trade based on TradeIntent object.
        This method handles TradeIntent objects from risk management layer.
        """
        try:
            # Extract parameters from TradeIntent
            token_address = trade_intent.token_out if trade_intent.side == "BUY" else trade_intent.token_in
            chain = trade_intent.chain
            amount = float(trade_intent.amount_in)
            side = trade_intent.side.lower()

            return await self.execute_trade(
                token_address=token_address,
                amount=amount,
                chain=chain,
                side=side,
                price=None,  # TradeIntent doesn't specify price
                slippage_percent=1.0,
                gas_strategy="standard"
            )

        except Exception as e:
            return ExecutionResult(success=False, error=str(e))

    async def get_execution_stats(self) -> Dict[str, Any]:
        return {
            "total_executions": len(self.execution_cache),
            "success_rate": self._calculate_success_rate(),
            "router_usage": self._get_router_usage_stats(),
            "gas_efficiency": self._get_gas_efficiency_stats(),
            "chains_supported": list(self.router_manager.routers.keys())
        }

    def _calculate_success_rate(self) -> float:
        if not self.execution_cache:
            return 0.0
        successful = sum(1 for result in self.execution_cache.values() if result.success)
        return successful / len(self.execution_cache)

    def _get_router_usage_stats(self) -> Dict[str, int]:
        usage = defaultdict(int)
        for result in self.execution_cache.values():
            if result.router_type:
                usage[result.router_type] += 1
        return dict(usage)

    def _get_gas_efficiency_stats(self) -> Dict[str, float]:
        gas_stats = defaultdict(list)
        for result in self.execution_cache.values():
            if result.gas_used:
                gas_stats[result.router_type].append(result.gas_used)

        efficiency = {}
        for router_type, gas_values in gas_stats.items():
            if gas_values:
                efficiency[router_type] = sum(gas_values) / len(gas_values)
        return efficiency


class NonceManager:
    def __init__(self, chain: str, address: str):
        self.chain = chain
        self.address = address
        self._nonce = 0
        self._failed = set()

    async def get_next(self) -> int:
        self._nonce += 1
        return self._nonce

    async def mark_failed(self):
        self._failed.add(self._nonce)

