# Scanner Investigation: Why No Tokens Are Being Found

**Date:** January 2025  
**Investigator:** Independent Analysis  
**Purpose:** Investigate root causes of scanners failing to find tokens based on actual codebase review

---

## Executive Summary

After conducting an independent investigation of the scanner codebase, several issues have been identified that explain why no tokens are being found. These range from configuration validation errors to architectural issues in the scanning pipeline.

---

## Actual Scanner Files Present

Based on directory listing of `/home/damien/ecosystem/scanners/`:

| File | Location | Status |
|------|----------|--------|
| DexScreenerScanner | `scanners/discovery/dex_screener_scanner.py` | ✅ Production-ready |
| MempoolScannerUltra | `scanners/discovery/mempool_scanner.py` | ✅ All P0/P1/P2 fixes applied |
| OnChainScannerUltra | `scanners/discovery/onchain_scanner.py` | ✅ All P0/P1/P2 fixes applied |
| TokenAnalyzerScanner | `scanners/discovery/token_analyzer_scanner.py` | ⚠️ Needs network_manager |
| ScanDirector | `scanners/scan_director.py` | ⚠️ Multiple issues |
| BaseScanner | `scanners/base_scanner.py` | ✅ OK |

**Note:** `dexscreener_ultra_scanner.py` does NOT exist in the discovery folder. It is only in `experimental/` subfolder.

---

## Root Causes Identified

### 1. MempoolScannerUltra Configuration Validation (CRITICAL)

**File:** `scanners/discovery/mempool_scanner.py`

The scanner requires explicit configuration or it will fail during initialization:

```python
REQUIRED_CONFIG_KEYS = ['min_whale_value', 'min_mev_profit', 'min_arb_profit', 'max_slippage']

def __init__(self, config: Optional[Dict] = None, ...):
    # ✅ P0.1 FIX - Proper config validation
    if not config:
        raise ValueError("Mempool scanner requires explicit configuration")
    
    missing_keys = [key for key in self.REQUIRED_CONFIG_KEYS if key not in config]
    if missing_keys:
        raise ValueError(f"Mempool scanner missing required config keys: {missing_keys}")
```

**Impact:** If the scanner is instantiated without proper config, it raises `ValueError` and fails to initialize, returning no tokens.

**Affected Chains:** The scanner only supports chains defined in `CHAIN_GAS_CONFIG`:
```python
CHAIN_GAS_CONFIG = {
    'ethereum': {...},
    'base': {...},
    'arbitrum': {...},
    'optimism': {...},
    'polygon': {...},
}
```

If a chain is not in this config, the scanner returns empty list:
```python
async def _scan_network_impl(self, chain: str) -> List[Dict]:
    if chain not in CHAIN_GAS_CONFIG:
        logger.debug(f"Mempool scanner does not support chain: {chain}")
        return []  # Returns empty!
```

---

### 2. OnChainScannerUltra RPC Requirements

**File:** `scanners/discovery/onchain_scanner.py`

The scanner requires specific network configuration to function:

```python
async def _get_web3(self, chain: str) -> Web3:
    conf = self.network_config.get(chain, {})
    rpc = conf.get('rpc')
    if not rpc:
        raise ValueError(f"No RPC for {chain}")
```

**Token Discovery Method:**
```python
async def _discover_tokens_via_logs(self, web3: Web3, chain: str, 
                                   lookback: int = 50) -> List[str]:
    """P1 FIX: Use eth_getLogs instead of filters"""
    factory = self.network_config.get(chain, {}).get('factory_v2')
    weth = self.network_config.get(chain, {}).get('weth')
    
    if not factory or not weth:
        return []  # Returns empty!
```

**Impact:** If `factory_v2` or `weth` addresses are not configured for a chain, no tokens will be discovered.

---

### 3. TokenAnalyzerScanner Missing Dependencies

**File:** `scanners/discovery/token_analyzer_scanner.py`

This scanner has a critical dependency issue:

```python
async def initialize(self) -> None:
    # Use the network_manager that should be set during construction
    if not hasattr(self, 'network_manager') or not self.network_manager:
        logger.warning("No network_manager available to TokenAnalyzerScanner")
        return  # Early return - scanner won't work!
    
    if not self.web3_connections:
        logger.error("No Web3 connections established")
        return  # Early return - scanner won't work!
```

**Impact:** If `network_manager` is not properly injected during construction, the scanner initializes but returns no tokens.

---

### 4. ScanDirector Capability Gating

**File:** `scanners/scan_director.py`

The `_check_scanner_capability_gating()` method can disable scanners:

```python
def _check_scanner_capability_gating(self, scanner_name: str) -> bool:
    # Check token availability first
    if hasattr(self.memory, 'get_token_availability_status'):
        token_status = self.memory.get_token_availability_status()
        
        # Allow scanners to run even without tokens for discovery scanners
        discovery_scanners = ['dex_screener', 'onchain_scanner_ultra', 'mempool_scanner']
        if scanner_name not in discovery_scanners:
            if not token_status.get('has_tokens', False):
                logger.warning(f"Scanner {scanner_name} disabled: No tokens available in memory")
                return False  # Scanner disabled!
```

**Impact:** Non-discovery scanners are disabled if memory has no tokens, which is expected for a fresh start.

---

### 5. Scanner Timeout Configuration

**File:** `scanners/scan_director.py`

Default timeout may be too aggressive:

```python
self.per_scanner_timeout_s = float(scanner_cfg.get("scan_scanner_timeout_s", 30.0))

# In _scan_single_chain:
scanner_results = await asyncio.gather(
    *[asyncio.wait_for(task, timeout=self.per_scanner_timeout_s) for task in tasks],
    return_exceptions=True
)
```

**Impact:** Complex scanners like OnChainScannerUltra may timeout and return empty results.

---

### 6. Network Availability Check

**File:** `scanners/scan_director.py`

If no networks are available, scanners won't run:

```python
def _get_enabled_networks(self) -> List[str]:
    # Fallback to network manager with clients
    if hasattr(self.network_manager, "clients") and self.network_manager.clients:
        all_networks = list(self.network_manager.clients.keys())
        return all_networks
    
    # No working network clients - cannot scan anything
    logger.error("❌ No working network clients available - scanners cannot operate")
    return []  # Returns empty list!
```

**Impact:** If RPC endpoints fail or network manager initialization fails, no networks are scanned.

---

### 7. Silent Error Handling in Scanner Results

**File:** `scanners/scan_director.py`

Exceptions are caught and logged, but return empty results:

```python
if isinstance(result, Exception):
    logger.error(f"❌ {scanner_name} failed on {chain}: {error_msg}", exc_info=result)
    self.scanner_health[scanner_name]['consecutive_failures'] += 1
    # Scanner disabled after 5 consecutive failures
    if self.scanner_health[scanner_name]['consecutive_failures'] >= 5:
        self.scanner_health[scanner_name]['disabled'] = True
```

**Impact:** Scanner failures don't propagate up; they just return empty lists.

---

### 8. MempoolScannerUltra Event Separation

**File:** `scanners/discovery/mempool_scanner.py`

The scanner explicitly separates MEV events from token data:

```python
async def _scan_network_impl(self, chain: str) -> List[Dict]:
    """✅ P0.2 + P2.8 FIX: Real tokens only, MEV as separate events"""
    # Only extracts REAL tokens from whale transactions
    tokens = []
    
    for tx in snapshot.whale_txs:
        if tx.affected_tokens:
            for token_addr in tx.affected_tokens:
                token_data = {...}
                tokens.append(token_data)
    
    # Store only real tokens, NOT MEV events
    # MEV events go to self.mev_opportunities (separate)
    
    return tokens
```

**Impact:** MEV opportunities are NOT returned as tokens - they're stored separately.

---

### 9. OnChainScannerUltra Confidence-Based Filtering

**File:** `scanners/discovery/onchain_scanner.py`

The scanner filters tokens based on confidence levels:

```python
token.price_confidence: MetricConfidence = MetricConfidence.UNAVAILABLE

# In _convert_to_dict:
"price_confidence": token.price_confidence.value,
"liquidity_confidence": token.liquidity.total_liquidity_confidence.value,
```

**Impact:** Tokens with `UNAVAILABLE` confidence may be filtered out by downstream processing.

---

### 10. Scanner Initialization Order Issues

**File:** `scanners/scan_director.py`

Scanners are initialized after creation:

```python
# Initialize individual scanners
for scanner in self.scanners:
    try:
        if hasattr(scanner, "initialize") and callable(scanner.initialize):
            await scanner.initialize()  # May fail here
        logger.info(f"✅ Scanner ready: {scanner.__class__.__name__}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize {scanner.__class__.__name__}: {e}", exc_info=True)
        # Scanner continues even if initialization fails!
```

**Impact:** Scanner initialization failures are logged but the scanner still runs (and fails silently).

---

## Scanner Complexity Analysis

| Scanner | Lines | Complexity | Risk Level |
|---------|-------|------------|------------|
| MempoolScannerUltra | ~1000+ | High | Medium |
| OnChainScannerUltra | ~800+ | High | Medium |
| DexScreenerScanner | ~900+ | Medium | Low |
| TokenAnalyzerScanner | ~200 | Low | High (deps) |

---

## Configuration Analysis

From `config/config_unified.yaml`, scanner configuration:

```yaml
scanners:
  dex_screener:
    enabled: true
    min_liquidity: 50000.0
    min_volume: 10000.0
    min_age_hours: 1.0
    
  mempool_scanner:
    enabled: true
    min_whale_value: 100000        # USD - HIGH THRESHOLD
    min_mev_profit: 500             # USD - HIGH THRESHOLD
    min_arb_profit: 250             # USD - HIGH THRESHOLD
    
  onchain_scanner_ultra:
    enabled: true
    min_price_difference_pct: 1.0
    
  token_analyzer:
    enabled: true
    min_market_cap: 1000000         # $1M - HIGH THRESHOLD
    min_holders: 100
```

**Potential Issues:**
- High `min_whale_value` (100k USD) filters out most whale transactions
- High `min_mev_profit` (500 USD) filters out most MEV opportunities
- High `min_market_cap` (1M USD) filters out new tokens
- No fallback mechanism when primary scanners fail

---

## Recommended Fixes

### P0 - Critical (Immediate)

1. **Fix MempoolScannerUltra configuration:**
   - Ensure config is always passed during construction
   - Add default values for optional config keys

2. **Fix OnChainScannerUltra RPC config:**
   - Ensure all chains have `factory_v2` and `weth` addresses configured
   - Add fallback discovery method for chains without factory config

3. **Fix TokenAnalyzerScanner dependency injection:**
   - Ensure `network_manager` is always passed to scanner
   - Add graceful fallback when network_manager unavailable

### P1 - High Priority

1. **Lower threshold values:**
   - Reduce `min_whale_value` from 100k to 10k USD
   - Reduce `min_mev_profit` from 500 to 50 USD
   - Reduce `min_market_cap` from 1M to 100k USD

2. **Add scanner health monitoring:**
   - Log when scanners return empty results
   - Alert when scanners timeout repeatedly
   - Track scanner success/failure rates

3. **Improve error propagation:**
   - Don't silently swallow scanner exceptions
   - Return error tokens instead of empty lists
   - Add error details to scan results

### P2 - Medium Priority

1. **Add comprehensive logging:**
   - Log token counts at each processing stage
   - Log network/client availability
   - Log threshold filtering decisions

2. **Add scanner fallback:**
   - Try multiple scanners if one fails
   - Use cached data if live scanning fails
   - Degrade gracefully under failure conditions

3. **Review timeout configuration:**
   - Increase timeout for complex scanners
   - Add per-scanner timeout configuration
   - Implement adaptive timeout based on chain activity

---

## Diagnostic Steps

To diagnose scanner issues in a running system:

```bash
# 1. Check scanner initialization
grep -E "Scanner ready|Failed to initialize" logs/*.log

# 2. Check for configuration errors
grep -E "missing required|No RPC|No network" logs/*.log

# 3. Check token counts
grep -E "tokens found|found .* tokens" logs/*.log

# 4. Check timeout errors
grep -E "timeout|TimeoutError" logs/*.log

# 5. Check network availability
grep -E "No working network|No enabled networks" logs/*.log
```

---

## Files Reviewed

| File | Path | Status |
|------|------|--------|
| ScanDirector | `/home/damien/ecosystem/scanners/scan_director.py` | Reviewed |
| DexScreenerScanner | `/home/damien/ecosystem/scanners/discovery/dex_screener_scanner.py` | Reviewed |
| MempoolScannerUltra | `/home/damien/ecosystem/scanners/discovery/mempool_scanner.py` | Reviewed |
| OnChainScannerUltra | `/home/damien/ecosystem/scanners/discovery/onchain_scanner.py` | Reviewed |
| TokenAnalyzerScanner | `/home/damien/ecosystem/scanners/discovery/token_analyzer_scanner.py` | Reviewed |
| BaseScanner | `/home/damien/ecosystem/scanners/base_scanner.py` | Reviewed |
| Configuration | `/home/damien/ecosystem/config/config_unified.yaml` | Reviewed |
| Main Entry | `/home/damien/ecosystem/main.py` | Reviewed |

---

## Conclusion

The scanner suite has several issues preventing token discovery:

1. **Configuration Issues** - MempoolScannerUltra requires explicit config or fails
2. **Missing Dependencies** - TokenAnalyzerScanner needs network_manager injection
3. **RPC Configuration** - OnChainScannerUltra needs factory/weth addresses for each chain
4. **High Thresholds** - Default thresholds filter out most opportunities
5. **Silent Failures** - Scanner errors return empty results instead of propagating
6. **Event Separation** - MEV events are not returned as tokens

**Immediate Action Required:**
1. Verify all scanners receive proper configuration
2. Lower threshold values for better token discovery
3. Add comprehensive logging to track scanner health
4. Implement error propagation instead of silent failures

---

**Report Generated:** January 2025  
**Next Review:** After P0 fixes are implemented

