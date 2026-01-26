# Strategy Weighting and Bias Analysis

## Current Strategy Selection System

### 1. Strategy Execution Flow

**Step 1: Parallel Execution** (`EliteStrategyManager.execute_strategies_parallel`)
- All enabled strategies run in parallel
- Each strategy evaluates the token independently
- Returns `StrategyResult` with `success`, `signal`, and `strategy_id`

**Step 2: Signal Evaluation** (`EliteAsyncAIController._evaluate_signals`)
- Filters to only successful signals: `valid = [r for r in results if r.success and r.signal]`
- For each signal, calls `neural_brain.evaluate_signal()` OR falls back to `signal.confidence`
- Selects the signal with the **highest score**

**Step 3: Strategy Selection**
- Returns the strategy with the best score as `best.strategy_id`

### 2. Current Issues Found

#### Issue 1: No Explicit Strategy Weighting
- **Problem**: There's no weighting system for individual strategies
- **Current behavior**: Simply selects the strategy with highest confidence/score
- **Impact**: Strategies that naturally return higher confidence scores will be selected more often

#### Issue 2: Neural Brain Mismatch
- **Problem**: `neural_brain.evaluate_signal()` expects signal categories (`technical`, `fundamental`, `sentiment`, `order_flow`)
- **Reality**: AI controller passes `{"confidence": result.signal.confidence}` which doesn't match expected format
- **Impact**: Neural brain likely returns `None` or low scores, causing fallback to raw confidence

#### Issue 3: No Strategy Performance Tracking
- **Problem**: No tracking of which strategies perform best over time
- **Impact**: Can't dynamically adjust weights based on performance

#### Issue 4: Potential Bias Sources

**RiskCaps Strategy Characteristics:**
- Uses sophisticated risk metrics (Sharpe ratio, VaR, Kelly Criterion)
- Calculates confidence from multiple factors with complex formulas
- May naturally produce higher confidence scores due to:
  - More comprehensive analysis
  - Multiple confidence boosters (liquidity_score, volatility adjustments)
  - Conservative Kelly fraction (0.25) but still may produce higher scores

**Other Strategies:**
- Momentum, Mean Reversion, Breakout: Simpler confidence calculations
- May produce lower confidence scores in comparison

### 3. RiskCaps Strategy Analysis

**Confidence Calculation** (`risk_caps.py:463-483`):
```python
def _calculate_confidence(self, risk_metrics, size, config):
    # Base confidence from Sharpe ratio
    confidence = risk_metrics.sharpe_ratio / 2.0
    
    # Boost for good liquidity
    confidence *= (0.7 + 0.3 * risk_metrics.liquidity_score)
    
    # Penalize high volatility
    confidence *= (1.0 / (1.0 + risk_metrics.volatility * 0.5))
    
    # Penalize large positions
    size_penalty = 1.0 - (size / config["max_position_size"]) * 0.2
    confidence *= size_penalty
    
    return max(0.05, min(0.95, confidence))
```

**Potential Issues:**
- If Sharpe ratio is high (e.g., 1.0), base confidence = 0.5
- Liquidity boost can add up to 30% more
- Final confidence can range from 0.05 to 0.95
- This is a **wide range** that may consistently beat simpler strategies

### 4. Recommendations

#### Immediate Fixes:

1. **Add Strategy Weighting System**
   - Create a strategy weight configuration
   - Apply weights when comparing strategies
   - Ensure fair competition between strategies

2. **Normalize Confidence Scores**
   - Normalize all strategy confidence scores to a common scale
   - Prevents one strategy from dominating due to scoring methodology

3. **Fix Neural Brain Integration**
   - Properly map strategy signals to neural brain categories
   - Or bypass neural brain if it's not being used correctly

4. **Add Strategy Performance Tracking**
   - Track which strategies are selected and their outcomes
   - Use this to adjust weights dynamically

#### Long-term Improvements:

1. **Ensemble Approach**
   - Consider multiple strategies, not just the best one
   - Weighted combination of top N strategies

2. **Market Regime Awareness**
   - Different strategies perform better in different market conditions
   - Adjust weights based on current market regime

3. **Performance-Based Weighting**
   - Continuously update strategy weights based on historical performance
   - Reduce weight of underperforming strategies

## Conclusion

**Current State**: No explicit bias towards RiskCaps, but the selection mechanism (highest confidence wins) may favor it if it consistently produces higher confidence scores.

**Action Required**: Implement proper strategy weighting and normalization to ensure fair competition.
