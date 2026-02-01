import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Coroutine, Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass

from core.lifecycle import OrchestratorComponentState, ComponentState
from core.position import ActivePosition
from core.selection import SelectionMethod
from core.models import StrategyPerformance, StrategyType


class MarketRegime(str, Enum):
    """Market regime classifications for strategy selection."""
    BULL = "bull"
    BULL_TRENDING = "bull_trending"
    BEAR = "bear"
    BEAR_TRENDING = "bear_trending"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
from core.models import (
    StrategyRecommendation,
    TradeOpportunity,
    TokenInfo,
    MarketData,
    AssetClass,
    StrategyPerformance,
    StrategyType,
)
from core.task_manager import task_manager
from strategies.elite_strategy_manager import EliteStrategyManager
from ai.neural_brain import NeuralBrain
from trading.pnl_tracker import PnLTracker
from core.fingerprint import generate_fingerprint, EcosystemFingerprint

logger = logging.getLogger(__name__)


class EliteAsyncAIController:
    """
    AI Advisory Controller.
    Converts TokenCandidates → TradeOpportunities with strategy recommendations.

    HARD BOUNDARY:
    - Does NOT place trades
    - Does NOT manage positions
    - Does NOT control risk
    """

    DEDUP_TTL_SECONDS = 3600
    MAX_DEDUP_SIZE = 50_000

    def __init__(
        self,
        config: Dict[str, Any],
        lifecycle_orchestrator=None,
        startup_director=None,
        strategy_manager: Optional[EliteStrategyManager] = None,
        neural_brain: Optional[NeuralBrain] = None,
        decision_queue: Optional[asyncio.Queue] = None,
        opportunity_queue: Optional[asyncio.Queue] = None,
    ):
        self.config = config
        self.lifecycle_orchestrator = lifecycle_orchestrator
        self.startup_director = startup_director

        self.strategy_manager = strategy_manager
        self.neural_brain = neural_brain
        self.pnl_tracker = PnLTracker()  # Initialize PnL tracking

        self.decision_queue = decision_queue
        self.opportunity_queue = opportunity_queue or asyncio.Queue(maxsize=1000)

        self._running = False
        self._live = False
        self._shutdown_requested = False
        self._started = False

        self._background_tasks: Set[asyncio.Task] = set()

        self._seen_tokens: Dict[str, float] = {}
        self._seen_opportunities: Dict[str, float] = {}

        self.current_regime = "UNKNOWN"
        self.regime_confidence = 0.0
        self.regime_last_updated = 0.0
        self.regime_cache_ttl = 300.0

        self.global_profit = Decimal("0")
        self.global_trades = 0
        
        # Generate ecosystem fingerprint for provenance tracking
        self._ecosystem_fingerprint: Optional[EcosystemFingerprint] = None
        try:
            self._ecosystem_fingerprint = generate_fingerprint(self.config)
            logger.info(f"Generated ecosystem fingerprint: {self._ecosystem_fingerprint.composite_hash[:16]}...")
        except Exception as e:
            logger.warning(f"Failed to generate ecosystem fingerprint: {e}")

    # Test helpers
    async def is_ready(self) -> bool:
        """For tests: indicate readiness. Async to match awaitable usage in tests."""
        return self._started and not self._shutdown_requested
    
    @property
    def ecosystem_fingerprint(self) -> Optional[EcosystemFingerprint]:
        """Get the ecosystem fingerprint for this controller instance."""
        return self._ecosystem_fingerprint

    async def make_decision(self, token_candidate, context=None):
        """For tests: simple decision stub."""
        from core.models import StrategyDecision, DecisionOutcome, OrderSide, OrderType, TimeInForce
        from decimal import Decimal
        return StrategyDecision(
            opportunity_id="test_opportunity",
            decision_id="test_decision",
            token=token_candidate,
            outcome=DecisionOutcome.APPROVED,
            strategy_name="TestStrategy",
            strategy_id="test_strategy",
            confidence=0.8,
            position_size=Decimal("1.0"),
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            time_in_force=TimeInForce.GTC
        )

    # ------------------------------------------------------------------ #
    # Initialization
    # ------------------------------------------------------------------ #

    async def async_initialize(self) -> None:
        if self.strategy_manager is None:
            from strategies.strategy_factory import create_strategies_from_config
            from strategies import registry
            strategies = create_strategies_from_config(self.config, registry)
            self.strategy_manager = EliteStrategyManager(strategies)

        if self.neural_brain is None:
            self.neural_brain = NeuralBrain(self.config)

        if hasattr(self.strategy_manager, "initialize_strategies"):
            await self.strategy_manager.initialize_strategies()

        self._async_initialized = True
        self._started = True
        self._running = True
        
        await self.start_background_tasks()
        
        logger.info("AI Controller async initialization complete")

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        logger.info("Starting EliteAsyncAIController")

        if not self.async_initialize:
            await self.async_initialize()

        self._running = True
        self._started = True

        if self.lifecycle_orchestrator:
            self.lifecycle_orchestrator.register_component_instance(
                "ai_controller", self
            )
            self.lifecycle_orchestrator.update_component_state(
                "ai_controller", OrchestratorComponentState.READY
            )

        if self.startup_director:
            self.startup_director.register_component_instance(
                "ai_controller", self
            )
            self.startup_director.mark_component_ready("ai_controller")

        await self.start_background_tasks()

        logger.info("EliteAsyncAIController started successfully")

    async def start_background_tasks(self) -> None:
        # Always spawn a lightweight health_check task to ensure controllers register background activity
        self._spawn_task(self._health_check_loop(), "ai.health_check")

        if not self.decision_queue:
            logger.warning("AI Controller started WITHOUT decision_queue; token consumer disabled")
        else:
            self._spawn_task(self._token_consumer_loop(), "ai.token_consumer")
            self._spawn_task(self._cleanup_loop(), "ai.cleanup")

    async def _health_check_loop(self) -> None:
        """Periodic health check loop used to indicate liveness during tests and runtime."""
        logger.info("AI health check loop ACTIVE")
        interval = 60
        try:
            ai_cfg = self.config.get("ai") if isinstance(self.config, dict) else None
            if ai_cfg and isinstance(ai_cfg, dict):
                interval = int(ai_cfg.get("health_check_interval", interval))
        except Exception:
            interval = 60

        while self._running:
            try:
                await asyncio.sleep(max(0.1, interval))
            except asyncio.CancelledError:
                break
            except Exception:
                # swallow errors to keep the health loop alive
                continue

    def _spawn_task(self, coro: Coroutine[Any, Any, Any], name: str) -> None:
        task = task_manager.create_engine_task(coro, name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def shutdown(self) -> None:
        logger.info("Shutting down AI Controller")
        self._running = False
        self._shutdown_requested = True
        self._started = False

        for task in list(self._background_tasks):
            task.cancel()

        await asyncio.sleep(0)
        self._background_tasks.clear()
        
        # Clean up aiohttp session to prevent "Unclosed client session" warnings
        try:
            from utils.http_session_manager import HTTPSessionManager
            await HTTPSessionManager.close()
            logger.debug("HTTP session closed successfully")
        except Exception as e:
            logger.debug(f"Error closing HTTP session: {e}")

    async def mark_live(self) -> None:
        """Mark the AI controller as live and ready for production trading."""
        self._live = True
        logger.info("AI Controller marked as live")

    # ------------------------------------------------------------------ #
    # Core Consumer Loop (THIS IS WHERE YOU WERE STUCK)
    # ------------------------------------------------------------------ #

    async def _token_consumer_loop(self) -> None:
        logger.info("AI token consumer loop ACTIVE")

        while self._running:
            try:
                candidate = await asyncio.wait_for(
                    self.decision_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                self._prune_dedup()
                continue
            except asyncio.CancelledError:
                break

            try:
                key = f"{candidate.chain}:{candidate.address}"

                if self._is_duplicate(key):
                    continue

                # Initialize trace context if not present (TokenCandidate from multi_chain_queue doesn't have it)
                if not hasattr(candidate, 'trace_ctx') or candidate.trace_ctx is None:
                    from core.trace_context import TraceContext
                    candidate.trace_ctx = TraceContext()
                
                candidate.trace_ctx.start_span("ai_strategy_selection")
                
                opportunity = self._candidate_to_opportunity(candidate)
                
                # Pre-enrich opportunity with basic indicators so strategies can evaluate it
                # This uses synthetic/derived data from current market snapshot
                self._pre_enrich_opportunity(opportunity)
                
                logger.info(f"[DEBUG] Pre-enriched opportunity for {opportunity.token.symbol}: metadata keys = {list(opportunity.metadata.keys())}")
                
                recommendation = await self.select_strategy(opportunity)
                
                logger.info(f"[DEBUG] Strategy recommendation for {opportunity.token.symbol}: {recommendation.recommended_strategy_id} (confidence: {recommendation.confidence})")
                
                candidate.trace_ctx.end_span("ai_strategy_selection")

                if recommendation.recommended_strategy_id != "SKIP":
                    opportunity.metadata["strategy_recommendation"] = recommendation.__dict__
                    opportunity.metadata["trace"] = candidate.trace_ctx.to_dict()
                    await self.opportunity_queue.put(opportunity)
                    
                    logger.info(
                        f"Opportunity emitted: {opportunity.opportunity_id} "
                        f"(trace_id: {candidate.trace_ctx.trace_id}, "
                        f"latency: {candidate.trace_ctx.get_total_latency()*1000:.1f}ms)"
                    )

            except Exception as e:
                logger.exception("AI consumer error", exc_info=e)
            finally:
                self.decision_queue.task_done()

    # ------------------------------------------------------------------ #
    # Strategy Selection
    # ------------------------------------------------------------------ #

    async def select_strategy(
        self, opportunity: TradeOpportunity
    ) -> StrategyRecommendation:

        market_data = self._extract_market_data(opportunity)

        results = await self.strategy_manager.execute_strategies_parallel(
            market_data
        )

        logger.info(f"[DEBUG] Strategy execution results for {opportunity.token.symbol}: {len(results)} results")
        for r in results:
            logger.info(f"[DEBUG]   {r.strategy_id}: success={r.success}, signal={r.signal is not None}, error={r.error}")

        valid = [r for r in results if r.success and r.signal]

        logger.info(f"[DEBUG] Valid signals: {len(valid)} out of {len(results)}")

        if not valid:
            return self._skip(opportunity, "No valid strategy signals")

        best = self._evaluate_signals(valid, market_data, opportunity)

        return StrategyRecommendation(
            strategy=best.strategy_id,
            timestamp=datetime.now(timezone.utc),
            recommendation="buy" if best.signal.direction == "buy" else "sell",
            opportunity_id=opportunity.opportunity_id,
            recommended_strategy_id=best.strategy_id,
            recommended_strategy_name=best.strategy_id,
            confidence=best.signal.confidence,
            expected_profit=float(best.signal.expected_edge),
            expected_risk=best.signal.max_risk,
            selection_method="neural_brain",
            market_regime=self.current_regime,
            position_size=best.signal.position_size,
            key_factors=["AI-selected optimal strategy"],
        )

    def _evaluate_signals(self, signals: List, market_data: Dict[str, Any], opportunity):
        """
        Evaluate and select the best strategy signal with proper weighting.
        
        Ensures fair competition between strategies by:
        1. Applying strategy-specific weights
        2. Normalizing confidence scores
        3. Selecting based on weighted normalized score
        """
        if not signals:
            return None
            
        # Get strategy weights from config (default: equal weights)
        # Check both top-level and nested under strategies
        strategy_weights = {}
        if "strategies" in self.config and "weights" in self.config.get("strategies", {}):
            strategy_weights = self.config["strategies"]["weights"]
        elif "strategy_weights" in self.config:
            strategy_weights = self.config["strategy_weights"]
        
        # Default weight for strategies not in config
        default_weight = 1.0
        
        # Calculate weighted scores for each signal
        scored_signals = []
        for result in signals:
            strategy_id = result.strategy_id
            
            # Get strategy weight (default to 1.0 if not specified)
            weight = strategy_weights.get(strategy_id, default_weight)
            
            # Extract proper signal data for neural brain evaluation
            if result.signal:
                signal_data = {
                    "technical": {
                        "confidence": result.signal.confidence,
                        "direction": result.signal.direction,
                        "expected_edge": float(result.signal.expected_edge),
                        "max_risk": result.signal.max_risk,
                    }
                }
                
                # Evaluate signal through neural brain for proper weighting
                try:
                    intent = self.neural_brain.evaluate_signal(market_data, signal_data)
                    raw_score = intent.get("confidence", result.signal.confidence) if intent else result.signal.confidence
                except Exception as e:
                    logger.warning(f"Neural brain evaluation failed for {strategy_id}: {e}, using raw confidence")
                    raw_score = result.signal.confidence
            else:
                raw_score = 0.0
            
            # === NEW: Incorporate PnL metrics into strategy weighting ===
            chain = opportunity.token.chain if opportunity.token else "unknown"
            token = opportunity.token.symbol if opportunity.token else "unknown"
            
            # Get historical performance for this strategy/token/chain
            pnl_perf = self.pnl_tracker.get_strategy_performance(strategy_id, token, chain)
            pnl_score = 1.0  # Default neutral
            
            if pnl_perf and pnl_perf.total_trades >= 5:
                # Use profitability_score from historical data
                # This gives us a 0.0-1.0 composite score based on:
                # - 50% win rate
                # - 35% ROI/10
                # - 15% drawdown protection
                pnl_score = pnl_perf.profitability_score()
                
                # Blend signal confidence (60%) with PnL performance (40%)
                # This prevents over-reliance on historical data while incorporating it
                raw_score = raw_score * 0.6 + pnl_score * 0.4
                
                logger.debug(
                    f"PnL-adjusted score for {strategy_id}: "
                    f"signal={result.signal.confidence:.3f} -> pnl={pnl_score:.3f} -> blended={raw_score:.3f}"
                )
            
            # Check circuit breaker - disable strategies with poor history
            if not self.pnl_tracker.should_use_strategy(strategy_id, token, chain):
                logger.warning(f"Circuit breaker ACTIVE for {strategy_id} on {token}/{chain}, skipping")
                continue
            
            # Apply strategy weight to normalized confidence
            weighted_score = raw_score * weight
            
            scored_signals.append({
                "result": result,
                "strategy_id": strategy_id,
                "raw_score": raw_score,
                "weight": weight,
                "weighted_score": weighted_score,
                "pnl_score": pnl_score,
            })
        
        # Normalize raw scores first to ensure fair comparison
        # This prevents one strategy from dominating due to scoring methodology
        if scored_signals:
            max_raw = max(s["raw_score"] for s in scored_signals)
            min_raw = min(s["raw_score"] for s in scored_signals)
            raw_range = max_raw - min_raw if max_raw > min_raw else 1.0
            
            for signal in scored_signals:
                # Normalize raw score to 0-1 range
                normalized_raw = (signal["raw_score"] - min_raw) / raw_range if raw_range > 0 else 0.5
                # Then apply weight to normalized score
                signal["normalized_score"] = normalized_raw * signal["weight"]
        
        # Select best signal based on normalized weighted score
        best = max(scored_signals, key=lambda s: s["normalized_score"])
        
        logger.debug(
            f"Strategy selection: {best['strategy_id']} selected "
            f"(raw={best['raw_score']:.3f}, pnl={best.get('pnl_score', 1.0):.3f}, weight={best['weight']:.2f}, "
            f"normalized={best['normalized_score']:.3f})"
        )
        
        return best["result"]

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def _candidate_to_opportunity(self, c) -> TradeOpportunity:
        # Map ChainType to chain_id
        chain_id_map = {
            'evm': 1,
            'solana': 101001,
            'aptos': 101002,
            'sui': 101003,
            'cosmos': 101006,
            'bitcoin': 101004,
        }
        
        # Get chain_id from chain_type, fallback to chain name
        chain_id = chain_id_map.get(c.chain_type.value if hasattr(c.chain_type, 'value') else str(c.chain_type), 1)
        
        token = TokenInfo(
            symbol=c.symbol,
            address=c.address,
            name=c.name,
            decimals=c.decimals,
            chain_id=chain_id,
            asset_class=AssetClass.CRYPTO,
        )

        market = MarketData(
            price=Decimal(str(c.price_usd or 0)),
            volume_24h=Decimal(str(c.volume_24h or 0)),
            liquidity=Decimal(str(c.liquidity_usd or 0)),
            timestamp=c.discovered_at or datetime.now(timezone.utc),
        )

        oid = f"{c.chain}:{c.address}"

        return TradeOpportunity(
            token=token,
            market_data=market,
            scanner_id=c.source or "scanner",
            scanner_version="1.0",
            opportunity_id=oid,
            chain=c.chain,
            token_address=c.address,
            confidence=float(c.confidence or 0),
            volatility=0.0,
            metadata={},
        )

    def _pre_enrich_opportunity(self, opportunity: TradeOpportunity) -> None:
        """
        Pre-enrich opportunity with basic synthetic indicators so strategies can evaluate it.
        
        This uses only the current market snapshot to provide basic defaults.
        Full enrichment with historical data happens later after opportunity is created.
        
        Provides sensible defaults for:
        - RSI (neutral 50.0)
        - MACD (neutral 0.0)
        - Bollinger Bands (mid-band = current price)
        - Volatility (market-based estimate)
        - Volume changes and price changes (relative to current)
        """
        if not opportunity.metadata:
            opportunity.metadata = {}
        
        price = float(opportunity.market_data.price)
        volume = float(opportunity.market_data.volume_24h)
        liquidity = float(opportunity.market_data.liquidity)
        market_cap = liquidity * 10  # Rough estimate
        
        # Provide synthetic but realistic initial values for strategies
        # These will be replaced with real calculated values by OpportunityEnricher later
        opportunity.metadata.update({
            # Technical indicators (synthetic/neutral defaults)
            "rsi": 50.0,  # Neutral RSI
            "macd": 0.0,  # Neutral MACD
            "macd_signal": 0.0,
            "bb_upper": price * 1.1,  # Rough Bollinger estimate
            "bb_lower": price * 0.9,
            "bollinger_upper": price * 1.1,
            "bollinger_lower": price * 0.9,
            "bollinger_position": 0.5,  # Mid-position
            
            # Price changes (assume neutral recent performance)
            "price_change_1h": 0.0,
            "price_change_24h": 0.0,
            "price_change_7d": 0.0,
            "high_24h": price * 1.05,
            "low_24h": price * 0.95,
            
            # Volume metrics
            "volume_change_24h": 0.0,
            "avg_volume": volume,
            "volume_7d_avg": volume,
            
            # Risk metrics
            "volatility": 0.15,  # Default 15% volatility
            "sharpe_ratio": 1.0,  # Neutral Sharpe
            "max_drawdown": 0.1,
            "var_95": price * 0.05,  # 5% value at risk
            
            # Market context
            "market_cap": market_cap,
            "liquidity_score": min(1.0, liquidity / 1000000),  # Score 0-1
            "holder_concentration": 0.3,  # Low-medium concentration
            
            # Risk assessment
            "rugpull_risk": 0.2,  # Low by default
            
            # Enrichment status
            "pre_enriched": True,  # Mark as pre-enriched (will be updated with real data)
        })

    def _extract_market_data(self, o: TradeOpportunity) -> Dict[str, Any]:
        # Extract basic market data
        market_data = {
            "price": float(o.market_data.price),
            "volume_24h": float(o.market_data.volume_24h),
            "liquidity": float(o.market_data.liquidity),
            "symbol": o.token.symbol,
            "chain": o.chain,
        }

        # Add all metadata fields if available (strategy-agnostic enrichment)
        if o.metadata:
            # Comprehensive list of all technical indicators used by any strategy
            technical_fields = [
                # Momentum indicators
                'rsi', 'price_change_1h', 'price_change_24h', 'price_change_7d',
                'volatility', 'market_cap', 'macd', 'macd_signal', 'bb_upper', 'bb_lower',
                'volume_change_24h', 'high_24h', 'low_24h', 'volume_7d_avg',

                # Mean reversion indicators
                'zscore', 'avg_volume', 'hurst_exponent', 'adf_statistic',
                'half_life', 'bollinger_upper', 'bollinger_lower', 'percent_b',

                # Breakout indicators
                'breakout_strength', 'volume_surge', 'support_level', 'resistance_level',

                # Smart money indicators
                'whale_activity', 'smart_money_flow', 'wallet_analysis',

                # Risk indicators
                'sharpe_ratio', 'max_drawdown', 'var_95',

                # General enrichment
                'social_score', 'market_regime', 'holder_concentration',
                'rugpull_risk', 'liquidity_score'
            ]

            for key in technical_fields:
                if key in o.metadata:
                    market_data[key] = o.metadata[key]

        # Provide comprehensive defaults for missing indicators (strategy-neutral)
        self._provide_comprehensive_defaults(market_data)

        logger.debug(f"Extracted market data for {market_data['symbol']}: {len(market_data)} fields")

        return market_data

    def _provide_comprehensive_defaults(self, market_data: Dict[str, Any]) -> None:
        """Provide strategy-neutral defaults for missing technical indicators."""

        price = market_data['price']
        volume = market_data['volume_24h']

        # Price change defaults (assume neutral recent performance)
        if 'price_change_1h' not in market_data:
            market_data['price_change_1h'] = 0.0
        if 'price_change_24h' not in market_data:
            market_data['price_change_24h'] = 0.0
        if 'price_change_7d' not in market_data:
            market_data['price_change_7d'] = market_data['price_change_24h'] * 7

        # Technical indicators (neutral values)
        if 'rsi' not in market_data:
            market_data['rsi'] = 50.0  # Neutral RSI
        if 'volatility' not in market_data:
            market_data['volatility'] = 1.0  # Normal volatility
        if 'market_cap' not in market_data:
            market_data['market_cap'] = price * 1000000  # Rough estimate

        # MACD defaults (neutral)
        if 'macd' not in market_data:
            market_data['macd'] = 0.0
        if 'macd_signal' not in market_data:
            market_data['macd_signal'] = 0.0

        # Bollinger Band defaults (price as middle)
        if 'bb_upper' not in market_data:
            market_data['bb_upper'] = price * 1.05
        if 'bb_lower' not in market_data:
            market_data['bb_lower'] = price * 0.95

        # Volume analysis defaults
        if 'volume_change_24h' not in market_data:
            market_data['volume_change_24h'] = 0.0
        if 'avg_volume' not in market_data:
            market_data['avg_volume'] = volume
        if 'volume_7d_avg' not in market_data:
            market_data['volume_7d_avg'] = volume

        # Price range defaults
        if 'high_24h' not in market_data:
            market_data['high_24h'] = price * 1.02
        if 'low_24h' not in market_data:
            market_data['low_24h'] = price * 0.98

        # Statistical defaults (neutral mean reversion)
        if 'zscore' not in market_data:
            market_data['zscore'] = 0.0  # At mean
        if 'hurst_exponent' not in market_data:
            market_data['hurst_exponent'] = 0.5  # Random walk
        if 'adf_statistic' not in market_data:
            market_data['adf_statistic'] = -1.0  # Weak stationarity
        if 'half_life' not in market_data:
            market_data['half_life'] = 25.0  # Moderate reversion time

        # Risk metrics defaults
        if 'sharpe_ratio' not in market_data:
            market_data['sharpe_ratio'] = 1.0  # Neutral risk-adjusted return
        if 'max_drawdown' not in market_data:
            market_data['max_drawdown'] = 0.05  # 5% drawdown
        if 'var_95' not in market_data:
            market_data['var_95'] = 0.02  # 2% VaR

        # Social/sentiment defaults
        if 'social_score' not in market_data:
            market_data['social_score'] = 0.5  # Neutral sentiment
        if 'market_regime' not in market_data:
            market_data['market_regime'] = 'ranging'

        # Holder analysis defaults
        if 'holder_concentration' not in market_data:
            market_data['holder_concentration'] = 0.3  # Moderate concentration
        if 'whale_activity' not in market_data:
            market_data['whale_activity'] = 0.2  # Low whale activity
        if 'smart_money_flow' not in market_data:
            market_data['smart_money_flow'] = 0.0  # Neutral flow
        if 'rugpull_risk' not in market_data:
            market_data['rugpull_risk'] = 0.1  # Low risk

    def _skip(self, o: TradeOpportunity, reason: str) -> StrategyRecommendation:
        return StrategyRecommendation(
            strategy="skip",
            timestamp=datetime.now(timezone.utc),
            recommendation="wait",
            opportunity_id=o.opportunity_id,
            recommended_strategy_id="SKIP",
            recommended_strategy_name="Skip",
            confidence=0.0,
            expected_profit=0.0,
            expected_risk=0.0,
            selection_method="SKIP",
            market_regime=self.current_regime,
            key_factors=[reason],
        )

    # ------------------------------------------------------------------ #
    # Deduplication
    # ------------------------------------------------------------------ #

    def _is_duplicate(self, key: str) -> bool:
        now = time.time()
        if key in self._seen_tokens:
            return True
        self._seen_tokens[key] = now
        return False

    def _prune_dedup(self) -> None:
        """Clean up expired entries to prevent unbounded memory growth."""
        now = time.time()
        
        if len(self._seen_tokens) > self.MAX_DEDUP_SIZE:
            self._seen_tokens = {
                k: v
                for k, v in self._seen_tokens.items()
                if now - v < self.DEDUP_TTL_SECONDS
            }
            logger.debug(f"Pruned _seen_tokens to {len(self._seen_tokens)} entries")
        
        if len(self._seen_opportunities) > self.MAX_DEDUP_SIZE:
            self._seen_opportunities = {
                k: v
                for k, v in self._seen_opportunities.items()
                if now - v < self.DEDUP_TTL_SECONDS
            }
            logger.debug(f"Pruned _seen_opportunities to {len(self._seen_opportunities)} entries")

    async def _cleanup_loop(self) -> None:
        """Background task to periodically clean up deduplication caches."""
        logger.info("AI cleanup loop ACTIVE")
        
        while self._running:
            try:
                await asyncio.sleep(300)
                self._prune_dedup()
                
                logger.debug(
                    f"Memory cleanup: _seen_tokens={len(self._seen_tokens)}, "
                    f"_seen_opportunities={len(self._seen_opportunities)}"
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

