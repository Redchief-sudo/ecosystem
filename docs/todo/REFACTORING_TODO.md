# Refactoring TODO List

## Phase 1: Foundation (Data Classes & StrategyManager)
- [ ] 1.1 Create `strategies/data_classes.py` with StrategyDecision, RiskProfile, HealthStatus, etc.
- [ ] 1.2 Create `strategies/strategy_manager.py` with new StrategyManager class
- [ ] 1.3 Update `strategies/__init__.py` to export new classes

## Phase 2: BaseStrategy Refactoring
- [ ] 2.1 Add new abstract methods to BaseStrategy:
  - [ ] strategy_id()
  - [ ] version()
  - [ ] description()
  - [ ] supported_markets()
  - [ ] timeframes()
  - [ ] required_features()
  - [ ] warmup_period()
  - [ ] signal_type()
  - [ ] risk_profile()
  - [ ] evaluate() (new, returns StrategyDecision)
- [ ] 2.2 Keep backward compatibility methods with deprecation warnings
- [ ] 2.3 Remove execution concerns from BaseStrategy

## Phase 3: Update All Concrete Strategies
- [ ] 3.1 Update `EliteMomentumStrategy` (strategies/features/momentum.py)
- [ ] 3.2 Update `EliteMeanReversionStrategy` (strategies/features/mean_reversion.py)
- [ ] 3.3 Update `BreakoutStrategy` (strategies/features/breakout.py)
- [ ] 3.4 Update `AggressiveStrategy` (strategies/features/aggressive.py)
- [ ] 3.5 Update `SafeStrategy` (strategies/features/safe.py)
- [ ] 3.6 Update `SmartMoneyStrategy` (strategies/features/smart_money.py)
- [ ] 3.7 Update `VolatilityBreakoutStrategy` (strategies/features/volatility_breakout.py)

## Phase 4: Update Strategy Manager
- [ ] 4.1 Wrap new StrategyManager in `EliteStrategyManager`
- [ ] 4.2 Add proper activation/deactivation methods
- [ ] 4.3 Implement health reporting
- [ ] 4.4 Add introspection methods

## Phase 5: Update Callers
- [ ] 5.1 Update `ai/elite_ai_controller.py` to use new architecture
- [ ] 5.2 Update `ai/elite_async_ai_controller.py` to use new architecture
- [ ] 5.3 Update any other callers

## Phase 6: Weighted Aggregation System
- [ ] 6.1 Implement weighted confidence scoring in StrategyManager
- [ ] 6.2 Implement ensemble voting mechanism
- [ ] 6.3 Add conflict resolution logic
- [ ] 6.4 Ensure all strategies are properly weighted

## Phase 7: Testing & Validation
- [ ] 7.1 Test all strategies can be registered
- [ ] 7.2 Test weighted aggregation works correctly
- [ ] 7.3 Test health checks
- [ ] 7.4 Test error handling and circuit breakers

---
## Notes
- All strategies should be weighted properly to avoid bias
- Backward compatibility should be maintained during transition
- Each strategy must return StrategyDecision objects
- The StrategyManager should aggregate all strategy decisions with proper weighting

