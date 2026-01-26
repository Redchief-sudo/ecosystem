# Strategy Wiring Fixes Applied

## Issues Fixed

### 1. **NeuralBrain Evaluation Now Extracts Signal Data**
**Before**: Empty strategy_signals dicts were passed to NeuralBrain
```python
strategy_signals = {
    'technical': {},  # Empty!
    'fundamental': {},
    'sentiment': {},
    'order_flow': {}
}
```

**After**: Actual signal data is extracted and categorized:
```python
# Extract signal data from NormalizedSignal
signal = result.signal
strategy_signals[signal_category] = {
    'confidence': signal.confidence,
    'expected_edge': signal.expected_edge,
    'direction': signal.direction,
    'max_risk': signal.max_risk,
}
```

**Impact**: NeuralBrain can now properly evaluate and compare strategies

### 2. **Trading Loop Uses AI Controller's Strategy Selection**
**Before**: Trading loop always re-evaluated strategies, ignoring AI controller's recommendation

**After**: 
- First checks if AI controller already selected a strategy (from opportunity metadata)
- Uses that recommendation if available
- Falls back to direct evaluation only if no recommendation exists
- When evaluating directly, selects the best strategy based on confidence

**Impact**: 
- Avoids duplicate strategy evaluation
- Uses the AI controller's weighted selection
- Properly selects best strategy when fallback is needed

### 3. **Best Strategy Selection Logic**
**Before**: Just checked `if any(s.success)` - didn't select best one

**After**: 
- Uses AI controller's recommendation when available
- When evaluating directly, selects strategy with highest confidence:
```python
best_signal = max(
    [s for s in signals if s.success and s.signal],
    key=lambda s: s.signal.confidence if s.signal else 0.0,
    default=None
)
```

**Impact**: Always uses the best available strategy

## Strategy Flow (Fixed)

1. **AI Controller** (in `_token_consumer_loop`):
   - Evaluates all strategies in parallel
   - Uses NeuralBrain to weight and select best strategy
   - Adds `strategy_recommendation` to opportunity metadata

2. **Trading Loop**:
   - Checks for AI controller's recommendation first
   - Uses it if available (preferred path)
   - Falls back to direct evaluation if needed
   - Selects best strategy by confidence when evaluating directly

## Strategy Weighting

Strategies are now properly weighted through:
1. **NeuralBrain weights** (configurable):
   - technical: 0.4
   - fundamental: 0.3
   - sentiment: 0.2
   - order_flow: 0.1

2. **Signal confidence**: Used as primary selection criteria

3. **Strategy categorization**: Strategies are categorized based on their type:
   - Momentum/Breakout/Volatility/Aggressive → technical
   - Smart Money/Professional/Elite → order_flow
   - Sentiment → sentiment

## Verification

✅ NeuralBrain receives actual signal data
✅ AI controller's strategy selection is used
✅ Best strategy is selected based on confidence
✅ No duplicate strategy evaluation
✅ Proper strategy weighting through NeuralBrain
