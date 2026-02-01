 #!/usr/bin/env python3
"""
Verify 252 Tokens Accessibility
=================================

Checks if the 252 tokens in memory are accessible and properly structured.
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)


def main():
    """Verify token memory setup."""
    log.info("=" * 80)
    log.info("TOKEN MEMORY VERIFICATION")
    log.info("=" * 80)
    
    # Check imports
    log.info("\n1. Checking imports...")
    try:
        from utils.memory import MemoryManager
        log.info("✓ MemoryManager imported")
    except ImportError as e:
        log.error(f"✗ Failed to import MemoryManager: {e}")
        return 1
    
    # Initialize memory
    log.info("\n2. Initializing MemoryManager...")
    try:
        memory = MemoryManager()
        log.info("✓ MemoryManager initialized")
    except Exception as e:
        log.error(f"✗ Failed to initialize MemoryManager: {e}")
        return 1
    
    # Check tokens
    log.info("\n3. Checking tokens in memory...")
    try:
        tokens = memory.tokens if hasattr(memory, 'tokens') else {}
        
        if isinstance(tokens, dict):
            log.info(f"✓ Found {len(tokens)} tokens in memory")
            
            if len(tokens) > 0:
                # Show sample token
                first_token_addr = list(tokens.keys())[0]
                first_token = tokens[first_token_addr]
                
                log.info(f"\nSample token ({first_token_addr}):")
                log.info(f"  - Symbol: {getattr(first_token, 'symbol', 'N/A')}")
                log.info(f"  - Chain: {getattr(first_token, 'chain', 'N/A')}")
                log.info(f"  - Price: ${getattr(first_token, 'price', 0):.6f}")
                log.info(f"  - Volume 24h: ${getattr(first_token, 'volume_24h', 0):,.0f}")
                log.info(f"  - Liquidity: ${getattr(first_token, 'liquidity', 0):,.0f}")
                log.info(f"  - Risk: {getattr(first_token, 'pump_risk', 0):.2f}")
                
                # Check token structure
                log.info(f"\nToken structure verification:")
                required_attrs = ['symbol', 'chain', 'price', 'volume_24h', 'liquidity']
                for attr in required_attrs:
                    has_attr = hasattr(first_token, attr)
                    status = "✓" if has_attr else "✗"
                    log.info(f"  {status} {attr}")
            else:
                log.warning("⚠ No tokens found in memory (this is OK if system is new)")
        else:
            log.error(f"✗ tokens is not a dict: {type(tokens)}")
            return 1
    
    except Exception as e:
        log.error(f"✗ Failed to check tokens: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Check database
    log.info("\n4. Checking SQLite database...")
    try:
        db_path = memory.db_path if hasattr(memory, 'db_path') else None
        if db_path:
            db_file = Path(db_path)
            if db_file.exists():
                size_mb = db_file.stat().st_size / (1024 * 1024)
                log.info(f"✓ Database exists: {db_path}")
                log.info(f"  - Size: {size_mb:.2f} MB")
            else:
                log.info(f"⚠ Database path configured but file not yet created: {db_path}")
        else:
            log.warning("⚠ No database path found")
    except Exception as e:
        log.error(f"✗ Failed to check database: {e}")
        return 1
    
    # Try to analyze
    log.info("\n5. Testing TokenMemoryAnalyzer...")
    try:
        from trading.token_memory_analyzer import TokenMemoryAnalyzer
        analyzer = TokenMemoryAnalyzer(memory_manager=memory)
        log.info("✓ TokenMemoryAnalyzer imported and initialized")
        
        if len(tokens) >= 10:  # Only analyze if we have enough tokens
            log.info("  Attempting to analyze all tokens...")
            analyzed, stats = analyzer.analyze_all_tokens()
            log.info(f"✓ Analyzed {analyzed} tokens")
            log.info(f"  - TIER_1: {stats.tier_1_count}")
            log.info(f"  - TIER_2: {stats.tier_2_count}")
            log.info(f"  - TIER_3: {stats.tier_3_count}")
        else:
            log.info("⚠ Not enough tokens to run full analysis (need 10+)")
    
    except Exception as e:
        log.error(f"✗ TokenMemoryAnalyzer failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Check PnL tracker
    log.info("\n6. Testing PnL Tracker...")
    try:
        from trading.pnl_tracker import PnLTracker
        pnl = PnLTracker(data_dir=Path("data"))
        log.info("✓ PnLTracker initialized")
        
        stats = pnl.get_all_performance_stats()
        log.info(f"✓ PnL tracker has {len(stats)} performance entries")
    
    except Exception as e:
        log.error(f"✗ PnL Tracker failed: {e}")
        return 1
    
    # Summary
    log.info("\n" + "=" * 80)
    log.info("✓ ALL CHECKS PASSED")
    log.info("=" * 80)
    log.info("\nNext steps:")
    log.info("1. Analyze tokens: python scripts/token_pnl_integration.py --analyze")
    log.info("2. Generate report: python scripts/token_pnl_integration.py --report")
    log.info("3. Add to watchlist: python scripts/token_pnl_integration.py --watch SYMBOL CHAIN")
    log.info("")
    log.info(f"You have {len(tokens)} tokens ready to analyze!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
