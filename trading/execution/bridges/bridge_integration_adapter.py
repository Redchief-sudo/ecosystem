#!/usr/bin/env python3
"""
Bridge Integration Adapter
==========================

Integrates the Elite Bridge Manager with the existing trading system.
Provides seamless cross-chain arbitrage execution capabilities.

Author: Elite Trading Systems
Version: 1.0.0
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from networks.cross_chain_mapper import CrossChainAddressMapper
from networks.multi_chain_manager import MultiChainManager
from typing import Union
from trading.bridges.elite_bridge_manager import (BridgeStatus,
                                                  BridgeTransaction,
                                                  EliteBridgeManager,
                                                  RouteQuote)
from trading.execution.trade_executor import TradeExecutor
from trading.models import TokenInfo, TradeOpportunity

logger = logging.getLogger(__name__)


@dataclass
class CrossChainArbitrageOpportunity:
    """Cross-chain arbitrage opportunity."""
    opportunity_id: str
    
    # Token information
    token_symbol: str
    token_address: str
    
    # Chain information
    source_chain: str
    dest_chain: str
    
    # Price information
    source_price: Decimal
    dest_price: Decimal
    price_difference_pct: Decimal
    
    # Bridge information
    bridge_quote: Optional[RouteQuote] = None
    estimated_bridge_cost: Decimal = Decimal('0')
    
    # Profit calculations
    estimated_profit: Decimal = Decimal('0')
    profit_after_bridging: Decimal = Decimal('0')
    
    # Risk metrics
    confidence_score: float = 0.0
    liquidity_score: float = 0.0
    
    # Timing
    discovered_at: datetime = None
    expires_at: datetime = None
    
    def __post_init__(self):
        if self.discovered_at is None:
            self.discovered_at = datetime.now(timezone.utc)
        if self.expires_at is None:
            self.expires_at = self.discovered_at + timedelta(minutes=10)


class BridgeIntegrationAdapter:
    """
    Adapter that integrates bridge functionality with the trading system.
    """
    
    def __init__(self, bridge_manager: EliteBridgeManager, 
                 multi_chain_manager: Union[Any, 'UniversalNetworkManager', 'MultiChainManager'],  # Support all manager types
                 trade_executor: TradeExecutor):
        """Initialize the bridge integration adapter."""
        self.bridge_manager = bridge_manager
        self.multi_chain_manager = multi_chain_manager
        self.trade_executor = trade_executor
        self.address_mapper = CrossChainAddressMapper()
        
        # Configuration
        self.min_profit_threshold = Decimal('50')  # $50 minimum profit
        self.max_bridge_time_minutes = 30
        self.max_slippage_pct = Decimal('2.0')
        
        # Active arbitrage tracking
        self.active_arbitrages: Dict[str, CrossChainArbitrageOpportunity] = {}
        self.bridge_transactions: Dict[str, BridgeTransaction] = {}
        
        logger.info("🔗 Bridge Integration Adapter initialized")
    
    async def detect_cross_chain_arbitrage(self, token_symbol: str) -> List[CrossChainArbitrageOpportunity]:
        """
        Detect cross-chain arbitrage opportunities for a token.
        
        Args:
            token_symbol: Token symbol to analyze
            
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        # Get token prices across all chains
        chain_prices = await self._get_token_prices_across_chains(token_symbol)
        
        if len(chain_prices) < 2:
            logger.debug(f"Insufficient price data for {token_symbol}")
            return opportunities
        
        # Find arbitrage pairs
        chains = list(chain_prices.keys())
        for i, source_chain in enumerate(chains):
            for dest_chain in chains[i+1:]:
                source_price = chain_prices[source_chain]
                dest_price = chain_prices[dest_chain]
                
                # Calculate price difference
                price_diff_pct = abs(dest_price - source_price) / source_price * Decimal('100')
                
                if price_diff_pct > Decimal('1.0'):  # Minimum 1% price difference
                    opportunity = await self._create_arbitrage_opportunity(
                        token_symbol, source_chain, dest_chain,
                        source_price, dest_price, price_diff_pct
                    )
                    
                    if opportunity and opportunity.estimated_profit > self.min_profit_threshold:
                        opportunities.append(opportunity)
        
        logger.info(f"🔍 Found {len(opportunities)} arbitrage opportunities for {token_symbol}")
        return opportunities
    
    async def _get_token_prices_across_chains(self, token_symbol: str) -> Dict[str, Decimal]:
        """Get token prices across all supported chains."""
        prices = {}
        
        # Get supported chains from bridge manager
        for chain_id, chain in self.bridge_manager.chains.items():
            try:
                # Get Web3 connection
                # Support MultiChainManager and UniversalNetworkManager
                web3 = None
                
                if hasattr(self.multi_chain_manager, 'get_web3'):
                    web3 = self.multi_chain_manager.get_web3(chain_id)
                elif hasattr(self.multi_chain_manager, 'get_w3'):
                    web3 = self.multi_chain_manager.get_w3(chain_id)
                elif hasattr(self.multi_chain_manager, 'get_web3_client'):
                    # UniversalNetworkManager
                    web3 = self.multi_chain_manager.get_web3_client(chain_id)
                elif hasattr(self.multi_chain_manager, 'clients') and chain_id in self.multi_chain_manager.clients:
                    # Direct access to clients dict
                    client = self.multi_chain_manager.clients[chain_id]
                    if hasattr(client, 'client') and hasattr(client.client, 'eth'):
                        web3 = client.client
                    elif hasattr(client, 'eth'):
                        web3 = client
                
                if not web3:
                    logger.warning(f"Could not get Web3 client for chain {chain_id}")
                    continue
                
                # Get token address for this chain
                token_address = await self._get_token_address_on_chain(token_symbol, chain_id)
                if not token_address:
                    continue
                
                # Get current price (simplified - in production would use DEX price feeds)
                price = await self._get_token_price(web3, token_address, chain_id)
                if price > 0:
                    prices[chain_id] = price
                    
            except Exception as e:
                logger.warning(f"Failed to get price for {token_symbol} on {chain_id}: {e}")
        
        return prices
    
    async def _get_token_address_on_chain(self, token_symbol: str, chain_id: str) -> Optional[str]:
        """Get token contract address on a specific chain."""
        # Use the cross-chain mapper to get the address
        # First check if we have a mapping for this token
        if not self.address_mapper.is_supported_token(token_symbol):
            logger.debug(f"No cross-chain mapping available for {token_symbol}")
            return None

        # Get the mapping for this token
        mapping = self.address_mapper.mappings.get(token_symbol.upper())
        if not mapping:
            return None

        # Get the address for this chain
        return mapping.get_address_for_chain(chain_id)
    
    async def _get_token_price(self, web3, token_address: str, chain_id: str) -> Decimal:
        """Get token price from DEX (simplified implementation)."""
        # In production, this would query DEX contracts for current price
        # For now, return a simulated price based on chain
        
        base_prices = {
            # EVM Networks - ETH priced chains
            'ethereum': Decimal('3000'),  # ETH price
            'arbitrum': Decimal('3000'),
            'optimism': Decimal('3000'),
            'base': Decimal('3000'),
            'scroll': Decimal('3000'),
            'zksync': Decimal('3000'),
            'zksync_era': Decimal('3000'),
            'linea': Decimal('3000'),
            'mantle': Decimal('3000'),
            'blast': Decimal('3000'),
            'mode': Decimal('3000'),
            'boba': Decimal('3000'),
            'aurora': Decimal('3000'),
            'near_aurora': Decimal('3000'),
            'metis': Decimal('3000'),
            'godwoken': Decimal('3000'),
            
            # BNB priced chains
            'bsc': Decimal('300'),       # BNB price
            'bnb_smart_chain': Decimal('300'),
            
            # MATIC priced chains
            'polygon': Decimal('0.9'),   # MATIC price
            'polygon_zkevm': Decimal('0.9'),
            
            # AVAX priced chains
            'avalanche': Decimal('35'),   # AVAX price
            
            # Other EVM chains
            'fantom': Decimal('0.8'),    # FTM price
            'cronos': Decimal('0.15'),    # CRO price
            'gnosis': Decimal('0.6'),     # XDAI price
            'moonriver': Decimal('2.5'),  # MOVR price
            'moonbeam': Decimal('0.7'),   # GLMR price
            'celo': Decimal('0.8'),       # CELO price
            'kava': Decimal('1.2'),       # KAVA price
            'canto': Decimal('0.3'),      # CANTO price
            'telos': Decimal('0.2'),      # TLOS price
            'step': Decimal('0.1'),       # STEP price
            'rangers': Decimal('0.05'),   # RPG price
            'astar': Decimal('0.15'),     # ASTR price
            'songbird': Decimal('0.02'),   # SGB price
            'evmos': Decimal('0.08'),     # EVMOS price
            'okc': Decimal('0.4'),        # OKT price
            'harmony': Decimal('0.03'),   # ONE price
            'acala': Decimal('0.25'),     # ACA price
            'hedera': Decimal('0.07'),    # HBAR price
            
            # Non-EVM Networks
            'solana': Decimal('150'),     # SOL price
            'tron': Decimal('0.12'),      # TRX price
            'osmosis': Decimal('0.5'),     # OSMO price
            'xrpl': Decimal('0.6'),       # XRP price
            'aptos': Decimal('8'),        # APT price
            'sui': Decimal('2'),          # SUI price
            'ton': Decimal('5'),          # TON price
            'cardano': Decimal('0.4'),    # ADA price
            'stacks': Decimal('1.5'),     # STX price
            'algorand': Decimal('0.2'),   # ALGO price
            'tezos': Decimal('1.2'),      # XTZ price
            'stellar': Decimal('0.15'),   # XLM price
            'thorchain': Decimal('3'),     # RUNE price
        }
        
        base_price = base_prices.get(chain_id, Decimal('1'))
        
        # Add some variance
        variance = Decimal(str(random.uniform(0.95, 1.05)))
        
        return base_price * variance
    
    async def _create_arbitrage_opportunity(self, token_symbol: str,
                                          source_chain: str, dest_chain: str,
                                          source_price: Decimal, dest_price: Decimal,
                                          price_diff_pct: Decimal) -> Optional[CrossChainArbitrageOpportunity]:
        """Create an arbitrage opportunity object."""
        
        # Determine direction (buy low, sell high)
        if source_price < dest_price:
            # Buy on source, sell on dest
            buy_chain, sell_chain = source_chain, dest_chain
            buy_price, sell_price = source_price, dest_price
        else:
            # Buy on dest, sell on source
            buy_chain, sell_chain = dest_chain, source_chain
            buy_price, sell_price = dest_price, source_price
        
        # Get bridge quote
        bridge_quotes = await self.bridge_manager.quote_bridge(
            buy_chain, sell_chain, token_symbol, Decimal('10000')  # Default amount
        )
        
        if not bridge_quotes:
            logger.debug(f"No bridge route available for {token_symbol} {buy_chain} -> {sell_chain}")
            return None
        
        best_quote = bridge_quotes[0]  # Already sorted by score
        
        # Calculate profits (simplified)
        trade_amount = Decimal('10000')  # $10k default
        bridge_cost = best_quote.estimated_cost
        
        # Estimated profit before bridge costs
        gross_profit = (sell_price - buy_price) * trade_amount / buy_price
        
        # Net profit after bridge costs
        net_profit = gross_profit - bridge_cost
        
        if net_profit < self.min_profit_threshold:
            return None
        
        # Create opportunity
        opportunity = CrossChainArbitrageOpportunity(
            opportunity_id=f"arb_{token_symbol}_{buy_chain}_{sell_chain}_{int(datetime.now().timestamp())}",
            token_symbol=token_symbol,
            token_address="",  # Would be populated with actual address
            source_chain=buy_chain,
            dest_chain=sell_chain,
            source_price=buy_price,
            dest_price=sell_price,
            price_difference_pct=price_diff_pct,
            bridge_quote=best_quote,
            estimated_bridge_cost=bridge_cost,
            estimated_profit=gross_profit,
            profit_after_bridging=net_profit,
            confidence_score=best_quote.success_probability,
            liquidity_score=min(1.0, float(best_quote.available_liquidity / trade_amount))
        )
        
        return opportunity
    
    async def execute_cross_chain_arbitrage(self, opportunity: CrossChainArbitrageOpportunity,
                                          trade_size: Decimal) -> Optional[BridgeTransaction]:
        """
        Execute a cross-chain arbitrage opportunity.
        
        Args:
            opportunity: The arbitrage opportunity to execute
            trade_size: Size of the trade in USD
            
        Returns:
            Bridge transaction if successful
        """
        logger.info(f"🚀 Executing arbitrage: {opportunity.token_symbol} "
                   f"{opportunity.source_chain} -> {opportunity.dest_chain}")
        
        try:
            # Step 1: Execute buy trade on source chain
            buy_success = await self._execute_buy_trade(opportunity, trade_size)
            if not buy_success:
                logger.error(f"Buy trade failed for {opportunity.opportunity_id}")
                return None
            
            # Step 2: Bridge tokens to destination chain
            bridge_tx = await self._execute_bridge_transfer(opportunity, trade_size)
            if not bridge_tx:
                logger.error(f"Bridge transfer failed for {opportunity.opportunity_id}")
                return None
            
            # Step 3: Execute sell trade on destination chain
            sell_success = await self._execute_sell_trade(opportunity, bridge_tx)
            if not sell_success:
                logger.error(f"Sell trade failed for {opportunity.opportunity_id}")
                return None
            
            # Track the arbitrage
            self.active_arbitrages[opportunity.opportunity_id] = opportunity
            self.bridge_transactions[bridge_tx.tx_id] = bridge_tx
            
            logger.info(f"✅ Arbitrage executed: {opportunity.opportunity_id}")
            return bridge_tx
            
        except Exception as e:
            logger.error(f"Arbitrage execution failed: {e}")
            return None
    
    async def _execute_buy_trade(self, opportunity: CrossChainArbitrageOpportunity,
                               trade_size: Decimal) -> bool:
        """Execute buy trade on source chain."""
        # This would integrate with the existing trade executor
        # For now, simulate success
        
        logger.debug(f"Executing buy trade on {opportunity.source_chain}")
        
        # Simulate trade execution time
        await asyncio.sleep(2)
        
        return True
    
    async def _execute_bridge_transfer(self, opportunity: CrossChainArbitrageOpportunity,
                                     trade_size: Decimal) -> Optional[BridgeTransaction]:
        """Execute bridge transfer."""
        if not opportunity.bridge_quote:
            return None
        
        # Get addresses
        sender_address = "0x1234567890123456789012345678901234567890"  # Would be actual wallet
        recipient_address = "0x0987654321098765432109876543210987654321"
        
        # Execute bridge
        bridge_tx = await self.bridge_manager.execute_bridge(
            quote=opportunity.bridge_quote,
            sender=sender_address,
            recipient=recipient_address,
            token_address="",  # Would be actual token address
            token_symbol=opportunity.token_symbol,
            amount=trade_size
        )
        
        return bridge_tx
    
    async def _execute_sell_trade(self, opportunity: CrossChainArbitrageOpportunity,
                                bridge_tx: BridgeTransaction) -> bool:
        """Execute sell trade on destination chain."""
        # Wait for bridge to complete
        while bridge_tx.status not in [BridgeStatus.COMPLETED, BridgeStatus.FAILED]:
            await asyncio.sleep(5)
            
            # Check if bridge failed
            if bridge_tx.status == BridgeStatus.FAILED:
                return False
        
        # Execute sell trade
        logger.debug(f"Executing sell trade on {opportunity.dest_chain}")
        
        # Simulate trade execution time
        await asyncio.sleep(2)
        
        return True
    
    async def monitor_active_arbitrages(self):
        """Monitor active arbitrage positions."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Check bridge transactions
                completed_arbitrages = []
                
                for arb_id, opportunity in self.active_arbitrages.items():
                    # Check if bridge transaction completed
                    bridge_tx = None
                    for tx_id, tx in self.bridge_transactions.items():
                        if tx.status == BridgeStatus.COMPLETED:
                            bridge_tx = tx
                            break
                    
                    if bridge_tx:
                        # Calculate actual profit
                        actual_profit = await self._calculate_actual_profit(opportunity, bridge_tx)
                        
                        logger.info(f"💰 Arbitrage completed: {arb_id} - Profit: ${actual_profit}")
                        completed_arbitrages.append(arb_id)
                
                # Remove completed arbitrages
                for arb_id in completed_arbitrages:
                    del self.active_arbitrages[arb_id]
                
            except Exception as e:
                logger.error(f"Error monitoring arbitrages: {e}")
    
    async def _calculate_actual_profit(self, opportunity: CrossChainArbitrageOpportunity,
                                     bridge_tx: BridgeTransaction) -> Decimal:
        """Calculate actual profit from completed arbitrage."""
        # Simplified profit calculation
        # In production, would track actual trade results
        
        if bridge_tx.received_amount:
            # Account for slippage
            slippage_loss = bridge_tx.slippage_percentage or Decimal('0')
            actual_profit = opportunity.estimated_profit - (opportunity.estimated_profit * slippage_loss / Decimal('100'))
        else:
            actual_profit = Decimal('0')
        
        return actual_profit
    
    async def get_arbitrage_statistics(self) -> Dict[str, Any]:
        """Get arbitrage execution statistics."""
        total_arbitrages = len(self.active_arbitrages) + len(self.bridge_transactions)
        active_count = len(self.active_arbitrages)
        
        # Get bridge manager stats
        bridge_health = await self.bridge_manager.get_route_health()
        
        return {
            'total_arbitrages_executed': total_arbitrages,
            'active_arbitrages': active_count,
            'bridge_routes_healthy': sum(1 for r in bridge_health.values() if r['is_healthy']),
            'total_bridge_routes': len(bridge_health),
            'average_bridge_time': sum(r['route_info']['estimated_time_minutes'] for r in bridge_health.values()) / len(bridge_health) if bridge_health else 0
        }


# Integration helper functions
async def initialize_bridge_integration(config: Dict, multi_chain_manager: Union[MultiChainManager, Any],
                                      trade_executor: TradeExecutor) -> BridgeIntegrationAdapter:
    """Initialize bridge integration with existing system."""
    # Initialize bridge manager
    bridge_manager = EliteBridgeManager(config)
    await bridge_manager.initialize()
    
    # Create adapter
    adapter = BridgeIntegrationAdapter(
        bridge_manager=bridge_manager,
        multi_chain_manager=multi_chain_manager,
        trade_executor=trade_executor
    )
    
    # Start monitoring
    asyncio.create_task(adapter.monitor_active_arbitrages())
    
    logger.info("🔗 Bridge integration initialized")
    return adapter
