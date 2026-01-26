#!/usr/bin/env python3
"""
Trading Blockage Diagnostic
===========================
Identifies why trades aren't executing by checking each gate.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from entry.policy import get_default_policy as get_entry_policy, EntryPolicyType
from position.policy import get_default_policy as get_position_policy, PositionPolicyType
from risk.risk_policy import get_default_policy as get_risk_policy, RiskPolicyType

def check_entry_policy():
    """Check entry policy requirements."""
    print("=" * 80)
    print("ENTRY POLICY ANALYSIS")
    print("=" * 80)
    
    for policy_type in EntryPolicyType:
        try:
            policy = get_entry_policy(policy_type)
            print(f"\n{policy_type.value.upper()} Policy:")
            print(f"  Name: {policy.name}")
            print(f"  Version: {policy.version}")
            print(f"  Min confidence: {getattr(policy, 'min_confidence', 'N/A')}")
            print(f"  Min liquidity: {getattr(policy, 'min_liquidity_usd', 'N/A')}")
            print(f"  Min volume: {getattr(policy, 'min_volume_24h_usd', 'N/A')}")
        except Exception as e:
            print(f"  Error loading {policy_type.value}: {e}")

def check_position_policy():
    """Check position policy requirements."""
    print("\n" + "=" * 80)
    print("POSITION POLICY ANALYSIS")
    print("=" * 80)
    
    for policy_type in PositionPolicyType:
        try:
            policy = get_position_policy(policy_type)
            print(f"\n{policy_type.value.upper()} Policy:")
            print(f"  Name: {policy.name}")
            print(f"  Max drawdown: {policy.max_drawdown_percent}%")
            print(f"  High risk threshold: {policy.high_risk_threshold}")
            print(f"  Critical risk threshold: {policy.critical_risk_threshold}")
        except Exception as e:
            print(f"  Error loading {policy_type.value}: {e}")

def check_risk_policy():
    """Check risk policy requirements."""
    print("\n" + "=" * 80)
    print("RISK POLICY ANALYSIS")
    print("=" * 80)
    
    for policy_type in RiskPolicyType:
        try:
            policy = get_risk_policy(policy_type)
            print(f"\n{policy_type.value.upper()} Policy:")
            print(f"  Name: {policy.name}")
            print(f"  Max exposure per asset: {policy.max_exposure_per_asset}%")
            print(f"  Max total exposure: {policy.max_total_exposure}%")
            print(f"  Max open positions: {policy.max_open_positions}")
            print(f"  Max trades per day: {policy.max_trades_per_day}")
            print(f"  Max drawdown: {policy.max_drawdown_pct}%")
        except Exception as e:
            print(f"  Error loading {policy_type.value}: {e}")

def check_strategy_requirements():
    """Check what strategies require."""
    print("\n" + "=" * 80)
    print("STRATEGY REQUIREMENTS")
    print("=" * 80)
    
    try:
        from strategies.elite_strategy_manager import EliteStrategyManager
        from config import load_config
        
        config = load_config()
        strategy_manager = EliteStrategyManager(config=config.get("strategies", {}))
        
        print("\nStrategy Manager initialized successfully")
        print(f"Available strategies: {list(strategy_manager.get_all_strategies_metadata().keys())}")
        
    except Exception as e:
        print(f"Error checking strategies: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all diagnostics."""
    print("TRADING BLOCKAGE DIAGNOSTIC")
    print("=" * 80)
    
    check_entry_policy()
    check_position_policy()
    check_risk_policy()
    check_strategy_requirements()
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print("""
1. Check logs for rejection reasons at each gate:
   - Strategy: Look for "Rejected by strategies"
   - Entry: Look for "Entry rejected"
   - Position: Look for "Position rejected"
   - Risk: Look for "Risk rejected"

2. Verify opportunities are being generated:
   - Check if opportunity_queue has items
   - Check if AI controller is processing tokens

3. Check policy configurations:
   - Entry policy may require minimum confidence/liquidity
   - Risk policy may limit max positions/trades
   - Position policy may have strict risk thresholds

4. Enable debug logging to see detailed rejection reasons
    """)

if __name__ == "__main__":
    main()
