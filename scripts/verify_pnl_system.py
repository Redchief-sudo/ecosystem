#!/usr/bin/env python3
"""
PnL System Verification Script
==============================

Verifies that the PnL tracking system is properly integrated and working.

Usage:
    python scripts/verify_pnl_system.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

def verify_imports():
    """Check that all PnL modules can be imported."""
    log.info("=" * 80)
    log.info("VERIFYING PnL SYSTEM IMPORTS")
    log.info("=" * 80)
    
    try:
        from trading.pnl_models import TradePnL, StrategyPerformance
        log.info("✓ trading.pnl_models imported successfully")
    except ImportError as e:
        log.error(f"✗ Failed to import pnl_models: {e}")
        return False
    
    try:
        from trading.pnl_tracker import PnLTracker
        log.info("✓ trading.pnl_tracker imported successfully")
    except ImportError as e:
        log.error(f"✗ Failed to import pnl_tracker: {e}")
        return False
    
    log.info("✓ All PnL imports successful\n")
    return True

def verify_pnl_tracker():
    """Test PnL tracker initialization and basic operations."""
    log.info("=" * 80)
    log.info("VERIFYING PnL TRACKER INITIALIZATION")
    log.info("=" * 80)
    
    try:
        from trading.pnl_tracker import PnLTracker
        from trading.pnl_models import TradePnL
        
        tracker = PnLTracker(data_dir=Path("data"))
        log.info("✓ PnLTracker initialized successfully")
        
        # Test entering a trade
        trade = TradePnL(
            token="TEST",
            chain="ethereum",
            strategy="test",
            entry_price=100.0,
            exit_price=None,
            size=10.0,
            fees=0.1,
            realized=False
        )
        
        tracker.enter_trade("test_trade_1", trade)
        log.info("✓ Trade entry recorded successfully")
        
        # Verify trade is in open trades
        if "test_trade_1" in tracker.open_trades:
            log.info("✓ Trade found in open_trades")
        else:
            log.error("✗ Trade not found in open_trades")
            return False
        
        # Test closing a trade
        closed_trade = tracker.close_trade("test_trade_1", 110.0)
        if closed_trade:
            log.info(f"✓ Trade closed successfully - PnL: ${closed_trade.pnl():.2f}")
        else:
            log.error("✗ Failed to close trade")
            return False
        
        # Verify CSV was created
        pnl_file = Path("data/pnl_history.csv")
        if pnl_file.exists():
            log.info(f"✓ PnL history CSV created: {pnl_file}")
        else:
            log.warning(f"⚠ PnL history CSV not found: {pnl_file}")
        
        # Test performance metrics
        perf = tracker.get_strategy_performance("test", "TEST", "ethereum")
        if perf:
            log.info(f"✓ Performance metrics retrieved:")
            log.info(f"  - Total trades: {perf.total_trades}")
            log.info(f"  - Winning trades: {perf.winning_trades}")
            log.info(f"  - Total PnL: ${perf.total_pnl:.2f}")
            log.info(f"  - Profitability score: {perf.profitability_score():.2f}")
        else:
            log.error("✗ Could not retrieve performance metrics")
            return False
        
        log.info("✓ PnL Tracker verification passed\n")
        return True
        
    except Exception as e:
        log.error(f"✗ PnL Tracker verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_ai_controller_integration():
    """Verify PnL tracker is integrated in AI controller."""
    log.info("=" * 80)
    log.info("VERIFYING AI CONTROLLER INTEGRATION")
    log.info("=" * 80)
    
    try:
        from ai.elite_async_ai_controller import EliteAsyncAIController
        import inspect
        
        # Check if __init__ mentions pnl_tracker
        source = inspect.getsource(EliteAsyncAIController.__init__)
        if "pnl_tracker" in source:
            log.info("✓ AI Controller has pnl_tracker initialization")
        else:
            log.warning("⚠ AI Controller __init__ doesn't mention pnl_tracker")
            return False
        
        # Check if PnL imports are present
        source = inspect.getsource(EliteAsyncAIController)
        if "pnl_tracker" in source and "get_strategy_performance" in source:
            log.info("✓ AI Controller uses PnL tracker for strategy scoring")
        else:
            log.warning("⚠ AI Controller doesn't use PnL tracker in strategy scoring")
        
        log.info("✓ AI Controller integration verified\n")
        return True
        
    except Exception as e:
        log.error(f"✗ AI Controller integration verification failed: {e}")
        return False

def verify_main_integration():
    """Verify PnL tracker is integrated in main.py."""
    log.info("=" * 80)
    log.info("VERIFYING MAIN.PY INTEGRATION")
    log.info("=" * 80)
    
    try:
        with open("main.py", "r") as f:
            source = f.read()
        
        checks = {
            "PnL imports": "from trading.pnl_tracker import PnLTracker",
            "PnLTracker initialization": "pnl_tracker = PnLTracker",
            "Component registration": "composition.components['pnl_tracker']",
            "Trade entry recording": "pnl_tracker.enter_trade"
        }
        
        all_passed = True
        for check_name, check_string in checks.items():
            if check_string in source:
                log.info(f"✓ {check_name} found in main.py")
            else:
                log.error(f"✗ {check_name} NOT found in main.py")
                all_passed = False
        
        if all_passed:
            log.info("✓ Main integration verification passed\n")
        
        return all_passed
        
    except Exception as e:
        log.error(f"✗ Main integration verification failed: {e}")
        return False

def verify_file_structure():
    """Verify all required files exist."""
    log.info("=" * 80)
    log.info("VERIFYING FILE STRUCTURE")
    log.info("=" * 80)
    
    required_files = {
        "trading/pnl_models.py": "PnL data models",
        "trading/pnl_tracker.py": "PnL tracking system",
        "PNL_TRACKING_GUIDE.md": "User documentation",
        "PNL_IMPLEMENTATION_CHECKLIST.md": "Implementation checklist",
    }
    
    all_exist = True
    for file_path, description in required_files.items():
        if Path(file_path).exists():
            log.info(f"✓ {file_path}: {description}")
        else:
            log.error(f"✗ {file_path}: {description} - NOT FOUND")
            all_exist = False
    
    if all_exist:
        log.info("✓ File structure verification passed\n")
    
    return all_exist

def print_summary(results):
    """Print final summary."""
    log.info("=" * 80)
    log.info("VERIFICATION SUMMARY")
    log.info("=" * 80)
    
    total = len(results)
    passed = sum(results.values())
    failed = total - passed
    
    for check, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        log.info(f"{status}: {check}")
    
    log.info("-" * 80)
    
    if failed == 0:
        log.info(f"✓ ALL CHECKS PASSED ({passed}/{total})")
        log.info("")
        log.info("Next steps:")
        log.info("1. Run your trading system with paper trading enabled")
        log.info("2. Execute some trades to populate data/pnl_history.csv")
        log.info("3. Check PnL performance: pnl_tracker.print_performance_summary()")
        log.info("4. Implement exit hook to auto-close trades (see checklist)")
        return 0
    else:
        log.error(f"✗ {failed} CHECK(S) FAILED ({passed}/{total} passed)")
        log.error("")
        log.error("Issues found. Please review the errors above.")
        return 1

def main():
    """Run all verification checks."""
    results = {}
    
    results["Imports"] = verify_imports()
    results["PnL Tracker"] = verify_pnl_tracker()
    results["AI Controller Integration"] = verify_ai_controller_integration()
    results["Main.py Integration"] = verify_main_integration()
    results["File Structure"] = verify_file_structure()
    
    return print_summary(results)

if __name__ == "__main__":
    sys.exit(main())
