# TODO: Risk/Limits.py Comprehensive Fixes

## Progress Tracking

### Phase 1: Core Data Structures
- [ ] 1.1 Update module docstring with new unit semantics
- [ ] 1.2 Add MAX_DRAWDOWN_RATIO to LimitType enum
- [ ] 1.3 Add asset_id field to RiskViolation
- [ ] 1.4 Remove HardLimitViolation exception class

### Phase 2: RiskLimit Changes
- [ ] 2.1 Remove unit validation for "pct" (keep only "ratio")
- [ ] 2.2 Fix check_violation() logic: current_value > self.threshold
- [ ] 2.3 Remove exception raising from check_violation()
- [ ] 2.4 Add asset_id parameter to check_violation()

### Phase 3: RiskLimits Validation
- [ ] 3.1 Add __post_init__ to RiskLimits
- [ ] 3.2 Validate no duplicate limit types
- [ ] 3.3 Ensure hard limits exist for core safety

### Phase 4: LimitCalculator Fixes
- [ ] 4.1 Fix calculate_concentration() to use portfolio_value
- [ ] 4.2 Make calculate_portfolio_exposure() direction-aware
- [ ] 4.3 Update calculate_drawdown() for ratio semantics

### Phase 5: Update Predefined Configurations
- [ ] 5.1 Update get_conservative_limits() with new ratios
- [ ] 5.2 Update get_moderate_limits() with new ratios
- [ ] 5.3 Update get_aggressive_limits() with new ratios
- [ ] 5.4 Update get_paper_trading_limits() with hard enforcement

### Phase 6: Update Exports
- [ ] 6.1 Update risk/__init__.py if needed

## Implementation Notes
- Decision: Use "ratio" for 0-1 values, eliminate "pct"
- Concentration thresholds: 20.0 → 0.20, 25.0 → 0.25, 30.0 → 0.30, 50.0 → 0.50
- All violations returned, RiskManager handles enforcement
- Paper trading: relaxed thresholds but hard enforcement

