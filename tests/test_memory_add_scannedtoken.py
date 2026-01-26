import asyncio


async def test_add_scanned_token_with_holders():
    from utils.memory import MemoryManager
    from trading.token_pipeline.token_normalizer import TokenNormalizer

    mem = MemoryManager()

    # Create a raw token dict and normalize it
    raw = {
        'address': '0xAbCd000000000000000000000000000000000000',
        'symbol': 'NEW',
        'name': 'New Token',
        'decimals': 18,
        'price': 1.5,
        'volume_24h': 1000,
        'liquidity_usd': 5000,
        'holders': 123
    }

    normalizer = TokenNormalizer()
    token = normalizer.normalize_trade_engine(raw)
    added = mem.add_token(token)
    assert added is True
    # Retrieve token from memory and ensure holders saved
    t = mem.get_token('0xabcd000000000000000000000000000000000000')
    assert t is not None
    print('Holders in DB:', mem.cursor.execute("SELECT holders FROM tokens WHERE address = ?", ('0xabcd000000000000000000000000000000000000',)).fetchone())

if __name__ == '__main__':
    asyncio.run(test_add_scanned_token_with_holders())
    print('PASS')
