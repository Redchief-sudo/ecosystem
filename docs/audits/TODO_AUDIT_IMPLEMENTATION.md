# Audit Implementation Plan

## Core Problems to Fix

### 1. Mixing EVM and Non-EVM Address Formats
- Introduce TokenIdentifier model with chain-aware validation
- Add CHAIN_IDENTIFIER_TYPES registry
- Update TokenCandidate to use strict chain-specific validation
- Remove lenient fallback address acceptance

### 2. Awaiting Non-Async Strategy Calls
- Enforce async contract in BaseStrategy.evaluate()
- Add runtime checks for awaitable returns
- Update strategy manager to handle async properly

### 3. Strategies Executed Without Configuration
- Enforce config injection at strategy initialization
- Fail fast on missing configs during boot
- Update compose.py to inject configs properly

## Implementation Steps

1. [ ] Update token_candidate.py with TokenIdentifier model
2. [ ] Add chain-aware validation functions
3. [ ] Update TokenCandidate to use new validation
4. [ ] Enforce async contract in BaseStrategy
5. [ ] Update strategy initialization in compose.py
6. [ ] Test the changes
