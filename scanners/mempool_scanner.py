"""
Mempool Scanner Ultra - Institutional Grade
-------------------------------------------
Advanced mempool intelligence with:
- Multi-dimensional MEV detection (sandwich, front-run, back-run, JIT)
- Gas price prediction using time-series models
- Whale transaction clustering and intent prediction
- Cross-pool arbitrage opportunity detection
- Toxic flow identification (informed trading)
- Transaction graph analysis for coordinated activity
- Priority fee optimization
- Slippage impact estimation
"""

import asyncio
import logging
import time
import statistics
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable, Awaitable, Deque
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from web3 import Web3
from web3.types import TxReceipt, TxData
from .base_scanner import ScannerBase
from eth_typing import ChecksumAddress, HexStr
import hashlib

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS & CONSTANTS
# ============================================================

class MEVStrategy(Enum):
    """MEV strategy types"""
    SANDWICH = "sandwich"           # Sandwich attack
    FRONTRUN = "frontrun"           # Simple front-running
    BACKRUN = "backrun"             # Back-running (arbitrage after)
    JIT_LIQUIDITY = "jit_liquidity" # Just-in-time liquidity
    LIQUIDATION = "liquidation"     # Liquidation sniping
    NFT_SNIPE = "nft_snipe"        # NFT mint sniping
    ATOMIC_ARB = "atomic_arb"       # Atomic arbitrage


class TxIntent(Enum):
    """Transaction intent classification"""
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    TOKEN_CREATION = "token_creation"
    APPROVAL = "approval"
    TRANSFER = "transfer"
    CONTRACT_INTERACTION = "contract_interaction"
    UNKNOWN = "unknown"


class FlowToxicity(Enum):
    """Order flow toxicity levels"""
    BENIGN = "benign"           # Uninformed retail
    NEUTRAL = "neutral"         # Average
    INFORMED = "informed"       # Smart money
    TOXIC = "toxic"             # Very informed (MEV, whales)
    HIGHLY_TOXIC = "highly_toxic"  # Institutional/insider


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class GasIntelligence:
    """Gas price analysis and prediction"""
    current_base_fee: float = 0.0
    current_priority_fee: float = 0.0
    predicted_next_base: float = 0.0
    optimal_priority_fee: float = 0.0
    volatility: float = 0.0
    percentile_50: float = 0.0
    percentile_75: float = 0.0
    percentile_90: float = 0.0
    gas_spike_probability: float = 0.0
    history: Deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class MEVOpportunity:
    """Detected MEV opportunity"""
    strategy: MEVStrategy
    target_tx_hash: str
    expected_profit_eth: float
    confidence: float
    gas_cost_eth: float
    net_profit_eth: float
    optimal_gas_price: float
    execution_deadline: int  # Block number
    risk_score: float
    frontrun_tx: Optional[Dict] = None
    backrun_tx: Optional[Dict] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionIntelligence:
    """Deep transaction analysis"""
    tx_hash: str
    from_address: str
    to_address: Optional[str]
    value_eth: float
    gas_price: float
    gas_limit: int
    nonce: int
    input_data: str
    
    # Classification
    intent: TxIntent = TxIntent.UNKNOWN
    toxicity: FlowToxicity = FlowToxicity.NEUTRAL
    
    # Wallet analysis
    sender_tier: str = "unknown"  # whale, institutional, retail
    sender_reputation: float = 0.0
    sender_pnl_30d: float = 0.0
    is_mev_bot: bool = False
    is_smart_money: bool = False
    
    # Impact analysis
    estimated_slippage: float = 0.0
    price_impact: float = 0.0
    affected_tokens: List[str] = field(default_factory=list)
    affected_pools: List[str] = field(default_factory=list)
    
    # MEV detection
    mev_opportunities: List[MEVOpportunity] = field(default_factory=list)
    is_mev_attack: bool = False
    mev_bundle_id: Optional[str] = None
    
    # Timing
    first_seen: float = 0.0
    block_target: int = 0
    time_in_mempool: float = 0.0
    
    # Metadata
    tags: List[str] = field(default_factory=list)


@dataclass
class WhaleActivity:
    """Whale wallet activity tracking"""
    address: str
    total_value_usd: float
    recent_txs: Deque = field(default_factory=lambda: deque(maxlen=50))
    win_rate: float = 0.0
    avg_profit_pct: float = 0.0
    favorite_tokens: List[str] = field(default_factory=list)
    trading_pattern: str = "unknown"  # accumulator, trader, holder
    correlation_cluster: int = 0
    reputation_score: float = 0.0


@dataclass
class ArbitrageOpportunity:
    """Cross-pool arbitrage detection"""
    token_address: str
    buy_pool: str
    sell_pool: str
    buy_price: float
    sell_price: float
    spread_pct: float
    estimated_profit_eth: float
    required_capital_eth: float
    gas_cost_eth: float
    net_profit_eth: float
    execution_path: List[str]
    confidence: float
    expires_at: int  # Block number


@dataclass
class MempoolSnapshot:
    """Real-time mempool state"""
    timestamp: float
    block_number: int
    pending_tx_count: int
    total_value_eth: float
    avg_gas_price: float
    median_gas_price: float
    gas_intelligence: GasIntelligence
    whale_txs: List[TransactionIntelligence]
    mev_opportunities: List[MEVOpportunity]
    arbitrage_opportunities: List[ArbitrageOpportunity]
    toxic_flow_score: float


# ============================================================
# ELITE MEMPOOL SCANNER
# ============================================================

class MempoolScannerUltra(ScannerBase):
    """
    Institutional-grade mempool scanner with advanced MEV and arbitrage detection
    """
    
    # Known MEV bot addresses (example - expand with real data)
    KNOWN_MEV_BOTS = {
        '0x0000000000007f150bd6f54c40a34d7c3d5e9f56',  # MEV bot example
    }
    
    # Known smart money wallets
    KNOWN_SMART_MONEY = set()
    
    # DEX router signatures
    DEX_ROUTER_SIGS = {
        '0x38ed1739': 'swapExactTokensForTokens',
        '0x8803dbee': 'swapTokensForExactTokens',
        '0x7ff36ab5': 'swapExactETHForTokens',
        '0x18cbafe5': 'swapExactTokensForETH',
        '0xfb3bdb41': 'swapETHForExactTokens',
        '0x5c11d795': 'swapExactTokensForTokensSupportingFeeOnTransferTokens',
    }
    
    # Configuration keys that must be explicitly provided
    REQUIRED_CONFIG_KEYS = [
        'min_whale_value', 'min_mev_profit', 'min_arb_profit', 'max_slippage'
    ]
    
    def __init__(
        self,
        config: Optional[Dict] = None,
        network_config: Optional[Dict] = None,
        network_manager = None,
        memory = None
    ):
        # Call parent constructor to initialize logger and other attributes
        super().__init__(config)
        self.memory = memory  # Store memory reference
        self.logger = logger  # Store logger reference
        
        self.config = config or {}
        self.network_config = network_config or {}
        
        # Web3 providers
        self.web3_providers: Dict[str, Web3] = {}
        
        # Mempool state
        self.pending_txs: Dict[str, TransactionIntelligence] = {}
        self.tx_graph: Dict[str, Set[str]] = defaultdict(set)  # Transaction relationships
        
        # Whale tracking
        self.whale_wallets: Dict[str, WhaleActivity] = {}
        self.scan_count = 0
        self.error_count = 0
        self.is_initialized = False
        
        # Gas intelligence
        self.gas_intelligence: Dict[str, GasIntelligence] = {}
        
        # MEV detection
        self.mev_opportunities: List[MEVOpportunity] = []
        self.detected_bundles: Dict[str, List[str]] = {}  # bundle_id -> tx_hashes
        
        # Arbitrage detection
        self.arbitrage_opportunities: List[ArbitrageOpportunity] = []
        
        # Performance tracking
        self.metrics: Dict[str, Any] = defaultdict(int)
        self.snapshots: Deque = deque(maxlen=1000)
        
        # Subscribers
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        
        self.running = False
        
        logger.info("Initialized Elite Mempool Scanner")
    
    # ========================================================
    # MAIN SCANNING LOGIC
    # ========================================================
    
    async def scan(self, *args, **kwargs) -> List[Dict]:
        """
        Scan method required by ScannerBase - delegates to _scan_network_impl.
        """
        # If chain is provided as first argument, use it
        if args and isinstance(args[0], str):
            return await self._scan_network_impl(args[0])
        # If chain is provided in kwargs
        elif 'chain' in kwargs:
            return await self._scan_network_impl(kwargs['chain'])
        # Default to ethereum
        else:
            return await self._scan_network_impl('ethereum')

    async def _scan_network_impl(self, chain: str) -> List[Dict]:
        """
        Implementation of abstract method from ScannerBase.
        Scan mempool for opportunities and return token data.
        """
        try:
            # Get current mempool snapshot
            snapshot = self.get_snapshot(chain)
            
            # Convert opportunities to token format expected by ScanDirector
            tokens = []
            
            # Add MEV opportunities as tokens
            for opp in snapshot.mev_opportunities:
                token_data = {
                    'symbol': opp.token_address[:8],  # Short address as symbol
                    'name': f'MEV Opportunity {opp.opportunity_type}',
                    'address': opp.token_address,
                    'price': opp.estimated_profit_eth,
                    'volume_24h': opp.required_capital_eth,
                    'liquidity': opp.required_capital_eth,
                    'confidence': opp.confidence,
                    'chain': chain,
                    'source': 'MempoolScannerUltra',
                    'type': 'mev_opportunity',
                    'opportunity_data': {
                        'type': opp.opportunity_type,
                        'profit_eth': opp.estimated_profit_eth,
                        'gas_cost_eth': opp.gas_cost_eth,
                        'expires_at': opp.expires_at
                    }
                }
                tokens.append(token_data)
            
            # Add arbitrage opportunities as tokens
            for opp in snapshot.arbitrage_opportunities:
                token_data = {
                    'symbol': f'ARB-{opp.token_a[:6]}-{opp.token_b[:6]}',
                    'name': f'Arbitrage {opp.token_a[:6]}/{opp.token_b[:6]}',
                    'address': opp.token_a,
                    'price': opp.sell_price,
                    'volume_24h': opp.required_capital_eth,
                    'liquidity': opp.required_capital_eth,
                    'confidence': opp.confidence,
                    'chain': chain,
                    'source': 'MempoolScannerUltra',
                    'type': 'arbitrage_opportunity',
                    'opportunity_data': {
                        'token_a': opp.token_a,
                        'token_b': opp.token_b,
                        'buy_price': opp.buy_price,
                        'sell_price': opp.sell_price,
                        'spread_pct': opp.spread_pct,
                        'profit_eth': opp.net_profit_eth
                    }
                }
                tokens.append(token_data)
            
            self.logger.info(f"Found {len(snapshot.mev_opportunities)} MEV and {len(snapshot.arbitrage_opportunities)} arbitrage opportunities on {chain}")
            return tokens
            
        except Exception as e:
            self.logger.error(f"Error scanning mempool for {chain}: {e}", exc_info=True)
            return []
    
    async def start(self, chains: Optional[List[str]] = None):
        """Start mempool monitoring"""
        if self.running:
            return
        
        self.running = True
        chains = chains or list(self.network_config.keys())
        
        logger.info(f"🚀 Starting elite mempool scanner on {len(chains)} chains")
        
        # Start monitoring tasks for each chain
        from utils.task_manager import task_manager
        for chain in chains:
            task = await task_manager.create_scanner_task(lambda ch=chain: self._monitor_mempool(ch), f"mempool.monitor.{chain}")
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

            task = await task_manager.create_scanner_task(lambda ch=chain: self._analyze_gas(ch), f"mempool.analyze.{chain}")
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

            task = await task_manager.create_scanner_task(lambda ch=chain: self._detect_mev(ch), f"mempool.mev.{chain}")
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

            task = await task_manager.create_scanner_task(lambda ch=chain: self._detect_arbitrage(ch), f"mempool.arb.{chain}")
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        
        # Start cleanup task
        cleanup_task = await task_manager.create_scanner_task(self._cleanup_loop, "mempool.cleanup")
        self._background_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(self._background_tasks.discard)
    
    async def stop(self):
        """Stop mempool monitoring"""
        self.running = False
        logger.info("Stopping elite mempool scanner")
    
    # ========================================================
    # MEMPOOL MONITORING
    # ========================================================
    
    async def _monitor_mempool(self, chain: str):
        """Monitor mempool for new transactions"""
        web3 = await self._get_web3(chain)

        # Create pending transaction filter
        pending_filter = web3.eth.filter('pending')

        logger.info(f"📡 Monitoring {chain} mempool")

        while self.running:
            try:
                # Get new pending transactions
                new_txs = pending_filter.get_new_entries()

                # Process transactions in batches to avoid overwhelming the system
                if new_txs:
                    # Limit batch size to prevent resource exhaustion
                    batch_size = min(len(new_txs), 50)  # Process max 50 txs per batch
                    for i in range(0, batch_size, 10):  # Process in sub-batches of 10
                        batch = new_txs[i:i+10]
                        tasks = []
                        for tx_hash in batch:
                            # Schedule per-tx processing via TaskManager so the tasks are tracked and cancellable
                            from core.task_manager import task_manager
                            task_id = f"mempool.tx.{chain}.{tx_hash.hex()}"
                            task = await task_manager.create_scanner_task(
                                lambda tx_hash=tx_hash: self._process_pending_tx(web3, chain, tx_hash),
                                task_id
                            )
                            tasks.append(task)

                        # Wait for the sub-batch to complete before processing the next
                        if tasks:
                            await asyncio.gather(*tasks, return_exceptions=True)

                # Increased polling interval to reduce resource usage and race conditions
                await asyncio.sleep(0.5)  # 500ms polling instead of 100ms

            except Exception as e:
                logger.warning(f"Error monitoring {chain} mempool: {e}")
                await asyncio.sleep(2)  # Longer backoff on error
    
    async def _process_pending_tx(
        self,
        web3: Web3,
        chain: str,
        tx_hash: HexStr
    ):
        """Process a single pending transaction"""
        try:
            # Get transaction details
            tx = web3.eth.get_transaction(tx_hash)
            
            if not tx:
                return
            
            # Create transaction intelligence object
            tx_intel = await self._analyze_transaction(web3, chain, tx)
            
            if not tx_intel:
                return
            
            # Store in mempool
            self.pending_txs[tx_hash.hex()] = tx_intel
            
            # Classify transaction intent
            tx_intel.intent = self._classify_intent(tx_intel)
            
            # Analyze sender
            await self._analyze_sender(web3, tx_intel)
            
            # Detect MEV opportunities
            if tx_intel.intent == TxIntent.SWAP and tx_intel.value_eth > 1.0:
                await self._analyze_mev_opportunity(web3, chain, tx_intel)
            
            # Notify subscribers
            await self._notify('new_transaction', tx_intel)
            
            # Update metrics
            self.metrics['total_txs_processed'] += 1
            
        except Exception as e:
            logger.debug(f"Error processing tx {tx_hash.hex()}: {e}")
    
    async def _analyze_transaction(
        self,
        web3: Web3,
        chain: str,
        tx: TxData
    ) -> Optional[TransactionIntelligence]:
        """Deep transaction analysis"""
        try:
            tx_intel = TransactionIntelligence(
                tx_hash=tx['hash'].hex(),
                from_address=tx['from'].lower(),
                to_address=tx['to'].lower() if tx['to'] else None,
                value_eth=float(web3.from_wei(tx['value'], 'ether')),
                gas_price=float(web3.from_wei(tx.get('gasPrice', 0), 'gwei')),
                gas_limit=tx['gas'],
                nonce=tx['nonce'],
                input_data=tx['input'].hex() if tx['input'] else '',
                first_seen=time.time(),
                block_target=web3.eth.block_number + 1
            )
            
            return tx_intel
            
        except Exception as e:
            logger.debug(f"Error analyzing transaction: {e}")
            return None
    
    # ========================================================
    # INTENT CLASSIFICATION
    # ========================================================
    
    def _classify_intent(self, tx: TransactionIntelligence) -> TxIntent:
        """Classify transaction intent"""
        
        # Check function signature (first 4 bytes of input)
        if len(tx.input_data) >= 10:
            sig = tx.input_data[:10]
            
            # DEX swap
            if sig in self.DEX_ROUTER_SIGS:
                return TxIntent.SWAP
            
            # Common function signatures
            intent_map = {
                '0xa9059cbb': TxIntent.TRANSFER,  # transfer
                '0x095ea7b3': TxIntent.APPROVAL,  # approve
                '0xe8e33700': TxIntent.ADD_LIQUIDITY,  # addLiquidity
                '0xbaa2abde': TxIntent.REMOVE_LIQUIDITY,  # removeLiquidity
            }
            
            if sig in intent_map:
                return intent_map[sig]
        
        # Contract creation (no to address)
        if tx.to_address is None:
            return TxIntent.TOKEN_CREATION
        
        # Large value transfer
        if tx.value_eth > 1.0:
            return TxIntent.TRANSFER
        
        return TxIntent.UNKNOWN
    
    # ========================================================
    # SENDER ANALYSIS
    # ========================================================
    
    async def _analyze_sender(
        self,
        web3: Web3,
        tx: TransactionIntelligence
    ):
        """Analyze transaction sender"""
        
        sender = tx.from_address
        
        # Check if MEV bot
        if sender in self.KNOWN_MEV_BOTS:
            tx.is_mev_bot = True
            tx.sender_tier = "mev_bot"
            tx.toxicity = FlowToxicity.HIGHLY_TOXIC
            tx.tags.append('mev_bot')
        
        # Check if smart money
        elif sender in self.KNOWN_SMART_MONEY:
            tx.is_smart_money = True
            tx.sender_tier = "smart_money"
            tx.toxicity = FlowToxicity.TOXIC
            tx.tags.append('smart_money')
        
        # Check if whale
        elif sender in self.whale_wallets:
            whale = self.whale_wallets[sender]
            tx.sender_tier = "whale"
            tx.sender_reputation = whale.reputation_score
            tx.sender_pnl_30d = whale.avg_profit_pct
            tx.toxicity = FlowToxicity.INFORMED if whale.win_rate > 0.6 else FlowToxicity.NEUTRAL
            tx.tags.append('whale')
        
        else:
            # New wallet - analyze
            try:
                balance = web3.eth.get_balance(web3.to_checksum_address(sender))
                balance_eth = float(web3.from_wei(balance, 'ether'))
                
                if balance_eth > 100:  # >100 ETH
                    tx.sender_tier = "whale"
                    tx.toxicity = FlowToxicity.INFORMED
                    
                    # Track as whale
                    self.whale_wallets[sender] = WhaleActivity(
                        address=sender,
                        total_value_usd=balance_eth * 2000,  # Rough USD
                        reputation_score=0.5
                    )
                elif balance_eth > 10:
                    tx.sender_tier = "dolphin"
                    tx.toxicity = FlowToxicity.NEUTRAL
                else:
                    tx.sender_tier = "retail"
                    tx.toxicity = FlowToxicity.BENIGN
                    
            except Exception as e:
                logger.debug(f"Error analyzing sender: {e}")
    
    # ========================================================
    # MEV DETECTION
    # ========================================================
    
    async def _detect_mev(self, chain: str):
        """Background MEV detection task"""
        while self.running:
            try:
                # Analyze pending transactions for MEV patterns
                await self._scan_for_sandwich_attacks()
                await self._scan_for_frontrunning()
                await self._scan_for_jit_liquidity()
                
                await asyncio.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                logger.warning(f"Error in MEV detection: {e}")
                await asyncio.sleep(1)
    
    async def _analyze_mev_opportunity(
        self,
        web3: Web3,
        chain: str,
        target_tx: TransactionIntelligence
    ):
        """Analyze MEV opportunity for a target transaction"""
        
        # Only analyze swaps with significant value
        if target_tx.intent != TxIntent.SWAP or target_tx.value_eth < 1.0:
            return
        
        # Estimate price impact
        price_impact = await self._estimate_price_impact(target_tx)
        
        if price_impact < 0.02:  # <2% impact, not worth it
            return
        
        # Calculate sandwich opportunity
        expected_profit = price_impact * target_tx.value_eth * 0.5  # Rough estimate
        gas_cost = await self._estimate_gas_cost(web3, 2)  # 2 txs (front+back)
        
        if expected_profit - gas_cost > self.MIN_MEV_PROFIT:
            opportunity = MEVOpportunity(
                strategy=MEVStrategy.SANDWICH,
                target_tx_hash=target_tx.tx_hash,
                expected_profit_eth=expected_profit,
                gas_cost_eth=gas_cost,
                net_profit_eth=expected_profit - gas_cost,
                optimal_gas_price=target_tx.gas_price + 1.0,  # +1 gwei
                execution_deadline=target_tx.block_target,
                risk_score=0.3,
                details={
                    'price_impact': price_impact,
                    'target_value': target_tx.value_eth
                }
            )
            
            self.mev_opportunities.append(opportunity)
            await self._notify('mev_opportunity', opportunity)
            
            self.metrics['mev_opportunities_found'] += 1
    
    async def _scan_for_sandwich_attacks(self):
        """Detect sandwich attack opportunities"""
        
        # Group transactions by target block
        by_block: Dict[int, List[TransactionIntelligence]] = defaultdict(list)
        
        for tx in self.pending_txs.values():
            if tx.intent == TxIntent.SWAP:
                by_block[tx.block_target].append(tx)
        
        # Look for sandwich patterns
        for block, txs in by_block.items():
            if len(txs) < 2:
                continue
            
            # Sort by gas price
            sorted_txs = sorted(txs, key=lambda t: t.gas_price, reverse=True)
            
            # Check for potential sandwiches
            for i in range(len(sorted_txs) - 1):
                high_gas_tx = sorted_txs[i]
                low_gas_tx = sorted_txs[i + 1]
                
                # Same pool, different directions
                if (high_gas_tx.affected_pools and 
                    low_gas_tx.affected_pools and
                    high_gas_tx.affected_pools == low_gas_tx.affected_pools):
                    
                    # Potential sandwich detected
                    logger.info(f"⚠️ Potential sandwich detected: {high_gas_tx.tx_hash[:10]}...{low_gas_tx.tx_hash[:10]}")
    
    async def _scan_for_frontrunning(self):
        """Detect simple front-running patterns"""
        
        # Look for transactions with identical input data but higher gas
        tx_by_data: Dict[str, List[TransactionIntelligence]] = defaultdict(list)
        
        for tx in self.pending_txs.values():
            if len(tx.input_data) > 10:
                # Group by function signature + first param
                key = tx.input_data[:74]  # 4 bytes sig + 32 bytes first param
                tx_by_data[key].append(tx)
        
        # Check for duplicates with different gas
        for data, txs in tx_by_data.items():
            if len(txs) > 1:
                # Sort by gas price
                sorted_txs = sorted(txs, key=lambda t: t.gas_price, reverse=True)
                
                if sorted_txs[0].gas_price > sorted_txs[1].gas_price * 1.5:
                    logger.info(f"⚠️ Potential front-run: {sorted_txs[0].tx_hash[:10]}... ahead of {sorted_txs[1].tx_hash[:10]}...")
    
    async def _scan_for_jit_liquidity(self):
        """Detect just-in-time liquidity provision"""
        
        # Look for add_liquidity followed immediately by swap
        recent_adds = [
            tx for tx in self.pending_txs.values()
            if tx.intent == TxIntent.ADD_LIQUIDITY
            and time.time() - tx.first_seen < 5
        ]
        
        recent_swaps = [
            tx for tx in self.pending_txs.values()
            if tx.intent == TxIntent.SWAP
            and time.time() - tx.first_seen < 5
        ]
        
        # Check for matching pools
        for add_tx in recent_adds:
            for swap_tx in recent_swaps:
                if (add_tx.affected_pools and swap_tx.affected_pools and
                    set(add_tx.affected_pools) & set(swap_tx.affected_pools)):
                    logger.info(f"⚠️ Potential JIT liquidity: {add_tx.tx_hash[:10]}... + {swap_tx.tx_hash[:10]}...")
    
    # ========================================================
    # ARBITRAGE DETECTION
    # ========================================================
    
    async def _detect_arbitrage(self, chain: str):
        """Background arbitrage detection task"""
        while self.running:
            try:
                await self._scan_for_arbitrage()
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                logger.warning(f"Error in arbitrage detection: {e}")
                await asyncio.sleep(2)
    
    async def _scan_for_arbitrage(self):
        """Scan for cross-pool arbitrage opportunities"""
        
        # Group swaps by token
        swaps_by_token: Dict[str, List[TransactionIntelligence]] = defaultdict(list)
        
        for tx in self.pending_txs.values():
            if tx.intent == TxIntent.SWAP and tx.affected_tokens:
                for token in tx.affected_tokens:
                    swaps_by_token[token].append(tx)
        
        # Look for price discrepancies
        for token, swaps in swaps_by_token.items():
            if len(swaps) < 2:
                continue
            
            # Check for different pools with price differences
            # (Simplified - real implementation would calculate actual prices)
            pools_involved = set()
            for swap in swaps:
                pools_involved.update(swap.affected_pools)
            
            if len(pools_involved) >= 2:
                # Potential arbitrage opportunity
                logger.debug(f"Potential arbitrage for token {token[:10]}... across {len(pools_involved)} pools")
    
    # ========================================================
    # GAS INTELLIGENCE
    # ========================================================
    
    async def _analyze_gas(self, chain: str):
        """Background gas analysis task"""
        web3 = await self._get_web3(chain)
        
        gas_intel = GasIntelligence()
        self.gas_intelligence[chain] = gas_intel
        
        while self.running:
            try:
                # Get current block
                block = web3.eth.get_block('latest')
                
                # Update base fee
                gas_intel.current_base_fee = float(web3.from_wei(
                    block.get('baseFeePerGas', 0), 'gwei'
                ))
                
                # Collect gas prices from pending txs
                gas_prices = [
                    tx.gas_price for tx in self.pending_txs.values()
                    if tx.gas_price > 0
                ]
                
                if gas_prices:
                    gas_intel.percentile_50 = np.percentile(gas_prices, 50)
                    gas_intel.percentile_75 = np.percentile(gas_prices, 75)
                    gas_intel.percentile_90 = np.percentile(gas_prices, 90)
                    
                    # Calculate volatility
                    if len(gas_prices) > 1:
                        gas_intel.volatility = np.std(gas_prices)
                    
                    # Predict next base fee (simplified EIP-1559)
                    gas_used = block.get('gasUsed', 0)
                    gas_limit = block.get('gasLimit', 1)
                    utilization = gas_used / gas_limit if gas_limit > 0 else 0
                    
                    if utilization > 0.5:
                        # Base fee increases
                        gas_intel.predicted_next_base = gas_intel.current_base_fee * 1.125
                        gas_intel.gas_spike_probability = min(1.0, (utilization - 0.5) * 2)
                    else:
                        # Base fee decreases
                        gas_intel.predicted_next_base = gas_intel.current_base_fee * 0.875
                        gas_intel.gas_spike_probability = 0.0
                    
                    # Optimal priority fee (75th percentile)
                    gas_intel.optimal_priority_fee = gas_intel.percentile_75
                
                # Store in history
                gas_intel.history.append({
                    'timestamp': time.time(),
                    'base_fee': gas_intel.current_base_fee,
                    'priority_fee': gas_intel.optimal_priority_fee
                })
                
                await asyncio.sleep(12)  # Every block (~12s)
                
            except Exception as e:
                logger.warning(f"Error analyzing gas: {e}")
                await asyncio.sleep(5)
    
    # ========================================================
    # UTILITY METHODS
    # ========================================================
    
    async def _get_web3(self, chain: str) -> Web3:
        """Get Web3 provider"""
        if chain in self.web3_providers:
            return self.web3_providers[chain]
        
        rpc_url = self.network_config.get(chain, {}).get('rpc')
        if not rpc_url:
            raise ValueError(f"No RPC for {chain}")
        
        web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.web3_providers[chain] = web3
        return web3
    
    async def _estimate_price_impact(
        self,
        tx: TransactionIntelligence
    ) -> float:
        """Estimate price impact of a swap"""
        # Simplified - real implementation would query pool reserves
        # and calculate using constant product formula
        
        if tx.value_eth < 1:
            return 0.001
        elif tx.value_eth < 10:
            return 0.01
        elif tx.value_eth < 50:
            return 0.05
        else:
            return 0.10
    
    async def _estimate_gas_cost(
        self,
        web3: Web3,
        num_txs: int
    ) -> float:
        """Estimate gas cost for MEV bundle"""
        avg_gas_per_tx = 200_000  # Average gas per swap
        
        gas_intel = self.gas_intelligence.get('ethereum')
        if gas_intel:
            gas_price = gas_intel.optimal_priority_fee + gas_intel.current_base_fee
        else:
            gas_price = 50  # Default 50 gwei
        
        total_gas = avg_gas_per_tx * num_txs
        gas_cost_wei = total_gas * int(gas_price * 1e9)
        
        return float(web3.from_wei(gas_cost_wei, 'ether'))
    
    async def _cleanup_loop(self):
        """Clean up old pending transactions"""
        while self.running:
            try:
                now = time.time()
                
                # Remove old transactions (>5 min)
                old_txs = [
                    tx_hash for tx_hash, tx in self.pending_txs.items()
                    if now - tx.first_seen > 300
                ]
                
                for tx_hash in old_txs:
                    del self.pending_txs[tx_hash]
                
                # Clean up old MEV opportunities
                current_block = max(
                    (tx.block_target for tx in self.pending_txs.values()),
                    default=0
                )
                
                self.mev_opportunities = [
                    opp for opp in self.mev_opportunities
                    if opp.execution_deadline >= current_block
                ]
                
                logger.debug(f"Cleaned up {len(old_txs)} old transactions")
                
                await asyncio.sleep(60)  # Every minute
                
            except Exception as e:
                logger.warning(f"Error in cleanup: {e}")
                await asyncio.sleep(60)
    
    async def _notify(self, event_type: str, data: Any):
        """Notify subscribers of events"""
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to events"""
        self.subscribers[event_type].append(callback)
        logger.info(f"Subscribed to {event_type} events")
    
    # ========================================================
    # SNAPSHOT & REPORTING
    # ========================================================
    
    def get_snapshot(self, chain: str) -> MempoolSnapshot:
        """Get current mempool snapshot"""
        
        web3 = self.web3_providers.get(chain)
        if not web3:
            return MempoolSnapshot(
                timestamp=time.time(),
                block_number=0,
                pending_tx_count=0,
                total_value_eth=0.0,
                avg_gas_price=0.0,
                median_gas_price=0.0,
                gas_intelligence=GasIntelligence(),
                whale_txs=[],
                mev_opportunities=[],
                arbitrage_opportunities=[],
                toxic_flow_score=0.0,
            )
        
        # Calculate metrics
        pending_txs = list(self.pending_txs.values())
        
        total_value = sum(tx.value_eth for tx in pending_txs)
        gas_prices = [tx.gas_price for tx in pending_txs if tx.gas_price > 0]
        
        avg_gas = statistics.mean(gas_prices) if gas_prices else 0.0
        median_gas = statistics.median(gas_prices) if gas_prices else 0.0
        
        # Whale transactions
        whale_txs = [
            tx for tx in pending_txs
            if tx.sender_tier in ['whale', 'institutional', 'smart_money']
        ]
        
        # Toxic flow score (0-1)
        toxicity_scores = {
            FlowToxicity.BENIGN: 0.0,
            FlowToxicity.NEUTRAL: 0.25,
            FlowToxicity.INFORMED: 0.5,
            FlowToxicity.TOXIC: 0.75,
            FlowToxicity.HIGHLY_TOXIC: 1.0
        }
        
        toxic_flow = statistics.mean([
            toxicity_scores[tx.toxicity] for tx in pending_txs
        ]) if pending_txs else 0.0
        
        # Market urgency (based on gas prices and MEV activity)
        if avg_gas > 0:
            gas_intel = self.gas_intelligence.get(chain)
            if gas_intel:
                # High gas prices = high urgency
                # MEV activity = high urgency
                gas_prediction = self._analyze_gas_intelligence(tx)
        
        return MempoolSnapshot(
            timestamp=time.time(),
            block_number=web3.eth.block_number,
            pending_tx_count=len(pending_txs),
            total_value_eth=total_value,
            avg_gas_price=avg_gas,
            median_gas_price=median_gas,
            gas_intelligence=self.gas_intelligence.get(chain, GasIntelligence()),
            whale_txs=whale_txs[:10],  # Top 10
            mev_opportunities=self.mev_opportunities[:10],
            arbitrage_opportunities=self.arbitrage_opportunities[:10],
            toxic_flow_score=toxic_flow,
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get scanner metrics"""
        return {
            'total_txs_processed': self.metrics['total_txs_processed'],
            'mev_opportunities_found': self.metrics['mev_opportunities_found'],
            'pending_tx_count': len(self.pending_txs),
            'whale_count': len(self.whale_wallets),
            'active_mev_opportunities': len(self.mev_opportunities),
            'active_arbitrage_opportunities': len(self.arbitrage_opportunities)
        }
    
    def get_top_whales(self, limit: int = 10) -> List[WhaleActivity]:
        """Get top whale wallets by activity"""
        sorted_whales = sorted(
            self.whale_wallets.values(),
            key=lambda w: w.reputation_score,
            reverse=True
        )
        return sorted_whales[:limit]
    
    def get_gas_prediction(self, chain: str) -> Optional[Dict]:
        """Get gas price prediction"""
        gas_intel = self.gas_intelligence.get(chain)
        if not gas_intel:
            return None
        
        return {
            'current_base_fee': gas_intel.current_base_fee,
            'predicted_next_base': gas_intel.predicted_next_base,
            'optimal_priority_fee': gas_intel.optimal_priority_fee,
            'recommended_total': gas_intel.predicted_next_base + gas_intel.optimal_priority_fee,
            'percentiles': {
                '50th': gas_intel.percentile_50,
                '75th': gas_intel.percentile_75,
                '90th': gas_intel.percentile_90
            },
            'volatility': gas_intel.volatility,
            'spike_probability': gas_intel.gas_spike_probability
        }


# ============================================================
# ADVANCED ANALYTICS
# ============================================================

class MempoolAnalytics:
    """Advanced analytics on mempool data"""
    
    def __init__(self, scanner: MempoolScannerUltra):
        self.scanner = scanner
    
    def calculate_market_sentiment(self) -> Dict[str, float]:
        """Calculate market sentiment from mempool activity"""
        
        pending_txs = list(self.scanner.pending_txs.values())
        
        if not pending_txs:
            return {
                'bullish': 0.5,
                'bearish': 0.5,
                'neutral': 1.0,
                'confidence': 0.0
            }
        
        # Count buy vs sell intents
        buys = sum(1 for tx in pending_txs if 'buy' in tx.tags)
        sells = sum(1 for tx in pending_txs if 'sell' in tx.tags)
        total = buys + sells
        
        if total == 0:
            return {
                'bullish': 0.5,
                'bearish': 0.5,
                'neutral': 1.0,
                'confidence': 0.0
            }
        
        buy_ratio = buys / total
        sell_ratio = sells / total
        
        # Weight by transaction value and sender tier
        whale_buys = sum(
            tx.value_eth for tx in pending_txs
            if 'buy' in tx.tags and tx.sender_tier in ['whale', 'institutional']
        )
        whale_sells = sum(
            tx.value_eth for tx in pending_txs
            if 'sell' in tx.tags and tx.sender_tier in ['whale', 'institutional']
        )
        
        # Calculate weighted sentiment
        if whale_buys + whale_sells > 0:
            weighted_buy = whale_buys / (whale_buys + whale_sells)
        else:
            weighted_buy = 0.5
        
        # Combine metrics
        sentiment = (buy_ratio * 0.4 + weighted_buy * 0.6)
        
        return {
            'bullish': sentiment,
            'bearish': 1 - sentiment,
            'neutral': abs(sentiment - 0.5) * 2,  # Distance from 50/50
            'confidence': min(1.0, total / 100)
        }
    
    def detect_coordinated_activity(self) -> List[Dict]:
        """Detect coordinated wallet activity"""
        
        coordinated = []
        
        # Group transactions by time window
        time_windows = defaultdict(list)
        
        for tx in self.scanner.pending_txs.values():
            window = int(tx.first_seen / 10) * 10  # 10-second windows
            time_windows[window].append(tx)
        
        # Look for clusters of similar transactions
        for window, txs in time_windows.items():
            if len(txs) < 3:
                continue
            
            # Group by target
            by_target = defaultdict(list)
            for tx in txs:
                if tx.to_address:
                    by_target[tx.to_address].append(tx)
            
            # Check for coordinated activity (3+ txs to same target)
            for target, target_txs in by_target.items():
                if len(target_txs) >= 3:
                    coordinated.append({
                        'window': window,
                        'target': target,
                        'tx_count': len(target_txs),
                        'total_value': sum(tx.value_eth for tx in target_txs),
                        'wallets': [tx.from_address for tx in target_txs]
                    })
        
        return coordinated
    
    def estimate_execution_probability(
        self,
        tx: TransactionIntelligence,
        target_block: int
    ) -> float:
        """Estimate probability of transaction execution in target block"""
        
        # Get gas intelligence
        gas_intel = self.scanner.gas_intelligence.get('ethereum')
        if not gas_intel:
            return 0.5
        
        # Compare to percentiles
        if tx.gas_price >= gas_intel.percentile_90:
            return 0.95
        elif tx.gas_price >= gas_intel.percentile_75:
            return 0.75
        elif tx.gas_price >= gas_intel.percentile_50:
            return 0.50
        else:
            return 0.25


# ============================================================
# EXAMPLE USAGE
# ============================================================

async def main():
    """Example usage"""
    import json
    
    # Mock network config
    network_config = {
        'ethereum': {
            'rpc': 'https://eth.llamarpc.com'
        }
    }
    
    scanner = MempoolScannerUltra(network_config=network_config)
    analytics = MempoolAnalytics(scanner)
    
    # Subscribe to events
    async def on_mev_opportunity(opp: MEVOpportunity):
        print(f"\n💰 MEV Opportunity Detected!")
        print(f"   Strategy: {opp.strategy.value}")
        print(f"   Expected Profit: {opp.expected_profit_eth:.4f} ETH")
        print(f"   Net Profit: {opp.net_profit_eth:.4f} ETH")
        print(f"   Confidence: {opp.confidence:.2%}")
    
    async def on_whale_tx(tx: TransactionIntelligence):
        print(f"\n🐋 Whale Transaction Detected!")
        print(f"   From: {tx.from_address[:10]}...")
        print(f"   Value: {tx.value_eth:.2f} ETH")
        print(f"   Intent: {tx.intent.value}")
        print(f"   Toxicity: {tx.toxicity.value}")
    
    scanner.subscribe('mev_opportunity', on_mev_opportunity)
    scanner.subscribe('new_transaction', on_whale_tx)
    
    # Start scanner
    await scanner.start(['ethereum'])
    
    print("🚀 Elite Mempool Scanner started")
    print("=" * 60)
    
    # Monitor for 60 seconds
    for i in range(12):
        await asyncio.sleep(5)
        
        # Get snapshot
        snapshot = scanner.get_snapshot('ethereum')
        
        print(f"\n📊 Mempool Snapshot (Block {snapshot.block_number})")
        print(f"   Pending TXs: {snapshot.pending_tx_count}")
        print(f"   Total Value: {snapshot.total_value_eth:.2f} ETH")
        print(f"   Avg Gas: {snapshot.avg_gas_price:.2f} gwei")
        print(f"   Whale TXs: {len(snapshot.whale_txs)}")
        print(f"   MEV Opportunities: {len(snapshot.mev_opportunities)}")
        print(f"   Toxic Flow: {snapshot.toxic_flow_score:.2%}")
        print(f"   Market Urgency: {snapshot.market_urgency:.2%}")
        
        # Gas prediction
        gas_pred = scanner.get_gas_prediction('ethereum')
        if gas_pred:
            print(f"\n⛽ Gas Prediction:")
            print(f"   Current Base: {gas_pred['current_base_fee']:.2f} gwei")
            print(f"   Next Base: {gas_pred['predicted_next_base']:.2f} gwei")
            print(f"   Recommended: {gas_pred['recommended_total']:.2f} gwei")
            print(f"   Spike Risk: {gas_pred['spike_probability']:.2%}")
        
        # Sentiment
        sentiment = analytics.calculate_market_sentiment()
        print(f"\n💭 Market Sentiment:")
        print(f"   Bullish: {sentiment['bullish']:.2%}")
        print(f"   Bearish: {sentiment['bearish']:.2%}")
        print(f"   Confidence: {sentiment['confidence']:.2%}")
    
    # Stop scanner
    await scanner.stop()
    
    # Final metrics
    print("\n" + "=" * 60)
    print("📈 Final Metrics:")
    metrics = scanner.get_metrics()
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
