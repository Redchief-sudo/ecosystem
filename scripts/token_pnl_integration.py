#!/usr/bin/env python3
"""
Token Memory + PnL Integration Script
======================================

Combines:
1. 252 tokens in memory (token characteristics, risk, momentum)
2. PnL tracker (historical strategy performance)
3. AI controller (strategy recommendations)

To create an intelligent token-strategy matching system.

Usage:
    python scripts/token_pnl_integration.py
    python scripts/token_pnl_integration.py --analyze
    python scripts/token_pnl_integration.py --watch PEPE ethereum
    python scripts/token_pnl_integration.py --report
"""

import sys
import logging
import argparse
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)


def load_modules():
    """Load required modules."""
    try:
        from utils.memory import MemoryManager
        from trading.pnl_tracker import PnLTracker
        from trading.token_memory_analyzer import TokenMemoryAnalyzer
        return MemoryManager, PnLTracker, TokenMemoryAnalyzer
    except ImportError as e:
        log.error(f"Failed to load modules: {e}")
        return None, None, None


def analyze_tokens(memory_manager, pnl_tracker):
    """Analyze all 252 tokens in memory."""
    log.info("=" * 80)
    log.info("ANALYZING 252 TOKENS IN MEMORY")
    log.info("=" * 80)
    
    try:
        from trading.token_memory_analyzer import TokenMemoryAnalyzer
        
        analyzer = TokenMemoryAnalyzer(
            memory_manager=memory_manager,
            pnl_tracker=pnl_tracker
        )
        
        # Analyze all tokens
        analyzed, stats = analyzer.analyze_all_tokens()
        
        log.info(f"\n✓ Analyzed {analyzed} tokens")
        analyzer.print_portfolio_summary()
        
        # Show top opportunities by strategy
        log.info("\n" + "=" * 80)
        log.info("TOP OPPORTUNITIES BY STRATEGY")
        log.info("=" * 80)
        
        for strategy in ["momentum", "mean_reversion", "arbitrage", "range_trading"]:
            tier1_tokens = analyzer.get_tokens_for_strategy(strategy, tier="TIER_1")
            if tier1_tokens:
                log.info(f"\n{strategy.upper()} (TIER_1 - Safe):")
                for token in tier1_tokens[:5]:
                    log.info(
                        f"  {token.symbol}/{token.chain}: "
                        f"risk={token.risk_score:.2f}, "
                        f"confidence={token.confidence:.2f}, "
                        f"momentum_24h={token.momentum_24h:.2f}"
                    )
            
            tier2_tokens = analyzer.get_tokens_for_strategy(strategy, tier="TIER_2")
            if tier2_tokens:
                log.info(f"\n{strategy.upper()} (TIER_2 - Moderate):")
                for token in tier2_tokens[:5]:
                    log.info(
                        f"  {token.symbol}/{token.chain}: "
                        f"risk={token.risk_score:.2f}, "
                        f"confidence={token.confidence:.2f}"
                    )
        
        return analyzer
        
    except Exception as e:
        log.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def show_strategy_recommendations(analyzer):
    """Show which strategies perform best on which tokens."""
    log.info("\n" + "=" * 80)
    log.info("STRATEGY PERFORMANCE vs TOKEN CHARACTERISTICS")
    log.info("=" * 80)
    
    try:
        from trading.token_memory_analyzer import TokenMemoryAnalyzer
        
        # Group tokens by lifecycle
        new_tokens = [t for t in analyzer.token_analyses.values() if t.is_new]
        emerging_tokens = [t for t in analyzer.token_analyses.values() if t.is_emerging]
        mature_tokens = [t for t in analyzer.token_analyses.values() if t.is_mature]
        
        if new_tokens:
            log.info(f"\n🆕 NEW TOKENS (<24h): {len(new_tokens)} tokens")
            for strategy in ["momentum", "arbitrage", "pump_tracker"]:
                count = sum(1 for t in new_tokens if strategy in t.recommended_strategies)
                log.info(f"  - {strategy}: {count} tokens")
        
        if emerging_tokens:
            log.info(f"\n📈 EMERGING TOKENS (1-7d): {len(emerging_tokens)} tokens")
            for strategy in ["momentum", "mean_reversion", "arbitrage"]:
                count = sum(1 for t in emerging_tokens if strategy in t.recommended_strategies)
                log.info(f"  - {strategy}: {count} tokens")
        
        if mature_tokens:
            log.info(f"\n✓ MATURE TOKENS (>7d): {len(mature_tokens)} tokens")
            for strategy in ["yield_farming", "range_trading", "mean_reversion"]:
                count = sum(1 for t in mature_tokens if strategy in t.recommended_strategies)
                log.info(f"  - {strategy}: {count} tokens")
        
        # High-confidence opportunities
        high_confidence = [
            t for t in analyzer.token_analyses.values() 
            if t.confidence > 0.7 and t.risk_score < 0.3
        ]
        if high_confidence:
            log.info(f"\n🎯 HIGH CONFIDENCE OPPORTUNITIES ({len(high_confidence)} tokens):")
            for token in sorted(high_confidence, key=lambda x: x.confidence, reverse=True)[:10]:
                log.info(
                    f"  {token.symbol}/{token.chain}: "
                    f"strategies={token.recommended_strategies}, "
                    f"confidence={token.confidence:.2f}"
                )
        
    except Exception as e:
        log.error(f"Strategy recommendation failed: {e}")


def add_to_watchlist(memory_manager, pnl_tracker, token_symbol, chain):
    """Add a token to watchlist."""
    log.info(f"Adding {token_symbol}/{chain} to watchlist...")
    
    try:
        from trading.token_memory_analyzer import TokenMemoryAnalyzer
        
        analyzer = TokenMemoryAnalyzer(
            memory_manager=memory_manager,
            pnl_tracker=pnl_tracker
        )
        
        # Analyze to populate data
        analyzer.analyze_all_tokens()
        
        # Find token
        found_token = None
        for addr, analysis in analyzer.token_analyses.items():
            if (analysis.symbol.upper() == token_symbol.upper() and 
                analysis.chain.lower() == chain.lower()):
                found_token = addr
                break
        
        if found_token:
            analyzer.add_to_watchlist(
                found_token,
                reason=f"User added to watchlist"
            )
            log.info(f"✓ Added {token_symbol}/{chain} to watchlist")
        else:
            log.warning(f"Token {token_symbol}/{chain} not found in memory")
        
    except Exception as e:
        log.error(f"Failed to add to watchlist: {e}")


def generate_report(memory_manager, pnl_tracker):
    """Generate comprehensive report."""
    log.info("=" * 80)
    log.info("COMPREHENSIVE TOKEN + PNL REPORT")
    log.info("=" * 80)
    
    try:
        from trading.token_memory_analyzer import TokenMemoryAnalyzer
        
        # Analyze tokens
        analyzer = TokenMemoryAnalyzer(
            memory_manager=memory_manager,
            pnl_tracker=pnl_tracker
        )
        analyzed, stats = analyzer.analyze_all_tokens()
        
        # PnL summary
        if pnl_tracker:
            log.info("\n" + "=" * 80)
            log.info("PnL PERFORMANCE SUMMARY")
            log.info("=" * 80)
            pnl_tracker.print_performance_summary()
        
        # Token analysis
        analyzer.print_portfolio_summary()
        
        # Integration insights
        log.info("\n" + "=" * 80)
        log.info("INTEGRATION INSIGHTS")
        log.info("=" * 80)
        
        # Find best performing token-strategy combinations
        if pnl_tracker:
            best_combos = {}
            for token_addr, analysis in analyzer.token_analyses.items():
                for strategy in analysis.recommended_strategies:
                    perf = pnl_tracker.get_strategy_performance(
                        strategy, analysis.symbol, analysis.chain
                    )
                    if perf and perf.total_trades >= 5:
                        score = perf.profitability_score()
                        key = f"{strategy}/{analysis.symbol}/{analysis.chain}"
                        best_combos[key] = {
                            'score': score,
                            'trades': perf.total_trades,
                            'win_rate': perf.win_rate
                        }
            
            if best_combos:
                sorted_combos = sorted(
                    best_combos.items(),
                    key=lambda x: x[1]['score'],
                    reverse=True
                )
                log.info("\nBest Performing Combinations:")
                for combo, data in sorted_combos[:10]:
                    log.info(
                        f"  {combo}: "
                        f"score={data['score']:.2f}, "
                        f"trades={data['trades']}, "
                        f"win_rate={data['win_rate']:.1%}"
                    )
        
        log.info("\n" + "=" * 80)
        log.info("✓ Report generation complete")
        
    except Exception as e:
        log.error(f"Report generation failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Token Memory + PnL Integration Tool"
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Analyze all 252 tokens in memory'
    )
    parser.add_argument(
        '--watch',
        nargs=2,
        metavar=('SYMBOL', 'CHAIN'),
        help='Add token to watchlist (e.g., PEPE ethereum)'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate comprehensive report'
    )
    
    args = parser.parse_args()
    
    # Load modules
    MemoryManager, PnLTracker, TokenMemoryAnalyzer = load_modules()
    if not all([MemoryManager, PnLTracker, TokenMemoryAnalyzer]):
        return 1
    
    # Initialize
    memory_manager = MemoryManager()
    pnl_tracker = PnLTracker(data_dir=Path("data"))
    
    # Execute commands
    if args.analyze:
        analyze_tokens(memory_manager, pnl_tracker)
        show_strategy_recommendations(None)  # Will be populated in analyze
        return 0
    
    elif args.watch:
        symbol, chain = args.watch
        add_to_watchlist(memory_manager, pnl_tracker, symbol, chain)
        return 0
    
    elif args.report:
        generate_report(memory_manager, pnl_tracker)
        return 0
    
    else:
        # Default: show quick analysis
        log.info("Token Memory + PnL Integration Tool")
        log.info("-" * 80)
        log.info("Usage:")
        log.info("  python scripts/token_pnl_integration.py --analyze")
        log.info("  python scripts/token_pnl_integration.py --report")
        log.info("  python scripts/token_pnl_integration.py --watch PEPE ethereum")
        log.info("-" * 80)
        
        # Quick memory check
        tokens = memory_manager.tokens if hasattr(memory_manager, 'tokens') else {}
        log.info(f"✓ Found {len(tokens)} tokens in memory")
        
        return 0


if __name__ == "__main__":
    sys.exit(main())
