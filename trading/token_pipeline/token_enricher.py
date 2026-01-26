"""
Token enrichment service - adds missing data fields to tokens.

This module provides data enrichment for tokens so that all strategies
can generate signals. It creates synthetic historical data and estimates
risk metrics based on available token information.
"""

import random
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TokenEnricher:
    """
    Enriches token data with computed fields for strategy evaluation.
    
    Uses:
    - Current price/volume to generate historical data
    - Liquidity as proxy for holder concentration
    - Price volatility as proxy for social sentiment
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.price_history_length = self.config.get('price_history_length', 20)
        self.default_volatility = self.config.get('default_volatility', 0.02)
        self._random = random.Random(42)  # Reproducible results
        
    def enrich(self, token: Dict) -> Dict:
        """Add computed fields to token data."""
        token = token.copy()  # Don't mutate original
        
        # Generate historical data
        if 'price_history' not in token or not token['price_history']:
            token['price_history'] = self._generate_price_history(
                token.get('price', 0.001)
            )
            
        if 'volume_history' not in token or not token.get('volume_history'):
            token['volume_history'] = self._generate_volume_history(
                token.get('volume_24h', 1000)
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
        if 'bids' not in token or not token.get('bids'):
            token['bids'] = self._generate_order_book(token.get('price', 0.001), 'bid')
            
        if 'asks' not in token or not token.get('asks'):
            token['asks'] = self._generate_order_book(token.get('price', 0.001), 'ask')
            
        # Estimate volume profile
        if 'volume_profile' not in token:
            token['volume_profile'] = self._estimate_volume_profile(token)
            
        logger.debug(f"Enriched token {token.get('symbol', 'UNKNOWN')}")
        return token
        
    def _generate_price_history(self, current_price: float) -> List[float]:
        """Generate synthetic price history using random walk."""
        if current_price <= 0:
            current_price = 0.001
            
        prices = [current_price]
        for _ in range(self.price_history_length - 1):
            change = self._random.gauss(0, self.default_volatility)
            new_price = prices[-1] * (1 + change)
            new_price = max(0.00000001, new_price)  # Prevent negative
            prices.append(new_price)
        return prices
        
    def _generate_volume_history(self, current_volume: float) -> List[float]:
        """Generate synthetic volume history."""
        if current_volume <= 0:
            current_volume = 1000
            
        volumes = [current_volume]
        for _ in range(self.price_history_length - 1):
            # Volume tends to be somewhat stable with some variation
            change = self._random.uniform(-0.2, 0.3)
            new_vol = volumes[-1] * (1 + change)
            new_vol = max(100, new_vol)  # Minimum volume
            volumes.append(new_vol)
        return volumes
        
    def _estimate_holder_concentration(self, liquidity: float) -> float:
        """
        Higher liquidity = lower holder concentration (more distributed).
        
        Estimates based on typical token distribution patterns:
        - $1M+ liquidity = ~10-15% top 10 holders
        - $10k liquidity = ~40-60% top 10 holders
        """
        if liquidity <= 0:
            return 0.5  # Unknown, assume moderate
            
        if liquidity > 1_000_000:
            return 0.12
        elif liquidity > 500_000:
            return 0.18
        elif liquidity > 100_000:
            return 0.25
        elif liquidity > 50_000:
            return 0.35
        elif liquidity > 10_000:
            return 0.45
        else:
            return 0.55
            
    def _estimate_whale_activity(self, token: Dict) -> float:
        """
        Estimate whale activity from volume and liquidity.
        
        High volume relative to liquidity suggests whale activity.
        """
        volume = token.get('volume_24h', 0)
        liquidity = token.get('liquidity', 0)
        
        if volume <= 0 or liquidity <= 0:
            return 0.3
            
        ratio = volume / liquidity
        return min(0.7, max(0.1, ratio * 0.4 + 0.1))
        
    def _estimate_rugpull_risk(self, token: Dict) -> float:
        """
        Estimate rugpull risk from token characteristics.
        
        Risk factors:
        - Low liquidity = higher risk
        - Low volume relative to liquidity = higher risk
        - Very new tokens = higher risk
        """
        liquidity = token.get('liquidity', 0)
        volume = token.get('volume_24h', 0)
        
        # Base risk from liquidity
        if liquidity < 10_000:
            risk = 0.6
        elif liquidity < 50_000:
            risk = 0.35
        elif liquidity < 100_000:
            risk = 0.20
        else:
            risk = 0.08
            
        # Additional risk from low volume ratio
        if liquidity > 0:
            volume_ratio = volume / liquidity
            if volume_ratio < 0.05:
                risk += 0.2
            elif volume_ratio < 0.1:
                risk += 0.1
                
        return min(0.9, max(0.05, risk))
        
    def _estimate_social_sentiment(self, token: Dict) -> float:
        """
        Estimate social sentiment from price action.
        
        Strong price movement = high social activity.
        """
        price_change = token.get('price_change_24h', 0)
        
        # Strong price movement suggests active social discussion
        sentiment = 0.5 + (price_change / 20)  # Normalize
        return min(0.85, max(0.15, sentiment))
        
    def _estimate_market_regime(self, token: Dict) -> int:
        """
        Estimate current market regime from price action.
        
        Returns:
            0 = Sideways (neutral)
            1 = Bull (uptrend)
            2 = Bear (downtrend)
        """
        change_1h = token.get('price_change_1h', 0)
        change_24h = token.get('price_change_24h', 0)
        
        avg_change = (change_1h * 0.3 + change_24h * 0.7)  # Weight 24h more
        
        if avg_change > 2:
            return 1  # Bull
        elif avg_change < -2:
            return 2  # Bear
        else:
            return 0  # Sideways
            
    def _estimate_smart_money_flow(self, token: Dict) -> float:
        """
        Estimate smart money activity from volume patterns.
        
        High volume in low liquidity suggests institutional activity.
        """
        volume = token.get('volume_24h', 0)
        liquidity = token.get('liquidity', 0)
        
        if volume <= 0 or liquidity <= 0:
            return 0.5
            
        ratio = volume / liquidity
        return min(0.75, max(0.25, ratio * 0.3 + 0.25))
        
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
                
            # Volume decreases with distance from current price
            volume = 1000 / (i + 1)
            orders.append(volume)
            
        return orders
        
    def _estimate_volume_profile(self, token: Dict) -> float:
        """
        Estimate volume profile strength.
        
        High volume relative to liquidity = strong volume profile.
        """
        volume = token.get('volume_24h', 0)
        liquidity = token.get('liquidity', 0)
        
        if volume <= 0 or liquidity <= 0:
            return 0.5
            
        ratio = volume / liquidity
        return min(0.85, max(0.15, ratio * 0.35 + 0.3))


def enrich_token(token: Dict, config: Optional[Dict] = None) -> Dict:
    """Convenience function to enrich a single token."""
    enricher = TokenEnricher(config)
    return enricher.enrich(token)


def enrich_tokens(tokens: List[Dict], config: Optional[Dict] = None) -> List[Dict]:
    """Enrich multiple tokens."""
    enricher = TokenEnricher(config)
    return [enricher.enrich(t) for t in tokens]

