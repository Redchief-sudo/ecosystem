# Token Data Enrichment Plan

## Problem

Other strategies (Momentum, MeanReversion, Breakout, etc.) return `None` because they require additional data fields that aren't available in scanned tokens.

### Data Fields Required by Strategies

| Field | Used By | Description |
|-------|---------|-------------|
| `price_history` | MACD, Bollinger, RSI | Array of historical prices |
| `volume_history` | Volume momentum | Array of historical volumes |
| `holder_concentration` | RiskCaps, Smart Money | Top holder percentage |
| `whale_activity` | Smart Money | Large transactions |
| `rugpull_risk` | Entry manager | Risk score (0-1) |
| `social_score` | Sentiment strategies | Social media sentiment |
| `order_book_imbalance` | Order flow | Bid/ask imbalance |
| `volume_profile` | Volume profile | Volume at price levels |
| `smart_money_flow` | Smart Money | Institutional flow |
| `market_regime` | Regime detection | Bull/bear/sideways |

### Current Token Data (from scanner)

```python
{
    'address': '0x...',
    'symbol': 'TOKEN',
    'name': 'Token Name',
    'price': 0.001,
    'volume_24h': 100000,
    'liquidity': 50000,
    'price_change_5m': 0.5,
    'price_change_1h': 2.3,
    'price_change_24h': -1.5,
    'chain': 'ethereum',
}
```

### Needed for All Strategies

```python
{
    # Current fields (keep)
    'address': '0x...',
    'symbol': 'TOKEN',
    'price': 0.001,
    'volume_24h': 100000,
    'liquidity': 50000,
    
    # NEW: Technical indicators
    'price_history': [0.001, 0.0011, 0.0009, ...],  # Last 20 prices
    'volume_history': [80000, 95000, 110000, ...],   # Last 20 volumes
    
    # NEW: Risk metrics
    'holder_concentration': 0.15,  # Top 10 holders / total
    'whale_activity': 0.3,          # Whale tx / total tx
    'rugpull_risk': 0.1,            # Risk score 0-1
    
    # NEW: Advanced metrics
    'social_score': 0.5,            # Twitter/Telegram sentiment
    'market_regime': 1,              # 0=sideways, 1=bull, 2=bear
    'smart_money_flow': 0.4,         # Institutional flow score
    
    # NEW: Order book (for advanced strategies)
    'bids': [0.0009, 0.00089, ...],  # Bid volumes
    'asks': [0.0011, 0.00112, ...],  # Ask volumes
}
```

---

## Solution Options

### Option 1: Simulate/Mock Missing Data (Quick Win)

Add a data enrichment service that generates synthetic data when real data isn't available:

```python
# In token_pipeline/token_enricher.py
class TokenEnricher:
    def enrich(self, token: Dict) -> Dict:
        # Generate price_history from current price + random walk
        token['price_history'] = self._generate_price_history(token['price'])
        
        # Generate volume_history from current volume
        token['volume_history'] = self._generate_volume_history(token['volume_24h'])
        
        # Estimate holder_concentration from liquidity (proxy)
        token['holder_concentration'] = min(0.5, 10000 / token['liquidity'])
        
        # Estimate social_score from price volatility
        token['social_score'] = self._estimate_social_sentiment(token)
        
        return token
```

### Option 2: Add Real Data Sources (Better)

1. **DexScreener API** - Already integrated, can get more fields
2. ** DEX RPC calls** - Query order book directly
3. **On-chain analysis** - Get holder data from blockchain
4. **Social APIs** - Twitter/Telegram sentiment

### Option 3: Hybrid Approach (Recommended)

Use mock data for development, real APIs for production.

---

## Implementation Plan

### Step 1: Create TokenEnricher Service

Create `/home/damien/ecosystem/trading/token_pipeline/token_enricher.py`:

```python
"""
Token enrichment service - adds missing data fields to tokens.
"""

import random
import logging
from typing import Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TokenEnricher:
    """
    Enriches token data with computed fields for strategy evaluation.
    
    Uses:
    - Current price/volume to generate historical data
    - Liquidity as proxy for holder concentration
    - Price volatility as proxy for social sentiment
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.price_history_length = self.config.get('price_history_length', 20)
        self.default_volatility = self.config.get('default_volatility', 0.02)
        
    def enrich(self, token: Dict) -> Dict:
        """Add computed fields to token data."""
        token = token.copy()  # Don't mutate original
        
        # Generate historical data
        if 'price_history' not in token:
            token['price_history'] = self._generate_price_history(
                token.get('price', 0)
            )
            
        if 'volume_history' not in token:
            token['volume_history'] = self._generate_volume_history(
                token.get('volume_24h', 0)
            )
            
        # Estimate risk metrics
        if 'holder_concentration' not in token:
            token['holder_concentration'] = self._estimate_holder_concentration(
                token.get('liquidity', 0)
            )
            
        if 'whale_activity' not in token:
            token['whale_activity'] = self._estimate_whale_activity(token)
            
        if 'rugpull_risk' not in token:
            token['rugpull_risk'] = self._estimate_rugpull_risk(token)
            
        # Estimate sentiment
        if 'social_score' not in token:
            token['social_score'] = self._estimate_social_sentiment(token)
            
        # Estimate market regime
        if 'market_regime' not in token:
            token['market_regime'] = self._estimate_market_regime(token)
            
        if 'smart_money_flow' not in token:
            token['smart_money_flow'] = self._estimate_smart_money_flow(token)
            
        # Estimate order book (for advanced strategies)
        if 'bids' not in token:
            token['bids'] = self._generate_order_book(token.get('price', 0), 'bid')
            
        if 'asks' not in token:
            token['asks'] = self._generate_order_book(token.get('price', 0), 'ask')
            
        # Estimate volume profile
        if 'volume_profile' not in token:
            token['volume_profile'] = self._estimate_volume_profile(token)
            
        logger.debug(f"Enriched token {token.get('symbol', 'UNKNOWN')}")
        return token
        
    def _generate_price_history(self, current_price: float) -> List[float]:
        """Generate synthetic price history using random walk."""
        if current_price <= 0:
            return [0.001] * self.price_history_length
            
        prices = [current_price]
        for _ in range(self.price_history_length - 1):
            change = random.gauss(0, self.default_volatility)
            new_price = prices[-1] * (1 + change)
            new_price = max(0.00000001, new_price)  # Prevent negative
            prices.append(new_price)
        return prices
        
    def _generate_volume_history(self, current_volume: float) -> List[float]:
        """Generate synthetic volume history."""
        if current_volume <= 0:
            return [1000] * self.price_history_length
            
        volumes = [current_volume]
        for _ in range(self.price_history_length - 1):
            change = random.uniform(-0.3, 0.5)  # Volume tends to increase
            new_vol = volumes[-1] * (1 + change)
            new_vol = max(100, new_vol)
            volumes.append(new_vol)
        return volumes
        
    def _estimate_holder_concentration(self, liquidity: float) -> float:
        """Higher liquidity = lower holder concentration (more distributed)."""
        if liquidity <= 0:
            return 0.5  # Unknown, assume moderate
        # Proxy: $1M+ liquidity = ~10% concentration, <$10k = ~50%
        if liquidity > 1_000_000:
            return 0.10
        elif liquidity > 100_000:
            return 0.20
        elif liquidity > 10_000:
            return 0.35
        else:
            return 0.50
            
    def _estimate_whale_activity(self, token: Dict) -> float:
        """Estimate whale activity from volume and liquidity."""
        volume = token.get('volume_24h', 0)
        liquidity = token.get('liquidity', 0)
        
        if volume <= 0 or liquidity <= 0:
            return 0.3
            
        # High volume relative to liquidity suggests whale activity
        ratio = volume / liquidity
        return min(0.8, max(0.1, ratio * 0.5))
        
    def _estimate_rugpull_risk(self, token: Dict) -> float:
        """Estimate rugpull risk from token characteristics."""
        liquidity = token.get('liquidity', 0)
        volume = token.get('volume_24h', 0)
        age = token.get('age_days', 30)  # If available
        
        # Low liquidity = higher risk
        if liquidity < 10_000:
            risk = 0.7
        elif liquidity < 50_000:
            risk = 0.4
        else:
            risk = 0.1
            
        # Low volume relative to liquidity = higher risk
        if liquidity > 0:
            volume_ratio = volume / liquidity
            if volume_ratio < 0.1:
                risk += 0.2
                
        return min(0.95, max(0.05, risk))
        
    def _estimate_social_sentiment(self, token: Dict) -> float:
        """Estimate social sentiment from price action."""
        price_change = token.get('price_change_24h', 0)
        
        # Strong price movement = high social activity
        sentiment = 0.5 + (price_change / 10)  # Normalize
        return min(0.9, max(0.1, sentiment))
        
    def _estimate_market_regime(self, token: Dict) -> int:
        """Estimate current market regime from price action."""
        change_1h = token.get('price_change_1h', 0)
        change_24h = token.get('price_change_24h', 0)
        
        avg_change = (change_1h + change_24h) / 2
        
        if avg_change > 2:
            return 1  # Bull
        elif avg_change < -2:
            return 2  # Bear
        else:
            return 0  # Sideways
            
    def _estimate_smart_money_flow(self, token: Dict) -> float:
        """Estimate smart money activity from volume patterns."""
        volume = token.get('volume_24h', 0)
        liquidity = token.get('liquidity', 0)
        
        if volume <= 0 or liquidity <= 0:
            return 0.5
            
        # High volume in low liquidity = smart money activity
        ratio = volume / liquidity
        return min(0.8, max(0.2, ratio * 0.3 + 0.2))
        
    def _generate_order_book(self, price: float, side: str) -> List[float]:
        """Generate synthetic order book data."""
        if price <= 0:
            price = 0.001
            
        orders = []
        for i in range(10):
            if side == 'bid':
                # Bids are below current price
                order_price = price * (1 - (i + 1) * 0.001)
            else:
                # Asks are above current price
                order_price = price * (1 + (i + 1) * 0.001)
                
            # Volume decreases with distance
            volume = 1000 / (i + 1)
            orders.append(volume)
            
        return orders
        
    def _estimate_volume_profile(self, token: Dict) -> float:
        """Estimate volume profile strength."""
        volume = token.get('volume_24h', 0)
        liquidity = token.get('liquidity', 0)
        
        if volume <= 0 or liquidity <= 0:
            return 0.5
            
        # High volume relative to liquidity = strong volume profile
        ratio = volume / liquidity
        return min(0.9, max(0.1, ratio * 0.4 + 0.3))


def enrich_token(token: Dict, config: Dict = None) -> Dict:
    """Convenience function to enrich a single token."""
    enricher = TokenEnricher(config)
    return enricher.enrich(token)


def enrich_tokens(tokens: List[Dict], config: Dict = None) -> List[Dict]:
    """Enrich multiple tokens."""
    enricher = TokenEnricher(config)
    return [enricher.enrich(t) for t in tokens]
```

### Step 2: Integrate TokenEnricher into Pipeline

Edit `/home/damien/ecosystem/trading/token_pipeline/token_normalizer.py`:

```python
from .token_enricher import TokenEnricher

class TokenNormalizer:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.enricher = TokenEnricher(self.config.get('enrichment', {}))
        
    def normalize(self, token: Dict) -> Dict:
        # ... existing normalization ...
        
        # NEW: Enrich token with computed fields
        normalized = self.enricher.enrich(normalized)
        
        return normalized
```

### Step 3: Update Config

Add to `config/config_unified.yaml`:

```yaml
token_enrichment:
  enabled: true
  price_history_length: 20
  default_volatility: 0.02
  
strategies:
  # Enable more strategies (they now have data)
  momentum: true
  mean_reversion: true
  breakout: true
  volatility_breakout: true
  aggressive: true
  risk_caps: true
  smart_money: true
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `/home/damien/ecosystem/trading/token_pipeline/token_enricher.py` | Create |
| `/home/damien/ecosystem/trading/token_pipeline/token_normalizer.py` | Modify |
| `/home/damien/ecosystem/config/config_unified.yaml` | Modify |
| `/home/damien/ecosystem/main.py` | Modify (config) |

---

## Expected Result

After implementing token enrichment:
- All 8 strategies will generate signals
- Strategy selection will pick the best signal (not just RiskCapsStrategy)
- More diverse trading decisions
- Better capital allocation across strategies

