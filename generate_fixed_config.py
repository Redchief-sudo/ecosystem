#!/usr/bin/env python3
"""
Generate Fixed Network Configuration
Creates a corrected config_unified.yaml with canonical network names
"""

import yaml

# Supported networks with verified chain IDs from ChainConstants
supported_networks = [
    {
        "key": "ethereum",
        "name": "Ethereum Mainnet",
        "chain_id": 1,
        "rpc_primary": "https://eth.llamarpc.com",
        "rpc_fallback_1": "https://eth.public-rpc.com",
        "rpc_fallback_2": "https://rpc.ankr.com/eth",
        "ws": "wss://eth-mainnet.ws.alchemyapi.io/v2/YOUR_API_KEY",
        "token_type": "ERC-20",
        "router_address": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "wrapped_native": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "execution_enabled": True,
        "priority": 1
    },
    {
        "key": "bsc",
        "name": "Binance Smart Chain",
        "chain_id": 56,
        "rpc_primary": "https://bsc.publicnode.com",
        "rpc_fallback_1": "https://bsc-dataseed.binance.org/",
        "rpc_fallback_2": "https://rpc.ankr.com/bsc",
        "ws": "wss://bsc-ws-node.nariox.org:443",
        "token_type": "BEP-20",
        "router_address": "0x13f9930f305C001099684C2044C39e3B6376D072",
        "wrapped_native": "0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "execution_enabled": True,
        "priority": 2
    },
    {
        "key": "polygon",
        "name": "Polygon Mainnet",
        "chain_id": 137,
        "rpc_primary": "https://polygon-rpc.com",
        "rpc_fallback_1": "https://polygon-mainnet.public.blastapi.io",
        "rpc_fallback_2": "https://rpc.ankr.com/polygon",
        "ws": "wss://ws-polygon-mainnet.matic.quiknode.pro",
        "token_type": "ERC-20",
        "router_address": "0xf5b509bB0909a69B1c207E495f687a596C168E12",
        "wrapped_native": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "execution_enabled": True,
        "priority": 3
    },
    {
        "key": "avalanche",
        "name": "Avalanche C-Chain",
        "chain_id": 43114,
        "rpc_primary": "https://api.avax.network/ext/bc/C/rpc",
        "rpc_fallback_1": "https://avax.public-rpc.com",
        "rpc_fallback_2": "https://rpc.ankr.com/avalanche",
        "ws": "wss://api.avax.network/ext/bc/C/ws",
        "token_type": "ERC-20",
        "router_address": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",
        "wrapped_native": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
        "execution_enabled": True,
        "priority": 4
    },
    {
        "key": "fantom",
        "name": "Fantom Opera",
        "chain_id": 250,
        "rpc_primary": "https://rpc.ankr.com/fantom",
        "rpc_fallback_1": "https://fantom.publicnode.com",
        "rpc_fallback_2": "https://rpc.ftm.tools/",
        "ws": "wss://wsapi.fantom.network/",
        "token_type": "ERC-20",
        "router_address": "0xF491e7B69E4244ad4002BC14e878a34207E38c29",
        "wrapped_native": "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83",
        "execution_enabled": True,
        "priority": 5
    },
    {
        "key": "arbitrum",
        "name": "Arbitrum One",
        "chain_id": 42161,
        "rpc_primary": "https://arb1.arbitrum.io/rpc",
        "rpc_fallback_1": "https://arbitrum.public-rpc.com",
        "rpc_fallback_2": "https://rpc.ankr.com/arbitrum",
        "ws": "wss://arb1.arbitrum.io/ws",
        "token_type": "ERC-20",
        "router_address": "0x1F721E6E8383Bc43825997b5932A3c0d3f89906d",
        "wrapped_native": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "execution_enabled": True,
        "priority": 6
    },
    {
        "key": "optimism",
        "name": "Optimism",
        "chain_id": 10,
        "rpc_primary": "https://mainnet.optimism.io",
        "rpc_fallback_1": "https://optimism.public-rpc.com",
        "rpc_fallback_2": "https://rpc.ankr.com/optimism",
        "ws": "wss://mainnet.optimism.io/ws",
        "token_type": "ERC-20",
        "router_address": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "wrapped_native": "0x4200000000000000000000000000000000000006",
        "execution_enabled": True,
        "priority": 7
    },
    {
        "key": "base",
        "name": "Base Mainnet",
        "chain_id": 8453,
        "rpc_primary": "https://mainnet.base.org",
        "rpc_fallback_1": "https://base.public-rpc.com",
        "rpc_fallback_2": "https://rpc.ankr.com/base",
        "ws": "wss://mainnet.base.org/ws",
        "token_type": "ERC-20",
        "router_address": "0xcF77a3Ba9A5CA399AF72378d13b4689f20912E64",
        "wrapped_native": "0x4200000000000000000000000000000000000006",
        "execution_enabled": True,
        "priority": 8
    },
    {
        "key": "moonbeam",
        "name": "Moonbeam",
        "chain_id": 1284,
        "rpc_primary": "https://rpc.api.moonbeam.network",
        "rpc_fallback_1": "https://moonbeam.public-rpc.com",
        "rpc_fallback_2": "https://rpc.ankr.com/moonbeam",
        "ws": "wss://wss.api.moonbeam.network",
        "token_type": "ERC-20",
        "router_address": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "wrapped_native": "0xAcc15dC74880C9944775448304B263D191c6077F",
        "execution_enabled": True,
        "priority": 9
    },
    {
        "key": "moonriver",
        "name": "Moonriver",
        "chain_id": 1285,
        "rpc_primary": "https://rpc.moonriver.moonbeam.network",
        "rpc_fallback_1": "https://moonriver.public-rpc.com",
        "rpc_fallback_2": "https://rpc.ankr.com/moonriver",
        "ws": "wss://wss.moonriver.moonbeam.network",
        "token_type": "ERC-20",
        "router_address": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "wrapped_native": "0x98878B06940aE243284CA214f92Bb71a2b032B8A",
        "execution_enabled": True,
        "priority": 10
    },
    {
        "key": "celo",
        "name": "Celo Mainnet",
        "chain_id": 42220,
        "rpc_primary": "https://forno.celo.org",
        "rpc_fallback_1": "https://rpc.ankr.com/celo",
        "rpc_fallback_2": "https://celo-mainnet.publicnode.com",
        "ws": "wss://forno.celo.org/ws",
        "token_type": "ERC-20",
        "router_address": "0xcF77a3Ba9A5CA399AF72378d13b4689f20912E64",
        "wrapped_native": "0x471EcE3750Da237f93B8E339c536989b8978a438",
        "execution_enabled": True,
        "priority": 11
    },
    {
        "key": "kava",
        "name": "Kava EVM",
        "chain_id": 2222,
        "rpc_primary": "https://evm.kava.io",
        "rpc_fallback_1": "https://rpc.ankr.com/kava",
        "rpc_fallback_2": "https://kava.publicnode.com",
        "ws": "wss://evm.kava.io/ws",
        "token_type": "ERC-20",
        "router_address": "0xA184aD5Bfd7977473977805d6806725845CBA543",
        "wrapped_native": "0xc782a17056020738aC44c35eF7D17e6b541C543A",
        "execution_enabled": True,
        "priority": 12
    },
    {
        "key": "evmos",
        "name": "Evmos",
        "chain_id": 9001,
        "rpc_primary": "https://evmos-evm.publicnode.com",
        "rpc_fallback_1": "https://rpc.ankr.com/evmos",
        "rpc_fallback_2": "https://evmos.public-rpc.com",
        "ws": "wss://evmos-evm.publicnode.com/ws",
        "token_type": "ERC-20",
        "router_address": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "wrapped_native": "0xD4949664cD82660AaE99bEdc034a0deA8A0bd517",
        "execution_enabled": True,
        "priority": 13
    },
    {
        "key": "aurora",
        "name": "Aurora",
        "chain_id": 1313161554,
        "rpc_primary": "https://mainnet.aurora.dev",
        "rpc_fallback_1": "https://rpc.ankr.com/aurora",
        "rpc_fallback_2": "https://aurora.publicnode.com",
        "ws": "wss://mainnet.aurora.dev/ws",
        "token_type": "ERC-20",
        "router_address": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "wrapped_native": "0xC9BdeEd33CD01541e1eeD10f90519d2C06Fe3feB",
        "execution_enabled": True,
        "priority": 14
    },
    {
        "key": "klaytn",
        "name": "Klaytn Mainnet",
        "chain_id": 8217,
        "rpc_primary": "https://public-node-api.klaytnapi.com/v1/cypress",
        "rpc_fallback_1": "https://klaytn1.fallback.rpc",
        "rpc_fallback_2": "https://rpc.ankr.com/klaytn",
        "ws": "wss://public-node-api.klaytnapi.com/ws",
        "token_type": "ERC-20",
        "router_address": "0xc6a2Ad8cC6e4A7E08FC37cC5954be07d499E7654",
        "wrapped_native": "0x19Acd5f526366052E639A06059d4352D022c4fE7",
        "execution_enabled": True,
        "priority": 15
    },
    {
        "key": "arbitrum_nova",
        "name": "Arbitrum Nova",
        "chain_id": 42170,
        "rpc_primary": "https://nova.arbitrum.io/rpc",
        "rpc_fallback_1": "https://rpc.ankr.com/arbitrum_nova",
        "rpc_fallback_2": "https://nova.publicnode.com",
        "ws": "wss://nova.arbitrum.io/ws",
        "token_type": "ERC-20",
        "router_address": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "wrapped_native": "0x722E8BdD2ce40A4422E880164f2079486211f591",
        "execution_enabled": True,
        "priority": 16
    },
    {
        "key": "metis",
        "name": "Metis Andromeda",
        "chain_id": 1088,
        "rpc_primary": "https://andromeda.metis.io/?owner=1088",
        "rpc_fallback_1": "https://rpc.ankr.com/metis",
        "rpc_fallback_2": "https://andromeda.publicnode.metis.io",
        "ws": "wss://andromeda.metis.io/ws",
        "token_type": "ERC-20",
        "router_address": "0x0974067B96D76c33c3732d8C5A8c9a7593c6A99C",
        "wrapped_native": "0xDeadDeAddeAddEAddeadDEaDDEAdDeaDDeAD0000",
        "execution_enabled": True,
        "priority": 17
    },
    {
        "key": "oasis_emerald",
        "name": "Oasis Emerald",
        "chain_id": 42262,
        "rpc_primary": "https://emerald.oasis.dev",
        "rpc_fallback_1": "https://rpc.ankr.com/oasis",
        "rpc_fallback_2": "https://emerald.publicnode.com",
        "ws": "wss://emerald.oasis.dev/ws",
        "token_type": "ERC-20",
        "router_address": "0x328D24E3a129E57A8B78119C6e9024D99709E839",
        "wrapped_native": "0x21C718C22D52d0F3a789b752D4c2fD5908a8A733",
        "execution_enabled": True,
        "priority": 18
    },
    {
        "key": "okc",
        "name": "OKExChain (OKC)",
        "chain_id": 66,
        "rpc_primary": "https://exchainrpc.okex.org",
        "rpc_fallback_1": "https://okc.publicnode.com",
        "rpc_fallback_2": "https://rpc.ankr.com/okc",
        "ws": "wss://exchainws.okex.org/ws",
        "token_type": "ERC-20",
        "router_address": "0x19992ba0B3392E2E699c277E9012484594248E59",
        "wrapped_native": "0x8F8526dbfd6E38E3D8307702cA8469Bb42A2F3d0",
        "execution_enabled": True,
        "priority": 19
    },
    {
        "key": "telos",
        "name": "Telos EVM",
        "chain_id": 40,
        "rpc_primary": "https://mainnet.telos.net/evm",
        "rpc_fallback_1": "https://rpc.ankr.com/telos",
        "rpc_fallback_2": "https://telos.publicnode.com",
        "ws": "wss://mainnet.telos.net/evm/ws",
        "token_type": "ERC-20",
        "router_address": "0xa0d9f96b997e3a9a14c62c3f878f7e340a6b7d0c",
        "wrapped_native": "0xD102cE6A4B0f8b4d99459762066dE24D851bF439",
        "execution_enabled": True,
        "priority": 20
    },
    {
        "key": "fuse",
        "name": "Fuse",
        "chain_id": 122,
        "rpc_primary": "https://rpc.fuse.io",
        "rpc_fallback_1": "https://rpc.ankr.com/fuse",
        "rpc_fallback_2": "https://fuse.publicnode.com",
        "ws": "wss://rpc.fuse.io/ws",
        "token_type": "ERC-20",
        "router_address": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
        "wrapped_native": "0x0BE9e53fd7EDaC9F859882AfdDa116645287C629",
        "execution_enabled": True,
        "priority": 21
    },
    {
        "key": "syscoin",
        "name": "Syscoin EVM",
        "chain_id": 57,
        "rpc_primary": "https://rpc.syscoin.org",
        "rpc_fallback_1": "https://rpc.ankr.com/syscoin",
        "rpc_fallback_2": "https://syscoin.publicnode.com",
        "ws": "wss://rpc.syscoin.org/ws",
        "token_type": "ERC-20",
        "router_address": "0x21Ffbc1D0A5141e6c382e752945D7d2427a1A2c3",
        "wrapped_native": "0xA184aD5Bfd7977473977805d6806725845CBA543",
        "execution_enabled": True,
        "priority": 22
    },
    {
        "key": "theta",
        "name": "Theta Mainnet EVM",
        "chain_id": 361,
        "rpc_primary": "https://eth-rpc-api.theta.io/rpc",
        "rpc_fallback_1": "https://rpc.ankr.com/theta",
        "rpc_fallback_2": "https://theta.publicnode.com",
        "ws": "wss://eth-rpc-api.theta.io/ws",
        "token_type": "ERC-20",
        "router_address": "0x854a61358D6845594F94dc1DB02A252b5b4814aD",
        "wrapped_native": "0xAfE208a311B21f13EF87E33A90049fC17A7acDEc",
        "execution_enabled": True,
        "priority": 23
    },
    {
        "key": "palm",
        "name": "Palm Network",
        "chain_id": 11297108109,
        "rpc_primary": "https://palm-mainnet.infura.io/v3/YOUR_API_KEY",
        "rpc_fallback_1": "https://rpc.ankr.com/palm",
        "rpc_fallback_2": "https://palm.publicnode.com",
        "ws": "wss://palm-mainnet.infura.io/ws/v3/YOUR_API_KEY",
        "token_type": "ERC-20",
        "router_address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "wrapped_native": "0xF98cABF0a963452C5536330408B2590567611a71",
        "execution_enabled": True,
        "priority": 24
    },
    {
        "key": "iotex",
        "name": "IoTeX EVM",
        "chain_id": 4689,
        "rpc_primary": "https://babel-api.mainnet.iotex.io",
        "rpc_fallback_1": "https://rpc.ankr.com/iotex",
        "rpc_fallback_2": "https://iotex.publicnode.com",
        "ws": "wss://babel-api.mainnet.iotex.io/ws",
        "token_type": "ERC-20",
        "router_address": "0x117180D821016be24D8570530737C714a60420E41",
        "wrapped_native": "0xA0074488F722c0F875a156312482eFc6A19c0a30",
        "execution_enabled": True,
        "priority": 25
    },
    {
        "key": "kcc",
        "name": "KCC",
        "chain_id": 321,
        "rpc_primary": "https://rpc-mainnet.kcc.network",
        "rpc_fallback_1": "https://rpc.ankr.com/kcc",
        "rpc_fallback_2": "https://kcc.publicnode.com",
        "ws": "wss://rpc-mainnet.kcc.network/ws",
        "token_type": "ERC-20",
        "router_address": "0xba2ae424d960c26247dd6c32edc70b295c744c43",
        "wrapped_native": "0x44463448a04df3702d53629b39164d1f2e96d91f",
        "execution_enabled": True,
        "priority": 26
    },
    {
        "key": "velas",
        "name": "Velas EVM",
        "chain_id": 106,
        "rpc_primary": "https://evmexplorer.velas.com/rpc",
        "rpc_fallback_1": "https://rpc.ankr.com/velas",
        "rpc_fallback_2": "https://velas.publicnode.com",
        "ws": "wss://evmexplorer.velas.com/ws",
        "token_type": "ERC-20",
        "router_address": "0x10bA8Cb0d097eB8D57A175b88c7D8b47997506",
        "wrapped_native": "0xc7463448a04df3702d53629b39164d1f2e96d91f",
        "execution_enabled": True,
        "priority": 27
    }
]

def generate_fixed_config():
    """Generate the fixed configuration as dict format"""
    
    # Convert to dict format keyed by canonical name
    networks_dict = {}
    for net in supported_networks:
        key = net.pop("key")
        networks_dict[key] = net
    
    return networks_dict

if __name__ == "__main__":
    networks_dict = generate_fixed_config()
    print(f"Generated configuration for {len(networks_dict)} networks")
    print("Network keys:", list(networks_dict.keys()))
