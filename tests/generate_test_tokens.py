"""
Test token generator for decision flow testing.
Run this to generate test tokens that will be processed by the trading engine.
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

test_tokens = [
    # High quality tokens (will be approved)
    {
        "symbol": f"GOOD_{i}",
        "price": round(10 + random.random() * 100, 4),
        "volume_24h": random.randint(1000000, 5000000),
        "liquidity": random.randint(500000, 2000000),
        "token_address": f"0x{'a' * 40}",
        "chain_id": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    } 
    for i in range(5)
] + [
    # Low quality tokens (will be rejected)
    {
        "symbol": f"BAD_{i}",
        "price": round(0.0001 + random.random(), 6),
        "volume_24h": random.randint(100, 1000),
        "liquidity": random.randint(10, 100),
        "token_address": f"0x{'b' * 40}",
        "chain_id": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    }
    for i in range(3)
]

def get_test_tokens():
    """Return a batch of test tokens"""
    # Return a copy of the test tokens
    return [dict(token) for token in test_tokens]

if __name__ == "__main__":
    # Print sample tokens
    import json
    print(json.dumps(get_test_tokens(), indent=2))
