"""
Elite Production-Grade Trading System
Lifecycle-Safe, Observable, Deterministic

FINAL FORM — SINGLE SOURCE OF TRUTH
"""

import asyncio
import logging
import os
import sys
import yaml
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

from core.logging import setup_logging
from core.lifecycle import get_startup_director

from core.models import (
    OrderSide,
    OrderType,
    TradeOpportunity,
    TokenInfo,
    MarketData,
    AssetClass,
)

from entry.verdict import EntryVerdict
from position.verdict import PositionVerdict
from risk.risk_verdict import RiskVerdict

from trading.trade_intent.trade_intent import TradeIntent, TradeSide
from trading.execution.trade_engine import ApprovedOrder
from trading.pnl_models import TradePnL
from trading.pnl_tracker import PnLTracker

from trading.token_pipeline.token_candidate import TokenCandidate


def load_yaml(file_path):
    """Load a YAML file."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}


def compose_system(project_root: Path) -> "SystemComposition":
    from core.health_check import HealthMonitor
    from core.task_manager import task_manager

    from scanners.scan_director import ScanDirector
    from strategies.elite_strategy_manager import EliteStrategyManager
    from strategies.strategy_factory import create_strategies_from_config
    from strategies import registry
    from ai.neural_brain import NeuralBrain
    from ai.elite_async_ai_controller import EliteAsyncAIController

    from entry import EntryManager, get_default_policy as entry_policy
    from position import PositionManager, get_default_policy as position_policy
    from risk import RiskManager
    from exit import ExitManager, get_default_policy as exit_policy

    from trading.execution.trade_engine import TradingEngine
    from trading.execution.trade_executor import HybridTradeExecutor
    from trading.execution.post_trade_manager import PostTradeManager
    from trading.token_pipeline.token_registry import TokenRegistry
    from trading.token_pipeline.multi_chain_ingestion import initialize_multi_chain_ingestion_pipeline
    from trading.token_pipeline import initialize_queue_manager
    from trading.trading_mode import TradingModeManager

    from router.hybrid_router_manager import HybridRouterManager
    from networks.universal_network_manager import UniversalNetworkManager
    from config import load_config
    from utils.profit_engine import ProfitEngine
    from utils.ownership_guard import OwnershipGuard
    from data_sources.data_manager import DataManager

    config = load_config()

    # Initialize ownership guard for startup verification and runtime kill-switch
    ownership_guard = OwnershipGuard(
        config=config,
        kill_switch_path=config.get('ownership', {}).get('kill_switch_path', 'kill.switch'),
    )
    ownership_guard.verify_startup()

    decision_queue: asyncio.Queue[TokenCandidate] = asyncio.Queue(maxsize=1000)
    opportunity_queue: asyncio.Queue[TradeOpportunity] = asyncio.Queue(maxsize=1000)

    # Initialize the multi-chain queue manager
    initialize_queue_manager()

    ingestion_pipeline = initialize_multi_chain_ingestion_pipeline(
        config.get("ai", {})
    )

    health_manager = HealthMonitor()
    
    # Use UniversalNetworkManager - this pulls RPCs from config_unified.yaml
    # This is critical for scanners to work - they need actual network clients
    # The UniversalNetworkManager reads networks from config["networks"]
    network_manager = UniversalNetworkManager(config)

    # Pass the full unified config so the HybridRouterManager can access `networks`.
    router_manager = HybridRouterManager(
        network_manager=network_manager,
        config=config
    )

    strategies = create_strategies_from_config(config, registry)
    strategy_manager = EliteStrategyManager(strategies)

    neural_brain = NeuralBrain(config=config.get("neural_brain", {}))

    ai_controller = EliteAsyncAIController(
        config=config.get("ai", {}),
        strategy_manager=strategy_manager,
        neural_brain=neural_brain,
        decision_queue=decision_queue,
        opportunity_queue=opportunity_queue
    )

    scan_director = ScanDirector(
        network_manager=network_manager,
        config=config,
        ai_controller=ai_controller
    )

    trade_executor = HybridTradeExecutor(
        config=config.get("trading", {}),
        network_manager=network_manager,
        hybrid_router_manager=router_manager,
        trading_mode=None
    )

    # Initialize profit engine for wallet balance tracking
    profit_engine = ProfitEngine()

    # Initialize data manager for opportunity enrichment
    data_manager = DataManager(
        db_path=config.get("database", {}).get("path", "database/trades.db"),
        network_manager=network_manager
    )

    # Initialize PnL tracker for profit/loss tracking and strategy performance
    pnl_tracker = PnLTracker(data_dir=Path("data"))

    # Initialize post-trade manager for position and risk management
    post_trade_manager = PostTradeManager(config=config.get("trading", {}))
    post_trade_manager.set_balance_tracking(profit_engine, trade_executor)

    trading_engine = TradingEngine(
        config=config.get("trading", {}),
        ai=None,
        risk=None,
        executor=trade_executor,
        options={}
    )

    composition = SystemComposition(config=config)

    composition.components['scan_director'] = scan_director
    composition.components['strategy_manager'] = strategy_manager
    composition.components['neural_brain'] = neural_brain
    composition.components['ai_controller'] = ai_controller
    composition.components['entry_manager'] = EntryManager(config.get("entry", {}), entry_policy())
    composition.components['position_manager'] = PositionManager(config.get("position", {}), position_policy())
    composition.components['risk_manager'] = RiskManager(config.get("risk", {}))
    composition.components['exit_manager'] = ExitManager(config.get("exit", {}), exit_policy())
    composition.components['trading_engine'] = trading_engine
    composition.components['trade_executor'] = trade_executor
    composition.components['token_registry'] = TokenRegistry(config.get("token_registry", {}))
    composition.components['trading_mode_manager'] = TradingModeManager(config.get("trading", {}))
    composition.components['decision_queue'] = decision_queue
    composition.components['opportunity_queue'] = opportunity_queue
    composition.components['ingestion_pipeline'] = ingestion_pipeline
    composition.components['health_manager'] = health_manager
    composition.components['task_manager'] = task_manager
    composition.components['profit_engine'] = profit_engine
    composition.components['data_manager'] = data_manager
    composition.components['pnl_tracker'] = pnl_tracker
    composition.components['ownership_guard'] = ownership_guard
    composition.components['post_trade_manager'] = post_trade_manager
    composition.components['network_manager'] = network_manager

    composition.components['startup_director'] = get_startup_director(composition)

    return composition


class SystemComposition:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.shutdown_requested = False
        self.components = {}

    def __getattr__(self, name):
        if name in self.components:
            return self.components[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    async def initialize(self) -> None:
        if self.scan_director:
            await self.scan_director.initialize()


def get_usdc_address(chain: str) -> str:
    usdc_addresses = {
        'ethereum': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'bsc': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',
        'polygon': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
        'arbitrum': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'optimism': '0x0b2C639c533813f4Aa9D7837AFe6E7c79E5dDfCa',
        'base': '0xd9aAEc86B65D86f6A7B5Bafb0a9E12fE6A9c9221',
        'avalanche': '0xA7D7079b0FEaD91F3E65f86E8915EbD7ef717d57',
        'fantom': '0x04068DA6C83AFCFA0e13ba15A6696662335D5B75',
        'blast': '0x430F2a20265b5F887BA15a0a1b65C4A9F88AfEdB',
        'cronos': '0xc21223249CA28397A4Ab32f18d00d804031A2C490',
        'kava': '0x965F84D1b5a68C1b846a452448C551bE6e6170f2',
        'aurora': '0xB12BFcA5A5585A5C72fb5eB11Fb9eBd8C6b86299',
        'harmony': '0x985458e523583A0A02032A8718C4533054B7C739',
        'celo': '0x765DE816845861e75A25f80b5bEe9609E6eF94a1',
        'moonriver': '0xE3F5a88A49fA967d5013539Ce4A1bE5a9Bf6EDD7',
        'moonbeam': '0xE3F5a88A49fA967d5013539Ce4A1bE5a9Bf6EDD7',
    }
    return usdc_addresses.get(chain.lower(), usdc_addresses['ethereum'])


async def token_candidate_bridge(composition: SystemComposition) -> None:
    """Bridge TokenCandidate objects from multi-chain queue to AI controller's decision_queue."""
    log = logging.getLogger("token_bridge")
    log.info("Token candidate bridge started")
    
    from trading.token_pipeline import dequeue_any_token
    from trading.token_pipeline.multi_chain_queue_manager import get_queue_manager
    
    # Verify we're using the correct queue manager instance
    queue_manager = get_queue_manager()
    log.info(f"Token bridge using queue manager instance: {id(queue_manager)}")
    
    # Log initial queue state
    stats = queue_manager.get_all_stats()
    for chain_type, chain_stats in stats.items():
        log.info(f"Initial {chain_type} queue: {chain_stats['current_size']} tokens")
    
    iteration_count = 0
    
    try:
        while not composition.shutdown_requested:
            try:
                # Dequeue token candidate from any chain
                candidate = await dequeue_any_token(timeout=1.0)
                if candidate is None:
                    iteration_count += 1
                    if iteration_count % 10 == 0:
                        log.info(f"Token bridge status - iteration {iteration_count}, queue empty")
                        # Log queue stats for debugging
                        stats = queue_manager.get_all_stats()
                        total_tokens = sum(chain_stats['current_size'] for chain_stats in stats.values())
                        log.info(f"Queue stats - Total tokens: {total_tokens} | {stats}")
                    continue
                
                log.info(f"Bridging token candidate: {candidate.symbol} on {candidate.chain_type.value}")
                
                # Put TokenCandidate directly into decision_queue for AI controller to process
                await composition.decision_queue.put(candidate)
                log.info(f"Sent token candidate to AI controller decision_queue: {candidate.symbol} on {candidate.chain_type.value}")
                iteration_count = 0  # Reset iteration counter when we process a token
                
            except asyncio.TimeoutError:
                iteration_count += 1
                if iteration_count % 10 == 0:
                    log.info(f"Token bridge status - iteration {iteration_count}")
                continue
            except Exception as e:
                log.error(f"Error in token bridge: {e}", exc_info=True)
                await asyncio.sleep(1)
                
    except Exception as e:
        log.error(f"Token bridge failed: {e}", exc_info=True)


async def trading_loop(composition: SystemComposition) -> None:
    log = logging.getLogger("trading")

    scanner_task = asyncio.create_task(scanner_loop(composition))

    log.info("Trading loop started")
    iteration_count = 0

    try:
        while not composition.shutdown_requested:
            try:
                opportunity = await asyncio.wait_for(
                    composition.opportunity_queue.get(),
                    timeout=1.0
                )
                log.info(f"Received opportunity: {opportunity.token.symbol} on {opportunity.chain}")
                
                # ENRICH: Add historical data and technical indicators
                opportunity = await _enrich_opportunity(opportunity, composition)
            except asyncio.TimeoutError:
                iteration_count += 1
                if iteration_count % 10 == 0:
                    log.info(f"Trading loop status - iteration {iteration_count}, opportunity queue size: {composition.opportunity_queue.qsize()}")
                continue

            strategy_recommendation = None
            if opportunity.metadata and 'strategy_recommendation' in opportunity.metadata:
                strategy_recommendation = opportunity.metadata['strategy_recommendation']
                strategy_id = strategy_recommendation.get('recommended_strategy_id', 'UNKNOWN')
                confidence = strategy_recommendation.get('confidence', 0)
                log.info(f"Using AI-selected strategy: {strategy_id} "
                         f"(confidence: {confidence:.2%})")

                # Skip trading if NO_TRADE sentinel is selected
                if strategy_id == "NO_TRADE":
                    log.debug(f"AI selected NO_TRADE for {opportunity.token.symbol}: {strategy_recommendation.get('key_factors', ['No reason provided'])}")
                    continue
            else:
                market_data = {
                    "symbol": opportunity.token.symbol,
                    "price": float(opportunity.market_data.price),
                    "liquidity": float(opportunity.market_data.liquidity),
                    "volume": float(opportunity.market_data.volume_24h),
                }

                signals = await composition.strategy_manager.execute_strategies_parallel(market_data)

                if not any(s.success for s in signals):
                    log.warning(f"Rejected by strategies: {opportunity.token.symbol}")
                    continue

                best_signal = max(
                    [s for s in signals if s.success and s.signal],
                    key=lambda s: s.signal.confidence if s.signal else 0.0,
                    default=None
                )

                if not best_signal:
                    log.warning(f"No valid strategy signal found for {opportunity.token.symbol}")
                    continue

                log.info(f"Strategy approval: {opportunity.token.symbol} - Selected: {best_signal.strategy_id} "
                         f"(confidence: {best_signal.signal.confidence:.2%})")

            entry_data = {
                "price": float(opportunity.market_data.price),
                "liquidity": float(opportunity.market_data.liquidity),
                "volume_24h": float(opportunity.market_data.volume_24h),
                "chain": opportunity.chain,
                "token_address": opportunity.token.address,
                "symbol": opportunity.token.symbol,
                "market_cap": opportunity.metadata.get("market_cap") if opportunity.metadata else None,
                "confidence": opportunity.confidence,
                # USE ENRICHED DATA - from opportunity enricher
                "price_history": opportunity.metadata.get("price_history", [float(opportunity.market_data.price)]) if opportunity.metadata else [float(opportunity.market_data.price)],
                "volume_history": opportunity.metadata.get("volume_history", [float(opportunity.market_data.volume_24h)]) if opportunity.metadata else [float(opportunity.market_data.volume_24h)],
                "rsi": opportunity.metadata.get("technical_indicators", {}).get("rsi", 50.0) if opportunity.metadata else 50.0,
                "volume_profile": opportunity.metadata.get("volume_profile", 0.5) if opportunity.metadata else 0.5,
                "social_score": opportunity.metadata.get("social_score", 0.5) if opportunity.metadata else 0.5,
                "holder_concentration": opportunity.metadata.get("holder_concentration", 0.5) if opportunity.metadata else 0.5,
                "whale_activity": opportunity.metadata.get("whale_activity", 0.0) if opportunity.metadata else 0.0,
                "rugpull_risk": opportunity.metadata.get("rugpull_risk", 0.0) if opportunity.metadata else 0.0,
                "smart_money_flow": opportunity.metadata.get("smart_money_flow", 0.0) if opportunity.metadata else 0.0,
                "market_regime": 0,
                "bids": [],
                "asks": [],
            }

            entry = composition.entry_manager.assess_opportunity(
                opportunity.token.symbol,
                entry_data
            )
            # Accept APPROVE verdicts, and allow CONDITIONAL during bootstrap (limited data)
            if entry.verdict not in (EntryVerdict.APPROVE, EntryVerdict.CONDITIONAL):
                log.warning(
                    f"Entry rejected: {opportunity.token.symbol} - "
                    f"Verdict: {entry.verdict.value}, Reason: {entry.reason}, "
                    f"Confidence: {entry.confidence:.2%}"
                )
                if entry.metadata and entry.metadata.get("has_limited_data"):
                    log.debug(
                        f"Limited historical data detected. "
                        f"Features: {entry.metadata.get('features', {})}"
                    )
                continue

            position = composition.position_manager.assess_new_opportunity(opportunity, entry)
            if position.verdict != PositionVerdict.HEALTHY:
                log.warning(f"Position rejected: {opportunity.token.symbol}")
                continue

            suggested_size = position.metadata.get('suggested_size', Decimal('0')) if position.metadata else Decimal('0')
            log.debug(f"Position assessment for {opportunity.token.symbol}: verdict={position.verdict.value}, suggested_size={suggested_size}")
            
            # Skip trade if suggested size is 0 or too small
            if suggested_size <= 0:
                log.warning(f"Skipping trade: suggested_size is {suggested_size} for {opportunity.token.symbol}")
                continue
            
            # Ensure minimum trade size (at least $10 to cover gas and be profitable)
            min_trade_size = Decimal('10.0')
            if suggested_size < min_trade_size:
                log.debug(f"Adjusting trade size from {suggested_size} to minimum {min_trade_size}")
                suggested_size = min_trade_size

            usdc_address = get_usdc_address(opportunity.chain)
            
            if not usdc_address:
                log.error(f"USDC address not found for chain {opportunity.chain}. Cannot execute trade.")
                continue

            intent = TradeIntent(
                chain=opportunity.chain,
                router="uniswap",
                token_in=usdc_address,
                token_out=opportunity.token.address,
                amount_in=suggested_size,
                min_amount_out=suggested_size * Decimal("0.95"),
                deadline=datetime.now(timezone.utc) + timedelta(minutes=5),
                opportunity_id=opportunity.opportunity_id,
                side=TradeSide.BUY,
            )

            if not hasattr(intent, 'amount_usd'):
                intent.amount_usd = float(suggested_size)

            risk = composition.risk_manager.assess_trade_intent(intent)
            if risk.verdict != RiskVerdict.APPROVED:
                log.warning(f"Risk rejected: {opportunity.token.symbol}")
                continue

            order = ApprovedOrder(
                order_id=f"trade_{int(datetime.now().timestamp())}",
                asset=opportunity.token.address,
                side=OrderSide.BUY,
                quantity=float(suggested_size),
                order_type=OrderType.MARKET,
                price=float(opportunity.market_data.price),
                chain=opportunity.chain
            )

            log.info(f"Executing trade: {opportunity.token.symbol}")
            result = await composition.trading_engine.execute_approved_order(order)
            log.info(f"Trade result: {result.status}")
            
            # === NEW: Record entry into PnL tracker ===
            if result.status == "executed":
                # Get the best strategy recommendation for this opportunity
                strategy_used = opportunity.metadata.get("recommended_strategy", "unknown") if opportunity.metadata else "unknown"
                
                # Record the opening trade
                trade = TradePnL(
                    token=opportunity.token.symbol,
                    chain=opportunity.chain,
                    strategy=strategy_used,
                    entry_price=float(opportunity.market_data.price),
                    exit_price=None,  # Not closed yet
                    size=float(suggested_size),
                    fees=0.0,  # Will be updated when position closes
                    entry_time=datetime.now(timezone.utc).isoformat(),
                    realized=False
                )
                
                # Store trade ID for later closing
                trade_id = order.order_id
                composition.pnl_tracker.enter_trade(trade_id, trade)
                log.debug(f"PnL entry recorded: {trade_id} for {opportunity.token.symbol}")

    finally:
        scanner_task.cancel()
        await asyncio.gather(scanner_task, return_exceptions=True)


async def _enrich_opportunity(opportunity: TradeOpportunity, composition: SystemComposition) -> TradeOpportunity:
    """
    Enrich opportunity with historical data and technical indicators.
    
    This ensures the Entry Manager receives complete market data instead of
    single data points, allowing it to make informed decisions based on real indicators.
    
    Args:
        opportunity: Original opportunity from scanner/AI controller
        composition: System composition for accessing data managers
        
    Returns:
        Enriched opportunity with price history, volume history, and calculated indicators
    """
    log = logging.getLogger("enrichment")
    
    try:
        from data_sources.opportunity_enricher import OpportunityEnricher
        
        # Create enricher with data manager
        data_manager = composition.components.get("data_manager")
        enricher = OpportunityEnricher(data_manager=data_manager)
        
        # Enrich the opportunity
        enriched = await enricher.enrich(opportunity)
        
        if enriched.metadata and enriched.metadata.get("data_enriched"):
            data_quality = enriched.metadata.get("data_quality", {})
            log.info(
                f"✅ Opportunity enriched: {enriched.token.symbol} "
                f"({data_quality.get('overall_quality', 'unknown')} data quality, "
                f"{data_quality.get('price_points', 0)} price points)"
            )
        
        return enriched
        
    except ImportError:
        log.warning("Opportunity enricher not available, using raw opportunity")
        return opportunity
    except Exception as e:
        log.warning(f"Failed to enrich opportunity: {e}")
        return opportunity


async def scanner_loop(composition: SystemComposition) -> None:
    log = logging.getLogger("scanner")
    log.info("Scanner started")

    while not composition.shutdown_requested:
        try:
            await composition.scan_director.scan_all()
            await asyncio.sleep(30)
        except Exception as e:
            log.error(f"Scanner error: {e}")
            await asyncio.sleep(10)


async def main() -> None:
    root = Path(__file__).parent
    setup_logging(LOG_LEVEL, root / "logs" / "ecosystem.log")

    composition = compose_system(root)
    await composition.initialize()

    await composition.ai_controller.start()
    await composition.ai_controller.mark_live()

    try:
        # Start both the token bridge and the trading loop
        bridge_task = asyncio.create_task(token_candidate_bridge(composition))
        trading_task = asyncio.create_task(trading_loop(composition))
        
        # Wait for either task to complete (usually due to shutdown)
        await asyncio.gather(bridge_task, trading_task, return_exceptions=True)
    finally:
        composition.shutdown_requested = True
        await composition.ai_controller.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown requested")
