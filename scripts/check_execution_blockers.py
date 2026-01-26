#!/usr/bin/env python3
"""
Execution Blocker Checker
=========================
Checks for anything that would prevent trades from executing.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_trading_mode():
    """Check trading mode configuration."""
    print("=" * 80)
    print("TRADING MODE CHECK")
    print("=" * 80)
    
    try:
        from config import load_config
        config = load_config()
        
        trading_config = config.get("trading", {})
        mode = trading_config.get("mode", "paper")
        paper_trading = trading_config.get("paper_trading", True)
        
        print(f"\nTrading Mode: {mode}")
        print(f"Paper Trading: {paper_trading}")
        
        if mode == "live" and not paper_trading:
            private_key = trading_config.get("private_key")
            if not private_key:
                print("❌ CRITICAL: Live trading mode but no private key configured!")
                return False
            else:
                print("✅ Private key configured for live trading")
        else:
            print("✅ Paper trading mode - no private key needed")
        
        return True
    except Exception as e:
        print(f"❌ Error checking trading mode: {e}")
        return False

def check_policy_thresholds():
    """Check if policy thresholds are too restrictive."""
    print("\n" + "=" * 80)
    print("POLICY THRESHOLD CHECK")
    print("=" * 80)
    
    try:
        from entry.policy import get_default_policy as get_entry_policy
        from risk.risk_policy import get_default_policy as get_risk_policy
        
        entry_policy = get_entry_policy()
        risk_policy = get_risk_policy()
        
        print(f"\nEntry Policy: {entry_policy.name}")
        print(f"  Approval threshold: {entry_policy.approval_threshold:.2%}")
        print(f"  Strong entry threshold: {entry_policy.strong_entry_threshold:.2%}")
        print(f"  Min liquidity: {getattr(entry_policy, 'min_liquidity_usd', 'N/A')}")
        
        print(f"\nRisk Policy: {risk_policy.name}")
        print(f"  Max exposure per asset: {risk_policy.max_exposure_per_asset}%")
        print(f"  Max total exposure: {risk_policy.max_total_exposure}%")
        print(f"  Max open positions: {risk_policy.max_open_positions}")
        print(f"  Max trades per day: {risk_policy.max_trades_per_day}")
        
        # Check if thresholds are reasonable
        if entry_policy.strong_entry_threshold > 0.9:
            print("⚠️  WARNING: Entry threshold very high (>90%) - may reject most opportunities")
        
        if risk_policy.max_exposure_per_asset < 0.01:
            print("⚠️  WARNING: Max exposure per asset very low (<0.01%) - may limit trading")
        
        if risk_policy.max_open_positions < 3:
            print("⚠️  WARNING: Max open positions very low (<3) - may limit trading")
        
        return True
    except Exception as e:
        print(f"❌ Error checking policies: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_execution_path():
    """Check if execution path is complete."""
    print("\n" + "=" * 80)
    print("EXECUTION PATH CHECK")
    print("=" * 80)
    
    issues = []
    
    # Check if trade_executor has execute method
    try:
        from trading.execution.trade_executor import HybridTradeExecutor
        if not hasattr(HybridTradeExecutor, 'execute'):
            issues.append("HybridTradeExecutor missing execute() method")
    except Exception as e:
        issues.append(f"Error checking HybridTradeExecutor: {e}")
    
    # Check if _execute_paper_trade exists
    try:
        executor_file = project_root / "trading" / "execution" / "trade_executor.py"
        with open(executor_file, 'r') as f:
            content = f.read()
            if "_execute_paper_trade" not in content:
                issues.append("_execute_paper_trade method not found - paper trading may not work")
    except Exception as e:
        issues.append(f"Error checking paper trade method: {e}")
    
    if issues:
        print("\n❌ ISSUES:")
        for issue in issues:
            print(f"  • {issue}")
        return False
    else:
        print("\n✅ Execution path appears complete")
        return True

def check_data_requirements():
    """Check if all required data is available."""
    print("\n" + "=" * 80)
    print("DATA REQUIREMENTS CHECK")
    print("=" * 80)
    
    issues = []
    
    # Check entry manager requirements
    try:
        from entry.entry import EntryManager
        from entry.policy import get_default_policy
        
        entry_manager = EntryManager({}, get_default_policy())
        
        # Check min_liquidity and min_volume
        min_liquidity = entry_manager.min_liquidity
        min_volume = entry_manager.min_volume
        
        print(f"\nEntry Manager Requirements:")
        print(f"  Min liquidity: ${min_liquidity:,.0f}")
        print(f"  Min volume: ${min_volume:,.0f}")
        
        if min_liquidity > 50000:
            issues.append(f"Min liquidity very high (${min_liquidity:,.0f}) - may reject many opportunities")
        
        if min_volume > 10000:
            issues.append(f"Min volume very high (${min_volume:,.0f}) - may reject many opportunities")
        
    except Exception as e:
        issues.append(f"Error checking entry manager: {e}")
    
    if issues:
        print("\n⚠️  WARNINGS:")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("\n✅ Data requirements appear reasonable")
    
    return len(issues) == 0

def main():
    """Run all checks."""
    print("EXECUTION BLOCKER ANALYSIS")
    print("=" * 80)
    
    results = []
    
    results.append(("Trading Mode", check_trading_mode()))
    results.append(("Policy Thresholds", check_policy_thresholds()))
    results.append(("Execution Path", check_execution_path()))
    results.append(("Data Requirements", check_data_requirements()))
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    critical = [name for name, result in results if not result]
    if critical:
        print(f"\n❌ CRITICAL BLOCKERS ({len(critical)}):")
        for name in critical:
            print(f"  • {name}")
    else:
        print("\n✅ No critical blockers found")
    
    print("\n" + "=" * 80)
    
    return len(critical) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
