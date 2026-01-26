# System Composition Root Fixes - Implementation Plan

## Critical Issues to Fix (High Severity)

### 1. Broken Composition Root
- **Problem**: `compose_system()` mixes composition and runtime instantiation
- **Fix**: Move all component creation to composition phase, return fully built composition

### 2. SystemComposition Class Issues
- **Problem**: Missing `shutdown_requested` attribute
- **Fix**: Add `shutdown_requested = False` in `__init__`
- **Problem**: No `run_with_trading_loop()` method
- **Fix**: Rename `run()` to `run_with_trading_loop()` or fix main() call

### 3. Runtime Loop Component Creation
- **Problem**: Components created inside `_runtime_loop()` on every iteration
- **Fix**: Move all component creation to `compose_system()`

### 4. Dead Code After Loop
- **Problem**: Component creation block after `while` loop never executes
- **Fix**: Remove dead code or move to composition

### 5. Inconsistent Logging
- **Problem**: Mix of `print()` and `logging`
- **Fix**: Use consistent logging throughout

### 6. Duplicate Lifecycle Components
- **Problem**: `startup_director` created twice
- **Fix**: Create once in composition

## Implementation Steps

1. ✅ Fix SystemComposition class
   - Add shutdown_requested attribute
   - Ensure proper run method exists

2. ✅ Fix compose_system() function
   - Move all component creation to composition phase
   - Return fully wired composition

3. ✅ Fix main() function
   - Call correct method on composition

4. ✅ Remove dead code
   - Clean up unused component creation blocks

5. ✅ Test fixes
   - Ensure system starts without AttributeError
   - Verify proper shutdown handling
