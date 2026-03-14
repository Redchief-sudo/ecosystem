import asyncio


async def test_onchain_client_verification_and_creation():
    from utils.onchain_client import OnchainClient

    # Minimal config - no external explorer available
    client = OnchainClient({'explorer_api_keys': {}, 'explorer_urls': {}, 'alchemy_urls': {}}, web3_instances={})

    # Without web3 or explorer, these should return safe fallbacks
    verified = await client.is_contract_verified('0x0000000000000000000000000000000000000000', 'ethereum')
    assert verified is False

    creation = await client.get_contract_creation('0x0000000000000000000000000000000000000000', 'ethereum')
    assert creation == (0, '')

    holders = await client.get_holder_count('0x0000000000000000000000000000000000000000', 'ethereum')
    assert holders is None

    print('PASS')

if __name__ == '__main__':
    ok = asyncio.run(test_onchain_client_verification_and_creation())
    print('PASS' if ok is None else ok)
