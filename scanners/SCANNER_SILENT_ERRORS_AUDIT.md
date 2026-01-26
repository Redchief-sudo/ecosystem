# Scanner Suite Silent Errors Audit

**Date:** January 2025  
**Purpose:** Identify and document silent errors in the scanner suite that may cause unexpected behavior without clear error messages

---

## Executive Summary

The scanner suite consists of multiple scanners that work together to discover and evaluate tokens. This audit identifies several potential silent errors that could cause scanners to fail quietly without proper error handling or logging.

---

## 1. CoinMarketCap Scanner Status

**Status:** REMOVED from scanner suite  
**Action Required:** Clean up any stale references

### Finding: `scanners/coinmarketcap_scanner.py` still exists but is no longer used

```
File: /home/damien/ecosystem/scanners/coinmarketcap_scanner.py
Issue: File exists but is not imported or used by ScanDirector
```

**Impact:** Low - file is orphaned but doesn't affect system  
**Recommendation:** Remove the file to avoid confusion

---

## 2. DexScreenerUltraScanner Silent Errors

**File:** `/home/damien/ecosystem/scanners/discovery/dexscreener_ultra_scanner.py`

### Error 2.1: Missing `MIN_MEV_PROFIT` constant
```python
# Line ~377 - Referenced but never defined
if expected_profit - gas_cost > self.MIN_MEV_PROFIT:
```
**Issue:** `self.MIN_MEV_PROFIT` is referenced in `_analyze_mev_opportunity()` but never defined in `__init__()`  
**Impact:** Will raise `AttributeError` when MEV opportunity is detected  
**Severity:** HIGH (will crash on MEV detection)

### Error 2.2: `_analyze_gas_intelligence` method undefined
```python
# Line ~594 - Method called but never defined
gas_prediction = self._analyze_gas_intelligence(tx)
```
**Issue:** `self._analyze_gas_intelligence()` is called in `get_snapshot()` but method doesn't exist  
**Impact:** Will raise `AttributeError` when getting snapshot  
**Severity:** MEDIUM (crashes when generating snapshot)

### Error 2.3: `market_urgency` attribute undefined in snapshot
```python
# Line ~618 - Attribute accessed but never set
print(f"   Market Urgency: {snapshot.market_urgency:.2%}")
```
**Issue:** `market_urgency` attribute is accessed on `MempoolSnapshot` but never defined in dataclass  
**Impact:** Will raise `AttributeError` when accessing  
**Severity:** MEDIUM

### Error 2.4: `opportunity_type` attribute missing in MEV opportunity dict
```python
# Line ~104 - Key doesn't match dataclass attribute
'token_address': opp.token_address  # But MEVOpportunity has no token_address
'token_a': opp.token_a  # But MEVOpportunity has no token_a/token_b
'opportunity_type': opp.opportunity_type  # But MEVOpportunity has no opportunity_type
```
**Issue:** Dictionary keys reference non-existent dataclass attributes  
**Impact:** Will raise `AttributeError` when creating token_data  
**Severity:** HIGH (MEV scanner output will crash)

### Error 2.5: `opp.token_a` / `opp.token_b` missing
```python
# Line ~107-108
'token_a': opp.token_a,
'token_b': opp.token_b,
```
**Issue:** `ArbitrageOpportunity` has `buy_pool` and `sell_pool` but no `token_a`/`token_b`  
**Impact:** Will raise `AttributeError`  
**Severity:** HIGH (arbitrage output will crash)

---

## 3. DexScreenerScanner Silent Errors

**File:** `/home/damien/ecosystem/scanners/dex_screener_scanner.py`

### Error 3.1: Uninitialized `_ai_controller` attribute
```python
# Line ~53 - Attribute set via hasattr check but never initialized
if hasattr(self, '_ai_controller') and self._ai_controller:
```
**Issue:** `_ai_controller` is never set in `__init__()` or `initialize()`  
**Impact:** AI scoring will silently be skipped even if AI controller is available  
**Severity:** LOW (AI scoring will just be skipped)

### Error 3.2: `_ai_controller.score_token` method may not exist
```python
# Line ~184 - Method called without verification
ai_score = await self._ai_controller.score_token(token)
```
**Issue:** Calls `score_token()` but doesn't verify method exists or signature  
**Impact:** Will raise `AttributeError` or `TypeError` if method doesn't exist  
**Severity:** MEDIUM

### Error 3.3: Missing `ai_score` in tokens before filtering
```python
# Line ~204
if token.get('ai_score', 0) < self.config['ai_score_threshold']:
```
**Issue:** Filters by `ai_score` but `_apply_ai_scoring()` may silently fail or not be called  
**Impact:** All tokens filtered out if AI scoring fails  
**Severity:** LOW (explicit check with default value)

---

## 4. AIDiscoveryScanner Silent Errors

**File:** `/home/damien/ecosystem/scanners/discovery/ai_discovery_scanner.py`

### Error 4.1: `_use_fallback_scoring` set but attribute may not exist
```python
# Line ~49
else:
    self._use_fallback_scoring = False
# Line ~77
if hasattr(self, '_use_fallback_scoring') and self._use_fallback_scoring:
```
**Issue:** `_use_fallback_scoring` is set conditionally but accessed unconditionally  
**Impact:** May cause unexpected behavior  
**Severity:** LOW (hasattr check protects)

### Error 4.2: `token.last_updated.timestamp()` may fail
```python
# Line ~95
if token.last_updated and (current_time - int(token.last_updated.timestamp())) > 3600:
```
**Issue:** `last_updated` may be a string or datetime, and `timestamp()` only exists on datetime objects  
**Impact:** Will raise `AttributeError` if `last_updated` is not a datetime object  
**Severity:** MEDIUM

### Error 4.3: TokenMetadata attribute access on objects
```python
# Line ~83-86 - Assumes TokenMetadata objects with specific attributes
liquidity = float(token.liquidity_usd or 0)
volume = float(token.volume_24h or 0)
price = float(token.price or 0)
symbol = token.symbol or "UNKNOWN"
```
**Issue:** Assumes `TokenMetadata` objects but `get_recent_tokens()` may return different types  
**Impact:** Will raise `AttributeError` if attributes don't exist  
**Severity:** HIGH

### Error 4.4: `token.market_cap` may not exist
```python
# Line ~140
'market_cap': token.market_cap if hasattr(token, 'market_cap') else None,
```
**Issue:** Uses `hasattr()` but earlier code assumes attributes exist  
**Impact:** Inconsistent error handling  
**Severity:** LOW (handled with hasattr)

---

## 5. MempoolScannerUltra Silent Errors

**File:** `/home/damien/ecosystem/scanners/discovery/mempool_scanner.py`

### Error 5.1: `self._background_tasks` never initialized
```python
# Line ~226 - Used in start() but never defined
self._background_tasks.add(task)
task.add_done_callback(self._background_tasks.discard)
```
**Issue:** `self._background_tasks` is used but never initialized in `__init__()`  
**Impact:** Will raise `AttributeError` when starting scanner  
**Severity:** HIGH

### Error 5.2: `self.MIN_MEV_PROFIT` referenced but not defined
```python
# Line ~377
if expected_profit - gas_cost > self.MIN_MEV_PROFIT:
```
**Issue:** Same as DexScreenerUltraScanner - constant never defined  
**Impact:** Will raise `AttributeError`  
**Severity:** HIGH

### Error 5.3: Undefined `tx` parameter in `_analyze_gas_intelligence`
```python
# Line ~594
gas_prediction = self._analyze_gas_intelligence(tx)
```
**Issue:** Method `self._analyze_gas_intelligence()` doesn't exist  
**Impact:** Will raise `AttributeError`  
**Severity:** MEDIUM

---

## 6. EnhancedOnchainScanner Silent Errors

**File:** `/home/damien/ecosystem/scanners/discovery/enhanced_onchain_scanner.py`

### Error 6.1: Missing `timezone` import
```python
# Line ~11
from datetime import datetime, timedelta
# Used later:
created_at=datetime.now(timezone.utc)
```
**Issue:** `timezone` is used but not imported  
**Impact:** Will raise `NameError` at runtime  
**Severity:** HIGH

### Error 6.2: `scan_network` returns `List[ScannedToken]` but docstring says `List[ScannedToken]`
```python
# Line ~227 - Return type annotation says List[ScannedToken] but actually returns list of dicts
async def scan_network(self, network: str) -> List[ScannedToken]:
    ...
    return tokens  # But tokens are dicts from _create_scanned_token().to_dict()
```
**Issue:** Type annotation doesn't match actual return type  
**Impact:** Type checking may give false results, downstream code may fail  
**Severity:** LOW

### Error 6.3: `_create_scanned_token` returns `ScannedToken.to_dict()` but docstring says `ScannedToken`
```python
# Line ~358
def _create_scanned_token(...) -> ScannedToken:
    return ScannedToken(...).to_dict()  # Returns dict, not ScannedToken
```
**Issue:** Return type annotation doesn't match actual return type  
**Impact:** Type checking issues, downstream code expecting ScannedToken may fail  
**Severity:** LOW

### Error 6.4: `TokenInfo` dataclass used but not returned
```python
# _get_token_info returns a dict, not a TokenInfo object
async def _get_token_info(...) -> Optional[TokenInfo]:
    return {...}  # Returns dict, not TokenInfo
```
**Issue:** Type annotation says `TokenInfo` but returns dict  
**Impact:** Type checking issues, IDE warnings, potential runtime errors  
**Severity:** LOW

### Error 6.5: `_get_pair_abi` returns list but should return dict
```python
# Line ~424
def _get_pair_abi(self):
    return [...]  # Returns list (ABI), but called expecting contract
```
**Issue:** Method returns raw ABI list, not a Contract object  
**Impact:** Code that expects a Contract will fail  
**Severity:** MEDIUM

---

## 7. ScanDirector Silent Errors

**File:** `/home/damien/ecosystem/scanners/scan_director.py`

### Error 7.1: Hybrid scanner class path may not exist
```python
# Line ~42
"hybrid_scanner": "scanners.hybrid_scanner.EliteHybridScanner",
```
**Issue:** `scanners/hybrid_scanner.py` may not exist (error shown earlier)  
**Impact:** Scanner will fail to load  
**Severity:** MEDIUM

### Error 7.2: `scan_network` wrapper doesn't pass through kwargs
```python
# Line ~88
async def _scan_network_wrapper(self, chain):
    return await self.scan(chain)  # Doesn't pass *args or **kwargs
```
**Issue:** Wrapper doesn't forward additional arguments to `scan()`  
**Impact:** Additional parameters may be silently ignored  
**Severity:** LOW

### Error 7.3: Memory commit after scan may fail silently
```python
# Line ~158
try:
    self.memory.conn.commit()
except Exception as e:
    logger.warning(f"Memory sync failed: {e}")
```
**Issue:** Commit failure only logged as warning, not propagated  
**Impact:** Token data may not be persisted but no error raised  
**Severity:** MEDIUM

---

## 8. ScannerBase Silent Errors

**File:** `/home/damien/ecosystem/scanners/base_scanner.py`

### Error 8.1: `get_effective_thresholds()` requires explicit config
```python
# Line ~44-52
thresholds = {
    'min_liquidity': FieldValidator.require_field(self.config, 'min_liquidity', ...),
    'min_volume': FieldValidator.require_field(self.config, 'min_volume', ...),
    ...
}
```
**Issue:** Throws `ValueError` if config not set, but many scanners use default values  
**Impact:** Some scanners may fail if config not explicitly provided  
**Severity:** LOW (intentional strict validation)

---

## Priority Fixes

### P0 - Critical (Will Cause Crashes)

1. **DexScreenerUltraScanner:** Add `MIN_MEV_PROFIT = 0.01` (or appropriate value) to `__init__()`
2. **MempoolScannerUltra:** Add `self._background_tasks = set()` to `__init__()`
3. **MempoolScannerUltra:** Add `MIN_MEV_PROFIT` constant
4. **EnhancedOnchainScanner:** Add `from datetime import timezone` import
5. **DexScreenerUltraScanner:** Fix undefined `_analyze_gas_intelligence()` method
6. **DexScreenerUltraScanner:** Fix undefined `market_urgency` attribute

### P1 - High (May Cause Unexpected Behavior)

1. **DexScreenerUltraScanner:** Fix MEV opportunity dict keys to match dataclass
2. **DexScreenerUltraScanner:** Fix arbitrage opportunity dict keys
3. **AIDiscoveryScanner:** Fix `token.last_updated.timestamp()` handling
4. **EnhancedOnchainScanner:** Fix return type annotations

### P2 - Medium (Type Safety / Code Quality)

1. **DexScreenerScanner:** Initialize `_ai_controller` properly
2. **EnhancedOnchainScanner:** Fix `_get_pair_abi()` to return Contract
3. **ScanDirector:** Handle missing scanner class paths gracefully
4. **Clean up:** Remove orphaned `coinmarketcap_scanner.py`

---

## Testing Recommendations

1. Add unit tests for each scanner that verify:
   - `__init__()` sets all required attributes
   - Methods don't raise undefined attribute errors
   - Return types match type annotations

2. Add integration tests:
   - Test scanner initialization with mock memory/AI
   - Test scan methods with simulated API responses
   - Test error paths in `_process_tokens()`, `_apply_ai_scoring()`, etc.

3. Add type checking:
   - Run mypy on scanner files
   - Fix type annotation mismatches

---

## Appendix: Files Reviewed

| File | Path | Status |
|------|------|--------|
| DexScreenerUltraScanner | `/home/damien/ecosystem/scanners/discovery/dexscreener_ultra_scanner.py` | Multiple errors |
| DexScreenerScanner | `/home/damien/ecosystem/scanners/dex_screener_scanner.py` | Minor issues |
| MempoolScannerUltra | `/home/damien/ecosystem/scanners/mempool_scanner.py` | Multiple errors |
| AIDiscoveryScanner | `/home/damien/ecosystem/scanners/ai_discovery_scanner.py` | Minor issues |
| EnhancedOnchainScanner | `/home/damien/ecosystem/scanners/discovery/enhanced_onchain_scanner.py` | Multiple errors |
| ScanDirector | `/home/damien/ecosystem/scanners/scan_director.py` | Minor issues |
| ScannerBase | `/home/damien/ecosystem/scanners/base_scanner.py` | OK |
| coinmarketcap_scanner.py | `/home/damien/ecosystem/scanners/coinmarketcap_scanner.py` | REMOVED (orphaned) |

---

## Recommendations Summary

1. **Immediate:** Fix P0 issues to prevent runtime crashes
2. **Short-term:** Fix P1 issues to ensure correct behavior
3. **Medium-term:** Fix P2 issues for code quality and type safety
4. **Ongoing:** Add tests and type checking to prevent regressions

