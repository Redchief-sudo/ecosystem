# AI Module Refactoring Plan
## Creating ai/ folder structure to mirror risk/ folder

## Current Risk Folder Structure:
```
risk/
├── __init__.py
├── limits.py
├── risk_manager.py
├── risk_policy.py
└── risk_verdict.py
```

## Target AI Folder Structure:
```
ai/
├── __init__.py
├── base_ai.py (keep)
├── neural_brain.py (keep)
├── token_scoring_service.py (keep)
├── elite_async_ai_controller.py (keep)
├── performance_tracker.py (keep)
├── weight_monitoring_dashboard.py (keep)
├── check_opportunities.py (keep)
├── ml/ (keep)
├── position/
│   ├── __init__.py
│   ├── position_ai.py      (NEW - Manager)
│   ├── position_policy.py  (NEW - Policy)
│   └── position_verdict.py (NEW - Verdict)
├── entry/
│   ├── __init__.py
│   ├── entry_ai.py         (MOVE from ai/entry_ai.py)
│   ├── entry_policy.py     (NEW - Policy)
│   └── entry_verdict.py    (NEW - Verdict)
└── exit/
    ├── __init__.py
    ├── exit_ai.py          (MOVE from ai/exit_ai.py)
    ├── exit_policy.py      (NEW - Policy)
    └── exit_verdict.py     (NEW - Verdict)
```

## Files to Create:
1. ai/position/__init__.py
2. ai/position/position_ai.py
3. ai/position/position_policy.py
4. ai/position/position_verdict.py
5. ai/entry/__init__.py
6. ai/entry/entry_policy.py
7. ai/entry/entry_verdict.py
8. ai/exit/__init__.py
9. ai/exit/exit_policy.py
10. ai/exit/exit_verdict.py

## Files to Move:
1. ai/entry_ai.py -> ai/entry/entry_ai.py
2. ai/exit_ai.py -> ai/exit/exit_ai.py

## Files to Update:
1. ai/__init__.py - update imports
2. ai/elite_async_ai_controller.py - update imports

