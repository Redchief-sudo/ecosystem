import pytest

from utils.memory import MemoryManager


@pytest.mark.asyncio
async def test_memory_manager_add_get_and_health():
    # Use in-memory SQLite to avoid filesystem side effects
    mem = MemoryManager(db_path=':memory:')

    # Initially no tokens -> health should be degraded
    health = await mem.health_check()
    assert not health.status
    assert health.metrics['token_count'] == 0

    # Add a token
    token_data = {
        'address': '0xabc',
        'symbol': 'TKN',
        'chain': 'ethereum',
        'price': 1.23,
        'volume_24h': 1000.0,
        'liquidity_usd': 500.0
    }
    assert mem.add_token(token_data)

    # Retrieve and verify
    token = mem.get_token('0xabc')
    assert token is not None
    assert token.symbol == 'TKN'
    assert token.price == 1.23

    # Health should now report token_count >= 1
    health2 = await mem.health_check()
    assert health2.status or health2.metrics['token_count'] >= 1

    # Cleanup
    mem.close()