import asyncio
import logging

log = logging.getLogger("ProfitEngine")

class ProfitEngine:
    """
    Legendary Ecosystem Profit Engine (Final Form)
    - No longer requires wallet, network_manager, router_manager in constructor
    - TradeExecutor supplies these during update calls
    """

    def __init__(self):
        self.balances = {}   # {chain: native_balance}
        self.total_portfolio_value = 0.0

    async def update_balances(self, executor):
        """
        Executor provides:
        - executor.network_manager
        - executor.wallet_address
        """
        nm = executor.network_manager
        wallet = executor.wallet_address

        total = 0.0

        for chain, client in nm.clients.items():
            try:
                if client is None:
                    log.error(f"[ProfitEngine] {chain} Web3 client is None")
                    continue

                bal = client.eth.get_balance(wallet)
                native = bal / 1e18

                self.balances[chain] = native
                total += native

            except Exception as e:
                log.error(f"[ProfitEngine] Failed to get native balance for {chain}: {e}")

        self.total_portfolio_value = total
        return total

