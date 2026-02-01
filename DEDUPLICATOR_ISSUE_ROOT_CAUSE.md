# CRITICAL ISSUE: Token Deduplication is Blocking All Trading

## Problem

**Opportunity queue size: 0** because NO tokens reach the AI Controller

The pipeline is:
```
Scanner finds tokens
  ↓
MultiChainDeduplicator.add_tokens()
  ↓ [BLOCKING HERE - all tokens marked as duplicates]
  ↓
MultiChainIngestion.enqueue to decision_queue
  ↓
EliteAsyncAIController.select_strategy()
  ↓
Opportunities emitted
```

## Root Cause

The `MultiChainDeduplicator` has a 1-hour TTL (3600 seconds):
- First scan: Finds tokens WETH, USDC, etc. → marks them in `seen_identities`
- Subsequent scans (same hour): Finds same tokens again → marked as **duplicates** and filtered out
- Result: After first scan, NO tokens are processed for the next hour

From logs (14:39:53):
```
Duplicate market found: ethereum:prjx:0x6c9a33e3b592c0d65b3ba59355d5be0d38259285 from scan_director
Duplicate market found: ethereum:prjx:0x6c9a33e3b592c0d65b3ba59355d5be0d38259285 from scan_director
Duplicate market found: ethereum:prjx:0x6c9a33e3b592c0d65b3ba59355d5be0d38259285 from scan_director
```

Every token the scanner finds gets marked as a duplicate.

## Code Location

File: `/home/damien/ecosystem/trading/token_pipeline/multi_chain_deduplicator.py`

```python
class MultiChainTokenDeduplicator:
    def __init__(self, ttl_seconds: int = 3600):  # ← 1 hour TTL
        self.seen_identities: Set[TokenIdentity] = set()
        self.ttl_seconds = ttl_seconds  # ← Tokens stay for 3600 seconds
    
    def is_duplicate(self, identity: TokenIdentity) -> bool:
        if identity in self.seen_identities:  # ← Already seen? Mark as duplicate
            return True
        self.seen_identities.add(identity)  # ← Never forget
        return False
    
    def _cleanup_expired_tokens(self):
        """Remove tokens older than TTL"""
        if current_time - self.last_cleanup < 300:  # Only cleanup every 5 min
            return  # ← But cleanup only happens every 5 minutes
```

## Why Deduplication Exists

It's designed to prevent the SAME opportunity from being reprocessed multiple times. But it's too aggressive:

- **Problem it solves**: "Don't buy the same token twice in 1 hour"
- **Problem it creates**: "Can't even process the same token once if another scanner found it too"

## Solution

Reduce the TTL from 3600 seconds (1 hour) to something reasonable:

**Option A: Process each token once per trading cycle (e.g., 30-60 seconds)**
```python
def __init__(self, ttl_seconds: int = 60):  # 60 seconds instead of 3600
```

**Option B: Use per-window deduplication**
```python
# Deduplicate only within a 30-second trading window
# Reset deduplicator at start of each trading cycle
```

**Option C: Chain-based + time-based deduplication**
```python
# Deduplicate per (chain, symbol) pair, not globally
# Allow same token on different chains
# But prevent reprocessing same (chain, symbol) within TTL
```

## Recommended Fix

**Shortest path to trading**: Reduce TTL to 60 seconds.

This allows:
- Scanners running at different times to find the same token ✅
- Same token being reprocessed every minute (reasonable for active trading) ✅
- Memory growth (expires after 1 minute) ✅

### Code Change

File: `/home/damien/ecosystem/trading/token_pipeline/multi_chain_ingestion.py` (line 32)

```python
# BEFORE:
self.deduplicator = MultiChainTokenDeduplicator()

# AFTER:
self.deduplicator = MultiChainTokenDeduplicator(ttl_seconds=60)  # 60 sec instead of 3600
```

## Impact

After fix:
- Scanners find tokens at 14:39:50, 14:39:55, 14:40:00, etc.
- All instances are processed (not marked as duplicates)
- Each token can be evaluated by strategy every trading cycle
- Opportunities actually appear in queue ✅
- Entry Manager can score them ✅
- Trades can execute ✅

## Verification

After applying fix:
1. Run trading system
2. Check logs for: `Successfully processed token:`  (should see 6+ tokens)
3. Check logs for: `Opportunity emitted:` (should see opportunities)
4. Check: `opportunity queue size:` (should be > 0)
5. Trades should execute

---

**NOTE**: Pre-enrichment IS working (tested successfully), but it never gets called because tokens don't reach the AI Controller due to the deduplicator blocking them.
