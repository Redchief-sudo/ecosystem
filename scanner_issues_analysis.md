# Scanner Issues Analysis

## Overview
This document summarizes the issues identified in the scanner suite based on the SCANNER_SILENT_ERRORS_AUDIT.md audit.

## Issues by Scanner

### 1. CoinMarketCap Scanner
- **File:** scanners/coinmarketcap_scanner.py
- **Issue:** File exists but is not used by ScanDirector (orphaned).
- **Impact:** Low - no effect on system.
- **Recommendation:** Remove the file.

### 2. DexScreenerUltraScanner
- **File:** scanners/discovery/dexscreener_ultra_scanner.py
- **Issues:**
  - MIN_MEV_PROFIT constant referenced but not defined (AttributeError on MEV detection).
  - _analyze_gas_intelligence method called but doesn't exist (AttributeError in get_snapshot).
  - market_urgency attribute accessed but never set in MempoolSnapshot.
  - MEV opportunity dict keys (opportunity_type, token_a, token_b) don't match dataclass attributes.
- **Severity:** High - will cause crashes.

### 3. DexScreenerScanner
- **File:** scanners/dex_screener_scanner.py
- **Issues:**
  - _ai_controller attribute checked but never initialized (AI scoring silently skipped).
  - score_token method called without verifying existence (potential AttributeError/TypeError).
- **Severity:** Medium.

### 4. AIDiscoveryScanner
- **File:** scanners/discovery/ai_discovery_scanner.py
- **Issues:**
  - token.last_updated.timestamp() may fail if not datetime object.
  - Assumes TokenMetadata objects but may receive different types (AttributeError).
- **Severity:** High.

### 5. MempoolScannerUltra
- **File:** scanners/discovery/mempool_scanner.py
- **Issues:**
  - _background_tasks used but never initialized (AttributeError in start).
  - MIN_MEV_PROFIT constant referenced but not defined.
  - _analyze_gas_intelligence method called but doesn't exist.
- **Severity:** High.

### 6. EnhancedOnchainScanner
- **File:** scanners/discovery/enhanced_onchain_scanner.py
- **Issues:**
  - Missing timezone import (NameError).
  - Return type annotations don't match actual returns (dicts instead of objects).
  - _get_pair_abi returns list instead of Contract object.
- **Severity:** Medium to High.

### 7. ScanDirector
- **File:** scanners/scan_director.py
- **Issues:**
  - Hybrid scanner class path may not exist.
  - _scan_network_wrapper doesn't pass kwargs.
  - Memory commit failures logged as warnings only.
- **Severity:** Medium.

### 8. ScannerBase
- **File:** scanners/base_scanner.py
- **Issue:** get_effective_thresholds() requires explicit config (may fail some scanners).
- **Severity:** Low.

## Priority Fixes

### P0 - Critical (Will Cause Crashes)
1. Add MIN_MEV_PROFIT constants to DexScreenerUltraScanner and MempoolScannerUltra.
2. Initialize _background_tasks in MempoolScannerUltra.
3. Add timezone import to EnhancedOnchainScanner.
4. Implement missing _analyze_gas_intelligence methods.
5. Fix undefined attributes in DexScreenerUltraScanner.

### P1 - High (Unexpected Behavior)
1. Fix dict keys in MEV/arbitrage opportunities.
2. Handle token.last_updated properly in AIDiscoveryScanner.
3. Fix return types in EnhancedOnchainScanner.

### P2 - Medium (Code Quality)
1. Initialize _ai_controller properly in DexScreenerScanner.
2. Fix _get_pair_abi return type.
3. Handle missing scanner paths gracefully in ScanDirector.
4. Remove orphaned coinmarketcap_scanner.py.

## Recommendations
1. Fix P0 issues immediately to prevent crashes.
2. Add unit and integration tests for scanners.
3. Run type checking (mypy) and fix annotations.
4. Implement proper error handling and logging.
