# PnL Tracking Integration Guide

## Overview

Your trading system now includes comprehensive **Profit & Loss (PnL) tracking** that converts it from a purely signal-driven system to a **profit-aware system** with historical feedback loops.

## Key Components

### 1. **PnL Data Models** (`trading/pnl_models.py`)

#### TradePnL Class
Records individual trades with entry/exit information:
```python
trade = TradePnL(
    token="PEPE",
    chain="ethereum",
    strategy="momentum",
    entry_price=0.00000015,
    exit_price=0.00000018,  # None until trade closes
    size=1000.0,  # USD
    fees=2.50,
    realized=False  # True only when position closed
)

# Methods
trade.pnl()           # $ profit/loss
trade.pnl_percent()   # % return
trade.roi()           # ROI in %
trade.to_dict()       # For CSV logging
```

#### StrategyPerformance Class
Aggregates metrics per strategy/token/chain:
```python
perf = tracker.get_strategy_performance(
    strategy="momentum",
    token="PEPE",
    chain="ethereum"
)

# Available metrics
perf.total_trades           # 42
perf.winning_trades         # 27
perf.losing_trades          # 15
perf.total_pnl              # $150.25
perf.avg_pnl                # $3.58
perf.max_drawdown           # -0.15 (15%)
perf.sharpe_ratio           # 1.25
perf.win_rate               # 0.643 (64.3%)

# Get composite profitability score for AI weighting
score = perf.profitability_score()  # 0.0-1.0
```

### 2. **PnL Tracker** (`trading/pnl_tracker.py`)

Central management system for all PnL operations:

#### Key Methods

**Enter a trade:**
```python
tracker.enter_trade(
    trade_id="trade_12345",
    trade=TradePnL(...)
)
```

**Close a trade:**
```python
closed_trade = tracker.close_trade(
    trade_id="trade_12345",
    exit_price=0.00000018
)
# Automatically logs to CSV and updates metrics
```

**Get strategy performance:**
```python
perf = tracker.get_strategy_performance(
    strategy="momentum",
    token="PEPE",
    chain="ethereum"
)
```

**Dynamic position sizing:**
```python
position_size = tracker.get_position_size(
    token="PEPE",
    chain="ethereum",
    strategy="momentum",
    base_size=10.0  # $10 base
)
# Returns: adjusted size based on historical performance
# Winning strategies get scaled up (1.5x max)
# Losing strategies get scaled down (0.5x min)
```

**Circuit breaker logic:**
```python
# Check if strategy should be used
if tracker.should_use_strategy(
    strategy="momentum",
    token="PEPE",
    chain="ethereum",
    min_win_rate=0.40  # Disable if < 40% wins
):
    # Execute trade
else:
    # Skip this strategy
```

### 3. **Integration Points**

#### A. AI Controller Integration (`ai/elite_async_ai_controller.py`)

PnL metrics now influence strategy selection:

**Before:**
- Strategy selection based 100% on signal confidence

**After:**
- Signal confidence: 60% weight
- Historical profitability: 40% weight
- Circuit breakers disable poor-performing strategies
- Dynamic weighting: `final_score = signal_confidence * 0.6 + profitability_score * 0.4`

**In the code:**
```python
# Get historical performance
pnl_perf = self.pnl_tracker.get_strategy_performance(
    strategy_id, token, chain
)

if pnl_perf and pnl_perf.total_trades >= 5:
    # Blend signal with historical performance
    pnl_score = pnl_perf.profitability_score()
    raw_score = raw_score * 0.6 + pnl_score * 0.4

# Check circuit breaker
if not self.pnl_tracker.should_use_strategy(strategy_id, token, chain):
    continue  # Skip this strategy
```

#### B. Trade Execution Integration (`main.py`)

Trades are recorded in the PnL tracker when executed:

```python
if result.status == "executed":
    trade = TradePnL(
        token=opportunity.token.symbol,
        chain=opportunity.chain,
        strategy=strategy_used,
        entry_price=float(opportunity.market_data.price),
        exit_price=None,
        size=float(suggested_size),
        fees=0.0,
        entry_time=datetime.now(timezone.utc).isoformat(),
        realized=False
    )
    
    composition.pnl_tracker.enter_trade(order.order_id, trade)
```

## CSV Output

PnL data is automatically logged to `data/pnl_history.csv`:

```csv
timestamp,token,chain,strategy,entry_price,exit_price,size,fees,pnl,pnl_percent,roi,realized
2024-01-15T10:30:45Z,PEPE,ethereum,momentum,0.00000015,0.00000018,1000.0,2.50,300.00,0.30,30.00,true
2024-01-15T10:45:20Z,SHIB,ethereum,mean_reversion,0.000015,0.000016,500.0,1.25,450.00,0.90,90.00,true
2024-01-15T11:00:00Z,DOGE,ethereum,momentum,0.12,NULL,2000.0,0.0,NULL,NULL,NULL,false
```

## Workflow Example

### 1. System Startup
```python
# PnL tracker initializes
pnl_tracker = PnLTracker(data_dir=Path("data"))

# Loads historical CSV if exists
# Rebuilds performance metrics from closed trades
```

### 2. Strategy Evaluation
```python
# When evaluating momentum strategy on PEPE/ethereum:
perf = pnl_tracker.get_strategy_performance("momentum", "PEPE", "ethereum")

# If history shows 60% win rate and $150 profit:
if perf.win_rate > 0.50:
    # Give this strategy higher weight in final selection
    strategy_score = signal_confidence * 0.6 + perf.profitability_score() * 0.4
```

### 3. Trade Entry
```python
# Trade executed
order_id = "trade_1234567890"
trade = TradePnL(
    token="PEPE",
    chain="ethereum",
    strategy="momentum",
    entry_price=0.00000015,
    ...
)

# Record in tracker
pnl_tracker.enter_trade(order_id, trade)
```

### 4. Trade Exit (Example - typically via exit manager)
```python
# Position closed, price is $0.00000018
exit_price = 0.00000018

# Close trade and record to CSV
closed_trade = pnl_tracker.close_trade(order_id, exit_price)

# Automatically:
# 1. Sets exit_price and realized=True
# 2. Logs to data/pnl_history.csv
# 3. Updates StrategyPerformance metrics
# 4. Next momentum/PEPE/ethereum signal gets better weighting
```

### 5. Performance Reporting
```python
# Print summary to logs
pnl_tracker.print_performance_summary()

# Output:
# ================================================================================
# PnL PERFORMANCE SUMMARY
# ================================================================================
# momentum on PEPE/ethereum: 27/42 wins | $150.25 | ROI +3.58%
# mean_reversion on SHIB/ethereum: 15/25 wins | $145.50 | ROI +5.82%
# ...
# ================================================================================
# TOTALS: 89/150 wins | $1,250.75 | Win rate 59.3%
# ================================================================================
```

## Dynamic Position Sizing Algorithm

Position size is adjusted based on strategy performance:

```
factor = 1.0 + (win_rate - 0.5) * 2 * 0.3 + (avg_roi / 10) * 0.2
factor = max(0.5, min(1.5, factor))  # Clamp to 0.5x - 1.5x

adjusted_size = base_size * factor
```

**Example:**
- Strategy A: 30% win rate, -5% avg ROI → size *= 0.6 ($6 instead of $10)
- Strategy B: 65% win rate, +8% avg ROI → size *= 1.3 ($13 instead of $10)

## Circuit Breaker Logic

Strategies are automatically disabled if they consistently lose:

```python
if perf.total_trades >= 3 and perf.win_rate < 0.40:
    # Circuit breaker OPENS
    strategy disabled until manually reset
    
# Reset circuit breaker:
pnl_tracker.reset_circuit_breaker(strategy, token, chain)
```

## Key Benefits

1. **Feedback Loops**: System learns from real profits/losses
2. **Adaptive Weighting**: Better strategies get more positions
3. **Risk Protection**: Poor strategies are automatically disabled
4. **Position Sizing**: Capital allocation optimized by performance
5. **Historical Record**: Complete audit trail in CSV format
6. **AI Integration**: Neural brain can use profitability scores

## Monitoring & Debugging

### Check if PnL tracking is working:

```python
# Get all cached performance metrics
perf_stats = pnl_tracker.get_all_performance_stats()

# Print summary
pnl_tracker.print_performance_summary()

# Check open trades
open = pnl_tracker.open_trades  # Dict[trade_id, TradePnL]

# Check circuit breakers
circuit_breakers = pnl_tracker.circuit_breakers  # Dict[key, bool]
```

### CSV Columns Explained

| Column | Meaning |
|--------|---------|
| timestamp | When trade was opened |
| token | Token symbol (e.g., PEPE) |
| chain | Blockchain (e.g., ethereum) |
| strategy | Strategy that generated the signal |
| entry_price | Price at entry |
| exit_price | Price at exit (NULL if still open) |
| size | Trade size in USD |
| fees | Transaction fees paid |
| pnl | Profit/loss in USD (NULL if still open) |
| pnl_percent | Profit/loss as percentage (NULL if still open) |
| roi | Return on investment % (NULL if still open) |
| realized | true if trade closed, false if still open |

## Next Steps

1. **Monitor PnL logs**: Check `data/pnl_history.csv` after first trades
2. **Tune circuit breaker thresholds**: Adjust `min_win_rate` based on risk tolerance
3. **Experiment with blending ratios**: Adjust 60/40 signal/PnL weighting
4. **Implement exit hooks**: Add PnL recording to your exit manager
5. **Dashboard integration**: Build visualization of PnL metrics

## File Locations

- **Data models**: `trading/pnl_models.py`
- **PnL tracker**: `trading/pnl_tracker.py`
- **CSV output**: `data/pnl_history.csv`
- **AI integration**: `ai/elite_async_ai_controller.py` (lines 333-385)
- **Main integration**: `main.py` (lines 411-429)

## Troubleshooting

### "PnL tracker not recording trades"
- Check that `composition.pnl_tracker` is properly initialized
- Verify `enter_trade()` is called after trade execution
- Check `data/` directory exists and is writable

### "Circuit breaker disabled all strategies"
- Lower the `min_win_rate` threshold (default 0.40 = 40%)
- Bootstrap phase needs more trades before circuit breaker activates
- Check `pnl_tracker.circuit_breakers` dict

### "Position sizes not adjusting"
- Ensure `get_position_size()` is called before executing trades
- Strategy must have >= 5 closed trades for sizing to take effect
- Check `perf.total_trades` count

## Performance Profitability Score Formula

```
win_rate_score = win_rate (0.0 to 1.0)
roi_score = min(1.0, max(0.0, avg_roi / 10.0))  # 10% ROI = 1.0 score
drawdown_score = max(0.0, 1.0 - abs(max_drawdown) * 10)

profitability_score = (
    win_rate_score * 0.50 +      # Win rate is most important (50%)
    roi_score * 0.35 +           # ROI matters (35%)
    drawdown_score * 0.15        # Drawdown protection (15%)
)
```

Result: 0.0 (terrible) to 1.0 (excellent)

---

**Status**: ✅ PnL tracking fully integrated
**Version**: 1.0
**Last Updated**: 2024
