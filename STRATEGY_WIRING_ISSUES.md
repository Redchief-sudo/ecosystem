# Strategy Wiring Issues Analysis

## Issues Found

### 1. **Double Strategy Evaluation**
- **Problem**: Strategies are evaluated TWICE:
  1. In AI controller's `select_strategy()` - properly selects best strategy
  2. In trading loop - evaluates again but doesn't use AI controller's selection
  
- **Impact**: Wasted computation, and trading loop doesn't use the best strategy

### 2. **NeuralBrain Evaluation Not Working**
- **Problem**: `_evaluate_signals_with_neural_brain()` creates empty strategy_signals dicts:
  ```python
  strategy_signals = {
      'technical': {},  # Empty!
      'fundamental': {},  # Empty!
      'sentiment': {},  # Empty!
      'order_flow': {}  # Empty!
  }
  ```
- **Impact**: NeuralBrain can't properly evaluate signals because it receives no data

### 3. **Strategy Recommendation Not Used**
- **Problem**: AI controller adds `strategy_recommendation` to opportunity metadata, but trading loop ignores it
- **Impact**: The best strategy selection is discarded

### 4. **No Proper Strategy Selection in Trading Loop**
- **Problem**: Trading loop just checks `if any(s.success for s in signals)` but doesn't select the best one
- **Impact**: May use a suboptimal strategy instead of the best one

## Solutions Needed

1. **Use AI Controller's Strategy Selection**: Trading loop should use the strategy recommendation from opportunity metadata
2. **Fix NeuralBrain Evaluation**: Extract actual signal data from SignalExecutionResult
3. **Remove Duplicate Evaluation**: Don't evaluate strategies twice
4. **Proper Weighting**: Use strategy weights/confidence to select best strategy
