"""
Token Memory Analyzer
====================

Analyzes the 252 tokens in memory to extract actionable insights and patterns.

Features:
- Categorize tokens by risk/volatility/momentum
- Track token age and lifecycle
- Identify emerging vs. mature tokens
- Detect pump signals and risk patterns
- Build token watchlists
- Generate trading strategy recommendations per token
"""

import logging
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
import statistics

logger = logging.getLogger(__name__)


@dataclass
class TokenAnalysis:
    """Complete analysis of a single token."""
    address: str
    symbol: str
    chain: str
    
    # Lifecycle metrics
    age_hours: float = 0.0
    is_new: bool = False  # < 24 hours
    is_emerging: bool = False  # 1-7 days
    is_mature: bool = False  # > 7 days
    
    # Market metrics
    price: float = 0.0
    volume_24h: float = 0.0
    liquidity: float = 0.0
    market_cap: Optional[float] = None
    
    # Risk assessment
    risk_score: float = 0.5  # 0.0 (safe) to 1.0 (risky)
    volatility_score: float = 0.5
    pump_risk: float = 0.0
    rugpull_risk: float = 0.0
    
    # Momentum indicators
    momentum_5m: float = 0.0
    momentum_1h: float = 0.0
    momentum_24h: float = 0.0
    
    # Recommendations
    trading_tier: str = "UNRANKED"  # TIER_1, TIER_2, TIER_3, UNRANKED
    confidence: float = 0.0
    recommended_strategies: List[str] = field(default_factory=list)
    
    # Watchlist status
    is_watchlisted: bool = False
    watch_reason: str = ""
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    last_analyzed: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging/storage."""
        return {
            'address': self.address,
            'symbol': self.symbol,
            'chain': self.chain,
            'age_hours': self.age_hours,
            'is_new': self.is_new,
            'is_emerging': self.is_emerging,
            'is_mature': self.is_mature,
            'price': self.price,
            'volume_24h': self.volume_24h,
            'liquidity': self.liquidity,
            'market_cap': self.market_cap,
            'risk_score': self.risk_score,
            'volatility_score': self.volatility_score,
            'pump_risk': self.pump_risk,
            'rugpull_risk': self.rugpull_risk,
            'momentum_5m': self.momentum_5m,
            'momentum_1h': self.momentum_1h,
            'momentum_24h': self.momentum_24h,
            'trading_tier': self.trading_tier,
            'confidence': self.confidence,
            'recommended_strategies': self.recommended_strategies,
            'is_watchlisted': self.is_watchlisted,
            'watch_reason': self.watch_reason,
            'tags': self.tags,
            'last_analyzed': self.last_analyzed,
        }


@dataclass
class TokenPortfolioStats:
    """Statistics across the entire token portfolio."""
    total_tokens: int = 0
    new_tokens: int = 0
    emerging_tokens: int = 0
    mature_tokens: int = 0
    
    tier_1_count: int = 0
    tier_2_count: int = 0
    tier_3_count: int = 0
    
    avg_risk_score: float = 0.0
    avg_volatility: float = 0.0
    avg_confidence: float = 0.0
    
    total_volume: float = 0.0
    total_liquidity: float = 0.0
    
    high_momentum_tokens: List[str] = field(default_factory=list)
    high_risk_tokens: List[str] = field(default_factory=list)
    watchlist_count: int = 0
    
    strategy_distribution: Dict[str, int] = field(default_factory=dict)


class TokenMemoryAnalyzer:
    """
    Analyzes 252 tokens in memory to extract insights and guide trading decisions.
    
    Integrates with PnL system to learn which tokens/strategies work best.
    """
    
    def __init__(self, memory_manager=None, pnl_tracker=None):
        """
        Initialize analyzer.
        
        Args:
            memory_manager: Access to 252 tokens in memory
            pnl_tracker: PnL tracker to learn from historical trades
        """
        self.memory = memory_manager
        self.pnl_tracker = pnl_tracker
        
        self.token_analyses: Dict[str, TokenAnalysis] = {}
        self.watchlist: Set[str] = set()
        self.tier_1_tokens: List[str] = []
        self.tier_2_tokens: List[str] = []
        self.tier_3_tokens: List[str] = []
        
        self.last_analysis_time = 0.0
        self.analysis_cache_ttl = 300.0  # 5 minutes
        
        logger.info("TokenMemoryAnalyzer initialized")
    
    def analyze_all_tokens(self) -> Tuple[int, TokenPortfolioStats]:
        """
        Analyze all 252 tokens in memory.
        
        Returns:
            Tuple of (tokens_analyzed, portfolio_stats)
        """
        if not self.memory:
            logger.warning("No memory manager provided")
            return 0, TokenPortfolioStats()
        
        start_time = time.time()
        
        try:
            # Get all tokens from memory
            tokens = self.memory.tokens if hasattr(self.memory, 'tokens') else {}
            analyzed = 0
            
            for token_addr, token_meta in tokens.items():
                try:
                    analysis = self._analyze_token(token_addr, token_meta)
                    self.token_analyses[token_addr] = analysis
                    analyzed += 1
                except Exception as e:
                    logger.error(f"Failed to analyze token {token_addr}: {e}")
            
            # Tier tokens based on analysis
            self._tier_tokens()
            
            # Calculate portfolio stats
            stats = self._calculate_portfolio_stats()
            
            elapsed = time.time() - start_time
            logger.info(
                f"Analyzed {analyzed} tokens in {elapsed:.2f}s | "
                f"Tier 1: {stats.tier_1_count}, "
                f"Tier 2: {stats.tier_2_count}, "
                f"Tier 3: {stats.tier_3_count}"
            )
            
            self.last_analysis_time = time.time()
            return analyzed, stats
            
        except Exception as e:
            logger.error(f"Token analysis failed: {e}")
            return 0, TokenPortfolioStats()
    
    def _analyze_token(self, token_addr: str, token_meta) -> TokenAnalysis:
        """Analyze a single token."""
        analysis = TokenAnalysis(
            address=token_addr,
            symbol=getattr(token_meta, 'symbol', 'UNKNOWN'),
            chain=getattr(token_meta, 'chain', 'unknown'),
        )
        
        # Extract available data from token_meta
        current_time = datetime.now(timezone.utc)
        
        if hasattr(token_meta, 'created_at'):
            created_at = token_meta.created_at
            if isinstance(created_at, (int, float)):
                created_at = datetime.fromtimestamp(created_at, tz=timezone.utc)
            age_delta = current_time - created_at
            analysis.age_hours = age_delta.total_seconds() / 3600.0
        
        # Categorize by age
        if analysis.age_hours < 24:
            analysis.is_new = True
        elif analysis.age_hours < 168:  # 7 days
            analysis.is_emerging = True
        else:
            analysis.is_mature = True
        
        # Extract market metrics
        analysis.price = getattr(token_meta, 'price', 0.0)
        analysis.volume_24h = getattr(token_meta, 'volume_24h', 0.0)
        analysis.liquidity = getattr(token_meta, 'liquidity', 0.0)
        analysis.market_cap = getattr(token_meta, 'market_cap', None)
        
        # Extract momentum
        momentum = getattr(token_meta, 'momentum', {})
        if isinstance(momentum, dict):
            analysis.momentum_5m = momentum.get('5m', 0.0)
            analysis.momentum_1h = momentum.get('1h', 0.0)
            analysis.momentum_24h = momentum.get('24h', 0.0)
        
        # Extract risk metrics
        analysis.pump_risk = getattr(token_meta, 'pump_risk', 0.0)
        analysis.rugpull_risk = getattr(token_meta, 'rugpull_risk', 0.0)
        analysis.volatility_score = getattr(token_meta, 'volatility', 0.5)
        
        # Calculate composite risk score
        analysis.risk_score = (
            analysis.pump_risk * 0.4 +
            analysis.rugpull_risk * 0.4 +
            analysis.volatility_score * 0.2
        )
        
        # Recommend strategies based on token characteristics
        analysis.recommended_strategies = self._recommend_strategies(analysis)
        
        # Extract tags
        analysis.tags = getattr(token_meta, 'tags', [])
        if isinstance(analysis.tags, str):
            analysis.tags = [analysis.tags]
        
        # Calculate confidence from PnL if available
        if self.pnl_tracker:
            analysis.confidence = self._calculate_confidence(analysis)
        
        analysis.last_analyzed = datetime.now(timezone.utc).isoformat()
        
        return analysis
    
    def _recommend_strategies(self, analysis: TokenAnalysis) -> List[str]:
        """Recommend trading strategies based on token analysis."""
        strategies = []
        
        # Momentum strategy for volatile, high-volume tokens
        if analysis.momentum_5m > 0.05 and analysis.volume_24h > 50000:
            strategies.append("momentum")
        
        # Mean reversion for high volatility
        if analysis.volatility_score > 0.7 and analysis.liquidity > 100000:
            strategies.append("mean_reversion")
        
        # Arbitrage for emerging tokens
        if analysis.is_emerging and analysis.liquidity > 50000:
            strategies.append("arbitrage")
        
        # Yield farming for stable, high-liquidity tokens
        if analysis.is_mature and analysis.liquidity > 500000 and analysis.risk_score < 0.3:
            strategies.append("yield_farming")
        
        # Low-volatility strategy for stable tokens
        if analysis.volatility_score < 0.3 and analysis.liquidity > 100000:
            strategies.append("range_trading")
        
        return strategies
    
    def _calculate_confidence(self, analysis: TokenAnalysis) -> float:
        """Calculate trading confidence from PnL data and token metrics."""
        confidence = 0.5  # Base neutral
        
        # Boost for tokens with good strategy history
        for strategy in analysis.recommended_strategies:
            perf = self.pnl_tracker.get_strategy_performance(
                strategy, analysis.symbol, analysis.chain
            )
            if perf and perf.total_trades >= 5:
                boost = perf.profitability_score() * 0.1
                confidence += boost
        
        # Reduce confidence for high-risk tokens
        if analysis.risk_score > 0.7:
            confidence *= 0.5
        
        return min(1.0, max(0.0, confidence))
    
    def _tier_tokens(self) -> None:
        """Tier tokens into TIER_1, TIER_2, TIER_3 based on analysis."""
        self.tier_1_tokens = []
        self.tier_2_tokens = []
        self.tier_3_tokens = []
        
        for addr, analysis in self.token_analyses.items():
            # TIER_1: Mature, low-risk, high-confidence
            if (analysis.is_mature and 
                analysis.risk_score < 0.3 and 
                analysis.confidence > 0.7):
                analysis.trading_tier = "TIER_1"
                self.tier_1_tokens.append(addr)
            
            # TIER_2: Emerging or moderate-risk, decent confidence
            elif (analysis.confidence > 0.5 and 
                  analysis.risk_score < 0.6):
                analysis.trading_tier = "TIER_2"
                self.tier_2_tokens.append(addr)
            
            # TIER_3: High-risk, low-confidence (speculative)
            elif analysis.confidence > 0.3:
                analysis.trading_tier = "TIER_3"
                self.tier_3_tokens.append(addr)
            
            else:
                analysis.trading_tier = "UNRANKED"
    
    def _calculate_portfolio_stats(self) -> TokenPortfolioStats:
        """Calculate aggregated portfolio statistics."""
        stats = TokenPortfolioStats(
            total_tokens=len(self.token_analyses)
        )
        
        if not self.token_analyses:
            return stats
        
        # Count by category
        risk_scores = []
        volatilities = []
        confidences = []
        
        for analysis in self.token_analyses.values():
            if analysis.is_new:
                stats.new_tokens += 1
            elif analysis.is_emerging:
                stats.emerging_tokens += 1
            elif analysis.is_mature:
                stats.mature_tokens += 1
            
            if analysis.trading_tier == "TIER_1":
                stats.tier_1_count += 1
            elif analysis.trading_tier == "TIER_2":
                stats.tier_2_count += 1
            elif analysis.trading_tier == "TIER_3":
                stats.tier_3_count += 1
            
            risk_scores.append(analysis.risk_score)
            volatilities.append(analysis.volatility_score)
            confidences.append(analysis.confidence)
            
            stats.total_volume += analysis.volume_24h
            stats.total_liquidity += analysis.liquidity
            
            # High momentum tokens
            if analysis.momentum_24h > 0.1:
                stats.high_momentum_tokens.append(f"{analysis.symbol}/{analysis.chain}")
            
            # High risk tokens
            if analysis.risk_score > 0.7:
                stats.high_risk_tokens.append(f"{analysis.symbol}/{analysis.chain}")
            
            # Strategy distribution
            for strategy in analysis.recommended_strategies:
                stats.strategy_distribution[strategy] = (
                    stats.strategy_distribution.get(strategy, 0) + 1
                )
        
        # Calculate averages
        if risk_scores:
            stats.avg_risk_score = statistics.mean(risk_scores)
        if volatilities:
            stats.avg_volatility = statistics.mean(volatilities)
        if confidences:
            stats.avg_confidence = statistics.mean(confidences)
        
        stats.watchlist_count = len(self.watchlist)
        
        return stats
    
    def get_tokens_for_strategy(self, strategy: str, tier: Optional[str] = None) -> List[TokenAnalysis]:
        """
        Get tokens recommended for a specific strategy.
        
        Args:
            strategy: Strategy name (momentum, mean_reversion, etc.)
            tier: Optional tier filter (TIER_1, TIER_2, TIER_3)
            
        Returns:
            List of TokenAnalysis objects
        """
        candidates = []
        
        for addr, analysis in self.token_analyses.items():
            if strategy in analysis.recommended_strategies:
                if tier is None or analysis.trading_tier == tier:
                    candidates.append(analysis)
        
        # Sort by confidence
        return sorted(candidates, key=lambda x: x.confidence, reverse=True)
    
    def get_watchlist_tokens(self) -> List[TokenAnalysis]:
        """Get all tokens on watchlist."""
        return [
            self.token_analyses[addr] 
            for addr in self.watchlist 
            if addr in self.token_analyses
        ]
    
    def add_to_watchlist(self, token_addr: str, reason: str = "") -> None:
        """Add token to watchlist."""
        self.watchlist.add(token_addr)
        if token_addr in self.token_analyses:
            self.token_analyses[token_addr].is_watchlisted = True
            self.token_analyses[token_addr].watch_reason = reason
        logger.info(f"Added {token_addr} to watchlist: {reason}")
    
    def remove_from_watchlist(self, token_addr: str) -> None:
        """Remove token from watchlist."""
        self.watchlist.discard(token_addr)
        if token_addr in self.token_analyses:
            self.token_analyses[token_addr].is_watchlisted = False
        logger.info(f"Removed {token_addr} from watchlist")
    
    def print_portfolio_summary(self) -> None:
        """Print human-readable portfolio summary."""
        logger.info("=" * 80)
        logger.info("TOKEN MEMORY PORTFOLIO SUMMARY (252 Tokens)")
        logger.info("=" * 80)
        
        stats = self._calculate_portfolio_stats()
        
        logger.info(f"Total Tokens: {stats.total_tokens}")
        logger.info(f"  New (< 24h): {stats.new_tokens}")
        logger.info(f"  Emerging (1-7d): {stats.emerging_tokens}")
        logger.info(f"  Mature (> 7d): {stats.mature_tokens}")
        
        logger.info("")
        logger.info(f"Trading Tiers:")
        logger.info(f"  TIER_1 (Safe): {stats.tier_1_count}")
        logger.info(f"  TIER_2 (Moderate): {stats.tier_2_count}")
        logger.info(f"  TIER_3 (Speculative): {stats.tier_3_count}")
        
        logger.info("")
        logger.info(f"Portfolio Metrics:")
        logger.info(f"  Avg Risk Score: {stats.avg_risk_score:.2f}")
        logger.info(f"  Avg Volatility: {stats.avg_volatility:.2f}")
        logger.info(f"  Avg Confidence: {stats.avg_confidence:.2f}")
        logger.info(f"  Total Volume 24h: ${stats.total_volume:,.0f}")
        logger.info(f"  Total Liquidity: ${stats.total_liquidity:,.0f}")
        
        logger.info("")
        if stats.high_momentum_tokens:
            logger.info(f"High Momentum Tokens ({len(stats.high_momentum_tokens)}):")
            for token in stats.high_momentum_tokens[:10]:
                logger.info(f"  - {token}")
        
        if stats.high_risk_tokens:
            logger.info(f"High Risk Tokens ({len(stats.high_risk_tokens)}):")
            for token in stats.high_risk_tokens[:10]:
                logger.info(f"  - {token}")
        
        if stats.strategy_distribution:
            logger.info(f"Recommended Strategies:")
            for strategy, count in sorted(stats.strategy_distribution.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {strategy}: {count} tokens")
        
        logger.info("=" * 80)
