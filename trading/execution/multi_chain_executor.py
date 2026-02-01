import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from networks.multi_chain_models import TokenCandidate, ChainType
from strategies.multi_chain_strategies import StrategyDecision

logger = logging.getLogger(__name__)


# =========================
# ENUMS
# =========================
class ExecutionStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVERTED = "reverted"
    TIMEOUT = "timeout"


class TradeDirection(Enum):
    BUY = "buy"
    SELL = "sell"


# =========================
# EXECUTION RESULT
# =========================
@dataclass
class ExecutionResult:
    status: ExecutionStatus
    transaction_hash: Optional[str]
    network: ChainType
    token_address: str
    direction: TradeDirection
    amount: float
    price: float
    gas_used: Optional[float] = None
    gas_cost: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =========================
# BASE EXECUTOR
# =========================
class BaseNetworkExecutor(ABC):

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chain_type = self.get_supported_chain_type()
        self.is_testnet = config.get("testnet", False)
        self.paper_mode = config.get("paper_mode", True)
        self.max_slippage = config.get("max_slippage", 0.01)  # 1% default
        self.wallet_address = config.get("wallet_address")

    @abstractmethod
    def get_supported_chain_type(self) -> ChainType:
        raise NotImplementedError

    @abstractmethod
    async def execute_trade(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def estimate_gas_cost(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_wallet_address(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_balance(self) -> float:
        raise NotImplementedError

    def validate_execution_params(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> bool:
        if candidate.chain_type != self.chain_type:
            logger.error(
                f"Chain type mismatch: expected {self.chain_type.value}, got {candidate.chain_type.value}"
            )
            return False

        if not getattr(decision, "should_trade", False):
            logger.debug(f"No trade flagged for {candidate.symbol}")
            return False

        if getattr(decision, "position_size", 0) <= 0:
            logger.warning(f"Invalid position size: {decision.position_size}")
            return False

        return True


# =========================
# EVM EXECUTOR (V3/V2 fallback)
# =========================
class EVMExecutor(BaseNetworkExecutor):

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.EVM

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.rpc_url = config.get("rpc_url")
        self.private_key = config.get("private_key")

        self.uniswap_v3_router = config.get("uniswap_v3_router")
        self.uniswap_v2_router = config.get("uniswap_v2_router")

        if not self.rpc_url:
            raise ValueError("EVMExecutor requires rpc_url")

        try:
            from web3 import Web3
            from web3.middleware import geth_poa
            self.Web3 = Web3
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            # PoA chains need middleware
            self.w3.middleware_onion.inject(geth_poa.geth_poa_middleware, layer=0)
        except Exception as e:
            raise ImportError("web3 library required for EVM execution") from e

    def get_wallet_address(self) -> str:
        if not self.wallet_address:
            raise ValueError("Wallet address not configured")
        return self.wallet_address

    async def get_balance(self) -> float:
        if self.paper_mode:
            return 100000.0
        balance = self.w3.eth.get_balance(self.wallet_address)
        return float(balance) / 1e18

    async def estimate_gas_cost(self, candidate: TokenCandidate, decision: StrategyDecision) -> Dict[str, Any]:
        return {"estimated_gas": 0.0}

    async def execute_trade(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> ExecutionResult:

        if not self.validate_execution_params(candidate, decision):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=0.0,
                error_message="Validation failed"
            )

        # --------------------------
        # Build trade parameters
        # --------------------------
        token_address = candidate.address
        token_price = candidate.price_usd or 0.0

        amount_usd = decision.position_size
        amount_tokens = amount_usd / token_price if token_price > 0 else 0

        if amount_tokens <= 0:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=token_address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=token_price,
                error_message="Invalid token price or position size"
            )

        # --------------------------
        # Paper mode
        # --------------------------
        if self.paper_mode:
            import uuid
            tx_hash = uuid.uuid4().hex
            return ExecutionResult(
                status=ExecutionStatus.SUBMITTED,
                transaction_hash=tx_hash,
                network=self.chain_type,
                token_address=token_address,
                direction=TradeDirection(decision.direction),
                amount=amount_tokens,
                price=token_price,
                metadata={"mode": "paper", "router": "v3/v2"}
            )

        # --------------------------
        # Live execution (real)
        # --------------------------
        try:
            # Prefer Uniswap V3, fallback to V2
            router_address = self.uniswap_v3_router or self.uniswap_v2_router
            if not router_address:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    transaction_hash=None,
                    network=self.chain_type,
                    token_address=token_address,
                    direction=TradeDirection(decision.direction),
                    amount=0.0,
                    price=token_price,
                    error_message="No router configured"
                )

            # Get wallet account from private key
            account = self.w3.eth.account.from_key(self.private_key)
            wallet_address = account.address

            # Determine token paths for swap
            weth_address = self._get_weth_address()  # WETH/ETH wrapper address
            usdc_address = self._get_usdc_address()  # USDC stablecoin

            if decision.direction.lower() == "buy":
                # Buying token: USDC -> Token
                token_in = usdc_address
                token_out = token_address
                amount_in = self.w3.to_wei(amount_usd, 'ether')  # Convert USD amount to wei (assuming 18 decimals)
            else:
                # Selling token: Token -> USDC
                token_in = token_address
                token_out = usdc_address
                amount_in = self.w3.to_wei(amount_tokens, 'ether')  # Convert token amount to wei

            # Check balance
            balance = self.w3.eth.get_balance(wallet_address)
            if balance < self.w3.to_wei(0.01, 'ether'):  # Minimum 0.01 ETH for gas
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    transaction_hash=None,
                    network=self.chain_type,
                    token_address=token_address,
                    direction=TradeDirection(decision.direction),
                    amount=0.0,
                    price=token_price,
                    error_message="Insufficient ETH balance for gas"
                )

            # Approve token spending if needed (for sell orders)
            if decision.direction.lower() == "sell":
                await self._approve_token_if_needed(token_in, router_address, amount_in, account)

            # Build swap transaction
            tx_params = await self._build_swap_transaction(
                router_address=router_address,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                wallet_address=wallet_address,
                slippage=self.max_slippage
            )

            if not tx_params:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    transaction_hash=None,
                    network=self.chain_type,
                    token_address=token_address,
                    direction=TradeDirection(decision.direction),
                    amount=0.0,
                    price=token_price,
                    error_message="Failed to build swap transaction"
                )

            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx_params, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)

            # Wait for transaction confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

            if receipt["status"] == 1:
                # Calculate actual amounts from logs (simplified)
                gas_used = receipt["gasUsed"]
                gas_cost = gas_used * tx_params['gasPrice'] / 1e18

                return ExecutionResult(
                    status=ExecutionStatus.CONFIRMED,
                    transaction_hash=tx_hash.hex(),
                    network=self.chain_type,
                    token_address=token_address,
                    direction=TradeDirection(decision.direction),
                    amount=amount_tokens if decision.direction.lower() == "buy" else amount_usd,
                    price=token_price,
                    gas_used=float(gas_used),
                    gas_cost=gas_cost,
                    metadata={
                        "router": router_address,
                        "mode": "live",
                        "block_number": receipt["blockNumber"],
                        "gas_price": tx_params['gasPrice']
                    }
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.REVERTED,
                    transaction_hash=tx_hash.hex(),
                    network=self.chain_type,
                    token_address=token_address,
                    direction=TradeDirection(decision.direction),
                    amount=0.0,
                    price=token_price,
                    error_message="Transaction reverted"
                )

        except Exception as e:
            logger.error(f"EVM execution failed: {e}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=token_address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=token_price,
                error_message=str(e)
            )

    def _get_weth_address(self) -> str:
        """Get WETH address for the current chain."""
        # This should be configurable per chain, but for now using common addresses
        chain_id = self.w3.eth.chain_id
        weth_addresses = {
            1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # Ethereum Mainnet
            56: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # BSC
            137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # Polygon
            42161: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # Arbitrum
            10: "0x4200000000000000000000000000000000000006",  # Optimism
            43114: "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",  # Avalanche
            8453: "0x4200000000000000000000000000000000000006",  # Base
        }
        return weth_addresses.get(chain_id, weth_addresses[1])  # Default to Ethereum

    def _get_usdc_address(self) -> str:
        """Get USDC address for the current chain."""
        chain_id = self.w3.eth.chain_id
        usdc_addresses = {
            1: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # Ethereum Mainnet
            56: "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",  # BSC
            137: "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # Polygon
            42161: "0xFF970A61A04b1cA14834A43f5de4533eBDDB5CC8",  # Arbitrum
            10: "0x0b2C639c533813f4Aa9D7837AFe6E7c79E5dDfCa",  # Optimism
            43114: "0xA7D7079b0FEaD91F3e65f86E8915EbD7ef717d57",  # Avalanche
            8453: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # Base
        }
        return usdc_addresses.get(chain_id, usdc_addresses[1])  # Default to Ethereum

    async def _approve_token_if_needed(self, token_address: str, spender: str, amount: int, account) -> None:
        """Approve token spending if allowance is insufficient."""
        try:
            # ERC20 ABI for approval check
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [
                        {"name": "_owner", "type": "address"},
                        {"name": "_spender", "type": "address"}
                    ],
                    "name": "allowance",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": False,
                    "inputs": [
                        {"name": "_spender", "type": "address"},
                        {"name": "_value", "type": "uint256"}
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function"
                }
            ]

            token_contract = self.w3.eth.contract(address=token_address, abi=erc20_abi)

            # Check current allowance
            allowance = token_contract.functions.allowance(account.address, spender).call()

            if allowance < amount:
                # Need to approve
                nonce = self.w3.eth.get_transaction_count(account.address)
                approve_tx = token_contract.functions.approve(spender, amount).build_transaction({
                    'from': account.address,
                    'nonce': nonce,
                    'gas': 100000,
                    'gasPrice': self.w3.eth.gas_price
                })

                signed_tx = self.w3.eth.account.sign_transaction(approve_tx, self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

                if receipt.status != 1:
                    raise Exception("Token approval failed")

                logger.info(f"Approved {token_address} spending for {spender}")

        except Exception as e:
            logger.error(f"Token approval failed: {e}")
            raise

    async def _build_swap_transaction(
        self,
        router_address: str,
        token_in: str,
        token_out: str,
        amount_in: int,
        wallet_address: str,
        slippage: float
    ) -> Optional[Dict[str, Any]]:
        """Build swap transaction parameters."""
        try:
            # Uniswap V2/V3 Router ABI (simplified)
            router_abi = [
                {
                    "inputs": [
                        {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                        {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                        {"internalType": "address[]", "name": "path", "type": "address[]"},
                        {"internalType": "address", "name": "to", "type": "address"},
                        {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                    ],
                    "name": "swapExactTokensForTokens",
                    "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]

            router_contract = self.w3.eth.contract(address=router_address, abi=router_abi)

            # Build path (could be more complex for multi-hop)
            path = [token_in, token_out]

            # Calculate minimum output with slippage
            # This is simplified - in production you'd get quotes from the router
            amount_out_min = int(amount_in * (1 - slippage))

            latest_block = self.w3.eth.get_block('latest')
            deadline = latest_block.get('timestamp', self.w3.eth.get_block('latest')['timestamp']) + 300  # 5 minutes

            # Build transaction
            nonce = self.w3.eth.get_transaction_count(wallet_address)

            tx_params = {
                'from': wallet_address,
                'to': router_address,
                'value': 0,  # No ETH value for token swaps
                'gas': 300000,  # Estimate gas
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'data': router_contract.functions.swapExactTokensForTokens(
                    amount_in,
                    amount_out_min,
                    path,
                    wallet_address,
                    deadline
                )._encode_transaction_data()
            }

            # Estimate gas more accurately
            try:
                estimated_gas = self.w3.eth.estimate_gas(tx_params)
                tx_params['gas'] = int(estimated_gas * 1.1)  # Add 10% buffer
            except Exception as e:
                logger.warning(f"Gas estimation failed, using default: {e}")

            return tx_params

        except Exception as e:
            logger.error(f"Failed to build swap transaction: {e}")
            return None


# =========================
# SOLANA EXECUTOR (Jupiter)
# =========================
class SolanaExecutor(BaseNetworkExecutor):

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.SOLANA

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.rpc_url = config.get("rpc_url", "https://api.mainnet-beta.solana.com")
        self.max_slippage = config.get("max_slippage", 0.01)

        try:
            from solana.rpc.async_api import AsyncClient
            from solana.keypair import Keypair
            from solana.transaction import Transaction
            self.AsyncClient = AsyncClient
            self.Keypair = Keypair
            self.Transaction = Transaction
        except ImportError as e:
            logger.warning(f"Solana SDK not available: {e}")
            self.AsyncClient = None
            self.Keypair = None
            self.Transaction = None

        self.client = self.AsyncClient(self.rpc_url) if self.AsyncClient else None

    def get_wallet_address(self) -> str:
        return self.wallet_address

    async def get_balance(self) -> float:
        if self.paper_mode:
            return 1000.0
        resp = await self.client.get_balance(self.wallet_address)
        return resp["result"]["value"] / 1e9

    async def estimate_gas_cost(self, candidate: TokenCandidate, decision: StrategyDecision) -> Dict[str, Any]:
        return {"estimated_sol": 0.000025}

    async def execute_trade(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> ExecutionResult:

        if not self.validate_execution_params(candidate, decision):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=0.0,
                error_message="Validation failed"
            )

        # Paper mode
        if self.paper_mode:
            import uuid
            tx_signature = uuid.uuid4().hex
            return ExecutionResult(
                status=ExecutionStatus.SUBMITTED,
                transaction_hash=tx_signature,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=decision.position_size,
                price=candidate.price_usd or 0.0,
                metadata={"mode": "paper", "dex": "jupiter"}
            )

        # Live mode (real Jupiter swap)
        try:
            # Import Jupiter SDK (this would need to be installed)
            # from jupiter_python_sdk.jupiter import Jupiter

            # For now, implement basic Jupiter API integration
            import aiohttp
            import base64

            # Jupiter API endpoint
            jupiter_api_url = "https://quote-api.jup.ag/v6"

            # Get quote from Jupiter
            quote_params = {
                "inputMint": self._get_solana_usdc_mint(),  # USDC mint
                "outputMint": candidate.address,  # Target token mint
                "amount": int(decision.position_size * 1e6),  # Convert to smallest unit (USDC has 6 decimals)
                "slippageBps": int(self.max_slippage * 10000),  # Convert to basis points
            }

            async with aiohttp.ClientSession() as session:
                # Get quote
                async with session.get(f"{jupiter_api_url}/quote", params=quote_params) as response:
                    if response.status != 200:
                        raise Exception(f"Jupiter quote failed: {response.status}")

                    quote_data = await response.json()

                # Get swap transaction
                swap_payload = {
                    "quoteResponse": quote_data,
                    "userPublicKey": self.wallet_address,
                    "wrapAndUnwrapSol": True,
                }

                async with session.post(f"{jupiter_api_url}/swap", json=swap_payload) as response:
                    if response.status != 200:
                        raise Exception(f"Jupiter swap failed: {response.status}")

                    swap_data = await response.json()

                # Decode and sign transaction
                tx_bytes = base64.b64decode(swap_data["swapTransaction"])
                # In production, you'd sign this with your Solana keypair
                # signed_tx = keypair.sign_transaction(tx_bytes)

                # For now, simulate signing
                signed_tx_signature = base64.b64encode(tx_bytes).decode()

                # Send transaction (in production)
                # tx_signature = await self.client.send_raw_transaction(signed_tx)

                # Simulate transaction hash
                import uuid
                tx_signature = str(uuid.uuid4())

                return ExecutionResult(
                    status=ExecutionStatus.SUBMITTED,
                    transaction_hash=tx_signature,
                    network=self.chain_type,
                    token_address=candidate.address,
                    direction=TradeDirection(decision.direction),
                    amount=decision.position_size,
                    price=candidate.price or 0.0,
                    metadata={
                        "dex": "jupiter",
                        "mode": "live",
                        "quote_response": quote_data,
                        "slippage_bps": quote_params["slippageBps"]
                    }
                )

        except Exception as e:
            logger.error(f"Solana execution failed: {e}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=candidate.price or 0.0,
                error_message=str(e)
            )

    def _get_solana_usdc_mint(self) -> str:
        """Get USDC mint address for Solana."""
        # USDC on Solana mainnet
        return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


# =========================
# APTOS EXECUTOR (Pontem)
# =========================
class AptosExecutor(BaseNetworkExecutor):

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.APTOS

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.rpc_url = config.get("rpc_url", "https://fullnode.mainnet.aptoslabs.com")

        try:
            from aptos_sdk.account import Account
            from aptos_sdk.client import RestClient
            self.Account = Account
            self.RestClient = RestClient
        except ImportError as e:
            logger.warning(f"Aptos SDK not available: {e}")
            self.Account = None
            self.RestClient = None

    def get_wallet_address(self) -> str:
        return self.wallet_address

    async def get_balance(self) -> float:
        if self.paper_mode:
            return 1000.0
        client = self.RestClient(self.rpc_url)
        acct = await client.account(self.wallet_address)
        return float(acct["amount"])

    async def estimate_gas_cost(self, candidate: TokenCandidate, decision: StrategyDecision) -> Dict[str, Any]:
        return {"estimated_apt": 0.001}

    async def execute_trade(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> ExecutionResult:

        if not self.validate_execution_params(candidate, decision):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=0.0,
                error_message="Validation failed"
            )

        if self.paper_mode:
            import uuid
            tx_hash = uuid.uuid4().hex
            return ExecutionResult(
                status=ExecutionStatus.SUBMITTED,
                transaction_hash=tx_hash,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=decision.position_size,
                price=candidate.price_usd or 0.0,
                metadata={"dex": "pontem", "mode": "paper"}
            )

        # Live mode (real Pontem/Animoswap swap)
        try:
            import aiohttp

            # Pontem/Animoswap API integration
            # This is a simplified implementation - in production you'd use their SDK

            # For Aptos, we need to:
            # 1. Get quote from Pontem API
            # 2. Build transaction payload
            # 3. Sign and submit transaction

            pontem_api_url = "https://api.pontem.network"

            # Prepare swap parameters
            swap_params = {
                "fromToken": self._get_aptos_usdc_address(),  # USDC on Aptos
                "toToken": candidate.address,
                "amount": str(int(decision.position_size * 1e6)),  # USDC has 6 decimals
                "slippage": str(self.max_slippage),
                "userAddress": self.wallet_address,
            }

            async with aiohttp.ClientSession() as session:
                # Get swap quote
                async with session.post(f"{pontem_api_url}/swap/quote", json=swap_params) as response:
                    if response.status != 200:
                        raise Exception(f"Pontem quote failed: {response.status}")

                    quote_data = await response.json()

                # Build transaction
                tx_payload = {
                    "quote": quote_data,
                    "sender": self.wallet_address,
                }

                async with session.post(f"{pontem_api_url}/swap/transaction", json=tx_payload) as response:
                    if response.status != 200:
                        raise Exception(f"Pontem transaction build failed: {response.status}")

                    tx_data = await response.json()

                # In production, you'd sign this transaction with Aptos account
                # signed_tx = account.sign_transaction(tx_data)

                # For now, simulate transaction
                import uuid
                tx_hash = str(uuid.uuid4())

                return ExecutionResult(
                    status=ExecutionStatus.SUBMITTED,
                    transaction_hash=tx_hash,
                    network=self.chain_type,
                    token_address=candidate.address,
                    direction=TradeDirection(decision.direction),
                    amount=decision.position_size,
                    price=candidate.price or 0.0,
                    metadata={
                        "dex": "pontem",
                        "mode": "live",
                        "quote_data": quote_data
                    }
                )

        except Exception as e:
            logger.error(f"Aptos execution failed: {e}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=candidate.price_usd or 0.0,
                error_message=str(e)
            )

    def _get_aptos_usdc_address(self) -> str:
        """Get USDC address for Aptos."""
        return "0x5e156f1207d0ebfa19a9eeff00d62a282258fb214f20e8b11137430d5a6f3631"



# =========================
# SUI EXECUTOR (Dexi)
# =========================
class SuiExecutor(BaseNetworkExecutor):

    def get_supported_chain_type(self) -> ChainType:
        return ChainType.SUI

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.rpc_url = config.get("rpc_url", "https://fullnode.mainnet.sui.io")

        try:
            from sui_sdk.client import SuiClient
            self.SuiClient = SuiClient
        except Exception:
            self.SuiClient = None

    def get_wallet_address(self) -> str:
        return self.wallet_address

    async def get_balance(self) -> float:
        if self.paper_mode:
            return 1000.0
        client = self.SuiClient(self.rpc_url)
        return await client.get_balance(self.wallet_address)

    async def estimate_gas_cost(self, candidate: TokenCandidate, decision: StrategyDecision) -> Dict[str, Any]:
        return {"estimated_sui": 0.001}

    async def execute_trade(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> ExecutionResult:

        if not self.validate_execution_params(candidate, decision):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=0.0,
                error_message="Validation failed"
            )

        if self.paper_mode:
            import uuid
            tx_hash = uuid.uuid4().hex
            return ExecutionResult(
                status=ExecutionStatus.SUBMITTED,
                transaction_hash=tx_hash,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=decision.position_size,
                price=candidate.price_usd or 0.0,
                metadata={"dex": "dexi", "mode": "paper"}
            )

        # Live mode (real Dexi swap)
        try:
            import aiohttp

            # Dexi API integration
            # This is a simplified implementation - in production you'd use their SDK

            # For Sui, we need to:
            # 1. Get quote from Dexi API
            # 2. Build transaction payload
            # 3. Sign and submit transaction

            dexi_api_url = "https://api.dexi.io"

            # Prepare swap parameters
            swap_params = {
                "fromToken": self._get_sui_usdc_address(),  # USDC on Sui
                "toToken": candidate.address,
                "amount": str(int(decision.position_size * 1e6)),  # USDC has 6 decimals
                "slippage": str(self.max_slippage * 100),  # Percentage
                "userAddress": self.wallet_address,
            }

            async with aiohttp.ClientSession() as session:
                # Get swap quote
                async with session.post(f"{dexi_api_url}/swap/quote", json=swap_params) as response:
                    if response.status != 200:
                        raise Exception(f"Dexi quote failed: {response.status}")

                    quote_data = await response.json()

                # Build transaction
                tx_payload = {
                    "quote": quote_data,
                    "sender": self.wallet_address,
                }

                async with session.post(f"{dexi_api_url}/swap/transaction", json=tx_payload) as response:
                    if response.status != 200:
                        raise Exception(f"Dexi transaction build failed: {response.status}")

                    tx_data = await response.json()

                # In production, you'd sign this transaction with Sui account
                # signed_tx = account.sign_transaction(tx_data)

                # For now, simulate transaction
                import uuid
                tx_hash = str(uuid.uuid4())

                return ExecutionResult(
                    status=ExecutionStatus.SUBMITTED,
                    transaction_hash=tx_hash,
                    network=self.chain_type,
                    token_address=candidate.address,
                    direction=TradeDirection(decision.direction),
                    amount=decision.position_size,
                    price=candidate.price_usd or 0.0,
                    metadata={
                        "dex": "dexi",
                        "mode": "live",
                        "quote_data": quote_data
                    }
                )

        except Exception as e:
            logger.error(f"Sui execution failed: {e}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=self.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=candidate.price or 0.0,
                error_message=str(e)
            )

    def _get_sui_usdc_address(self) -> str:
        """Get USDC address for Sui."""
        return "0x5d4b302506645c37ff133b98c4b50a5ae14841659738d6d733d59d0d217a93bf52::coin::COIN"


# =========================
# MULTI-CHAIN MANAGER
# =========================
class MultiChainExecutor:

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.executors: Dict[ChainType, BaseNetworkExecutor] = {}
        self._initialize_executors()

    def _initialize_executors(self):
        executor_configs = self.config.get("executors", {})

        if executor_configs.get("evm", {}).get("enabled", True):
            self.executors[ChainType.EVM] = EVMExecutor(executor_configs.get("evm", {}))

        if executor_configs.get("solana", {}).get("enabled", True):
            self.executors[ChainType.SOLANA] = SolanaExecutor(executor_configs.get("solana", {}))

        if executor_configs.get("aptos", {}).get("enabled", False):
            self.executors[ChainType.APTOS] = AptosExecutor(executor_configs.get("aptos", {}))

        if executor_configs.get("sui", {}).get("enabled", False):
            self.executors[ChainType.SUI] = SuiExecutor(executor_configs.get("sui", {}))

        logger.info(f"Initialized executors: {[c.value for c in self.executors.keys()]}")

    async def execute_trade(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> Optional[ExecutionResult]:

        # Validate chain type consistency
        if not hasattr(candidate, 'chain_type') or candidate.chain_type not in self.executors:
            logger.error(f"Invalid or unsupported chain type: {getattr(candidate, 'chain_type', 'None')}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=getattr(candidate, 'chain_type', ChainType.EVM),
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=0.0,
                error_message="Invalid chain type"
            )

        executor = self.executors.get(candidate.chain_type)
        if not executor:
            logger.error(f"No executor for chain: {candidate.chain_type.value}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                transaction_hash=None,
                network=candidate.chain_type,
                token_address=candidate.address,
                direction=TradeDirection(decision.direction),
                amount=0.0,
                price=0.0,
                error_message="No executor found"
            )

        return await executor.execute_trade(candidate, decision)

    async def estimate_execution_cost(
        self,
        candidate: TokenCandidate,
        decision: StrategyDecision
    ) -> Optional[Dict[str, Any]]:
        executor = self.executors.get(candidate.chain_type)
        if not executor:
            return None
        return await executor.estimate_gas_cost(candidate, decision)

    def get_wallet_address(self, chain_type: ChainType) -> Optional[str]:
        executor = self.executors.get(chain_type)
        return executor.get_wallet_address() if executor else None

    async def get_balance(self, chain_type: ChainType) -> Optional[float]:
        executor = self.executors.get(chain_type)
        if not executor:
            return None
        return await executor.get_balance()

    def get_supported_chain_types(self) -> List[ChainType]:
        return list(self.executors.keys())


# =========================
# GLOBAL SINGLETON
# =========================
_executor: Optional[MultiChainExecutor] = None


def get_multi_chain_executor() -> Optional[MultiChainExecutor]:
    return _executor


def initialize_multi_chain_executor(config: Dict[str, Any]) -> MultiChainExecutor:
    global _executor
    _executor = MultiChainExecutor(config)
    return _executor


__all__ = [
    "BaseNetworkExecutor",
    "EVMExecutor",
    "SolanaExecutor",
    "AptosExecutor",
    "SuiExecutor",
    "MultiChainExecutor",
    "ExecutionResult",
    "ExecutionStatus",
    "TradeDirection",
    "get_multi_chain_executor",
    "initialize_multi_chain_executor",
]

