# Potential Blockers Analysis

## Critical Blockers Found

### 1. ⚠️ **USDC Address Missing for Most Chains** - CRITICAL

**Location**: `trading/execution/trade_executor.py:347-353`

**Problem**: 
- `_get_usdc_address()` only has 3 chains: ethereum, bsc, polygon
- But `main.py:get_usdc_address()` has USDC addresses for 40+ chains
- If a trade is attempted on any chain not in the executor's list, it will **FAIL** with "USDC address not found"

**Impact**: 
- Trades on arbitrum, optimism, avalanche, base, blast, cronos, gnosis, etc. will ALL FAIL
- This is a **critical blocker** for multi-network sniper functionality

**Fix Required**: Use the same USDC address mapping from `main.py` or share the function

---

### 2. ⚠️ **Execution Admission Controller - Supported Chains Check**

**Location**: `trading/execution/execution_admission_controller.py:161-164`

**Problem**:
- Checks if chain is in `self.supported_chains`
- If `execution_admission.supported_chains` is not configured or empty, **ALL chains will be blocked**

**Impact**: 
- Even if scanners discover tokens on all networks, trades will be rejected if chains aren't in the supported list

**Fix Required**: 
- If `supported_chains` is empty, allow all chains (true sniper mode)
- Or auto-populate from network_portfolios

---

### 3. ⚠️ **Execution Admission Controller - Router Deployment Check**

**Location**: `trading/execution/execution_admission_controller.py:226-230`

**Problem**:
- Checks if router is in `deployed_routers` for the chain
- If routers aren't configured, trades will be **BLOCKED**

**Impact**: 
- Even if routers exist and work, trades will fail if not in the deployment list

**Fix Required**: 
- Make router check optional or auto-detect available routers
- Or bypass check if `deployed_routers` is empty

---

### 4. ⚠️ **Position Manager - Hardcoded Max Positions**

**Location**: `position/position.py:289`

**Problem**:
- Hardcoded `max_positions = 10`
- Should come from config (risk_manager has `max_open_trades: 10`)
- If this limit is reached, new opportunities are rejected

**Impact**: 
- After 10 positions, no new trades can be opened
- This is reasonable but should be configurable

**Fix Required**: Read from config or risk_manager

---

### 5. ⚠️ **Position Size Calculation - Potential Too Small**

**Location**: `position/position.py:301-316`

**Problem**:
- Base position size: $100
- Suggested size = $100 * confidence
- If confidence is 0.4, size = $40
- Minimum is $50, so it gets bumped to $50
- But config has `min_trade_size: 0.005` (0.5% of portfolio = $1 for $200 portfolio)

**Impact**: 
- Position sizes might be too small to be profitable after gas
- Or might be rejected by minimum notional checks

**Fix Required**: Align position sizing with config and ensure profitability

---

### 6. ⚠️ **Minimum Notional Check**

**Location**: `trading/execution/execution_admission_controller.py:183-190`

**Problem**:
- Checks if trade amount is above `minimum_notional_usd` for the chain
- If not configured, this check passes (None check)
- But if configured too high, small trades will be blocked

**Impact**: 
- Small position sizes might be rejected

**Fix Required**: Ensure minimum notional is reasonable or not set too high

---

### 7. ⚠️ **Risk Manager - Portfolio State Not Updated**

**Location**: `risk/risk_manager.py:186-194`

**Problem**:
- Portfolio state is initialized but may not be updated after trades
- `daily_trades` counter may not reset
- `current_exposure` may not be updated
- This could cause false rejections

**Impact**: 
- After a few trades, risk manager might think limits are exceeded when they're not
- Daily trade limit might block all trades after first day

**Fix Required**: Ensure portfolio state is properly updated after each trade

---

### 8. ⚠️ **Suggested Size = 0 Check**

**Location**: `main.py:297`

**Problem**:
- If `suggested_size` is 0, trade will still proceed
- But amount_in will be 0, which might cause execution errors

**Impact**: 
- Trades with $0 size might attempt to execute and fail

**Fix Required**: Skip trade if suggested_size is 0

---

## Summary of Critical Issues

1. **USDC Address Missing** - BLOCKS trades on 37+ chains
2. **Supported Chains Check** - BLOCKS trades if not configured
3. **Router Deployment Check** - BLOCKS trades if not configured
4. **Portfolio State Not Updated** - Causes false rejections over time
5. **Position Size Too Small** - May cause execution failures

## Priority Fixes

1. **IMMEDIATE**: Fix USDC address mapping in trade_executor
2. **IMMEDIATE**: Make execution admission checks more permissive for sniper mode
3. **HIGH**: Fix portfolio state updates
4. **MEDIUM**: Fix position size calculation
5. **LOW**: Make max_positions configurable
