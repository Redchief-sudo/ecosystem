# Risk/Limits.py Implementation Plan

## Information Gathered

### Current State Analysis:
1. **risk/limits.py** contains:
   - `LimitType` enum with 10 limit types
   - `RiskViolation` dataclass with `asset_symbol: Optional[str]`
   - `HardLimitViolation` exception class
   - `RiskLimit` dataclass with check_violation() that raises exceptions for hard limits
   - `RiskLimits` dataclass as container without validation
   - `LimitCalculator` with static methods for calculations
   - 4 predefined limit configurations (conservative, moderate, aggressive, paper)

2. **risk/risk_manager.py** - Separate module with different RiskManager implementation
3. **risk/risk_verdict.py** - Contains RiskVerdict, RiskAssessment for verdicts

### Key Issues Identified:
1. Unit ambiguity ("pct" used for both 0-1 and 0-100)
2. Silent bypass in check_violation logic
3. Exceptions in RiskLimit break composability
4. Asset identity uses only symbol (not chain+token)
5. Concentration calculation uses wrong denominator
6. Exposure ignores position direction
7. DRAWDOWN limit naming is misleading
8. RiskLimits lacks validation
9. Paper trading has no enforcement

---

## Plan: Comprehensive Fixes for risk/limits.py

### Step 1: Fix Unit Semantics (Issue 1)
**Decision: Use "ratio" for 0-1 values, eliminate "pct"**
- Update module docstring to reflect new semantics
- Rename "pct" → "ratio" in all RiskLimit definitions
- Update concentration threshold values (20.0 → 0.20)

### Step 2: Remove Exceptions from RiskLimit (Issue 3)
- Remove `HardLimitViolation` exception class or deprecate it
- Remove exception raising from `check_violation()`
- Return all violations, let RiskManager handle enforcement

### Step 3: Fix check_violation() Logic (Issue 2)
- Change `current_value <= self.threshold` to `current_value > self.threshold`
- Always return violation when exceeded, None when compliant
- Never return None for violations

### Step 4: Fix Asset Identity (Issue 4)
- Add `asset_id: Optional[Tuple[str, str]]` to RiskViolation
- Keep `asset_symbol` for backward compatibility but deprecate
- Update `check_violation()` to accept asset_id

### Step 5: Fix Concentration Math (Issue 5)
- Change `calculate_concentration(asset_exposure, total_exposure)` 
- To: `calculate_concentration(asset_exposure, portfolio_value)`
- Return 0-1 ratio instead of 0-100 percentage

### Step 6: Make Exposure Direction-Aware (Issue 6)
- Update `calculate_portfolio_exposure()` to handle position side
- Update `calculate_asset_exposure()` to accept side parameter

### Step 7: Rename Drawdown Limit (Issue 7)
- Add `MAX_DRAWDOWN_RATIO` to LimitType enum
- Keep `DRAWDOWN` for backward compatibility with deprecation warning
- Update unit to "ratio" consistently

### Step 8: Add RiskLimits Validation (Issue 8)
- Add `__post_init__()` to RiskLimits
- Validate no duplicate limit types
- Ensure hard limits exist for core safety

### Step 9: Fix Paper Trading Limits (Issue 9)
- Convert paper limits from "warning" to appropriate "hard"/"soft"
- Keep thresholds relaxed but enforce core invariants

### Step 10: Update Predefined Configurations
- Update all 4 limit configurations with new values
- Ensure consistent "ratio" semantics throughout

---

## Dependent Files to be Edited

1. `/home/damien/ecosystem/risk/limits.py` - Main implementation
2. `/home/damien/ecosystem/risk/__init__.py` - Update exports if needed

---

## Followup Steps

1. Create comprehensive tests to verify all fixes
2. Update any code that uses the old API
3. Add type hints for better type safety
4. Update documentation strings

---

## Confirmation Required

Please review and confirm this plan before I proceed with implementation.

