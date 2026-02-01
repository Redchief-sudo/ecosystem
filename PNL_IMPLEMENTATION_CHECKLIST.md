# PnL Implementation Checklist

## Phase 1: Core Integration ✅ COMPLETE

- [x] Created `trading/pnl_models.py` with TradePnL and StrategyPerformance dataclasses
- [x] Created `trading/pnl_tracker.py` with PnLTracker management class
- [x] Integrated PnL tracker into `ai/elite_async_ai_controller.py` for strategy scoring
- [x] Added PnL tracker initialization to `main.py`
- [x] Added PnL entry recording in main trade execution loop
- [x] Created comprehensive `PNL_TRACKING_GUIDE.md` documentation

## Phase 2: Enhanced Trade Execution (RECOMMENDED)

- [ ] Add PnL exit hook in position manager or exit manager
  - File: `position/position.py` or `exit/exit.py`
  - Action: Call `pnl_tracker.close_trade(trade_id, exit_price)` when position closes
  - Benefit: Automatic PnL recording, eliminates unrealized tracking

- [ ] Update trade execution to track trade IDs
  - File: `trading/execution/trade_engine.py` or post-trade manager
  - Action: Maintain mapping of position_id → trade_id for exit hooks
  - Benefit: Can close trades when positions are exited

## Phase 3: Dashboard & Reporting (OPTIONAL)

- [ ] Create PnL reporting script
  - File: `scripts/report_pnl.py`
  - Features:
    - Read `data/pnl_history.csv`
    - Group by strategy, token, chain
    - Display daily/weekly/monthly summaries
    - Show win rates, ROI, max drawdown

- [ ] Create PnL visualization dashboard
  - File: `dashboard/backend/pnl_endpoints.py`
  - Endpoints:
    - GET `/api/pnl/summary` - overall stats
    - GET `/api/pnl/strategies` - per-strategy breakdown
    - GET `/api/pnl/tokens` - per-token breakdown
    - GET `/api/pnl/history` - full trade history

- [ ] Create Grafana dashboard
  - Data source: SQLite conversion of CSV
  - Panels:
    - Win rate trend
    - Cumulative PnL
    - Strategy performance heatmap
    - Drawdown chart

## Phase 4: Advanced Features (OPTIONAL)

- [ ] Dynamic position sizing based on PnL history
  - File: `position/position.py`
  - Implementation: Use `pnl_tracker.get_position_size()`
  - Benefit: Automatically scale positions by performance

- [ ] Adaptive thresholds based on PnL
  - File: `entry/entry.py`
  - Logic: Adjust entry thresholds based on recent strategy performance
  - Example: Lower entry threshold for high-performing strategies

- [ ] Risk-adjusted position sizing (Kelly Criterion)
  - File: `position/position.py`
  - Formula: f* = (bp - q) / b
  - Benefit: Mathematically optimal position sizing

- [ ] Strategy backtesting against historical PnL
  - File: `scripts/backtest_with_pnl.py`
  - Features:
    - Replay historical trades
    - Show what-if scenarios
    - Optimize strategy weights

## Phase 5: Deployment & Monitoring

- [ ] Set up PnL monitoring in production
  - [ ] Log to monitoring system (Prometheus metrics)
  - [ ] Alert on circuit breaker activations
  - [ ] Track PnL per strategy per hour

- [ ] Set up database backup for PnL history
  - CSV backup daily: `data/pnl_history_backup_YYYYMMDD.csv`
  - Database migration if moving to SQLite for scale

- [ ] Create PnL health checks
  - File: `core/health_check.py`
  - Checks:
    - CSV file exists and is writable
    - Performance metrics are updating
    - No data loss on restarts

## Quick Start Commands

### View PnL Performance

```bash
# Print summary to logs
python -c "
from trading.pnl_tracker import PnLTracker
tracker = PnLTracker()
tracker.print_performance_summary()
"
```

### Reset a Circuit Breaker

```bash
# If a strategy is disabled but you want to retry
python -c "
from trading.pnl_tracker import PnLTracker
tracker = PnLTracker()
tracker.reset_circuit_breaker('momentum', 'PEPE', 'ethereum')
"
```

### Query Strategy Performance

```bash
python -c "
from trading.pnl_tracker import PnLTracker
tracker = PnLTracker()

perf = tracker.get_strategy_performance('momentum')
print(f'Win rate: {perf.win_rate:.1%}')
print(f'Avg PnL: ${perf.avg_pnl:.2f}')
print(f'Max drawdown: {perf.max_drawdown:.1%}')
print(f'Score: {perf.profitability_score():.2f}')
"
```

### Check Position Size Adjustment

```bash
python -c "
from trading.pnl_tracker import PnLTracker
tracker = PnLTracker()

size = tracker.get_position_size(
    token='PEPE',
    chain='ethereum',
    strategy='momentum',
    base_size=10.0
)
print(f'Adjusted size: \${size:.2f}')
"
```

## Testing Checklist

- [ ] Run a paper trading session with PnL enabled
- [ ] Verify `data/pnl_history.csv` is created and populated
- [ ] Check that PnL tracker logs appear in system logs
- [ ] Confirm circuit breaker activates after poor performance
- [ ] Verify position sizing adjusts based on strategy history

## Performance Expectations

After 100+ trades:
- [ ] PnL summary should be readable (no NaN/None errors)
- [ ] Strategy scores should range 0.0-1.0
- [ ] Circuit breaker should have disabled 0-2 strategies (if working well)
- [ ] Win rates should cluster around 50% (neutral skill)
- [ ] Positive PnL strategies should be weighted higher

## Troubleshooting Guide

### Issue: CSV file not created
```
Solution: Check that data/ directory exists and is writable
$ mkdir -p data/
$ touch data/pnl_history.csv
```

### Issue: PnL tracker not recording trades
```
Solution: Verify composition has pnl_tracker initialized
# In main.py, check:
composition.pnl_tracker = PnLTracker()
# Also verify enter_trade() is called after execution
```

### Issue: Strategy scores always 1.0
```
Solution: Check if historical trades exist and have 5+ trades
# Verify CSV has closed trades (realized=true)
# If CSV is empty, run some paper trades first
```

### Issue: Circuit breaker too aggressive
```
Solution: Lower min_win_rate threshold
# Current: 40% (0.40)
# Try: 30% (0.30) for more aggressive filtering
should_use_strategy(..., min_win_rate=0.30)
```

## Integration Points Verification

### ✅ AI Controller Integration
- Location: `ai/elite_async_ai_controller.py` lines 333-385
- Verified: PnL scoring blended with signal confidence (60/40)
- Circuit breaker: Strategies filtered based on performance

### ✅ Main Loop Integration
- Location: `main.py` lines 411-429
- Verified: Trade entry recorded with TradePnL dataclass
- Trade ID: Uses order.order_id for tracking

### ⚠️ Exit Hook (PENDING)
- Location: Should be in exit manager or position manager
- TODO: Call `pnl_tracker.close_trade(trade_id, exit_price)`
- Impact: Without this, trades remain in "open" state

### ⚠️ Dynamic Sizing (PENDING)
- Location: Should be in position manager
- TODO: Use `pnl_tracker.get_position_size()` before executing
- Impact: Without this, all positions same size regardless of performance

## Files Modified/Created

### Created Files
1. ✅ `trading/pnl_models.py` - Data structures (~190 lines)
2. ✅ `trading/pnl_tracker.py` - PnL management (~450 lines)
3. ✅ `PNL_TRACKING_GUIDE.md` - User documentation
4. ✅ `PNL_IMPLEMENTATION_CHECKLIST.md` - This file

### Modified Files
1. ✅ `ai/elite_async_ai_controller.py` - Added PnL tracker import and initialization
2. ✅ `ai/elite_async_ai_controller.py` - Added PnL scoring in strategy selection (lines 333-385)
3. ✅ `main.py` - Added PnL imports
4. ✅ `main.py` - Added PnL tracker initialization
5. ✅ `main.py` - Added PnL entry recording after trade execution (lines 411-429)

## Success Criteria

Your PnL system is working correctly when:

1. ✅ `data/pnl_history.csv` is created on first trade
2. ✅ Each executed trade is recorded with entry_price and size
3. ✅ Closed trades show exit_price and calculated pnl
4. ✅ `pnl_tracker.print_performance_summary()` shows aggregated stats
5. ✅ Strategy scores blend signal confidence + historical performance
6. ✅ Logs show PnL-adjusted scores for strategy selection
7. ✅ Circuit breaker warnings appear for poor strategies

## Next Priority Actions

1. **HIGH**: Implement exit hook in exit manager
   - This ensures all trades get recorded as realized
   - Current: Only entry is recorded (trades stuck as "open")

2. **MEDIUM**: Add dynamic position sizing
   - Use profitability scores to adjust trade sizes
   - Better performers → larger positions

3. **LOW**: Create reporting dashboard
   - Nice to have but not essential
   - CSV already provides audit trail

---

**Status**: Phase 1 ✅ COMPLETE, Phases 2-5 PENDING
**Date**: 2024
**Owner**: Trading System
