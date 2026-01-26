#!/bin/bash
# Real-time Trading Log Viewer
# Shows only relevant trading activity

echo "🚀 Starting Real-time Trading Log Monitor"
echo "📝 Watching ecosystem logs..."
echo "=" * 60

# Monitor the most recent log file with filters
tail -f /home/damien/ecosystem/logs/ecosystem_debug.log 2>/dev/null | \
grep --line-buffered -E "(SCAN|NORMALIZE|DEDUPLICATE|ELITE|OPTIMIZED|EXECUTING|APPROVED|REJECTED|SUCCESS|FAILED|🔍|📦|🔄|🧠|⚙️|🚀|✅|❌|💊|📊)" || \
tail -f /home/damien/ecosystem/logs/ecosystem.log 2>/dev/null | \
grep --line-buffered -E "(SCAN|NORMALIZE|DEDUPLICATE|ELITE|OPTIMIZED|EXECUTING|APPROVED|REJECTED|SUCCESS|FAILED|🔍|📦|🔄|🧠|⚙️|🚀|✅|❌|💊|📊)" || \
echo "❌ No active log files found. Start the trading system first."
