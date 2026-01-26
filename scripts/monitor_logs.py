#!/usr/bin/env python3
"""
Real-time Log Monitor for Trading Engine
Shows live trading activity as it happens
"""

import os
import sys
import time
from pathlib import Path


def monitor_logs():
    """Monitor trading logs in real-time"""
    log_dir = Path("/home/damien/ecosystem/logs")
    
    # Priority order for log files
    log_files = [
        "ecosystem_debug.log",
        "ecosystem.log", 
        "trading.log"
    ]
    
    # Find the most recent log file
    target_log = None
    for log_file in log_files:
        log_path = log_dir / log_file
        if log_path.exists():
            target_log = log_path
            break
    
    if not target_log:
        print("❌ No log files found")
        return
    
    print(f"📝 Monitoring: {target_log}")
    print("=" * 80)
    
    try:
        with open(target_log, 'r') as f:
            # Go to end of file
            f.seek(0, 2)
            
            while True:
                line = f.readline()
                if line:
                    # Filter for important trading events
                    if any(keyword in line for keyword in [
                        'SCAN', 'NORMALIZE', 'DEDUPLICATE', 'ELITE', 'OPTIMIZED', 
                        'EXECUTING', 'APPROVED', 'REJECTED', 'SUCCESS', 'FAILED',
                        '🔍', '📦', '🔄', '🧠', '⚙️', '🚀', '✅', '❌'
                    ]):
                        print(line.strip())
                else:
                    time.sleep(0.1)
                    
    except KeyboardInterrupt:
        print("\n🛑 Log monitoring stopped")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    monitor_logs()
