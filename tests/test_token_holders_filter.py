import asyncio


async def test_tokenmetadata_without_holders_not_filtered():
    from scanners.hybrid_scanner import EliteHybridScanner
    from utils.memory import MemoryManager, TokenMetadata

    # Setup memory and add a TokenMetadata that has no holders attribute
    mem = MemoryManager()
    token = TokenMetadata(symbol='XTOKEN', address='0xabcde0000000000000000000000000000000000', chain='ethereum', price=1.0, volume_24h=1000.0, liquidity_usd=5000.0)
    # Ensure address stored in same format as MemoryManager (lowercase)
    mem.tokens[token.address] = token

    # Configure scanner with a positive min_holders so naive implementations would filter out
    scanner = EliteHybridScanner(config={
        'min_holders': 100,
        'min_liquidity_usd': 0,
        'min_volume_24h_usd': 0,
        'data_freshness_hours': 8760
    }, memory=mem)

    # Call internal filter directly
    result = await scanner._passes_filters(token)
    assert result is True, "TokenMetadata without holders should not be filtered by min_holders"

if __name__ == '__main__':
    import sys
    ok = asyncio.run(test_tokenmetadata_without_holders_not_filtered())
    print('PASS' if ok is None else ok)
