#!/usr/bin/env python3
"""
Trading System Summary & Verification
======================================
Verifies the complete bot is working end-to-end.
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, '/home/damien/ecosystem')

# Minimal test
async def verify_system():
    """Quick verification that the system pipeline is working."""
    
    print("=" * 80)
    print("TRADING SYSTEM VERIFICATION")
    print("=" * 80)
    print()
    
    # 1. Check if processes are running
    import subprocess
    result = subprocess.run(['pgrep', '-f', 'python3 main.py'], capture_output=True)
    if result.stdout:
        pids = result.stdout.decode().strip().split('\n')
        print(f"✅ Main system running (PIDs: {', '.join(pids)})")
    else:
        print("❌ Main system not running")
        print("   Run: python3 main.py")
        return
    
    # 2. Check logs exist
    log_file = '/home/damien/ecosystem/logs/ecosystem.log'
    if os.path.exists(log_file):
        size_mb = os.path.getsize(log_file) / (1024 * 1024)
        print(f"✅ Log file exists ({size_mb:.1f} MB)")
    else:
        print("❌ Log file not found")
        return
    
    # 3. Count opportunities emitted
    with open(log_file, 'r') as f:
        content = f.read()
        
    emitted = content.count("Opportunity emitted")
    received = content.count("Received opportunity")
    accepted = content.count("Position within acceptable")
    executing = content.count("Executing trade")
    executed = content.count("Trade result")
    
    print()
    print("PIPELINE STATS:")
    print(f"  ✅ Opportunities emitted:        {emitted}")
    print(f"  ✅ Opportunities received:       {received}")
    print(f"  ✅ Positions accepted:           {accepted}")
    print(f"  🟡 Trades executing:            {executing}") 
    print(f"  🟡 Trades executed:             {executed}")
    print()
    
    # 4. Summary
    print("SUMMARY:")
    if emitted > 0:
        print(f"✅ Scanner → AI Controller: WORKING ({emitted} opportunities)")
    else:
        print("❌ Scanner → AI Controller: NOT WORKING")
    
    if received > 0:
        print(f"✅ Opportunity queue: WORKING ({received} received)")
    else:
        print("❌ Opportunity queue: NOT WORKING")
    
    if accepted > 0:
        print(f"✅ Entry assessment: WORKING ({accepted} positions accepted)")
    else:
        print("🟡 Entry assessment: CONDITIONAL verdicts only (lower bootstrap thresholds)")
    
    if executing > 0:
        print(f"✅ Trade execution: WORKING ({executing} trades executing)")
    else:
        print("🟡 Trade execution: NOT EXECUTING YET (check position_size, risk, USDC address)")
    
    print()
    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print()
    if executing == 0:
        print("To start executing trades:")
        print("  1. Bootstrap historical data:")
        print("     python3 scripts/bootstrap_historical_data.py")
        print()
        print("  2. Verify system is running:")
        print("     python3 scripts/verify_system.py")
        print()
        print("  3. Check logs in real-time:")
        print("     tail -f logs/ecosystem.log | grep -i 'executing\\|trade'")
    else:
        print("✅ System is executing trades!")
        print("   Monitor in real-time: tail -f logs/ecosystem.log | grep -i 'trade'")
    print()

if __name__ == '__main__':
    asyncio.run(verify_system())
