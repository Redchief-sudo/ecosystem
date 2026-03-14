import pytest
import asyncio
from trading.execution.trade_executor import HybridTradeExecutor

from networks import NetworkManager
from router.hybrid_router_manager import HybridRouterManager


@pytest.mark.asyncio
async def test_paper_mode_real_components():
    config = {
        "trading": {
            "mode": "paper",
            "paper_trading": True
        },
        "networks": {
            "ethereum": {
                "rpc_url": "https://mainnet.infura.io/v3/YOUR_INFURA_KEY",
                "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "routers": {
                    "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
                }
            }
        }
    }

    network_manager = NetworkManager(config["networks"])
    router_manager = HybridRouterManager(config=config, network_manager=network_manager)

    executor = HybridTradeExecutor(
        config=config,
        network_manager=network_manager,
        hybrid_router_manager=router_manager
    )

    await executor.initialize()

    result = await executor.execute_trade(
        token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # USDC token (example)
        amount=1.0,
        chain="ethereum",
        side="buy"
    )

    assert result.success is True
    assert result.transaction_hash is not None

